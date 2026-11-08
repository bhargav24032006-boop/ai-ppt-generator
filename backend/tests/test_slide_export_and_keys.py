import pytest
from starlette.testclient import TestClient
from main import app
from app.services.deck_builder import create_presentation
from app.schemas import Outline, Slide

client = TestClient(app)

def test_api_providers_endpoint():
    res = client.get("/api/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    provider_ids = [p["id"] for p in data["providers"]]
    assert "gemini" in provider_ids
    assert "grok" in provider_ids
    assert "openai" in provider_ids
    assert "claude" in provider_ids


def test_api_verify_llm_key_endpoint():
    # Empty key test
    res_empty = client.post("/api/verify-llm-key", json={"api_key": ""})
    assert res_empty.status_code == 200
    assert res_empty.json()["valid"] is False

    # Invalid fake key test
    res_invalid = client.post("/api/verify-llm-key", json={"api_key": "sk-invalid-test-key-12345", "provider": "openai"})
    assert res_invalid.status_code == 200
    data = res_invalid.json()
    assert data["valid"] is False
    assert data["provider"] == "openai"


def test_slide_image_export_endpoints():
    # 1. Create a real presentation
    outline = Outline(
        title="Slide Image Export Test",
        subtitle="High-Fidelity PowerPoint Image Rendering",
        theme_id="google-gemini",
        slides=[
            Slide(
                id="s1",
                type="title",
                category="VERIFICATION",
                title="Slide Image Export Test",
                subtitle="High-Fidelity PowerPoint Image Rendering"
            ),
            Slide(
                id="s2",
                type="bullets",
                category="PILLARS",
                title="Pillars of Slide Image Rendering",
                bullets=["Native PowerPoint COM export at 1920x1080", "Lossless PNG compression", "Slide deck ZIP archive bundling"]
            )
        ]
    )
    file_id = create_presentation(outline)
    assert file_id

    # 2. Test export slides endpoint
    res_export = client.get(f"/api/export-slides/{file_id}")
    assert res_export.status_code == 200
    exp_data = res_export.json()
    assert exp_data["file_id"] == file_id
    assert exp_data["count"] == 2
    assert len(exp_data["slides"]) == 2
    assert exp_data["slides"][0]["slide_index"] == 1
    assert exp_data["slides"][0]["width"] == 1920

    # 3. Test individual slide image download
    img_res = client.get(f"/api/download/{file_id}/slides/1/image")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 1000

    # 4. Test slide zip bundle
    zip_res = client.get(f"/api/download/{file_id}/slides/zip")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert len(zip_res.content) > 1000
