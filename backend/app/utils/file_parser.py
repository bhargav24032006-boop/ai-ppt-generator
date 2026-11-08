"""Utility to extract text, inspect documents, templates, and process uploaded images."""
from __future__ import annotations

import io
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from PIL import Image
import pypdf
import docx

from ..config import STORAGE_DIR, TEMPLATES_DIR, IMAGES_DIR
from ..services.template_analyzer import analyze_template


def sanitize_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        texts = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text()
            if txt and txt.strip():
                texts.append(f"--- Page {i+1} ---\n{txt.strip()}")
        return "\n\n".join(texts)
    except Exception as e:
        return f"[Failed to parse PDF: {str(e)}]"


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        # Also extract table text
        table_texts = []
        for table in doc.tables:
            for row in table.rows:
                row_str = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_str:
                    table_texts.append(row_str)
        
        all_text = paragraphs + table_texts
        return "\n\n".join(all_text)
    except Exception as e:
        return f"[Failed to parse DOCX: {str(e)}]"


def extract_text_from_pptx(file_bytes: bytes) -> str:
    try:
        from pptx import Presentation
        prs = Presentation(io.BytesIO(file_bytes))
        slide_texts = []
        for idx, slide in enumerate(prs.slides):
            texts = []
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text_frame.text.strip():
                    texts.append(shape.text_frame.text.strip())
            if texts:
                slide_texts.append(f"--- Slide {idx + 1} ---\n" + "\n".join(texts))
        return "\n\n".join(slide_texts)
    except Exception as e:
        return f"[Could not read PPTX text: {e}]"


def process_uploaded_file(file_bytes: bytes, original_filename: str) -> Dict[str, Any]:
    """Inspect and extract content based on file extension."""
    ext = Path(original_filename).suffix.lower()
    file_id = uuid.uuid4().hex
    
    # 1. Documents (PDF, Word, Text, Markdown)
    if ext == ".pdf":
        text = extract_text_from_pdf(file_bytes)
        word_count = len(text.split())
        return {
            "id": file_id,
            "filename": original_filename,
            "file_type": "document",
            "format": "pdf",
            "extracted_text": text,
            "word_count": word_count,
            "summary": f"PDF document ({word_count:,} words extracted)"
        }
    
    elif ext in (".docx", ".doc"):
        text = extract_text_from_docx(file_bytes)
        word_count = len(text.split())
        return {
            "id": file_id,
            "filename": original_filename,
            "file_type": "document",
            "format": "docx",
            "extracted_text": text,
            "word_count": word_count,
            "summary": f"Word document ({word_count:,} words extracted)"
        }
        
    elif ext in (".txt", ".md", ".csv", ".json"):
        try:
            text = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = file_bytes.decode("latin-1", errors="replace")
        word_count = len(text.split())
        return {
            "id": file_id,
            "filename": original_filename,
            "file_type": "document",
            "format": ext.replace(".", ""),
            "extracted_text": text,
            "word_count": word_count,
            "summary": f"Text file ({word_count:,} words)"
        }

    # 2. PowerPoint Templates (.pptx)
    elif ext in (".pptx", ".potx"):
        template_id = file_id
        template_path = TEMPLATES_DIR / f"{template_id}.pptx"
        with open(template_path, "wb") as f:
            f.write(file_bytes)
            
        pptx_text = extract_text_from_pptx(file_bytes)
        word_count = len(pptx_text.split()) if pptx_text else 0

        try:
            template_info = analyze_template(template_path, template_id, original_filename)
            info_dict = template_info.model_dump()
            return {
                "id": template_id,
                "filename": original_filename,
                "file_type": "template",
                "format": "pptx",
                "template_id": template_id,
                "template_info": info_dict,
                "extracted_text": pptx_text,
                "word_count": word_count,
                "summary": f"PowerPoint template with {len(template_info.layouts)} layouts, {template_info.theme.major_font} typography, and {len(info_dict.get('layouts', []))} layouts ({word_count:,} words)"
            }
        except Exception as e:
            return {
                "id": template_id,
                "filename": original_filename,
                "file_type": "template",
                "format": "pptx",
                "template_id": template_id,
                "extracted_text": pptx_text,
                "word_count": word_count,
                "summary": f"PowerPoint template uploaded ({original_filename}, {word_count:,} words extracted)"
            }

    # 3. Images (PNG, JPG, JPEG, WEBP, SVG)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"):
        saved_filename = f"{file_id}{ext}"
        image_path = IMAGES_DIR / saved_filename
        with open(image_path, "wb") as f:
            f.write(file_bytes)
            
        width, height = 0, 0
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
        except Exception:
            pass
            
        return {
            "id": file_id,
            "filename": original_filename,
            "file_type": "image",
            "format": ext.replace(".", ""),
            "image_id": file_id,
            "saved_filename": saved_filename,
            "url": f"/api/images/{saved_filename}",
            "dimensions": {"width": width, "height": height},
            "summary": f"Image asset ({width}x{height}px)"
        }

    # Fallback / other
    else:
        return {
            "id": file_id,
            "filename": original_filename,
            "file_type": "other",
            "format": ext.replace(".", ""),
            "summary": f"File uploaded: {original_filename}"
        }
