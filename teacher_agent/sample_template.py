from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr/>
    <w:rPr>
      <w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei" w:hAnsi="Microsoft YaHei"/>
      <w:sz w:val="22"/>
    </w:rPr>
  </w:style>
</w:styles>
"""


def _paragraph(text: str, bold: bool = False) -> str:
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:p><w:r><w:rPr>"
        f"{bold_xml}"
        '<w:rFonts w:ascii="Microsoft YaHei" w:eastAsia="Microsoft YaHei" w:hAnsi="Microsoft YaHei"/>'
        "</w:rPr>"
        f"<w:t>{escape(text)}</w:t>"
        "</w:r></w:p>"
    )


def _cell(text: str, width: str = "4500", bold: bool = False) -> str:
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
        f"{_paragraph(text, bold=bold)}"
        "</w:tc>"
    )


def _row(label: str, value: str) -> str:
    return f"<w:tr>{_cell(label, '2200', True)}{_cell(value, '7200')}</w:tr>"


def _document_xml() -> str:
    rows = [
        _row("课题", "{{lesson_title}}"),
        _row("学科", "{{subject}}"),
        _row("年级", "{{grade}}"),
        _row("课时", "{{class_hour}}"),
        _row("教学目标", "{{teaching_goals}}"),
        _row("教学重点", "{{key_points}}"),
        _row("教学难点", "{{difficult_points}}"),
        _row("教学准备", "{{teaching_preparation}}"),
        _row("教学过程", "{{teaching_process}}"),
        _row("板书设计", "{{blackboard_design}}"),
        _row("作业设计", "{{homework}}"),
        _row("教学反思", "{{reflection}}"),
    ]
    table = (
        "<w:tbl>"
        "<w:tblPr><w:tblW w:w=\"9500\" w:type=\"dxa\"/>"
        "<w:tblBorders>"
        "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"666666\"/>"
        "</w:tblBorders></w:tblPr>"
        + "".join(rows)
        + "</w:tbl>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + _paragraph("标准教案模板", bold=True)
        + table
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        + "</w:body></w:document>"
    )


def create_sample_template(output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_path, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", CONTENT_TYPES)
        docx.writestr("_rels/.rels", RELS)
        docx.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS)
        docx.writestr("word/styles.xml", STYLES)
        docx.writestr("word/document.xml", _document_xml())

    return output_path
