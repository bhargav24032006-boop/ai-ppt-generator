import pytest
from app.schemas import ChatRequest, Outline, Slide
from app.services.ai_service import _smart_generate_fallback, generate_deck_from_chat

def test_smart_generate_fallback():
    outline = _smart_generate_fallback(
        prompt="Pitch Deck for an Autonomous AI Startup",
        slide_count=8,
        theme_id="google-gemini"
    )
    assert outline is not None
    assert len(outline.slides) == 8
    assert outline.slides[0].type == "title"
    assert outline.title
    assert any(s.type == "metrics" for s in outline.slides)
    assert any(s.type == "two_column" for s in outline.slides)
    assert any(s.type == "conclusion" for s in outline.slides)

def test_chat_theme_switch_intent():
    # Initial deck
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    assert initial_outline.theme_id == "google-gemini"

    req = ChatRequest(
        prompt="Change the theme to sunset",
        current_deck=initial_outline
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert deck.theme_id == "sunset-gradient"
    assert "sunset-gradient" in msg

def test_chat_add_metrics_slide_intent():
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    initial_count = len(initial_outline.slides)

    req = ChatRequest(
        prompt="Add a metrics and KPI slide with our performance stats",
        current_deck=initial_outline
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert len(deck.slides) == initial_count + 1
    new_slide = deck.slides[-1]
    assert new_slide.type == "metrics"
    assert len(new_slide.stats) > 0

def test_chat_add_table_slide_intent():
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    initial_count = len(initial_outline.slides)

    req = ChatRequest(
        prompt="Add a comparison table slide with benchmark dimensions",
        current_deck=initial_outline
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert len(deck.slides) == initial_count + 1
    new_slide = deck.slides[-1]
    assert new_slide.type == "table"
    assert new_slide.table is not None
    assert len(new_slide.table.headers) > 0

def test_chat_add_timeline_slide_intent():
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    initial_count = len(initial_outline.slides)

    req = ChatRequest(
        prompt="Add a phased timeline roadmap slide",
        current_deck=initial_outline
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert len(deck.slides) == initial_count + 1
    new_slide = deck.slides[-1]
    assert new_slide.type == "timeline"
    assert len(new_slide.bullets) >= 4

def test_chat_rename_slide_intent():
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    req = ChatRequest(
        prompt="Change the title of slide 2 to 'Autonomous Neural Engine'",
        current_deck=initial_outline
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert deck.slides[1].title == "Autonomous Neural Engine"
    assert modified_idx == 1

def test_chat_duplicate_and_delete_slide_intent():
    initial_outline = _smart_generate_fallback("AI Cloud Platform", slide_count=5)
    # Duplicate slide 1
    req_dup = ChatRequest(
        prompt="Duplicate slide 1",
        current_deck=initial_outline
    )
    deck, msg, _ = generate_deck_from_chat(req_dup)
    assert len(deck.slides) == 6

    # Delete slide 2
    req_del = ChatRequest(
        prompt="Delete slide 2",
        current_deck=deck
    )
    deck2, msg2, _ = generate_deck_from_chat(req_del)
    assert len(deck2.slides) == 5


def test_grok_aipptmaker_key_handling():
    req = ChatRequest(
        prompt="Create an enterprise AI roadmap keynote",
        slide_count=5,
        api_key="grok_46580b20988b83a360d82699b8e2cf39_a6b20bd9ec170814e3a38176c18d669f51f80a893d345a2cf0fbeeda1798e256"
    )
    deck, msg, modified_idx = generate_deck_from_chat(req)
    assert deck is not None
    assert len(deck.slides) >= 4
    assert deck.title
    assert modified_idx == 0

