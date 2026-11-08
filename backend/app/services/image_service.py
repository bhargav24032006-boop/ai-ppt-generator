"""Cloud and Neural Network AI Image Generation Service.

Provides multi-tier image generation:
1. Cloud Diffusion Neural Networks (FLUX.1 / SDXL via Cloud AI Inference - Zero API key needed)
2. Google Gemini / Vertex AI Imagen 3 (When GEMINI_API_KEY is available)
3. Unsplash Cloud CDN (Contextual curated photography)
4. Procedural Neural / Vector Graphic Fallback (Offline PIL generator)
"""
from __future__ import annotations

import base64
import io
import math
import os
import random
import re
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

from ..config import (
    IMAGES_DIR, GEMINI_API_KEY,
    OPENAI_API_KEY, OPENAI_IMAGE_MODEL, OPENAI_BASE_URL,
    is_valid_api_key
)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)[:50]


def build_neural_image_prompt(
    slide_title: str,
    topic: str = "",
    category: str = "",
    style: str = "3d",
    custom_prompt: str = ""
) -> str:
    """Craft an executive-grade prompt engineered for presentation slide visuals (Gamma/Canva style)."""
    if custom_prompt.strip():
        base = custom_prompt.strip()
    else:
        subject = slide_title or topic or "Strategic Business Innovation"
        # Extract meaningful subject keywords
        subject = re.sub(r'^(the|an|a|overview of|insights on)\s+', '', subject, flags=re.IGNORECASE)
        base = f"{subject}, {category}" if category else subject

    style_modifiers = {
        "3d": "modern 3D isometric digital render, sleek volumetric lighting, glassmorphism elements, clean minimalist tech aesthetic, vibrant subtle gradients, Octane Render style, premium presentation hero asset, 8k, award-winning composition, no text, no watermarks",
        "photo": "editorial cinematic studio photography, high-end corporate documentary aesthetic, shallow depth of field, natural soft lighting, Hasselblad medium format, ultra-detailed 8k, professional executive keynote visual, no text",
        "cyberpunk": "futuristic cyberpunk neon aesthetic, glowing neural pathways, holographic data streams, deep indigo and violet ambient lighting, cinematic digital concept art, highly detailed, no text",
        "vector": "sleek minimalist flat vector illustration, clean lines, harmonious modern color palette, corporate tech branding style, crisp vector graphics, white and deep blue tones, no text",
        "abstract": "luxurious abstract flowing organic shapes, dynamic silk ribbon waves, iridescent color gradients, smooth ambient studio lighting, elegant modern desktop wallpaper style, high resolution, no text"
    }

    modifier = style_modifiers.get(style.lower(), style_modifiers["3d"])
    return f"{base}, {modifier}"


_GENERIC_WORDS = {
    "the", "a", "an", "of", "and", "for", "to", "in", "on", "with", "by", "from", "into", "its", "is", "are",
    "overview", "introduction", "conclusion", "summary", "strategy", "strategic", "executive", "comprehensive",
    "framework", "foundations", "context", "evidence", "comparison", "roadmap", "case", "study", "key",
    "insights", "analysis", "approach", "model", "models", "high", "velocity", "led", "product", "scaling",
    "future", "outlook", "next", "steps", "slide", "keynote", "visual", "asset", "depicting", "presentation",
    "deck", "hero", "concept", "vs", "how", "why", "what", "your", "our", "best", "practices", "guide",
}


def extract_visual_subject(slide_title: str, topic: str = "", max_words: int = 6) -> str:
    """Reduce a slide title + deck topic to a concrete, searchable visual subject.

    The deck topic is the anchor (so every image relates to the presentation subject);
    distinctive words from the slide title add slide-specific detail.
    """
    def keywords(text: str):
        words = re.findall(r"[A-Za-z][A-Za-z']+", text or "")
        return [w for w in words if w.lower() not in _GENERIC_WORDS and len(w) > 2]

    topic_words = keywords(topic)[:4]
    seen = {t.lower() for t in topic_words}
    title_words = [w for w in keywords(slide_title) if w.lower() not in seen]
    combined = topic_words + title_words[: max(0, max_words - len(topic_words))]
    if not combined:
        combined = keywords(slide_title) or keywords(topic) or ["business", "innovation"]
    return " ".join(combined[:max_words])


_pollinations_down_until = 0.0


def generate_with_huggingface(prompt: str) -> Optional[bytes]:
    """Open-source FLUX.1-schnell via Hugging Face Inference (needs a free HF_TOKEN)."""
    token = os.getenv("HF_TOKEN", "").strip() or os.getenv("HUGGINGFACE_API_KEY", "").strip()
    if not token:
        return None
    model = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    try:
        resp = requests.post(
            f"https://router.huggingface.co/hf-inference/models/{model}",
            headers={"Authorization": f"Bearer {token}", "Accept": "image/png"},
            json={"inputs": prompt[:400]},
            timeout=60,
        )
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image") and len(resp.content) > 3000:
            return resp.content
        print(f"[image_service] HuggingFace returned {resp.status_code}")
    except Exception as e:
        print(f"[image_service] HuggingFace request failed: {e}")
    return None


def fetch_from_openverse(query: str) -> Optional[bytes]:
    """Open-licensed (CC) photographs matching the subject from Openverse (no API key)."""
    if not query.strip():
        return None
    headers = {"User-Agent": "SlideCraftAI/2.0 (presentation generator)"}
    try:
        resp = requests.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": 8, "license_type": "commercial", "aspect_ratio": "wide", "mature": "false"},
            headers=headers, timeout=15,
        )
        if resp.status_code != 200:
            return None
        for item in resp.json().get("results", []):
            if (item.get("width") or 0) < 700:
                continue
            for url in (item.get("url"), item.get("thumbnail")):
                if not url:
                    continue
                try:
                    img = requests.get(url, headers=headers, timeout=12)
                    if img.status_code == 200 and len(img.content) > 8000 and img.headers.get("content-type", "").startswith("image"):
                        return img.content
                except Exception:
                    continue
    except Exception as e:
        print(f"[image_service] Openverse search failed: {e}")
    return None


def generate_with_cloud_diffusion(prompt: str, seed: Optional[int] = None) -> Optional[bytes]:
    """Generate image using Pollinations (open FLUX/SDXL). Skipped for 5 min after a failure."""
    global _pollinations_down_until
    if time.time() < _pollinations_down_until:
        return None
    if seed is None:
        seed = random.randint(1000, 9999999)
    encoded_prompt = urllib.parse.quote(prompt[:350])
    # 16:10 or 16:9 presentation friendly ratio
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=640&seed={seed}&nologo=true&model=flux"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 SlideCraftAI/2.0"
    }
    
    try:
        try:
            resp = requests.get(url, headers=headers, timeout=6)
        except Exception:
            resp = requests.get(url, headers=headers, verify=False, timeout=6)
        if resp and resp.status_code == 200 and len(resp.content) > 3000:
            return resp.content
    except Exception as e:
        print(f"[image_service] Cloud diffusion primary request failed: {e}")
        
    # Fallback to standard diffusion endpoint
    try:
        url_std = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=500&seed={seed}&nologo=true"
        try:
            resp = requests.get(url_std, headers=headers, timeout=5)
        except Exception:
            resp = requests.get(url_std, headers=headers, verify=False, timeout=5)
        if resp and resp.status_code == 200 and len(resp.content) > 3000:
            return resp.content
    except Exception as e:
        print(f"[image_service] Cloud diffusion fallback failed: {e}")

    _pollinations_down_until = time.time() + 300
    return None


def fetch_from_web_reference(slide_title: str, topic: str = "") -> Optional[bytes]:
    """Fetch verified high-resolution photograph matching the topic from Wikipedia/Wikimedia Commons."""
    from .web_search_service import fetch_web_reference, fetch_wikimedia_images

    headers = {
        "User-Agent": "SlideCraftAI/2.0 (slidecraft-presentation-agent; https://github.com/slidecraft)"
    }

    # 1. Search for direct slide title or topic reference
    queries = [f"{slide_title} {topic}".strip(), slide_title, topic]
    for q in queries:
        if not q:
            continue
        try:
            ref = fetch_web_reference(q)
            if ref and ref.get("image_url"):
                img_url = ref["image_url"]
                try:
                    resp = requests.get(img_url, headers=headers, timeout=5)
                except Exception:
                    resp = requests.get(img_url, headers=headers, verify=False, timeout=5)
                if resp and resp.status_code == 200 and len(resp.content) > 4000:
                    return resp.content

            # Try Wikimedia search
            wiki_imgs = fetch_wikimedia_images(q, limit=2)
            for wimg in wiki_imgs:
                if wimg.get("url"):
                    try:
                        resp = requests.get(wimg["url"], headers=headers, timeout=5)
                    except Exception:
                        resp = requests.get(wimg["url"], headers=headers, verify=False, timeout=5)
                    if resp and resp.status_code == 200 and len(resp.content) > 4000:
                        return resp.content
        except Exception as e:
            print(f"[image_service] Web reference image search failed for '{q}': {e}")

    return None


def generate_with_gemini_imagen(prompt: str, api_key: str = "") -> Optional[bytes]:
    """Generate image via Google Gemini / Vertex GenAI SDK if user provided an API key."""
    key = (api_key or "").strip() or GEMINI_API_KEY
    if not key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=key)
        # Try Imagen 3 model
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt[:400],
            config=dict(
                number_of_images=1,
                aspect_ratio="16:9",
                person_generation="ALLOW_ADULT",
            )
        )
        if result.generated_images and len(result.generated_images) > 0:
            img_bytes = result.generated_images[0].image.image_bytes
            return img_bytes
    except Exception as e:
        print(f"[image_service] Gemini Imagen generation failed: {e}")

    return None


def generate_with_openai_dalle(prompt: str, api_key: str = "") -> Optional[bytes]:
    """Generate widescreen presentation visual via OpenAI DALL-E 3 or gpt-image-1."""
    clean_key = (api_key or "").strip() if is_valid_api_key(api_key or "") else ""
    if clean_key and (not clean_key.startswith("sk-") or clean_key.startswith(("sk-ant-", "sk-or-"))):
        clean_key = ""
    key = clean_key or (OPENAI_API_KEY if is_valid_api_key(OPENAI_API_KEY) else "")
    if not key:
        return None

    img_model = (OPENAI_IMAGE_MODEL or "dall-e-3").strip()
    base = (OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    endpoint = f"{base}/images/generations"

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    if img_model.startswith("gpt-image"):
        payload = {
            "model": img_model,
            "prompt": prompt[:1500],
            "n": 1,
            "size": "1536x1024",
        }
    else:
        payload = {
            "model": img_model,
            "prompt": prompt[:1500],
            "n": 1,
            "size": "1792x1024",
            "quality": "standard",
            "response_format": "b64_json",
        }

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=45)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data and isinstance(data, list):
                first = data[0]
                if first.get("b64_json"):
                    return base64.b64decode(first["b64_json"])
                if first.get("url"):
                    dl = requests.get(first["url"], timeout=20)
                    if dl.status_code == 200 and len(dl.content) > 4000:
                        return dl.content
        else:
            print(f"[image_service] OpenAI image API HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[image_service] OpenAI DALL-E generation failed: {e}")

    return None


STOCK_PHOTO_CATEGORIES = {
    "network": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1544197150-b99a580bb7a8?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "ai": [
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "code": [
        "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "business": [
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "metrics": [
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "science": [
        "https://images.unsplash.com/photo-1507413245164-6160d8298b31?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1518152006812-edab29b069ac?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "space": [
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1506703719100-a0f3a48c0f86?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "history": [
        "https://images.unsplash.com/photo-1552832230-c0197dd311b5?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1564507592333-c60657eea523?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "health": [
        "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "nature": [
        "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1466611653911-95081537e5b7?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "food": [
        "https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "art": [
        "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1513364776144-60967b0f800f?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1541701494587-cb58502866ab?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "education": [
        "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "fitness": [
        "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1538805060514-97d9cc17730c?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "cyber": [
        "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1510511459019-5dda7724fd87?auto=format&fit=crop&w=1024&h=640&q=80"
    ],
    "quantum": [
        "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=1024&h=640&q=80",
        "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1024&h=640&q=80"
    ]
}

ALL_STOCK_PHOTOS = [url for urls in STOCK_PHOTO_CATEGORIES.values() for url in urls]

def fetch_from_unsplash_stock(query: str) -> Optional[bytes]:
    """Fetch high-resolution curated stock photograph matching keywords from Unsplash Cloud CDN."""
    q_lower = query.lower()
    selected_pool = ALL_STOCK_PHOTOS

    # Contextual category matching
    cat_rules = [
        ("history", ["history", "revolution", "rome", "roman", "ancient", "war", "century", "empire", "civilization"]),
        ("space", ["space", "astronomy", "galaxy", "cosmic", "orbit", "planet", "telescope", "solar"]),
        ("health", ["health", "medicine", "medical", "patient", "clinical", "hospital", "pharma", "doctor", "disease"]),
        ("nature", ["climate", "nature", "environment", "renewable", "green", "energy", "earth", "eco", "forest", "ocean"]),
        ("food", ["food", "cooking", "culinary", "bread", "baking", "sourdough", "chef", "wine", "recipe", "dish"]),
        ("art", ["art", "artist", "design", "music", "painting", "aesthetic", "sculpture", "film", "creative"]),
        ("education", ["education", "school", "learning", "student", "study", "classroom", "book", "university"]),
        ("fitness", ["fitness", "workout", "exercise", "running", "gym", "athlete", "sport", "muscle"]),
        ("quantum", ["quantum", "qubit", "physic", "particle", "atom"]),
        ("science", ["science", "biolog", "dna", "cell", "research", "chem", "lab"]),
        ("cyber", ["secur", "cyber", "lock", "shield", "protect"]),
        ("network", ["cloud", "server", "infra", "connect", "network"]),
        ("ai", ["ai", "neural", "model", "learn", "gpt", "robot", "intelligence"]),
        ("code", ["soft", "dev", "program", "api", "code"]),
        ("metrics", ["stat", "growth", "chart", "rate", "financ", "revenue", "invest", "market", "economy"]),
        ("business", ["business", "strategy", "office", "corporate", "team", "leader", "enterprise"])
    ]

    matched = False
    for cat_name, keywords in cat_rules:
        if any(k in q_lower for k in keywords):
            if cat_name in STOCK_PHOTO_CATEGORIES:
                selected_pool = STOCK_PHOTO_CATEGORIES[cat_name]
                matched = True
                break
    if not matched:
        return None

    seed_idx = abs(hash(query)) % len(selected_pool)
    target_url = selected_pool[seed_idx]
    try:
        resp = requests.get(target_url, timeout=6)
        if resp.status_code == 200 and len(resp.content) > 3000:
            return resp.content
    except Exception as e:
        print(f"[image_service] Unsplash fetch error: {e}")

    return None


def generate_procedural_neural_graphic(title: str, category: str = "") -> bytes:
    """Generate a high-resolution abstract procedural neural gradient artwork (offline guaranteed fallback)."""
    width, height = 1024, 640
    img = Image.new("RGB", (width, height), color=(15, 23, 42))  # Slate dark base
    draw = ImageDraw.Draw(img)

    # Radiant gradient orbs
    colors = [
        (99, 102, 241),   # Indigo
        (139, 92, 246),   # Purple
        (59, 130, 246),   # Sky blue
        (16, 185, 129),   # Emerald
        (236, 72, 153),   # Pink
    ]
    random.seed(abs(hash(title + category)) % 10000)
    c1 = random.choice(colors)
    c2 = random.choice(colors)

    # Draw ambient glowing circles
    for r in range(300, 0, -15):
        alpha = int(255 * (1 - r / 300) * 0.15)
        cx1, cy1 = int(width * 0.3), int(height * 0.45)
        draw.ellipse([cx1 - r, cy1 - r, cx1 + r, cy1 + r], fill=(c1[0], c1[1], c1[2]))
        
        cx2, cy2 = int(width * 0.7), int(height * 0.55)
        draw.ellipse([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=(c2[0], c2[1], c2[2]))

    # Neural network nodes and connecting synapses
    num_nodes = 24
    nodes = []
    for _ in range(num_nodes):
        nx = random.randint(100, width - 100)
        ny = random.randint(80, height - 80)
        nodes.append((nx, ny))

    # Connect nearby nodes
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            x1, y1 = nodes[i]
            x2, y2 = nodes[j]
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist < 190:
                width_line = 2 if dist < 100 else 1
                draw.line([(x1, y1), (x2, y2)], fill=(200, 220, 255), width=width_line)

    # Draw glowing node points
    for nx, ny in nodes:
        rad = random.randint(4, 9)
        draw.ellipse([nx - rad, ny - rad, nx + rad, ny + rad], fill=(255, 255, 255))
        draw.ellipse([nx - rad - 2, ny - rad - 2, nx + rad + 2, ny + rad + 2], outline=c1, width=1)

    # Overlay subtle grid
    for x in range(0, width, 64):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255), width=1)
    for y in range(0, height, 64):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255), width=1)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def generate_slide_image(
    slide_title: str,
    topic: str = "",
    category: str = "",
    style: str = "3d",
    custom_prompt: str = "",
    preferred_provider: str = "diffusion",
    api_key: str = ""
) -> Dict[str, Any]:
    """End-to-end unified image generation function with cloud neural models & robust fallback."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Pipeline-generated boilerplate prompts aren't user intent; derive a concrete subject instead.
    user_prompt = "" if custom_prompt.strip().lower().startswith("keynote visual asset") else custom_prompt
    subject = extract_visual_subject(slide_title, topic)
    prompt = build_neural_image_prompt(
        slide_title=slide_title,
        topic=topic,
        category="",
        style=style,
        custom_prompt=user_prompt or subject,
    )
    search_query = user_prompt.strip() or subject
    wants_photo = preferred_provider in ("stock", "internet", "web") or style == "photo"

    image_bytes = None
    provider_used = "cloud_diffusion"

    def photo_search() -> Optional[bytes]:
        data = fetch_from_web_reference(search_query, "")
        if data:
            return data
        return fetch_from_openverse(search_query)

    # 1. OpenAI DALL-E 3 / gpt-image-1 if explicitly requested or configured for AI generation
    valid_user_key = (api_key or "").strip() if is_valid_api_key(api_key or "") else ""
    is_openai_key = bool(
        (valid_user_key and valid_user_key.startswith("sk-") and not valid_user_key.startswith(("sk-ant-", "sk-or-")))
        or is_valid_api_key(OPENAI_API_KEY)
    )
    if preferred_provider in ("openai", "dalle", "dall-e-3") and is_openai_key:
        image_bytes = generate_with_openai_dalle(prompt, api_key=valid_user_key)
        if image_bytes:
            provider_used = "openai_dalle"

    # 2. Gemini Imagen if a Gemini key was provided
    is_gemini_key = bool(
        valid_user_key and not valid_user_key.startswith("grok_") and not valid_user_key.startswith("xai-") and not valid_user_key.startswith("sk-")
    )
    if not image_bytes and ((preferred_provider == "gemini" and is_gemini_key) or (is_gemini_key and not wants_photo)):
        image_bytes = generate_with_gemini_imagen(prompt, api_key=valid_user_key)
        if image_bytes:
            provider_used = "gemini_imagen"

    # 3. Real photographs on the topic when requested
    if not image_bytes and wants_photo:
        image_bytes = photo_search()
        if image_bytes:
            provider_used = "open_photo"

    # 4. Open-source diffusion models (FLUX via Hugging Face, then Pollinations)
    if not image_bytes:
        image_bytes = generate_with_huggingface(prompt)
        if image_bytes:
            provider_used = "huggingface_flux"
    if not image_bytes:
        image_bytes = generate_with_cloud_diffusion(prompt)
        if image_bytes:
            provider_used = "cloud_diffusion_flux"

    # 4b. OpenAI DALL-E fallback when AI generation was requested and open diffusion timed out
    if not image_bytes and is_openai_key and not wants_photo:
        image_bytes = generate_with_openai_dalle(prompt, api_key=api_key)
        if image_bytes:
            provider_used = "openai_dalle"

    # 4. Topic-matched open-licensed photos if diffusion is unavailable
    if not image_bytes and not wants_photo:
        image_bytes = photo_search()
        if image_bytes:
            provider_used = "open_photo"

    # 5. Category-matched curated stock (only when keywords match, never random)
    if not image_bytes:
        image_bytes = fetch_from_unsplash_stock(f"{subject} {slide_title}")
        if image_bytes:
            provider_used = "unsplash_cloud"

    # 6. Reliable Procedural Neural Graphic (guaranteed fallback)
    if not image_bytes:
        image_bytes = generate_procedural_neural_graphic(slide_title, category)
        provider_used = "procedural_neural"

    # Save to storage/images
    img_uuid = uuid.uuid4().hex[:12]
    filename = f"gen_{img_uuid}.jpg"
    file_path = IMAGES_DIR / filename
    
    with open(file_path, "wb") as f:
        f.write(image_bytes)

    caption = user_prompt if user_prompt else slide_title
    if len(caption) > 75:
        caption = caption[:72] + "..."

    return {
        "image_id": img_uuid,
        "filename": filename,
        "url": f"/api/images/{filename}",
        "local_path": str(file_path),
        "caption": caption,
        "prompt": prompt,
        "provider": provider_used,
        "style": style
    }
