from __future__ import annotations

from io import BytesIO

import pytest

from teacher_agent.multipart_form import parse_multipart_form


def _multipart_body(boundary: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="title"\r\n'
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "传感器基础\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="template"; filename="学校模板.docx"\r\n'
        "Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n"
        "\r\n"
    ).encode("utf-8") + b"docx-bytes\r\n" + f"--{boundary}--\r\n".encode("ascii")


def test_parse_multipart_form_preserves_unicode_text_and_uploaded_file():
    boundary = "teacher-skill-boundary"
    body = _multipart_body(boundary)

    form = parse_multipart_form(
        BytesIO(body),
        f"multipart/form-data; boundary={boundary}",
        len(body),
    )

    assert form["title"].filename is None
    assert form["title"].value == "传感器基础"
    assert form["template"].filename == "学校模板.docx"
    assert form["template"].file.read() == b"docx-bytes"


def test_parse_multipart_form_rejects_non_multipart_content_type():
    with pytest.raises(ValueError, match="请使用表单提交"):
        parse_multipart_form(BytesIO(b"{}"), "application/json", 2)


def test_web_app_no_longer_imports_removed_cgi_module():
    source = (pytest.importorskip("teacher_agent.web_app").PROJECT_ROOT / "teacher_agent" / "web_app.py").read_text(
        encoding="utf-8"
    )

    assert "import cgi" not in source
    assert "cgi.FieldStorage" not in source
