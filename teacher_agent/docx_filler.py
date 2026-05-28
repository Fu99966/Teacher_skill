from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from docx import Document

from .template_parser import PLACEHOLDER_PATTERN, analyze_template, iter_paragraphs


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


def _replace_placeholders(text: str, data: dict[str, Any]) -> str:
    def replace(match) -> str:
        key = match.group(1).strip()
        if key not in data:
            return match.group(0)
        return _docx_text(data[key])

    return PLACEHOLDER_PATTERN.sub(replace, text)


def _replace_paragraph(paragraph, data: dict[str, Any]) -> None:
    full_text = "".join(run.text for run in paragraph.runs)
    if "{{" not in full_text:
        return

    if not PLACEHOLDER_PATTERN.search(full_text):
        return

    changed_single_run = False
    for run in paragraph.runs:
        if PLACEHOLDER_PATTERN.search(run.text):
            new_text = _replace_placeholders(run.text, data)
            if new_text != run.text:
                run.text = new_text
                changed_single_run = True

    if changed_single_run:
        full_text = "".join(run.text for run in paragraph.runs)
        if not PLACEHOLDER_PATTERN.search(full_text):
            return

    replaced = _replace_placeholders(full_text, data)

    if replaced == full_text or not paragraph.runs:
        return

    paragraph.runs[0].text = replaced
    for run in paragraph.runs[1:]:
        run.text = ""


def _write_paragraph_preserving_style(paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(_docx_text(text))
        return

    paragraph.runs[0].text = _docx_text(text)
    for run in paragraph.runs[1:]:
        run.text = ""


def _write_cell_preserving_layout(cell, value: Any) -> None:
    text = _docx_text(value)
    if not cell.paragraphs:
        cell.add_paragraph(text)
        return

    lines = text.split("\n")
    _write_paragraph_preserving_style(cell.paragraphs[0], lines[0] if lines else "")
    for paragraph in cell.paragraphs[1:]:
        _write_paragraph_preserving_style(paragraph, "")

    for line in lines[1:]:
        paragraph = cell.add_paragraph()
        paragraph.add_run(line)


def _append_cell_preserving_label(cell, value: Any) -> None:
    text = _docx_text(value)
    if not text:
        return
    if not cell.paragraphs:
        cell.add_paragraph(text)
        return

    for paragraph in cell.paragraphs[1:]:
        if not paragraph.text.strip():
            _write_paragraph_preserving_style(paragraph, text)
            return

    paragraph = cell.add_paragraph()
    paragraph.add_run(text)


def _fill_table_mappings(document: Document, data: dict[str, Any], mappings: dict[str, Any]) -> None:
    for field, target in mappings.items():
        if field not in data:
            continue
        mapping_type = target.get("type")
        if mapping_type not in {"table_cell", "table_cell_append"}:
            continue

        table_index = int(target.get("table", -1))
        row_index = int(target.get("row", -1))
        col_index = int(target.get("col", -1))
        if table_index < 0 or row_index < 0 or col_index < 0:
            continue
        if table_index >= len(document.tables):
            continue

        table = document.tables[table_index]
        if row_index >= len(table.rows) or col_index >= len(table.rows[row_index].cells):
            continue

        cell = table.rows[row_index].cells[col_index]
        if mapping_type == "table_cell_append":
            _append_cell_preserving_label(cell, data[field])
        else:
            _write_cell_preserving_layout(cell, data[field])


def fill_docx_template(template_path: str | Path, data: dict[str, Any], output_path: str | Path) -> Path:
    """Fill placeholders in a .docx template while preserving document structure.

    Best result: keep each placeholder as a single Word run in the template.
    The function also handles placeholders split across runs by replacing the
    whole paragraph text with the style of the first run.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = Document(str(template_path))
    for paragraph in iter_paragraphs(document):
        _replace_paragraph(paragraph, data)

    analysis = analyze_template(template_path)
    _fill_table_mappings(document, data, analysis.get("table_mappings", {}))

    document.save(str(output_path))
    return output_path
