"""Built-in presentation design themes with curated palettes, typography, and layout rules."""
from __future__ import annotations
from typing import Dict, Any, List
from pydantic import BaseModel

class ThemePreset(BaseModel):
    id: str
    name: str
    description: str
    dark_mode: bool
    bg_color: str        # Hex without # or with #
    card_bg: str
    text_primary: str
    text_secondary: str
    accent_primary: str
    accent_secondary: str
    badge_bg: str
    font_title: str
    font_body: str
    gradient: str

PRESET_THEMES: Dict[str, ThemePreset] = {
    "google-gemini": ThemePreset(
        id="google-gemini",
        name="Gemini Aura",
        description="Google AI-inspired deep slate with vibrant indigo & cyan glow",
        dark_mode=True,
        bg_color="0B0F19",
        card_bg="161D2F",
        text_primary="F8FAFC",
        text_secondary="94A3B8",
        accent_primary="6366F1",
        accent_secondary="06B6D4",
        badge_bg="1E293B",
        font_title="Segoe UI",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #0B0F19 0%, #161D2F 100%)"
    ),
    "modern-dark": ThemePreset(
        id="modern-dark",
        name="Modern Titanium",
        description="Sleek, obsidian dark mode with electric blue and emerald accents",
        dark_mode=True,
        bg_color="121316",
        card_bg="1C1E24",
        text_primary="F9FAFB",
        text_secondary="9CA3AF",
        accent_primary="3B82F6",
        accent_secondary="10B981",
        badge_bg="272A34",
        font_title="Segoe UI",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #121316 0%, #1C1E24 100%)"
    ),
    "corporate-clean": ThemePreset(
        id="corporate-clean",
        name="Executive Clean",
        description="Crisp editorial white with commanding royal navy and warm amber",
        dark_mode=False,
        bg_color="FFFFFF",
        card_bg="F8FAFC",
        text_primary="0F172A",
        text_secondary="475569",
        accent_primary="1E3A8A",
        accent_secondary="2563EB",
        badge_bg="EEF2F6",
        font_title="Segoe UI Semibold",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%)"
    ),
    "emerald-tech": ThemePreset(
        id="emerald-tech",
        name="Tech Emerald",
        description="Deep midnight green with high-tech mint and cyber glow",
        dark_mode=True,
        bg_color="022C22",
        card_bg="064E3B",
        text_primary="F0FDF4",
        text_secondary="A7F3D0",
        accent_primary="10B981",
        accent_secondary="34D399",
        badge_bg="043D2F",
        font_title="Segoe UI",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #022C22 0%, #064E3B 100%)"
    ),
    "sunset-gradient": ThemePreset(
        id="sunset-gradient",
        name="Sunset Horizon",
        description="Warm charcoal with vibrant rose, coral, and glowing amber",
        dark_mode=True,
        bg_color="18181B",
        card_bg="27272A",
        text_primary="FAFAFA",
        text_secondary="A1A1AA",
        accent_primary="F43F5E",
        accent_secondary="F59E0B",
        badge_bg="3F3F46",
        font_title="Segoe UI",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #18181B 0%, #27272A 100%)"
    ),
    "luxury-gold": ThemePreset(
        id="luxury-gold",
        name="Royal Onyx",
        description="Refined dark obsidian with warm champagne gold and ivory",
        dark_mode=True,
        bg_color="0F0F11",
        card_bg="1C1C22",
        text_primary="FDF8F6",
        text_secondary="D1D5DB",
        accent_primary="D97706",
        accent_secondary="F59E0B",
        badge_bg="292524",
        font_title="Georgia",
        font_body="Segoe UI",
        gradient="linear-gradient(135deg, #0F0F11 0%, #1C1C22 100%)"
    )
}

def get_theme(theme_id: str = "google-gemini") -> ThemePreset:
    return PRESET_THEMES.get(theme_id, PRESET_THEMES["google-gemini"])

def list_themes() -> List[Dict[str, Any]]:
    return [theme.model_dump() for theme in PRESET_THEMES.values()]
