from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from teacher_agent.material_ingestion import extract_material_bytes


def _text_pdf_bytes(text: str | None = None) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    if text:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_ref}
                )
            }
        )

        content = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extracts_selectable_text_from_pdf():
    result = extract_material_bytes(
        "sensor-course.pdf",
        _text_pdf_bytes("Sensor curriculum standard and assessment tasks"),
    )

    assert "Sensor curriculum standard" in result.text
    assert result.warnings == []


def test_blank_pdf_explains_that_scanned_material_needs_ocr():
    result = extract_material_bytes("scan.pdf", _text_pdf_bytes())

    assert result.text == ""
    assert any("未检测到可提取文本" in warning for warning in result.warnings)
    assert any("OCR" in warning for warning in result.warnings)


def test_invalid_pdf_returns_readable_warning_without_binary_garbage():
    result = extract_material_bytes("broken.pdf", b"%PDF-not-a-real-document")

    assert result.text == ""
    assert any("PDF 教材读取失败" in warning for warning in result.warnings)
