"""Inspect an uploaded template / example deck: layouts, placeholders, theme, prototypes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

from ..schemas import LayoutInfo, TemplateInfo, ThemeInfo
from ..utils.pptx_xml import load_presentation

A_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
IGNORED_PH = {PP_PLACEHOLDER.DATE, PP_PLACEHOLDER.FOOTER, PP_PLACEHOLDER.SLIDE_NUMBER}
TITLE_PH = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE, PP_PLACEHOLDER.VERTICAL_TITLE}
BODY_PH = {PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.VERTICAL_BODY,
           PP_PLACEHOLDER.VERTICAL_OBJECT}

DEFAULT_COLORS = {
    "dk1": "1F2937", "lt1": "FFFFFF", "dk2": "1E3A8A", "lt2": "F3F4F6",
    "accent1": "4F46E5", "accent2": "0EA5E9", "accent3": "10B981",
    "accent4": "F59E0B", "accent5": "EF4444", "accent6": "8B5CF6",
}


# ------------------------------------------------------------------ theme
def read_theme(prs) -> ThemeInfo:
    master = prs.slide_masters[0]
    colors = dict(DEFAULT_COLORS)
    major, minor = "Calibri Light", "Calibri"
    try:
        theme_part = master.part.part_related_by(RT.THEME)
        root = etree.fromstring(theme_part.blob)
        scheme = root.find(".//a:clrScheme", A_NS)
        if scheme is not None:
            for child in scheme:
                name = etree.QName(child).localname
                srgb = child.find("a:srgbClr", A_NS)
                sysc = child.find("a:sysClr", A_NS)
                if srgb is not None:
                    colors[name] = srgb.get("val")
                elif sysc is not None and sysc.get("lastClr"):
                    colors[name] = sysc.get("lastClr")
        mj = root.find(".//a:fontScheme/a:majorFont/a:latin", A_NS)
        mn = root.find(".//a:fontScheme/a:minorFont/a:latin", A_NS)
        major = (mj.get("typeface") if mj is not None else None) or major
        minor = (mn.get("typeface") if mn is not None else None) or minor
    except (KeyError, etree.XMLSyntaxError):
        pass

    clr_map = master._element.find(qn("p:clrMap"))
    dark = clr_map is not None and clr_map.get("bg1") == "dk1"
    return ThemeInfo(colors=colors, major_font=major, minor_font=minor, dark_background=dark)


# ---------------------------------------------------------------- layouts
def placeholder_kinds(layout) -> list[str]:
    kinds = []
    for ph in layout.placeholders:
        t = ph.placeholder_format.type
        if t in IGNORED_PH:
            continue
        if t in TITLE_PH:
            kinds.append("center_title" if t == PP_PLACEHOLDER.CENTER_TITLE else "title")
        elif t == PP_PLACEHOLDER.SUBTITLE:
            kinds.append("subtitle")
        elif t in BODY_PH:
            kinds.append("body")
        elif t == PP_PLACEHOLDER.PICTURE:
            kinds.append("picture")
        elif t in (PP_PLACEHOLDER.CHART, PP_PLACEHOLDER.TABLE, PP_PLACEHOLDER.MEDIA_CLIP,
                   PP_PLACEHOLDER.ORG_CHART, PP_PLACEHOLDER.BITMAP):
            kinds.append("object")
        else:
            kinds.append(str(t).lower())
    return kinds


def classify_layout(layout) -> str:
    name = (layout.name or "").lower()
    kinds = placeholder_kinds(layout)
    has_title = "title" in kinds or "center_title" in kinds
    n_body = kinds.count("body") + kinds.count("object")
    if "center_title" in kinds or "title slide" in name:
        return "title"
    if "section" in name or ("header" in name and n_body <= 1):
        return "section"
    if "picture" in kinds and has_title:
        return "picture"
    if has_title and n_body >= 2:
        return "two_content"
    if has_title and n_body == 1:
        return "content"
    if has_title and "subtitle" in kinds:
        return "title"
    if has_title:
        return "title_only"
    if not kinds:
        return "blank"
    return "other"


def all_layouts(prs):
    for mi, master in enumerate(prs.slide_masters):
        for li, layout in enumerate(master.slide_layouts):
            yield mi, li, layout


# ------------------------------------------------------------- prototypes
@dataclass
class Prototype:
    slide_index: int
    title_shape_id: int | None = None
    body_shape_id: int | None = None
    body_box: tuple[int, int, int, int] | None = None     # left, top, width, height (EMU)
    title_box: tuple[int, int, int, int] | None = None
    drop_shape_ids: set[int] = field(default_factory=set)


def _text_of(shape) -> str:
    return shape.text_frame.text.strip() if shape.has_text_frame else ""


def _is_title_ph(shape) -> bool:
    return shape.is_placeholder and shape.placeholder_format.type in TITLE_PH


def _max_font_pt(shape) -> float:
    best = 0.0
    if not shape.has_text_frame:
        return best
    for p in shape.text_frame.paragraphs:
        for r in p.runs:
            if r.font.size:
                best = max(best, r.font.size.pt)
    return best


def analyze_prototype(slide, slide_w: int, slide_h: int, index: int) -> Prototype:
    """Find which shapes on an example slide are the title / body so they can be
    refilled, and which content shapes must be dropped when cloning."""
    proto = Prototype(slide_index=index)
    text_shapes = [s for s in slide.shapes if _text_of(s)]
    band_top, band_bottom = slide_h * 0.08, slide_h * 0.88

    def is_chrome(s) -> bool:  # header/footer text such as college name or page numbers
        top, bottom = s.top or 0, (s.top or 0) + (s.height or 0)
        short = len(_text_of(s)) <= 60
        return short and (bottom <= band_top or top >= band_bottom)

    candidates = [s for s in text_shapes if not is_chrome(s)]
    title = next((s for s in candidates if _is_title_ph(s)), None)
    if title is None and candidates:
        upper = [s for s in candidates if (s.top or 0) < slide_h * 0.45]
        pool = upper or candidates
        title = max(pool, key=lambda s: (_max_font_pt(s), -len(_text_of(s)), -(s.top or 0)))
    if title is not None:
        proto.title_shape_id = title.shape_id
        proto.title_box = (title.left, title.top, title.width, title.height)

    bodies = [s for s in candidates if s is not title]
    if bodies:
        body = max(bodies, key=lambda s: (s.width or 0) * (s.height or 0))
        proto.body_shape_id = body.shape_id
        proto.body_box = (body.left, body.top, body.width, body.height)

    slide_area = slide_w * slide_h
    for s in slide.shapes:
        if s.shape_id in (proto.title_shape_id, proto.body_shape_id):
            continue
        if _text_of(s) and not is_chrome(s):
            proto.drop_shape_ids.add(s.shape_id)
        elif (s.shape_type in (MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.TABLE, MSO_SHAPE_TYPE.MEDIA)
              or getattr(s, "has_chart", False) or getattr(s, "has_table", False)):
            proto.drop_shape_ids.add(s.shape_id)
        elif s.shape_type == MSO_SHAPE_TYPE.PICTURE:
            ratio = ((s.width or 0) * (s.height or 0)) / slide_area
            if 0.08 < ratio < 0.6:          # mid-size picture = content, not decoration
                proto.drop_shape_ids.add(s.shape_id)
    return proto


def pick_prototypes(prs) -> dict[str, Prototype]:
    sw, sh = prs.slide_width, prs.slide_height
    protos = [analyze_prototype(s, sw, sh, i) for i, s in enumerate(prs.slides)]
    if not protos:
        return {}
    result = {"title": protos[0]}
    content = [p for p in protos[1:] if p.body_box] or [p for p in protos if p.body_box]
    if content:
        best = max(content, key=lambda p: p.body_box[2] * p.body_box[3])
        result["content"] = best
    else:
        result["content"] = protos[1] if len(protos) > 1 else protos[0]
    section = [p for p in protos[1:-1] if p.title_shape_id and not p.body_box]
    result["section"] = section[0] if section else result["title"]
    return result


def decide_mode(prs) -> str:
    slides = list(prs.slides)
    roles = {classify_layout(l) for _, _, l in all_layouts(prs)}
    has_layouts = "content" in roles
    if not slides:
        return "layouts"
    with_title_ph = sum(1 for s in slides if any(_is_title_ph(sh) and _text_of(sh) for sh in s.shapes))
    if has_layouts and with_title_ph >= len(slides) / 2:
        return "layouts"
    return "prototype"


# ------------------------------------------------------------------ public
def analyze_template(path: Path, template_id: str, filename: str) -> TemplateInfo:
    prs = load_presentation(path)
    layouts = [
        LayoutInfo(index=li, master_index=mi, name=layout.name or f"Layout {li}",
                   role=classify_layout(layout), placeholders=placeholder_kinds(layout))
        for mi, li, layout in all_layouts(prs)
    ]
    return TemplateInfo(
        id=template_id,
        filename=filename,
        slide_width=prs.slide_width,
        slide_height=prs.slide_height,
        mode=decide_mode(prs),
        layouts=layouts,
        theme=read_theme(prs),
        source_slide_count=len(prs.slides),
    )
