import io
import pytest
import docx
from pptx import Presentation
from app.utils.file_parser import (
    process_uploaded_file,
    extract_text_from_docx,
    extract_text_from_pptx
)

def test_parse_plain_text():
    sample_text = "This is a strategic review of AI agents.\nMilestones and targets."
    res = process_uploaded_file(sample_text.encode("utf-8"), "notes.txt")
    assert res["file_type"] == "document"
    assert res["format"] == "txt"
    assert "strategic review" in res["extracted_text"]
    assert res["word_count"] > 0

def test_parse_markdown():
    sample_md = "# Architecture Keynote\n- High availability\n- Microservices"
    res = process_uploaded_file(sample_md.encode("utf-8"), "arch.md")
    assert res["file_type"] == "document"
    assert res["format"] == "md"
    assert "High availability" in res["extracted_text"]

def test_parse_docx():
    # Build a small in-memory docx
    doc = docx.Document()
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph("Revenue grew 45% YoY with 99.4% uptime.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    extracted = extract_text_from_docx(docx_bytes)
    assert "Executive Summary" in extracted
    assert "Revenue grew" in extracted

    res = process_uploaded_file(docx_bytes, "report.docx")
    assert res["file_type"] == "document"
    assert res["format"] == "docx"
    assert "Executive Summary" in res["extracted_text"]

def test_parse_pptx():
    # Build a small in-memory pptx
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Sample PPTX Title"
    slide.placeholders[1].text = "Subtitle content"
    buf = io.BytesIO()
    prs.save(buf)
    pptx_bytes = buf.getvalue()

    extracted = extract_text_from_pptx(pptx_bytes)
    assert "Sample PPTX Title" in extracted

    res = process_uploaded_file(pptx_bytes, "template.pptx")
    assert res["file_type"] == "template"
    assert res["format"] == "pptx"
    assert "template_id" in res
