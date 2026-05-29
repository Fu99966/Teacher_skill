from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.oxml.ns import qn

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^{}\r\n\t<>]+?)\s*\}\}")

# ── Field label mapping ──
# "主要教学内容" MUST map to teaching_process, NOT lesson_title.
FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "lesson_title": ("课题", "课题名称", "题目", "课题（含章节号）", "课题(含章节号)"),
    "subject": ("学科", "课程", "课程名称", "科目"),
    "grade": ("年级", "授课年级", "适用年级"),
    "class_name": ("班级", "授课班级"),
    "class_type": ("授课类型", "课型"),
    "class_hour": ("课时", "课时安排", "授课课时", "学时", "课时数"),
    "teaching_date": ("授课日期",),
    "teaching_goals": (
        "教学目的", "教学目的与要求", "教学目的及要求",
        "教学目标", "教学目标与要求", "教学目标及要求",
        "学习目标", "核心素养目标", "知识目标", "能力目标", "情感目标",
    ),
    "key_points": ("教学重点", "重点", "重点内容"),
    "difficult_points": ("教学难点", "难点", "难点内容"),
    "teaching_key_difficult": ("教学重难点", "重难点", "教学重点与难点", "重点难点", "重点和难点"),
    "teaching_preparation": ("教学准备", "课前准备", "教具准备", "教学资源"),
    "teaching_environment": ("对教学环境的要求", "教学环境", "教学环境要求"),
    "teaching_aids": ("教具挂图", "教具", "挂图", "教学用具", "教学挂图"),
    "student_analysis": ("学情分析", "学生分析", "学习者分析"),
    "teaching_process": (
        "主要教学内容", "教学内容", "主要教学内容安排",
        "教学过程", "教学流程", "教学环节", "课堂过程", "过程设计", "教学活动",
    ),
    "teaching_method": (
        "教学方法的运用", "教学方法运用", "教学方法",
        "教法", "学法", "教学方式",
    ),
    "teacher_activity": ("教师活动", "教师行为", "教师指导"),
    "student_activity": ("学生活动", "学生行为", "学习活动"),
    "design_intent": ("设计意图", "设计说明", "活动意图"),
    "blackboard_design": ("板书设计", "板书", "板书规划"),
    "homework": ("作业设计", "作业", "课后作业", "课后任务"),
    "reflection": ("课后小记", "课后小结", "教学反思", "课后反思", "教学后记"),
}

# Fields that MUST prefer next-row fill over right-side fill
NEXT_ROW_PREFERRED_FIELDS = {"teaching_process", "teaching_method"}

# All known aliases sorted by length (longer = higher priority)
FIELD_LABELS_BY_ALIAS: list[tuple[str, str]] = sorted(
    [(f, a) for f, aliases in FIELD_LABELS.items() for a in aliases],
    key=lambda x: -len(x[1]),
)


DIRECT_LABEL_FIELDS = {
    "教材分析", "课程标准", "核心素养", "学习任务", "学习活动",
    "评价任务", "评价标准", "教学评价", "教学资源", "信息技术应用",
    "课堂小结", "课后拓展", "安全教育", "德育渗透", "跨学科融合",
    "二次备课", "个性化修改", "教研组意见", "审批意见",
    "授课日期", "授课班级", "授课类型", "准备",
}


# ── GridCell: true OOXML cell representation ───────────────────────────

@dataclass
class GridCell:
    """Represents one real cell in a Word table grid."""
    row: int
    physical_col: int      # index within row.cells
    grid_col: int          # true OOXML grid column
    grid_span: int         # w:gridSpan value
    text: str
    normalized_text: str
    cell: Any              # python-docx Cell proxy


# ── Real OOXML grid parsing ────────────────────────────────────────────

def parse_table_grid(table) -> list[list[GridCell]]:
    """Parse a Word table's OOXML grid to build true grid layout.

    Reads w:tblGrid for total columns, then iterates each w:tr and
    each w:tc to compute grid_col from gridSpan.
    Handles vertical merges (w:vMerge) by repeating cell into subsequent rows.

    Returns: grid[row_index][grid_col_index] = GridCell
    """
    tbl = table._tbl

    # Read total grid columns from w:tblGrid
    tbl_grid = tbl.find(qn('w:tblGrid'))
    num_cols = 0
    if tbl_grid is not None:
        for grid_col_el in tbl_grid.findall(qn('w:gridCol')):
            num_cols += 1
    # Fallback: count max columns from first row
    if num_cols <= 0:
        for tr in tbl.findall(qn('w:tr')):
            span_total = 0
            for tc in tr.findall(qn('w:tc')):
                tc_pr = tc.find(qn('w:tcPr'))
                gs = 1
                if tc_pr is not None:
                    gs_el = tc_pr.find(qn('w:gridSpan'))
                    if gs_el is not None and gs_el.get(qn('w:val')):
                        gs = int(gs_el.get(qn('w:val')))
                span_total += gs
            if span_total > num_cols:
                num_cols = span_total

    if num_cols <= 0:
        num_cols = max((len(row.cells) for row in table.rows), default=2)

    # Build grid row-by-row from OOXML
    grid: list[list[GridCell | None]] = []
    vmerge_carry: dict[int, GridCell] = {}  # grid_col → cell carried from prev row

    for row_index, row in enumerate(table.rows):
        row_grid: list[GridCell | None] = [None] * num_cols
        tc_elements = row._tr.findall(qn('w:tc'))
        physical_idx = 0
        grid_col = 0

        for tc in tc_elements:
            # Skip if this grid_col was filled by a vMerge carry from previous row
            while grid_col < num_cols and row_grid[grid_col] is not None:
                grid_col += 1
            if grid_col >= num_cols:
                break

            tc_pr = tc.find(qn('w:tcPr'))
            grid_span = 1
            is_vmerge_continue = False
            is_vmerge_restart = False

            if tc_pr is not None:
                gs_el = tc_pr.find(qn('w:gridSpan'))
                if gs_el is not None and gs_el.get(qn('w:val')):
                    grid_span = int(gs_el.get(qn('w:val')))

                vm_el = tc_pr.find(qn('w:vMerge'))
                if vm_el is not None:
                    val = vm_el.get(qn('w:val'))
                    if val == 'restart':
                        is_vmerge_restart = True
                    else:
                        is_vmerge_continue = True

            # Get text
            cell_proxy = table.cell(row_index, physical_idx) if physical_idx < len(row.cells) else None
            text = ""
            normalized = ""
            if cell_proxy is not None:
                text = "\n".join(p.text for p in cell_proxy.paragraphs).strip()
                normalized = re.sub(r"[\s:：；;、，,。.·\-—–（）()\[\]【】<>《》]+", "", text)

            gcell = GridCell(
                row=row_index,
                physical_col=physical_idx,
                grid_col=grid_col,
                grid_span=grid_span,
                text=text,
                normalized_text=normalized,
                cell=cell_proxy,
            )

            # Place in grid
            for g in range(grid_span):
                pos = grid_col + g
                if pos < num_cols:
                    row_grid[pos] = gcell

            # Handle vMerge: carry to next row
            if is_vmerge_restart or is_vmerge_continue:
                # Find the original cell this continues
                base_gcell = gcell
                if is_vmerge_continue:
                    base_gcell = vmerge_carry.get(grid_col, gcell)
                for g in range(grid_span):
                    vmerge_carry[grid_col + g] = base_gcell
            elif not is_vmerge_continue:
                # Clear carry for this column
                for g in range(grid_span):
                    vmerge_carry.pop(grid_col + g, None)

            grid_col += grid_span
            physical_idx += 1

        # Fill vMerge carries that weren't covered by explicit tc elements
        for gcol, carry_cell in list(vmerge_carry.items()):
            if row_grid[gcol] is None:
                # Extend the carry cell into this row
                carry_cell.grid_span = 1  # per-column carry
                row_grid[gcol] = carry_cell

        grid.append(row_grid)

    return grid


def get_grid_cell_at(table, grid: list[list[GridCell]], row: int, grid_col: int) -> Any | None:
    """Get the python-docx Cell at a given (row, grid_col) in the grid."""
    if row < 0 or row >= len(grid):
        return None
    row_grid = grid[row]
    if grid_col < 0 or grid_col >= len(row_grid):
        return None
    gcell = row_grid[grid_col]
    if gcell is None:
        return None
    return gcell.cell


# ── Helpers ────────────────────────────────────────────────────────────

def _sanitize_field_name(text: str) -> str:
    return re.sub(r"[\r\n\t<>]", "", str(text or "")).replace("{{", "").replace("}}", "").strip()


def _normalize_label(text: str) -> str:
    text = PLACEHOLDER_PATTERN.sub("", text or "")
    text = re.sub(r"[\s:：；;、，,。.·\-—–（）()\[\]【】<>《》]+", "", text)
    return text.strip()


def _cell_text(cell) -> str:
    return "\n".join(paragraph.text for paragraph in cell.paragraphs).strip()


def _is_blankish(text: str) -> bool:
    normalized = _normalize_label(text)
    return not normalized or set(normalized) <= {"_", "-", "—", "一", ".", "。"}


def _match_field(label: str) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None
    for field, alias in FIELD_LABELS_BY_ALIAS:
        if normalized == _normalize_label(alias) or _normalize_label(alias) in normalized:
            return field
    return None


def _direct_field_from_label(label: str) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None
    if normalized in DIRECT_LABEL_FIELDS:
        return normalized
    if re.search(r"[\u4e00-\u9fff]", normalized) and 2 <= len(normalized) <= 18:
        return normalized
    return None


def _add_ordered(target: list[str], field: str) -> None:
    if field and field not in target:
        target.append(field)


def find_placeholders_in_text(text: str) -> list[str]:
    fields: list[str] = []
    for match in PLACEHOLDER_PATTERN.finditer(text or ""):
        field = _sanitize_field_name(match.group(1))
        if field and field not in fields:
            fields.append(field)
    return fields


# ── Fill target selection ───────────────────────────────────────────────

def _choose_table_target(
    field: str,
    grid: list[list[GridCell]],
    label_row: int,
    label_grid_col: int,
    label_grid_span: int,
) -> tuple[int, int, int | None, str, str]:
    """Choose the best fill target cell for a label.

    Returns: (target_grid_col, target_grid_span, target_row_override, mapping_type, target_type)

    Rules (priority differs by field):
     A) For NEXT_ROW_PREFERRED_FIELDS: check next-row same grid_cols first
     B) Right-side fill: blank cell to the right
     C) Next-row fill: blank cell in next row
     D) Append in-place
    """
    num_cols = len(grid[0]) if grid else 0

    def _blank_in_grid(row_idx: int, col_start: int, col_end: int) -> bool:
        if row_idx < 0 or row_idx >= len(grid):
            return False
        r = grid[row_idx]
        for c in range(col_start, min(col_end, len(r))):
            gcell = r[c]
            if gcell is None:
                continue
            if not _is_blankish(gcell.text):
                return False
        return True

    # ── Rule A (for NEXT_ROW_PREFERRED_FIELDS): next-row first ──
    if field in NEXT_ROW_PREFERRED_FIELDS:
        next_row = label_row + 1
        if next_row < len(grid):
            if _blank_in_grid(next_row, label_grid_col, label_grid_col + label_grid_span):
                return (label_grid_col, label_grid_span, next_row, "table_cell", "next_row_cell")

    # ── Rule B: right-side blank cell ──
    right_col = label_grid_col + label_grid_span
    if right_col < num_cols:
        r = grid[label_row]
        gcell = r[right_col]
        if gcell is not None:
            if _is_blankish(gcell.text) or "{{" in gcell.text:
                return (gcell.grid_col, gcell.grid_span, None, "table_cell", "right_cell")

    # ── Rule C: next-row fill (for non-preferred fields fallback) ──
    next_row = label_row + 1
    if next_row < len(grid):
        if _blank_in_grid(next_row, label_grid_col, label_grid_col + label_grid_span):
            return (label_grid_col, label_grid_span, next_row, "table_cell", "next_row_cell")

    # ── Rule D: append ──
    return (label_grid_col, label_grid_span, None, "table_cell_append", "append_label_cell")


# ── Table scanning ──────────────────────────────────────────────────────

def _scan_table_labels(
    table,
    *,
    table_index: int,
    location: str,
    section: int | None,
    mapped_fields: list[str],
    field_context: dict[str, list[dict[str, Any]]],
    table_mappings: dict[str, list[dict[str, Any]]],
) -> tuple[list[list[GridCell]], list[list[str]]]:
    """Scan a table using real OOXML grid. Returns (grid, row_texts)."""
    grid = parse_table_grid(table)
    num_rows = len(grid)
    num_cols = len(grid[0]) if grid else 0

    row_texts: list[list[str]] = []
    for row_idx in range(num_rows):
        texts = []
        for gc in range(num_cols):
            gcell = grid[row_idx][gc]
            if gcell is not None and gcell.grid_col == gc:
                texts.append(gcell.text)
            else:
                texts.append("")
        row_texts.append(texts)

    # Scan each grid cell
    scanned_cells: set[int] = set()
    for row_idx in range(num_rows):
        for gc in range(num_cols):
            gcell = grid[row_idx][gc]
            if gcell is None:
                continue
            if gcell.grid_col != gc:
                continue  # only process at the cell's origin grid_col
            cell_id = id(gcell.cell._tc) if gcell.cell else (row_idx * 10000 + gc)
            if cell_id in scanned_cells:
                continue
            scanned_cells.add(cell_id)

            text = gcell.text

            # Placeholders
            for pf in find_placeholders_in_text(text):
                _add_ordered(mapped_fields, pf)
                field_context.setdefault(pf, []).append({
                    "source": "placeholder", "location": location,
                    "section": section, "table": table_index,
                    "row": row_idx, "grid_col": gc, "text": text,
                })

            # Known labels - match_field OR direct_field
            field = _match_field(text)
            if not field:
                field = _direct_field_from_label(text)
            if not field:
                continue

            _add_ordered(mapped_fields, field)

            tgt_col, tgt_span, tgt_row_override, map_type, target_type = _choose_table_target(
                field, grid, row_idx, gcell.grid_col, gcell.grid_span
            )

            effective_row = tgt_row_override if tgt_row_override is not None else row_idx
            effective_target_text = ""
            tgt_physical_col = gcell.physical_col  # fallback to label cell's physical_col
            if effective_row < len(grid) and tgt_col < num_cols:
                tgt_gcell = grid[effective_row][tgt_col]
                if tgt_gcell is not None:
                    effective_target_text = tgt_gcell.text
                    tgt_physical_col = tgt_gcell.physical_col

            target_info: dict[str, Any] = {
                "field": field,
                "type": map_type,
                "target_type": target_type,
                "location": location,
                "section": section,
                "table": table_index,
                "label_row": row_idx,
                "label_grid_col": gcell.grid_col,
                "label_grid_span": gcell.grid_span,
                "row": effective_row,
                "grid_col": tgt_col,
                "grid_span": tgt_span,
                "physical_col": tgt_physical_col,
                "col": tgt_physical_col,  # backward compat: target cell's physical col
                "label": text,
                "target_text": effective_target_text,
            }
            table_mappings.setdefault(field, []).append(target_info)

            field_context.setdefault(field, []).append({
                "source": "table_label",
                "location": location,
                "section": section,
                "table": table_index,
                "field": field,
                "label": text,
                "label_row": row_idx,
                "label_grid_col": gcell.grid_col,
                "target_row": effective_row,
                "target_grid_col": tgt_col,
                "target_type": target_type,
                "mapping_type": map_type,
            })

    return grid, row_texts


# ── Paragraph iteration ─────────────────────────────────────────────────

def _paragraph_location(paragraph) -> str:
    parent = paragraph._p.getparent()
    while parent is not None:
        tag = str(parent.tag)
        if tag.endswith("}hdr"):
            return "header"
        if tag.endswith("}ftr"):
            return "footer"
        if tag.endswith("}tc"):
            return "table"
        parent = parent.getparent()
    return "body"


def iter_paragraphs(document: Document) -> Iterable:
    for paragraph in document.paragraphs:
        yield paragraph
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph
    for section in document.sections:
        for paragraph in section.header.paragraphs:
            yield paragraph
        for paragraph in section.footer.paragraphs:
            yield paragraph
        for table in section.header.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        yield paragraph
        for table in section.footer.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        yield paragraph


# ── Public API ──────────────────────────────────────────────────────────

def scan_template(path: str | Path) -> list[str]:
    document = Document(str(path))
    fields: list[str] = []
    for paragraph in iter_paragraphs(document):
        for field in find_placeholders_in_text(paragraph.text):
            _add_ordered(fields, field)
    return fields


def _scan_placeholders(document: Document) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    placeholders: list[str] = []
    occurrences: dict[str, list[dict[str, Any]]] = {}
    for paragraph_index, paragraph in enumerate(iter_paragraphs(document)):
        for field in find_placeholders_in_text(paragraph.text):
            _add_ordered(placeholders, field)
            occurrences.setdefault(field, []).append({
                "source": "placeholder",
                "location": _paragraph_location(paragraph),
                "paragraph": paragraph_index,
                "text": paragraph.text,
            })
    return placeholders, occurrences


def analyze_template(path: str | Path) -> dict[str, Any]:
    document = Document(str(path))
    placeholders, field_context = _scan_placeholders(document)
    mapped_fields: list[str] = []
    table_mappings: dict[str, list[dict[str, Any]]] = {}
    tables: list[dict[str, Any]] = []

    for field in placeholders:
        _add_ordered(mapped_fields, field)

    for table_index, table in enumerate(document.tables):
        grid, row_texts = _scan_table_labels(
            table, table_index=table_index, location="body_table",
            section=None, mapped_fields=mapped_fields,
            field_context=field_context, table_mappings=table_mappings,
        )
        cells_serializable = []
        seen = set()
        for grid_row in grid:
            for gc, gcell in enumerate(grid_row):
                if gcell is None:
                    continue
                cid = (gcell.row, gcell.grid_col)
                if cid in seen:
                    continue
                seen.add(cid)
                cells_serializable.append({
                    "row": gcell.row,
                    "physical_col": gcell.physical_col,
                    "grid_col": gcell.grid_col,
                    "grid_span": gcell.grid_span,
                    "text": gcell.text,
                    "normalized_text": gcell.normalized_text,
                })
        tables.append({
            "index": table_index, "location": "body_table",
            "rows": row_texts, "grid_cells": cells_serializable,
            "num_rows": len(grid),
            "num_cols": len(grid[0]) if grid else 0,
        })

    for section_index, section in enumerate(document.sections):
        for table_index, table in enumerate(section.header.tables):
            grid, row_texts = _scan_table_labels(
                table, table_index=table_index, location="header_table",
                section=section_index, mapped_fields=mapped_fields,
                field_context=field_context, table_mappings=table_mappings,
            )
            tables.append({
                "index": table_index, "section": section_index,
                "location": "header_table", "rows": row_texts,
            })

        for table_index, table in enumerate(section.footer.tables):
            grid, row_texts = _scan_table_labels(
                table, table_index=table_index, location="footer_table",
                section=section_index, mapped_fields=mapped_fields,
                field_context=field_context, table_mappings=table_mappings,
            )
            tables.append({
                "index": table_index, "section": section_index,
                "location": "footer_table", "rows": row_texts,
            })

    errors: list[str] = []
    warnings: list[str] = []
    if not mapped_fields:
        errors.append('未识别到可填写字段。请在模板中加入 {{field_name}} 占位符，或使用可识别的表格标签，例如"教学目标""教学过程""作业设计"。')
    if placeholders and table_mappings:
        warnings.append("模板同时包含占位符和表格标签，系统会按模板出现顺序填充两类字段。")

    return {
        "placeholders": placeholders,
        "placeholder_occurrences": field_context,
        "table_mappings": table_mappings,
        "mapped_fields": mapped_fields,
        "field_context": field_context,
        "tables": tables,
        "table_count": len(document.tables),
        "paragraph_count": len(document.paragraphs),
        "mode": "mixed" if placeholders and table_mappings else ("placeholder" if placeholders else "table_mapping"),
        "fillable_count": len(mapped_fields),
        "needs_template_markers": not mapped_fields,
        "warnings": warnings,
        "errors": errors,
    }
