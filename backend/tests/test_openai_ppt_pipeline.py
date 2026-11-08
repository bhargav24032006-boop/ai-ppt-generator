"""End-to-end verification tests for the OpenAI-powered PPT presentation pipeline."""
from __future__ import annotations

import base64
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import ChatRequest, AIOutline, Slide, Outline
from app.services.llm_gateway import (
    detect_provider,
    resolve_credentials,
    has_configured_llm,
    normalize_slide_payload,
    normalize_outline_payload,
)
from app.services.presentation_agent import presentation_agent
from app.services.ai_service import generate_deck_from_chat
from app.services.deck_builder import create_presentation
from app.services.image_service import generate_with_openai_dalle


def test_openai_credential_resolution():
    assert detect_provider("sk-proj-abc123xyz") == "openai"
    assert detect_provider("sk-ant-api03-xyz") == "claude"
    assert detect_provider("sk-or-v1-xyz") == "custom"
    assert detect_provider("AIzaSyAbc123") == "gemini"

    prov, key, mod, base = resolve_credentials(
        api_key="sk-proj-testkey999",
        provider="openai",
        model="gpt-4o",
    )
    assert prov == "openai"
    assert mod == "gpt-4o"
    assert base == "https://api.openai.com/v1"
    assert key == "sk-proj-testkey999"
    assert has_configured_llm("sk-proj-testkey999", "openai") is True

    # Legacy expired demo Grok key should be ignored automatically when no env keys are set
    demo_grok = "grok_46580b20988b83a360d82699b8e2cf39_a6b20bd9ec170814e3a38176c18d669f51f80a893d345a2cf0fbeeda1798e256"
    with patch("app.services.llm_gateway.OPENAI_API_KEY", ""), \
         patch("app.services.llm_gateway.GEMINI_API_KEY", ""), \
         patch("app.services.llm_gateway.GROK_API_KEY", ""):
        assert has_configured_llm(demo_grok, "grok") is False


def test_normalize_openai_outline_payload():
    raw_openai_json = {
        "deck_title": "AI-Native Cloud Infrastructure",
        "deck_subtitle": "Scaling low-latency inference across global edge regions",
        "slides": [
            {
                "layout": "cover",
                "badge": "architecture keynote",
                "headline": "AI-Native Cloud Infrastructure",
                "subheadline": "Next-generation distributed inference fabric",
                "image_prompt": "Futuristic isometric cloud server architecture with glowing fiber optics",
                "speaker_notes": "Welcome the executive leadership team.",
            },
            {
                "slide_type": "kpi",
                "tag": "BENCHMARKS",
                "title": "Quantified Infrastructure Gains",
                "kpis": [
                    {"number": "4.2x", "metric": "Throughput", "delta": "+68% YoY"},
                    {"number": "18ms", "metric": "P99 Latency", "delta": "-54% vs legacy"},
                    {"number": "99.99%", "metric": "SLA Uptime", "delta": "Multi-region"},
                ],
                "presenter_notes": "Highlight the 4.2x throughput improvement.",
            },
            {
                "type": "comparison",
                "title": "Legacy Clusters vs AI-Native Fabric",
                "left_column": ["Static GPU reservations", "Manual failover scripts", "High idle cost"],
                "right_column": ["Elastic tensor routing", "Autonomous self-healing", "Zero-waste spot orchestration"],
            },
            {
                "type": "matrix",
                "title": "Regional Deployment Matrix",
                "table": {
                    "columns": ["Region", "Baseline Latency", "Edge Fabric"],
                    "rows": [
                        {"Region": "US-East", "Baseline Latency": "62ms", "Edge Fabric": "14ms"},
                        {"Region": "EU-Central", "Baseline Latency": "78ms", "Edge Fabric": "19ms"},
                    ],
                },
            },
            {
                "type": "roadmap",
                "title": "Phased Rollout Timeline",
                "phases": [
                    {"phase": "Q1", "title": "Core Mesh", "desc": "Deploy control plane"},
                    {"phase": "Q2", "title": "Global Edge", "desc": "Activate 24 PoPs"},
                ],
            },
        ],
    }

    normalized = normalize_outline_payload(raw_openai_json)
    ai_outline = AIOutline(**normalized)
    assert ai_outline.title == "AI-Native Cloud Infrastructure"
    assert len(ai_outline.slides) == 5
    assert ai_outline.slides[0].type == "title"
    assert ai_outline.slides[0].visual.image.prompt.startswith("Futuristic isometric")
    assert ai_outline.slides[1].type == "metrics"
    assert len(ai_outline.slides[1].stats) == 3
    assert ai_outline.slides[2].type == "two_column"
    assert ai_outline.slides[3].type == "table"
    assert ai_outline.slides[3].table.headers == ["Region", "Baseline Latency", "Edge Fabric"]
    assert ai_outline.slides[4].type == "timeline"
    assert len(ai_outline.slides[4].bullets) == 2


def test_openai_agent_and_conversational_refinement():
    mock_openai_deck = {
        "title": "Quantum Cryptography Readiness",
        "subtitle": "Post-quantum migration roadmap for enterprise banking",
        "slides": [
            {
                "type": "title",
                "category": "SECURITY KEYNOTE",
                "title": "Quantum Cryptography Readiness",
                "subtitle": "Post-quantum migration roadmap for enterprise banking",
                "bullets": [],
                "notes": "Opening remarks.",
            },
            {
                "type": "bullets",
                "category": "CORE PILLARS",
                "title": "NIST PQC Standard Adoption",
                "subtitle": "Transitioning from RSA-2048 to lattice-based ML-KEM",
                "bullets": [
                    "Cryptographic Inventory: Audit all TLS 1.3 and HSM key exchange endpoints",
                    "Hybrid Key Exchange: Deploy X25519Kyber768 across external API gateways",
                    "Hardware Acceleration: Upgrade HSM firmware for lattice signature verification",
                ],
                "notes": "Walk through the three migration pillars.",
            },
            {
                "type": "metrics",
                "category": "BENCHMARKS",
                "title": "Migration Telemetry",
                "stats": [
                    {"value": "100%", "label": "NIST FIPS 203 Compliance", "change": "Verified"},
                    {"value": "< 1.4ms", "label": "Handshake Overhead", "change": "Sub-2ms SLA"},
                    {"value": "480+", "label": "Protected Microservices", "change": "Zero Downtime"},
                ],
                "notes": "Present key performance metrics.",
            },
        ],
    }

    with patch("app.services.presentation_agent.call_llm_json_with_meta") as mock_llm:
        mock_llm.return_value = (mock_openai_deck, "openai", "gpt-4o-mini")
        req = ChatRequest(
            prompt="Create a 3 slide presentation on Quantum Cryptography Readiness",
            slide_count=3,
            api_key="sk-proj-testopenai",
            provider="openai",
            model="gpt-4o-mini",
            auto_generate_images=False,
        )
        outline, msg, idx = presentation_agent.generate_presentation(req)
        assert outline.title == "Quantum Cryptography Readiness"
        assert len(outline.slides) == 3
        assert "OpenAI (gpt-4o-mini)" in msg

        # Compile to actual .pptx and verify file creation
        file_id = create_presentation(outline=outline, theme_id="google-gemini")
        assert file_id

    # Test conversational slide polish on Slide 2 without losing the deck
    with patch("app.services.ai_service.call_llm_json_with_meta") as mock_polish_llm:
        mock_polish_llm.return_value = (
            {
                "type": "bullets",
                "category": "EXECUTIVE BRIEFING",
                "title": "Accelerated NIST FIPS 203 Post-Quantum Migration",
                "subtitle": "Zero-trust lattice cryptography across tier-1 banking gateways",
                "bullets": [
                    "Full Discovery: Automated cryptographic bill of materials (CBOM) across 480 services",
                    "Hybrid TLS: Immediate protection against harvest-now-decrypt-later attacks",
                    "HSM Readiness: Validated FIPS 203/204 firmware across primary data centers",
                ],
                "notes": "Executive summary of NIST PQC readiness.",
            },
            "openai",
            "gpt-4o-mini",
        )
        polish_req = ChatRequest(
            prompt="Sharpen and make the title and bullet points on slide 2 more executive, authoritative, and impactful.",
            api_key="sk-proj-testopenai",
            provider="openai",
            model="gpt-4o-mini",
            current_deck=outline,
            auto_generate_images=False,
        )
        updated_deck, polish_msg, mod_idx = generate_deck_from_chat(polish_req)
        assert len(updated_deck.slides) == 3
        assert mod_idx == 1
        assert updated_deck.slides[1].title == "Accelerated NIST FIPS 203 Post-Quantum Migration"
        assert "OpenAI (gpt-4o-mini)" in polish_msg


def test_openai_dalle_image_generation():
    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 5000
    encoded = base64.b64encode(fake_bytes).decode("ascii")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"b64_json": encoded}]}

    with patch("app.services.image_service.requests.post", return_value=mock_resp) as mock_post:
        result = generate_with_openai_dalle("Isometric 3D cloud neural network", api_key="sk-proj-testopenai")
        assert result == fake_bytes
        assert mock_post.called


def test_full_http_endpoints_and_template_engine():
    from fastapi.testclient import TestClient
    import main
    from app.config import TEMPLATES_DIR, DECKS_DIR
    from app.services.reverse_engineering_engine import reverse_engineer_template
    from app.services.template_deck_builder import generate_presentation_from_template

    client = TestClient(main.app)

    # 1. Health & Providers
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "online"
    assert "has_openai_key" in r_health.json()

    r_prov = client.get("/api/providers")
    assert r_prov.status_code == 200
    assert r_prov.json()["providers"][0]["id"] == "openai"

    # 2. Themes & Templates
    r_themes = client.get("/api/themes")
    assert r_themes.status_code == 200
    assert len(r_themes.json()) >= 5

    r_tmpls = client.get("/api/templates")
    assert r_tmpls.status_code == 200
    templates_list = r_tmpls.json()
    assert isinstance(templates_list, list)

    # 3. Conversational /api/chat with mocked OpenAI
    sample_openai_deck = {
        "title": "Next-Gen Autonomous Robotics",
        "subtitle": "Embodied AI and industrial dexterous manipulation",
        "slides": [
            {
                "type": "title",
                "category": "ROBOTICS KEYNOTE",
                "title": "Next-Gen Autonomous Robotics",
                "subtitle": "Embodied AI and industrial dexterous manipulation",
                "bullets": [],
                "notes": "Welcome to the keynote.",
            },
            {
                "type": "metrics",
                "category": "TELEMETRY",
                "title": "Actuation Precision & Throughput",
                "stats": [
                    {"value": "99.7%", "label": "Grasp Success Rate", "change": "+24% YoY"},
                    {"value": "3.4x", "label": "Assembly Speed", "change": "Verified"},
                    {"value": "12ms", "label": "Control Loop Latency", "change": "Edge Inference"},
                ],
                "notes": "Discuss the 12ms control loop.",
            },
            {
                "type": "table",
                "category": "BENCHMARKS",
                "title": "Generation Comparison Matrix",
                "table": {
                    "headers": ["Capability", "Gen-1", "Gen-2 Embodied AI", "Gain"],
                    "rows": [
                        ["Degrees of Freedom", "6 DoF", "22 DoF Bimanual", "3.6x Dexterity"],
                        ["Task Adaptation", "Hardcoded paths", "Zero-shot VLA policy", "Instant"],
                    ],
                },
                "notes": "Compare Gen-1 and Gen-2.",
            },
        ],
    }

    with patch("app.services.presentation_agent.call_llm_json_with_meta") as mock_llm:
        mock_llm.return_value = (sample_openai_deck, "openai", "gpt-4o")
        r_chat = client.post(
            "/api/chat",
            json={
                "prompt": "Create a 3 slide presentation on Next-Gen Autonomous Robotics",
                "slide_count": 3,
                "api_key": "sk-proj-testopenai",
                "provider": "openai",
                "model": "gpt-4o",
                "theme_id": "google-gemini",
                "auto_generate_images": False,
            },
        )
        assert r_chat.status_code == 200
        chat_data = r_chat.json()
        assert chat_data["provider_used"] == "openai"
        assert chat_data["model_used"] == "gpt-4o"
        assert "OpenAI (gpt-4o)" in chat_data["message"]
        assert len(chat_data["deck"]["slides"]) == 3
        file_id = chat_data["file_id"]

        # Verify PPTX download
        r_dl = client.get(f"/api/download/{file_id}")
        assert r_dl.status_code == 200
        assert len(r_dl.content) > 10000

    # 4. Template Reverse Engineering & Generation (/api/generate-from-template)
    existing_tmpls = list(TEMPLATES_DIR.glob("*.pptx"))
    if existing_tmpls:
        t_id = existing_tmpls[0].stem
        with patch("app.services.presentation_agent.call_llm_json_with_meta") as mock_tmpl_llm:
            mock_tmpl_llm.return_value = (sample_openai_deck, "openai", "gpt-4o-mini")
            r_gen_tmpl = client.post(
                "/api/generate-from-template",
                json={
                    "api_key": "sk-proj-testopenai",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "template_id": t_id,
                    "theme_id": "google-gemini",
                    "topic": "Next-Gen Autonomous Robotics",
                    "prompt": "Embodied AI and industrial dexterous manipulation",
                    "slide_count": 3,
                    "image_source": "none",
                },
            )
            assert r_gen_tmpl.status_code == 200
            gen_data = r_gen_tmpl.json()
            assert gen_data["status"] == "success"
            assert len(gen_data["neural_match_report"]) == 3
            tmpl_pptx = DECKS_DIR / f"{gen_data['file_id']}.pptx"
            assert tmpl_pptx.exists() and tmpl_pptx.stat().st_size > 10000


def test_neural_network_training_accuracy_and_archetype_planning():
    from app.services.neural_engine import (
        get_neural_model,
        generate_training_dataset,
        predict_slide_archetype,
        plan_deck_archetypes_from_prompt,
        ARCHETYPES,
    )

    model = get_neural_model(force_retrain=True)
    X_train, y_train = generate_training_dataset(seed=101, samples_per_class=160)
    X_val, y_val = generate_training_dataset(seed=777, samples_per_class=80)

    train_eval = model.evaluate(X_train, y_train)
    val_eval = model.evaluate(X_val, y_val)

    print(
        f"[NeuralEngine] Train Accuracy: {train_eval['accuracy']}% (loss={train_eval['loss']}) | "
        f"Unseen Val Accuracy: {val_eval['accuracy']}% (loss={val_eval['loss']})"
    )
    print(f"[NeuralEngine] Per-Class Val Accuracy: {val_eval['per_class_accuracy']}")

    assert train_eval["accuracy"] >= 99.0, f"Expected >= 99% train accuracy, got {train_eval['accuracy']}%"
    assert val_eval["accuracy"] >= 99.0, f"Expected >= 99% val accuracy, got {val_eval['accuracy']}%"
    for arch in ARCHETYPES:
        assert val_eval["per_class_accuracy"][arch] >= 97.5, f"Archetype {arch} accuracy too low: {val_eval['per_class_accuracy'][arch]}%"

    # Verify real-world slide intent predictions
    p_title = predict_slide_archetype(title="AI Cloud Strategy 2026", subtitle="Executive Keynote Overview", slide_index=0, total_slides=8)
    assert p_title["best_archetype"] == "title" and p_title["confidence_percent"] >= 90.0

    p_comp = predict_slide_archetype(title="Monolithic vs Microservices Comparison", left=["Legacy monolith"], right=["Cloud-native mesh"], slide_index=2, total_slides=8)
    assert p_comp["best_archetype"] == "two_column" and p_comp["confidence_percent"] >= 90.0

    p_metrics = predict_slide_archetype(title="Q4 Revenue & ROI Benchmarks", stats=[{"value": "4.2x", "label": "ROI"}, {"value": "99.9%", "label": "SLA"}], slide_index=3, total_slides=8)
    assert p_metrics["best_archetype"] == "metrics" and p_metrics["confidence_percent"] >= 90.0

    p_timeline = predict_slide_archetype(title="Phased Rollout Roadmap & Q1-Q4 Milestones", bullets=["Phase 1: Discovery", "Phase 2: Pilot", "Phase 3: Scale"], slide_index=4, total_slides=8)
    assert p_timeline["best_archetype"] == "timeline" and p_timeline["confidence_percent"] >= 85.0

    p_table = predict_slide_archetype(title="Feature Specification Matrix & Pricing Tier Breakdown", table={"headers": ["A", "B"], "rows": [["1", "2"]]}, slide_index=5, total_slides=8)
    assert p_table["best_archetype"] == "table" and p_table["confidence_percent"] >= 90.0

    p_quote = predict_slide_archetype(title="Foundational Vision", quote="Intelligence is the ultimate force multiplier for human creativity.", slide_index=5, total_slides=8)
    assert p_quote["best_archetype"] == "quote" and p_quote["confidence_percent"] >= 90.0

    p_conc = predict_slide_archetype(title="Conclusion & Strategic Next Steps", bullets=["Immediate action items", "Q&A"], slide_index=7, total_slides=8)
    assert p_conc["best_archetype"] == "conclusion" and p_conc["confidence_percent"] >= 90.0

    # Verify prompt-driven deck archetype planning
    plan = plan_deck_archetypes_from_prompt(
        "Create a 6-slide presentation on Renewable Energy Storage including Lithium-Ion vs Solid-State Batteries, Market Growth & ROI Metrics, and 2025-2030 Deployment Roadmap",
        slide_count=6,
    )
    assert len(plan) == 6
    assert plan[0]["archetype"] == "title"
    assert plan[-1]["archetype"] == "conclusion"
    middle_archs = [p["archetype"] for p in plan[1:-1]]
    assert "two_column" in middle_archs
    assert "metrics" in middle_archs
    assert "timeline" in middle_archs


def test_input_faithful_synthesis_and_query_cleaning():
    from app.config import is_valid_api_key
    from app.services.web_search_service import clean_query_term
    from app.services.presentation_agent import extract_semantic_profile, SemanticContentSynthesizer

    assert is_valid_api_key("your_api_key_here") is False
    assert is_valid_api_key("sk-your-key-here") is False
    assert is_valid_api_key("sk-proj-validRealLookingKey123456") is True

    cleaned = clean_query_term(
        "Create a 6-slide presentation on Quantum Computing including Qubits, Error Correction, and Cryptography (Ground in verified web reference facts)"
    )
    assert cleaned == "Quantum Computing"

    profile = extract_semantic_profile(
        "Create a 6-slide presentation on Solid-State Battery Technology vs Lithium-Ion including Energy Density, Fast Charging, and Manufacturing Roadmap (Ground in verified web reference facts)"
    )
    assert "Ground In Verified" not in profile.topic_title
    assert "Solid-State Battery Technology" in profile.topic_title
    assert any("energy density" in kp.lower() for kp in profile.key_phrases)

    profile.web_facts = {
        "title": "Solid-state battery",
        "description": "Battery technology that uses solid electrodes and a solid electrolyte",
        "key_facts": [
            "Solid-state batteries replace liquid or polymer gel electrolytes with solid electrolytes for higher energy density.",
            "They substantially reduce flammability risk and enable faster charging cycles compared to conventional lithium-ion cells.",
            "In 2023 major automotive manufacturers announced pilot production lines targeting 500 Wh/kg specific energy.",
        ],
        "sections": [
            {
                "heading": "Electrolyte Materials & Architecture",
                "bullets": [
                    "Ceramics, sulfides, and solid polymers serve as primary ion-conducting solid electrolytes.",
                    "Dendrite suppression at the lithium-metal anode interface is a central engineering focus.",
                ],
            }
        ],
        "timeline_events": [
            "In 2023 major automotive manufacturers announced pilot production lines targeting 500 Wh/kg specific energy."
        ],
        "quantitative_facts": [
            "In 2023 major automotive manufacturers announced pilot production lines targeting 500 Wh/kg specific energy."
        ],
    }

    deck = SemanticContentSynthesizer.synthesize_deck(profile=profile, slide_count=6)
    assert len(deck.slides) == 6
    deck_blob = " ".join(
        f"{s.title} {s.subtitle} {' '.join(s.bullets)} {' '.join(s.left)} {' '.join(s.right)}"
        for s in deck.slides
    ).lower()
    assert "solid-state" in deck_blob
    assert "electrolyte" in deck_blob
    assert "energy density" in deck_blob
    assert any(s.type == "diagram" and s.visual and s.visual.diagram and len(s.visual.diagram.nodes) >= 4 for s in deck.slides)


def test_architecture_generation_drawing_and_planning():
    import os
    from fastapi.testclient import TestClient
    import main
    from app.config import IMAGES_DIR, DECKS_DIR
    from app.services.architecture_engine import (
        generate_architecture_blueprint,
        build_architecture_slides_from_blueprint,
    )

    os.environ["DISABLE_FREE_LLM_RELAY"] = "1"
    try:
        bp = generate_architecture_blueprint(
            prompt="Generate architecture for an Autonomous Multi-Agent Cloud Platform including API Gateway, Neural Router, RAG Vector DB, and Event Stream, draw it, understand it, and give plans and ideas",
            topic="Autonomous Multi-Agent Cloud Platform",
            draw_image=True,
        )
        assert bp["diagram"] is not None
        assert len(bp["diagram"].clusters) >= 3
        assert len(bp["diagram"].nodes) >= 5
        assert len(bp["diagram"].edges) >= 4
        assert len(bp["architecture_understanding"]) >= 4
        assert len(bp["execution_plan"]) >= 4
        assert len(bp["strategic_ideas"]) >= 4
        assert bp["image_url"].startswith("/api/images/arch_")
        img_file = IMAGES_DIR / bp["image_id"]
        assert img_file.exists() and img_file.stat().st_size > 15000

        slides = build_architecture_slides_from_blueprint(bp)
        assert len(slides) == 3
        assert slides[0].type == "diagram"
        assert slides[1].type == "timeline"
        assert slides[2].type == "two_column"

        # Compile an Outline containing the diagram slide into a real .pptx file
        arch_outline = Outline(
            title=bp["title"],
            subtitle=bp["subtitle"],
            theme_id="google-gemini",
            slides=slides,
        )
        pptx_id = create_presentation(outline=arch_outline, theme_id="google-gemini")
        assert (DECKS_DIR / f"{pptx_id}.pptx").exists()

        # Verify HTTP endpoint /api/architecture/generate
        client = TestClient(main.app)
        r_arch = client.post(
            "/api/architecture/generate",
            json={
                "prompt": "Design a Smart Grid Renewable Battery Storage Architecture and give plans and ideas",
                "draw_image": True,
            },
        )
        assert r_arch.status_code == 200
        arch_json = r_arch.json()
        assert arch_json["status"] == "success"
        assert len(arch_json["diagram"]["nodes"]) >= 5
        assert len(arch_json["execution_plan"]) >= 4
        assert len(arch_json["strategic_ideas"]) >= 4
        assert "Architecture Understanding" in arch_json["summary_markdown"]
    finally:
        os.environ.pop("DISABLE_FREE_LLM_RELAY", None)


if __name__ == "__main__":
    test_openai_credential_resolution()
    print("[PASS] test_openai_credential_resolution")
    test_normalize_openai_outline_payload()
    print("[PASS] test_normalize_openai_outline_payload")
    test_openai_agent_and_conversational_refinement()
    print("[PASS] test_openai_agent_and_conversational_refinement")
    test_openai_dalle_image_generation()
    print("[PASS] test_openai_dalle_image_generation")
    test_neural_network_training_accuracy_and_archetype_planning()
    print("[PASS] test_neural_network_training_accuracy_and_archetype_planning")
    test_input_faithful_synthesis_and_query_cleaning()
    print("[PASS] test_input_faithful_synthesis_and_query_cleaning")
    test_architecture_generation_drawing_and_planning()
    print("[PASS] test_architecture_generation_drawing_and_planning")
    test_full_http_endpoints_and_template_engine()
    print("[PASS] test_full_http_endpoints_and_template_engine")
    print("ALL OPENAI PPT PIPELINE, NEURAL ACCURACY, ARCHITECTURE & E2E HTTP TESTS PASSED!")
