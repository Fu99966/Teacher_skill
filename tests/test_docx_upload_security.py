from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

import teacher_agent.docx_security as docx_security
import teacher_agent.web_app as web_app
from teacher_agent.material_ingestion import extract_material_bytes
from teacher_agent.template_parser import analyze_template
from teacher_agent.web_app import TeacherAgentHandler


def _minimal_docx_bytes(document_xml: bytes = b"<w:document/>") -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_invalid_docx_template_is_rejected_before_parser(tmp_path):
    path = tmp_path / "伪造模板.docx"
    path.write_bytes(b"not a Word package")

    with pytest.raises(docx_security.DocxSecurityError, match="不是有效的 Word .docx"):
        analyze_template(path)


def test_oversized_uncompressed_docx_is_rejected(monkeypatch):
    monkeypatch.setattr(docx_security, "MAX_DOCX_UNCOMPRESSED_BYTES", 16)

    with pytest.raises(docx_security.DocxSecurityError, match="解压后内容过大"):
        docx_security.validate_docx_bytes(_minimal_docx_bytes(b"x" * 32))


def test_web_rejects_invalid_template_without_saving_upload(monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(web_app, "UPLOAD_DIR", upload_dir)
    handler = object.__new__(TeacherAgentHandler)

    with pytest.raises(docx_security.DocxSecurityError, match="不是有效的 Word .docx"):
        handler._save_template(
            {"template": SimpleNamespace(filename="学校模板.docx", file=BytesIO(b"invalid"))}
        )

    assert not upload_dir.exists() or not list(upload_dir.iterdir())


def test_invalid_docx_material_is_ignored_with_teacher_readable_warning():
    extraction = extract_material_bytes("教材.docx", b"invalid")

    assert extraction.text == ""
    assert any("不是有效的 Word .docx" in warning for warning in extraction.warnings)
