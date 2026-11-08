"""Multi-Provider LLM Gateway for SlideCraft AI (OpenAI First-Class + Multi-LLM).

Unified connection layer supporting:
- OpenAI (GPT-4.1, GPT-4o, GPT-4o-mini, o3-mini, o4-mini) with Structured JSON & Reasoning Model support
- Google Gemini (Gemini 2.5 / 2.0 / 1.5)
- Grok / xAI (Grok-2)
- Anthropic Claude (Claude 3.5 Sonnet / Haiku)
- Custom OpenAI-compatible endpoints (OpenRouter, DeepSeek, Ollama, LocalAI, Azure OpenAI)

Features auto-detection by API key prefix, environment-key fallback, credential validation,
latency measurement, strict JSON enforcement, and resilient schema normalization.
"""
from __future__ import annotations

import json
import re
import time
from typing import Optional, Dict, Any, Tuple, List

import requests

from ..config import (
    OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL,
    GEMINI_API_KEY, TEXT_MODEL,
    GROK_API_KEY, GROK_BASE_URL, GROK_MODEL, GROK_API_KEY_NAME,
    DEMO_PLACEHOLDER_KEYS, is_valid_api_key
)

VALID_SLIDE_TYPES = {
    "title", "section", "bullets", "two_column", "image_text",
    "diagram", "chart", "table", "quote", "metrics", "conclusion",
    "timeline", "process",
}

SLIDE_TYPE_ALIASES = {
    "hero": "title",
    "cover": "title",
    "intro": "title",
    "introduction": "bullets",
    "comparison": "two_column",
    "compare": "two_column",
    "split": "two_column",
    "two-column": "two_column",
    "pros_cons": "two_column",
    "versus": "two_column",
    "kpi": "metrics",
    "kpis": "metrics",
    "stats": "metrics",
    "statistics": "metrics",
    "numbers": "metrics",
    "roadmap": "timeline",
    "steps": "timeline",
    "milestones": "timeline",
    "phases": "timeline",
    "matrix": "table",
    "grid": "table",
    "image": "image_text",
    "visual": "image_text",
    "text_image": "image_text",
    "image-text": "image_text",
    "summary": "conclusion",
    "takeaways": "conclusion",
    "closing": "conclusion",
    "cta": "conclusion",
    "divider": "section",
    "architecture": "diagram",
    "system_architecture": "diagram",
    "flowchart": "diagram",
    "blueprint": "diagram",
    "workflow": "diagram",
}


def _clean_user_key(api_key: Optional[str], hint: str = "auto") -> str:
    """Return stripped user key, ignoring expired demo or placeholder keys."""
    key = (api_key or "").strip()
    if not is_valid_api_key(key):
        return ""
    return key


def has_configured_llm(api_key: Optional[str] = None, provider: str = "auto") -> bool:
    """Return True if a usable user or environment API key is available."""
    key = _clean_user_key(api_key, hint=provider)
    return bool(key or OPENAI_API_KEY or GEMINI_API_KEY or GROK_API_KEY)


def detect_provider(api_key: str, hint: str = "auto") -> str:
    """Detect LLM provider from explicit hint, API key format, or configured environment keys."""
    clean_hint = (hint or "auto").lower().strip()
    key = _clean_user_key(api_key, hint=clean_hint)

    # Check key prefix overrides first to prevent sending mismatched keys to the wrong host
    if key:
        if key.startswith("AIza"):
            return "gemini"
        if key.startswith("sk-ant-"):
            return "claude"
        if key.startswith("sk-or-"):
            return "custom"
        if key.startswith("grok_") or key.startswith("xai-"):
            return "grok"
        if key.startswith("sk-"):
            return "openai" if clean_hint != "custom" else "custom"

    if clean_hint in ("openai", "gemini", "grok", "claude", "custom"):
        return clean_hint

    # Environment fallback order: OpenAI first, then Gemini, then Grok
    if OPENAI_API_KEY:
        return "openai"
    if GEMINI_API_KEY:
        return "gemini"
    if GROK_API_KEY:
        return "grok"
    return "openai"


def resolve_credentials(
    api_key: Optional[str] = None,
    provider: str = "auto",
    model: str = "",
    base_url: str = ""
) -> Tuple[str, str, str, str]:
    """Resolve (provider, effective_key, active_model, endpoint_base_url)."""
    clean_hint = (provider or "auto").lower().strip()
    user_key = _clean_user_key(api_key, hint=clean_hint)
    active_provider = detect_provider(user_key, hint=clean_hint)

    effective_key = user_key
    if not effective_key:
        if active_provider == "openai":
            effective_key = OPENAI_API_KEY
        elif active_provider == "gemini":
            effective_key = GEMINI_API_KEY
        elif active_provider == "grok":
            effective_key = GROK_API_KEY

        # Secondary fallback if hinted provider has no key at all, but another env key exists
        if not effective_key:
            if OPENAI_API_KEY:
                active_provider, effective_key = "openai", OPENAI_API_KEY
            elif GEMINI_API_KEY:
                active_provider, effective_key = "gemini", GEMINI_API_KEY
            elif GROK_API_KEY:
                active_provider, effective_key = "grok", GROK_API_KEY

    if active_provider == "openai":
        active_model = model or OPENAI_MODEL or "gpt-4o-mini"
        active_base = (base_url or OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
    elif active_provider == "gemini":
        active_model = model or TEXT_MODEL or "gemini-2.0-flash"
        active_base = ""
    elif active_provider == "grok":
        active_model = model or GROK_MODEL or "grok-2-latest"
        active_base = (GROK_BASE_URL or "https://api.x.ai/v1").rstrip("/")
    elif active_provider == "claude":
        active_model = model or "claude-3-5-sonnet-20241022"
        active_base = "https://api.anthropic.com/v1"
    else:
        # Custom / OpenRouter
        if effective_key.startswith("sk-or-") and not base_url:
            active_base = "https://openrouter.ai/api/v1"
        else:
            active_base = (base_url or OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        active_model = model or "gpt-4o-mini"

    return active_provider, effective_key, active_model, active_base


def _is_openai_reasoning_model(model_name: str) -> bool:
    m = (model_name or "").lower().strip()
    return any(m.startswith(prefix) for prefix in ("o1", "o3", "o4"))


def verify_llm_key(
    api_key: str,
    provider: str = "auto",
    model: str = "",
    base_url: str = ""
) -> Dict[str, Any]:
    """Test and verify an API key against its respective provider with latency measurement."""
    active_provider, clean_key, active_model, active_base = resolve_credentials(
        api_key=api_key, provider=provider, model=model, base_url=base_url
    )
    if not clean_key:
        return {
            "valid": False,
            "provider": active_provider,
            "model": active_model,
            "latency_ms": 0,
            "message": "No API key provided and no environment API key found (.env)."
        }

    start_time = time.time()

    try:
        if active_provider == "gemini":
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=clean_key)
            client.models.generate_content(
                model=active_model,
                contents="Ping. Respond with 'PONG' only.",
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                    temperature=0.1
                )
            )
            latency = int((time.time() - start_time) * 1000)
            return {
                "valid": True,
                "provider": "gemini",
                "model": active_model,
                "latency_ms": latency,
                "message": f"Successfully connected to Google Gemini ({active_model})."
            }

        elif active_provider in ("openai", "grok", "custom"):
            endpoint = f"{active_base}/chat/completions"
            is_reasoning = active_provider == "openai" and _is_openai_reasoning_model(active_model)

            body_dict: Dict[str, Any] = {
                "model": active_model,
                "messages": [{"role": "user", "content": "Reply with the single word PONG."}],
            }
            if is_reasoning:
                body_dict["max_completion_tokens"] = 32
            else:
                body_dict["max_tokens"] = 12
                body_dict["temperature"] = 0.1

            headers = {
                "Authorization": f"Bearer {clean_key}",
                "Content-Type": "application/json",
                "User-Agent": f"SlideCraft-AI/2.0 ({GROK_API_KEY_NAME})"
            }

            resp = requests.post(endpoint, json=body_dict, headers=headers, timeout=20)
            latency = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                provider_label = "OpenAI" if active_provider == "openai" else active_provider.upper()
                return {
                    "valid": True,
                    "provider": active_provider,
                    "model": active_model,
                    "latency_ms": latency,
                    "message": f"Successfully connected to {provider_label} ({active_model})."
                }
            else:
                err_msg = resp.text[:300]
                try:
                    err_msg = resp.json().get("error", {}).get("message", err_msg)
                except Exception:
                    pass
                return {
                    "valid": False,
                    "provider": active_provider,
                    "model": active_model,
                    "latency_ms": latency,
                    "message": f"Authentication failed (HTTP {resp.status_code}): {err_msg}"
                }

        elif active_provider == "claude":
            endpoint = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": active_model,
                "max_tokens": 12,
                "messages": [{"role": "user", "content": "Ping"}]
            }
            headers = {
                "x-api-key": clean_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            latency = int((time.time() - start_time) * 1000)
            if resp.status_code == 200:
                return {
                    "valid": True,
                    "provider": "claude",
                    "model": active_model,
                    "latency_ms": latency,
                    "message": f"Successfully connected to Anthropic Claude ({active_model})."
                }
            err_msg = resp.text[:300]
            try:
                err_msg = resp.json().get("error", {}).get("message", err_msg)
            except Exception:
                pass
            return {
                "valid": False,
                "provider": "claude",
                "model": active_model,
                "latency_ms": latency,
                "message": f"Authentication failed (HTTP {resp.status_code}): {err_msg}"
            }

    except Exception as e:
        return {
            "valid": False,
            "provider": active_provider,
            "model": active_model or "default",
            "latency_ms": int((time.time() - start_time) * 1000),
            "message": f"Connection error: {str(e)}"
        }

    return {
        "valid": False,
        "provider": active_provider,
        "model": "unknown",
        "latency_ms": 0,
        "message": f"Unsupported provider: {active_provider}"
    }


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Extract and parse valid JSON from LLM output, handling markdown fences and stray text."""
    if not raw:
        return None
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"slides": parsed}
    except Exception:
        m = re.search(r'(\{.*\})', cleaned, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
    return None


def _flatten_str_list(items: Any) -> List[str]:
    """Normalize a list of strings or dicts into clean bullet/column strings."""
    if not items:
        return []
    if isinstance(items, str):
        return [s.strip() for s in items.split("\n") if s.strip()]
    if not isinstance(items, list):
        return []

    out: List[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            phase = str(item.get("phase") or item.get("step") or item.get("date") or "").strip()
            head = str(item.get("title") or item.get("heading") or item.get("name") or item.get("label") or "").strip()
            desc = str(item.get("desc") or item.get("description") or item.get("detail") or item.get("text") or "").strip()
            if phase and head and desc:
                out.append(f"{phase} — {head}: {desc}")
            elif phase and desc:
                out.append(f"{phase}: {desc}")
            elif head and desc:
                out.append(f"{head}: {desc}")
            elif head or desc or phase:
                out.append(head or desc or phase)
    return out


def normalize_slide_payload(raw_slide: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    """Normalize an LLM-generated slide dictionary so it strictly conforms to AISlide."""
    if not isinstance(raw_slide, dict):
        return {
            "type": "bullets",
            "category": "KEY INSIGHTS",
            "title": f"Slide {index + 1}",
            "subtitle": "",
            "bullets": [str(raw_slide)],
            "notes": ""
        }

    raw_type = str(
        raw_slide.get("type")
        or raw_slide.get("layout")
        or raw_slide.get("slide_type")
        or ("title" if index == 0 else "bullets")
    ).lower().strip()
    stype = SLIDE_TYPE_ALIASES.get(raw_type, raw_type)

    title = str(
        raw_slide.get("title")
        or raw_slide.get("heading")
        or raw_slide.get("headline")
        or f"Slide {index + 1}"
    ).strip()
    subtitle = str(
        raw_slide.get("subtitle")
        or raw_slide.get("subheadline")
        or raw_slide.get("summary")
        or ""
    ).strip()
    category = str(
        raw_slide.get("category")
        or raw_slide.get("badge")
        or raw_slide.get("tag")
        or ("EXECUTIVE KEYNOTE" if index == 0 else "STRATEGIC INSIGHTS")
    ).strip().upper()

    bullets = _flatten_str_list(
        raw_slide.get("bullets")
        or raw_slide.get("points")
        or raw_slide.get("items")
        or raw_slide.get("key_points")
    )

    # Support timeline array returned by LLMs
    timeline_items = _flatten_str_list(raw_slide.get("timeline") or raw_slide.get("phases") or raw_slide.get("steps"))
    if timeline_items and not bullets:
        bullets = timeline_items

    left = _flatten_str_list(raw_slide.get("left") or raw_slide.get("left_column") or raw_slide.get("column_left"))
    right = _flatten_str_list(raw_slide.get("right") or raw_slide.get("right_column") or raw_slide.get("column_right"))

    # Normalize stats / KPIs
    raw_stats = raw_slide.get("stats") or raw_slide.get("metrics") or raw_slide.get("kpis") or []
    stats: List[Dict[str, str]] = []
    if isinstance(raw_stats, list):
        for st in raw_stats:
            if isinstance(st, dict):
                val = str(st.get("value") or st.get("stat") or st.get("number") or "").strip()
                lbl = str(st.get("label") or st.get("name") or st.get("metric") or st.get("title") or "").strip()
                chg = str(st.get("change") or st.get("delta") or st.get("trend") or st.get("context") or "").strip()
                if val and lbl:
                    stats.append({"value": val, "label": lbl, "change": chg})

    # Normalize table
    table_obj = None
    raw_table = raw_slide.get("table")
    if isinstance(raw_table, dict):
        headers = [str(h).strip() for h in (raw_table.get("headers") or raw_table.get("columns") or []) if str(h).strip()]
        raw_rows = raw_table.get("rows") or []
        rows: List[List[str]] = []
        if headers and isinstance(raw_rows, list):
            for r in raw_rows:
                if isinstance(r, list):
                    row_cells = [str(c).strip() for c in r[:len(headers)]]
                    while len(row_cells) < len(headers):
                        row_cells.append("")
                    rows.append(row_cells)
                elif isinstance(r, dict):
                    rows.append([str(r.get(h, "")).strip() for h in headers])
        if headers and rows:
            table_obj = {"headers": headers, "rows": rows}

    quote = str(raw_slide.get("quote") or raw_slide.get("statement") or "").strip()
    notes = str(
        raw_slide.get("notes")
        or raw_slide.get("speaker_notes")
        or raw_slide.get("presenter_notes")
        or ""
    ).strip()
    image_url = str(raw_slide.get("image_url") or "").strip()
    image_caption = str(raw_slide.get("image_caption") or raw_slide.get("caption") or "").strip()

    # Preserve custom image generation prompt if LLM provided one
    img_prompt = str(
        raw_slide.get("image_prompt")
        or raw_slide.get("visual_prompt")
        or (
            raw_slide.get("visual", {}).get("image", {}).get("prompt", "")
            if isinstance(raw_slide.get("visual"), dict) and isinstance(raw_slide.get("visual", {}).get("image"), dict)
            else ""
        )
    ).strip()

    visual_obj: Dict[str, Any] = {"kind": "none"}
    if img_prompt:
        visual_obj = {"kind": "image", "image": {"prompt": img_prompt, "stock_query": img_prompt[:80], "prefer_stock": False}}

    # Check if slide has an explicit diagram / architecture specification
    raw_diag = (
        raw_slide.get("diagram")
        or raw_slide.get("architecture")
        or (raw_slide.get("visual", {}).get("diagram") if isinstance(raw_slide.get("visual"), dict) else None)
    )
    if raw_diag or stype == "diagram":
        try:
            from .architecture_engine import normalize_diagram_dict, synthesize_diagram_spec
            if isinstance(raw_diag, dict):
                diag_spec = normalize_diagram_dict(raw_diag, fallback_topic=title or "System Architecture")
            else:
                diag_spec = synthesize_diagram_spec(title or "System Architecture", bullets=bullets)
            visual_obj = {
                "kind": "architecture",
                "diagram": diag_spec.model_dump(),
            }
            if img_prompt:
                visual_obj["image"] = {"prompt": img_prompt, "stock_query": img_prompt[:80], "prefer_stock": False}
            stype = "diagram"
        except Exception as diag_err:
            print(f"[LLMGateway] Diagram normalization warning: {diag_err}")

    # Validate & reconcile slide type against populated content
    if stype not in VALID_SLIDE_TYPES:
        if index == 0:
            stype = "title"
        elif table_obj:
            stype = "table"
        elif stats:
            stype = "metrics"
        elif left and right:
            stype = "two_column"
        elif quote and not bullets:
            stype = "quote"
        else:
            stype = "bullets"

    # Ensure layout-specific fields aren't empty if the LLM chose a specialized layout
    if stype == "two_column" and (not left or not right) and len(bullets) >= 2:
        mid = max(1, len(bullets) // 2)
        left = left or bullets[:mid]
        right = right or bullets[mid:]
    elif stype == "metrics" and not stats and bullets:
        stype = "bullets"
    elif stype == "table" and not table_obj and bullets:
        stype = "bullets"
    elif stype in ("bullets", "timeline", "conclusion", "image_text") and not bullets:
        if left or right:
            bullets = left + right
        elif subtitle:
            bullets = [subtitle]

    return {
        "type": stype,
        "category": category,
        "title": title,
        "subtitle": subtitle,
        "bullets": bullets,
        "left": left,
        "right": right,
        "stats": stats,
        "quote": quote,
        "visual": visual_obj,
        "table": table_obj,
        "image_url": image_url,
        "image_caption": image_caption,
        "notes": notes or f"Present the key takeaways for '{title}'."
    }


def normalize_outline_payload(data: Dict[str, Any], fallback_title: str = "Executive Presentation") -> Optional[Dict[str, Any]]:
    """Normalize top-level LLM JSON output into a valid AIOutline dict."""
    if not isinstance(data, dict):
        return None

    # Unwrap nested wrappers like {"presentation": {...}} or {"outline": {...}}
    for wrapper_key in ("presentation", "outline", "deck"):
        if wrapper_key in data and isinstance(data[wrapper_key], dict) and "slides" in data[wrapper_key]:
            data = data[wrapper_key]
            break

    raw_slides = data.get("slides")
    if not isinstance(raw_slides, list) or len(raw_slides) == 0:
        return None

    normalized_slides = [normalize_slide_payload(s, idx) for idx, s in enumerate(raw_slides)]
    # Guarantee first slide is title layout unless caller requested single slide
    if len(normalized_slides) > 1 and normalized_slides[0]["type"] not in ("title",):
        normalized_slides[0]["type"] = "title"

    deck_title = str(
        data.get("title")
        or data.get("deck_title")
        or data.get("presentation_title")
        or normalized_slides[0].get("title")
        or fallback_title
    ).strip()
    deck_subtitle = str(
        data.get("subtitle")
        or data.get("deck_subtitle")
        or data.get("tagline")
        or normalized_slides[0].get("subtitle")
        or ""
    ).strip()

    return {
        "title": deck_title,
        "subtitle": deck_subtitle,
        "slides": normalized_slides
    }


def _call_free_openai_relay(
    system_instruction: str,
    user_prompt: str,
    temperature: float = 0.65
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """
    Zero-key OpenAI-compatible cloud relay fallback using Pollinations OpenAI endpoint
    (backed by GPT-4o-mini). Used when no paid user API key is configured so every prompt
    still receives genuine OpenAI structured JSON synthesis.
    Can be disabled in unit tests via DISABLE_FREE_LLM_RELAY=1.
    """
    import os
    if os.getenv("DISABLE_FREE_LLM_RELAY", "").strip() in ("1", "true", "yes"):
        return None, "", ""

    if "json" not in system_instruction.lower() and "json" not in user_prompt.lower():
        user_prompt = f"{user_prompt}\n\nRespond ONLY with a valid JSON object."

    endpoint = "https://text.pollinations.ai/openai"
    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=28,
        )
        if resp.status_code == 200:
            res_body = resp.json()
            choices = res_body.get("choices") or []
            if choices:
                raw = choices[0].get("message", {}).get("content", "")
                parsed = _extract_json(raw)
                if parsed:
                    return parsed, "openai", "gpt-4o-mini-relay"
            parsed = _extract_json(resp.text)
            if parsed:
                return parsed, "openai", "gpt-4o-mini-relay"
    except Exception as e:
        print(f"[LLMGateway] OpenAI cloud relay fallback notice: {e}")

    return None, "", ""


def call_llm_json_with_meta(
    system_instruction: str,
    user_prompt: str,
    api_key: Optional[str] = None,
    provider: str = "auto",
    model: str = "",
    base_url: str = "",
    temperature: float = 0.7
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """Execute an LLM chat request demanding JSON output, returning (parsed_dict, provider_used, model_used)."""
    active_provider, effective_key, active_model, active_base = resolve_credentials(
        api_key=api_key, provider=provider, model=model, base_url=base_url
    )

    if not effective_key:
        return _call_free_openai_relay(system_instruction, user_prompt, temperature=temperature)

    if "json" not in system_instruction.lower() and "json" not in user_prompt.lower():
        user_prompt = f"{user_prompt}\n\nRespond with a valid JSON object."

    if active_provider == "gemini":
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=effective_key)
            models_to_try = [active_model, TEXT_MODEL, "gemini-2.0-flash", "gemini-1.5-flash"]
            models_to_try = [m for m in dict.fromkeys(models_to_try) if m]

            for m in models_to_try:
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            temperature=temperature,
                        )
                    )
                    parsed = _extract_json(resp.text)
                    if parsed:
                        return parsed, "gemini", m
                except Exception as model_err:
                    print(f"[LLMGateway] Gemini model '{m}' warning: {model_err}")
                    continue
        except Exception as e:
            print(f"[LLMGateway] Gemini execution error: {e}")

    elif active_provider in ("openai", "grok", "custom"):
        endpoint = f"{active_base}/chat/completions"
        if active_provider == "openai":
            models_to_try = [active_model, OPENAI_MODEL, "gpt-4o-mini", "gpt-4o"]
        else:
            models_to_try = [active_model]
        models_to_try = [m for m in dict.fromkeys(models_to_try) if m]

        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json",
            "User-Agent": f"SlideCraft-AI/2.0 ({GROK_API_KEY_NAME})"
        }

        for m in models_to_try:
            try:
                is_reasoning = active_provider == "openai" and _is_openai_reasoning_model(m)
                sys_role = "developer" if (is_reasoning and not m.startswith("o1-mini")) else "system"
                messages = (
                    [{"role": "user", "content": f"{system_instruction}\n\n{user_prompt}"}]
                    if m.startswith("o1-mini")
                    else [
                        {"role": sys_role, "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ]
                )

                body_dict: Dict[str, Any] = {
                    "model": m,
                    "messages": messages,
                }
                if not is_reasoning:
                    body_dict["temperature"] = temperature
                if not m.startswith("o1-mini"):
                    body_dict["response_format"] = {"type": "json_object"}

                resp = requests.post(endpoint, json=body_dict, headers=headers, timeout=55)
                if resp.status_code != 200 and "response_format" in body_dict:
                    # Retry once without response_format for models/endpoints that reject json_object
                    fallback_body = {k: v for k, v in body_dict.items() if k != "response_format"}
                    resp = requests.post(endpoint, json=fallback_body, headers=headers, timeout=55)

                if resp.status_code == 200:
                    res_body = resp.json()
                    raw = res_body["choices"][0]["message"]["content"]
                    parsed = _extract_json(raw)
                    if parsed:
                        return parsed, active_provider, m
                else:
                    err_snippet = resp.text[:250]
                    print(f"[LLMGateway] {active_provider} ({m}) HTTP {resp.status_code}: {err_snippet}")
                    # Stop trying sibling models on auth failure (401/403) or insufficient quota
                    if resp.status_code in (401, 403):
                        break
            except Exception as e:
                print(f"[LLMGateway] {active_provider} ({m}) execution error: {e}")

    elif active_provider == "claude":
        try:
            endpoint = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": active_model,
                "max_tokens": 4096,
                "system": system_instruction + "\nYou must reply ONLY with valid raw JSON.",
                "messages": [{"role": "user", "content": user_prompt}]
            }
            headers = {
                "x-api-key": effective_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=45)
            if resp.status_code == 200:
                res_body = resp.json()
                raw = res_body["content"][0]["text"]
                parsed = _extract_json(raw)
                if parsed:
                    return parsed, "claude", active_model
            else:
                print(f"[LLMGateway] Claude HTTP {resp.status_code}: {resp.text[:250]}")
        except Exception as e:
            print(f"[LLMGateway] Claude execution error: {e}")

    # Final fallback: try the OpenAI-compatible cloud relay if the configured key failed
    return _call_free_openai_relay(system_instruction, user_prompt, temperature=temperature)


def call_llm_json(
    system_instruction: str,
    user_prompt: str,
    api_key: Optional[str] = None,
    provider: str = "auto",
    model: str = "",
    base_url: str = "",
    temperature: float = 0.7
) -> Optional[Dict[str, Any]]:
    """Backward-compatible wrapper returning only the parsed JSON dictionary."""
    parsed, _, _ = call_llm_json_with_meta(
        system_instruction=system_instruction,
        user_prompt=user_prompt,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        temperature=temperature
    )
    return parsed
