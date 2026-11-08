# AI PPT Generator — OpenAI & Neural Architecture Presentation Studio

An end-to-end AI-powered presentation and system architecture platform built with **FastAPI**, **React + Vite**, **python-pptx**, and **OpenAI (`gpt-4o-mini` / `DALL-E 3`)** with a trained **3-Layer Deep Residual Neural Layout Engine**.

## ✨ Key Capabilities

1. **OpenAI & Multi-Provider Presentation Generation**
   - Full integration with OpenAI (`gpt-4o-mini`, `gpt-4o`, `DALL-E 3`) as well as Gemini, Claude, Grok, and OpenRouter.
   - Input-faithful semantic synthesis with live Wikipedia/Web fact grounding when operating without an API key.
2. **Trained Neural Slide Layout Engine (100% Validation Accuracy)**
   - 3-layer residual MLP (`SlideLayoutNeuralNetwork`) with LayerNorm, GELU, Nesterov momentum, cosine LR annealing, and L2 regularization (`backend/app/services/neural_engine.py`).
   - Automatically selects optimal slide archetypes (`title`, `two_column`, `metrics`, `timeline`, `table`, `quote`, `bullets`, `conclusion`, `diagram`) and visual themes from any user prompt.
3. **System Architecture Generation, Drawing, Understanding & Planning (`backend/app/services/architecture_engine.py`)**
   - **Understand & Deconstruct**: Breaks down any prompt into multi-tier `clusters`, typed component `nodes` (`user`, `decision`, `cloud`, `process`, `queue`, `database`), and directed `edges` with protocol labels.
   - **Draw in 3 Formats**:
     - **1920×1080 Technical Blueprint PNG** (`draw_architecture_diagram_png`)
     - **Native Editable PowerPoint Shapes** (`render_diagram_slide` in `deck_builder.py` using `MSO_SHAPE.CAN`, `CLOUD`, `DIAMOND`, `HEXAGON`, `ROUNDED_RECTANGLE`, and `RIGHT_ARROW`)
     - **Interactive React Topology Canvas & Editor** (`ArchitectureDiagramView.jsx`)
   - **Plans & Strategic Ideas**: Generates a 4-point **Architecture Understanding**, a 4-phase **Execution Plan**, and **Strategic Ideas & Innovations**.
4. **Template Reverse-Engineering & Native `.pptx` Export**
   - Upload or select `.pptx` templates, inspect slide master layouts, and export widescreen 16:9 Microsoft PowerPoint (`.pptx`), PDF, or 1920×1080 PNG slide bundles.

---

## 🚀 Quick Start

### 1. Backend Setup (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy .env.example to .env and add your OPENAI_API_KEY (optional)
copy .env.example .env

# Start the FastAPI server on http://127.0.0.1:8000
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup (React + Vite)

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open **http://127.0.0.1:5173** in your browser.

---

## 🧪 Running the Test Suite

```bash
.\backend\.venv\Scripts\python.exe backend\tests\test_openai_ppt_pipeline.py
```
