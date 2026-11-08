"""Low-level python-pptx / OOXML helpers (loading templates, deleting and cloning slides)."""
from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn

_MAIN_TYPES = (
    b"application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
    b"application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml",
)
_PRES_TYPE = b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def load_presentation(path: str | Path | None):
    """Open .pptx/.potx/.ppsx. Templates and slideshows get their main content-type
    rewritten to a normal presentation so python-pptx accepts them."""
    if path is None:
        return Presentation()
    data = Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zin:
        ct = zin.read("[Content_Types].xml")
        if not any(t in ct for t in _MAIN_TYPES):
            return Presentation(io.BytesIO(data))
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                blob = zin.read(item.filename)
                if item.filename == "[Content_Types].xml":
                    for t in _MAIN_TYPES:
                        blob = blob.replace(t, _PRES_TYPE)
                zout.writestr(item, blob)
    out.seek(0)
    return Presentation(out)


def delete_slide(prs, slide) -> None:
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst):
        if prs.part.related_part(sld_id.rId) is slide.part:
            prs.part.drop_rel(sld_id.rId)
            sld_id_lst.remove(sld_id)
            return


def remove_shape(shape) -> None:
    el = shape._element
    el.getparent().remove(el)


def _insert_shape_el(sp_tree, el) -> None:
    ext = sp_tree.find(qn("p:extLst"))
    if ext is not None:
        ext.addprevious(el)
    else:
        sp_tree.append(el)


def clone_slide(prs, src, keep=None):
    """Append a copy of `src` (same layout, background, shapes and media).

    `keep(shape) -> bool` filters which top-level shapes are copied.
    Returns (new_slide, mapping src_shape_id -> new shape element).
    """
    new = prs.slides.add_slide(src.slide_layout)
    for shp in list(new.shapes):
        remove_shape(shp)

    copied = []
    bg = src._element.cSld.bg
    if bg is not None:
        new_bg = copy.deepcopy(bg)
        new._element.cSld.insert(0, new_bg)
        copied.append(new_bg)

    id_map = {}
    for shp in src.shapes:
        if keep is not None and not keep(shp):
            continue
        el = copy.deepcopy(shp._element)
        _insert_shape_el(new.shapes._spTree, el)
        copied.append(el)
        id_map[shp.shape_id] = el

    # Re-create relationships (images, media, hyperlinks) that the copied XML references.
    rid_map = {}
    for root in copied:
        for node in root.iter():
            for attr, val in list(node.attrib.items()):
                if not attr.startswith(_R_NS):
                    continue
                if val not in rid_map:
                    rel = src.part.rels.get(val)
                    if rel is None or rel.reltype in (RT.SLIDE_LAYOUT, RT.NOTES_SLIDE):
                        continue
                    if rel.is_external:
                        rid_map[val] = new.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
                    else:
                        rid_map[val] = new.part.relate_to(rel.target_part, rel.reltype)
                node.set(attr, rid_map[val])
    return new, id_map


def set_text_keep_format(text_frame, lines: list[str]) -> None:
    """Replace the text of a text frame, reusing the first paragraph/run formatting
    as the template for every new line (keeps the example deck's look)."""
    txBody = text_frame._txBody
    paras = txBody.findall(qn("a:p"))
    if not paras:
        text_frame.text = "\n".join(lines)
        return
    proto = copy.deepcopy(paras[0])
    for p in paras:
        txBody.remove(p)
    # Strip runs from prototype but keep the first run's properties.
    runs = proto.findall(qn("a:r"))
    rpr = None
    if runs:
        rpr = runs[0].find(qn("a:rPr"))
    for child in list(proto):
        if child.tag in (qn("a:r"), qn("a:br"), qn("a:fld")):
            proto.remove(child)
    for line in lines or [""]:
        p = copy.deepcopy(proto)
        r = p.makeelement(qn("a:r"), {})
        if rpr is not None:
            r.append(copy.deepcopy(rpr))
        t = r.makeelement(qn("a:t"), {})
        t.text = line
        r.append(t)
        er = p.find(qn("a:endParaRPr"))
        if er is not None:
            er.addprevious(r)
        else:
            p.append(r)
        txBody.append(p)
