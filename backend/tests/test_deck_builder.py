import os
from pathlib import Path
import pytest
from pptx import Presentation

from app.schemas import Outline, Slide, StatItem, TableSpec
from app.services.deck_builder import create_presentation
from app.config import DECKS_DIR

def test_deck_builder_all_layouts():
    slides = [
        Slide(
            id="s1",
            type="title",
            category="EXECUTIVE KEYNOTE",
            title="Next-Gen Autonomous Enterprise",
            subtitle="Architectural Foundations & Scaling Vectors",
            notes="Opening greeting for keynote."
        ),
        Slide(
            id="s2",
            type="section",
            category="SECTION 01",
            title="Strategic Foundation & Thesis",
            subtitle="Transitioning to self-orchestrating systems",
            notes="Section intro."
        ),
        Slide(
            id="s3",
            type="bullets",
            category="CORE PILLARS",
            title="Strategic Execution Imperatives",
            subtitle="Actionable principles powering velocity",
            bullets=[
                "Modular architecture decoupling core services",
                "Continuous feedback optimization loop",
                "Verifiable delivery milestones"
            ],
            notes="Review core pillars."
        ),
        Slide(
            id="s4",
            type="two_column",
            category="COMPARISON",
            title="Comparative Architecture: Legacy vs Modern",
            subtitle="Trade-off evaluation across dimensions",
            left=["Legacy Constraints", "• High manual friction", "• Slow iteration cycles"],
            right=["Modern Solution", "• Autonomous generation", "• Real-time canvas editing"],
            notes="Explain comparison."
        ),
        Slide(
            id="s5",
            type="metrics",
            category="TRACTION & IMPACT",
            title="Measurable Quantitative Proof",
            subtitle="Validated benchmark numbers",
            stats=[
                StatItem(value="99.8%", label="Service Reliability", change="+14% YoY"),
                StatItem(value="4.5x", label="Efficiency Factor", change="Top Decile"),
                StatItem(value="$14.2M", label="Annual Run Rate", change="+88% Growth")
            ],
            notes="Highlight the metrics."
        ),
        Slide(
            id="s6",
            type="timeline",
            category="ROADMAP",
            title="Phased Implementation Roadmap",
            subtitle="Milestones from architecture to scale",
            bullets=[
                "Phase 1: Architecture Blueprint & Technical Scoping",
                "Phase 2: Platform MVP & Multi-Agent Integration",
                "Phase 3: Security Validation & Enterprise Pilot",
                "Phase 4: Full Deployment & Continuous Optimization"
            ],
            notes="Walk through phases."
        ),
        Slide(
            id="s7",
            type="table",
            category="EVALUATION",
            title="Operational Benchmark Matrix",
            subtitle="Side-by-side evaluation table",
            table=TableSpec(
                headers=["Dimension", "Legacy Baseline", "Modern AI Engine", "Efficiency Multiplier"],
                rows=[
                    ["Turnaround", "3-5 Days", "Under 2 Seconds", "99% Faster"],
                    ["Visual Quality", "Generic clip art", "Tailored isometric 3D", "10x Engagement"]
                ]
            ),
            notes="Review table data."
        ),
        Slide(
            id="s8",
            type="quote",
            category="EXECUTIVE VISION",
            title="Core Vision",
            subtitle="Guiding philosophy",
            quote="Innovation is the ability to see change as an opportunity - not a threat.",
            notes="Close with inspiring quote."
        ),
        Slide(
            id="s9",
            type="image_text",
            category="VISUAL ASSET",
            title="Architecture Blueprint",
            subtitle="Multi-tier neural processing pipeline",
            bullets=["Context grounding", "Prompt orchestration", "Native PowerPoint compilation"],
            image_caption="Architecture Visual Blueprint",
            notes="Explain architecture blueprint."
        ),
        Slide(
            id="s10",
            type="conclusion",
            category="NEXT STEPS",
            title="Strategic Takeaways & Call to Action",
            subtitle="Immediate execution checkpoints",
            bullets=["Deploy production pilot", "Track real-time telemetry", "Expand to enterprise tiers"],
            notes="Open for questions."
        )
    ]

    outline = Outline(
        title="Next-Gen Autonomous Enterprise",
        subtitle="Architectural Foundations & Scaling Vectors",
        theme_id="google-gemini",
        slides=slides
    )

    file_id = create_presentation(outline, theme_id="google-gemini")
    assert file_id is not None
    assert len(file_id) > 10

    pptx_path = DECKS_DIR / f"{file_id}.pptx"
    assert pptx_path.exists()
    assert pptx_path.stat().st_size > 5000  # Valid PowerPoint file size

    # Re-open the generated PowerPoint presentation to prove it is 100% valid PPTX
    prs = Presentation(str(pptx_path))
    assert len(prs.slides) == 10

    # Verify speaker notes are written
    assert prs.slides[0].notes_slide.notes_text_frame.text == "Opening greeting for keynote."
    assert "Open for questions." in prs.slides[9].notes_slide.notes_text_frame.text

    # Verify 16:9 widescreen dimensions (13.333 x 7.5 inches)
    assert round(prs.slide_width.inches, 2) == 13.33
    assert round(prs.slide_height.inches, 2) == 7.5
