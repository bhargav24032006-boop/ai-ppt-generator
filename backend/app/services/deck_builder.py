"""High-fidelity PowerPoint deck generator with theme support, rich card layouts, images & speaker notes."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple

import requests
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE

from ..schemas import Outline, Slide
from ..themes import get_theme, ThemePreset
from ..config import DECKS_DIR, TEMPLATES_DIR, IMAGES_DIR


def resolve_image_path(image_url: str) -> Optional[Path]:
    """Resolve an image URL or filename to an existing Path on disk, downloading if external."""
    if not image_url:
        return None
    clean_name = image_url.split("/")[-1].split("?")[0]
    local_path = IMAGES_DIR / clean_name
    if local_path.exists():
        return local_path
    if image_url.startswith("http://") or image_url.startswith("https://"):
        try:
            resp = requests.get(image_url, timeout=12)
            if resp.status_code == 200 and len(resp.content) > 1000:
                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(resp.content)
                return local_path
        except Exception as e:
            print(f"Failed to download image from {image_url}: {e}")
    return None



def _finalize_text_styles(prs) -> None:
    """Copy paragraph-level font settings onto runs and shrink text that would overflow.

    python-pptx's ``paragraph.font`` writes <a:defRPr>, which PowerPoint ignores for
    existing runs; styling must live on the runs themselves.
    """
    def fix_frame(tf, box_h_emu=None, box_w_emu=None):
        total_chars = 0
        paras = list(tf.paragraphs)
        for p in paras:
            f = p.font
            for r in p.runs:
                if f.name and not r.font.name:
                    r.font.name = f.name
                if f.size and not r.font.size:
                    r.font.size = f.size
                if f.bold is not None and r.font.bold is None:
                    r.font.bold = f.bold
                if f.italic is not None and r.font.italic is None:
                    r.font.italic = f.italic
                try:
                    if f.color and f.color.type is not None and r.font.color.type is None:
                        r.font.color.rgb = f.color.rgb
                except Exception:
                    pass
            total_chars += len(p.text)
        # Overflow guard: estimate lines needed vs. available height
        if box_h_emu and box_w_emu and paras:
            size_pt = next((p.font.size.pt for p in paras if p.font.size), 14)
            usable_w_in = max((box_w_emu - Inches(0.8)) / 914400, 1)
            usable_h_in = max((box_h_emu - Inches(0.6)) / 914400, 0.5)
            for _ in range(8):
                chars_per_line = max(int(usable_w_in * 72 / (size_pt * 0.5)), 1)
                lines = sum(max(1, -(-len(p.text) // chars_per_line)) for p in paras)
                needed_in = lines * size_pt * 1.5 / 72 + len(paras) * 0.15
                if needed_in <= usable_h_in or size_pt <= 9:
                    break
                size_pt -= 1
            for p in paras:
                orig = p.font.size.pt if p.font.size else 14
                if size_pt < orig:
                    p.font.size = Pt(size_pt)
                    for r in p.runs:
                        r.font.size = Pt(size_pt)

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                tf = shape.text_frame
                if shape.shape_type is not None and tf.text.strip():
                    tf.word_wrap = True
                    is_card = shape.height > Inches(1.5)
                    if is_card and shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
                        tf.vertical_anchor = MSO_ANCHOR.TOP
                        for p in tf.paragraphs:
                            if p.alignment is None:
                                p.alignment = PP_ALIGN.LEFT
                    fix_frame(tf, shape.height if is_card else None, shape.width if is_card else None)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        fix_frame(cell.text_frame)


def _add_fitted_picture(slide, img_path, left, top, box_w, box_h):
    """Add a picture centered in a box, preserving aspect ratio via cropping (no stretch)."""
    pic = slide.shapes.add_picture(str(img_path), int(left), int(top), width=int(box_w), height=int(box_h))
    try:
        iw, ih = pic.image.size
        box_ratio = box_w / box_h
        img_ratio = iw / ih
        if img_ratio > box_ratio:
            crop = (1 - box_ratio / img_ratio) / 2
            pic.crop_left = pic.crop_right = crop
        else:
            crop = (1 - img_ratio / box_ratio) / 2
            pic.crop_top = pic.crop_bottom = crop
    except Exception:
        pass
    return pic


def hex_to_rgb(hex_str: str) -> RGBColor:
    """Convert hex string (with or without #) to RGBColor."""
    clean = hex_str.lstrip("#").strip()
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "6366F1"
    r = int(clean[0:2], 16)
    g = int(clean[2:4], 16)
    b = int(clean[4:6], 16)
    return RGBColor(r, g, b)


def add_background_shape(slide, theme: ThemePreset, width: Inches, height: Inches):
    """Create a solid background shape with subtle accent header line."""
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), width, height
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = hex_to_rgb(theme.bg_color)
    bg.line.color.rgb = hex_to_rgb(theme.bg_color)
    
    # Accent top border line
    accent_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), width, Inches(0.08)
    )
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = hex_to_rgb(theme.accent_primary)
    accent_bar.line.fill.background()


def add_category_badge(slide, theme: ThemePreset, text: str, left: Inches, top: Inches) -> None:
    """Add a category/badge tag pill (e.g. 'EXECUTIVE OVERVIEW')."""
    if not text:
        return
    badge = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(2.8), Inches(0.38)
    )
    badge.fill.solid()
    badge.fill.fore_color.rgb = hex_to_rgb(theme.badge_bg)
    badge.line.color.rgb = hex_to_rgb(theme.accent_primary)
    badge.line.width = Pt(1)
    
    tf = badge.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = text.upper()
    p.alignment = PP_ALIGN.CENTER
    p.font.name = theme.font_title
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = hex_to_rgb(theme.accent_secondary)


def add_slide_header(slide, theme: ThemePreset, slide_data: Slide) -> Tuple[Inches, Inches]:
    """Standard header for content slides."""
    start_top = Inches(0.5)
    
    # Category badge
    if slide_data.category:
        add_category_badge(slide, theme, slide_data.category, Inches(0.8), start_top)
        start_top += Inches(0.5)
    
    # Title Box
    title_box = slide.shapes.add_textbox(Inches(0.8), start_top, Inches(11.7), Inches(0.8))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.title
    p.font.name = theme.font_title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = hex_to_rgb(theme.text_primary)
    
    content_top = start_top + Inches(0.8)
    
    # Subtitle
    if slide_data.subtitle:
        sub_box = slide.shapes.add_textbox(Inches(0.8), content_top, Inches(11.7), Inches(0.45))
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = slide_data.subtitle
        sp.font.name = theme.font_body
        sp.font.size = Pt(14)
        sp.font.color.rgb = hex_to_rgb(theme.text_secondary)
        content_top += Inches(0.5)
        
    return Inches(0.8), content_top + Inches(0.2)


def render_title_slide(slide, theme: ThemePreset, slide_data: Slide, outline_title: str):
    """Hero Title Slide layout with optional AI visual asset."""
    category = slide_data.category or "PRESENTATION DECK"
    img_path = resolve_image_path(slide_data.image_url)

    if img_path and img_path.exists():
        # Dual-column Hero Title layout with visual asset on right
        add_category_badge(slide, theme, category, Inches(0.9), Inches(1.5))
        
        # Left Title Box
        title_box = slide.shapes.add_textbox(Inches(0.9), Inches(2.1), Inches(6.4), Inches(2.3))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = slide_data.title or outline_title
        p.font.name = theme.font_title
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        
        # Subtitle Box
        subtitle = slide_data.subtitle or "AI-Powered Strategy & Execution"
        sub_box = slide.shapes.add_textbox(Inches(0.9), Inches(4.5), Inches(6.4), Inches(1.4))
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = subtitle
        sp.font.name = theme.font_body
        sp.font.size = Pt(16)
        sp.font.color.rgb = hex_to_rgb(theme.text_secondary)
        
        # Decorative line
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(6.0), Inches(3.5), Inches(0.04)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = hex_to_rgb(theme.accent_primary)
        line.line.fill.background()
        
        # Right Image Frame & Picture
        img_left = Inches(7.6)
        img_top = Inches(1.5)
        img_width = Inches(4.8)
        img_height = Inches(4.8)
        
        frame = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, img_left, img_top, img_width, img_height
        )
        frame.fill.solid()
        frame.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        frame.line.color.rgb = hex_to_rgb(theme.accent_primary)
        frame.line.width = Pt(1.5)
        
        try:
            _add_fitted_picture(
                slide, img_path, img_left + Inches(0.15), img_top + Inches(0.15),
                img_width - Inches(0.3), img_height - Inches(0.3)
            )
        except Exception as e:
            print(f"Failed to add hero picture: {e}")
    else:
        # Full width title slide
        add_category_badge(slide, theme, category, Inches(1.0), Inches(1.8))
        
        title_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.4), Inches(10.5), Inches(2.0))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = slide_data.title or outline_title
        p.font.name = theme.font_title
        p.font.size = Pt(40)
        p.font.bold = True
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        
        subtitle = slide_data.subtitle or "AI-Powered Strategy & Execution"
        sub_box = slide.shapes.add_textbox(Inches(1.0), Inches(4.5), Inches(10.5), Inches(1.2))
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = subtitle
        sp.font.name = theme.font_body
        sp.font.size = Pt(18)
        sp.font.color.rgb = hex_to_rgb(theme.text_secondary)
        
        line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(5.8), Inches(4.0), Inches(0.04)
        )
        line.fill.solid()
        line.fill.fore_color.rgb = hex_to_rgb(theme.accent_primary)
        line.line.fill.background()



def render_metrics_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Metrics / KPI Stat Cards Slide."""
    left, top = add_slide_header(slide, theme, slide_data)
    stats = slide_data.stats or []
    if not stats:
        # Fallback to bullets if stats empty
        render_bullets_slide(slide, theme, slide_data)
        return
        
    count = min(len(stats), 4)
    card_width = int((Inches(11.7) - (Inches(0.3) * (count - 1))) / count)
    card_height = Inches(3.8)
    
    for i in range(count):
        stat = stats[i]
        card_left = left + (i * (card_width + Inches(0.3)))
        
        # Background card
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, card_left, top, card_width, card_height
        )
        card.fill.solid()
        card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        card.line.color.rgb = hex_to_rgb(theme.badge_bg)
        card.line.width = Pt(1.5)
        
        # Stat value text box
        val_box = slide.shapes.add_textbox(card_left + Inches(0.2), top + Inches(0.6), card_width - Inches(0.4), Inches(1.2))
        vtf = val_box.text_frame
        vtf.word_wrap = True
        vp = vtf.paragraphs[0]
        vp.text = stat.value
        vp.alignment = PP_ALIGN.CENTER
        vp.font.name = theme.font_title
        vp.font.size = Pt(36)
        vp.font.bold = True
        vp.font.color.rgb = hex_to_rgb(theme.accent_secondary)
        
        # Stat label text box
        lbl_box = slide.shapes.add_textbox(card_left + Inches(0.2), top + Inches(1.9), card_width - Inches(0.4), Inches(1.0))
        ltf = lbl_box.text_frame
        ltf.word_wrap = True
        lp = ltf.paragraphs[0]
        lp.text = stat.label
        lp.alignment = PP_ALIGN.CENTER
        lp.font.name = theme.font_body
        lp.font.size = Pt(14)
        lp.font.bold = True
        lp.font.color.rgb = hex_to_rgb(theme.text_primary)
        
        # Change badge if present
        if stat.change:
            chg_box = slide.shapes.add_textbox(card_left + Inches(0.2), top + Inches(2.9), card_width - Inches(0.4), Inches(0.5))
            ctf = chg_box.text_frame
            ctf.word_wrap = True
            cp = ctf.paragraphs[0]
            cp.text = stat.change
            cp.alignment = PP_ALIGN.CENTER
            cp.font.name = theme.font_body
            cp.font.size = Pt(12)
            cp.font.color.rgb = hex_to_rgb(theme.accent_primary)


def render_two_column_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Two Column Comparison / Dual Pillar layout."""
    left, top = add_slide_header(slide, theme, slide_data)
    col_width = Inches(5.65)
    gap = Inches(0.4)
    height = Inches(4.0)
    
    # Left Column Card
    card_l = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, col_width, height
    )
    card_l.fill.solid()
    card_l.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
    card_l.line.color.rgb = hex_to_rgb(theme.badge_bg)
    card_l.line.width = Pt(1.5)
    
    ltf = card_l.text_frame
    ltf.word_wrap = True
    ltf.margin_left = Inches(0.4)
    ltf.margin_right = Inches(0.4)
    ltf.margin_top = Inches(0.4)
    
    for idx, item in enumerate(slide_data.left):
        p = ltf.paragraphs[0] if idx == 0 else ltf.add_paragraph()
        p.text = f"•  {item.lstrip('•').strip()}"
        p.font.name = theme.font_body
        p.font.size = Pt(14)
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        p.space_after = Pt(12)
        
    # Right Column Card
    card_r = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left + col_width + gap, top, col_width, height
    )
    card_r.fill.solid()
    card_r.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
    card_r.line.color.rgb = hex_to_rgb(theme.accent_primary)
    card_r.line.width = Pt(1.5)
    
    rtf = card_r.text_frame
    rtf.word_wrap = True
    rtf.margin_left = Inches(0.4)
    rtf.margin_right = Inches(0.4)
    rtf.margin_top = Inches(0.4)
    
    for idx, item in enumerate(slide_data.right):
        p = rtf.paragraphs[0] if idx == 0 else rtf.add_paragraph()
        p.text = f"•  {item.lstrip('•').strip()}"
        p.font.name = theme.font_body
        p.font.size = Pt(14)
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        p.space_after = Pt(12)


def render_bullets_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Clean Bullets / Points layout with card background."""
    left, top = add_slide_header(slide, theme, slide_data)
    bullets = slide_data.bullets or []
    
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, Inches(11.7), Inches(4.0)
    )
    card.fill.solid()
    card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
    card.line.color.rgb = hex_to_rgb(theme.badge_bg)
    card.line.width = Pt(1.5)
    
    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.6)
    tf.margin_right = Inches(0.6)
    tf.margin_top = Inches(0.5)
    
    for idx, b in enumerate(bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        clean_text = b.lstrip("•").strip()
        p.text = f"•   {clean_text}"
        p.font.name = theme.font_body
        p.font.size = Pt(16)
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        p.space_after = Pt(16)


def render_image_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Layout pairing text content with an uploaded image."""
    left, top = add_slide_header(slide, theme, slide_data)
    
    text_width = Inches(6.0)
    img_width = Inches(5.3)
    img_height = Inches(3.8)
    img_left = left + text_width + Inches(0.4)
    
    # Left Content Card
    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, text_width, img_height
    )
    card.fill.solid()
    card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
    card.line.color.rgb = hex_to_rgb(theme.badge_bg)
    card.line.width = Pt(1.5)
    
    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.4)
    tf.margin_right = Inches(0.4)
    tf.margin_top = Inches(0.4)
    
    items = slide_data.bullets or [slide_data.subtitle] or []
    for idx, item in enumerate(items):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = f"•  {item.lstrip('•').strip()}"
        p.font.name = theme.font_body
        p.font.size = Pt(14)
        p.font.color.rgb = hex_to_rgb(theme.text_primary)
        p.space_after = Pt(12)
        
    # Check if image file exists
    image_inserted = False
    img_path = resolve_image_path(slide_data.image_url)
    if img_path and img_path.exists():
        try:
            # Subtle card backdrop for picture
            frame = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, img_left, top, img_width, img_height
            )
            frame.fill.solid()
            frame.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
            frame.line.color.rgb = hex_to_rgb(theme.accent_primary)
            frame.line.width = Pt(1.5)

            _add_fitted_picture(
                slide, img_path, img_left + Inches(0.12), top + Inches(0.12),
                img_width - Inches(0.24), img_height - Inches(0.24)
            )
            image_inserted = True
        except Exception as e:
            print(f"Failed to embed picture: {e}")
                
    if not image_inserted:
        # Fallback image placeholder card
        img_card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, img_left, top, img_width, img_height
        )
        img_card.fill.solid()
        img_card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        img_card.line.color.rgb = hex_to_rgb(theme.accent_primary)
        img_card.line.width = Pt(1.5)
        itf = img_card.text_frame
        itf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ip = itf.paragraphs[0]
        ip.text = slide_data.image_caption or "Visual Blueprint / Asset"
        ip.alignment = PP_ALIGN.CENTER
        ip.font.name = theme.font_body
        ip.font.size = Pt(14)
        ip.font.color.rgb = hex_to_rgb(theme.accent_secondary)


def render_quote_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Executive Quote / Vision Statement slide layout."""
    left, top = add_slide_header(slide, theme, slide_data)
    card_width = Inches(11.7)
    card_height = Inches(3.8)

    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, left, top, card_width, card_height
    )
    card.fill.solid()
    card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
    card.line.color.rgb = hex_to_rgb(theme.accent_primary)
    card.line.width = Pt(2.0)

    # Accent vertical bar on the left
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left + Inches(0.5), top + Inches(0.6), Inches(0.1), card_height - Inches(1.2)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = hex_to_rgb(theme.accent_secondary)
    bar.line.fill.background()

    # Quote text
    quote_text = slide_data.quote or slide_data.subtitle or (slide_data.bullets[0] if slide_data.bullets else "Innovation distinguishes between a leader and a follower.")
    q_box = slide.shapes.add_textbox(left + Inches(0.9), top + Inches(0.8), card_width - Inches(1.5), Inches(1.8))
    qtf = q_box.text_frame
    qtf.word_wrap = True
    qp = qtf.paragraphs[0]
    qp.text = f'"{quote_text.strip()}"'
    qp.font.name = theme.font_title
    qp.font.size = Pt(24)
    qp.font.italic = True
    qp.font.color.rgb = hex_to_rgb(theme.text_primary)


def render_table_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Render a clean structured table slide."""
    left, top = add_slide_header(slide, theme, slide_data)
    table_spec = slide_data.table
    
    headers = table_spec.headers if table_spec and table_spec.headers else [
        "Dimension", "Baseline State", "Target Benchmark", "Velocity Multiplier"
    ]
    rows = table_spec.rows if table_spec and table_spec.rows else [
        ["Speed & Latency", "3-5 business days manual drafting", "Instant multi-modal synthesis (< 2s)", "98% faster turnaround"],
        ["Visual Fidelity", "Generic clip art & stock templates", "Tailored neural isometric 3D renders", "10x visual engagement"],
        ["Data Accuracy", "Prone to manual transcription errors", "Contextual schema grounding", "100% verifiable metrics"],
        ["Iterability", "Tedious slide-by-slide reformatting", "Real-time conversational refinement", "Zero workflow friction"],
    ]
    
    num_rows = len(rows) + 1
    num_cols = len(headers)
    table_width = Inches(11.7)
    table_height = Inches(min(3.8, 0.6 * num_rows))
    
    shape = slide.shapes.add_table(num_rows, num_cols, left, top, table_width, table_height)
    tbl = shape.table
    
    # Header row
    for col_idx, header in enumerate(headers):
        cell = tbl.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = hex_to_rgb(theme.badge_bg)
        tf = cell.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.text = header
        p.font.name = theme.font_title
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = hex_to_rgb(theme.accent_secondary)
        
    # Data rows
    for row_idx, row_data in enumerate(rows):
        for col_idx in range(num_cols):
            cell = tbl.cell(row_idx + 1, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = hex_to_rgb(theme.card_bg) if row_idx % 2 == 0 else hex_to_rgb(theme.bg_color)
            tf = cell.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = tf.paragraphs[0]
            val = row_data[col_idx] if col_idx < len(row_data) else ""
            p.text = str(val)
            p.font.name = theme.font_body
            p.font.size = Pt(12)
            p.font.color.rgb = hex_to_rgb(theme.text_primary)


def render_timeline_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Horizontal process / timeline roadmap layout."""
    left, top = add_slide_header(slide, theme, slide_data)
    steps = slide_data.bullets or ["Phase 1: Discovery & Scoping", "Phase 2: Architecture & Prototype", "Phase 3: Production Rollout", "Phase 4: Global Scale"]
    count = min(len(steps), 4)
    card_width = int((Inches(11.7) - (Inches(0.3) * (count - 1))) / count)
    card_height = Inches(3.8)
    
    for i in range(count):
        step_text = steps[i]
        card_left = left + (i * (card_width + Inches(0.3)))
        
        card = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, card_left, top, card_width, card_height
        )
        card.fill.solid()
        card.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        card.line.color.rgb = hex_to_rgb(theme.accent_primary) if i == 0 else hex_to_rgb(theme.badge_bg)
        card.line.width = Pt(1.5)
        
        # Step number pill
        pill = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, card_left + Inches(0.3), top + Inches(0.4), Inches(0.6), Inches(0.6)
        )
        pill.fill.solid()
        pill.fill.fore_color.rgb = hex_to_rgb(theme.accent_primary)
        pill.line.fill.background()
        ptf = pill.text_frame
        ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
        pp = ptf.paragraphs[0]
        pp.text = f"0{i+1}"
        pp.alignment = PP_ALIGN.CENTER
        pp.font.name = theme.font_title
        pp.font.size = Pt(13)
        pp.font.bold = True
        pp.font.color.rgb = hex_to_rgb("FFFFFF")
        
        # Content box
        tbox = slide.shapes.add_textbox(card_left + Inches(0.2), top + Inches(1.2), card_width - Inches(0.4), card_height - Inches(1.4))
        tf = tbox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = step_text.lstrip("•").strip()
        p.font.name = theme.font_body
        p.font.size = Pt(14)
        p.font.color.rgb = hex_to_rgb(theme.text_primary)


def render_diagram_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Render an editable multi-tier System Architecture Diagram slide using native PowerPoint shapes."""
    from .architecture_engine import synthesize_diagram_spec

    left, top = add_slide_header(slide, theme, slide_data)
    diag = (
        slide_data.visual.diagram
        if (slide_data.visual and slide_data.visual.diagram and slide_data.visual.diagram.nodes)
        else synthesize_diagram_spec(slide_data.title or "System Architecture", bullets=slide_data.bullets)
    )

    nodes = diag.nodes or []
    clusters = diag.clusters or []
    edges = diag.edges or []

    # Group nodes into columns by cluster
    cluster_groups = []
    if clusters:
        used = set()
        for cl in clusters:
            cnodes = [n for n in nodes if n.cluster == cl.id]
            if cnodes:
                cluster_groups.append((cl.label, cnodes))
                used.update(n.id for n in cnodes)
        rem = [n for n in nodes if n.id not in used]
        if rem:
            if cluster_groups:
                cluster_groups[-1][1].extend(rem)
            else:
                cluster_groups.append(("Core Architecture", rem))
    if not cluster_groups:
        col_count = min(4, max(2, (len(nodes) + 1) // 2))
        chunk = max(1, (len(nodes) + col_count - 1) // col_count)
        for i in range(0, len(nodes), chunk):
            cluster_groups.append((f"Layer {len(cluster_groups) + 1}", nodes[i:i + chunk]))

    num_cols = len(cluster_groups)
    total_w = Inches(11.7)
    has_bottom_insights = bool(slide_data.bullets)
    diag_h = Inches(2.85) if has_bottom_insights else Inches(3.85)
    col_gap = Inches(0.32)
    col_w = int((total_w - col_gap * (num_cols - 1)) / max(1, num_cols))

    shape_map = {
        "database": MSO_SHAPE.CAN,
        "cloud": MSO_SHAPE.CLOUD,
        "decision": MSO_SHAPE.DIAMOND,
        "user": MSO_SHAPE.HEXAGON,
        "device": MSO_SHAPE.OCTAGON,
        "queue": MSO_SHAPE.FLOWCHART_DIRECT_ACCESS_STORAGE,
        "start_end": MSO_SHAPE.FLOWCHART_TERMINATOR,
        "process": MSO_SHAPE.ROUNDED_RECTANGLE,
        "box": MSO_SHAPE.ROUNDED_RECTANGLE,
    }

    for c_idx, (c_label, c_nodes) in enumerate(cluster_groups):
        c_left = left + c_idx * (col_w + col_gap)

        # Cluster swimlane container
        lane = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, c_left, top, col_w, diag_h
        )
        lane.fill.solid()
        lane.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        lane.line.color.rgb = hex_to_rgb(theme.accent_primary if c_idx % 2 == 0 else theme.accent_secondary)
        lane.line.width = Pt(1.25)

        # Cluster header label
        hdr_box = slide.shapes.add_textbox(c_left + Inches(0.1), top + Inches(0.06), col_w - Inches(0.2), Inches(0.36))
        htf = hdr_box.text_frame
        htf.word_wrap = True
        hp = htf.paragraphs[0]
        hp.text = c_label.upper()
        hp.alignment = PP_ALIGN.CENTER
        hp.font.name = theme.font_title
        hp.font.size = Pt(10)
        hp.font.bold = True
        hp.font.color.rgb = hex_to_rgb(theme.accent_secondary if c_idx % 2 else theme.accent_primary)

        # Render nodes inside this cluster column
        n_count = len(c_nodes)
        inner_top = top + Inches(0.46)
        avail_h = diag_h - Inches(0.58)
        node_gap = Inches(0.16)
        node_h = int((avail_h - node_gap * max(0, n_count - 1)) / max(1, n_count))
        node_h = min(int(Inches(1.15)), max(int(Inches(0.62)), node_h))

        for n_idx, node in enumerate(c_nodes):
            n_top = inner_top + n_idx * (node_h + node_gap)
            n_left = c_left + Inches(0.16)
            n_w = col_w - Inches(0.32)
            mso_type = shape_map.get(node.shape, MSO_SHAPE.ROUNDED_RECTANGLE)

            n_shape = slide.shapes.add_shape(mso_type, n_left, n_top, n_w, node_h)
            n_shape.fill.solid()
            n_shape.fill.fore_color.rgb = hex_to_rgb(theme.badge_bg)
            n_shape.line.color.rgb = hex_to_rgb(theme.accent_primary if n_idx % 2 == 0 else theme.accent_secondary)
            n_shape.line.width = Pt(1.5)

            ntf = n_shape.text_frame
            ntf.word_wrap = True
            ntf.vertical_anchor = MSO_ANCHOR.MIDDLE
            np_para = ntf.paragraphs[0]
            np_para.text = node.label
            np_para.alignment = PP_ALIGN.CENTER
            np_para.font.name = theme.font_title
            np_para.font.size = Pt(11)
            np_para.font.bold = True
            np_para.font.color.rgb = hex_to_rgb(theme.text_primary)

        # Draw inter-tier flow arrow to next cluster column
        if c_idx < num_cols - 1:
            arrow_left = c_left + col_w + Inches(0.04)
            arrow_top = top + int(diag_h / 2) - Inches(0.14)
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW, arrow_left, arrow_top, col_gap - Inches(0.08), Inches(0.28)
            )
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = hex_to_rgb(theme.accent_secondary)
            arrow.line.fill.background()

    # Bottom architectural insights / plan strip if bullets exist
    if has_bottom_insights:
        strip_top = top + diag_h + Inches(0.18)
        strip_h = Inches(1.0)
        strip = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, strip_top, total_w, strip_h
        )
        strip.fill.solid()
        strip.fill.fore_color.rgb = hex_to_rgb(theme.card_bg)
        strip.line.color.rgb = hex_to_rgb(theme.badge_bg)
        strip.line.width = Pt(1)

        stf = strip.text_frame
        stf.word_wrap = True
        stf.margin_left = Inches(0.25)
        stf.margin_right = Inches(0.25)
        stf.margin_top = Inches(0.12)
        for b_idx, b_text in enumerate(slide_data.bullets[:2]):
            bp = stf.paragraphs[0] if b_idx == 0 else stf.add_paragraph()
            bp.text = f"▸  {b_text.lstrip('•▸').strip()}"
            bp.font.name = theme.font_body
            bp.font.size = Pt(11)
            bp.font.color.rgb = hex_to_rgb(theme.text_primary)
            bp.space_after = Pt(4)


def render_section_slide(slide, theme: ThemePreset, slide_data: Slide):
    """Render a dramatic Section Header / Transition slide."""
    category = slide_data.category or "SECTION BREAK"
    add_category_badge(slide, theme, category, Inches(1.5), Inches(2.2))
    
    title_box = slide.shapes.add_textbox(Inches(1.5), Inches(2.8), Inches(10.3), Inches(1.8))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = slide_data.title
    p.font.name = theme.font_title
    p.font.size = Pt(38)
    p.font.bold = True
    p.font.color.rgb = hex_to_rgb(theme.text_primary)
    
    if slide_data.subtitle:
        sub_box = slide.shapes.add_textbox(Inches(1.5), Inches(4.8), Inches(10.3), Inches(1.0))
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = slide_data.subtitle
        sp.font.name = theme.font_body
        sp.font.size = Pt(18)
        sp.font.color.rgb = hex_to_rgb(theme.text_secondary)
        
    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(1.5), Inches(6.0), Inches(4.5), Inches(0.05)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = hex_to_rgb(theme.accent_primary)
    line.line.fill.background()


def add_slide_footer(
    slide,
    theme: ThemePreset,
    deck_title: str,
    slide_index: int,
    total_slides: int,
    width: Inches,
    height: Inches
) -> None:
    """Render subtle executive PowerPoint footer with deck title, divider line, and running slide counter."""
    footer_top = height - Inches(0.48)
    line_top = footer_top - Inches(0.08)

    # 1. Subtle hairline divider rule
    divider = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.8), line_top, width - Inches(1.6), Pt(1)
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = hex_to_rgb(theme.badge_bg)
    divider.line.fill.background()

    # 2. Deck title on left
    tbox = slide.shapes.add_textbox(Inches(0.8), footer_top, width - Inches(3.6), Inches(0.35))
    tf = tbox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = deck_title or "Executive Presentation"
    p.font.name = theme.font_body
    p.font.size = Pt(9)
    p.font.color.rgb = hex_to_rgb(theme.text_secondary)

    # 3. Slide counter on right (e.g. "02 / 08")
    counter_box = slide.shapes.add_textbox(width - Inches(2.6), footer_top, Inches(1.8), Inches(0.35))
    ctf = counter_box.text_frame
    cp = ctf.paragraphs[0]
    cp.alignment = PP_ALIGN.RIGHT
    cp.text = f"{slide_index:02d} / {total_slides:02d}"
    cp.font.name = theme.font_body
    cp.font.size = Pt(9)
    cp.font.bold = True
    cp.font.color.rgb = hex_to_rgb(theme.text_secondary)


def create_presentation(
    outline: Outline,
    template_id: str = "",
    theme_id: str = "",
    aspect_ratio: str = "16:9"
) -> str:
    """Generate a PowerPoint presentation (.pptx) and return the file_id.
    If template_id is provided, utilizes the deep Reverse Engineering & Neural Template Builder.
    """
    active_template_id = template_id or outline.template_id
    if active_template_id:
        try:
            from .template_deck_builder import generate_presentation_from_template
            file_id, _ = generate_presentation_from_template(outline, active_template_id)
            return file_id
        except Exception as e:
            print(f"Template generator failed, falling back to rich theme builder: {e}")

    prs = Presentation()
    
    # Set dimensions: 16:9 widescreen (13.333 x 7.5 inches) or 4:3 standard (10.0 x 7.5 inches)
    if aspect_ratio == "4:3":
        prs.slide_width = Inches(10.0)
        prs.slide_height = Inches(7.5)
    else:
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
    
    active_theme_id = theme_id or outline.theme_id or "google-gemini"
    theme = get_theme(active_theme_id)
    
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    total_slides = len(outline.slides)
    
    for idx, slide_data in enumerate(outline.slides):
        slide = prs.slides.add_slide(blank_layout)
        
        # 1. Base slide background
        add_background_shape(slide, theme, prs.slide_width, prs.slide_height)
        
        # 2. Render layout type
        stype = slide_data.type
        if stype == "title":
            render_title_slide(slide, theme, slide_data, outline.title)
        elif stype == "section":
            render_section_slide(slide, theme, slide_data)
        elif stype == "metrics" or (slide_data.stats and len(slide_data.stats) > 0):
            render_metrics_slide(slide, theme, slide_data)
        elif stype == "two_column" or (slide_data.left and slide_data.right):
            render_two_column_slide(slide, theme, slide_data)
        elif stype in ("timeline", "process"):
            render_timeline_slide(slide, theme, slide_data)
        elif stype == "diagram" or (slide_data.visual and slide_data.visual.diagram and slide_data.visual.diagram.nodes):
            render_diagram_slide(slide, theme, slide_data)
        elif stype == "table" or slide_data.table:
            render_table_slide(slide, theme, slide_data)
        elif stype == "image_text" or (slide_data.image_url and stype != "title"):
            render_image_slide(slide, theme, slide_data)
        elif stype == "quote" or slide_data.quote:
            render_quote_slide(slide, theme, slide_data)
        elif stype == "conclusion":
            render_bullets_slide(slide, theme, slide_data)
        else:
            render_bullets_slide(slide, theme, slide_data)
            
        # 3. Professional slide footer on all content slides
        if stype not in ("title", "section"):
            add_slide_footer(
                slide, theme, outline.title, idx + 1, total_slides,
                prs.slide_width, prs.slide_height
            )

        # 4. Speaker notes
        if slide_data.notes:
            try:
                notes_slide = slide.notes_slide
                text_frame = notes_slide.notes_text_frame
                text_frame.text = slide_data.notes
            except Exception as e:
                print(f"Could not write speaker notes: {e}")


    _finalize_text_styles(prs)

    file_id = uuid.uuid4().hex
    filepath = DECKS_DIR / f"{file_id}.pptx"
    prs.save(str(filepath))
    return file_id
