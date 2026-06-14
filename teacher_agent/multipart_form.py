from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from io import BytesIO
from typing import BinaryIO


@dataclass
class MultipartItem:
    value: str | bytes
    filename: str | None
    file: BytesIO
    content_type: str


class MultipartForm(dict[str, MultipartItem]):
    pass


def parse_multipart_form(stream: BinaryIO, content_type: str, content_length: int) -> MultipartForm:
    if "multipart/form-data" not in content_type.lower():
        raise ValueError("请使用表单提交")
    if content_length < 0:
        raise ValueError("Content-Length 无效")

    body = stream.read(content_length)
    if len(body) != content_length:
        raise ValueError("表单内容不完整，请重新提交")

    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1", errors="replace")
    message = BytesParser(policy=policy.default).parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("表单内容格式无效，请重新提交")

    form = MultipartForm()
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue

        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            charset = part.get_content_charset() or "utf-8"
            value: str | bytes = payload.decode(charset, errors="replace")
        else:
            value = payload
        form[str(name)] = MultipartItem(
            value=value,
            filename=filename,
            file=BytesIO(payload),
            content_type=part.get_content_type(),
        )
    return form
