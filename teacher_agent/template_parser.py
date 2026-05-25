from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from docx import Document


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-\.]+)\s*\}\}")


def find_placeholders_in_text(text: str) -> set[str]:
    """Return placeholder names found in text."""
    return {match.group(1).strip() for match in PLACEHOLDER_PATTERN.finditer(text)}


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
