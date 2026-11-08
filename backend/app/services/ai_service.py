"""AI presentation generation & refinement service using Gemini 2.5 / 1.5 with smart fallback."""
from __future__ import annotations

import json
import re
import uuid
from typing import Optional, List, Dict, Any, Tuple
from google import genai
from google.genai import types

from ..config import (
    OPENAI_API_KEY, OPENAI_MODEL,
    GEMINI_API_KEY, TEXT_MODEL,
    GROK_API_KEY, GROK_API_KEY_NAME, GROK_BASE_URL, GROK_MODEL
)
from ..schemas import (
    ChatRequest, OutlineRequest, Outline, Slide, AISlide, AIOutline,
    StatItem, Visual, FileAttachment, TableSpec
)
from .image_service import generate_slide_image
from .presentation_agent import presentation_agent, extract_semantic_profile
from .llm_gateway import (
    has_configured_llm,
    call_llm_json_with_meta,
    normalize_slide_payload,
    normalize_outline_payload,
)


def get_gemini_client(api_key: Optional[str] = None):
    key = (api_key or "").strip() or GEMINI_API_KEY
    if key:
        return genai.Client(api_key=key)
    return None


def _generate_single_slide_with_llm(
    request: ChatRequest,
    slide_type_hint: str,
    current_deck: Outline,
) -> Tuple[Optional[Slide], str]:
    """Use OpenAI / configured LLM to synthesize a single topic-grounded slide for an existing deck."""
    if not has_configured_llm(request.api_key, request.provider):
        return (None, "")

    existing_titles = ", ".join(f"{i+1}. {s.title}" for i, s in enumerate(current_deck.slides[:12]))
    system_instruction = f"""You are an executive presentation strategist adding a single slide to an existing deck titled "{current_deck.title}".
Existing slides: {existing_titles}
Requested slide layout type: "{slide_type_hint}"
Audience: {request.audience or 'Executive & Technical Stakeholders'}
Tone: {request.tone or 'Authoritative and insightful'}

Return ONLY a valid JSON object for a SINGLE slide with this schema:
{{
  "type": "{slide_type_hint}",
  "category": "UPPERCASE BADGE TAG",
  "title": "Action-oriented Slide Title",
  "subtitle": "Concise 1-sentence framing subtitle",
  "bullets": ["Lead Term: Specific factual insight (14-24 words)", "..."],
  "left": ["Left Column Item 1", "Item 2", "Item 3"],
  "right": ["Right Column Item 1", "Item 2", "Item 3"],
  "stats": [{{"value": "99.4%", "label": "Metric Label", "change": "+18% YoY"}}],
  "table": {{"headers": ["Dimension", "Baseline", "Target", "Impact"], "rows": [["Row 1", "Val 1", "Val 2", "Val 3"]]}},
  "quote": "Executive quote if type is quote",
  "notes": "2-3 sentences of speaker notes"
}}"""

    user_prompt = f"""Deck Title: "{current_deck.title}"
Deck Subtitle: "{current_deck.subtitle}"
User Instruction: "{request.prompt}"

Generate the single slide JSON object now, deeply tailored to "{current_deck.title}" and the user instruction."""

    try:
        data, prov_used, mod_used = call_llm_json_with_meta(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            api_key=request.api_key,
            temperature=0.65,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
        )
        if data and isinstance(data, dict):
            raw_slide = data["slides"][0] if ("slides" in data and isinstance(data["slides"], list) and data["slides"]) else data
            norm = normalize_slide_payload(raw_slide, index=len(current_deck.slides))
            if slide_type_hint and slide_type_hint in ("diagram", "table", "timeline", "quote", "two_column", "metrics", "bullets", "image_text"):
                norm["type"] = slide_type_hint
            ai_slide = AISlide(**norm)
            prov_label = f"{'OpenAI' if prov_used == 'openai' else prov_used.upper()} ({mod_used})" if prov_used else "AI"
            return (Slide(**ai_slide.model_dump(), id=uuid.uuid4().hex[:10]), prov_label)
    except Exception as e:
        print(f"[ai_service] Single slide LLM generation fallback: {e}")

    return (None, "")


def _refine_slide_with_llm(
    request: ChatRequest,
    current_deck: Outline,
    target_idx: int,
) -> Tuple[Outline, str, int]:
    """Refine or polish a specific slide in-place using OpenAI / configured LLM, with smart local fallback."""
    target_slide = current_deck.slides[target_idx]

    # Check if user explicitly asked to convert this slide into an Architecture Diagram & Plan
    p_low = request.prompt.lower()
    if any(k in p_low for k in ["architecture", "diagram", "blueprint", "draw architecture", "flowchart", "topology"]):
        try:
            from .architecture_engine import generate_architecture_blueprint, format_architecture_chat_summary
            bp = generate_architecture_blueprint(
                prompt=f"{target_slide.title}. {' '.join(target_slide.bullets or [])}. {request.prompt}",
                topic=target_slide.title or current_deck.title,
                api_key=request.api_key,
                provider=request.provider,
                model=request.model,
                base_url=request.base_url,
                draw_image=True,
            )
            target_slide.type = "diagram"
            target_slide.category = "SYSTEM ARCHITECTURE BLUEPRINT"
            target_slide.title = bp["title"]
            target_slide.subtitle = bp["subtitle"]
            target_slide.bullets = bp["architecture_understanding"][:4]
            target_slide.visual = Visual(kind="architecture", diagram=bp["diagram"])
            if bp.get("image_url"):
                target_slide.image_url = bp["image_url"]
                target_slide.image_id = bp.get("image_id", "")
                target_slide.image_caption = f"Architecture Blueprint: {bp['topic']}"
            return (
                current_deck,
                f"🏗️ Drawn & structured Slide {target_idx + 1} as an **Architecture Blueprint**.\n\n{format_architecture_chat_summary(bp)}",
                target_idx,
            )
        except Exception as arch_err:
            print(f"[ai_service] Slide architecture conversion fallback: {arch_err}")

    if has_configured_llm(request.api_key, request.provider):
        system_instruction = f"""You are an elite executive presentation editor refining Slide {target_idx + 1} of the presentation "{current_deck.title}".
Apply the user's editing/polishing instruction to the slide while preserving accuracy and visual structure.

Return ONLY a valid JSON object for the updated SINGLE slide:
{{
  "type": "{target_slide.type}",
  "category": "UPPERCASE BADGE TAG",
  "title": "Refined Slide Title",
  "subtitle": "Refined Subtitle",
  "bullets": ["Refined bullet 1", "Refined bullet 2", "Refined bullet 3", "Refined bullet 4"],
  "left": ["Left item 1", "..."],
  "right": ["Right item 1", "..."],
  "stats": [{{"value": "...", "label": "...", "change": "..."}}],
  "table": {{"headers": [...], "rows": [[...]]}},
  "quote": "...",
  "notes": "Updated speaker notes"
}}"""
        current_json = json.dumps(
            {
                "type": target_slide.type,
                "category": target_slide.category,
                "title": target_slide.title,
                "subtitle": target_slide.subtitle,
                "bullets": target_slide.bullets,
                "left": target_slide.left,
                "right": target_slide.right,
                "stats": [s.model_dump() for s in (target_slide.stats or [])],
                "table": target_slide.table.model_dump() if target_slide.table else None,
                "quote": target_slide.quote,
                "notes": target_slide.notes,
            },
            indent=2,
        )
        user_prompt = f"""Current Slide {target_idx + 1} JSON:
{current_json}

User Refinement Instruction:
"{request.prompt}"

Return the updated slide JSON object now."""
        try:
            data, prov_used, mod_used = call_llm_json_with_meta(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                api_key=request.api_key,
                temperature=0.6,
                provider=request.provider,
                model=request.model,
                base_url=request.base_url,
            )
            if data and isinstance(data, dict):
                raw_slide = data["slides"][0] if ("slides" in data and isinstance(data["slides"], list) and data["slides"]) else data
                norm = normalize_slide_payload(raw_slide, index=target_idx)
                ai_slide = AISlide(**norm)
                updated_slide = Slide(
                    **ai_slide.model_dump(),
                    id=target_slide.id,
                    image_id=target_slide.image_id,
                )
                if target_slide.image_url and not updated_slide.image_url:
                    updated_slide.image_url = target_slide.image_url
                if target_slide.image_caption and not updated_slide.image_caption:
                    updated_slide.image_caption = target_slide.image_caption
                current_deck.slides[target_idx] = updated_slide
                prov_label = f" with {'OpenAI' if prov_used == 'openai' else prov_used.upper()} ({mod_used})" if prov_used else ""
                return (
                    current_deck,
                    f"✨ Polished Slide {target_idx + 1} ('{updated_slide.title}'){prov_label}.",
                    target_idx,
                )
        except Exception as e:
            print(f"[ai_service] Slide LLM refinement fallback: {e}")

    # Deterministic local fallback if no LLM key is active
    p_low = request.prompt.lower()
    if "concise" in p_low or "shorten" in p_low or "8 words" in p_low:
        target_slide.bullets = [
            " ".join(b.split()[:10]).rstrip(".,;:") for b in (target_slide.bullets or [])
        ]
    elif "expand" in p_low or "deeper" in p_low or "detail" in p_low:
        target_slide.bullets = [
            f"{b} — backed by verifiable operational benchmarks and execution governance"
            if len(b.split()) < 16 else b
            for b in (target_slide.bullets or ["Core strategic pillar: high-velocity execution and measurable ROI"])
        ]
    elif "metric" in p_low or "kpi" in p_low:
        target_slide.type = "metrics"
        if not target_slide.stats:
            target_slide.stats = [
                StatItem(value="3.8x", label="Execution Velocity", change="+42% vs Baseline"),
                StatItem(value="99.4%", label="Operational Reliability", change="Top Decile"),
                StatItem(value="38%", label="Cost Efficiency Gain", change="Verified ROI"),
            ]
    else:
        if target_slide.title and not target_slide.title.startswith("Executive "):
            target_slide.category = target_slide.category or "EXECUTIVE BRIEFING"
            target_slide.subtitle = target_slide.subtitle or f"Strategic priorities and measurable outcomes for {current_deck.title}"

    return (
        current_deck,
        f"✨ Refined Slide {target_idx + 1} ('{target_slide.title}').",
        target_idx,
    )


def generate_deck_from_chat(request: ChatRequest) -> Tuple[Outline, str, Optional[int]]:
    """Generate or update a presentation outline based on chat prompt, attachments and AI image generation."""
    # 0. Check for interactive modification commands on current deck
    if request.current_deck and len(request.current_deck.slides) > 0:
        p_lower = request.prompt.lower().strip()
        current_deck = request.current_deck

        # A. Theme change intent
        theme_map = {
            "gemini": "google-gemini",
            "google": "google-gemini",
            "aura": "google-gemini",
            "modern": "modern-dark",
            "titanium": "modern-dark",
            "dark": "modern-dark",
            "corporate": "corporate-clean",
            "executive": "corporate-clean",
            "clean": "corporate-clean",
            "white": "corporate-clean",
            "light": "corporate-clean",
            "emerald": "emerald-tech",
            "tech": "emerald-tech",
            "green": "emerald-tech",
            "sunset": "sunset-gradient",
            "horizon": "sunset-gradient",
            "coral": "sunset-gradient",
            "rose": "sunset-gradient",
            "luxury": "luxury-gold",
            "gold": "luxury-gold",
            "royal": "luxury-gold",
            "onyx": "luxury-gold",
        }
        if any(w in p_lower for w in ["theme", "color scheme", "style palette"]):
            for key, t_id in theme_map.items():
                if key in p_lower:
                    current_deck.theme_id = t_id
                    return (
                        current_deck,
                        f"🎨 I have switched the presentation design theme to '{t_id}'.",
                        None
                    )

        # B. Image modification / regeneration intent
        if any(w in p_lower for w in ["image", "photo", "picture", "visual", "illustration", "graphic"]):
            m = re.search(r'slide\s*(\d+)', p_lower)
            target_idx = 0
            if m:
                target_idx = max(0, min(int(m.group(1)) - 1, len(current_deck.slides) - 1))
            elif "first" in p_lower or "title" in p_lower or "hero" in p_lower:
                target_idx = 0
            elif "last" in p_lower:
                target_idx = len(current_deck.slides) - 1

            target_slide = current_deck.slides[target_idx]
            
            # Detect requested style override
            chosen_style = request.image_style or "3d"
            for st in ["photo", "cyberpunk", "vector", "abstract", "3d"]:
                if st in p_lower:
                    chosen_style = st
                    break

            img_prompt = re.sub(
                r'^(generate|change|make|regenerate|create|add|update)\s+(the\s+)?(image|photo|visual)\s+(for|on|in)\s+slide\s*\d*\s*(to|as|about)?\s*',
                '', request.prompt, flags=re.IGNORECASE
            ).strip()

            try:
                new_img = generate_slide_image(
                    slide_title=target_slide.title,
                    topic=current_deck.title,
                    category=target_slide.category or "VISUAL CONCEPT",
                    style=chosen_style,
                    custom_prompt=img_prompt if len(img_prompt) > 3 else "",
                    preferred_provider=request.preferred_image_provider,
                    api_key=request.api_key
                )
                target_slide.image_url = new_img["url"]
                target_slide.image_id = new_img["filename"]
                target_slide.image_caption = new_img["caption"]
                if target_slide.type not in ("title", "image_text"):
                    target_slide.type = "image_text"

                return (
                    current_deck,
                    f"✨ I've regenerated the visual asset for Slide {target_idx + 1} ('{target_slide.title}') with {chosen_style} styling.",
                    target_idx
                )
            except Exception as e:
                print(f"Conversational image generation error: {e}")

        # B2. Architecture Generation, Drawing, Understanding, Planning & Ideas Intent
        wants_arch_action = any(
            k in p_lower
            for k in [
                "architecture", "system design", "blueprint", "flowchart",
                "draw it", "draw a diagram", "draw architecture", "give plans and ideas",
                "plans and ideas", "strategic ideas", "understand it"
            ]
        )
        if wants_arch_action and not re.search(r'\b(slide\s*\d+)\b', p_lower):
            try:
                from .architecture_engine import (
                    generate_architecture_blueprint,
                    build_architecture_slides_from_blueprint,
                    format_architecture_chat_summary,
                )
                bp = generate_architecture_blueprint(
                    prompt=f"{current_deck.title}: {request.prompt}",
                    topic=current_deck.title,
                    api_key=request.api_key,
                    provider=request.provider,
                    model=request.model,
                    base_url=request.base_url,
                    draw_image=True,
                )
                new_slides = build_architecture_slides_from_blueprint(bp)
                # Always append the Architecture Diagram slide; if user also asked for plans/ideas, append those slides too
                wants_plan_and_ideas = any(k in p_lower for k in ["plan", "idea", "all", "roadmap", "understand"])
                if wants_plan_and_ideas:
                    insert_pos = max(1, len(current_deck.slides) - 1)
                    for s_new in new_slides:
                        current_deck.slides.insert(insert_pos, s_new)
                        insert_pos += 1
                    focus_idx = insert_pos - len(new_slides)
                else:
                    current_deck.slides.append(new_slides[0])
                    focus_idx = len(current_deck.slides) - 1

                return (
                    current_deck,
                    f"✨ Generated & drawn the **System Architecture Blueprint**, **Phased Execution Plan**, and **Strategic Ideas** for '{current_deck.title}':\n\n{format_architecture_chat_summary(bp)}",
                    focus_idx,
                )
            except Exception as arch_e:
                print(f"[ai_service] Architecture chat action error: {arch_e}")

        # C. Add new slide intent
        if any(w in p_lower for w in ["add", "insert", "create new"]) and any(w in p_lower for w in ["slide", "section", "part", "diagram", "architecture"]):
            # Determine target layout hint
            slide_type_hint = "bullets"
            if any(w in p_lower for w in ["architecture", "diagram", "blueprint", "flowchart", "topology"]):
                slide_type_hint = "diagram"
            elif any(w in p_lower for w in ["table", "matrix", "grid"]):
                slide_type_hint = "table"
            elif any(w in p_lower for w in ["timeline", "roadmap", "milestone", "process", "phases", "phased"]):
                slide_type_hint = "timeline"
            elif any(w in p_lower for w in ["quote", "vision", "statement", "motto"]):
                slide_type_hint = "quote"
            elif any(w in p_lower for w in ["two column", "2-column", "2 column", "comparison", "compare", "versus", "vs", "pros"]):
                slide_type_hint = "two_column"
            elif any(w in p_lower for w in ["metric", "kpi", "stat", "number", "traction", "benchmark"]):
                slide_type_hint = "metrics"

            # Try OpenAI / LLM synthesis for the new slide first
            llm_slide, prov_label = _generate_single_slide_with_llm(request, slide_type_hint, current_deck)
            if llm_slide:
                current_deck.slides.append(llm_slide)
                return (
                    current_deck,
                    f"➕ Added new '{llm_slide.type}' slide ('{llm_slide.title}') synthesized via {prov_label}.",
                    len(current_deck.slides) - 1
                )

            # C1: Table / Matrix slide (Fallback)
            if slide_type_hint == "table":
                new_slide = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="table",
                    category="COMPARATIVE MATRIX",
                    title="Evaluation Matrix & Structural Benchmarks",
                    subtitle="Direct multi-vector comparison across critical operational dimensions",
                    table=TableSpec(
                        headers=["Dimension", "Baseline State", "Target Benchmark", "Velocity Multiplier"],
                        rows=[
                            ["Speed & Latency", "3-5 business days manual drafting", "Instant multi-modal synthesis (< 2s)", "98% faster turnaround"],
                            ["Visual Fidelity", "Generic clip art & stock templates", "Tailored neural isometric 3D renders", "10x visual engagement"],
                            ["Data Accuracy", "Prone to manual transcription errors", "Contextual schema grounding", "100% verifiable metrics"],
                            ["Iterability", "Tedious slide-by-slide reformatting", "Real-time conversational refinement", "Zero workflow friction"],
                        ]
                    ),
                    notes="Present this structured table to give stakeholders an apples-to-apples comparison of operational metrics."
                )
                current_deck.slides.append(new_slide)
                return (
                    current_deck,
                    "📋 I've added a Structured Evaluation Matrix table slide to your presentation.",
                    len(current_deck.slides) - 1
                )

            # C2: Timeline / Roadmap slide
            if slide_type_hint == "timeline":
                new_slide = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="timeline",
                    category="STRATEGIC ROADMAP",
                    title="Execution Phases & Milestone Roadmap",
                    subtitle="A structured 4-phase rollout pathway from foundation to scale",
                    bullets=[
                        "Phase 1: Discovery, Architecture Blueprint & Tech Stack Alignment",
                        "Phase 2: Core Platform Development & Multi-Agent Engine Integration",
                        "Phase 3: Security Hardening, Automated Testing & Enterprise Pilot",
                        "Phase 4: Full Production Rollout, Global Scaling & Continuous Analytics"
                    ],
                    notes="Walk through these milestones to establish execution confidence and timelines."
                )
                current_deck.slides.append(new_slide)
                return (
                    current_deck,
                    "🗺️ I've added an Executive Roadmap & Timeline slide to outline your key milestones.",
                    len(current_deck.slides) - 1
                )

            # C3: Executive Quote slide
            if slide_type_hint == "quote":
                new_slide = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="quote",
                    category="EXECUTIVE VISION",
                    title="Core Strategic Vision",
                    subtitle="Guiding philosophy powering innovation and long-term execution",
                    quote="The future belongs to those who build architectures capable of continuous, autonomous evolution.",
                    notes="Present this guiding quote to align stakeholders around the long-term vision."
                )
                current_deck.slides.append(new_slide)
                return (
                    current_deck,
                    "🎯 I've added an Executive Quote slide to emphasize your strategic vision.",
                    len(current_deck.slides) - 1
                )

            # C4: Two-column / comparison slide
            if slide_type_hint == "two_column":
                new_slide = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="two_column",
                    category="STRATEGIC COMPARISON",
                    title="Comparative Analysis: Traditional vs Modern Approach",
                    subtitle="Evaluating trade-offs, structural efficiencies, and velocity",
                    left=[
                        "Baseline Constraints:",
                        "• Legacy fragmentation and high manual overhead",
                        "• Bottlenecks slowing cross-team delivery",
                        "• Delayed turnaround on mission-critical deliverables"
                    ],
                    right=[
                        "Our Accelerated Paradigm:",
                        "• Autonomous orchestration and instant iteration",
                        "• Multi-tier neural intelligence with end-to-end reliability",
                        "• Scalable architecture with continuous optimization"
                    ],
                    notes="Contrast current operational friction against our high-velocity paradigm."
                )
                current_deck.slides.append(new_slide)
                return (
                    current_deck,
                    "⚖️ I've added a Comparative Two-Column slide to your presentation.",
                    len(current_deck.slides) - 1
                )

            # C5: Metrics & KPI slide
            if slide_type_hint == "metrics":
                new_slide = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="metrics",
                    category="KEY METRICS & TRACTION",
                    title="Validated Benchmarks & Growth Vectors",
                    subtitle="Measurable performance indicators and impact analysis",
                    stats=[
                        StatItem(value="99.8%", label="Service Reliability", change="+14% YoY"),
                        StatItem(value="4.6x", label="Efficiency Multiplier", change="Top Decile"),
                        StatItem(value="$14.2M", label="Annual Run-Rate", change="+88% Growth"),
                        StatItem(value="< 25ms", label="Real-time Latency", change="Edge Accelerated")
                    ],
                    notes="Review these core benchmarks with the executive audience to validate ROI and performance."
                )
                current_deck.slides.append(new_slide)
                return (
                    current_deck,
                    "📊 I've added a new Executive Metrics & KPI slide to highlight your quantifiable impact.",
                    len(current_deck.slides) - 1
                )

            # C6: General topic slide
            clean_sub = re.sub(r'^(add|insert|create)\s+(a\s+)?(new\s+)?slide\s+(about|on|for)?\s*', '', request.prompt, flags=re.IGNORECASE).strip()
            topic_name = clean_sub.title() if clean_sub else "Strategic Deep Dive"
            if len(topic_name) > 50:
                topic_name = topic_name[:47] + "..."

            new_slide = Slide(
                id=uuid.uuid4().hex[:10],
                type="bullets",
                category="STRATEGIC DEEP DIVE",
                title=topic_name,
                subtitle="Key operational imperatives and actionable considerations",
                bullets=[
                    "Primary vector: establish high-fidelity execution milestones",
                    "Operational acceleration: eliminate friction across dependent workflows",
                    "Long-term value creation: scalable governance and verifiable outcomes"
                ],
                notes=f"Speaker notes for {topic_name}: focus on clear team ownership and milestone delivery."
            )
            current_deck.slides.append(new_slide)
            return (
                current_deck,
                f"➕ I've added a new slide on '{topic_name}' to your presentation.",
                len(current_deck.slides) - 1
            )

        # D. Layout switch intent
        if any(w in p_lower for w in ["change layout", "switch layout", "make slide", "turn slide"]):
            m = re.search(r'slide\s*(\d+)', p_lower)
            if m:
                target_idx = max(0, min(int(m.group(1)) - 1, len(current_deck.slides) - 1))
                target_slide = current_deck.slides[target_idx]
                new_layout = None
                if any(w in p_lower for w in ["metric", "kpi", "stat"]):
                    new_layout = "metrics"
                    if not target_slide.stats:
                        target_slide.stats = [
                            StatItem(value="99.4%", label="Performance Score", change="+18%"),
                            StatItem(value="3.5x", label="Velocity Factor", change="Benchmark"),
                            StatItem(value="$10M+", label="Pipeline Target", change="+45%"),
                        ]
                elif any(w in p_lower for w in ["two column", "2 column", "split", "compare"]):
                    new_layout = "two_column"
                    if not target_slide.left or not target_slide.right:
                        target_slide.left = ["Key Focus Area 1", "Core driver & requirement", "Execution checkpoint"]
                        target_slide.right = ["Strategic Outcome 1", "Efficiency multiplier", "Expected deliverables"]
                elif any(w in p_lower for w in ["image", "visual", "photo"]):
                    new_layout = "image_text"
                elif any(w in p_lower for w in ["quote"]):
                    new_layout = "quote"
                    if not target_slide.quote:
                        target_slide.quote = target_slide.subtitle or "Innovation distinguishes between a leader and a follower."
                elif any(w in p_lower for w in ["timeline", "roadmap", "milestone", "process"]):
                    new_layout = "timeline"
                    if not target_slide.bullets:
                        target_slide.bullets = [
                            "Phase 1: Foundation & Requirements Gathering",
                            "Phase 2: Architectural Build & Core Pipelines",
                            "Phase 3: Validation, Pilot & Enterprise Integration",
                            "Phase 4: Full Deployment & Continuous Evolution"
                        ]
                elif any(w in p_lower for w in ["table", "matrix", "grid"]):
                    new_layout = "table"
                    if not target_slide.table:
                        from ..schemas import TableSpec
                        target_slide.table = TableSpec(
                            headers=["Metric", "Current Baseline", "Target Benchmark", "Velocity Factor"],
                            rows=[
                                ["Operational Speed", "4-5 Days", "Under 2 Hours", "50x Faster"],
                                ["Quality Score", "82%", "99.4%", "Industry Leading"],
                                ["Resource Cost", "High Friction", "Automated Zero-Touch", "65% Savings"]
                            ]
                        )
                elif any(w in p_lower for w in ["bullet", "point"]):
                    new_layout = "bullets"

                if new_layout:
                    target_slide.type = new_layout
                    return (
                        current_deck,
                        f"📐 I've switched Slide {target_idx + 1} ('{target_slide.title}') to the '{new_layout}' layout.",
                        target_idx
                    )

        # E. Rename slide / Change title intent
        m_title = re.search(r'(?:change|update|set|rename)\s+(?:the\s+)?title\s+(?:of|on|for)?\s*slide\s*(\d+)\s+(?:to|as)\s+["\']?([^"\']+)["\']?', request.prompt, re.IGNORECASE)
        if not m_title:
            m_title = re.search(r'rename\s+slide\s*(\d+)\s+(?:to|as)\s+["\']?([^"\']+)["\']?', request.prompt, re.IGNORECASE)
        if m_title:
            target_idx = max(0, min(int(m_title.group(1)) - 1, len(current_deck.slides) - 1))
            new_title = m_title.group(2).strip().rstrip('.')
            target_slide = current_deck.slides[target_idx]
            target_slide.title = new_title
            return (
                current_deck,
                f"📝 I have updated the title of Slide {target_idx + 1} to '{new_title}'.",
                target_idx
            )

        # F. Change subtitle intent
        m_sub = re.search(r'(?:change|update|set)\s+(?:the\s+)?subtitle\s+(?:of|on|for)?\s*slide\s*(\d+)\s+(?:to|as)\s+["\']?([^"\']+)["\']?', request.prompt, re.IGNORECASE)
        if m_sub:
            target_idx = max(0, min(int(m_sub.group(1)) - 1, len(current_deck.slides) - 1))
            new_sub = m_sub.group(2).strip().rstrip('.')
            target_slide = current_deck.slides[target_idx]
            target_slide.subtitle = new_sub
            return (
                current_deck,
                f"✏️ I have updated the subtitle of Slide {target_idx + 1} to '{new_sub}'.",
                target_idx
            )

        # G. Delete slide intent
        m_del = re.search(r'(?:delete|remove)\s+slide\s*(\d+)', p_lower)
        if m_del:
            del_idx = int(m_del.group(1)) - 1
            if 0 <= del_idx < len(current_deck.slides):
                if len(current_deck.slides) > 1:
                    removed = current_deck.slides.pop(del_idx)
                    new_active = min(del_idx, len(current_deck.slides) - 1)
                    return (
                        current_deck,
                        f"🗑️ Removed Slide {del_idx + 1} ('{removed.title}'). The presentation now has {len(current_deck.slides)} slides.",
                        new_active
                    )
                else:
                    return (
                        current_deck,
                        "⚠️ A presentation must have at least one slide. Cannot delete the only remaining slide.",
                        0
                    )

        # H. Duplicate slide intent
        m_dup = re.search(r'(?:duplicate|copy|clone)\s+slide\s*(\d+)', p_lower)
        if m_dup:
            dup_idx = int(m_dup.group(1)) - 1
            if 0 <= dup_idx < len(current_deck.slides):
                orig = current_deck.slides[dup_idx]
                dup_slide = orig.model_copy(deep=True)
                dup_slide.id = uuid.uuid4().hex[:10]
                dup_slide.title = f"{orig.title} (Copy)"
                current_deck.slides.insert(dup_idx + 1, dup_slide)
                return (
                    current_deck,
                    f"📋 Duplicated Slide {dup_idx + 1}. Inserted as Slide {dup_idx + 2} ('{dup_slide.title}').",
                    dup_idx + 1
                )

        # I. Slide-specific Polish / Rewrite / Refinement intent (e.g. Studio AI Polish or "rewrite slide 2...")
        m_slide_ref = re.search(r'slide\s*(\d+)', p_lower)
        if m_slide_ref and not any(w in p_lower for w in ["create a presentation", "new presentation", "generate a presentation", "slide presentation"]):
            ref_idx = max(0, min(int(m_slide_ref.group(1)) - 1, len(current_deck.slides) - 1))
            return _refine_slide_with_llm(request, current_deck, ref_idx)

        # J. Deck-wide conversational refinement when modifying the existing deck rather than starting a brand-new topic
        is_new_deck_intent = any(
            phrase in p_lower
            for phrase in [
                "create a ", "create an ", "make a ", "make an ", "generate a ", "generate an ",
                "build a ", "build an ", "new presentation", "new deck", "presentation about",
                "presentation on", "deck about", "deck on", "pitch deck for", "slides about", "slides on"
            ]
        )
        is_edit_deck_intent = any(
            w in p_lower
            for w in [
                "refine", "polish", "improve", "rewrite", "shorten", "expand", "translate",
                "make the presentation", "make all slides", "update the deck", "more executive",
                "more technical", "more concise", "add more metrics"
            ]
        )
        if is_edit_deck_intent and not is_new_deck_intent and has_configured_llm(request.api_key, request.provider):
            try:
                deck_summary = json.dumps(
                    {
                        "title": current_deck.title,
                        "subtitle": current_deck.subtitle,
                        "slides": [
                            {
                                "type": s.type,
                                "category": s.category,
                                "title": s.title,
                                "subtitle": s.subtitle,
                                "bullets": s.bullets,
                                "left": s.left,
                                "right": s.right,
                                "stats": [st.model_dump() for st in (s.stats or [])],
                                "table": s.table.model_dump() if s.table else None,
                                "quote": s.quote,
                                "notes": s.notes,
                            }
                            for s in current_deck.slides
                        ],
                    },
                    indent=2,
                )
                sys_inst = f"""You are an executive presentation strategist updating an existing {len(current_deck.slides)}-slide presentation.
Apply the user's refinement instruction across the deck while preserving slide count and structure unless asked otherwise.
Return ONLY a valid JSON object with "title", "subtitle", and "slides" matching the input schema."""
                usr_p = f"""Current Deck JSON:\n{deck_summary}\n\nUser Refinement Instruction:\n"{request.prompt}"\n\nReturn the updated JSON presentation object now."""
                data, prov_used, mod_used = call_llm_json_with_meta(
                    system_instruction=sys_inst,
                    user_prompt=usr_p,
                    api_key=request.api_key,
                    temperature=0.6,
                    provider=request.provider,
                    model=request.model,
                    base_url=request.base_url,
                )
                if data and isinstance(data, dict):
                    normalized = normalize_outline_payload(data, fallback_title=current_deck.title)
                    if normalized.get("slides"):
                        ai_outline = AIOutline(**normalized)
                        new_slides: List[Slide] = []
                        for idx, s in enumerate(ai_outline.slides):
                            prev = current_deck.slides[idx] if idx < len(current_deck.slides) else None
                            sl = Slide(
                                **s.model_dump(),
                                id=prev.id if prev else uuid.uuid4().hex[:10],
                                image_id=prev.image_id if prev else "",
                            )
                            if prev and prev.image_url and not sl.image_url:
                                sl.image_url = prev.image_url
                            if prev and prev.image_caption and not sl.image_caption:
                                sl.image_caption = prev.image_caption
                            new_slides.append(sl)
                        updated_outline = Outline(
                            title=ai_outline.title or current_deck.title,
                            subtitle=ai_outline.subtitle or current_deck.subtitle,
                            theme_id=current_deck.theme_id,
                            template_id=current_deck.template_id,
                            slides=new_slides,
                        )
                        prov_label = f" via {'OpenAI' if prov_used == 'openai' else prov_used.upper()} ({mod_used})" if prov_used else ""
                        return (
                            updated_outline,
                            f"✨ Updated your {len(new_slides)}-slide presentation ('{updated_outline.title}'){prov_label}.",
                            0,
                        )
            except Exception as e:
                print(f"[ai_service] Deck-wide LLM refinement fallback: {e}")

    client = get_gemini_client(request.api_key)
    
    # 1. Gather context from attachments
    doc_texts = []
    image_attachments = []
    template_info = None

    for att in request.attachments:
        if att.file_type == "document" and att.extracted_text:
            doc_texts.append(f"--- Document: {att.filename} ---\n{att.extracted_text[:8000]}")
        elif att.file_type == "image":
            image_attachments.append(att)
        elif att.file_type == "template" and att.template_id:
            template_info = att.template_info

    combined_sources = "\n\n".join(doc_texts)

    # 2. Invoke AIPresentationAgent to synthesize deck, ground technical details & generate required visuals
    outline, response_msg, modified_slide_idx = presentation_agent.generate_presentation(request)
    return (outline, response_msg, modified_slide_idx)





def _call_grok_chat(
    api_key: Optional[str],
    request: ChatRequest,
    combined_sources: str,
    image_attachments: List[FileAttachment],
    template_info: Optional[Dict[str, Any]]
) -> Optional[Outline]:
    """Execute presentation generation using Grok (xAI) or OpenAI-compatible endpoint."""
    import urllib.request
    import ssl

    key = (api_key or "").strip() or GROK_API_KEY
    if not key:
        return None

    url = f"{GROK_BASE_URL.rstrip('/')}/chat/completions"

    images_desc = ""
    if image_attachments:
        images_desc = "\nAvailable uploaded images to incorporate:\n"
        for idx, img in enumerate(image_attachments):
            images_desc += f"- Image {idx+1}: Filename: '{img.filename}', URL: '{img.url}', Summary: '{img.summary}'\n"

    system_instruction = f"""You are an elite executive presentation designer and keynote strategist.
Create a publication-ready presentation deck.

Target slide count: {request.slide_count} slides
Audience: {request.audience}
Tone: {request.tone}
Theme Style: {request.theme_id}

Guidelines:
1. First slide MUST be 'title' with a compelling headline, subtitle, and category badge.
2. Middle slides should feature diverse layout types: 'two_column', 'metrics', 'bullets', 'timeline', 'table', 'quote', 'section'.
3. Every slide must include realistic presenter notes ('notes').
{images_desc}

You MUST output ONLY a valid JSON object matching this schema:
{{
  "title": "Presentation Title",
  "subtitle": "Subtitle",
  "slides": [
    {{
      "type": "title",
      "category": "EXECUTIVE OVERVIEW",
      "title": "Slide Title",
      "subtitle": "Slide Subtitle",
      "bullets": ["Point 1", "Point 2"],
      "left": [],
      "right": [],
      "stats": [{{"value": "99.8%", "label": "Reliability", "change": "+12%"}}],
      "quote": "",
      "notes": "Speaker notes here"
    }}
  ]
}}"""

    user_prompt = f"""User Prompt: "{request.prompt}"

Attached Context:
{combined_sources if combined_sources else "(No documents attached, generate based on prompt)"}

Generate the complete JSON presentation outline now."""

    payload = json.dumps({
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": f"SlideCraft-AIPptMaker/1.0 ({GROK_API_KEY_NAME})"
    }

    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, data=payload, headers=headers)

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            raw_text = resp_body["choices"][0]["message"]["content"]
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(raw_text)
            ai_outline = AIOutline(**data)

            slides = []
            for s in ai_outline.slides:
                slide_dict = s.model_dump()
                slide_dict["id"] = uuid.uuid4().hex[:10]
                slides.append(Slide(**slide_dict))

            return Outline(
                title=ai_outline.title,
                subtitle=ai_outline.subtitle,
                theme_id=request.theme_id,
                template_id=request.template_id,
                slides=slides
            )
    except Exception as e:
        print(f"Grok API call encountered error: {e}")
        return None




def _call_gemini_chat(
    client: genai.Client,
    request: ChatRequest,
    combined_sources: str,
    image_attachments: List[FileAttachment],
    template_info: Optional[Dict[str, Any]]
) -> Outline:
    """Execute structured Gemini prompt."""
    
    images_desc = ""
    if image_attachments:
        images_desc = "\nAvailable uploaded images to incorporate:\n"
        for idx, img in enumerate(image_attachments):
            images_desc += f"- Image {idx+1}: Filename: '{img.filename}', URL: '{img.url}', Summary: '{img.summary}'\n"
        images_desc += "Assign these image_url values to appropriate slides (e.g. image_text or content slides) with descriptive captions."

    history_context = ""
    if request.history:
        history_context = "Conversation history:\n"
        for h in request.history[-4:]:
            history_context += f"[{h.role}]: {h.content}\n"

    system_instruction = f"""
You are an elite executive presentation designer and keynote strategist.
Your task is to create a stunning, publication-ready presentation deck.

Target slide count: {request.slide_count} slides
Audience: {request.audience}
Tone: {request.tone}
Theme Style: {request.theme_id}

Guidelines:
1. First slide MUST be 'title' with a compelling headline, subtitle, and uppercase category badge (e.g. "EXECUTIVE KEYNOTE").
2. Middle slides MUST have diverse, engaging layout types:
   - 'two_column': for comparative analysis, pros/cons, before/after, or split topics. Provide 'left' and 'right' bullet arrays.
   - 'metrics': for statistics, impact, or financial metrics. Provide 3-4 'stats' items with 'value' (e.g., '+145%', '10x', '$4.2B') and 'label'.
   - 'bullets': for focused pillars with crisp, high-impact bullet points.
   - 'image_text': for visual storytelling with image_url and caption.
   - 'conclusion': for strategic roadmap, executive takeaways, and call to action.
3. Every single slide MUST include detailed, realistic presenter notes ('notes') explaining the speaking script and talking points.
4. If source documents are provided below, rigorously synthesize and extract accurate facts, metrics, and arguments from them.
{images_desc}
"""

    prompt = f"""
{history_context}

User Prompt:
"{request.prompt}"

Attached Document Content:
{combined_sources if combined_sources else "(No documents attached, generate based on prompt)"}

Create the complete presentation outline now.
"""

    response = client.models.generate_content(
        model=TEXT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=AIOutline,
            temperature=0.7,
        )
    )

    data = json.loads(response.text)
    ai_outline = AIOutline(**data)

    slides = []
    for s in ai_outline.slides:
        slide_dict = s.model_dump()
        slide_dict["id"] = uuid.uuid4().hex[:10]
        slides.append(Slide(**slide_dict))

    return Outline(
        title=ai_outline.title,
        subtitle=ai_outline.subtitle,
        theme_id=request.theme_id,
        template_id=request.template_id,
        slides=slides
    )


def _smart_generate_fallback(
    prompt: str,
    slide_count: int = 8,
    theme_id: str = "google-gemini",
    template_id: str = "",
    source_text: str = "",
    image_attachments: Optional[List[FileAttachment]] = None,
    current_deck: Optional[Outline] = None
) -> Outline:
    """Intelligent rule-based generator that synthesizes realistic, rich slide decks."""
    
    # If modifying an existing deck based on a tweak instruction
    if current_deck and len(current_deck.slides) > 0:
        p_lower = prompt.lower()
        if "add" in p_lower and "slide" in p_lower:
            new_slide = Slide(
                id=uuid.uuid4().hex[:10],
                type="bullets",
                category="EXPANDED FOCUS",
                title=f"Strategic Insights on {prompt[:40]}",
                subtitle="Deep dive into additional opportunities and considerations",
                bullets=[
                    "Core requirement identified from user analysis",
                    "Immediate operational and technical advantages",
                    "Long-term value creation and scalability trajectory"
                ],
                notes="This slide was added per user request to highlight additional tactical and strategic perspectives."
            )
            updated_slides = list(current_deck.slides) + [new_slide]
            return Outline(
                title=current_deck.title,
                subtitle=current_deck.subtitle,
                theme_id=theme_id or current_deck.theme_id,
                template_id=template_id or current_deck.template_id,
                slides=updated_slides
            )

    profile = extract_semantic_profile(prompt, source_text=source_text)
    outline = presentation_agent.synthesizer.synthesize_deck(
        profile=profile,
        slide_count=slide_count,
        theme_id=theme_id or "google-gemini",
        template_id=template_id
    )

    if image_attachments and outline.slides:
        for idx, att in enumerate(image_attachments):
            if idx < len(outline.slides):
                outline.slides[idx].image_url = att.url
                outline.slides[idx].image_caption = att.summary or f"Attachment: {att.filename}"
                if outline.slides[idx].type not in ("title", "image_text"):
                    outline.slides[idx].type = "image_text"

    return outline


def generate_outline(request: OutlineRequest) -> Outline:
    """Backward compatible endpoint for simple outline generation."""
    chat_req = ChatRequest(
        prompt=request.topic,
        slide_count=request.slide_count,
        audience=request.audience,
        tone=request.tone,
        theme_id=request.theme_id,
        template_id=request.template_id,
        api_key=request.api_key,
        provider=request.provider,
        model=request.model,
        base_url=request.base_url,
    )
    outline, _, _ = generate_deck_from_chat(chat_req)
    return outline

