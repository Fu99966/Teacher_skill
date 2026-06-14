from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


MAX_DOCX_ARCHIVE_ENTRIES = 5_000
MAX_DOCX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_DOCX_SINGLE_ENTRY_BYTES = 128 * 1024 * 1024
REQUIRED_DOCX_ENTRIES = {"[Content_Types].xml", "word/document.xml"}


class DocxSecurityError(ValueError):
    pass


def validate_docx_path(path: str | Path) -> None:
    target = Path(path)
    try:
        with target.open("rb") as file:
            validate_docx_file(file, source_name=target.name)
    except FileNotFoundError as exc:
        raise DocxSecurityError(f"Word 文件不存在：{target}") from exc


def validate_docx_bytes(raw: bytes, source_name: str = "Word 文档") -> None:
    validate_docx_file(BytesIO(raw), source_name=source_name)


def validate_docx_file(file_obj, source_name: str = "Word 文档") -> None:
    try:
        with ZipFile(file_obj) as archive:
            entries = archive.infolist()
    except (BadZipFile, OSError) as exc:
        raise DocxSecurityError(f"{source_name}不是有效的 Word .docx 文件，请重新选择。") from exc

    if len(entries) > MAX_DOCX_ARCHIVE_ENTRIES:
        raise DocxSecurityError(f"{source_name}包含过多文件条目，已停止解析。")

    names = {entry.filename for entry in entries}
    if not REQUIRED_DOCX_ENTRIES.issubset(names):
        raise DocxSecurityError(f"{source_name}不是有效的 Word .docx 文件，缺少必要文档结构。")

    total_uncompressed = 0
    for entry in entries:
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or ".." in path.parts:
            raise DocxSecurityError(f"{source_name}包含不安全的压缩包路径，已停止解析。")
        if entry.flag_bits & 0x1:
            raise DocxSecurityError(f"{source_name}包含加密内容，暂不支持解析。")
        if entry.file_size > MAX_DOCX_SINGLE_ENTRY_BYTES:
            raise DocxSecurityError(f"{source_name}包含异常大的内部文件，已停止解析。")
        total_uncompressed += entry.file_size
        if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise DocxSecurityError(f"{source_name}解压后内容过大，已停止解析以保护本机资源。")
