"""Architecture Generation, Drawing, Understanding, Planning & Ideation Engine.

Provides end-to-end capabilities to:
1. Understand any user topic, system description, or document and synthesize a multi-tier
   Architecture Blueprint (clusters, typed nodes, directed dataflow edges).
2. Generate Phased Execution Plans and Strategic Innovation Ideas tailored to the input.
3. Draw high-resolution 1920x1080 widescreen Architecture Blueprint PNG diagrams using Pillow
   (with layered swimlanes, database cylinders, cloud nodes, decision diamonds, and arrows).
4. Convert architectural blueprints into interactive presentation slides (`type="diagram"`).
"""
from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PIL import Image, ImageDraw, ImageFont

from ..config import IMAGES_DIR
from ..schemas import (
    DiagramSpec,
    DiagramNode,
    DiagramEdge,
    DiagramCluster,
    Visual,
    Slide,
    StatItem,
    TableSpec,
)
from .llm_gateway import call_llm_json_with_meta


VALID_NODE_SHAPES = {
    "box", "process", "database", "cloud", "user", "queue", "device", "decision", "start_end"
}


def _clean_topic_label(raw_prompt: str) -> str:
    """Extract a clean subject title from an architecture/planning prompt."""
    cleaned = re.sub(r'\([^)]*\)', ' ', raw_prompt or "").strip()
    cleaned = re.sub(
        r'^(?:please\s+)?(?:can\s+you\s+)?(?:generate|create|build|make|draw|design|explain|understand|give\s+me|show\s+me|plan)\s+'
        r'(?:an?\s+|the\s+)?(?:\d+[\s-]slide\s+)?'
        r'(?:system\s+|software\s+|cloud\s+|enterprise\s+|technical\s+|full\s+|complete\s+)?'
        r'(?:architecture|diagram|blueprint|flowchart|presentation|ppt|deck|plan|ideas|strategy|overview)*\s*'
        r'(?:and\s+(?:draw|understand|plan|ideas|give\s+plans)[\w\s]*)*'
        r'(?:for|of|on|about|regarding|to)?\s*',
        '',
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r'\s*(?:and\s+)?(?:draw\s+it|understand\s+it|give\s+plans(?:\s+and\s+ideas)?|with\s+architecture|with\s+plans\s+and\s+ideas).*$',
        '',
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r'[\.\?!;:]+$', '', cleaned).strip()
    words = cleaned.split()
    if len(words) > 9:
        cleaned = " ".join(words[:9])
    return cleaned.title() if cleaned else "Autonomous AI & Cloud System"


def _extract_component_keywords(prompt: str, topic: str) -> List[str]:
    """Extract explicit component or subtopic names mentioned in the user's prompt."""
    cleaned = re.sub(r'\([^)]*\)', ' ', prompt or "")
    cleaned = re.sub(
        r'\b(?:make\s+sure|it\s+can|generate|architecture|draw\s+it|understand\s+it|give\s+plans|and\s+ideas|and\s+all|presentation|ppt|slides?)\b',
        ' ',
        cleaned,
        flags=re.IGNORECASE,
    )
    parts = re.split(r'[,;\n•\*]+|\b(?:including|covering|with|using|via|between|from|to)\b', cleaned, flags=re.IGNORECASE)
    components: List[str] = []
    for p in parts:
        c = p.strip(" .:-_!?")
        if 3 <= len(c) <= 42 and len(c.split()) <= 5:
            if c.lower() not in {"the", "and", "for", "with", "system", "model", "topic", topic.lower()}:
                title_c = c[:1].upper() + c[1:]
                if title_c not in components:
                    components.append(title_c)
    return components[:8]


def synthesize_diagram_spec(
    topic: str,
    prompt: str = "",
    bullets: Optional[List[str]] = None,
    direction: str = "LR"
) -> DiagramSpec:
    """
    Synthesize a rich, domain-accurate 4-tier Architecture DiagramSpec (clusters, nodes, edges)
    tailored to any topic or slide content.
    """
    clean_topic = _clean_topic_label(topic or prompt)
    lower_blob = f"{topic} {prompt} {' '.join(bullets or [])}".lower()
    user_components = _extract_component_keywords(prompt, clean_topic)

    # Also extract lead terms from bullets ("Lead Term: description")
    bullet_terms: List[str] = []
    for b in (bullets or []):
        b_clean = re.sub(r'^[•\-\*\d\.]+\s*', '', b.strip())
        if ":" in b_clean:
            lead = b_clean.split(":", 1)[0].strip()
            if 3 <= len(lead) <= 34:
                bullet_terms.append(lead)
        elif 4 <= len(b_clean) <= 34:
            bullet_terms.append(b_clean)

    all_terms = []
    for t in user_components + bullet_terms:
        if t not in all_terms:
            all_terms.append(t)

    # Choose domain-appropriate architectural tiers & node labels
    if any(k in lower_blob for k in ["ai", "llm", "neural", "model", "ml", "agent", "rag", "gpt", "openai", "nlp", "vision"]):
        clusters = [
            DiagramCluster(id="tier_ingest", label="1. Client & Multimodal Input"),
            DiagramCluster(id="tier_orch", label="2. AI Agent & Prompt Gateway"),
            DiagramCluster(id="tier_core", label="3. Neural Inference & Reasoning"),
            DiagramCluster(id="tier_data", label="4. Vector Knowledge & Output"),
        ]
        n1_lbl = all_terms[0] if len(all_terms) > 0 else "User Prompt & Docs"
        n2_lbl = all_terms[1] if len(all_terms) > 1 else "Semantic Router & Guardrails"
        n3_lbl = all_terms[2] if len(all_terms) > 2 else f"{clean_topic[:20]} Coordinator"
        n4_lbl = all_terms[3] if len(all_terms) > 3 else "LLM / Neural Engine"
        n5_lbl = all_terms[4] if len(all_terms) > 4 else "RAG & Web Grounding"
        n6_lbl = all_terms[5] if len(all_terms) > 5 else "Vector DB & Artifact Store"
        nodes = [
            DiagramNode(id="n1", label=n1_lbl[:28], shape="user", cluster="tier_ingest"),
            DiagramNode(id="n2", label=n2_lbl[:28], shape="process", cluster="tier_orch"),
            DiagramNode(id="n3", label=n3_lbl[:28], shape="decision", cluster="tier_orch"),
            DiagramNode(id="n4", label=n4_lbl[:28], shape="cloud", cluster="tier_core"),
            DiagramNode(id="n5", label=n5_lbl[:28], shape="process", cluster="tier_core"),
            DiagramNode(id="n6", label=n6_lbl[:28], shape="database", cluster="tier_data"),
        ]
        edges = [
            DiagramEdge(source="n1", target="n2", label="Request / Context"),
            DiagramEdge(source="n2", target="n3", label="Intent Parse"),
            DiagramEdge(source="n3", target="n4", label="Neural Dispatch"),
            DiagramEdge(source="n3", target="n5", label="Context Fetch"),
            DiagramEdge(source="n5", target="n6", label="Embeddings / Facts"),
            DiagramEdge(source="n4", target="n6", label="Structured Output"),
        ]
    elif any(k in lower_blob for k in ["battery", "energy", "solar", "grid", "climate", "power", "electric", "renewable"]):
        clusters = [
            DiagramCluster(id="tier_gen", label="1. Generation & Capture"),
            DiagramCluster(id="tier_conv", label="2. Power Conditioning & BMS"),
            DiagramCluster(id="tier_store", label="3. High-Density Storage Core"),
            DiagramCluster(id="tier_dist", label="4. Smart Grid & Load Dispatch"),
        ]
        nodes = [
            DiagramNode(id="n1", label=(all_terms[0] if len(all_terms) > 0 else "Renewable Input Array")[:28], shape="cloud", cluster="tier_gen"),
            DiagramNode(id="n2", label=(all_terms[1] if len(all_terms) > 1 else "Bi-Directional Inverter")[:28], shape="process", cluster="tier_conv"),
            DiagramNode(id="n3", label=(all_terms[2] if len(all_terms) > 2 else "AI Thermal & BMS Control")[:28], shape="decision", cluster="tier_conv"),
            DiagramNode(id="n4", label=(all_terms[3] if len(all_terms) > 3 else f"{clean_topic[:20]} Cells")[:28], shape="database", cluster="tier_store"),
            DiagramNode(id="n5", label=(all_terms[4] if len(all_terms) > 4 else "Peak Shaving Buffer")[:28], shape="queue", cluster="tier_store"),
            DiagramNode(id="n6", label=(all_terms[5] if len(all_terms) > 5 else "Grid & EV Telemetry")[:28], shape="user", cluster="tier_dist"),
        ]
        edges = [
            DiagramEdge(source="n1", target="n2", label="DC Harvest"),
            DiagramEdge(source="n2", target="n3", label="Charge Regulation"),
            DiagramEdge(source="n3", target="n4", label="Balanced Cell Flow"),
            DiagramEdge(source="n4", target="n5", label="High-Density Reserve"),
            DiagramEdge(source="n5", target="n6", label="AC Grid Dispatch"),
        ]
    elif any(k in lower_blob for k in ["medical", "health", "clinical", "patient", "drug", "genom", "crispr", "biotech", "hospital"]):
        clusters = [
            DiagramCluster(id="tier_1", label="1. Patient & Biomarker Intake"),
            DiagramCluster(id="tier_2", label="2. Diagnostic & Assay Pipeline"),
            DiagramCluster(id="tier_3", label="3. Therapeutic Decision Engine"),
            DiagramCluster(id="tier_4", label="4. Clinical Delivery & Outcomes"),
        ]
        nodes = [
            DiagramNode(id="n1", label=(all_terms[0] if len(all_terms) > 0 else "Patient Genomic Profile")[:28], shape="user", cluster="tier_1"),
            DiagramNode(id="n2", label=(all_terms[1] if len(all_terms) > 1 else "Multi-Omics Sequencing")[:28], shape="process", cluster="tier_2"),
            DiagramNode(id="n3", label=(all_terms[2] if len(all_terms) > 2 else "Biomarker Stratification")[:28], shape="decision", cluster="tier_2"),
            DiagramNode(id="n4", label=(all_terms[3] if len(all_terms) > 3 else f"{clean_topic[:20]} Protocol")[:28], shape="cloud", cluster="tier_3"),
            DiagramNode(id="n5", label=(all_terms[4] if len(all_terms) > 4 else "Clinical Safety Telemetry")[:28], shape="database", cluster="tier_4"),
            DiagramNode(id="n6", label=(all_terms[5] if len(all_terms) > 5 else "Targeted Remission Outcome")[:28], shape="process", cluster="tier_4"),
        ]
        edges = [
            DiagramEdge(source="n1", target="n2", label="Sample Assay"),
            DiagramEdge(source="n2", target="n3", label="Variant Filtering"),
            DiagramEdge(source="n3", target="n4", label="Precision Match"),
            DiagramEdge(source="n4", target="n5", label="Dosing & Monitoring"),
            DiagramEdge(source="n5", target="n6", label="Verified Outcome"),
        ]
    else:
        clusters = [
            DiagramCluster(id="tier_entry", label="1. Input & Stakeholder Layer"),
            DiagramCluster(id="tier_gateway", label="2. Orchestration & Control"),
            DiagramCluster(id="tier_engine", label="3. Core Processing Architecture"),
            DiagramCluster(id="tier_store", label="4. Data, Analytics & Delivery"),
        ]
        nodes = [
            DiagramNode(id="n1", label=(all_terms[0] if len(all_terms) > 0 else f"{clean_topic[:18]} Portal")[:28], shape="user", cluster="tier_entry"),
            DiagramNode(id="n2", label=(all_terms[1] if len(all_terms) > 1 else "API & Policy Gateway")[:28], shape="process", cluster="tier_gateway"),
            DiagramNode(id="n3", label=(all_terms[2] if len(all_terms) > 2 else "Routing & Validation")[:28], shape="decision", cluster="tier_gateway"),
            DiagramNode(id="n4", label=(all_terms[3] if len(all_terms) > 3 else f"{clean_topic[:18]} Engine")[:28], shape="cloud", cluster="tier_engine"),
            DiagramNode(id="n5", label=(all_terms[4] if len(all_terms) > 4 else "Event & Workflow Bus")[:28], shape="queue", cluster="tier_engine"),
            DiagramNode(id="n6", label=(all_terms[5] if len(all_terms) > 5 else "Telemetry & Knowledge Store")[:28], shape="database", cluster="tier_store"),
        ]
        edges = [
            DiagramEdge(source="n1", target="n2", label="Ingress Request"),
            DiagramEdge(source="n2", target="n3", label="Auth & Schema Check"),
            DiagramEdge(source="n3", target="n4", label="Core Execution"),
            DiagramEdge(source="n4", target="n5", label="Async Event Stream"),
            DiagramEdge(source="n5", target="n6", label="State & Analytics"),
        ]

    return DiagramSpec(
        direction="TB" if str(direction).upper() == "TB" else "LR",
        clusters=clusters,
        nodes=nodes,
        edges=edges,
    )


def normalize_diagram_dict(raw_diag: Any, fallback_topic: str = "System Architecture") -> DiagramSpec:
    """Validate and normalize a raw LLM or user diagram dictionary into a guaranteed DiagramSpec."""
    if not isinstance(raw_diag, dict):
        return synthesize_diagram_spec(fallback_topic)

    direction = str(raw_diag.get("direction", "LR")).upper()
    if direction not in ("LR", "TB"):
        direction = "LR"

    raw_clusters = raw_diag.get("clusters") or raw_diag.get("layers") or raw_diag.get("tiers") or []
    clusters: List[DiagramCluster] = []
    if isinstance(raw_clusters, list):
        for idx, c in enumerate(raw_clusters[:6]):
            if isinstance(c, dict):
                cid = str(c.get("id") or f"cluster_{idx + 1}")
                clabel = str(c.get("label") or c.get("name") or c.get("title") or f"Layer {idx + 1}")
                clusters.append(DiagramCluster(id=cid, label=clabel[:40]))
            elif isinstance(c, str) and c.strip():
                clusters.append(DiagramCluster(id=f"cluster_{idx + 1}", label=c.strip()[:40]))

    raw_nodes = raw_diag.get("nodes") or raw_diag.get("components") or []
    nodes: List[DiagramNode] = []
    if isinstance(raw_nodes, list):
        for idx, n in enumerate(raw_nodes[:10]):
            if isinstance(n, dict):
                nid = str(n.get("id") or f"n{idx + 1}")
                nlabel = str(n.get("label") or n.get("name") or n.get("title") or f"Component {idx + 1}").strip()
                nshape = str(n.get("shape") or n.get("type") or "box").lower().strip()
                if nshape not in VALID_NODE_SHAPES:
                    if any(k in nshape or k in nlabel.lower() for k in ["db", "data", "store", "sql", "vector", "cache"]):
                        nshape = "database"
                    elif any(k in nshape or k in nlabel.lower() for k in ["cloud", "ai", "llm", "model", "engine"]):
                        nshape = "cloud"
                    elif any(k in nshape or k in nlabel.lower() for k in ["user", "client", "portal", "ui", "app"]):
                        nshape = "user"
                    elif any(k in nshape or k in nlabel.lower() for k in ["queue", "bus", "stream", "kafka", "event"]):
                        nshape = "queue"
                    elif any(k in nshape or k in nlabel.lower() for k in ["router", "decision", "check", "guard", "auth"]):
                        nshape = "decision"
                    else:
                        nshape = "process"
                ncluster = str(n.get("cluster") or (clusters[min(idx, len(clusters) - 1)].id if clusters else ""))
                nodes.append(DiagramNode(id=nid, label=nlabel[:32], shape=nshape, cluster=ncluster))
            elif isinstance(n, str) and n.strip():
                nodes.append(DiagramNode(id=f"n{idx + 1}", label=n.strip()[:32], shape="process"))

    if len(nodes) < 3:
        return synthesize_diagram_spec(fallback_topic)

    if not clusters:
        # Auto-assign 3 clusters across the nodes
        clusters = [
            DiagramCluster(id="c_input", label="1. Ingress & Interface"),
            DiagramCluster(id="c_core", label="2. Core Processing & Logic"),
            DiagramCluster(id="c_data", label="3. Storage & Output Layer"),
        ]
        for i, node in enumerate(nodes):
            if i == 0:
                node.cluster = "c_input"
            elif i >= len(nodes) - 2:
                node.cluster = "c_data"
            else:
                node.cluster = "c_core"

    node_ids = {n.id for n in nodes}
    raw_edges = raw_diag.get("edges") or raw_diag.get("connections") or raw_diag.get("links") or []
    edges: List[DiagramEdge] = []
    if isinstance(raw_edges, list):
        for e in raw_edges[:14]:
            if isinstance(e, dict):
                src = str(e.get("source") or e.get("from") or "")
                tgt = str(e.get("target") or e.get("to") or "")
                lbl = str(e.get("label") or e.get("protocol") or e.get("action") or "")[:28]
                if src in node_ids and tgt in node_ids and src != tgt:
                    edges.append(DiagramEdge(source=src, target=tgt, label=lbl))

    if not edges:
        for i in range(len(nodes) - 1):
            edges.append(DiagramEdge(source=nodes[i].id, target=nodes[i + 1].id, label="Data Flow"))

    return DiagramSpec(direction=direction, clusters=clusters, nodes=nodes, edges=edges)


def _hex_to_rgba(hex_code: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    clean = (hex_code or "6366F1").lstrip("#").strip()
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        clean = "6366F1"
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16), alpha)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_architecture_diagram_png(
    diagram: DiagramSpec,
    title: str = "System Architecture Blueprint",
    subtitle: str = "End-to-End Component Topology & Dataflow",
    bg_hex: str = "#0B0F19",
    accent_primary_hex: str = "#6366F1",
    accent_secondary_hex: str = "#06B6D4",
    text_primary_hex: str = "#F8FAFC",
) -> Dict[str, str]:
    """
    Draw a crisp 1920x1080 widescreen Architecture Blueprint PNG image with layered clusters,
    typed node geometries (database cylinder, cloud, decision diamond, process box, user pill),
    and directional arrow connectors with protocol badges.
    """
    W, H = 1920, 1080
    img = Image.new("RGBA", (W, H), _hex_to_rgba(bg_hex, 255))
    draw = ImageDraw.Draw(img, "RGBA")

    # 1. Subtle architectural blueprint grid
    grid_color = (148, 163, 184, 18)
    for gx in range(0, W, 48):
        draw.line([(gx, 0), (gx, H)], fill=grid_color, width=1)
    for gy in range(0, H, 48):
        draw.line([(0, gy), (W, gy)], fill=grid_color, width=1)

    # Top accent bar
    p_rgba = _hex_to_rgba(accent_primary_hex, 255)
    s_rgba = _hex_to_rgba(accent_secondary_hex, 255)
    txt_rgba = _hex_to_rgba(text_primary_hex, 255)
    muted_rgba = (148, 163, 184, 230)

    draw.rectangle([0, 0, W, 10], fill=p_rgba)

    font_badge = _load_font(20, bold=True)
    font_title = _load_font(42, bold=True)
    font_sub = _load_font(24, bold=False)
    font_cluster = _load_font(22, bold=True)
    font_node = _load_font(23, bold=True)
    font_shape_tag = _load_font(16, bold=True)
    font_edge = _load_font(17, bold=True)

    # Header block
    draw.rounded_rectangle([72, 38, 430, 82], radius=18, fill=(99, 102, 241, 40), outline=p_rgba, width=2)
    draw.text((96, 48), "ARCHITECTURE BLUEPRINT", fill=s_rgba, font=font_badge)
    draw.text((72, 98), (title or "System Architecture")[:62], fill=txt_rgba, font=font_title)
    draw.text((72, 152), (subtitle or "Layered Component Topology & Dataflow")[:95], fill=muted_rgba, font=font_sub)

    nodes = diagram.nodes or []
    clusters = diagram.clusters or []
    edges = diagram.edges or []

    # Group nodes into columns by cluster (or evenly into 3-4 columns)
    cluster_groups: List[Tuple[str, List[DiagramNode]]] = []
    if clusters:
        used_node_ids = set()
        for cl in clusters:
            cnodes = [n for n in nodes if n.cluster == cl.id]
            if cnodes:
                cluster_groups.append((cl.label, cnodes))
                used_node_ids.update(n.id for n in cnodes)
        leftover = [n for n in nodes if n.id not in used_node_ids]
        if leftover:
            if cluster_groups:
                cluster_groups[-1][1].extend(leftover)
            else:
                cluster_groups.append(("Core Architecture", leftover))
    if not cluster_groups:
        col_count = min(4, max(2, math.ceil(len(nodes) / 2)))
        chunk = max(1, math.ceil(len(nodes) / col_count))
        for i in range(0, len(nodes), chunk):
            cluster_groups.append((f"Tier {len(cluster_groups) + 1}", nodes[i:i + chunk]))

    num_cols = len(cluster_groups)
    area_left, area_top, area_right, area_bottom = 72, 215, W - 72, H - 90
    col_gap = 46
    col_w = int((area_right - area_left - col_gap * (num_cols - 1)) / max(1, num_cols))

    node_centers: Dict[str, Tuple[int, int, int, int]] = {}  # id -> (x1, y1, x2, y2)

    # 2. Draw cluster swimlanes and compute node bounding boxes
    for c_idx, (c_label, c_nodes) in enumerate(cluster_groups):
        cx1 = area_left + c_idx * (col_w + col_gap)
        cx2 = cx1 + col_w
        cy1 = area_top
        cy2 = area_bottom

        # Swimlane card
        draw.rounded_rectangle(
            [cx1, cy1, cx2, cy2],
            radius=22,
            fill=(15, 23, 42, 210),
            outline=(99, 102, 241, 95) if c_idx % 2 == 0 else (6, 182, 212, 95),
            width=2,
        )
        # Swimlane header bar
        draw.rounded_rectangle(
            [cx1 + 12, cy1 + 12, cx2 - 12, cy1 + 64],
            radius=14,
            fill=(30, 41, 59, 240),
        )
        draw.text((cx1 + 26, cy1 + 24), c_label[:30], fill=s_rgba if c_idx % 2 else p_rgba, font=font_cluster)

        n_count = len(c_nodes)
        inner_top = cy1 + 92
        inner_bottom = cy2 - 28
        avail_h = inner_bottom - inner_top
        node_h = min(165, int((avail_h - 32 * max(0, n_count - 1)) / max(1, n_count)))
        total_nodes_h = n_count * node_h + max(0, n_count - 1) * 36
        start_y = inner_top + max(0, (avail_h - total_nodes_h) // 2)

        for n_idx, node in enumerate(c_nodes):
            nx1 = cx1 + 26
            nx2 = cx2 - 26
            ny1 = start_y + n_idx * (node_h + 36)
            ny2 = ny1 + node_h
            node_centers[node.id] = (nx1, ny1, nx2, ny2)

    # 3. Draw directed edges with arrowheads and labels
    for edge in edges:
        if edge.source not in node_centers or edge.target not in node_centers:
            continue
        sx1, sy1, sx2, sy2 = node_centers[edge.source]
        tx1, ty1, tx2, ty2 = node_centers[edge.target]

        scx, scy = (sx1 + sx2) // 2, (sy1 + sy2) // 2
        tcx, tcy = (tx1 + tx2) // 2, (ty1 + ty2) // 2

        if abs(tcx - scx) > abs(tcy - scy):
            start_pt = (sx2 if tcx > scx else sx1, scy)
            end_pt = (tx1 if tcx > scx else tx2, tcy)
        else:
            start_pt = (scx, sy2 if tcy > scy else sy1)
            end_pt = (tcx, ty1 if tcy > scy else ty2)

        mid_x = (start_pt[0] + end_pt[0]) // 2
        mid_y = (start_pt[1] + end_pt[1]) // 2

        line_col = (56, 189, 248, 235)
        draw.line([start_pt, (mid_x, start_pt[1]), (mid_x, end_pt[1]), end_pt], fill=line_col, width=4)

        # Arrowhead at end_pt
        dx = end_pt[0] - mid_x if end_pt[0] != mid_x else 0
        dy = end_pt[1] - start_pt[1] if end_pt[0] == mid_x else 0
        angle = math.atan2(dy, dx if dx != 0 else 1)
        ah = 14
        p1 = end_pt
        p2 = (int(end_pt[0] - ah * math.cos(angle - 0.45)), int(end_pt[1] - ah * math.sin(angle - 0.45)))
        p3 = (int(end_pt[0] - ah * math.cos(angle + 0.45)), int(end_pt[1] - ah * math.sin(angle + 0.45)))
        draw.polygon([p1, p2, p3], fill=line_col)

        if edge.label:
            lbl = edge.label[:22]
            pill_w = max(90, len(lbl) * 10 + 20)
            draw.rounded_rectangle(
                [mid_x - pill_w // 2, mid_y - 16, mid_x + pill_w // 2, mid_y + 16],
                radius=10,
                fill=(15, 23, 42, 245),
                outline=(56, 189, 248, 180),
                width=1,
            )
            draw.text((mid_x - pill_w // 2 + 10, mid_y - 10), lbl, fill=(224, 242, 254, 255), font=font_edge)

    # 4. Draw styled nodes on top of connectors
    shape_Colors = {
        "user": ((16, 185, 129, 45), (16, 185, 129, 240), "CLIENT / INPUT"),
        "cloud": ((99, 102, 241, 50), (129, 140, 248, 245), "CLOUD / AI ENGINE"),
        "database": ((6, 182, 212, 45), (34, 211, 238, 245), "DATA STORE / DB"),
        "decision": ((245, 158, 11, 45), (251, 191, 36, 245), "ROUTER / GATEWAY"),
        "queue": ((236, 72, 153, 45), (244, 114, 182, 245), "STREAM / BUS"),
        "process": ((59, 130, 246, 45), (96, 165, 250, 245), "SERVICE / PROCESS"),
    }

    for node in nodes:
        if node.id not in node_centers:
            continue
        nx1, ny1, nx2, ny2 = node_centers[node.id]
        fill_c, border_c, tag_text = shape_Colors.get(node.shape, shape_Colors["process"])

        if node.shape == "database":
            # Cylinder-style representation
            draw.rounded_rectangle([nx1, ny1 + 12, nx2, ny2], radius=16, fill=(17, 24, 39, 250), outline=border_c, width=3)
            draw.ellipse([nx1, ny1, nx2, ny1 + 28], fill=(30, 41, 59, 255), outline=border_c, width=3)
        elif node.shape == "decision":
            draw.rounded_rectangle([nx1, ny1, nx2, ny2], radius=24, fill=(17, 24, 39, 250), outline=border_c, width=3)
        else:
            draw.rounded_rectangle([nx1, ny1, nx2, ny2], radius=18, fill=(17, 24, 39, 250), outline=border_c, width=3)

        # Top inner badge for node archetype
        draw.rounded_rectangle([nx1 + 16, ny1 + 16, nx2 - 16, ny1 + 46], radius=8, fill=fill_c)
        draw.text((nx1 + 26, ny1 + 21), tag_text, fill=border_c, font=font_shape_tag)

        # Node primary label
        label_lines = []
        words = node.label.split()
        cur = ""
        for w in words:
            if len(cur + " " + w) <= 22:
                cur = (cur + " " + w).strip()
            else:
                if cur:
                    label_lines.append(cur)
                cur = w
        if cur:
            label_lines.append(cur)

        ty = ny1 + 58
        for ln in label_lines[:2]:
            draw.text((nx1 + 22, ty), ln, fill=txt_rgba, font=font_node)
            ty += 30

    # Footer bar
    draw.text(
        (72, H - 52),
        f"SlideCraft AI Architecture Engine • {len(clusters)} Architectural Tiers • {len(nodes)} Components • {len(edges)} Dataflow Channels",
        fill=muted_rgba,
        font=font_edge,
    )

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"arch_{uuid.uuid4().hex[:10]}.png"
    out_path = IMAGES_DIR / filename
    img.convert("RGB").save(str(out_path), format="PNG", optimize=True)

    return {
        "filename": filename,
        "url": f"/api/images/{filename}",
        "caption": f"Architecture Blueprint: {title}",
        "provider": "architecture_engine",
    }


def generate_architecture_blueprint(
    prompt: str,
    topic: str = "",
    api_key: Optional[str] = None,
    provider: str = "auto",
    model: str = "",
    base_url: str = "",
    draw_image: bool = True,
) -> Dict[str, Any]:
    """
    Understand the user's request/topic, generate a complete system/domain architecture
    (clusters, nodes, edges), draw the visual blueprint PNG, and synthesize a phased execution
    plan + actionable strategic ideas.
    """
    clean_topic = _clean_topic_label(topic or prompt)

    system_instruction = f"""You are a Principal Systems Architect and Executive Strategy Director.
Analyze the user's request about "{clean_topic}" and design:
1. A structured multi-tier architecture diagram ("diagram") with 3-4 clusters/layers, 5-7 nodes (with shapes from: "user", "process", "cloud", "database", "queue", "decision"), and 5-7 directed edges with concise dataflow/protocol labels.
2. "architecture_understanding": 4 clear architectural insights explaining how the components interact, data flow, scalability, and resilience.
3. "execution_plan": 4 sequential implementation phases ("Phase 1 — ...", "Phase 2 — ...", "Phase 3 — ...", "Phase 4 — ...") with concrete deliverables.
4. "strategic_ideas": 4 high-impact innovation ideas, optimization opportunities, or strategic extensions tailored to "{clean_topic}".

Respond ONLY with a valid JSON object matching this schema:
{{
  "title": "Architecture & Strategic Blueprint: {clean_topic}",
  "subtitle": "Concise 1-sentence architectural thesis",
  "diagram": {{
    "direction": "LR",
    "clusters": [
      {{"id": "c1", "label": "1. Tier Name"}}
    ],
    "nodes": [
      {{"id": "n1", "label": "Component Name", "shape": "user|process|cloud|database|queue|decision", "cluster": "c1"}}
    ],
    "edges": [
      {{"source": "n1", "target": "n2", "label": "Protocol / Flow"}}
    ]
  }},
  "architecture_understanding": [
    "Layer 1 Ingress: ...",
    "Core Processing: ...",
    "State & Persistence: ...",
    "Reliability & Security: ..."
  ],
  "execution_plan": [
    "Phase 1 — Foundation & Contracts: ...",
    "Phase 2 — Core Engine & Pipelines: ...",
    "Phase 3 — Security, Telemetry & Pilot: ...",
    "Phase 4 — Global Rollout & Optimization: ..."
  ],
  "strategic_ideas": [
    "Idea 1 — ...: ...",
    "Idea 2 — ...: ...",
    "Idea 3 — ...: ...",
    "Idea 4 — ...: ..."
  ]
}}"""

    user_msg = f"""User Request: "{prompt}"
Target System / Topic: "{clean_topic}"

Generate the complete JSON architecture blueprint, understanding breakdown, phased execution plan, and strategic ideas now."""

    llm_data, prov_used, mod_used = call_llm_json_with_meta(
        system_instruction=system_instruction,
        user_prompt=user_msg,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        temperature=0.6,
    )

    if isinstance(llm_data, dict) and llm_data.get("diagram"):
        diag_spec = normalize_diagram_dict(llm_data.get("diagram"), fallback_topic=clean_topic)
        arch_title = str(llm_data.get("title") or f"{clean_topic} — System Architecture")
        arch_sub = str(llm_data.get("subtitle") or f"End-to-end component topology, dataflow, and execution strategy for {clean_topic}")
        understanding = [str(x) for x in (llm_data.get("architecture_understanding") or []) if x][:4]
        plan_steps = [str(x) for x in (llm_data.get("execution_plan") or []) if x][:4]
        ideas = [str(x) for x in (llm_data.get("strategic_ideas") or []) if x][:5]
    else:
        diag_spec = synthesize_diagram_spec(clean_topic, prompt=prompt)
        arch_title = f"{clean_topic}: End-to-End Architecture Blueprint"
        arch_sub = f"Multi-tier component topology, dataflow channels, and governance for {clean_topic}"
        understanding = [
            f"Ingress & Interface Layer ({diag_spec.nodes[0].label}): Captures requests, validates inputs, and enforces edge policies for {clean_topic}.",
            f"Orchestration & Routing ({diag_spec.nodes[1].label} → {diag_spec.nodes[2].label}): Decouples request routing, schema validation, and load distribution.",
            f"Core Processing Engine ({diag_spec.nodes[3].label}): Executes primary domain workloads with horizontal auto-scaling and fault isolation.",
            f"Persistence & Telemetry ({diag_spec.nodes[-1].label}): Guarantees durable state storage, real-time analytics, and end-to-end observability.",
        ]
        plan_steps = [
            f"Phase 1 — Architecture Blueprint & Interface Contracts: Finalize component schemas, API boundaries, and security baseline for {clean_topic}.",
            f"Phase 2 — Core Engine & Data Pipeline Implementation: Build {diag_spec.nodes[1].label} and {diag_spec.nodes[3].label} with automated integration tests.",
            f"Phase 3 — Resilience, Telemetry & Pilot Validation: Stress-test throughput, failovers, and observability across {diag_spec.nodes[-1].label}.",
            f"Phase 4 — Production Cutover & Autonomous Scaling: Roll out multi-region deployment with continuous performance optimization.",
        ]
        ideas = [
            f"Autonomous Self-Healing & Circuit Breakers: Embed predictive anomaly detection across {diag_spec.nodes[2].label} to eliminate cascading failures.",
            f"Intelligent Caching & Edge Acceleration: Introduce low-latency caching ahead of {diag_spec.nodes[-1].label} to cut P99 latency by 60%+.",
            f"Modular Plugin & API Ecosystem: Expose standardized webhooks and SDKs on {diag_spec.nodes[1].label} for rapid third-party extensibility.",
            f"Real-Time Cost & Carbon Telemetry: Track compute utilization and unit economics per transaction across {clean_topic}.",
        ]

    img_info = {"url": "", "filename": "", "caption": ""}
    if draw_image:
        try:
            img_info = draw_architecture_diagram_png(
                diagram=diag_spec,
                title=arch_title,
                subtitle=arch_sub,
            )
        except Exception as e:
            print(f"[ArchitectureEngine] PNG render warning: {e}")

    # Build Mermaid diagram snippet for documentation/chat display
    mermaid_lines = [f"flowchart {diag_spec.direction}"]
    for n in diag_spec.nodes:
        safe_lbl = n.label.replace('"', "'")
        mermaid_lines.append(f'    {n.id}["{safe_lbl} ({n.shape})"]')
    for e in diag_spec.edges:
        if e.label:
            mermaid_lines.append(f'    {e.source} -->|"{e.label}"| {e.target}')
        else:
            mermaid_lines.append(f'    {e.source} --> {e.target}')

    return {
        "topic": clean_topic,
        "title": arch_title,
        "subtitle": arch_sub,
        "diagram": diag_spec,
        "architecture_understanding": understanding,
        "execution_plan": plan_steps,
        "strategic_ideas": ideas,
        "image_url": img_info.get("url", ""),
        "image_id": img_info.get("filename", ""),
        "mermaid": "\n".join(mermaid_lines),
        "provider_used": prov_used,
        "model_used": mod_used,
    }


def build_architecture_slides_from_blueprint(blueprint: Dict[str, Any]) -> List[Slide]:
    """Create a 3-slide set (Architecture Diagram, Phased Execution Plan, Strategic Ideas) from a blueprint."""
    diag_spec: DiagramSpec = blueprint["diagram"]
    topic = blueprint["topic"]

    arch_slide = Slide(
        id=uuid.uuid4().hex[:10],
        type="diagram",
        category="SYSTEM ARCHITECTURE BLUEPRINT",
        title=blueprint["title"],
        subtitle=blueprint["subtitle"],
        bullets=blueprint["architecture_understanding"][:4],
        visual=Visual(kind="architecture", diagram=diag_spec),
        image_url=blueprint.get("image_url", ""),
        image_id=blueprint.get("image_id", ""),
        image_caption=f"Architecture Topology: {topic}",
        notes=(
            f"Walk through the {len(diag_spec.clusters)}-tier architecture for {topic}. "
            + " ".join(blueprint["architecture_understanding"][:2])
        ),
    )

    plan_slide = Slide(
        id=uuid.uuid4().hex[:10],
        type="timeline",
        category="ARCHITECTURAL EXECUTION PLAN",
        title=f"Phased Implementation Plan: {topic[:42]}",
        subtitle=f"Structured 4-stage rollout from architectural foundation to production scale",
        bullets=blueprint["execution_plan"][:4],
        notes=f"Present the 4-phase execution plan for {topic}, highlighting concrete deliverables and validation gates.",
    )

    ideas_list = blueprint["strategic_ideas"][:4]
    understanding_list = blueprint["architecture_understanding"][:4]
    ideas_slide = Slide(
        id=uuid.uuid4().hex[:10],
        type="two_column",
        category="STRATEGIC IDEAS & INNOVATIONS",
        title=f"Architectural Insights & High-Impact Ideas: {topic[:36]}",
        subtitle=f"System design principles paired with forward-looking innovation opportunities",
        left=understanding_list,
        right=ideas_list,
        notes=f"Discuss the core architectural insights on the left and strategic innovation ideas on the right for {topic}.",
    )

    return [arch_slide, plan_slide, ideas_slide]


def format_architecture_chat_summary(blueprint: Dict[str, Any]) -> str:
    """Format a rich markdown summary of the architecture understanding, plan, and ideas for the chat feed."""
    diag: DiagramSpec = blueprint["diagram"]
    flow_chain = " ➔ ".join(f"[{n.label}]" for n in diag.nodes[:6])
    understanding_md = "\n".join(f"• {u}" for u in blueprint["architecture_understanding"][:4])
    plan_md = "\n".join(f"• {p}" for p in blueprint["execution_plan"][:4])
    ideas_md = "\n".join(f"• {i}" for i in blueprint["strategic_ideas"][:4])

    return (
        f"🏗️ **Architecture Blueprint & System Topology ({blueprint['topic']})**\n"
        f"• **Data & Control Flow:** {flow_chain}\n\n"
        f"🧠 **Architecture Understanding & How It Works:**\n{understanding_md}\n\n"
        f"🗺️ **Phased Execution Plan:**\n{plan_md}\n\n"
        f"💡 **Strategic Ideas & Innovations:**\n{ideas_md}"
    )

