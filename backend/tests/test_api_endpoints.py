import pytest
from starlette.testclient import TestClient
from main import app
from app.services.ai_service import _smart_generate_fallback

client = TestClient(app)

def test_api_chat_generate_deck():
    payload = {
        "prompt": "Create an executive pitch presentation for a Cloud AI platform",
        "slide_count": 5,
        "theme_id": "google-gemini",
        "auto_generate_images": False
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "deck" in data
    assert len(data["deck"]["slides"]) == 5
    assert data["file_id"]
    assert data["download_url"]

def test_api_export_presentation():
    # Create sample deck outline
    deck = _smart_generate_fallback("Market Strategy Review", slide_count=4)
    payload = {
        "deck": deck.model_dump(),
        "theme_id": "modern-dark"
    }
    response = client.post("/api/export", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "file_id" in data
    assert "download_url" in data

    # Test download endpoint with the generated file_id
    dl_res = client.get(data["download_url"])
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 5000
    assert dl_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

def test_api_generate_image():
    payload = {
        "slide_title": "Multi-Modal Autonomous Agents",
        "topic": "AI Research",
        "category": "INNOVATION",
        "style": "3d",
        "preferred_provider": "procedural"
    }
    response = client.post("/api/generate-image", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "image_id" in data
    assert "url" in data
    assert "filename" in data

    # Verify serving the image
    img_res = client.get(data["url"])
    assert img_res.status_code == 200
    assert len(img_res.content) > 2000
