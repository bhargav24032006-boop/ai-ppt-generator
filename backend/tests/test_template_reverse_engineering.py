import pytest
from pathlib import Path
from app.services.reverse_engineering_engine import reverse_engineer_template
from app.services.neural_engine import get_neural_model, predict_slide_archetype, train_neural_model_on_template
from app.services.template_deck_builder import generate_presentation_from_template, find_template_file
from app.schemas import Outline, Slide, StatItem
from app.config import TEMPLATES_DIR, DECKS_DIR

def test_reverse_engineering_and_neural_matching():
    # 1. Find existing template
    existing = list(TEMPLATES_DIR.glob("*.pptx"))
    assert len(existing) > 0, "At least one template should exist in storage/templates"
    tmpl_path = existing[0]

    # 2. Test Reverse Engineering
    meta = reverse_engineer_template(tmpl_path, template_id=tmpl_path.stem)
    assert meta.total_slides > 0
    assert meta.slide_width_in > 0
    assert meta.slide_height_in > 0
    assert len(meta.primary_color) == 6
    assert meta.title_font != ""

    # 3. Test Neural Model Prediction
    model = get_neural_model()
    assert model.trained_epochs > 0

    pred_metrics = predict_slide_archetype(
        title="Q3 Growth Metrics",
        subtitle="Key metrics",
        stats=[StatItem(value="99.4%", label="Uptime")]
    )
    assert pred_metrics["best_archetype"] == "metrics"
    assert pred_metrics["confidence_percent"] > 50.0

    pred_compare = predict_slide_archetype(
        title="Architecture Comparison: Monolith vs Microservices",
        left=["Single DB", "High coupling"],
        right=["Isolated services", "Scalable"]
    )
    assert pred_compare["best_archetype"] == "two_column"

    # 4. Test Template-driven PPT generation
    outline = Outline(
        title="Neural Template Generation Test",
        subtitle="Reverse Engineered Pipeline",
        template_id=tmpl_path.stem,
        slides=[
            Slide(
                id="t1",
                type="title",
                category="AI PRESENTATION",
                title="Neural Template Generation Test",
                subtitle="Reverse Engineered Pipeline",
                notes="Intro notes."
            ),
            Slide(
                id="t2",
                type="metrics",
                category="VALIDATED BENCHMARKS",
                title="Performance Metrics",
                subtitle="Measured output",
                stats=[
                    StatItem(value="99.9%", label="High Availability"),
                    StatItem(value="4.5x", label="Velocity")
                ],
                notes="Metrics notes."
            )
        ]
    )

    file_id, report = generate_presentation_from_template(outline, template_id=tmpl_path.stem)
    assert file_id is not None
    generated_file = DECKS_DIR / f"{file_id}.pptx"
    assert generated_file.exists(), "Generated PPTX must exist on disk"
    assert generated_file.stat().st_size > 1000, "Generated PPTX must not be empty"
    assert len(report["neural_match_report"]) == 2
