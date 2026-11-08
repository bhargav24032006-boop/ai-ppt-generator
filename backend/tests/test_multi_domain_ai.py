import pytest
from app.schemas import ChatRequest
from app.services.ai_service import generate_deck_from_chat
from app.services.presentation_agent import extract_semantic_profile

def test_multi_domain_classification():
    # 1. History
    p_hist = extract_semantic_profile("The French Revolution: Catalysts, Upheaval and Modern Legacy")
    assert p_hist.domain == "history_culture"
    assert "French Revolution" in p_hist.topic_title

    # 2. Culinary / Food
    p_food = extract_semantic_profile("The Art of Artisanal Sourdough Baking and Wild Yeast Fermentation")
    assert p_food.domain == "food_culinary"

    # 3. Science
    p_sci = extract_semantic_profile("Quantum Computing: Principles of Superposition and Entanglement")
    assert p_sci.domain == "science_space"

    # 4. Medicine & Health
    p_med = extract_semantic_profile("Targeted Immunotherapy and Oncology Clinical Trial Breakthroughs")
    assert p_med.domain == "medicine_health"

    # 5. Wellness & Fitness
    p_fit = extract_semantic_profile("VO2 Max Optimization, Endurance Marathon Conditioning and Recovery Science")
    assert p_fit.domain == "wellness_fitness"

    # 6. Climate
    p_env = extract_semantic_profile("Decarbonization Pathways: Scaling Solar, Wind and Grid Battery Storage")
    assert p_env.domain == "climate_environment"


def test_generate_presentation_on_history_topic():
    req = ChatRequest(
        prompt="The French Revolution: Catalysts, Upheaval and Modern Legacy",
        slide_count=6,
        auto_generate_images=False
    )
    deck, msg, _ = generate_deck_from_chat(req)
    assert deck is not None
    assert len(deck.slides) == 6
    assert "French Revolution" in deck.title
    # Check that it did NOT output generic software boilerplate
    for s in deck.slides:
        assert "microservices" not in s.title.lower()
        assert "kubernetes" not in s.title.lower()
        if s.type == "title":
            assert "HISTORICAL" in s.category


def test_generate_presentation_on_culinary_topic():
    req = ChatRequest(
        prompt="Mastering Sourdough Bread: Hydration Ratios, Cold Fermentation and Baking",
        slide_count=6,
        auto_generate_images=False
    )
    deck, msg, _ = generate_deck_from_chat(req)
    assert deck is not None
    assert len(deck.slides) == 6
    assert any(s.type == "metrics" for s in deck.slides)
    # Check metric numbers relate to fermentation or baking
    metric_slide = next(s for s in deck.slides if s.type == "metrics")
    labels = [stat.label.lower() for stat in metric_slide.stats]
    assert any("hydration" in l or "fermentation" in l or "baking" in l or "crumb" in l or "leavened" in l for l in labels)


def test_generate_presentation_with_user_custom_numbers():
    req = ChatRequest(
        prompt="Autonomous Drone Delivery: Achieving 45ms collision latency, 120km flight radius, and $2.50 cost per delivery",
        slide_count=6,
        auto_generate_images=False
    )
    deck, msg, _ = generate_deck_from_chat(req)
    metric_slide = next(s for s in deck.slides if s.type == "metrics")
    values = [stat.value for stat in metric_slide.stats]
    # Verify user numbers were captured into metrics
    assert any("45ms" in v or "120km" in v or "$2.50" in v or "45" in v for v in values)
