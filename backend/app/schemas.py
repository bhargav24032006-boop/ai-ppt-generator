"""Pydantic models shared by the AI layer, the deck builder and the API.

`AI*` models are sent to Gemini as response schemas, so they only contain fields
the model should fill. App-level models extend them with runtime fields.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional, List, Dict, Any

from pydantic import BaseModel, Field

SlideType = Literal[
    "title", "section", "bullets", "two_column", "image_text",
    "diagram", "chart", "table", "quote", "metrics", "conclusion",
    "timeline", "process",
]
VisualKind = Literal[
    "architecture", "flowchart", "sequence", "timeline", "hierarchy",
    "cycle", "mindmap", "image", "chart", "none",
]
DIAGRAM_KINDS = {"architecture", "flowchart", "sequence", "timeline", "hierarchy", "cycle", "mindmap"}
NodeShape = Literal["box", "process", "database", "cloud", "user", "queue", "device", "decision", "start_end"]


# ---------------------------------------------------------------- AI schema
class DiagramNode(BaseModel):
    id: str
    label: str
    shape: NodeShape = "box"
    cluster: str = ""


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class DiagramCluster(BaseModel):
    id: str
    label: str


class DiagramSpec(BaseModel):
    direction: Literal["LR", "TB"] = "LR"
    clusters: list[DiagramCluster] = Field(default_factory=list)
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)


class ImageSpec(BaseModel):
    prompt: str = ""
    stock_query: str = ""
    prefer_stock: bool = False


class ChartSeries(BaseModel):
    name: str
    values: list[float]


class ChartSpec(BaseModel):
    kind: Literal["bar", "line", "pie"] = "bar"
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)


class TableSpec(BaseModel):
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class StatItem(BaseModel):
    value: str
    label: str
    change: str = ""


class Visual(BaseModel):
    kind: VisualKind = "none"
    diagram: Optional[DiagramSpec] = None
    image: Optional[ImageSpec] = None
    chart: Optional[ChartSpec] = None


class AISlide(BaseModel):
    type: SlideType = "bullets"
    category: str = ""             # Badge/Category tag e.g. "MARKET OVERVIEW"
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = Field(default_factory=list)
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)
    stats: list[StatItem] = Field(default_factory=list)
    quote: str = ""
    visual: Visual = Field(default_factory=Visual)
    table: Optional[TableSpec] = None
    image_url: str = ""
    image_caption: str = ""
    notes: str = ""                # Presenter speaker notes


class AIOutline(BaseModel):
    title: str
    subtitle: str = ""
    slides: list[AISlide]


class QAResult(BaseModel):
    relevance: float = 0
    correctness: float = 0
    readability: float = 0
    style: float = 0
    artifacts_free: float = 0
    overall: float = 0
    issues: list[str] = Field(default_factory=list)


# --------------------------------------------------------------- App models
class Slide(AISlide):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    image_id: str = ""          # generated / stock / uploaded image in storage/images
    image_credit: str = ""
    qa: Optional[QAResult] = None


class Outline(BaseModel):
    title: str
    subtitle: str = ""
    theme_id: str = "google-gemini"
    template_id: str = ""
    slides: list[Slide]


class Branding(BaseModel):
    college: str = ""
    department: str = ""
    presenter: str = ""
    guide: str = ""
    logo_id: str = ""
    logo_position: Literal["top-right", "top-left", "bottom-right", "bottom-left"] = "top-right"
    show_footer: bool = True


class ThemeInfo(BaseModel):
    colors: dict[str, str] = Field(default_factory=dict)   # dk1, lt1, accent1..6 -> hex
    major_font: str = "Calibri Light"
    minor_font: str = "Calibri"
    dark_background: bool = False


class LayoutInfo(BaseModel):
    index: int
    master_index: int
    name: str
    role: str
    placeholders: list[str]


class TemplateInfo(BaseModel):
    id: str
    filename: str
    slide_width: int
    slide_height: int
    mode: Literal["layouts", "prototype"]
    layouts: list[LayoutInfo]
    theme: ThemeInfo
    source_slide_count: int


# ------------------------------------------------------------ Chat & API requests
class FileAttachment(BaseModel):
    id: str
    filename: str
    file_type: str                   # "document", "template", "image", "other"
    format: str = ""
    extracted_text: str = ""
    template_id: str = ""
    template_info: Optional[Dict[str, Any]] = None
    image_id: str = ""
    saved_filename: str = ""
    url: str = ""
    dimensions: Optional[Dict[str, int]] = None
    summary: str = ""


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    attachments: list[FileAttachment] = Field(default_factory=list)


class ChatRequest(BaseModel):
    prompt: str
    history: list[ChatHistoryItem] = Field(default_factory=list)
    attachments: list[FileAttachment] = Field(default_factory=list)
    theme_id: str = "google-gemini"
    template_id: str = ""
    slide_count: int = 8
    audience: str = "general professional"
    tone: str = "engaging and authoritative"
    api_key: str = ""
    provider: str = "auto"
    model: str = ""
    base_url: str = ""
    current_deck: Optional[Outline] = None
    auto_generate_images: bool = True
    image_style: str = "3d"
    preferred_image_provider: str = "diffusion"



class ChatResponse(BaseModel):
    message: str
    deck: Optional[Outline] = None
    file_id: Optional[str] = None
    download_url: Optional[str] = None
    theme_id: str = "google-gemini"
    template_id: str = ""
    modified_slide_index: Optional[int] = None
    provider_used: str = ""
    model_used: str = ""
    status: str = "success"



class OutlineRequest(BaseModel):
    topic: str
    slide_count: int = Field(8, ge=3, le=30)
    audience: str = "college students and faculty"
    tone: str = "academic, clear"
    language: str = "English"
    source_text: str = ""
    template_id: str = ""
    theme_id: str = "google-gemini"
    extra_instructions: str = ""
    api_key: str = ""
    provider: str = "auto"
    model: str = ""
    base_url: str = ""


class VisualRequest(BaseModel):
    slide: Slide
    topic: str = ""
    template_id: str = ""
    image_style: str = "flat vector illustration"
    quality_check: bool = True
    force_kind: Optional[VisualKind] = None
    feedback: str = ""


class DiagramPreviewRequest(BaseModel):
    kind: VisualKind = "architecture"
    diagram: DiagramSpec
    template_id: str = ""


class GenerateRequest(BaseModel):
    outline: Outline
    template_id: str = ""
    theme_id: str = "google-gemini"
    branding: Branding = Field(default_factory=Branding)


class GenerateImageRequest(BaseModel):
    slide_title: str = ""
    topic: str = ""
    category: str = ""
    style: str = "3d"
    custom_prompt: str = ""
    preferred_provider: str = "diffusion"
    api_key: str = ""
    slide_id: str = ""


class GenerateImageResponse(BaseModel):
    image_id: str
    filename: str
    url: str
    caption: str
    prompt: str
    provider: str
    style: str
    slide_id: str = ""


class ExportRequest(BaseModel):
    deck: Outline
    theme_id: str = "google-gemini"
    template_id: str = ""


class ReverseEngineerRequest(BaseModel):
    template_id: str = ""


class NeuralTrainRequest(BaseModel):
    template_id: str = ""
    epochs: int = 30
    learning_rate: float = 0.06


class GenerateFromTemplateRequest(BaseModel):
    template_id: str
    topic: str
    prompt: Optional[str] = ""
    slide_count: int = 8
    audience: str = "general professional"
    tone: str = "engaging and authoritative"
    theme_id: str = "google-gemini"
    api_key: str = ""
    provider: str = "auto"
    model: str = ""
    base_url: str = ""
    image_style: str = "3d"
    image_source: str = "internet"
    auto_generate_images: bool = True


class VerifyKeyRequest(BaseModel):
    api_key: str = ""
    provider: str = "auto"
    model: str = ""
    base_url: str = ""


class VerifyKeyResponse(BaseModel):
    valid: bool
    provider: str
    model: str
    latency_ms: int = 0
    message: str


class SlideImageInfo(BaseModel):
    slide_index: int
    filename: str
    url: str
    width: int = 1920
    height: int = 1080


class ExportSlidesResponse(BaseModel):
    file_id: str
    slides: list[SlideImageInfo]
    count: int
    zip_url: str

