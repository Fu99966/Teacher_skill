from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from docx import Document

from .template_parser import PLACEHOLDER_PATTERN, analyze_template, iter_paragraphs, parse_table_grid, get_grid_cell_at


@dataclass
class FillReport:
    output_path: str
    filled_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    empty_fields: list[str] = field(default_factory=list)
    skipped_empty_fields: list[str] = field(default_factory=list)
    unfilled_template_fields: list[str] = field(default_factory=list)
    filled_non_empty_count: int = 0
    remaining_placeholders: list[str] = field(default_factory=list)
    placeholder_fields_filled: list[str] = field(default_factory=list)
    table_fields_filled: list[str] = field(default_factory=list)
    table_write_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return Path(self.output_path)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __fspath__(self) -> str:
        return self.output_path

    def __str__(self) -> str:
        return self.output_path


def _docx_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")
    if isinstance(value, (list, tuple)):
        return "\n".join(_docx_text(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _is_effectively_empty(value: Any) -> bool:
    return not _docx_text(value).strip()


def _add_ordered(target: list[str], field_name: str) -> None:
    if field_name and field_name not in target:
        target.append(field_name)


def _replace_placeholders_in_run(run, data: dict[str, Any], report: FillReport) -> bool:
    original = run.text
    changed = False

    def replace(match) -> str:
        nonlocal changed
        key = match.group(1).strip()
        if key not in data:
            _add_ordered(report.missing_fields, key)
            return match.group(0)
        if _is_effectively_empty(data[key]):
            _add_ordered(report.empty_fields, key)
            _add_ordered(report.skipped_empty_fields, key)
            return match.group(0)
        changed = True
        _add_ordered(report.filled_fields, key)
        _add_ordered(report.placeholder_fields_filled, key)
        return _docx_text(data[key])

    new_text = PLACEHOLDER_PATTERN.sub(replace, original)
    if changed:
        run.text = new_text
    return changed


def _run_ranges(paragraph) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    cursor = 0
    for index, run in enumerate(paragraph.runs):
        start = cursor
        cursor += len(run.text)
        ranges.append((index, start, cursor))
    return ranges


def _replace_cross_run_placeholder(paragraph, match, data: dict[str, Any], report: FillReport) -> bool:
    key = match.group(1).strip()
    if key not in data:
        _add_ordered(report.missing_fields, key)
        return False
    if _is_effectively_empty(data[key]):
        _add_ordered(report.empty_fields, key)
        _add_ordered(report.skipped_empty_fields, key)
        return False

    ranges = _run_ranges(paragraph)
    first_run_index: int | None = None
    last_run_index: int | None = None
    for index, start, end in ranges:
        if end <= match.start() or start >= match.end():
            continue
        if first_run_index is None:
            first_run_index = index
        last_run_index = index
    if first_run_index is None or last_run_index is None:
        return False

    first_run = paragraph.runs[first_run_index]
    first_start = ranges[first_run_index][1]
    last_run = paragraph.runs[last_run_index]
    last_start = ranges[last_run_index][1]
    prefix = first_run.text[: max(0, match.start() - first_start)]
    suffix = last_run.text[max(0, match.end() - last_start) :]
    first_run.text = prefix + _docx_text(data[key]) + suffix
    for run_index in range(first_run_index + 1, last_run_index + 1):
        paragraph.runs[run_index].text = ""
    _add_ordered(report.filled_fields, key)
    _add_ordered(report.placeholder_fields_filled, key)
    return True


def _replace_paragraph(paragraph, data: dict[str, Any], report: FillReport) -> None:
    if "{{" not in paragraph.text:
        return
    for run in paragraph.runs:
        _replace_placeholders_in_run(run, data, report)
    full_text = "".join(run.text for run in paragraph.runs)
    matches = list(PLACEHOLDER_PATTERN.finditer(full_text))
    if not matches:
        return
    for match in reversed(matches):
        _replace_cross_run_placeholder(paragraph, match, data, report)


def _copy_paragraph_style(source, target) -> None:
    target.style = source.style
    target.alignment = source.alignment
    target.paragraph_format.left_indent = source.paragraph_format.left_indent
    target.paragraph_format.right_indent = source.paragraph_format.right_indent
    target.paragraph_format.first_line_indent = source.paragraph_format.first_line_indent
    target.paragraph_format.space_before = source.paragraph_format.space_before
    target.paragraph_format.space_after = source.paragraph_format.space_after
    target.paragraph_format.line_spacing = source.paragraph_format.line_spacing


def _write_paragraph_preserving_style(paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    paragraph.runs[0].text = text
    for run in paragraph.runs[1:]:
        run.text = ""


def _write_cell_preserving_layout(cell, value: Any) -> None:
    text = _docx_text(value)
    if not cell.paragraphs:
        cell.add_paragraph(text)
        return
    lines = text.split("\n")
    template_paragraph = cell.paragraphs[0]
    _write_paragraph_preserving_style(template_paragraph, lines[0] if lines else "")
    for paragraph in cell.paragraphs[1:]:
        _write_paragraph_preserving_style(paragraph, "")
    for line in lines[1:]:
        paragraph = cell.add_paragraph()
        _copy_paragraph_style(template_paragraph, paragraph)
        paragraph.add_run(line)


def _append_cell_preserving_label(cell, value: Any) -> None:
    text = _docx_text(value)
    if not text:
        return
    if not cell.paragraphs:
        cell.add_paragraph(text)
        return
    lines = text.split("\n")
    target = None
    for paragraph in cell.paragraphs[1:]:
        if not paragraph.text.strip():
            target = paragraph
            break
    if target is None:
        target = cell.add_paragraph()
        _copy_paragraph_style(cell.paragraphs[0], target)
    _write_paragraph_preserving_style(target, lines[0] if lines else "")
    for line in lines[1:]:
        paragraph = cell.add_paragraph()
        _copy_paragraph_style(target, paragraph)
        paragraph.add_run(line)


def _resolve_table(document: Document, target: dict[str, Any]):
    location = target.get("location") or "body_table"
    table_index = int(target.get("table", -1))
    if table_index < 0:
        return None
    if location == "header_table":
        section_index = int(target.get("section") or 0)
        if section_index >= len(document.sections):
            return None
        return document.sections[section_index].header.tables[table_index] if table_index < len(document.sections[section_index].header.tables) else None
    elif location == "footer_table":
        section_index = int(target.get("section") or 0)
        if section_index >= len(document.sections):
            return None
        return document.sections[section_index].footer.tables[table_index] if table_index < len(document.sections[section_index].footer.tables) else None
    else:
        return document.tables[table_index] if table_index < len(document.tables) else None


def _fill_one_table_target(
    document: Document,
    field_name: str,
    value: str,
    target: dict[str, Any],
    report: FillReport,
) -> bool:
    """Write content to a single table target using grid-based cell lookup."""
    mapping_type = target.get("type")
    if mapping_type not in {"table_cell", "table_cell_append"}:
        return False

    row_index = int(target.get("row", -1))
    if row_index < 0:
        return False

    table = _resolve_table(document, target)
    if table is None:
        return False

    # ── Grid-based cell lookup ──
    grid = parse_table_grid(table)
    grid_col = target.get("grid_col", target.get("col", -1))
    if grid_col < 0:
        # fallback: use physical col
        col_physical = int(target.get("col", -1))
        if col_physical < 0:
            return False
        if row_index >= len(table.rows) or col_physical >= len(table.rows[row_index].cells):
            return False
        cell = table.rows[row_index].cells[col_physical]
    else:
        cell = get_grid_cell_at(table, grid, row_index, grid_col)
        if cell is None:
            # fallback to physical col
            col_physical = int(target.get("physical_col", int(target.get("col", 0))))
            if row_index >= len(table.rows) or col_physical >= len(table.rows[row_index].cells):
                return False
            cell = table.rows[row_index].cells[col_physical]

    if cell is None:
        return False

    if mapping_type == "table_cell_append":
        _append_cell_preserving_label(cell, value)
    else:
        _write_cell_preserving_layout(cell, value)

    report.table_write_count += 1
    return True


def _fill_table_mappings(
    document: Document,
    data: dict[str, Any],
    mappings: dict[str, list[dict[str, Any]]],
    report: FillReport,
) -> None:
    for field_name, targets in mappings.items():
        if field_name not in data:
            _add_ordered(report.missing_fields, field_name)
            continue
        if _is_effectively_empty(data[field_name]):
            _add_ordered(report.empty_fields, field_name)
            _add_ordered(report.skipped_empty_fields, field_name)
            continue

        value = data[field_name]
        wrote_any = False
        for target in targets:
            if _fill_one_table_target(document, field_name, value, target, report):
                wrote_any = True

        if wrote_any:
            _add_ordered(report.filled_fields, field_name)
            _add_ordered(report.table_fields_filled, field_name)


def _remaining_placeholders(document: Document) -> list[str]:
    fields: list[str] = []
    for paragraph in iter_paragraphs(document):
        for match in PLACEHOLDER_PATTERN.finditer(paragraph.text):
            _add_ordered(fields, match.group(1).strip())
    return fields


def fill_docx_template(template_path: str | Path, data: dict[str, Any], output_path: str | Path) -> FillReport:
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    analysis = analyze_template(template_path)
    report = FillReport(output_path=str(output_path))

    document = Document(str(template_path))
    for paragraph in iter_paragraphs(document):
        _replace_paragraph(paragraph, data, report)

    _fill_table_mappings(document, data, analysis.get("table_mappings", {}), report)

    for field_name in analysis.get("mapped_fields", []):
        if field_name not in data:
            _add_ordered(report.missing_fields, field_name)
        elif _is_effectively_empty(data[field_name]):
            _add_ordered(report.empty_fields, field_name)
            _add_ordered(report.skipped_empty_fields, field_name)
        if field_name not in report.filled_fields:
            _add_ordered(report.unfilled_template_fields, field_name)

    report.remaining_placeholders = _remaining_placeholders(document)
    report.filled_non_empty_count = len(report.filled_fields)
    template_field_count = len(analysis.get("mapped_fields", []))
    if template_field_count > 0 and report.filled_non_empty_count == 0:
        report.errors.append("生成失败：检测到输出可能为空白模板，未写入任何非空字段。")
    elif template_field_count > 0 and report.filled_non_empty_count < max(1, template_field_count * 0.5):
        report.warnings.append("警告：本次只填入少量模板字段，请检查字段映射和生成结果。")
    document.save(str(output_path))
    return report
