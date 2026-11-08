"""Web Search & Reference Knowledge Service.

Fetches factual summaries, historical milestones, scientific concepts, and
high-resolution verified imagery from Wikipedia & Wikimedia Commons API.
Provides grounding data for Google Gemini & autonomous presentation synthesis.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
import requests
import urllib3

# Suppress SSL warnings in case system clock skew triggers cert validation warnings
urllib3.disable_warnings()

WIKI_HEADERS = {
    "User-Agent": "SlideCraftAI/2.0 (slidecraft-presentation-agent; https://github.com/slidecraft)"
}


def clean_query_term(query: str) -> str:
    """Extract clean search terms from a conversational user prompt."""
    if not query:
        return "Technology"

    # Strip parenthetical directives like "(Ground in verified web reference facts)"
    cleaned = re.sub(r'\([^)]*\)', ' ', query)

    # Take first line if multi-line prompt
    first_line = next((ln.strip() for ln in cleaned.splitlines() if ln.strip()), cleaned.strip())
    cleaned = first_line

    # Strip leading conversational request phrases
    cleaned = re.sub(
        r'^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?(?:generate|create|build|make|draft|design|prepare|develop|write|give\s+me|explain|present)\s+(?:an?\s+|the\s+)?(?:\d+[\s-]slide\s+)?(?:comprehensive\s+|detailed\s+|executive\s+|professional\s+|desired\s+)?(?:presentation|ppt|powerpoint|slide\s*deck|deck|slides|keynote|overview|report)?\s*(?:about|on|for|from|regarding|titled|covering|of)?\s*',
        '', cleaned, flags=re.IGNORECASE
    ).strip()

    # Strip trailing clauses like "with 8 slides", "with help of openai", "including ...", "focusing on ..."
    cleaned = re.sub(r'\s+(?:with|in|across)\s+\d+\s+slides?.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+(?:with\s+(?:the\s+)?help\s+of|using|via|powered\s+by)\s+(?:open\s*ai|gpt[\w\-]*|gemini|claude|ai).*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*(?:,|;|\b(?:including|covering|focusing\s+on|highlighting|comparing|with\s+sections\s+on))\s+.*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[\.\?!;:]+$', '', cleaned).strip()

    # Take up to 6 key words for Wikipedia search
    words = cleaned.split()
    if len(words) > 6:
        return " ".join(words[:6])
    return cleaned or "Technology"


def _parse_wiki_sections(full_extract: str, fallback_sentences: List[str]) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    """Parse MediaWiki plain-text extract into structured sections, timeline milestones, and quantitative facts."""
    sections: List[Dict[str, Any]] = []
    timeline_events: List[str] = []
    quant_facts: List[str] = []

    if not full_extract:
        for s in fallback_sentences:
            if re.search(r'\b(18\d\d|19\d\d|20\d\d)\b', s):
                timeline_events.append(s)
            if re.search(r'\b\d+(?:\.\d+)?(?:\s*%|\s*billion|\s*million|\s*trillion|\s*km|\s*GW|\s*MW|\s*x)\b', s, re.I):
                quant_facts.append(s)
        return sections, timeline_events[:6], quant_facts[:6]

    skip_headings = {"see also", "references", "external links", "further reading", "notes", "bibliography"}
    parts = re.split(r'\n==+\s*([^=\n]+?)\s*==+\n', full_extract)

    # parts[0] is intro, then pairs of (heading, body)
    for idx in range(1, len(parts) - 1, 2):
        heading = parts[idx].strip()
        body = parts[idx + 1].strip()
        if heading.lower() in skip_headings or not body:
            continue
        sents = [
            s.strip().rstrip(".") + "."
            for s in re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', body))
            if 25 <= len(s.strip()) <= 220
        ]
        if sents:
            sections.append({
                "heading": heading,
                "bullets": sents[:4],
            })
            for s in sents:
                if re.search(r'\b(18\d\d|19\d\d|20\d\d)\b', s):
                    timeline_events.append(s)
                if re.search(r'\b\d+(?:\.\d+)?(?:\s*%|\s*billion|\s*million|\s*trillion|\s*km|\s*GW|\s*MW|\s*x)\b', s, re.I):
                    quant_facts.append(s)

    return sections[:6], timeline_events[:6], quant_facts[:6]


def fetch_web_reference(query: str) -> Optional[Dict[str, Any]]:
    """Fetch factual overview, multi-section extracts, timeline facts, and verified image from Wikipedia."""
    term = clean_query_term(query)
    if not term:
        return None

    headers = {
        "User-Agent": "SlideCraftAI/2.0 (slidecraft-presentation-agent; https://github.com/slidecraft)"
    }

    try:
        # Fast direct lookup on Wikipedia REST API (Summary endpoint)
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
        s_resp = None
        try:
            s_resp = requests.get(summary_url, headers=headers, verify=False, timeout=(2.0, 3.0))
        except Exception:
            pass

        # If direct page summary didn't match or returned disambiguation, try a 1-result search
        if not s_resp or s_resp.status_code != 200 or s_resp.json().get("type") == "disambiguation":
            search_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&list=search"
                f"&srsearch={urllib.parse.quote(term)}&utf8=&format=json&srlimit=1"
            )
            try:
                search_resp = requests.get(search_url, headers=headers, verify=False, timeout=(2.0, 2.5))
                if search_resp and search_resp.status_code == 200:
                    items = search_resp.json().get("query", {}).get("search", [])
                    if items and items[0].get("title"):
                        matched_title = items[0]["title"]
                        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(matched_title)}"
                        s_resp = requests.get(summary_url, headers=headers, verify=False, timeout=(2.0, 3.0))
            except Exception:
                pass

        if not s_resp or s_resp.status_code != 200:
            return None

        s_data = s_resp.json()
        title = s_data.get("title", term)
        extract = s_data.get("extract", "")
        description = s_data.get("description", "")
        
        thumbnail_url = s_data.get("thumbnail", {}).get("source")
        original_img_url = s_data.get("originalimage", {}).get("source")
        page_url = s_data.get("content_urls", {}).get("desktop", {}).get("page", "")

        # Extract factual sentences from summary
        sentences = [
            s.strip().rstrip(".") + "."
            for s in re.split(r'\.\s+', extract)
            if len(s.strip()) > 15
        ]

        # Fetch deeper multi-section plain-text extract for richer topic-specific slides
        full_extract = ""
        try:
            ext_url = (
                f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
                f"&explaintext=1&exchars=5000&titles={urllib.parse.quote(title)}&format=json"
            )
            ext_resp = requests.get(ext_url, headers=headers, verify=False, timeout=(2.0, 2.8))
            if ext_resp and ext_resp.status_code == 200:
                pages = ext_resp.json().get("query", {}).get("pages", {})
                for _, pdata in pages.items():
                    full_extract = pdata.get("extract", "") or ""
                    break
        except Exception:
            pass

        sections, timeline_events, quant_facts = _parse_wiki_sections(full_extract, sentences)
        for sec in sections:
            for b in sec.get("bullets", []):
                if b not in sentences and len(sentences) < 14:
                    sentences.append(b)
        
        return {
            "query": term,
            "title": title,
            "description": description,
            "extract": extract,
            "key_facts": sentences[:12],
            "sections": sections,
            "timeline_events": timeline_events,
            "quantitative_facts": quant_facts,
            "thumbnail_url": thumbnail_url or original_img_url,
            "image_url": original_img_url or thumbnail_url,
            "source_url": page_url,
            "source": "Wikipedia & Wikimedia Commons"
        }

    except Exception as e:
        print(f"[web_search_service] Web reference fetch failed: {e}")
        return None


def fetch_wikimedia_images(query: str, limit: int = 4) -> List[Dict[str, str]]:
    """Search Wikimedia Commons for authentic high-res photos matching the topic."""
    term = clean_query_term(query)
    if not term:
        return []

    images = []
    try:
        url = (
            f"https://en.wikipedia.org/w/api.php?action=query&generator=search"
            f"&gsrsearch={urllib.parse.quote(term)}&gsrlimit={limit}&prop=pageimages"
            f"&pithumbsize=1024&format=json"
        )
        try:
            resp = requests.get(url, headers=WIKI_HEADERS, timeout=6)
        except Exception:
            resp = requests.get(url, headers=WIKI_HEADERS, verify=False, timeout=6)

        if resp and resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                thumb = pdata.get("thumbnail", {}).get("source")
                title = pdata.get("title", "")
                if thumb and not any(ext in thumb.lower() for ext in [".svg", ".ogg", ".webm"]):
                    images.append({
                        "title": title,
                        "url": thumb,
                        "source": "Wikimedia Commons"
                    })
    except Exception as e:
        print(f"[web_search_service] Wikimedia images fetch failed: {e}")

    return images
