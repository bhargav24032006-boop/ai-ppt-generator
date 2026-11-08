"""Slide-to-Image and Presentation Image Export Service.

Supports native Microsoft PowerPoint rendering at 1920x1080 resolution,
with graceful fallbacks to PDF page rasterization and high-res Pillow rendering.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from PIL import Image, ImageDraw

from ..config import DECKS_DIR, STORAGE_DIR


def _get_slides_dir(file_id: str) -> Path:
    slides_dir = DECKS_DIR / f"{file_id}_slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    return slides_dir


def _export_via_powerpoint_com(pptx_path: Path, output_dir: Path) -> List[Path]:
    """Export slides to 1920x1080 PNG using Microsoft PowerPoint COM automation."""
    abs_pptx = pptx_path.resolve()
    abs_out = output_dir.resolve()
    
    ps_script = f'''
$ErrorActionPreference = "Stop"
$app = $null
try {{
    $app = New-Object -ComObject PowerPoint.Application
    $p = $app.Presentations.Open('{abs_pptx}', $true, $false, $false)
    $i = 1
    foreach ($slide in $p.Slides) {{
        $slidePath = Join-Path '{abs_out}' ("slide_" + $i + ".png")
        $slide.Export($slidePath, "PNG", 1920, 1080)
        $i++
    }}
    $p.Close()
}} finally {{
    if ($app -ne $null) {{
        $app.Quit()
        [System.GC]::Collect()
        [System.GC]::WaitForPendingFinalizers()
    }}
}}
'''
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as tf:
        tf.write(ps_script)
        script_path = Path(tf.name)

    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            check=True, timeout=60, capture_output=True, text=True
        )
    finally:
        if script_path.exists():
            script_path.unlink()

    images = sorted(
        output_dir.glob("slide_*.png"),
        key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0
    )
    return images


def _export_via_pdf_fallback(pptx_path: Path, output_dir: Path) -> List[Path]:
    """Attempt export via PDF converter (LibreOffice or PowerPoint COM) + rasterizer."""
    from .pdf_export import convert_pptx_to_pdf
    pdf_path = convert_pptx_to_pdf(pptx_path)
    
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            out_files = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=150)
                out_path = output_dir / f"slide_{i+1}.png"
                pix.save(str(out_path))
                out_files.append(out_path)
            doc.close()
            return out_files
        except ImportError:
            pass
    except Exception:
        pass
    return []


def _export_via_pillow_fallback(file_id: str, output_dir: Path) -> List[Path]:
    """High-res visual fallback using Pillow when Office automation is completely unavailable."""
    from pptx import Presentation

    pptx_path = DECKS_DIR / f"{file_id}.pptx"
    prs = Presentation(str(pptx_path))
    out_files = []

    width, height = 1920, 1080
    for idx, slide in enumerate(prs.slides):
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)

        # Header accent bar
        draw.rectangle([0, 0, width, 12], fill=(99, 102, 241))

        # Extract text snippets from shapes
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                texts.append(shape.text_frame.text.strip())

        title_text = texts[0] if texts else f"Slide {idx + 1}"
        subtitle_text = texts[1] if len(texts) > 1 else ""

        # Draw card container
        draw.rounded_rectangle(
            [120, 120, width - 120, height - 120],
            radius=20,
            fill=(30, 41, 59),
            outline=(99, 102, 241),
            width=2
        )

        # Draw Title & subtitle
        draw.text((180, 180), title_text[:70], fill=(255, 255, 255))
        if subtitle_text:
            draw.text((180, 240), subtitle_text[:100], fill=(148, 163, 184))

        # Bullets / content
        start_y = 340
        for t in texts[2:7]:
            draw.text((200, start_y), f"• {t[:90]}", fill=(226, 232, 240))
            start_y += 60

        # Footer
        draw.text((180, height - 170), f"Slide {idx + 1} of {len(prs.slides)}", fill=(100, 116, 139))

        out_path = output_dir / f"slide_{idx + 1}.png"
        img.save(str(out_path), "PNG")
        out_files.append(out_path)

    return out_files


def export_presentation_slides_to_images(file_id: str, force_regenerate: bool = False) -> List[Dict[str, Any]]:
    """Export or retrieve pre-rendered slide images for a presentation."""
    pptx_path = DECKS_DIR / f"{file_id}.pptx"
    if not pptx_path.exists():
        raise FileNotFoundError(f"Presentation deck '{file_id}.pptx' not found")

    output_dir = _get_slides_dir(file_id)

    # Check cache
    existing = sorted(
        output_dir.glob("slide_*.png"),
        key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0
    )
    if existing and not force_regenerate and pptx_path.stat().st_mtime <= existing[0].stat().st_mtime:
        return [
            {
                "slide_index": int(p.stem.split("_")[-1]),
                "filename": p.name,
                "url": f"/api/download/{file_id}/slides/{p.stem.split('_')[-1]}/image",
                "width": 1920,
                "height": 1080
            }
            for p in existing
        ]

    # Clean old images if regenerating
    for f in output_dir.glob("slide_*.png"):
        try:
            f.unlink()
        except Exception:
            pass

    # Try PowerPoint COM first (Highest quality native rendering)
    generated: List[Path] = []
    if sys.platform == "win32":
        try:
            generated = _export_via_powerpoint_com(pptx_path, output_dir)
        except Exception as e:
            print(f"[SlideExportService] PowerPoint COM export warning: {e}. Trying fallbacks.")

    # Try PDF rasterization fallback
    if not generated:
        try:
            generated = _export_via_pdf_fallback(pptx_path, output_dir)
        except Exception as e:
            print(f"[SlideExportService] PDF export warning: {e}")

    # Fallback to high-res Pillow rendering
    if not generated:
        generated = _export_via_pillow_fallback(file_id, output_dir)

    results = []
    for p in generated:
        idx_str = p.stem.split("_")[-1]
        results.append({
            "slide_index": int(idx_str) if idx_str.isdigit() else 1,
            "filename": p.name,
            "url": f"/api/download/{file_id}/slides/{idx_str}/image",
            "width": 1920,
            "height": 1080
        })

    return results


def get_slide_image_path(file_id: str, slide_index: int) -> Optional[Path]:
    """Retrieve Path for an individual slide image, generating if not yet cached.
    Supports both 0-indexed (0..N-1) and 1-indexed (1..N) requests gracefully.
    """
    output_dir = _get_slides_dir(file_id)
    
    # Check 1-indexed or direct match first
    candidates = [
        output_dir / f"slide_{slide_index}.png",
        output_dir / f"slide_{slide_index + 1}.png" if slide_index >= 0 else None
    ]
    for c in candidates:
        if c and c.exists():
            return c

    # Trigger generation
    export_presentation_slides_to_images(file_id)
    
    for c in candidates:
        if c and c.exists():
            return c

    # Fallback to sorted list by index
    existing = sorted(output_dir.glob("slide_*.png"), key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else 0)
    if existing:
        if 0 <= slide_index < len(existing):
            return existing[slide_index]
        if 1 <= slide_index <= len(existing):
            return existing[slide_index - 1]

    return None



def create_slides_zip(file_id: str) -> Path:
    """Create a ZIP file containing all exported slide images."""
    slides_info = export_presentation_slides_to_images(file_id)
    if not slides_info:
        raise RuntimeError("No slide images could be generated for export")

    zip_path = DECKS_DIR / f"{file_id}_images.zip"
    output_dir = _get_slides_dir(file_id)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for info in slides_info:
            img_file = output_dir / info["filename"]
            if img_file.exists():
                arcname = f"Slide_{info['slide_index']:02d}.png"
                zf.write(str(img_file), arcname=arcname)

    return zip_path
