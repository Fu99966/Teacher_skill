from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.oxml.ns import qn


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^{}\r\n\t<>]+?)\s*\}\}")

# ── Field label mapping ──────────────────────────────────────────────────
# Each standard field maps to a tuple of Chinese labels it can match.
# "主要教学内容" MUST map to teaching_process, NOT lesson_title.
FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "lesson_title": ("课题", "课题名称", "题目", "教学课题", "课题（含章节号）", "课题(含章节号)", "授课内容"),
    "subject": ("学科", "课程", "课程名称", "科目"),
    "grade": ("年级", "班级", "授课年级", "适用年级", "授课班级"),
    "class_hour": ("课时", "课时安排", "授课课时", "学时", "课时数"),
    "teaching_goals": (
        "教学目的", "教学目的与要求", "教学目的及要求",
        "教学目标", "教学目标与要求", "教学目标及要求",
        "学习目标", "目标", "核心素养目标", "知识目标", "能力目标", "情感目标",
    ),
    "key_points": ("教学重点", "重点", "重点内容"),
    "difficult_points": ("教学难点", "难点", "难点内容"),
    "teaching_key_difficult": ("教学重难点", "重难点", "教学重点与难点", "重点难点"),
    "teaching_preparation": ("教学准备", "课前准备", "准备", "教具准备", "教学资源"),
    "teaching_environment": (
        "对教学环境的要求", "教学环境", "教学环境要求",
    ),
    "teaching_aids": (
        "教具挂图", "教具", "挂图", "教学用具", "教学挂图",
    ),
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
    "reflection": ("课后小记", "课后小结", "教学反思", "课后反思", "反思", "教学后记"),
}

DIRECT_LABEL_FIELDS = {
    "教材分析",
    "课程标准",
    "核心素养",
    "学习任务",
    "学习活动",
    "评价任务",
    "评价标准",
    "教学评价",
    "教学资源",
    "信息技术应用",
    "课堂小结",
    "课后拓展",
    "安全教育",
    "德育渗透",
    "跨学科融合",
    "二次备课",
    "个性化修改",
    "教研组意见",
    "审批意见",
}

FIELD_LABELS_BY_ALIAS: list[tuple[str, str]] = [
    (field, alias) for field, aliases in FIELD_LABELS.items() for alias in aliases
]

# Priority ordering: longer aliases match first
FIELD_LABELS_BY_ALIAS.sort(key=lambda x: -len(x[1]))


def find_placeholders_in_text(text: str) -> list[str]:
    """Return placeholder names found in text, preserving order."""
    fields: list[str] = []
    for match in PLACEHOLDER_PATTERN.finditer(text or ""):
        field = _sanitize_field_name(match.group(1))
        if field and field not in fields:
            fields.append(field)
    return fields


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
    """Match a Chinese label to a standard field name, with priority for longer aliases."""
    normalized = _normalize_label(label)
    if not normalized:
        return None

    for field, alias in FIELD_LABELS_BY_ALIAS:
        normalized_alias = _normalize_label(alias)
        if not normalized_alias:
            continue
        if normalized == normalized_alias or normalized_alias in normalized:
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


# ── Grid column helper ──────────────────────────────────────────────────

def _parse_cell_grid_col(cell) -> int:
    """Return the OOXML grid column index for a cell, or its Python index as fallback."""
    tc_pr = cell._tc.find(qn('w:tcPr'))
    if tc_pr is not None:
        grid_span_el = tc_pr.find(qn('w:gridSpan'))
        if grid_span_el is not None:
            # gridSpan doesn't tell us the column, but we can use OOXML position
            pass
    return -1


def _get_cell_grid_info(table) -> list[dict[str, Any]]:
    """Parse the full grid structure of a Word table using OOXML.
    
    Returns a list of cell info dicts with: row, col, grid_col, grid_span, text.
    """
    cells_info: list[dict[str, Any]] = []
    
    for row_index, row in enumerate(table.rows):
        for cell_index, cell in enumerate(row.cells):
            # Try to read gridSpan and vMerge from OOXML
            tc = cell._tc
            tc_pr = tc.find(qn('w:tcPr'))
            grid_span = 1
            if tc_pr is not None:
                grid_span_el = tc_pr.find(qn('w:gridSpan'))
                if grid_span_el is not None and grid_span_el.get(qn('w:val')):
                    grid_span = int(grid_span_el.get(qn('w:val')))
            
            text = _cell_text(cell)
            cells_info.append({
                "row": row_index,
                "col": cell_index,
                "grid_col": cell_index,  # Python index as approximate grid_col
                "grid_span": grid_span,
                "text": text,
            })
    
    return cells_info


# ── Fill target selection ───────────────────────────────────────────────

def _choose_table_target(
    row_texts: list[str],
    cell_index: int,
    all_rows: list[list[str]],
    row_index: int,
    field: str,
) -> tuple[int, str, int | None]:
    """Choose the most likely fill target for a table label.
    
    Returns: (target_col, mapping_type, target_row_override)
    
    Rules:
      A) Right-side fill: if right cell is blank, write there.
      B) Next-row fill: if current row looks like a header row and next row
         has blank cells in corresponding columns, write to next row.
      C) Append: fall back to appending text in the label cell.
    """
    # Rule A: right-side blank cell
    for target_col in range(cell_index + 1, len(row_texts)):
        target_text = row_texts[target_col]
        if _match_field(target_text):
            # The right cell is another label, skip it
            continue
        if _is_blankish(target_text) or "{{" in target_text:
            return target_col, "table_cell", None

    # Rule B: next-row fill
    if row_index + 1 < len(all_rows):
        next_row = all_rows[row_index + 1]
        if cell_index < len(next_row):
            next_text = next_row[cell_index]
            if _is_blankish(next_text) or "{{" in next_text:
                return cell_index, "table_cell", row_index + 1

    # Rule C: append in-place if immediate right isn't another field
    if cell_index + 1 < len(row_texts):
        next_text = row_texts[cell_index + 1]
        if next_text != row_texts[cell_index] and not _match_field(next_text):
            return cell_index + 1, "table_cell", None

    return cell_index, "table_cell_append", None


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
) -> list[list[str]]:
    """Scan a single table for fillable fields.
    
    Returns full row_texts matrix for diagnostic use.
    """
    rows: list[list[str]] = []
    
    # Collect all row texts first
    for row_index, row in enumerate(table.rows):
        row_texts = [_cell_text(cell) for cell in row.cells]
        rows.append(row_texts)
    
    # Now scan for fields (per-row seen_cells to avoid merged-cell issues)
    for row_index, row in enumerate(table.rows):
        row_texts = rows[row_index]
        seen_in_row: set[int] = set()
        
        for cell_index, cell in enumerate(row.cells):
            cell_id = id(cell._tc)
            if cell_id in seen_in_row:
                continue
            seen_in_row.add(cell_id)
            
            text = row_texts[cell_index]
            
            # Check for {{placeholders}} in cell text
            for field in find_placeholders_in_text(text):
                _add_ordered(mapped_fields, field)
                field_context.setdefault(field, []).append({
                    "source": "placeholder",
                    "location": location,
                    "section": section,
                    "table": table_index,
                    "row": row_index,
                    "col": cell_index,
                    "text": text,
                })
            
            # Match known label fields
            field = _match_field(text)
            if not field:
                # Try direct field if there's a plausible fill target nearby
                if _has_plausible_fill_target(rows, row_index, cell_index):
                    field = _direct_field_from_label(text)
            
            if not field:
                continue
            
            # Always record in field_context and mapped_fields
            _add_ordered(mapped_fields, field)
            
            target_col, mapping_type, target_row_override = _choose_table_target(
                row_texts, cell_index, rows, row_index, field
            )
            
            effective_row = target_row_override if target_row_override is not None else row_index
            effective_target_text = ""
            if target_row_override is not None and target_row_override < len(rows):
                tr = rows[target_row_override]
                if target_col < len(tr):
                    effective_target_text = tr[target_col]
            elif target_col < len(row_texts):
                effective_target_text = row_texts[target_col]
            
            target_info = {
                "type": mapping_type,
                "location": location,
                "section": section,
                "table": table_index,
                "row": effective_row,
                "col": target_col,
                "label": text,
                "target_text": effective_target_text,
                "label_row": row_index,
                "label_col": cell_index,
            }
            
            # Support multiple targets per field
            table_mappings.setdefault(field, []).append(target_info)
            
            field_context.setdefault(field, []).append({
                "source": "table_label",
                "location": location,
                "section": section,
                "table": table_index,
                "row": effective_row,
                "label_col": cell_index,
                "target_col": target_col,
                "label": text,
                "row_text": " | ".join(item for item in row_texts if item),
                "target_row_override": target_row_override,
                "mapping_type": mapping_type,
            })
    
    return rows


def _has_plausible_fill_target(all_rows: list[list[str]], row_index: int, cell_index: int) -> bool:
    """Check if a cell label has a plausible fill target nearby."""
    if row_index >= len(all_rows):
        return False
    row_texts = all_rows[row_index]
    
    # Check right cell
    if cell_index + 1 < len(row_texts):
        next_text = row_texts[cell_index + 1]
        if _is_blankish(next_text) or "{{" in next_text:
            return True
    
    # Check next row same column
    if row_index + 1 < len(all_rows):
        next_row = all_rows[row_index + 1]
        if cell_index < len(next_row):
            next_text = next_row[cell_index]
            if _is_blankish(next_text) or "{{" in next_text:
                return True
    
    return False


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
    """Scan a .docx template and return placeholder names in template order."""
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
    """Return a serializable report describing fillable fields in a Word template."""
    document = Document(str(path))
    placeholders, field_context = _scan_placeholders(document)
    mapped_fields: list[str] = []
    table_mappings: dict[str, list[dict[str, Any]]] = {}
    tables: list[dict[str, Any]] = []

    for field in placeholders:
        _add_ordered(mapped_fields, field)

    # Scan body tables
    for table_index, table in enumerate(document.tables):
        rows = _scan_table_labels(
            table,
            table_index=table_index,
            location="body_table",
            section=None,
            mapped_fields=mapped_fields,
            field_context=field_context,
            table_mappings=table_mappings,
        )
        # Add detailed grid info
        cell_grid = _get_cell_grid_info(table)
        tables.append({
            "index": table_index,
            "rows": rows,
            "cells": cell_grid,
            "location": "body_table",
        })

    # Scan header/footer tables
    for section_index, section in enumerate(document.sections):
        for table_index, table in enumerate(section.header.tables):
            rows = _scan_table_labels(
                table,
                table_index=table_index,
                location="header_table",
                section=section_index,
                mapped_fields=mapped_fields,
                field_context=field_context,
                table_mappings=table_mappings,
            )
            tables.append({
                "index": table_index, "section": section_index,
                "location": "header_table", "rows": rows,
            })

        for table_index, table in enumerate(section.footer.tables):
            rows = _scan_table_labels(
                table,
                table_index=table_index,
                location="footer_table",
                section=section_index,
                mapped_fields=mapped_fields,
                field_context=field_context,
                table_mappings=table_mappings,
            )
            tables.append({
                "index": table_index, "section": section_index,
                "location": "footer_table", "rows": rows,
            })

    errors: list[str] = []
    warnings: list[str] = []
    if not mapped_fields:
        errors.append(
            '未识别到可填写字段。请在模板中加入 {{field_name}} 占位符，或使用可识别的表格标签，例如"教学目标""教学过程""作业设计"。'
        )
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
