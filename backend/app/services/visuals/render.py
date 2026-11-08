"""Render a diagram Scene to native PowerPoint shapes, SVG (preview) or PNG (vision QA)."""
from __future__ import annotations

import io
import math
from html import escape
from pathlib import Path

from lxml import etree
from PIL import Image, ImageDraw, ImageFont
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE, MSO_THEME_COLOR
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from ...schemas import ThemeInfo
from .diagrams import Scene, SNode, site_points, wrap_label

EMU_PER_PT = 12700
ACCENTS = [MSO_THEME_COLOR.ACCENT_1, MSO_THEME_COLOR.ACCENT_2, MSO_THEME_COLOR.ACCENT_3,
           MSO_THEME_COLOR.ACCENT_4, MSO_THEME_COLOR.ACCENT_5, MSO_THEME_COLOR.ACCENT_6]

# Shapes whose connection sites are (top, left, bottom, right) -> safe to glue connectors.
PPTX_SHAPES = {
    "box": (MSO_SHAPE.ROUNDED_RECTANGLE, True),
    "process": (MSO_SHAPE.RECTANGLE, True),
    "database": (MSO_SHAPE.FLOWCHART_MAGNETIC_DISK, True),
    "queue": (MSO_SHAPE.FLOWCHART_DIRECT_ACCESS_STORAGE, True),
    "device": (MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS, True),
    "decision": (MSO_SHAPE.FLOWCHART_DECISION, True),
    "start_end": (MSO_SHAPE.FLOWCHART_TERMINATOR, True),
    "user": (MSO_SHAPE.FLOWCHART_TERMINATOR, True),
    "cloud": (MSO_SHAPE.CLOUD, False),
    "dot": (MSO_SHAPE.OVAL, False),
}


# =================================================================== PPTX
def _accent(i: int):
    return ACCENTS[(max(i, 1) - 1) % 6]


def _arrow(line_shape) -> None:
    ln = line_shape.line._get_or_add_ln()
    tail = ln.find(qn("a:tailEnd"))
    if tail is None:
        tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")


def _style_text(tf, text: str, size: float, color, bold=False, align=PP_ALIGN.CENTER, font=None):
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Pt(4)
    tf.margin_top = tf.margin_bottom = Pt(2)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.text = text
    for p in tf.paragraphs:
        p.alignment = align
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.name = font or "+mn-lt"
            if isinstance(color, RGBColor):
                r.font.color.rgb = color
            else:
                r.font.color.theme_color = color


def draw_scene_pptx(slide, scene: Scene, left: int, top: int, width: int, height: int) -> None:
    sc = min(width / (scene.width * EMU_PER_PT), height / (scene.height * EMU_PER_PT), 1.5)
    ox = left + (width - scene.width * EMU_PER_PT * sc) / 2
    oy = top + (height - scene.height * EMU_PER_PT * sc) / 2

    def X(v): return Emu(int(ox + v * EMU_PER_PT * sc))
    def Y(v): return Emu(int(oy + v * EMU_PER_PT * sc))
    def L(v): return Emu(int(v * EMU_PER_PT * sc))
    def F(pt): return max(9.0, min(18.0, pt * sc))

    shapes = slide.shapes
    group = shapes.add_group_shape()
    gs = group.shapes

    for c in scene.clusters:
        box = gs.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, X(c.x), Y(c.y), L(c.w), L(c.h))
        box.adjustments[0] = 0.06
        box.fill.solid()
        box.fill.fore_color.theme_color = _accent(c.color)
        box.fill.fore_color.brightness = 0.9
        box.line.color.theme_color = _accent(c.color)
        box.line.width = Pt(1.25)
        box.line.dash_style = MSO_LINE.DASH
        box.shadow.inherit = False
        lbl = gs.add_textbox(X(c.x + 8), Y(c.y + 2), L(c.w - 16), L(22))
        _style_text(lbl.text_frame, c.label, F(13), MSO_THEME_COLOR.DARK_1, bold=True, align=PP_ALIGN.LEFT)

    shape_of = {}
    for n in scene.nodes:
        mso, _ = PPTX_SHAPES.get(n.shape, PPTX_SHAPES["box"])
        shp = gs.add_shape(mso, X(n.x), Y(n.y), L(n.w), L(n.h))
        shp.shadow.inherit = False
        shp.fill.solid()
        shp.fill.fore_color.theme_color = _accent(n.color)
        if n.shape == "dot":
            shp.line.fill.background()
        else:
            shp.fill.fore_color.brightness = 0.78
            shp.line.color.theme_color = _accent(n.color)
            shp.line.width = Pt(1.75)
            if n.shape == "user":
                shp.line.width = Pt(2.5)
            _style_text(shp.text_frame, n.label, F(n.font), MSO_THEME_COLOR.DARK_1, bold=True)
        shape_of[n.id] = shp

    for e in scene.edges:
        src, dst = scene.node(e.source), scene.node(e.target)
        if not src or not dst:
            continue
        a, b, p1, p2 = site_points(src, dst)
        con = gs.add_connector(MSO_CONNECTOR.STRAIGHT, X(p1[0]), Y(p1[1]), X(p2[0]), Y(p2[1]))
        if PPTX_SHAPES.get(src.shape, (None, True))[1]:
            con.begin_connect(shape_of[src.id], a)
        if PPTX_SHAPES.get(dst.shape, (None, True))[1]:
            con.end_connect(shape_of[dst.id], b)
        con.line.color.theme_color = MSO_THEME_COLOR.TEXT_1
        con.line.width = Pt(1.5)
        if e.dashed:
            con.line.dash_style = MSO_LINE.DASH
        _arrow(con)
        if e.label:
            _edge_label(gs, e.label, (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, X, Y, L, F)

    for ln in scene.lines:
        con = gs.add_connector(MSO_CONNECTOR.STRAIGHT, X(ln.x1), Y(ln.y1), X(ln.x2), Y(ln.y2))
        con.line.color.theme_color = MSO_THEME_COLOR.TEXT_1
        con.line.width = Pt(1.25 if ln.dashed else 2)
        if ln.dashed:
            con.line.dash_style = MSO_LINE.DASH
        if ln.arrow:
            _arrow(con)
        if ln.label:
            _edge_label(gs, ln.label, (ln.x1 + ln.x2) / 2, min(ln.y1, ln.y2) - 11, X, Y, L, F)


def _edge_label(gs, text, cx, cy, X, Y, L, F):
    w = 8.0 * len(text) + 14
    tb = gs.add_textbox(X(cx - w / 2), Y(cy - 10), L(w), L(20))
    tb.fill.solid()
    tb.fill.fore_color.theme_color = MSO_THEME_COLOR.BACKGROUND_1
    _style_text(tb.text_frame, text, F(11), MSO_THEME_COLOR.TEXT_1)
    tb.text_frame.margin_top = tb.text_frame.margin_bottom = 0


# ==================================================================== SVG
def _tint(hex_color: str, amount: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def _palette(theme: ThemeInfo):
    c = theme.colors
    accents = ["#" + c.get(f"accent{i}", "4F46E5") for i in range(1, 7)]
    dark = "#" + c.get("dk1", "1F2937")
    light = "#" + c.get("lt1", "FFFFFF")
    ink = light if theme.dark_background else dark
    bg = dark if theme.dark_background else light
    return accents, dark, ink, bg


def _svg_shape(n: SNode, fill: str, stroke: str) -> str:
    x, y, w, h = n.x, n.y, n.w, n.h
    sw = 2.5 if n.shape == "user" else 1.75
    common = f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"'
    if n.shape == "dot":
        return f'<circle cx="{x + w / 2}" cy="{y + h / 2}" r="{w / 2}" fill="{stroke}"/>'
    if n.shape == "decision":
        pts = f"{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}"
        return f'<polygon points="{pts}" {common}/>'
    if n.shape in ("database",):
        ry = 8
        return (f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0 1 {x + w},{y + ry} V{y + h - ry} '
                f'A{w / 2},{ry} 0 0 1 {x},{y + h - ry} Z" {common}/>'
                f'<path d="M{x},{y + ry} A{w / 2},{ry} 0 0 0 {x + w},{y + ry}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>')
    rx = {"box": 10, "process": 2, "start_end": h / 2, "user": h / 2, "cloud": h / 2.2,
          "queue": h / 3, "device": 4}.get(n.shape, 10)
    extra = ""
    if n.shape == "device":
        extra = (f'<line x1="{x + 10}" y1="{y}" x2="{x + 10}" y2="{y + h}" stroke="{stroke}" stroke-width="1.5"/>'
                 f'<line x1="{x + w - 10}" y1="{y}" x2="{x + w - 10}" y2="{y + h}" stroke="{stroke}" stroke-width="1.5"/>')
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" {common}/>' + extra


def scene_to_svg(scene: Scene, theme: ThemeInfo) -> str:
    accents, dark, ink, bg = _palette(theme)
    font = escape(theme.minor_font or "Segoe UI")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {scene.width:.0f} {scene.height:.0f}" '
           f'font-family="{font}, Segoe UI, Arial, sans-serif">',
           f'<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{ink}"/></marker></defs>']
    for c in scene.clusters:
        acc = accents[(c.color - 1) % 6]
        out.append(f'<rect x="{c.x}" y="{c.y}" width="{c.w}" height="{c.h}" rx="12" fill="{_tint(acc, 0.9)}" '
                   f'stroke="{acc}" stroke-width="1.25" stroke-dasharray="6 4"/>')
        out.append(f'<text x="{c.x + 10}" y="{c.y + 18}" font-size="13" font-weight="700" fill="{dark}">{escape(c.label)}</text>')
    for e in scene.edges:
        src, dst = scene.node(e.source), scene.node(e.target)
        if not src or not dst:
            continue
        _, _, p1, p2 = site_points(src, dst)
        dash = ' stroke-dasharray="5 4"' if e.dashed else ""
        out.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{ink}" stroke-width="1.5"'
                   f' marker-end="url(#arr)"{dash}/>')
        if e.label:
            out.append(_svg_label(e.label, (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2, ink, bg))
    for ln in scene.lines:
        dash = ' stroke-dasharray="5 4"' if ln.dashed else ""
        marker = ' marker-end="url(#arr)"' if ln.arrow else ""
        out.append(f'<line x1="{ln.x1}" y1="{ln.y1}" x2="{ln.x2}" y2="{ln.y2}" stroke="{ink}" '
                   f'stroke-width="{1.25 if ln.dashed else 2}"{dash}{marker}/>')
        if ln.label:
            out.append(_svg_label(ln.label, (ln.x1 + ln.x2) / 2, min(ln.y1, ln.y2) - 11, ink, bg))
    for n in scene.nodes:
        acc = accents[(n.color - 1) % 6]
        out.append(_svg_shape(n, _tint(acc, 0.78), acc))
        if n.label:
            lines = wrap_label(n.label)
            fs = n.font
            y0 = n.y + n.h / 2 - (len(lines) - 1) * fs * 0.6
            for i, line in enumerate(lines):
                out.append(f'<text x="{n.x + n.w / 2}" y="{y0 + i * fs * 1.2}" font-size="{fs}" font-weight="700" '
                           f'fill="{dark}" text-anchor="middle" dominant-baseline="middle">{escape(line)}</text>')
    out.append("</svg>")
    return "".join(out)


def _svg_label(text, cx, cy, ink, bg):
    w = 7.0 * len(text) + 12
    return (f'<rect x="{cx - w / 2}" y="{cy - 9}" width="{w}" height="18" rx="4" fill="{bg}"/>'
            f'<text x="{cx}" y="{cy}" font-size="11" fill="{ink}" text-anchor="middle" '
            f'dominant-baseline="middle">{escape(text)}</text>')


# ==================================================================== PNG
_FONT_CANDIDATES = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(size: int):
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _dashed(draw, p1, p2, fill, width, dash=10, gap=7):
    (x1, y1), (x2, y2) = p1, p2
    length = math.hypot(x2 - x1, y2 - y1) or 1
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        draw.line([(x1 + dx * pos, y1 + dy * pos), (x1 + dx * end, y1 + dy * end)], fill=fill, width=width)
        pos = end + gap


def _arrowhead(draw, p1, p2, fill, size):
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    a = (p2[0] - size * math.cos(ang - 0.4), p2[1] - size * math.sin(ang - 0.4))
    b = (p2[0] - size * math.cos(ang + 0.4), p2[1] - size * math.sin(ang + 0.4))
    draw.polygon([p2, a, b], fill=fill)


def scene_to_png(scene: Scene, theme: ThemeInfo, scale: float = 2.0) -> bytes:
    accents, dark, ink, bg = _palette(theme)
    W, H = int(scene.width * scale) + 2, int(scene.height * scale) + 2
    img = Image.new("RGB", (W, H), _hex(bg))
    d = ImageDraw.Draw(img)
    s = scale

    for c in scene.clusters:
        acc = accents[(c.color - 1) % 6]
        box = [c.x * s, c.y * s, (c.x + c.w) * s, (c.y + c.h) * s]
        d.rounded_rectangle(box, radius=12 * s, fill=_hex(_tint(acc, 0.9)), outline=_hex(acc), width=int(1.5 * s))
        d.text(((c.x + 10) * s, (c.y + 6) * s), c.label, fill=_hex(dark), font=_font(int(13 * s)))

    def edge(p1, p2, dashed=False, arrow=True, label=""):
        P1, P2 = (p1[0] * s, p1[1] * s), (p2[0] * s, p2[1] * s)
        if dashed:
            _dashed(d, P1, P2, _hex(ink), int(1.5 * s))
        else:
            d.line([P1, P2], fill=_hex(ink), width=int(1.75 * s))
        if arrow:
            _arrowhead(d, P1, P2, _hex(ink), 10 * s)
        if label:
            f = _font(int(11 * s))
            cx, cy = (P1[0] + P2[0]) / 2, (P1[1] + P2[1]) / 2
            tw = d.textlength(label, font=f)
            d.rectangle([cx - tw / 2 - 4, cy - 8 * s, cx + tw / 2 + 4, cy + 8 * s], fill=_hex(bg))
            d.text((cx, cy), label, fill=_hex(ink), font=f, anchor="mm")

    for e in scene.edges:
        src, dst = scene.node(e.source), scene.node(e.target)
        if src and dst:
            _, _, p1, p2 = site_points(src, dst)
            edge(p1, p2, e.dashed, True, e.label)
    for ln in scene.lines:
        edge((ln.x1, ln.y1), (ln.x2, ln.y2), ln.dashed, ln.arrow, ln.label)

    for n in scene.nodes:
        acc = accents[(n.color - 1) % 6]
        box = [n.x * s, n.y * s, (n.x + n.w) * s, (n.y + n.h) * s]
        if n.shape == "dot":
            d.ellipse(box, fill=_hex(acc))
            continue
        fill, outline = _hex(_tint(acc, 0.78)), _hex(acc)
        if n.shape == "decision":
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            d.polygon([(cx, box[1]), (box[2], cy), (cx, box[3]), (box[0], cy)], fill=fill, outline=outline,
                      width=int(1.75 * s))
        else:
            radius = {"process": 2, "device": 4}.get(n.shape, min(n.h / 2, 10) if n.shape == "box" else n.h / 2)
            d.rounded_rectangle(box, radius=radius * s, fill=fill, outline=outline, width=int(1.75 * s))
        f = _font(int(n.font * s))
        lines = wrap_label(n.label)
        cy0 = (n.y + n.h / 2) * s - (len(lines) - 1) * n.font * s * 0.6
        for i, line in enumerate(lines):
            d.text(((n.x + n.w / 2) * s, cy0 + i * n.font * s * 1.2), line, fill=_hex(dark), font=f, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
