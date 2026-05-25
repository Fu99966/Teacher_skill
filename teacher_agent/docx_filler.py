from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document

from .template_parser import PLACEHOLDER_PATTERN, iter_paragraphs


def _placeholder(name: str) -> str:
    return "{{" + name + "}}"


def _replace_run_text(text: str, data: dict[str, Any]) -> str:
    for key, value in data.items():
        text = text.replace(_placeholder(key), str(value))
    return text


def _replace_paragraph(paragraph, data: dict[str, Any]) -> None:
    full_text = "".join(run.text for run in paragraph.runs)
    if "{{" not in full_text:
        return

    if not PLACEHOLDER_PATTERN.search(full_text):
        return

    changed_single_run = False
    for run in paragraph.runs:
        if "{{" in run.text and "}}" in run.text:
            new_text = _replace_run_text(run.text, data)
            if new_text != run.text:
                run.text = new_text
                changed_single_run = True

    if changed_single_run:
        return

    replaced = full_text
    for key, value in data.items():
        replaced = replaced.replace(_placeholder(key), str(value))

    if replaced == full_text or not paragraph.runs:
        return

    paragraph.runs[0].text = replaced
    for run in paragraph.runs[1:]:
        run.text = ""


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

    document.save(str(output_path))
    return output_path
