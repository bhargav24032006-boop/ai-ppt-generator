import pytest
from starlette.testclient import TestClient
from main import app
from app.themes import list_themes, get_theme, PRESET_THEMES

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "themes_count" in data
    assert data["themes_count"] >= 6
    assert "has_grok_key" in data
    assert data["has_grok_key"] is True
    assert data["grok_key_name"] == "aipptmaker"
    assert data["ai_active"] is True

def test_themes_endpoint():
    response = client.get("/api/themes")
    assert response.status_code == 200
    themes = response.json()
    assert len(themes) >= 6
    theme_ids = [t["id"] for t in themes]
    assert "google-gemini" in theme_ids
    assert "modern-dark" in theme_ids
    assert "corporate-clean" in theme_ids
    assert "emerald-tech" in theme_ids
    assert "sunset-gradient" in theme_ids
    assert "luxury-gold" in theme_ids

def test_theme_properties():
    theme = get_theme("google-gemini")
    assert theme.id == "google-gemini"
    assert theme.bg_color
    assert theme.card_bg
    assert theme.accent_primary
    assert theme.accent_secondary
    assert theme.font_title
    assert theme.font_body

def test_theme_fallback():
    theme = get_theme("non-existent-theme-xyz")
    assert theme.id == "google-gemini"
