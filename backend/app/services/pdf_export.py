"""Convert a generated .pptx into a PDF using LibreOffice or Microsoft PowerPoint."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


def _find_soffice() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _convert_with_libreoffice(soffice: str, pptx: Path, pdf: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(pptx)],
            check=True, timeout=180, capture_output=True,
        )
        out = Path(tmp) / f"{pptx.stem}.pdf"
        if not out.exists():
            raise RuntimeError("LibreOffice did not produce a PDF")
        shutil.move(str(out), str(pdf))


def _convert_with_powerpoint(pptx: Path, pdf: Path) -> None:
    script = (
        "$ErrorActionPreference='Stop';"
        "$app=New-Object -ComObject PowerPoint.Application;"
        "try{"
        f"$p=$app.Presentations.Open('{pptx.resolve()}',$true,$false,$false);"
        f"$p.SaveAs('{pdf.resolve()}',32);"
        "$p.Close()"
        "}finally{$app.Quit()}"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, timeout=180, capture_output=True,
    )
    if not pdf.exists():
        raise RuntimeError("PowerPoint did not produce a PDF")


def convert_pptx_to_pdf(pptx: Path) -> Path:
    """Return the PDF path for ``pptx`` (cached next to it). Raises RuntimeError if no converter works."""
    pdf = pptx.with_suffix(".pdf")
    if pdf.exists() and pdf.stat().st_mtime >= pptx.stat().st_mtime:
        return pdf

    errors = []
    soffice = _find_soffice()
    if soffice:
        try:
            _convert_with_libreoffice(soffice, pptx, pdf)
            return pdf
        except Exception as e:  # noqa: BLE001
            errors.append(f"LibreOffice: {e}")
    if sys.platform == "win32":
        try:
            _convert_with_powerpoint(pptx, pdf)
            return pdf
        except Exception as e:  # noqa: BLE001
            errors.append(f"PowerPoint: {e}")
    raise RuntimeError(
        "PDF export needs LibreOffice or Microsoft PowerPoint installed. " + "; ".join(errors)
    )
