from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from docx import Document


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-\.]+)\s*\}\}")

FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "lesson_title": ("课题", "课题名称", "题目", "教学课题"),
    "subject": ("学科", "课程", "课程名称"),
    "grade": ("年级", "班级", "授课年级", "适用年级"),
    "class_hour": ("课时", "课时安排", "授课课时", "学时"),
    "teaching_goals": ("教学目标", "学习目标", "目标", "核心素养目标"),
    "key_points": ("教学重点", "重点", "教学重难点", "重点内容"),
    "difficult_points": ("教学难点", "难点", "教学重难点", "难点内容"),
    "teaching_preparation": ("教学准备", "课前准备", "准备", "教具准备"),
    "teaching_process": ("教学过程", "教学流程", "教学环节", "课堂过程", "过程设计"),
    "blackboard_design": ("板书设计", "板书", "板书规划"),
    "homework": ("作业设计", "作业", "课后作业", "课后任务"),
    "reflection": ("教学反思", "课后反思", "反思", "教学后记"),
}


def find_placeholders_in_text(text: str) -> set[str]:
    """Return placeholder names found in text."""
    return {match.group(1).strip() for match in PLACEHOLDER_PATTERN.finditer(text)}


def _normalize_label(text: str) -> str:
    text = re.sub(r"\{\{.*?\}\}", "", text)
    return re.sub(r"[\s:：;；,，.。|｜/\\（）()【】\[\]<>《》]+", "", text).strip()


def _match_field(label: str) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None
    for field, aliases in FIELD_LABELS.items():
        for alias in aliases:
            normalized_alias = _normalize_label(alias)
            if normalized == normalized_alias or normalized_alias in normalized:
                return field
    return None


def _cell_text(cell) -> str:
    return "\n".join(paragraph.text for paragraph in cell.paragraphs).strip()


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
    """Scan a .docx template and return sorted placeholder names."""
    document = Document(str(path))
    fields: set[str] = set()

    for paragraph in iter_paragraphs(document):
        fields.update(find_placeholders_in_text(paragraph.text))

    return sorted(fields)


def analyze_template(path: str | Path) -> dict[str, Any]:
    """Return a JSON-serializable report for Word template mapping.

    The report keeps the original template as the source of truth. It identifies
    explicit placeholders first, then infers table targets from teacher-facing
    labels such as "教学目标" or "教学过程".
    """
    document = Document(str(path))
    placeholders = scan_template(path)
    placeholder_set = set(placeholders)
    table_mappings: dict[str, dict[str, Any]] = {}
    tables: list[dict[str, Any]] = []

    for table_index, table in enumerate(document.tables):
        rows: list[list[str]] = []
        for row_index, row in enumerate(table.rows):
            row_texts = [_cell_text(cell) for cell in row.cells]
            rows.append(row_texts)
            for cell_index, text in enumerate(row_texts):
                field = _match_field(text)
                if not field or field in placeholder_set or field in table_mappings:
                    continue
                target_col = cell_index + 1 if cell_index + 1 < len(row.cells) else cell_index
                if target_col == cell_index:
                    continue
                table_mappings[field] = {
                    "type": "table_cell",
                    "table": table_index,
                    "row": row_index,
                    "col": target_col,
                    "label": text,
                    "target_text": row_texts[target_col],
                }
        tables.append({"index": table_index, "rows": rows})

    mapped_fields = sorted(set(placeholders) | set(table_mappings))
    return {
        "placeholders": placeholders,
        "table_mappings": table_mappings,
        "mapped_fields": mapped_fields,
        "tables": tables,
        "table_count": len(document.tables),
        "paragraph_count": len(document.paragraphs),
        "mode": "placeholder" if placeholders else "table_mapping",
    }
