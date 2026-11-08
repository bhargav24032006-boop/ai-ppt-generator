import io
from pathlib import Path
from PIL import Image
import pytest

from app.services.image_service import (
    build_neural_image_prompt,
    generate_procedural_neural_graphic,
    generate_slide_image
)
from app.config import IMAGES_DIR

def test_build_neural_image_prompt():
    prompt = build_neural_image_prompt(
        slide_title="Autonomous Cloud Architecture",
        topic="Enterprise Cloud",
        category="INFRASTRUCTURE",
        style="3d"
    )
    assert "Autonomous Cloud Architecture" in prompt
    assert "3D isometric digital render" in prompt

def test_generate_procedural_neural_graphic():
    img_bytes = generate_procedural_neural_graphic("AI Core", "Neural Networks")
    assert img_bytes is not None
    assert len(img_bytes) > 2000

    # Verify valid image using PIL
    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1024, 640)
    assert img.format == "JPEG"

def test_generate_slide_image_service():
    res = generate_slide_image(
        slide_title="High-Velocity Multi-Agent Engine",
        topic="Next-Gen AI Systems",
        category="ARCHITECTURE",
        style="3d",
        preferred_provider="procedural"  # Test reliable offline generator directly
    )
    assert "image_id" in res
    assert "filename" in res
    assert "url" in res
    assert res["url"].startswith("/api/images/")
    assert Path(res["local_path"]).exists()
