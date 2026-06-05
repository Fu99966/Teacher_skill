from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from docx import Document


@dataclass
class MaterialExtraction:
    text: str
    source_name: str
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source_name": self.source_name,
            "warnings": self.warnings,
            "char_count": len(self.text),
        }


def extract_material_from_upload(filename: str, file_obj: BinaryIO) -> MaterialExtraction:
    raw = file_obj.read()
    return extract_material_bytes(filename, raw)


def extract_material_bytes(filename: str, raw: bytes) -> MaterialExtraction:
    suffix = Path(filename or "").suffix.lower()
    warnings: list[str] = []
    text = ""

    if suffix in {".txt", ".md"}:
        text = _decode_text(raw)
    elif suffix == ".docx":
        text = _extract_docx_text(raw, warnings)
    elif suffix == ".pdf":
        text = _extract_pdf_text_best_effort(raw, warnings)
    else:
        warnings.append("暂不支持该教材文件类型，已忽略文件内容。")

    return MaterialExtraction(text=_normalize_material_text(text), source_name=filename, warnings=warnings)


def merge_material_text(typed_material: str, extracted: MaterialExtraction | None) -> str:
    typed = (typed_material or "").strip()
    if not extracted or not extracted.text.strip():
        return typed
    if typed:
        return f"{typed}\n\n# 上传教材资料：{extracted.source_name}\n{extracted.text}"
    return extracted.text


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _extract_docx_text(raw: bytes, warnings: list[str]) -> str:
    try:
        document = Document(BytesIO(raw))
    except Exception as exc:
        warnings.append(f"Word 教材读取失败：{exc}")
        return ""

    parts: list[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_pdf_text_best_effort(raw: bytes, warnings: list[str]) -> str:
    # This is intentionally dependency-free. It can read text-based PDFs poorly,
    # but gives a graceful path until OCR / pypdf is introduced.
    decoded = raw.decode("latin-1", errors="ignore")
    visible = []
    for chunk in decoded.replace("\r", "\n").splitlines():
        chunk = "".join(ch for ch in chunk if ch == "\t" or ch == " " or ch.isprintable()).strip()
        if len(chunk) >= 12 and not chunk.startswith(("%PDF", "endobj", "xref", "stream")):
            visible.append(chunk)
    warnings.append("PDF 仅做无依赖文本尝试；扫描版 PDF 需要后续 OCR 支持。")
    return "\n".join(visible[:80])


def _normalize_material_text(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank:
                compact.append("")
            blank = True
            continue
        compact.append(line)
        blank = False
    return "\n".join(compact).strip()
