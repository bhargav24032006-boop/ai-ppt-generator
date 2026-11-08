"""Template-Driven PowerPoint Deck Builder.

Uses an uploaded/selected template (.pptx) as the *design source* and produces a
real, editable presentation:

* The template file is copied, so slide masters, layouts, theme fonts/colours and
  backgrounds are preserved exactly.
* For every generated slide, a template slide is cloned (including its image
  relationships, so logos and background pictures keep working).
* The template's "chrome" (backgrounds, header band, logo, footer band) is kept,
  while the template's previous body content is removed.
* New content is laid out in the free body area with native, editable shapes
  (bullet panels, comparison columns, KPI cards, timelines, tables, quotes) that
  are coloured from the template's palette, with text auto-sized to fit.
"""
from __future__ import annotations

import copy
import math
import shutil
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.dml import MSO_FILL
from pptx.oxml.ns import qn

from ..schemas import Outline, Slide
from ..config import DECKS_DIR, TEMPLATES_DIR
from .reverse_engineering_engine import reverse_engineer_template, ReverseEngineeredTemplate
from .neural_engine import predict_slide_archetype
from .deck_builder import resolve_image_path
from .image_service import generate_slide_image

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EMU_PER_IN = 914400


# ============================================================================
# Template lookup
# ============================================================================
def find_template_file(template_id: str) -> Optional[Path]:
    """Locate the template PPTX file by ID or name in storage/templates."""
    if not template_id:
        existing = list(TEMPLATES_DIR.glob("*.pptx"))
        return existing[0] if existing else None

    # 1. Exact match in TEMPLATES_DIR
    p1 = TEMPLATES_DIR / f"{template_id}.pptx"
    if p1.exists():
        return p1

    p2 = TEMPLATES_DIR / template_id
    if p2.exists() and p2.is_file():
        return p2

    # 2. Check if template_id is a partial name
    for f in TEMPLATES_DIR.glob("*.pptx"):
        if template_id.lower() in f.stem.lower() or template_id.lower() in f.name.lower():
            return f

    # 3. Fallback to any existing template in storage/templates
    existing = list(TEMPLATES_DIR.glob("*.pptx"))
    if existing:
        return existing[0]

    return None


# ============================================================================
# Colour helpers & palette
# ============================================================================
def _norm_hex(h: Optional[str], default: str = "000000") -> str:
    h = (h or "").lstrip("#").strip().upper()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return h if len(h) == 6 and all(c in "0123456789ABCDEF" for c in h) else default


def _lum(h: str) -> float:
    h = _norm_hex(h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _blend(a: str, b: str, t: float) -> str:
    a, b = _norm_hex(a), _norm_hex(b)
    out = []
    for i in (0, 2, 4):
        va, vb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(f"{round(va + (vb - va) * t):02X}")
    return "".join(out)


def _rgb(h: str) -> RGBColor:
    return RGBColor.from_string(_norm_hex(h))


@dataclass
class Palette:
    bg: str
    text: str
    muted: str
    accent: str
    accent2: str
    card: str
    card_line: str
    on_accent: str
    title_font: str
    body_font: str


def _solid_fill_hex(shape) -> Optional[str]:
    try:
        if shape.fill.type == MSO_FILL.SOLID:
            return str(shape.fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _run_colors(shape) -> List[str]:
    out = []
    try:
        for p in shape.text_frame.paragraphs:
            for r in p.runs:
                if not r.text.strip():
                    continue
                try:
                    if r.font.color and r.font.color.type is not None and r.font.color.rgb:
                        out.append(str(r.font.color.rgb))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def _detect_background(slide, meta: ReverseEngineeredTemplate, sw: int, sh: int) -> str:
    # Full-slide solid shape acting as background
    for shp in slide.shapes:
        try:
            if shp.width >= sw * 0.9 and shp.height >= sh * 0.85:
                fh = _solid_fill_hex(shp)
                if fh:
                    return fh
        except Exception:
            pass
    for owner in (slide, slide.slide_layout, slide.slide_layout.slide_master):
        try:
            fill = owner.background.fill
            if fill.type == MSO_FILL.SOLID:
                return str(fill.fore_color.rgb)
        except Exception:
            pass
    return _norm_hex(meta.background_color, "FFFFFF")


def _build_palette(meta: ReverseEngineeredTemplate, bg: str,
                   text_samples: List[str], fill_samples: List[str]) -> Palette:
    bg = _norm_hex(bg, "FFFFFF")
    dark = _lum(bg) < 0.5

    text = None
    for c, _ in Counter(text_samples).most_common():
        if abs(_lum(c) - _lum(bg)) >= 0.45:
            text = c
            break
    text = _norm_hex(text, "F1F5F9" if dark else "1F2937")

    accent = None
    for cand in [meta.primary_color, meta.secondary_color] + list(meta.accent_colors or []):
        c = _norm_hex(cand, "")
        if c and abs(_lum(c) - _lum(bg)) >= 0.22 and abs(_lum(c) - _lum(text)) >= 0.12:
            accent = c
            break
    accent = accent or ("60A5FA" if dark else "2563EB")

    accent2 = None
    for cand in [meta.secondary_color] + list(meta.accent_colors or []):
        c = _norm_hex(cand, "")
        if c and c != accent and abs(_lum(c) - _lum(bg)) >= 0.2:
            accent2 = c
            break
    accent2 = accent2 or _blend(accent, text, 0.35)

    card = None
    for c, _ in Counter(fill_samples).most_common():
        if abs(_lum(c) - _lum(text)) >= 0.5 and abs(_lum(c) - _lum(bg)) <= 0.12:
            card = c
            break
    card = card or _blend(bg, text, 0.10 if dark else 0.05)

    return Palette(
        bg=bg,
        text=text,
        muted=_blend(text, bg, 0.35),
        accent=accent,
        accent2=accent2,
        card=card,
        card_line=_blend(card, accent, 0.35),
        on_accent="FFFFFF" if _lum(accent) < 0.62 else "111827",
        title_font=meta.title_font or "Calibri",
        body_font=meta.body_font or "Calibri",
    )


# ============================================================================
# Text measurement & primitives
# ============================================================================
def _lines_needed(text: str, width_in: float, size_pt: float) -> int:
    cpl = max(6, int(width_in * 72 / (size_pt * 0.52)))
    lines, cur = 1, 0
    for word in text.split():
        add = len(word) + (1 if cur else 0)
        if cur + add > cpl:
            lines += 1 + (len(word) // cpl)
            cur = len(word) % cpl
        else:
            cur += add
    return lines


def _fit_size(items: List[str], width_in: float, height_in: float,
              max_pt: int = 20, min_pt: int = 10, gap: float = 0.5, indent_in: float = 0.0) -> int:
    items = [i for i in items if i] or [""]
    for size in range(int(max_pt), int(min_pt) - 1, -1):
        total = sum(_lines_needed(i, width_in - indent_in, size) * size * 1.18 / 72 for i in items)
        total += max(0, len(items) - 1) * size * gap / 72
        if total <= height_in:
            return size
    return int(min_pt)


def _clean(text: str, limit: int = 220) -> str:
    t = (text or "").strip().lstrip("•-–—*· ").strip()
    if len(t) > limit:
        t = t[: limit - 1].rsplit(" ", 1)[0] + "…"
    return t


def _clean_items(items: List[str], max_items: int = 6, limit: int = 200) -> List[str]:
    return [c for c in (_clean(i, limit) for i in (items or [])) if c][:max_items]


def _split_lead(item: str) -> Tuple[str, str]:
    """Split 'Heading: detail' into ('Heading', 'detail') for bold lead-ins."""
    for sep in (": ", " — ", " – ", " - "):
        idx = item.find(sep)
        if 2 < idx <= 48:
            return item[:idx].strip(), item[idx + len(sep):].strip()
    return "", item


def _textbox(slide, l, t, w, h, anchor=MSO_ANCHOR.TOP, margin=0.05):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    return tb, tf


def _run(p, text, font, size, color, bold=False, italic=False):
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = _rgb(color)
    return r


def _para(tf, first: bool, text: str, font: str, size: float, color: str,
          bold=False, italic=False, align=None, space_after: float = 0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    if align is not None:
        p.alignment = align
    if space_after:
        p.space_after = Pt(space_after)
    _run(p, text, font, size, color, bold=bold, italic=italic)
    return p


def _set_bullet(p, color_hex: str, indent_in: float = 0.28, char: str = "•"):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(indent_in))))
    pPr.set("indent", str(-int(Inches(indent_in))))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buClr", "a:buFont", "a:buSzPct"):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    bu_clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(bu_clr, qn("a:srgbClr")).set("val", _norm_hex(color_hex))
    etree.SubElement(pPr, qn("a:buSzPct")).set("val", "100000")
    etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
    etree.SubElement(pPr, qn("a:buChar")).set("char", char)


def _write_bullets(tf, items: List[str], pal: Palette, size: int, bullet_color: Optional[str] = None):
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(round(size * 0.5))
        _set_bullet(p, bullet_color or pal.accent)
        head, body = _split_lead(item)
        if head:
            _run(p, head + ": ", pal.body_font, size, pal.text, bold=True)
            _run(p, body, pal.body_font, size, pal.text)
        else:
            _run(p, item, pal.body_font, size, pal.text)


def _card(slide, l, t, w, h, fill: str, line: Optional[str] = None, rounded: bool = True):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(l), Inches(t), Inches(w), Inches(h)
    )
    if rounded:
        try:
            shp.adjustments[0] = min(0.2, 0.12 / max(0.1, min(w, h)))
        except Exception:
            pass
    shp.fill.solid()
    shp.fill.fore_color.rgb = _rgb(fill)
    if line:
        shp.line.color.rgb = _rgb(line)
        shp.line.width = Pt(1)
    else:
        shp.line.fill.background()
    try:
        shp.shadow.inherit = False
    except Exception:
        pass
    return shp


def _picture_cover(slide, img_path: Path, l, t, w, h, replace_el=None):
    """Add a picture that fills the box (centre-cropped, no distortion)."""
    try:
        pic = slide.shapes.add_picture(str(img_path), Inches(l), Inches(t), Inches(w), Inches(h))
    except Exception as e:
        print(f"[template_deck_builder] add_picture failed: {e}")
        return None
    try:
        from PIL import Image
        with Image.open(str(img_path)) as im:
            iw, ih = im.size
        img_ratio, box_ratio = iw / ih, w / h
        if img_ratio > box_ratio:
            excess = 1 - box_ratio / img_ratio
            pic.crop_left = pic.crop_right = excess / 2
        elif img_ratio < box_ratio:
            excess = 1 - img_ratio / box_ratio
            pic.crop_top = pic.crop_bottom = excess / 2
    except Exception:
        pass
    if replace_el is not None:
        try:
            replace_el.addprevious(pic._element)
            replace_el.getparent().remove(replace_el)
        except Exception:
            pass
    return pic


# ============================================================================
# Slide cloning (with relationship remapping)
# ============================================================================
def _remap_rels(el, src_part, dst_part):
    for node in el.iter():
        for attr, val in list(node.attrib.items()):
            if not attr.startswith("{%s}" % R_NS):
                continue
            try:
                rel = src_part.rels[val]
            except Exception:
                continue
            try:
                if rel.is_external:
                    new_rid = dst_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
                else:
                    new_rid = dst_part.relate_to(rel.target_part, rel.reltype)
                node.set(attr, new_rid)
            except Exception as e:
                print(f"[template_deck_builder] rel remap failed: {e}")


def _clone_slide(prs, src):
    """Duplicate a slide with full fidelity: background, shapes and image relationships."""
    new = prs.slides.add_slide(src.slide_layout)
    # Remove auto-generated placeholders (avoids duplicated placeholders)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)

    src_cSld = src._element.cSld
    new_cSld = new._element.cSld
    src_bg = src_cSld.find(qn("p:bg"))
    if src_bg is not None:
        for old in new_cSld.findall(qn("p:bg")):
            new_cSld.remove(old)
        bg_copy = copy.deepcopy(src_bg)
        _remap_rels(bg_copy, src.part, new.part)
        new_cSld.insert(0, bg_copy)

    sp_tree = new.shapes._spTree
    for el in src.shapes._spTree.iterchildren():
        tag = etree.QName(el).localname
        if tag in ("nvGrpSpPr", "grpSpPr", "extLst"):
            continue
        new_el = copy.deepcopy(el)
        _remap_rels(new_el, src.part, new.part)
        sp_tree.append(new_el)
    return new


def _remove_shape(slide, shp):
    el = shp._element
    rids = [v for n in el.iter() for a, v in n.attrib.items() if a.startswith("{%s}" % R_NS)]
    el.getparent().remove(el)
    for rid in rids:
        try:
            slide.part.drop_rel(rid)
        except Exception:
            pass


# ============================================================================
# Template text replacement (preserves the template's run formatting)
# ============================================================================
def _first_run_size_pt(tf) -> Optional[float]:
    for p in tf.paragraphs:
        for r in p.runs:
            if r.text.strip() and r.font.size:
                return r.font.size.pt
    return None


def _replace_text(shape, text: str, max_lines: Optional[int] = None,
                  min_pt: float = 10, default_pt: float = 24):
    """Replace a template text box's text, keeping its exact run style (font, colour,
    weight, theme colours) and shrinking the font so it fits the box."""
    tf = shape.text_frame
    txBody = tf._txBody
    first_r = None
    first_p = None
    for p in tf.paragraphs:
        for r in p.runs:
            if r.text.strip():
                first_r, first_p = r, p
                break
        if first_r is not None:
            break
    rPr = copy.deepcopy(first_r._r.rPr) if first_r is not None and first_r._r.rPr is not None else None
    pPr = copy.deepcopy(first_p._p.pPr) if first_p is not None and first_p._p.pPr is not None else None
    cur_pt = _first_run_size_pt(tf) or default_pt

    paras = txBody.findall(qn("a:p"))
    for extra in paras[1:]:
        txBody.remove(extra)
    p_el = paras[0]
    for child in list(p_el):
        p_el.remove(child)
    if pPr is not None:
        p_el.append(pPr)
    r_el = p_el.add_r()
    r_el.text = text
    if rPr is not None:
        r_el.insert(0, rPr)

    tf.word_wrap = True
    w_in = max(0.5, (shape.width or Inches(4)) / EMU_PER_IN - 0.2)
    h_in = max(0.3, (shape.height or Inches(1)) / EMU_PER_IN - 0.08)
    size = _fit_size([text], w_in, h_in, max_pt=int(cur_pt), min_pt=int(min_pt), gap=0)
    if max_lines:
        while size > min_pt and _lines_needed(text, w_in, size) > max_lines:
            size -= 1
    run = tf.paragraphs[0].runs[0]
    run.font.size = Pt(size)


# ============================================================================
# Chrome analysis: keep template design, strip template content
# ============================================================================
@dataclass
class ChromeInfo:
    title_shape: Any = None
    subtitle_shape: Any = None
    footer_label: Any = None
    page_number: Any = None
    hero_picture: Any = None
    header_bottom_in: float = 0.0
    footer_top_in: float = 0.0
    title_left_in: float = 0.5


def _geom(shp) -> Optional[Tuple[float, float, float, float]]:
    try:
        if None in (shp.left, shp.top, shp.width, shp.height):
            return None
        return (shp.left / EMU_PER_IN, shp.top / EMU_PER_IN, shp.width / EMU_PER_IN, shp.height / EMU_PER_IN)
    except Exception:
        return None


def _is_title_placeholder(shp) -> bool:
    try:
        return shp.is_placeholder and shp.placeholder_format.type in (1, 3)  # TITLE, CENTER_TITLE
    except Exception:
        return False


def _max_font_pt(shp) -> float:
    best = 0.0
    try:
        for p in shp.text_frame.paragraphs:
            for r in p.runs:
                if r.font.size:
                    best = max(best, r.font.size.pt)
    except Exception:
        pass
    return best


def _prepare_content_chrome(slide, sw_in: float, sh_in: float,
                            text_samples: List[str], fill_samples: List[str]) -> ChromeInfo:
    info = ChromeInfo(header_bottom_in=0.0, footer_top_in=sh_in)
    header_limit = sh_in * 0.18
    footer_limit = sh_in * 0.88

    header_texts = []
    for shp in list(slide.shapes):
        g = _geom(shp)
        has_text = shp.has_text_frame and shp.text_frame.text.strip() != ""

        if _is_title_placeholder(shp):
            info.title_shape = shp
            if g:
                info.header_bottom_in = max(info.header_bottom_in, g[1] + g[3])
                info.title_left_in = g[0]
            continue
        if g is None:
            _remove_shape(slide, shp)
            continue
        l, t, w, h = g
        # Full-slide backgrounds stay
        if w >= sw_in * 0.9 and h >= sh_in * 0.85:
            continue
        # Header band
        if t + h <= header_limit and t < sh_in * 0.15:
            info.header_bottom_in = max(info.header_bottom_in, t + h)
            if has_text:
                header_texts.append(shp)
            continue
        # Footer band
        if t >= footer_limit:
            info.footer_top_in = min(info.footer_top_in, t)
            if has_text:
                txt = shp.text_frame.text.strip()
                if txt.isdigit():
                    info.page_number = shp
                elif w >= sw_in * 0.25 and info.footer_label is None:
                    info.footer_label = shp
            continue
        # Body content from the template -> sample its style, then remove
        if has_text:
            text_samples.extend(_run_colors(shp))
        elif shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE and w > 1.0 and h > 0.5:
            fh = _solid_fill_hex(shp)
            if fh:
                fill_samples.append(fh)
        _remove_shape(slide, shp)

    if info.title_shape is None and header_texts:
        wide = sorted([s for s in header_texts if s.width / EMU_PER_IN >= sw_in * 0.3], key=lambda s: s.top)
        if wide:
            info.title_shape = wide[0]
            info.title_left_in = wide[0].left / EMU_PER_IN
            if len(wide) > 1:
                info.subtitle_shape = wide[1]
            for extra in wide[2:]:
                _remove_shape(slide, extra)
        # Long, narrow header texts belong to the old deck; short ones are branding (keep)
        for s in header_texts:
            if s in wide:
                continue
            if len(s.text_frame.text.strip()) > 24:
                _remove_shape(slide, s)
    return info


def _prepare_title_chrome(slide, sw_in: float, sh_in: float) -> ChromeInfo:
    info = ChromeInfo(header_bottom_in=0.0, footer_top_in=sh_in)
    texts = [s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
    placeholders = [s for s in texts if _is_title_placeholder(s)]
    ranked = placeholders + sorted(
        [s for s in texts if s not in placeholders],
        key=lambda s: (_max_font_pt(s), (s.width or 0) * (s.height or 0)),
        reverse=True,
    )
    if ranked:
        info.title_shape = ranked[0]
        for s in ranked[1:]:
            txt = s.text_frame.text.strip()
            g = _geom(s)
            if info.subtitle_shape is None and len(txt) > 12 and g and g[1] < sh_in * 0.88:
                info.subtitle_shape = s
            elif txt.isdigit():
                info.page_number = s
            elif len(txt) > 24:
                _remove_shape(slide, s)

    # Hero picture = largest picture outside the header band
    best_area = sw_in * sh_in * 0.04
    for shp in slide.shapes:
        if shp.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue
        g = _geom(shp)
        if not g or g[1] < sh_in * 0.1:
            continue
        if g[2] >= sw_in * 0.9 and g[3] >= sh_in * 0.85:
            continue  # background picture
        area = g[2] * g[3]
        if area > best_area:
            best_area, info.hero_picture = area, shp
    return info


# ============================================================================
# Body layouts (rendered inside the free body box)
# ============================================================================
def _layout_kind(sd: Slide) -> str:
    bullets = [b for b in (sd.bullets or []) if b and b.strip()]
    if sd.table and sd.table.headers:
        return "table"
    if sd.stats:
        return "metrics"
    if sd.left and sd.right:
        return "two_column"
    if sd.type in ("timeline", "process") and 2 <= len(bullets) <= 5:
        return "timeline"
    if sd.quote and not bullets:
        return "quote"
    if bullets or sd.left or sd.right:
        return "bullets"
    if sd.quote:
        return "quote"
    return "statement"


def _render_bullets(slide, sd: Slide, box, pal: Palette, img_path: Optional[Path]):
    l, t, w, h = box
    items = _clean_items(sd.bullets or (sd.left + sd.right))
    text_w = w
    if img_path:
        img_w = min(w * 0.40, h * 1.1)
        gap = 0.3
        text_w = w - img_w - gap
        _picture_cover(slide, img_path, l + text_w + gap, t, img_w, h)
    _card(slide, l, t, text_w, h, pal.card, pal.card_line)
    _card(slide, l, t + 0.3, 0.07, h - 0.6, pal.accent, rounded=False)
    pad = 0.4
    inner_w, inner_h = text_w - 2 * pad, h - 2 * pad
    size = _fit_size(items, inner_w, inner_h, max_pt=20, min_pt=11, indent_in=0.3)
    _, tf = _textbox(slide, l + pad, t + pad, inner_w, inner_h,
                     anchor=MSO_ANCHOR.MIDDLE if len(items) <= 3 else MSO_ANCHOR.TOP)
    _write_bullets(tf, items, pal, size)


def _render_two_column(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    gap = 0.35
    cw = (w - gap) / 2
    for i, raw in enumerate((sd.left or [], sd.right or [])):
        items = _clean_items(raw)
        heading = ""
        if items and items[0].endswith(":"):
            heading = items.pop(0).rstrip(":")
        x = l + i * (cw + gap)
        color = pal.accent if i == 1 else pal.accent2
        _card(slide, x, t, cw, h, pal.card, pal.card_line)
        _card(slide, x, t, cw, 0.09, color, rounded=False)
        pad = 0.35
        y = t + 0.3
        if heading:
            hs = _fit_size([heading], cw - 2 * pad, 0.6, max_pt=18, min_pt=12, gap=0)
            _, htf = _textbox(slide, x + pad, y, cw - 2 * pad, 0.6, anchor=MSO_ANCHOR.MIDDLE)
            _para(htf, True, heading, pal.title_font, hs, color, bold=True)
            y += 0.7
        inner_h = t + h - pad - y
        size = _fit_size(items, cw - 2 * pad, inner_h, max_pt=18, min_pt=10, indent_in=0.3)
        _, tf = _textbox(slide, x + pad, y, cw - 2 * pad, inner_h)
        _write_bullets(tf, items, pal, size, bullet_color=color)


def _render_metrics(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    stats = (sd.stats or [])[:6]
    bullets = _clean_items(sd.bullets, max_items=3)
    stats_h = h if not bullets else h * 0.58
    rows = 1 if len(stats) <= 4 else 2
    per_row = math.ceil(len(stats) / rows)
    gap = 0.3
    cw = (w - gap * (per_row - 1)) / per_row
    ch = (stats_h - gap * (rows - 1)) / rows
    for i, st in enumerate(stats):
        r, c = divmod(i, per_row)
        x, y = l + c * (cw + gap), t + r * (ch + gap)
        _card(slide, x, y, cw, ch, pal.card, pal.card_line)
        _card(slide, x, y, cw, 0.08, pal.accent if i % 2 == 0 else pal.accent2, rounded=False)
        value = _clean(st.value, 14)
        label = _clean(st.label, 80)
        change = _clean(st.change, 60)
        v_size = int(max(18, min(44, (cw - 0.3) * 72 / (max(3, len(value)) * 0.62), ch * 72 * 0.32)))
        _, vtf = _textbox(slide, x + 0.15, y + ch * 0.12, cw - 0.3, ch * 0.4, anchor=MSO_ANCHOR.MIDDLE)
        _para(vtf, True, value, pal.title_font, v_size, pal.accent, bold=True, align=PP_ALIGN.CENTER)
        lab_items = [label] + ([change] if change else [])
        l_size = _fit_size(lab_items, cw - 0.3, ch * 0.42, max_pt=15, min_pt=9, gap=0.3)
        _, ltf = _textbox(slide, x + 0.15, y + ch * 0.52, cw - 0.3, ch * 0.44)
        _para(ltf, True, label, pal.body_font, l_size, pal.text, bold=True, align=PP_ALIGN.CENTER)
        if change:
            _para(ltf, False, change, pal.body_font, max(9, l_size - 2), pal.muted, align=PP_ALIGN.CENTER)
    if bullets:
        by = t + stats_h + 0.3
        bh = t + h - by
        _card(slide, l, by, w, bh, pal.card, pal.card_line)
        size = _fit_size(bullets, w - 0.8, bh - 0.4, max_pt=16, min_pt=10, indent_in=0.3)
        _, tf = _textbox(slide, l + 0.4, by + 0.2, w - 0.8, bh - 0.4, anchor=MSO_ANCHOR.MIDDLE)
        _write_bullets(tf, bullets, pal, size)


def _render_timeline(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    steps = _clean_items(sd.bullets, max_items=5, limit=170)
    n = len(steps)
    gap = 0.25
    cw = (w - gap * (n - 1)) / n
    dot = 0.62
    line_y = t + dot / 2
    _card(slide, l + cw / 2, line_y - 0.025, w - cw, 0.05, pal.card_line, rounded=False)
    for i, step in enumerate(steps):
        x = l + i * (cw + gap)
        cx = x + cw / 2 - dot / 2
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx), Inches(t), Inches(dot), Inches(dot))
        circ.fill.solid()
        circ.fill.fore_color.rgb = _rgb(pal.accent if i % 2 == 0 else pal.accent2)
        circ.line.fill.background()
        ctf = circ.text_frame
        ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ctf.margin_left = ctf.margin_right = 0
        _para(ctf, True, f"{i + 1:02d}", pal.title_font, 14, pal.on_accent, bold=True, align=PP_ALIGN.CENTER)

        cy = t + dot + 0.25
        chh = t + h - cy
        _card(slide, x, cy, cw, chh, pal.card, pal.card_line)
        head, body = _split_lead(step)
        pad = 0.2
        y = cy + pad
        if head:
            hs = _fit_size([head], cw - 2 * pad, 0.8, max_pt=16, min_pt=11, gap=0)
            _, htf = _textbox(slide, x + pad, y, cw - 2 * pad, 0.8)
            _para(htf, True, head, pal.title_font, hs, pal.accent, bold=True)
            y += 0.85
        bh = cy + chh - pad - y
        bs = _fit_size([body], cw - 2 * pad, bh, max_pt=15, min_pt=10, gap=0)
        _, btf = _textbox(slide, x + pad, y, cw - 2 * pad, bh)
        _para(btf, True, body, pal.body_font, bs, pal.text)


def _render_table(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    headers = [_clean(x, 40) for x in sd.table.headers[:5]]
    rows = [[_clean(str(c), 90) for c in r[:len(headers)]] for r in (sd.table.rows or [])[:7]]
    n_rows, n_cols = len(rows) + 1, len(headers)
    row_h = min(0.85, h / n_rows)
    size = 14 if n_rows <= 4 else 12 if n_rows <= 6 else 11
    longest = max([len(c) for r in rows for c in r] + [10])
    if longest > 60:
        size = min(size, 11)
    gshape = slide.shapes.add_table(n_rows, n_cols, Inches(l), Inches(t), Inches(w), Inches(row_h * n_rows))
    tbl = gshape.table
    for c, head in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = _rgb(pal.accent)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.text_frame.word_wrap = True
        cell.text_frame.paragraphs[0].text = ""
        _run(cell.text_frame.paragraphs[0], head, pal.title_font, size + 1, pal.on_accent, bold=True)
    alt = _blend(pal.card, pal.bg, 0.5)
    for r, row in enumerate(rows, start=1):
        for c in range(n_cols):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = _rgb(pal.card if r % 2 else alt)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text_frame.word_wrap = True
            val = row[c] if c < len(row) else ""
            cell.text_frame.paragraphs[0].text = ""
            _run(cell.text_frame.paragraphs[0], val, pal.body_font, size, pal.text, bold=(c == 0))
    for r in range(n_rows):
        tbl.rows[r].height = Inches(row_h)


def _render_quote(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    quote = _clean(sd.quote or sd.subtitle or sd.title, 320).strip('"“”')
    _card(slide, l, t, w, h, pal.card, pal.card_line)
    _, mtf = _textbox(slide, l + 0.4, t + 0.1, 1.5, 1.4)
    _para(mtf, True, "\u201C", "Georgia", 96, pal.accent, bold=True)
    size = _fit_size([quote], w - 2.4, h - 1.2, max_pt=30, min_pt=14, gap=0)
    _, qtf = _textbox(slide, l + 1.2, t + 0.6, w - 2.4, h - 1.2, anchor=MSO_ANCHOR.MIDDLE)
    _para(qtf, True, quote, pal.title_font, size, pal.text, italic=True, align=PP_ALIGN.CENTER)


def _render_statement(slide, sd: Slide, box, pal: Palette):
    l, t, w, h = box
    text = _clean(sd.subtitle or sd.title, 260)
    size = _fit_size([text], w - 1.6, h - 1.0, max_pt=34, min_pt=16, gap=0)
    _, tf = _textbox(slide, l + 0.8, t + 0.5, w - 1.6, h - 1.0, anchor=MSO_ANCHOR.MIDDLE)
    _para(tf, True, text, pal.title_font, size, pal.text, bold=True, align=PP_ALIGN.CENTER)


def _fetch_image(sd: Slide, topic: str, image_source: str) -> Optional[Path]:
    img_path = resolve_image_path(sd.image_url) if sd.image_url else None
    if img_path and img_path.exists():
        return img_path
    try:
        res = generate_slide_image(
            slide_title=sd.title,
            topic=topic,
            category=sd.category or "",
            preferred_provider="stock" if image_source == "internet" else "diffusion",
        )
        if res and res.get("local_path"):
            p = Path(res["local_path"])
            if p.exists():
                sd.image_url = res.get("url", sd.image_url)
                return p
    except Exception as e:
        print(f"[template_deck_builder] image fetch failed: {e}")
    return None


# ============================================================================
# Per-slide population
# ============================================================================
def _populate_title_slide(slide, sd: Slide, outline: Outline, info: ChromeInfo,
                          pal: Palette, sw_in: float, sh_in: float, image_source: str):
    title = sd.title or outline.title
    subtitle = sd.subtitle or outline.subtitle or ""
    if info.title_shape is not None:
        _replace_text(info.title_shape, title, min_pt=20, default_pt=40)
    else:
        tb, tf = _textbox(slide, 0.8, sh_in * 0.3, sw_in * 0.55, sh_in * 0.25, anchor=MSO_ANCHOR.BOTTOM)
        size = _fit_size([title], sw_in * 0.55, sh_in * 0.25, max_pt=44, min_pt=22, gap=0)
        _para(tf, True, title, pal.title_font, size, pal.text, bold=True)
    if subtitle:
        if info.subtitle_shape is not None:
            _replace_text(info.subtitle_shape, subtitle, min_pt=12, default_pt=18)
        elif info.title_shape is None:
            tb, tf = _textbox(slide, 0.8, sh_in * 0.57, sw_in * 0.55, sh_in * 0.15)
            _para(tf, True, subtitle, pal.body_font, 18, pal.muted)
    elif info.subtitle_shape is not None:
        _remove_shape(slide, info.subtitle_shape)
    if info.hero_picture is not None:
        img = _fetch_image(sd, outline.title, image_source)
        if img:
            g = _geom(info.hero_picture)
            _picture_cover(slide, img, *g, replace_el=info.hero_picture._element)


def _populate_content_slide(slide, sd: Slide, idx: int, outline: Outline, info: ChromeInfo,
                            pal: Palette, sw_in: float, sh_in: float, image_source: str):
    # Header title / subtitle
    if info.title_shape is not None:
        _replace_text(info.title_shape, sd.title, max_lines=1 if info.subtitle_shape is not None else 2,
                      min_pt=14, default_pt=28)
        header_bottom = max(info.header_bottom_in, 0.9)
    else:
        size = _fit_size([sd.title], sw_in - 1.2, 0.8, max_pt=30, min_pt=16, gap=0)
        _, tf = _textbox(slide, 0.6, 0.35, sw_in - 1.2, 0.8, anchor=MSO_ANCHOR.MIDDLE)
        _para(tf, True, sd.title, pal.title_font, size, pal.text, bold=True)
        header_bottom = max(info.header_bottom_in, 1.2)

    if info.subtitle_shape is not None:
        if sd.subtitle:
            _replace_text(info.subtitle_shape, sd.subtitle, max_lines=1, min_pt=10, default_pt=14)
        else:
            _remove_shape(slide, info.subtitle_shape)

    if info.page_number is not None:
        _replace_text(info.page_number, str(idx + 1), min_pt=8, default_pt=12)
    if info.footer_label is not None:
        _replace_text(info.footer_label, outline.title, max_lines=1, min_pt=8, default_pt=12)

    # Body box
    margin = max(0.4, min(info.title_left_in, 0.7))
    top = header_bottom + 0.22
    bottom = (info.footer_top_in if info.footer_top_in < sh_in else sh_in) - 0.18
    if info.title_shape is None and info.subtitle_shape is None and sd.subtitle:
        _, stf = _textbox(slide, margin, top - 0.05, sw_in - 2 * margin, 0.45)
        _para(stf, True, _clean(sd.subtitle, 160), pal.body_font, 15, pal.muted)
        top += 0.5
    box = (margin, top, sw_in - 2 * margin, max(1.5, bottom - top))

    kind = _layout_kind(sd)
    if kind == "table":
        _render_table(slide, sd, box, pal)
    elif kind == "metrics":
        _render_metrics(slide, sd, box, pal)
    elif kind == "two_column":
        _render_two_column(slide, sd, box, pal)
    elif kind == "timeline":
        _render_timeline(slide, sd, box, pal)
    elif kind == "quote":
        _render_quote(slide, sd, box, pal)
    elif kind == "bullets":
        img = _fetch_image(sd, outline.title, image_source) if box[2] >= 8 else None
        _render_bullets(slide, sd, box, pal, img)
    else:
        _render_statement(slide, sd, box, pal)
    return kind


def _pick_layout(prs, names: List[str]):
    for want in names:
        for layout in prs.slide_layouts:
            if layout.name.lower() == want:
                return layout
    return None


# ============================================================================
# Entry point
# ============================================================================
def generate_presentation_from_template(
    outline: Outline,
    template_id: str = "",
    image_source: str = "internet"
) -> Tuple[str, Dict[str, Any]]:
    """Generate a PowerPoint presentation that uses the given template's design."""
    tmpl_path = find_template_file(template_id or outline.template_id)
    if not tmpl_path or not tmpl_path.exists():
        raise FileNotFoundError(f"Template with id '{template_id}' could not be located in storage/templates.")

    template_meta = reverse_engineer_template(tmpl_path, template_id=tmpl_path.stem)

    file_id = uuid.uuid4().hex
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DECKS_DIR / f"{file_id}.pptx"
    shutil.copyfile(str(tmpl_path), str(out_path))
    prs = Presentation(str(out_path))

    sw_in = prs.slide_width / EMU_PER_IN
    sh_in = prs.slide_height / EMU_PER_IN
    originals = list(prs.slides)
    n_orig = len(originals)

    title_proto = originals[0] if originals else None
    content_proto = originals[1] if n_orig > 1 else None
    content_layout = None
    if content_proto is None:
        content_layout = _pick_layout(prs, ["title only", "title and content"])
    title_layout = None
    if title_proto is None:
        title_layout = _pick_layout(prs, ["title slide"]) or prs.slide_layouts[0]

    neural_match_report = []
    text_samples: List[str] = []
    fill_samples: List[str] = []
    palette: Optional[Palette] = None

    # Pre-sample palette from the content prototype
    if content_proto is not None:
        probe = _clone_slide(prs, content_proto)
        _prepare_content_chrome(probe, sw_in, sh_in, text_samples, fill_samples)
        palette = _build_palette(template_meta, _detect_background(probe, template_meta, prs.slide_width, prs.slide_height),
                                 text_samples, fill_samples)
        rid = prs.slides._sldIdLst[-1].rId
        prs.part.drop_rel(rid)
        del prs.slides._sldIdLst[-1]
    if palette is None:
        bg = (_detect_background(title_proto, template_meta, prs.slide_width, prs.slide_height)
              if title_proto is not None else template_meta.background_color)
        palette = _build_palette(template_meta, bg, [], [])

    total = len(outline.slides)
    for idx, sd in enumerate(outline.slides):
        is_title = idx == 0 or sd.type == "title"

        if is_title:
            slide = _clone_slide(prs, title_proto) if title_proto is not None else prs.slides.add_slide(title_layout)
            info = _prepare_title_chrome(slide, sw_in, sh_in)
            _populate_title_slide(slide, sd, outline, info, palette, sw_in, sh_in, image_source)
            kind = "title"
        else:
            if content_proto is not None:
                slide = _clone_slide(prs, content_proto)
            elif content_layout is not None:
                slide = prs.slides.add_slide(content_layout)
            else:
                slide = _clone_slide(prs, title_proto)
            info = _prepare_content_chrome(slide, sw_in, sh_in, [], [])
            kind = _populate_content_slide(slide, sd, idx, outline, info, palette, sw_in, sh_in, image_source)

        if sd.notes:
            try:
                slide.notes_slide.notes_text_frame.text = sd.notes
            except Exception:
                pass

        try:
            pred = predict_slide_archetype(
                title=sd.title, subtitle=sd.subtitle, bullets=sd.bullets, stats=sd.stats,
                left=sd.left, right=sd.right, table=sd.table, quote=sd.quote,
                slide_index=idx, total_slides=total, image_url=sd.image_url
            )
            confidence = f"{pred['confidence_percent']}%"
            predicted = pred["best_archetype"]
        except Exception:
            confidence, predicted = "n/a", kind
        matched_proto = template_meta.prototypes.get(kind) or template_meta.prototypes.get(predicted)
        matched_desc = (
            "Title design"
            if is_title
            else (
                f"Content design (Template Slide {matched_proto.slide_index + 1} • {matched_proto.archetype})"
                if matched_proto
                else "Content design"
            )
        )
        neural_match_report.append({
            "slide_index": idx + 1,
            "title": sd.title,
            "predicted_archetype": predicted,
            "rendered_layout": kind,
            "confidence": confidence,
            "matched_template_layout": matched_desc,
        })

    # Remove the template's original slides (they were only design prototypes)
    for _ in range(n_orig):
        rid = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(rid)
        del prs.slides._sldIdLst[0]

    prs.save(str(out_path))

    return file_id, {
        "file_id": file_id,
        "template_id": template_meta.template_id,
        "filename": template_meta.filename,
        "slide_count": len(outline.slides),
        "file_size_bytes": out_path.stat().st_size,
        "dimensions": f"{template_meta.slide_width_in}\" x {template_meta.slide_height_in}\"",
        "neural_match_report": neural_match_report,
        "template_features": template_meta.extracted_features_summary,
    }
