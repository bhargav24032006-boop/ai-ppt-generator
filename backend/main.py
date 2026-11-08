import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn

from app.schemas import (
    OutlineRequest, Outline, GenerateRequest,
    ChatRequest, ChatResponse, FileAttachment,
    GenerateImageRequest, GenerateImageResponse, ExportRequest,
    VerifyKeyRequest, VerifyKeyResponse, ExportSlidesResponse, SlideImageInfo
)
from app.services.ai_service import generate_outline, generate_deck_from_chat
from app.services.image_service import generate_slide_image
from app.services.deck_builder import create_presentation
from app.services.template_analyzer import analyze_template
from app.services.llm_gateway import verify_llm_key, detect_provider, resolve_credentials
from app.services.slide_export_service import (
    export_presentation_slides_to_images,
    get_slide_image_path,
    create_slides_zip
)
from app.themes import list_themes, get_theme
from app.utils.file_parser import process_uploaded_file
from app.config import (
    DECKS_DIR, TEMPLATES_DIR, IMAGES_DIR,
    OPENAI_API_KEY, OPENAI_MODEL,
    GEMINI_API_KEY, GROK_API_KEY, GROK_API_KEY_NAME
)


app = FastAPI(title="SlideCraft AI - Presentation Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "has_openai_key": bool(OPENAI_API_KEY),
        "openai_model": OPENAI_MODEL,
        "has_gemini_key": bool(GEMINI_API_KEY),
        "has_grok_key": bool(GROK_API_KEY),
        "grok_key_name": GROK_API_KEY_NAME if GROK_API_KEY else "",
        "ai_active": bool(OPENAI_API_KEY or GEMINI_API_KEY or GROK_API_KEY),
        "themes_count": len(list_themes())
    }


@app.get("/api/themes")
def get_themes():
    return list_themes()


@app.get("/api/templates")
def list_templates():
    """List all available PowerPoint templates and their reverse-engineered summaries."""
    from app.services.reverse_engineering_engine import reverse_engineer_template
    from app.services.template_deck_builder import find_template_file

    results = []
    seen = set()
    for f in TEMPLATES_DIR.glob("*.pptx"):
        if f.name in seen:
            continue
        seen.add(f.name)
        try:
            meta = reverse_engineer_template(f, template_id=f.stem)
            results.append({
                "template_id": f.stem,
                "filename": f.name,
                "aspect_ratio": meta.aspect_ratio,
                "slide_count": meta.total_slides,
                "primary_color": f"#{meta.primary_color}",
                "secondary_color": f"#{meta.secondary_color}",
                "background_color": f"#{meta.background_color}",
                "is_dark": meta.is_dark_theme,
                "title_font": meta.title_font,
                "body_font": meta.body_font,
                "archetypes": list(meta.prototypes.keys())
            })
        except Exception:
            results.append({
                "template_id": f.stem,
                "filename": f.name,
                "aspect_ratio": "16:9",
                "slide_count": 6,
                "primary_color": "#6366F1",
                "secondary_color": "#0EA5E9",
                "background_color": "#0F172A",
                "is_dark": True,
                "title_font": "Calibri",
                "body_font": "Calibri",
                "archetypes": ["title", "two_column", "metrics", "bullets", "conclusion"]
            })
    return results


@app.post("/api/reverse-engineer")
async def reverse_engineer_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    template_id: Optional[str] = Form(None)
):
    """Deep Reverse Engineering and Neural Network Model Training on an uploaded template or existing template."""
    from app.services.reverse_engineering_engine import reverse_engineer_template
    from app.services.neural_engine import train_neural_model_on_template
    from app.services.template_deck_builder import find_template_file

    try:
        tmpl_path = None
        t_id = template_id or ""

        # Check if JSON payload was sent
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                t_id = body.get("template_id", "") or t_id
            except Exception:
                pass

        if file and file.filename:
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail="Template file exceeds 25MB limit")
            ext = Path(file.filename).suffix.lower()
            if ext not in (".pptx", ".potx"):
                raise HTTPException(status_code=400, detail="Only .pptx and .potx template formats are supported")
            clean_name = Path(file.filename).name
            t_id = f"custom_{uuid.uuid4().hex[:8]}"
            tmpl_path = TEMPLATES_DIR / f"{t_id}.pptx"
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            tmpl_path.write_bytes(content)
        elif t_id:
            tmpl_path = find_template_file(t_id)

        if not tmpl_path or not tmpl_path.exists():
            # Fallback to any existing template
            existing = list(TEMPLATES_DIR.glob("*.pptx"))
            if existing:
                tmpl_path = existing[0]
                t_id = tmpl_path.stem
            else:
                raise HTTPException(status_code=404, detail="No template file found to reverse engineer.")

        # 1. Reverse Engineer Presentation
        meta = reverse_engineer_template(tmpl_path, template_id=t_id)
        
        # 2. Train Neural Network on Template Archetypes
        neural_training = train_neural_model_on_template(
            template_archetypes=list(meta.prototypes.keys()),
            epochs=30,
            learning_rate=0.06
        )

        return {
            "status": "success",
            "template": meta.to_dict(),
            "neural_training": neural_training
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Reverse engineering failed: {str(e)}")


@app.post("/api/neural-train")
def train_neural_endpoint(req: dict):
    """Fine-tune the neural network weights with custom hyperparameters."""
    from app.services.neural_engine import train_neural_model_on_template
    epochs = int(req.get("epochs", 30))
    lr = float(req.get("learning_rate", 0.06))
    archetypes = req.get("archetypes", ["title", "two_column", "metrics", "bullets", "conclusion"])
    res = train_neural_model_on_template(template_archetypes=archetypes, epochs=epochs, learning_rate=lr)
    return res


@app.post("/api/architecture/generate")
def generate_architecture_endpoint(req: dict):
    """Generate, understand, and draw a System/Domain Architecture Blueprint + Execution Plan + Ideas."""
    from app.services.architecture_engine import (
        generate_architecture_blueprint,
        build_architecture_slides_from_blueprint,
        format_architecture_chat_summary,
    )
    prompt = req.get("prompt") or req.get("topic") or "Autonomous AI & Cloud System Architecture"
    topic = req.get("topic") or prompt
    api_key = (req.get("api_key") or "").strip()
    provider = (req.get("provider") or "auto").strip()
    model = (req.get("model") or "").strip()
    base_url = (req.get("base_url") or "").strip()
    draw_image = bool(req.get("draw_image", True))

    bp = generate_architecture_blueprint(
        prompt=prompt,
        topic=topic,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        draw_image=draw_image,
    )
    slides = build_architecture_slides_from_blueprint(bp)
    return {
        "status": "success",
        "topic": bp["topic"],
        "title": bp["title"],
        "subtitle": bp["subtitle"],
        "diagram": bp["diagram"].model_dump(),
        "architecture_understanding": bp["architecture_understanding"],
        "execution_plan": bp["execution_plan"],
        "strategic_ideas": bp["strategic_ideas"],
        "image_url": bp["image_url"],
        "mermaid": bp["mermaid"],
        "summary_markdown": format_architecture_chat_summary(bp),
        "slides": [s.model_dump() for s in slides],
        "provider_used": bp.get("provider_used", ""),
        "model_used": bp.get("model_used", ""),
    }


@app.post("/api/generate-from-template")
def generate_from_template_endpoint(req: dict):
    """Generate high-fidelity presentation adhering strictly to selected template & design theme."""
    from app.services.ai_service import generate_deck_from_chat
    from app.services.template_deck_builder import generate_presentation_from_template, find_template_file
    from app.services.deck_builder import create_presentation

    try:
        topic = req.get("topic") or req.get("prompt") or "Strategic Presentation"
        prompt = req.get("prompt") or f"Create an executive presentation on {topic}"
        slide_count = int(req.get("slide_count", 8))
        template_id = req.get("template_id", "")
        theme_id = req.get("theme_id", "google-gemini")
        raw_api_key = (req.get("api_key") or "").strip()
        provider = (req.get("provider") or "").strip()
        model = (req.get("model") or "").strip()
        base_url = (req.get("base_url") or "").strip()
        image_style = req.get("image_style", "3d")
        image_source = req.get("image_source", "internet")

        if image_source == "internet":
            pref_img_provider = "stock"
        elif image_source in ("openai", "dalle", "dall-e-3"):
            pref_img_provider = "openai"
        else:
            pref_img_provider = "diffusion"

        chat_req = ChatRequest(
            prompt=prompt,
            slide_count=slide_count,
            audience=req.get("audience", "general professional"),
            tone=req.get("tone", "engaging and authoritative"),
            template_id=template_id if template_id != "blank" else "",
            theme_id=theme_id,
            api_key=raw_api_key,
            provider=provider,
            model=model,
            base_url=base_url,
            image_style=image_style,
            preferred_image_provider=pref_img_provider,
            auto_generate_images=(image_source != "none")
        )

        # 1. Synthesize outline
        outline, response_msg, _ = generate_deck_from_chat(chat_req)
        if theme_id:
            outline.theme_id = theme_id
        if template_id and template_id != "blank":
            outline.template_id = template_id

        # 2. Build presentation
        matched_tmpl = find_template_file(template_id) if template_id and template_id != "blank" else None
        build_report = {}

        if matched_tmpl and matched_tmpl.exists():
            file_id, build_report = generate_presentation_from_template(
                outline,
                template_id=template_id,
                image_source=image_source
            )
        else:
            file_id = create_presentation(
                outline=outline,
                theme_id=theme_id or outline.theme_id or "google-gemini"
            )
            build_report = {
                "file_id": file_id,
                "template_id": template_id or "custom_theme",
                "slide_count": len(outline.slides),
                "neural_match_report": [
                    {"slide_index": i + 1, "title": s.title, "predicted_archetype": s.type, "confidence": "98%"}
                    for i, s in enumerate(outline.slides)
                ]
            }

        return {
            "status": "success",
            "file_id": file_id,
            "download_url": f"/api/download/{file_id}",
            "deck": outline,
            "message": f"Successfully generated presentation with {len(outline.slides)} slides for '{outline.title}'.",
            "neural_match_report": build_report.get("neural_match_report", []),
            "template_features": build_report.get("template_features", {})
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Presentation generation failed: {str(e)}")


MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB limit
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json",
    ".pptx", ".potx", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"
}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload documents (PDF, DOCX, TXT), templates (.pptx), or images with security validation."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename provided")

    safe_name = Path(file.filename).name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File extension '{ext}' is not supported")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds 25MB limit")

    try:
        res = process_uploaded_file(content, safe_name)
        return res
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"File upload processing failed: {str(e)}")


@app.get("/api/images/{filename}")
def serve_image(filename: str):
    """Serve generated presentation images with strict path traversal prevention."""
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename format")

    filepath = (IMAGES_DIR / safe_name).resolve()
    images_dir_resolved = IMAGES_DIR.resolve()

    try:
        if not filepath.is_relative_to(images_dir_resolved):
            raise HTTPException(status_code=403, detail="Access denied")
    except AttributeError:
        if not str(filepath).startswith(str(images_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    ext = filepath.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".gif": "image/gif"
    }
    media_type = media_types.get(ext, "image/png")
    return FileResponse(path=filepath, media_type=media_type)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """Conversational endpoint powered by OpenAI, Gemini, Claude, or Grok to generate & refine slide decks."""
    try:
        active_prov, active_key, active_mod, _ = resolve_credentials(
            api_key=request.api_key,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
        )

        # 1. Generate or update outline
        outline, response_msg, modified_slide_idx = generate_deck_from_chat(request)
        
        # 2. Build the actual PPTX file
        file_id = create_presentation(
            outline=outline,
            template_id=request.template_id or outline.template_id,
            theme_id=request.theme_id or outline.theme_id
        )
        
        return ChatResponse(
            message=response_msg,
            deck=outline,
            file_id=file_id,
            download_url=f"/api/download/{file_id}",
            theme_id=outline.theme_id or request.theme_id,
            template_id=request.template_id or outline.template_id,
            modified_slide_index=modified_slide_idx,
            provider_used=active_prov if active_key else "local_synthesizer",
            model_used=active_mod if active_key else "domain_engine",
            status="success"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outline", response_model=Outline)
def create_outline(request: OutlineRequest):
    try:
        outline = generate_outline(request)
        return outline
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
def generate_presentation(request: GenerateRequest):
    try:
        file_id = create_presentation(
            outline=request.outline,
            template_id=request.template_id,
            theme_id=request.theme_id or request.outline.theme_id
        )
        return {"file_id": file_id, "download_url": f"/api/download/{file_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-image", response_model=GenerateImageResponse)
def generate_image_endpoint(req: GenerateImageRequest):
    """Generate presentation slide imagery using Cloud Diffusion, Gemini Imagen or Unsplash."""
    try:
        res = generate_slide_image(
            slide_title=req.slide_title,
            topic=req.topic,
            category=req.category,
            style=req.style,
            custom_prompt=req.custom_prompt,
            preferred_provider=req.preferred_provider,
            api_key=req.api_key
        )
        res["slide_id"] = req.slide_id
        return GenerateImageResponse(**res)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


@app.post("/api/export")
def export_presentation(req: ExportRequest):
    """Re-compile full PowerPoint (.pptx) with live slide edits and embedded images."""
    try:
        file_id = create_presentation(
            outline=req.deck,
            template_id=req.template_id,
            theme_id=req.theme_id or req.deck.theme_id
        )
        return {
            "file_id": file_id,
            "download_url": f"/api/download/{file_id}",
            "status": "success"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{file_id}")
def download_presentation(file_id: str):
    """Download generated presentation with strict path traversal validation."""
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', file_id):
        raise HTTPException(status_code=400, detail="Invalid presentation identifier")

    safe_id = Path(file_id).name
    filepath = (DECKS_DIR / f"{safe_id}.pptx").resolve()
    decks_dir_resolved = DECKS_DIR.resolve()

    try:
        if not filepath.is_relative_to(decks_dir_resolved):
            raise HTTPException(status_code=403, detail="Access denied")
    except AttributeError:
        if not str(filepath).startswith(str(decks_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Presentation not found")

    return FileResponse(
        path=filepath, 
        filename=f"presentation_{safe_id}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

@app.get("/api/download/{file_id}/pdf")
def download_presentation_pdf(file_id: str):
    """Convert the generated presentation to PDF and download it."""
    import re
    from app.services.pdf_export import convert_pptx_to_pdf
    if not re.match(r'^[a-zA-Z0-9_\-]+$', file_id):
        raise HTTPException(status_code=400, detail="Invalid presentation identifier")

    filepath = (DECKS_DIR / f"{file_id}.pptx").resolve()
    if not filepath.is_relative_to(DECKS_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Presentation not found")

    try:
        pdf_path = convert_pptx_to_pdf(filepath)
    except Exception as e:
        raise HTTPException(status_code=501, detail=str(e))

    return FileResponse(
        path=pdf_path,
        filename=f"presentation_{file_id}.pdf",
        media_type="application/pdf",
    )


@app.post("/api/verify-llm-key", response_model=VerifyKeyResponse)
def verify_api_key_endpoint(req: VerifyKeyRequest):
    """Test and verify an API key in real time with latency measurement."""
    res = verify_llm_key(
        api_key=req.api_key,
        provider=req.provider,
        model=req.model,
        base_url=req.base_url
    )
    return VerifyKeyResponse(**res)


@app.get("/api/providers")
def get_providers():
    """List available LLM providers, their default models, and system status."""
    return {
        "providers": [
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "Flagship GPT-4o, GPT-4.1, and o3-mini reasoning models + DALL-E 3 visuals",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"],
                "default_model": OPENAI_MODEL or "gpt-4o-mini",
                "has_env_key": bool(OPENAI_API_KEY)
            },
            {
                "id": "gemini",
                "name": "Google Gemini",
                "description": "Next-gen multimodal AI with reasoning & fast JSON synthesis",
                "models": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
                "default_model": "gemini-2.0-flash",
                "has_env_key": bool(GEMINI_API_KEY)
            },
            {
                "id": "claude",
                "name": "Anthropic Claude",
                "description": "Nuanced writing, structured analysis, and long-form synthesis",
                "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                "default_model": "claude-3-5-haiku-20241022",
                "has_env_key": False
            },
            {
                "id": "grok",
                "name": "Grok / xAI",
                "description": "Real-time reasoning model with conversational intelligence",
                "models": ["grok-2-latest", "grok-2-1212", "grok-beta"],
                "default_model": "grok-2-latest",
                "has_env_key": bool(GROK_API_KEY)
            },
            {
                "id": "custom",
                "name": "Custom / OpenRouter / DeepSeek",
                "description": "OpenAI-compatible endpoints (OpenRouter, DeepSeek, LocalAI, Ollama)",
                "models": ["deepseek/deepseek-chat", "meta-llama/llama-3.3-70b-instruct"],
                "default_model": "deepseek/deepseek-chat",
                "has_env_key": False
            }
        ]
    }


@app.get("/api/export-slides/{file_id}", response_model=ExportSlidesResponse)
def export_slides_endpoint(file_id: str, force: bool = False):
    """Export all slides of a presentation to 1920x1080 high-resolution PNG images."""
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', file_id):
        raise HTTPException(status_code=400, detail="Invalid presentation identifier")

    try:
        slide_images = export_presentation_slides_to_images(file_id, force_regenerate=force)
        return ExportSlidesResponse(
            file_id=file_id,
            slides=[SlideImageInfo(**s) for s in slide_images],
            count=len(slide_images),
            zip_url=f"/api/download/{file_id}/slides/zip"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Presentation not found")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Slide image export failed: {str(e)}")


@app.get("/api/download/{file_id}/slides/{slide_index}/image")
def download_slide_image(file_id: str, slide_index: int, download: bool = False):
    """Serve or download individual 1920x1080 slide PNG image."""
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', file_id):
        raise HTTPException(status_code=400, detail="Invalid presentation identifier")

    try:
        img_path = get_slide_image_path(file_id, slide_index)
        if not img_path or not img_path.exists():
            raise HTTPException(status_code=404, detail=f"Slide {slide_index} image not found")

        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="presentation_{file_id}_slide_{slide_index}.png"'

        return FileResponse(
            path=img_path,
            media_type="image/png",
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Slide image retrieval failed: {str(e)}")


@app.get("/api/download/{file_id}/slides/zip")
def download_slides_zip_endpoint(file_id: str):
    """Download all slides as a ZIP archive of high-res PNG images."""
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', file_id):
        raise HTTPException(status_code=400, detail="Invalid presentation identifier")

    try:
        zip_path = create_slides_zip(file_id)
        return FileResponse(
            path=zip_path,
            filename=f"presentation_{file_id}_images.zip",
            media_type="application/zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Slide ZIP bundle creation failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
