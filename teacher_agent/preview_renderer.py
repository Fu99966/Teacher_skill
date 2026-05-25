from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which


def render_docx_pdf_preview(docx_path: str | Path, output_dir: str | Path) -> Path | None:
    """Render a DOCX to PDF when LibreOffice is available.

    The app treats this as optional: Word download remains the source of truth,
    and preview rendering is enabled automatically on machines with `soffice`.
    """
    docx_path = Path(docx_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    soffice = which("soffice") or which("libreoffice")
    if not soffice:
        return None

    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return None

    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    return pdf_path if pdf_path.exists() else None
