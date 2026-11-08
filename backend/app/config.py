"""Runtime configuration loaded from .env files."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Project .env wins, then backend .env, then the user's home .env as a fallback.
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(Path.home() / ".env")

# Known expired/placeholder demo keys that should not override valid env keys or OpenAI fallback
DEMO_PLACEHOLDER_KEYS = {
    "grok_46580b20988b83a360d82699b8e2cf39_a6b20bd9ec170814e3a38176c18d669f51f80a893d345a2cf0fbeeda1798e256",
    "your_api_key_here",
    "your-api-key-here",
    "your_openai_api_key_here",
    "your_gemini_api_key_here",
    "sk-your-api-key-here",
    "replace_me",
}


def is_valid_api_key(val: str) -> bool:
    """Return True only if val looks like a real API key and not a dummy placeholder."""
    if not val:
        return False
    clean = val.strip()
    low = clean.lower()
    if clean in DEMO_PLACEHOLDER_KEYS or low in DEMO_PLACEHOLDER_KEYS:
        return False
    if len(clean) < 10:
        return False
    if any(tok in low for tok in ("your_api", "your-api", "your_key", "your-key", "api_key_here", "apikeyhere", "placeholder", "replace_with", "insert_your", "example_key", "xxxx")):
        return False
    return True


_raw_gemini = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_API_KEY = _raw_gemini if is_valid_api_key(_raw_gemini) else ""

_raw_openai = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_API_KEY = _raw_openai if is_valid_api_key(_raw_openai) else ""
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3").strip() or "dall-e-3"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"

_raw_grok = (os.getenv("GROK_API_KEY", "") or os.getenv("XAI_API_KEY", "") or os.getenv("AIPPTMAKER_API_KEY", "")).strip()
GROK_API_KEY = _raw_grok if is_valid_api_key(_raw_grok) else ""
GROK_API_KEY_NAME = os.getenv("GROK_API_KEY_NAME", "aipptmaker")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-2-latest")

TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-2.0-flash")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-3.0-generate-002")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
QA_MIN_SCORE = float(os.getenv("QA_MIN_SCORE", "8"))
QA_MAX_RETRIES = int(os.getenv("QA_MAX_RETRIES", "2"))

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BACKEND_DIR / "storage"))
TEMPLATES_DIR = STORAGE_DIR / "templates"
LOGOS_DIR = STORAGE_DIR / "logos"
IMAGES_DIR = STORAGE_DIR / "images"
DECKS_DIR = STORAGE_DIR / "decks"
CACHE_DIR = STORAGE_DIR / "cache"
for _d in (TEMPLATES_DIR, LOGOS_DIR, IMAGES_DIR, DECKS_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Graphviz is often installed without being added to PATH for the current session.
_GV_BIN = Path(r"C:\Program Files\Graphviz\bin")
if _GV_BIN.exists() and str(_GV_BIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_GV_BIN) + os.pathsep + os.environ.get("PATH", "")


def graphviz_available() -> bool:
    return shutil.which("dot") is not None


def ai_available() -> bool:
    return bool(OPENAI_API_KEY or GEMINI_API_KEY or GROK_API_KEY)
