"""Template Reverse Engineering Engine for PowerPoint Presentations (.pptx).

Performs deep structural, visual, and typographical reverse engineering:
- Color palette extraction (background, headers, accents, text)
- Typography token extraction (major/minor font families, pt sizes, weights)
- Shape geometry and bounding box coordinate mapping
- Master slide layout hierarchy and placeholder mapping
- Archetype layout identification for Neural Network training
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set

from lxml import etree
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
P_NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}


def emu_to_inches(val: Optional[int]) -> float:
    if val is None:
        return 0.0
    return round(float(val) / 914400.0, 3)


def rgb_to_hex(rgb) -> str:
    if rgb is None:
        return "4F46E5"
    try:
        return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
    except Exception:
        return "4F46E5"


@dataclass
class ExtractedShape:
    shape_id: int
    name: str
    shape_type: str
    left_in: float
    top_in: float
    width_in: float
    height_in: float
    has_text: bool = False
    text_snippet: str = ""
    font_name: str = ""
    font_size_pt: float = 0.0
    font_color_hex: str = ""
    fill_color_hex: str = ""
    is_placeholder: bool = False
    placeholder_type: str = ""
    is_container: bool = False   # True if it's a card/panel background


@dataclass
class ExtractedSlidePrototype:
    slide_index: int
    archetype: str              # title, two_column, metrics, timeline, table, bullets, conclusion, section
    shapes_count: int
    title_box: Optional[Tuple[float, float, float, float]] = None      # left, top, width, height (Inches)
    subtitle_box: Optional[Tuple[float, float, float, float]] = None
    body_box: Optional[Tuple[float, float, float, float]] = None
    title_font: str = ""
    title_font_size: float = 0.0
    title_color: str = ""
    body_font: str = ""
    body_font_size: float = 0.0
    body_color: str = ""
    has_banner: bool = False
    has_cards: bool = False
    container_boxes: List[Tuple[float, float, float, float]] = field(default_factory=list)
    decorative_shape_ids: List[int] = field(default_factory=list)
    content_shape_ids: List[int] = field(default_factory=list)


@dataclass
class ReverseEngineeredTemplate:
    template_id: str
    filename: str
    slide_width_in: float
    slide_height_in: float
    aspect_ratio: str               # "16:9" or "4:3"
    total_slides: int
    primary_color: str              # Hex e.g. "1E3A8A"
    secondary_color: str            # Hex e.g. "0EA5E9"
    background_color: str           # Hex e.g. "FFFFFF" or "0F172A"
    accent_colors: List[str]        # List of hex codes
    title_font: str                 # e.g. "Inter", "Calibri", "Arial"
    body_font: str
    is_dark_theme: bool
    prototypes: Dict[str, ExtractedSlidePrototype] = field(default_factory=dict)
    all_slide_prototypes: List[ExtractedSlidePrototype] = field(default_factory=list)
    master_layouts_count: int = 0
    extracted_features_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "filename": self.filename,
            "slide_width_in": self.slide_width_in,
            "slide_height_in": self.slide_height_in,
            "aspect_ratio": self.aspect_ratio,
            "total_slides": self.total_slides,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color,
            "background_color": self.background_color,
            "accent_colors": self.accent_colors,
            "title_font": self.title_font,
            "body_font": self.body_font,
            "is_dark_theme": self.is_dark_theme,
            "master_layouts_count": self.master_layouts_count,
            "archetypes_available": list(self.prototypes.keys()),
            "extracted_features_summary": self.extracted_features_summary
        }


def _extract_theme_colors(prs) -> Tuple[Dict[str, str], str, str]:
    """Inspect DrawingML color scheme in Master theme part."""
    colors = {
        "dk1": "1E293B", "lt1": "FFFFFF", "dk2": "0F172A", "lt2": "F8FAFC",
        "accent1": "6366F1", "accent2": "0EA5E9", "accent3": "10B981",
        "accent4": "F59E0B", "accent5": "EF4444", "accent6": "8B5CF6"
    }
    major_font = "Calibri"
    minor_font = "Calibri"

    try:
        if prs.slide_masters and len(prs.slide_masters) > 0:
            master = prs.slide_masters[0]
            theme_part = master.part.part_related_by(RT.THEME)
            root = etree.fromstring(theme_part.blob)
            scheme = root.find(".//a:clrScheme", A_NS)
            if scheme is not None:
                for child in scheme:
                    name = etree.QName(child).localname
                    srgb = child.find("a:srgbClr", A_NS)
                    sysc = child.find("a:sysClr", A_NS)
                    if srgb is not None and srgb.get("val"):
                        colors[name] = srgb.get("val").upper()
                    elif sysc is not None and sysc.get("lastClr"):
                        colors[name] = sysc.get("lastClr").upper()

            mj = root.find(".//a:fontScheme/a:majorFont/a:latin", A_NS)
            mn = root.find(".//a:fontScheme/a:minorFont/a:latin", A_NS)
            if mj is not None and mj.get("typeface"):
                major_font = mj.get("typeface")
            if mn is not None and mn.get("typeface"):
                minor_font = mn.get("typeface")
    except Exception:
        pass

    return colors, major_font, minor_font


def _inspect_shape(shape) -> ExtractedShape:
    """Extract geometry and styling metrics for a single shape."""
    left_in = emu_to_inches(shape.left)
    top_in = emu_to_inches(shape.top)
    w_in = emu_to_inches(shape.width)
    h_in = emu_to_inches(shape.height)

    has_text = False
    text_snippet = ""
    font_name = ""
    font_size_pt = 0.0
    font_color_hex = ""
    fill_color_hex = ""

    if shape.has_text_frame:
        has_text = bool(shape.text_frame.text.strip())
        if has_text:
            text_snippet = shape.text_frame.text.strip()[:100]
            for p in shape.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.name and not font_name:
                        font_name = r.font.name
                    if r.font.size and font_size_pt == 0.0:
                        font_size_pt = r.font.size.pt
                    if hasattr(r.font, "color") and r.font.color:
                        try:
                            if r.font.color.rgb:
                                font_color_hex = rgb_to_hex(r.font.color.rgb)
                        except Exception:
                            pass

    # Check fill
    try:
        if shape.fill.type and hasattr(shape.fill, "fore_color") and shape.fill.fore_color:
            if hasattr(shape.fill.fore_color, "rgb") and shape.fill.fore_color.rgb:
                fill_color_hex = rgb_to_hex(shape.fill.fore_color.rgb)
    except Exception:
        pass

    is_ph = shape.is_placeholder
    ph_type = str(shape.placeholder_format.type).lower() if is_ph else ""
    is_container = (w_in > 2.0 and h_in > 1.5 and not is_ph and shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE)

    return ExtractedShape(
        shape_id=shape.shape_id,
        name=shape.name or f"Shape_{shape.shape_id}",
        shape_type=str(shape.shape_type),
        left_in=left_in,
        top_in=top_in,
        width_in=w_in,
        height_in=h_in,
        has_text=has_text,
        text_snippet=text_snippet,
        font_name=font_name,
        font_size_pt=font_size_pt,
        font_color_hex=font_color_hex,
        fill_color_hex=fill_color_hex,
        is_placeholder=is_ph,
        placeholder_type=ph_type,
        is_container=is_container
    )


def classify_slide_archetype(slide, slide_w_in: float, slide_h_in: float, slide_idx: int) -> str:
    """Reverse-engineers slide content patterns to determine semantic archetype."""
    text_shapes = [s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
    raw_text = " ".join([s.text_frame.text.lower() for s in text_shapes])
    
    # 1. Slide 0 is predominantly Title slide
    if slide_idx == 0:
        return "title"
    
    # Check for title slide keywords
    if any(k in raw_text for k in ["welcome", "agenda", "keynote", "presenter", "presentation title"]):
        if len(text_shapes) <= 3:
            return "title"

    # 2. Check for Table
    has_table = any(getattr(s, "has_table", False) for s in slide.shapes)
    if has_table:
        return "table"

    # 3. Check for Metrics / Stats
    has_metrics = bool(re.search(r'\b(\d+[\%kmb\+]|\$\d+|\d+\.\d+x)\b', raw_text, re.IGNORECASE))
    stat_boxes = [s for s in text_shapes if re.search(r'\b\d+[\%kmb\+]?\b', s.text_frame.text)]
    if has_metrics and len(stat_boxes) >= 2:
        return "metrics"

    # 4. Check for Two-Column / Comparison
    mid_x = slide_w_in / 2.0
    left_boxes = [s for s in text_shapes if emu_to_inches(s.left) + emu_to_inches(s.width) < mid_x + 0.5 and emu_to_inches(s.width) > 2.0]
    right_boxes = [s for s in text_shapes if emu_to_inches(s.left) > mid_x - 0.5 and emu_to_inches(s.width) > 2.0]
    if len(left_boxes) >= 1 and len(right_boxes) >= 1:
        return "two_column"

    # 5. Check for Timeline / Process
    if any(k in raw_text for k in ["phase 1", "phase 2", "q1", "q2", "step 1", "milestone", "roadmap"]):
        return "timeline"

    # 6. Check for Conclusion
    if any(k in raw_text for k in ["conclusion", "summary", "takeaways", "next steps", "thank you", "q&a"]):
        return "conclusion"

    # 7. Check for Section Divider
    if len(text_shapes) <= 2 and all(emu_to_inches(s.top) > slide_h_in * 0.25 for s in text_shapes):
        return "section"

    return "bullets"


def reverse_engineer_slide(slide, slide_w_in: float, slide_h_in: float, slide_idx: int) -> ExtractedSlidePrototype:
    """Analyze a single slide and extract coordinate boxes and prototype roles."""
    archetype = classify_slide_archetype(slide, slide_w_in, slide_h_in, slide_idx)
    shapes = [_inspect_shape(s) for s in slide.shapes]
    
    proto = ExtractedSlidePrototype(
        slide_index=slide_idx,
        archetype=archetype,
        shapes_count=len(shapes)
    )

    # 1. Identify Title Box
    title_shape = None
    if slide.shapes.title and slide.shapes.title.has_text_frame:
        title_shape = slide.shapes.title
    else:
        # Largest font or highest top candidate
        candidates = [s for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
        if candidates:
            # Prefer upper 40% of slide
            upper = [s for s in candidates if emu_to_inches(s.top) < slide_h_in * 0.45]
            pool = upper or candidates
            title_shape = max(pool, key=lambda s: emu_to_inches(s.width))

    if title_shape:
        proto.title_box = (
            emu_to_inches(title_shape.left),
            emu_to_inches(title_shape.top),
            emu_to_inches(title_shape.width),
            emu_to_inches(title_shape.height)
        )
        if title_shape.has_text_frame and title_shape.text_frame.text:
            proto.title_font = title_shape.text_frame.paragraphs[0].font.name or ""
            if title_shape.text_frame.paragraphs[0].font.size:
                proto.title_font_size = title_shape.text_frame.paragraphs[0].font.size.pt

    # 2. Identify Subtitle or Body box
    body_candidates = [
        s for s in slide.shapes 
        if s.has_text_frame and s != title_shape and s.text_frame.text.strip()
    ]
    if body_candidates:
        main_body = max(body_candidates, key=lambda s: emu_to_inches(s.width) * emu_to_inches(s.height))
        proto.body_box = (
            emu_to_inches(main_body.left),
            emu_to_inches(main_body.top),
            emu_to_inches(main_body.width),
            emu_to_inches(main_body.height)
        )
        if main_body.has_text_frame and main_body.text_frame.paragraphs:
            proto.body_font = main_body.text_frame.paragraphs[0].font.name or ""
            if main_body.text_frame.paragraphs[0].font.size:
                proto.body_font_size = main_body.text_frame.paragraphs[0].font.size.pt

    # 3. Detect cards / containers and decorative shapes
    for s in shapes:
        if s.is_container:
            proto.has_cards = True
            proto.container_boxes.append((s.left_in, s.top_in, s.width_in, s.height_in))
        if not s.has_text:
            proto.decorative_shape_ids.append(s.shape_id)
        else:
            proto.content_shape_ids.append(s.shape_id)

    # 4. Check top banner
    banner = any(s.top_in <= 0.1 and s.width_in >= slide_w_in * 0.9 for s in shapes)
    proto.has_banner = banner

    return proto


def reverse_engineer_template(pptx_path: Path, template_id: str = "") -> ReverseEngineeredTemplate:
    """Full reverse engineering of an uploaded PowerPoint template."""
    prs = Presentation(str(pptx_path))
    slide_w_in = emu_to_inches(prs.slide_width)
    slide_h_in = emu_to_inches(prs.slide_height)

    # Detect aspect ratio
    ratio_val = slide_w_in / (slide_h_in if slide_h_in > 0 else 1)
    aspect_ratio = "16:9" if ratio_val >= 1.6 else "4:3"

    theme_colors, major_font, minor_font = _extract_theme_colors(prs)

    # Reverse engineer each slide prototype
    prototypes_by_archetype: Dict[str, ExtractedSlidePrototype] = {}
    all_prototypes: List[ExtractedSlidePrototype] = []

    extracted_fonts: Set[str] = set()
    extracted_colors: Set[str] = set()

    for idx, slide in enumerate(prs.slides):
        proto = reverse_engineer_slide(slide, slide_w_in, slide_h_in, idx)
        all_prototypes.append(proto)
        if proto.archetype not in prototypes_by_archetype:
            prototypes_by_archetype[proto.archetype] = proto

        if proto.title_font:
            extracted_fonts.add(proto.title_font)
        if proto.body_font:
            extracted_fonts.add(proto.body_font)

    # Determine primary colors
    primary = theme_colors.get("accent1", "4F46E5")
    secondary = theme_colors.get("accent2", "0EA5E9")
    bg = theme_colors.get("lt1", "FFFFFF")
    
    # Check if slides have dark background
    is_dark = False
    if prs.slides and len(prs.slides) > 0:
        first_slide = prs.slides[0]
        # Inspect background shape if present
        for shape in first_slide.shapes:
            if shape.left == 0 and shape.top == 0 and shape.width == prs.slide_width and shape.height == prs.slide_height:
                if shape.has_text_frame is False and hasattr(shape, "fill") and shape.fill:
                    try:
                        if shape.fill.fore_color and shape.fill.fore_color.rgb:
                            c_hex = rgb_to_hex(shape.fill.fore_color.rgb)
                            bg = c_hex
                            r = int(c_hex[0:2], 16)
                            g = int(c_hex[2:4], 16)
                            b = int(c_hex[4:6], 16)
                            if (r * 0.299 + g * 0.587 + b * 0.114) < 128:
                                is_dark = True
                    except Exception:
                        pass

    accents = [
        theme_colors.get("accent1", "4F46E5"),
        theme_colors.get("accent2", "0EA5E9"),
        theme_colors.get("accent3", "10B981"),
        theme_colors.get("accent4", "F59E0B"),
        theme_colors.get("accent5", "EF4444")
    ]

    title_font = major_font or (list(extracted_fonts)[0] if extracted_fonts else "Calibri")
    body_font = minor_font or (list(extracted_fonts)[-1] if extracted_fonts else "Calibri")

    summary = {
        "dimensions": f"{slide_w_in}\" x {slide_h_in}\" ({aspect_ratio})",
        "archetypes_found": list(prototypes_by_archetype.keys()),
        "fonts": [title_font, body_font],
        "palette": {
            "primary": f"#{primary}",
            "secondary": f"#{secondary}",
            "background": f"#{bg}",
            "accents": [f"#{a}" for a in accents]
        },
        "is_dark_theme": is_dark,
        "clonable_prototypes_count": len(all_prototypes)
    }

    return ReverseEngineeredTemplate(
        template_id=template_id or pptx_path.stem,
        filename=pptx_path.name,
        slide_width_in=slide_w_in,
        slide_height_in=slide_h_in,
        aspect_ratio=aspect_ratio,
        total_slides=len(prs.slides),
        primary_color=primary,
        secondary_color=secondary,
        background_color=bg,
        accent_colors=accents,
        title_font=title_font,
        body_font=body_font,
        is_dark_theme=is_dark,
        prototypes=prototypes_by_archetype,
        all_slide_prototypes=all_prototypes,
        master_layouts_count=len(prs.slide_layouts),
        extracted_features_summary=summary
    )
