"""Diagram engine: AI diagram spec -> laid-out Scene (renderer independent).

Graph-like kinds (architecture, flowchart, hierarchy, mindmap) are laid out with
Graphviz. Timeline, cycle and sequence diagrams use dedicated geometric layouts.
All coordinates are in points with the origin at the top-left.
"""
from __future__ import annotations

import json
import math
import re
import textwrap
from collections import deque
from dataclasses import dataclass, field

import graphviz

from ...schemas import DiagramSpec

MAX_NODES = 14
MAX_LABEL = 48


# ------------------------------------------------------------------ scene
@dataclass
class SNode:
    id: str
    label: str
    shape: str
    x: float
    y: float
    w: float
    h: float
    color: int = 1           # accent index 1..6
    font: float = 14


@dataclass
class SCluster:
    id: str
    label: str
    x: float
    y: float
    w: float
    h: float
    color: int = 1


@dataclass
class SEdge:
    source: str
    target: str
    label: str = ""
    dashed: bool = False


@dataclass
class SLine:
    x1: float
    y1: float
    x2: float
    y2: float
    dashed: bool = False
    arrow: bool = False
    label: str = ""


@dataclass
class Scene:
    width: float
    height: float
    nodes: list[SNode] = field(default_factory=list)
    clusters: list[SCluster] = field(default_factory=list)
    edges: list[SEdge] = field(default_factory=list)
    lines: list[SLine] = field(default_factory=list)

    def node(self, nid: str) -> SNode | None:
        return next((n for n in self.nodes if n.id == nid), None)


# ---------------------------------------------------------------- helpers
def wrap_label(label: str, width: int = 16) -> list[str]:
    lines = textwrap.wrap(label, width=width, break_long_words=True) or [""]
    return lines[:4]


def node_size(label: str, shape: str) -> tuple[float, float]:
    lines = wrap_label(label)
    longest = max(len(l) for l in lines)
    w = max(110.0, min(200.0, 9.0 * longest + 36))
    h = 46.0 + 18.0 * (len(lines) - 1)
    if shape == "decision":
        w, h = w * 1.35, h * 1.6
    elif shape in ("database", "queue"):
        h += 14
    return w, h


def site_points(src: SNode, dst: SNode) -> tuple[int, int, tuple[float, float], tuple[float, float]]:
    """Choose connection sites (0 top, 1 left, 2 bottom, 3 right) for an edge."""
    sx, sy = src.x + src.w / 2, src.y + src.h / 2
    tx, ty = dst.x + dst.w / 2, dst.y + dst.h / 2
    gap_x = abs(tx - sx) - (src.w + dst.w) / 2
    gap_y = abs(ty - sy) - (src.h + dst.h) / 2
    if gap_x > gap_y:
        a, b = (3, 1) if tx > sx else (1, 3)
    else:
        a, b = (2, 0) if ty > sy else (0, 2)
    return a, b, site_xy(src, a), site_xy(dst, b)


def site_xy(n: SNode, idx: int) -> tuple[float, float]:
    return {
        0: (n.x + n.w / 2, n.y),
        1: (n.x, n.y + n.h / 2),
        2: (n.x + n.w / 2, n.y + n.h),
        3: (n.x + n.w, n.y + n.h / 2),
    }[idx]


def sanitize(spec: DiagramSpec) -> DiagramSpec:
    """Make AI output safe to lay out: unique ids, short labels, valid edges."""
    seen: dict[str, str] = {}
    nodes = []
    for n in spec.nodes[:MAX_NODES]:
        nid = re.sub(r"\W+", "_", n.id.strip() or n.label.strip()).strip("_").lower() or f"n{len(nodes)}"
        while nid in seen.values():
            nid += "_"
        seen[n.id] = nid
        nodes.append(n.model_copy(update={"id": nid, "label": n.label.strip()[:MAX_LABEL] or nid}))
    cluster_ids = {c.id for c in spec.clusters}
    for n in nodes:
        if n.cluster and n.cluster not in cluster_ids:
            n.cluster = ""
    edges, pairs = [], set()
    for e in spec.edges:
        s, t = seen.get(e.source), seen.get(e.target)
        if not s or not t or (s, t) in pairs:
            continue
        pairs.add((s, t))
        edges.append(e.model_copy(update={"source": s, "target": t, "label": e.label.strip()[:24]}))
    used_clusters = [c for c in spec.clusters if any(n.cluster == c.id for n in nodes)]
    return DiagramSpec(direction=spec.direction, clusters=used_clusters, nodes=nodes, edges=edges)


def _depths(spec: DiagramSpec) -> dict[str, int]:
    targets = {e.target for e in spec.edges}
    roots = [n.id for n in spec.nodes if n.id not in targets] or [spec.nodes[0].id]
    depth = {r: 0 for r in roots}
    q = deque(roots)
    while q:
        cur = q.popleft()
        for e in spec.edges:
            if e.source == cur and e.target not in depth:
                depth[e.target] = depth[cur] + 1
                q.append(e.target)
    return depth


# ---------------------------------------------------------- graphviz kinds
def _graphviz_scene(spec: DiagramSpec, kind: str) -> Scene:
    engine = "twopi" if kind == "mindmap" else "dot"
    rankdir = "TB" if kind in ("hierarchy", "flowchart") and spec.direction != "LR" else spec.direction
    g = graphviz.Digraph(engine=engine)
    g.attr(rankdir=rankdir, nodesep="0.45", ranksep="0.75", splines="line", newrank="true",
           fontsize="14", overlap="false")
    if kind == "mindmap" and spec.nodes:
        g.attr(root=spec.nodes[0].id, ranksep="1.6")

    sizes = {n.id: node_size(n.label, n.shape) for n in spec.nodes}

    def add_node(target, n):
        w, h = sizes[n.id]
        target.node(n.id, label="", shape="box", fixedsize="true",
                    width=f"{w / 72:.3f}", height=f"{h / 72:.3f}")

    for c in spec.clusters:
        with g.subgraph(name=f"cluster_{c.id}") as sg:
            sg.attr(label=c.label, margin="18", fontsize="15")
            for n in spec.nodes:
                if n.cluster == c.id:
                    add_node(sg, n)
    for n in spec.nodes:
        if not n.cluster:
            add_node(g, n)
    for e in spec.edges:
        g.edge(e.source, e.target)

    data = json.loads(g.pipe(format="json").decode("utf-8"))
    x0, y0, x1, y1 = (float(v) for v in data["bb"].split(","))
    height = y1 - y0
    scene = Scene(width=x1 - x0, height=height)

    cluster_color = {c.id: (i % 6) + 1 for i, c in enumerate(spec.clusters)}
    depth = _depths(spec) if kind in ("hierarchy", "mindmap", "flowchart") else {}
    by_id = {n.id: n for n in spec.nodes}

    for obj in data.get("objects", []):
        name = obj.get("name", "")
        if name.startswith("cluster_") and "bb" in obj:
            cid = name[len("cluster_"):]
            bx0, by0, bx1, by1 = (float(v) for v in obj["bb"].split(","))
            label = next((c.label for c in spec.clusters if c.id == cid), cid)
            scene.clusters.append(SCluster(cid, label, bx0 - x0, height - (by1 - y0),
                                           bx1 - bx0, by1 - by0, cluster_color.get(cid, 1)))
        elif "pos" in obj and name in by_id:
            n = by_id[name]
            cx, cy = (float(v) for v in obj["pos"].split(","))
            w, h = sizes[name]
            if n.cluster:
                color = cluster_color.get(n.cluster, 1)
            elif kind == "flowchart":
                color = {"decision": 4, "start_end": 3}.get(n.shape, 1)
            elif depth:
                color = (depth.get(name, 0) % 6) + 1
            else:
                color = 1
            scene.nodes.append(SNode(name, n.label, n.shape, cx - x0 - w / 2,
                                     height - (cy - y0) - h / 2, w, h, color))
    scene.edges = [SEdge(e.source, e.target, e.label) for e in spec.edges]
    return _pad(scene, 12)


# ------------------------------------------------------------ custom kinds
def _timeline_scene(spec: DiagramSpec) -> Scene:
    n = len(spec.nodes)
    step, box_w, box_h = 190.0, 170.0, 64.0
    width = step * n + 40
    axis_y = 170.0
    scene = Scene(width=width, height=340)
    scene.lines.append(SLine(10, axis_y, width - 10, axis_y, arrow=True))
    for i, node in enumerate(spec.nodes):
        cx = 30 + step * i + step / 2 - 10
        color = (i % 6) + 1
        scene.nodes.append(SNode(f"{node.id}__dot", "", "dot", cx - 9, axis_y - 9, 18, 18, color))
        above = i % 2 == 0
        by = axis_y - 40 - box_h - 20 if above else axis_y + 60
        scene.nodes.append(SNode(node.id, node.label, "box", cx - box_w / 2, by, box_w, box_h, color, 13))
        y_box_edge = by + box_h if above else by
        scene.lines.append(SLine(cx, axis_y + (-9 if above else 9), cx, y_box_edge, dashed=True))
    return _pad(_normalize(scene), 10)


def _cycle_scene(spec: DiagramSpec) -> Scene:
    n = len(spec.nodes)
    radius = max(150.0, 48.0 * n)
    box_w, box_h = 160.0, 60.0
    scene = Scene(width=0, height=0)
    for i, node in enumerate(spec.nodes):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        x = radius * math.cos(ang) - box_w / 2
        y = radius * 0.75 * math.sin(ang) - box_h / 2
        scene.nodes.append(SNode(node.id, node.label, "box", x, y, box_w, box_h, (i % 6) + 1, 13))
    for i in range(n):
        scene.edges.append(SEdge(spec.nodes[i].id, spec.nodes[(i + 1) % n].id))
    return _pad(_normalize(scene), 10)


def _normalize(scene: Scene) -> Scene:
    xs = [n.x for n in scene.nodes] + [n.x + n.w for n in scene.nodes]
    ys = [n.y for n in scene.nodes] + [n.y + n.h for n in scene.nodes]
    for l in scene.lines:
        xs += [l.x1, l.x2]
        ys += [l.y1, l.y2]
    mx, my = min(xs), min(ys)
    for nd in scene.nodes:
        nd.x -= mx
        nd.y -= my
    for l in scene.lines:
        l.x1 -= mx; l.x2 -= mx; l.y1 -= my; l.y2 -= my
    scene.width, scene.height = max(xs) - mx, max(ys) - my
    return scene


def _sequence_scene(spec: DiagramSpec) -> Scene:
    actors = spec.nodes
    col, head_w, head_h, row = 210.0, 160.0, 50.0, 56.0
    msgs = spec.edges[:12]
    height = head_h + 40 + row * (len(msgs) + 1)
    scene = Scene(width=col * len(actors) + 20, height=height)
    xs = {}
    for i, a in enumerate(actors):
        x = 10 + col * i + (col - head_w) / 2
        xs[a.id] = x + head_w / 2
        scene.nodes.append(SNode(a.id, a.label, "user" if a.shape == "user" else "box",
                                 x, 0, head_w, head_h, (i % 6) + 1, 13))
        scene.lines.append(SLine(xs[a.id], head_h, xs[a.id], height, dashed=True))
    for j, m in enumerate(msgs):
        y = head_h + 40 + row * j
        x1, x2 = xs.get(m.source), xs.get(m.target)
        if x1 is None or x2 is None:
            continue
        if x1 == x2:
            x2 = x1 + 60
        scene.lines.append(SLine(x1, y, x2, y, arrow=True, label=m.label or f"step {j + 1}"))
    return scene


def _pad(scene: Scene, pad: float) -> Scene:
    for n in scene.nodes:
        n.x += pad
        n.y += pad
    for c in scene.clusters:
        c.x += pad
        c.y += pad
    for l in scene.lines:
        l.x1 += pad; l.x2 += pad; l.y1 += pad; l.y2 += pad
    scene.width += 2 * pad
    scene.height += 2 * pad
    return scene


# ------------------------------------------------------------------ public
def build_scene(kind: str, spec: DiagramSpec) -> Scene:
    spec = sanitize(spec)
    if not spec.nodes:
        raise ValueError("Diagram has no nodes")
    if kind == "timeline":
        return _timeline_scene(spec)
    if kind == "cycle":
        return _cycle_scene(spec)
    if kind == "sequence":
        return _sequence_scene(spec)
    return _graphviz_scene(spec, kind)


def validate_scene(scene: Scene) -> list[str]:
    """Programmatic readability checks used alongside the vision QA."""
    issues = []
    boxes = [n for n in scene.nodes if n.shape != "dot"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h:
                issues.append(f"Nodes '{a.label}' and '{b.label}' overlap")
    if scene.width / max(scene.height, 1) > 5:
        issues.append("Diagram is very wide; consider fewer nodes per row or direction TB")
    if scene.height / max(scene.width, 1) > 3:
        issues.append("Diagram is very tall; consider direction LR")
    return issues
