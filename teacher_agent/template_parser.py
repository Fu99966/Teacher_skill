from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from docx import Document


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-\.]+)\s*\}\}")

FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "lesson_title": ("课题", "课题名称", "题目", "教学课题", "授课内容", "教学内容"),
    "subject": ("学科", "课程", "课程名称", "科目"),
    "grade": ("年级", "班级", "授课年级", "适用年级"),
    "class_hour": ("课时", "课时安排", "授课课时", "学时"),
    "teaching_goals": ("教学目标", "学习目标", "目标", "核心素养目标", "知识目标", "能力目标", "情感目标"),
    "key_points": ("教学重点", "重点", "重点内容"),
    "difficult_points": ("教学难点", "难点", "难点内容"),
    "teaching_key_difficult": ("教学重难点", "重难点", "教学重点与难点", "重点难点"),
    "teaching_preparation": ("教学准备", "课前准备", "准备", "教具准备", "教学资源"),
    "student_analysis": ("学情分析", "学生分析", "学习者分析"),
    "teaching_process": ("教学过程", "教学流程", "教学环节", "课堂过程", "过程设计", "教学活动"),
    "teacher_activity": ("教师活动", "教师行为", "教师指导"),
    "student_activity": ("学生活动", "学生行为", "学习活动"),
    "design_intent": ("设计意图", "设计说明", "活动意图"),
    "blackboard_design": ("板书设计", "板书", "板书规划"),
    "homework": ("作业设计", "作业", "课后作业", "课后任务"),
    "reflection": ("教学反思", "课后反思", "反思", "教学后记"),
}

FIELD_LABELS_BY_ALIAS: list[tuple[str, str]] = [
    (field, alias) for field, aliases in FIELD_LABELS.items() for alias in aliases
]


def find_placeholders_in_text(text: str) -> list[str]:
    """Return placeholder names found in text, preserving order."""
    fields: list[str] = []
    for match in PLACEHOLDER_PATTERN.finditer(text or ""):
        field = match.group(1).strip()
        if field and field not in fields:
            fields.append(field)
    return fields


def _normalize_label(text: str) -> str:
    text = PLACEHOLDER_PATTERN.sub("", text or "")
    text = re.sub(r"[\s:：；;，,。\.、\-\—_（）()【】\[\]<>《》]+", "", text)
    return text.strip()


def _match_field(label: str) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None

    best_field: str | None = None
    best_alias_len = 0
    for field, alias in FIELD_LABELS_BY_ALIAS:
        normalized_alias = _normalize_label(alias)
        if not normalized_alias:
            continue
        if normalized == normalized_alias or normalized_alias in normalized:
            if len(normalized_alias) > best_alias_len:
                best_field = field
                best_alias_len = len(normalized_alias)
    return best_field


def _cell_text(cell) -> str:
    return "\n".join(paragraph.text for paragraph in cell.paragraphs).strip()


def _is_blankish(text: str) -> bool:
    normalized = _normalize_label(text)
    return not normalized or set(normalized) <= {"_", "-", "—", "一", ".", "。"}


def _add_ordered(target: list[str], field: str) -> None:
    if field and field not in target:
        target.append(field)


def _choose_table_target(row_texts: list[str], cell_index: int) -> tuple[int, str]:
    """Choose the most likely fill target for a table label."""
    for target_col in range(cell_index + 1, len(row_texts)):
        target_text = row_texts[target_col]
        if _match_field(target_text):
            continue
        if _is_blankish(target_text) or "{{" in target_text:
            return target_col, "table_cell"

    if cell_index + 1 < len(row_texts):
        next_text = row_texts[cell_index + 1]
        if next_text != row_texts[cell_index] and not _match_field(next_text):
            return cell_index + 1, "table_cell"

    return cell_index, "table_cell_append"


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
            occurrences.setdefault(field, []).append(
                {
                    "source": "placeholder",
                    "location": _paragraph_location(paragraph),
                    "paragraph": paragraph_index,
                    "text": paragraph.text,
                }
            )
    return placeholders, occurrences


def analyze_template(path: str | Path) -> dict[str, Any]:
    """Return a serializable report describing fillable fields in a Word template."""
    document = Document(str(path))
    placeholders, field_context = _scan_placeholders(document)
    mapped_fields: list[str] = []
    table_mappings: dict[str, dict[str, Any]] = {}
    tables: list[dict[str, Any]] = []

    for field in placeholders:
        _add_ordered(mapped_fields, field)

    for table_index, table in enumerate(document.tables):
        rows: list[list[str]] = []
        seen_cells: set[int] = set()
        for row_index, row in enumerate(table.rows):
            row_texts = [_cell_text(cell) for cell in row.cells]
            rows.append(row_texts)
            for cell_index, cell in enumerate(row.cells):
                cell_id = id(cell._tc)
                if cell_id in seen_cells:
                    continue
                seen_cells.add(cell_id)

                text = row_texts[cell_index]
                for field in find_placeholders_in_text(text):
                    _add_ordered(mapped_fields, field)
                    field_context.setdefault(field, []).append(
                        {
                            "source": "placeholder",
                            "location": "table",
                            "table": table_index,
                            "row": row_index,
                            "col": cell_index,
                            "text": text,
                        }
                    )

                field = _match_field(text)
                if not field or field in table_mappings:
                    continue

                target_col, mapping_type = _choose_table_target(row_texts, cell_index)
                table_mappings[field] = {
                    "type": mapping_type,
                    "table": table_index,
                    "row": row_index,
                    "col": target_col,
                    "label": text,
                    "target_text": row_texts[target_col] if target_col < len(row_texts) else "",
                }
                _add_ordered(mapped_fields, field)
                field_context.setdefault(field, []).append(
                    {
                        "source": "table_label",
                        "location": "table",
                        "table": table_index,
                        "row": row_index,
                        "label_col": cell_index,
                        "target_col": target_col,
                        "label": text,
                        "row_text": " | ".join(item for item in row_texts if item),
                    }
                )
        tables.append({"index": table_index, "rows": rows})

    errors: list[str] = []
    warnings: list[str] = []
    if not mapped_fields:
        errors.append(
            "未识别到可填字段。请在模板中加入 {{field_name}} 占位符，或使用可识别的表格标签，如“教学目标”“教学过程”“作业设计”。"
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
