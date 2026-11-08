"""AI Presentation Agent.

Autonomous multi-stage strategic presentation planner, multi-domain semantic content synthesizer,
and contextual visual asset generator for SlideCraft AI. Supports generating publication-ready
keynotes and presentations on ANY topic across technology, science, history, business, healthcare,
arts, culinary, philosophy, fitness, and more.
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
import ssl
import uuid
from typing import Optional, List, Dict, Any, Tuple

from ..config import (
    OPENAI_API_KEY, OPENAI_MODEL,
    GEMINI_API_KEY, TEXT_MODEL,
    GROK_API_KEY, GROK_API_KEY_NAME, GROK_BASE_URL, GROK_MODEL
)
from ..schemas import (
    ChatRequest, OutlineRequest, Outline, Slide, AISlide, AIOutline,
    StatItem, Visual, FileAttachment, TableSpec
)
from .image_service import generate_slide_image
from .llm_gateway import (
    has_configured_llm,
    call_llm_json_with_meta,
    normalize_outline_payload,
)


# ==============================================================================
# 1. Semantic Input Parser & Multi-Domain Classifier
# ==============================================================================

class SemanticProfile:
    """Deconstructed semantic representation of the user prompt and context."""
    def __init__(
        self,
        raw_topic: str,
        clean_topic: str,
        topic_title: str,
        domain: str,
        key_phrases: List[str],
        numerical_entities: List[Tuple[str, str]],
        pain_points: List[str],
        solutions: List[str],
        technical_pillars: List[str],
        raw_prompt: str,
        source_text: str = "",
        web_facts: Optional[Dict[str, Any]] = None
    ):
        self.raw_topic = raw_topic
        self.clean_topic = clean_topic
        self.topic_title = topic_title
        self.domain = domain
        self.key_phrases = key_phrases
        self.numerical_entities = numerical_entities
        self.pain_points = pain_points
        self.solutions = solutions
        self.technical_pillars = technical_pillars
        self.raw_prompt = raw_prompt
        self.source_text = source_text
        self.web_facts = web_facts or {}


DOMAIN_TAXONOMY = {
    "history_culture": [
        "history", "historical", "revolution", "civilization", "empire", "roman", "rome", "greece", "greek",
        "ancient", "medieval", "renaissance", "war", "battle", "dynasty", "monarchy", "colonial",
        "century", "archaeology", "archaeological", "museum", "biography", "relic", "conquest",
        "treaty", "feudal", "pharaoh", "egypt", "ottoman", "french revolution", "silk road", "napoleon"
    ],
    "science_space": [
        "physics", "chemistry", "astronomy", "quantum", "universe", "space", "galaxy", "particle",
        "thermodynamics", "optics", "gravity", "relativity", "cosmic", "solar", "planet", "orbit",
        "mars", "telescope", "astrophysics", "electromagnetism", "nuclear", "atom", "nanotechnology"
    ],
    "medicine_health": [
        "medicine", "medical", "health", "healthcare", "clinical", "patient", "disease", "therapy",
        "drug", "pharma", "pharmaceutical", "hospital", "diagnosis", "genetic", "genomics", "immune",
        "immunology", "vaccine", "surgical", "surgery", "neurobiology", "neuroscience", "cardiology",
        "cancer", "oncology", "pathology", "cellular", "biotechnology", "microbiome", "doctor"
    ],
    "wellness_fitness": [
        "fitness", "workout", "exercise", "gym", "yoga", "nutrition", "diet", "wellness",
        "mental health", "meditation", "mindfulness", "running", "marathon", "athletics", "muscle",
        "cardio", "sleep", "stress", "caloric", "metabolism", "endurance", "longevity", "hydration"
    ],
    "climate_environment": [
        "climate", "environment", "environmental", "carbon", "energy", "renewable", "solar energy",
        "wind power", "ocean", "marine", "ecology", "ecological", "biodiversity", "sustainable",
        "sustainability", "pollution", "emissions", "green", "conservation", "decarbonization",
        "ecosystem", "wildlife", "global warming", "recycling", "net zero", "clean tech"
    ],
    "food_culinary": [
        "food", "cooking", "culinary", "gastronomy", "recipe", "chef", "baking", "bread",
        "sourdough", "pastry", "restaurant", "wine", "fermentation", "cuisine", "dining",
        "ingredients", "flavor", "flavour", "gourmet", "taste", "kitchen", "coffee", "roasting"
    ],
    "arts_humanities": [
        "art", "artist", "design", "music", "musical", "painting", "sculpture", "film",
        "cinema", "movie", "photography", "literature", "novel", "poetry", "theatre", "theater",
        "philosophy", "philosophical", "architecture", "architectural", "ethics", "aesthetics",
        "creativity", "composition", "harmony"
    ],
    "education_learning": [
        "education", "educational", "school", "teaching", "student", "teacher", "learning",
        "university", "curriculum", "classroom", "pedagogy", "pedagogical", "academic", "study",
        "exam", "literacy", "training", "stem", "higher education", "instruction"
    ],
    "business_strategy": [
        "business", "strategy", "strategic", "startup", "company", "management", "leadership",
        "customer", "sales", "marketing", "product management", "growth", "operations", "workflow",
        "brand", "branding", "enterprise", "stakeholder", "b2b", "b2c", "organization", "agile"
    ],
    "finance_economics": [
        "finance", "financial", "revenue", "investment", "investor", "market", "stock", "stocks",
        "economy", "economic", "economics", "capital", "fund", "venture capital", "crypto", "bitcoin",
        "banking", "budget", "valuation", "portfolio", "monetary", "inflation", "cagr", "ebitda", "arr"
    ],
    "technology_ai": [
        "ai", "artificial intelligence", "cloud", "software", "api", "model", "neural", "neural network",
        "code", "coding", "developer", "devops", "cyber", "cybersecurity", "security", "algorithm",
        "data", "database", "computer", "network", "app", "application", "mobile", "web", "robotics",
        "machine learning", "deep learning", "infrastructure", "kubernetes", "microservices"
    ],
    "law_governance": [
        "law", "legal", "government", "policy", "politics", "political", "rights", "constitution",
        "constitutional", "regulation", "regulatory", "justice", "court", "international relations",
        "diplomacy", "civic", "governance", "democracy", "treaties", "legislation"
    ]
}


def extract_semantic_profile(prompt: str, source_text: str = "") -> SemanticProfile:
    """Analyze the user's prompt and attached documents to extract domain, entities, and arguments."""
    # Strip UI-appended directives like "(Ground in verified web reference facts)"
    clean_prompt = re.sub(
        r'\s*\(ground\s+in\s+verified\s+web\s+reference\s+facts\)\s*',
        ' ',
        prompt or "",
        flags=re.IGNORECASE
    ).strip()

    # Extract clean topic from prompt
    topic_match = re.sub(
        r'^(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?(?:generate|create|build|make|draft|design|prepare|develop|write|give\s+me|explain|present)\s+(?:an?\s+|the\s+)?(?:\d+[\s-]slide\s+)?(?:comprehensive\s+|detailed\s+|executive\s+|professional\s+|desired\s+)?(?:presentation|ppt|powerpoint|slide\s*deck|deck|slides|keynote|overview|report)?\s*(?:about|on|for|from|regarding|titled|covering|of)?\s*',
        '', clean_prompt, flags=re.IGNORECASE
    ).strip()

    # Strip trailing model/helper phrases from topic candidate
    topic_match = re.sub(
        r'\s+(?:with\s+(?:the\s+)?help\s+of|using|via|powered\s+by)\s+(?:open\s*ai|gpt[\w\-]*|gemini|claude|ai).*$',
        '', topic_match, flags=re.IGNORECASE
    ).strip()

    # If prompt starts with quotes
    q_match = re.search(r'["\']([^"\']{4,80})["\']', topic_match)
    if q_match:
        topic = q_match.group(1).strip()
    else:
        # Take first sentence or clause before "including / covering / focusing on / with sections on"
        first_sentence = re.split(r'[\.\n\?!;]', topic_match)[0].strip()
        first_sentence = re.sub(r'\s+(?:with|in|across)\s+\d+\s+slides?.*$', '', first_sentence, flags=re.IGNORECASE).strip()
        first_sentence = re.sub(
            r'\s*(?:,|\b(?:including|covering|focusing\s+on|highlighting|comparing|with\s+sections\s+on|such\s+as))\s+.*$',
            '', first_sentence, flags=re.IGNORECASE
        ).strip()
        words = first_sentence.split()
        if len(words) > 10:
            topic = " ".join(words[:10])
        else:
            topic = first_sentence or "Strategic Vision & Architecture"

    if not topic or re.search(r'^(this|the)\s+(attached\s+)?(file|document|paper|pdf|notes|data)', topic, flags=re.IGNORECASE):
        if source_text:
            first_lines = [l.strip() for l in source_text.split('\n') if l.strip() and not l.startswith('---')]
            topic = first_lines[0].split('.')[0].strip() if first_lines else "Strategic Research & Findings"
        else:
            topic = "Strategic Architecture & Execution"

    # Remove any leftover conversational command fragments
    topic = re.sub(r'^(?:make|create|generate)\s+a\s+\d+\s+slide\s+presentation\s+on\s+', '', topic, flags=re.IGNORECASE)
    topic = re.sub(r'\([^)]*\)', '', topic).strip()
    topic_title = topic.strip().title()
    if len(topic_title) > 65:
        topic_title = topic_title[:62] + "..."

    combined_text = f"{clean_prompt}\n{source_text}"
    lower_text = combined_text.lower()

    # Multi-Domain Scoring
    domain_scores = {dom: 0 for dom in DOMAIN_TAXONOMY}
    for dom, kws in DOMAIN_TAXONOMY.items():
        for kw in kws:
            if kw in lower_text:
                domain_scores[dom] += 2 if f" {kw} " in f" {lower_text} " else 1

    best_domain = max(domain_scores, key=domain_scores.get)
    if domain_scores[best_domain] > 0:
        domain = best_domain
    else:
        domain = "general"

    # Extract Key phrases / subtopics from user prompt (commas, bullets, semicolons, "including X, Y and Z")
    phrases: List[str] = []
    meta_headers = [
        "core topics:", "core topic:", "key metrics:", "key metric:", "compare against:",
        "milestones:", "presentation on:", "presentation about:", "features:", "pillars:", "topics:",
        "including", "covering", "focusing on", "highlighting"
    ]
    # Also split on " and " when part of a list after including/covering
    expanded_prompt = re.sub(r'\b(?:including|covering|focusing\s+on|highlighting|such\s+as)\s+', ', ', clean_prompt, flags=re.IGNORECASE)
    clauses = re.split(r'[,;:\n•\-\t]|(?:\s+and\s+(?=[a-zA-Z]{3,}))', expanded_prompt)
    for c in clauses:
        c_clean = re.sub(r'\([^)]*\)', '', c).strip().strip('.!?')
        for mh in meta_headers:
            if c_clean.lower().startswith(mh):
                c_clean = c_clean[len(mh):].strip()
        if 3 < len(c_clean) <= 95 and len(c_clean.split()) <= 12:
            if not any(w in c_clean.lower() for w in [
                "create a", "make a", "generate a", "build a", "slide deck",
                "presentation on", "presentation about", "slides on", "ground in verified"
            ]):
                if c_clean.lower() != topic.lower() and c_clean not in phrases:
                    phrases.append(c_clean)

    # Extract numerical entities (percentages, multipliers, currency, dates, numbers)
    numerical_entities: List[Tuple[str, str]] = []
    num_matches = re.findall(r'(\+?[\$€£]?\d+(?:\.\d+)?(?:%|x|X|M|B|k|K|ms|s|gb|tb|fps|°C|km|kg|hrs)?)\s+([a-zA-Z\s]{3,25})', combined_text)
    for val, lbl in num_matches[:6]:
        lbl_clean = lbl.strip().title()
        if len(lbl_clean) > 3 and not any(w in lbl_clean.lower() for w in ["slides", "presentation", "deck", "page"]):
            numerical_entities.append((val, lbl_clean))

    # Identify explicit pain points / bottlenecks
    pain_points = []
    for line in re.split(r'[\.\n;]', combined_text):
        l_str = line.strip()
        if any(w in l_str.lower() for w in ["bottleneck", "legacy", "challenge", "problem", "inefficiency", "latency", "manual", "fragment", "costly", "slow", "barrier", "risk", "struggle", "obstacle"]):
            if len(l_str) > 10:
                pain_points.append(l_str)

    # Identify explicit solutions / features
    solutions = []
    for line in re.split(r'[\.\n;]', combined_text):
        l_str = line.strip()
        if any(w in l_str.lower() for w in ["accelerat", "automat", "optimiz", "solution", "deliver", "scalable", "instant", "intelligent", "transform", "revolution", "mastery", "discovery", "breakthrough"]):
            if len(l_str) > 10:
                solutions.append(l_str)

    technical_pillars = [p for p in phrases if len(p.split()) >= 2][:6]

    return SemanticProfile(
        raw_topic=topic,
        clean_topic=topic,
        topic_title=topic_title,
        domain=domain,
        key_phrases=phrases[:10],
        numerical_entities=numerical_entities,
        pain_points=pain_points[:4],
        solutions=solutions[:4],
        technical_pillars=technical_pillars,
        raw_prompt=clean_prompt,
        source_text=source_text
    )


# ==============================================================================
# 2. Deep Multi-Domain Semantic Synthesizer (Zero-Failure Engine)
# ==============================================================================

DOMAIN_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    "history_culture": {
        "badge": "HISTORICAL CHRONICLE",
        "subtitle": "Catalysts, Transformational Events & Enduring Global Legacy",
        "left_header": "Antecedents & Baseline Pressures:",
        "left_items": [
            "Socioeconomic disparity and structural institutional rigidity",
            "Escalating systemic unrest and unaddressed popular grievances",
            "Breakdown of traditional governing consensus"
        ],
        "right_header": "Transformational Paradigm Shift:",
        "right_items": [
            "Emergence of revolutionary ideology and collective mobilization",
            "Rapid restructuring of legal, civic, and cultural frameworks",
            "Permanent transformation of the sociopolitical landscape"
        ],
        "core_bullets": [
            "Ideological Catalysts: Foundational texts, debates, and philosophical shifts",
            "Crucial Turning Points: Decisive milestones that reshaped the trajectory of power",
            "Civic & Cultural Transformation: Re-imagining society, identity, and governance",
            "Enduring Global Impact: Precedents established for modern institutional thought"
        ],
        "stats": [
            ("1789", "Foundational Epoch / Spark", "Historic Catalyst"),
            ("26M+", "Demographic Impact", "Directly Affected"),
            ("100%", "Constitutional Reorganization", "Complete Shift"),
            ("3+", "Continents Influenced", "Global Legacy")
        ],
        "table_headers": ["Historical Dimension", "Ancien Régime / Baseline", "Revolutionary Transformation", "Modern Legacy"],
        "table_rows": [
            ["Power & Governance", "Hereditary autocratic control", "Popular sovereignty and representative bodies", "Constitutional democracy"],
            ["Legal Framework", "Feudal decrees and regional fragmentation", "Unified egalitarian legal codes", "Universal civil rights"],
            ["Social Hierarchy", "Rigid estate stratification", "Merit-based civic participation", "Democratic mobility"],
            ["Cultural Consciousness", "Orthodox state doctrine", "Secular intellectual discourse", "Modern civic education"]
        ],
        "case_bullets": [
            "Grassroots Mobilization: Spontaneous convergence of local movements into national change",
            "Institutional Reconstruction: Rapid drafting of declarations, charters, and civic codes",
            "Resistance & Polarization: Navigating domestic friction and external geopolitical pressures",
            "Cultural Synthesis: Codifying new civic symbols, holidays, and shared heritage"
        ],
        "phases": [
            "Phase 1: Catalysts, Early Grievances & Intellectual Awakening",
            "Phase 2: Popular Mobilization & Institutional Rupture",
            "Phase 3: Constitutional Codification & Structural Reorganization",
            "Phase 4: Global Diffusion & Enduring Historical Precedent"
        ],
        "conclusion": [
            "Permanent Paradigm Shift: Shattered century-old dogmas and redefined sovereignty",
            "Universal Precedents: Established foundational principles still governing modern society",
            "Complex Historical Balance: Both tremendous humanitarian progress and turbulent upheaval",
            "Enduring Modern Relevance: Critical lessons for understanding contemporary societal change"
        ]
    },
    "science_space": {
        "badge": "SCIENTIFIC EXPEDITION",
        "subtitle": "Empirical Principles, Theoretical Breakthroughs & Frontier Horizons",
        "left_header": "Classical Limitations & Knowledge Gaps:",
        "left_items": [
            "Inability of legacy models to explain anomalous experimental observations",
            "Measurement constraints and instrumentation resolution ceilings",
            "Theoretical fragmentation across discrete sub-disciplines"
        ],
        "right_header": "Unified Theoretical Breakthrough:",
        "right_items": [
            "Comprehensive empirical formulation resolving classical paradoxes",
            "High-precision telemetry confirming predictive mathematical models",
            "Cross-domain convergence unlocking revolutionary frontiers"
        ],
        "core_bullets": [
            "Foundational Mechanics: Primary equations and core conservation laws",
            "Experimental Verification: Rigorous observational protocols and sensory arrays",
            "Computational Modeling: High-throughput simulations modeling extreme conditions",
            "Frontier Horizons: Open questions driving the next generation of scientific inquiry"
        ],
        "stats": [
            ("99.998%", "Empirical Confidence (5-Sigma)", "Definitive Proof"),
            ("3.8x", "Observational Resolution", "Deep Space / Micro"),
            ("< 0.001", "Statistical p-value", "Peer Validated"),
            ("100%", "Reproducibility Rate", "Global Consortia")
        ],
        "table_headers": ["Scientific Vector", "Classical Hypothesis", "Empirical Breakthrough", "Frontier Implication"],
        "table_rows": [
            ["Observational Scope", "Limited localized optical spectra", "Multi-messenger deep telemetry", "Unified cosmic mapping"],
            ["Predictive Precision", "Phenomenological approximations", "Closed-form tensor mathematics", "Deterministic forecasts"],
            ["Instrumentation", "Manual optical capture", "Cryogenic quantum detector arrays", "Sub-atomic resolution"],
            ["Interdisciplinary Reach", "Isolated physics silos", "Convergence with astrophysics and chemistry", "Holistic cosmological models"]
        ],
        "case_bullets": [
            "Observational Deployment: Launching sensitive orbital and subterranean detector arrays",
            "Signal Isolation: Extracting faint signatures from massive ambient background noise",
            "Cross-Laboratory Replication: Independent verification by peer teams across international facilities",
            "Theoretical Refinement: Iterating models to incorporate high-fidelity empirical data"
        ],
        "phases": [
            "Phase 1: Theoretical Hypothesis & Mathematical Formulation",
            "Phase 2: Instrumentation Design & Experimental Calibration",
            "Phase 3: High-Sensitivity Telemetry Gathering & Data Validation",
            "Phase 4: Synthesis, Peer Replication & Paradigmatic Integration"
        ],
        "conclusion": [
            "Verified Theoretical Model: Replaces incomplete classical hypotheses with rigorous proof",
            "Technological Multipliers: Direct spillover innovations across sensors, compute, and energy",
            "Deepened Cosmic Perspective: Fundamentally expands human comprehension of natural laws",
            "Active Research Agenda: Illuminates specific unanswered questions for the next decade"
        ]
    },
    "medicine_health": {
        "badge": "BIOMEDICAL RESEARCH",
        "subtitle": "Pathological Insights, Clinical Innovations & Patient-Centric Outcomes",
        "left_header": "Traditional Clinical Limitations:",
        "left_items": [
            "Generalized broad-spectrum treatments with high adverse effect rates",
            "Delayed diagnostic detection leading to advanced progression",
            "Fragmented patient telemetry and reactive rather than preventative care"
        ],
        "right_header": "Precision Medicine Paradigm:",
        "right_items": [
            "Targeted molecular therapies tailored to individual biomarker profiles",
            "Early detection via high-sensitivity assays and continuous monitoring",
            "Holistic therapeutic regimens maximizing quality of life and clinical efficacy"
        ],
        "core_bullets": [
            "Biological Mechanisms: Cellular pathways, receptor interactions, and disease etiology",
            "Therapeutic Modalities: Precision interventions engineered for maximum bioavailability",
            "Clinical Validation: Controlled multi-phase human trials validating safety and efficacy",
            "Translational Application: Protocols for real-world deployment across hospital systems"
        ],
        "stats": [
            ("94.8%", "Clinical Efficacy Rate", "Phase III Validated"),
            ("N=14,200", "Multi-Center Cohort", "Statistically Robust"),
            ("-58%", "Adverse Event Incidence", "Superior Tolerability"),
            ("< 48 hrs", "Median Time-to-Remission", "Accelerated Recovery")
        ],
        "table_headers": ["Clinical Metric", "Standard of Care", "Advanced Targeted Protocol", "Patient Advantage"],
        "table_rows": [
            ["Mechanism of Action", "Broad systemic intervention", "Receptor-targeted molecular therapy", "Minimized healthy tissue damage"],
            ["Diagnostic Precision", "Symptom-based clinical evaluation", "Biomarker genomic profiling", "Pinpoint early detection"],
            ["Adherence & Tolerability", "High patient drop-out due to toxicity", "Optimized micro-dosing schedule", "Sustained treatment completion"],
            ["Long-Term Recurrence", "Frequent post-treatment relapses", "Durable immunological response", "Long-term disease-free survival"]
        ],
        "case_bullets": [
            "Cohort Stratification: Isolating patient subgroups based on genetic and metabolic markers",
            "Protocol Administration: Implementing strict dosing schedules with continuous biomarker assays",
            "Adverse Event Management: Rapid mitigation protocols maintaining high patient comfort",
            "Outcome Documentation: Statistically significant improvements in survival and functional recovery"
        ],
        "phases": [
            "Phase 1: Pre-Clinical In Vitro & In Vivo Mechanistic Validation",
            "Phase 2: Phase I/II Dosage Optimization & Safety Characterization",
            "Phase 3: Multi-Center Randomized Double-Blind Phase III Trial",
            "Phase 4: Regulatory Approval, Formulary Inclusion & Clinical Rollout"
        ],
        "conclusion": [
            "Step-Function Efficacy: Clinically demonstrated superiority over legacy standard-of-care",
            "Elevated Safety Profile: Dramatic reduction in toxicity and treatment-related complications",
            "Holistic Quality of Life: Preserves functional capacity and daily wellbeing for patients",
            "Scalable Healthcare Integration: Readily adoptable protocols across major hospital networks"
        ]
    },
    "wellness_fitness": {
        "badge": "HUMAN PERFORMANCE",
        "subtitle": "Physiological Conditioning, Evidence-Based Nutrition & Holistic Vitality",
        "left_header": "Conventional Fitness Pitfalls:",
        "left_items": [
            "Unsustainable extreme regimes leading to injury and burnout",
            "Generic routines ignoring individual biomechanics and recovery capacity",
            "Over-emphasis on aesthetics at the expense of metabolic and mental health"
        ],
        "right_header": "Evidence-Based Optimization:",
        "right_items": [
            "Progressive overload calibrated to biological recovery and sleep metrics",
            "Nutrient-dense fueling tailored to metabolic demands and gut health",
            "Sustainable habit architecture promoting lifelong physical and mental resilience"
        ],
        "core_bullets": [
            "Biomechanics & Movement: Foundational kinetic chains protecting joint longevity",
            "Metabolic Conditioning: Optimizing aerobic capacity (VO2 max) and mitochondrial density",
            "Recovery Science: Sleep architecture, HRV tracking, and active tissue regeneration",
            "Behavioral Psychology: Building frictionless adherence and sustainable daily rituals"
        ],
        "stats": [
            ("+34%", "Aerobic Capacity (VO2 Max)", "12-Week Protocol"),
            ("88%", "Sustained 1-Year Adherence", "Habit-Loop Design"),
            ("-42%", "Systemic Cortisol / Stress", "HRV Validated"),
            ("100%", "Injury-Free Progression", "Biomechanical Alignment")
        ],
        "table_headers": ["Fitness Vector", "Quick-Fix Fads", "Science-Backed Protocol", "Long-Term Payoff"],
        "table_rows": [
            ["Training Intensity", "Constant failure and exhaustion", "Periodized progressive stimulus", "Consistent compounding strength"],
            ["Nutritional Approach", "Severe caloric starvation", "Macronutrient balance and micronutrient density", "Optimal metabolic health"],
            ["Recovery Prioritization", "Treated as weakness or lost time", "Prioritized sleep and parasympathetic reset", "Accelerated tissue adaptation"],
            ["Mental Outlook", "Punitive self-criticism", "Mindful celebration of daily capability", "Lifelong joy in movement"]
        ],
        "case_bullets": [
            "Baseline Assessment: Evaluating movement mobility, cardiovascular fitness, and lifestyle habits",
            "Program Customization: Structuring a realistic weekly rhythm that fits demanding schedules",
            "Progressive Tracking: Monitoring quantifiable strength, body composition, and sleep quality",
            "Long-Term Integration: Transitioning from rigid discipline to effortless daily lifestyle"
        ],
        "phases": [
            "Phase 1: Biomechanical Assessment & Movement Foundation",
            "Phase 2: Progressive Adaptation & Metabolic Conditioning",
            "Phase 3: Peak Performance, Strength & Power Development",
            "Phase 4: Sustainable Maintenance, Longevity & Habit Mastery"
        ],
        "conclusion": [
            "Sustainable Transformation: Real results achieved through consistency rather than punishment",
            "Comprehensive Health Span: Improves vitality, mental clarity, and chronic disease resilience",
            "Biomechanical Freedom: Unlocks pain-free athletic movement at every stage of life",
            "Lifelong Architecture: Practical systems that thrive amidst real-world work and family demands"
        ]
    },
    "climate_environment": {
        "badge": "ECOLOGICAL HORIZONS",
        "subtitle": "Decarbonization Pathways, Biodiversity Preservation & Sustainable Systems",
        "left_header": "Linear Exploitative Model:",
        "left_items": [
            "Heavy reliance on carbon-intensive fossil infrastructure",
            "Accelerating biodiversity loss and fragile ecosystem degradation",
            "Unchecked resource depletion and polluting waste streams"
        ],
        "right_header": "Regenerative Circular Architecture:",
        "right_items": [
            "Rapid deployment of cost-competitive renewable generation and storage",
            "Active ecological restoration and nature-based carbon sequestration",
            "Circular closed-loop supply chains eliminating industrial waste"
        ],
        "core_bullets": [
            "Energy Transition: Scaling solar, wind, geothermal, and grid storage technologies",
            "Ecosystem Stewardship: Reforestation, watershed protection, and marine sanctuaries",
            "Circular Industrial Design: Material reuse, life-cycle efficiency, and zero-landfill goals",
            "Policy & Economics: Carbon pricing, regulatory incentives, and green capital allocation"
        ],
        "stats": [
            ("-65%", "Carbon Intensity Reduction", "By 2030 Horizon"),
            ("2.4 TW", "Global Renewable Capacity", "Exponential Growth"),
            ("1.5°C", "Target Warming Threshold", "Global Imperative"),
            ("92%", "Material Circularity Potential", "Zero-Waste Design")
        ],
        "table_headers": ["Environmental Domain", "Business-As-Usual", "Regenerative Solution", "Ecological Impact"],
        "table_rows": [
            ["Power Generation", "Centralized coal and gas turbines", "Distributed renewables + battery storage", "Zero carbon emissions"],
            ["Industrial Materials", "Virgin resource extraction", "Bio-based and recycled closed loops", "80% lower footprint"],
            ["Land Use", "Deforestation for mono-cropping", "Regenerative agroforestry and rewilding", "Restored biodiversity"],
            ["Capital Flows", "Short-term fossil subsidies", "Green bond financing and ESG alignment", "Long-term climate resilience"]
        ],
        "case_bullets": [
            "Renewable Integration: Commissioning gigawatt-scale wind and solar complexes with battery reserves",
            "Habitat Restoration: Re-establishing native flora and fauna across degraded ecosystems",
            "Supply Chain Decarbonization: Auditing Scope 1, 2, and 3 emissions across global suppliers",
            "Community Co-Benefits: Creating clean energy employment and improving local public health"
        ],
        "phases": [
            "Phase 1: Emissions Baseline Audit & Ecosystem Vulnerability Mapping",
            "Phase 2: Renewable Deployment & Energy Efficiency Upgrades",
            "Phase 3: Circular Supply Chain Integration & Nature-Based Sequestration",
            "Phase 4: Full Net-Zero Operation, Climate Resilience & Global Leadership"
        ],
        "conclusion": [
            "Commercially Viable: Clean technologies are now cheaper and more reliable than fossil fuels",
            "Systemic Resilience: Insulates organizations from geopolitical energy shocks and regulations",
            "Planetary Stewardship: Safeguards vital life-support systems for future generations",
            "Urgent Action Decade: Immediate execution required to maintain the 1.5°C climate window"
        ]
    },
    "food_culinary": {
        "badge": "GASTRONOMIC MASTERCLASS",
        "subtitle": "Artisanal Techniques, Food Chemistry & Exquisite Flavor Profiles",
        "left_header": "Commercial Mass Production:",
        "left_items": [
            "Artificial additives, expedited fermentations, and uniform blandness",
            "Loss of ancestral grain varieties, heirloom produce, and regional culinary heritage",
            "Industrial processing prioritizing shelf-life over nutrient density and digestion"
        ],
        "right_header": "Artisanal Precision & Chemistry:",
        "right_items": [
            "Slow natural fermentation developing complex lactic and acetic acidity",
            "Heirloom ingredients celebrating terroir, seasonality, and biodiversity",
            "Mastery of thermal dynamics, enzymatic breakdown, and Maillard reactions"
        ],
        "core_bullets": [
            "Ingredients & Terroir: Selecting unbleached flours, stone-ground grains, and pristine water",
            "Fermentation Dynamics: Cultivating wild yeast and lactobacilli for digestibility and flavor",
            "Thermal Execution: Steam injection, hearth conductive heat, and crust blister crystallization",
            "Sensory Harmony: Balancing acidity, salinity, texture, crumb aeration, and aroma"
        ],
        "stats": [
            ("78%", "Dough Hydration Ratio", "Open Crumb Structure"),
            ("24-36 hrs", "Cold Retardation Window", "Complex Flavor Profile"),
            ("240°C", "Hearth Baking Temperature", "Optimal Oven Spring"),
            ("100%", "Naturally Leavened", "Zero Commercial Additives")
        ],
        "table_headers": ["Culinary Factor", "Commercial Fast-Bake", "Artisanal Wild Ferment", "Gastronomic Difference"],
        "table_rows": [
            ["Fermentation Method", "Fast commercial baker's yeast (90 min)", "Wild sourdough culture (24+ hours)", "Deep, complex, digestible flavor"],
            ["Gluten Breakdown", "Minimal enzymatic degradation", "Extensive gluten pre-digestion", "Gentle on digestive systems"],
            ["Crust & Crumb", "Soft, spongy, uniform crumb", "Custardy, aerated crumb with blistered crust", "Exquisite multi-textural mouthfeel"],
            ["Preservation", "Chemical preservatives and emulsifiers", "Natural acidity safeguards freshness", "Fresh for 5+ days without chemicals"]
        ],
        "case_bullets": [
            "Mother Culture Nurturing: Maintaining consistent feeding cycles to balance yeast and bacterial activity",
            "Autolyse & Hydration: Allowing flour to fully hydrate and form gluten bonds without mechanical stress",
            "Bulk Fermentation & Shaping: Gentle coil folds trapping gas bubbles while building surface tension",
            "Bake Execution: High-heat steam injection creating a golden blistered ear and caramelized crust"
        ],
        "phases": [
            "Phase 1: Ingredient Sourcing & Starter Culture Inoculation",
            "Phase 2: Autolyse, Bulk Fermentation & Structural Coil Folds",
            "Phase 3: Bench Rest, Final Shaping & Cold Retardation",
            "Phase 4: Hearth Baking, Steam Injection & Cooling Crystallization"
        ],
        "conclusion": [
            "Culinary Alchemy: Simple flour, water, and salt transformed into exceptional gastronomy",
            "Nutritional Superiority: Enhanced bio-availability of minerals and improved digestibility",
            "Celebration of Craft: Reviving time-honored artisanal patience in a hurried modern world",
            "Repeatable Excellence: Scientific understanding of variables guarantees consistent masterclass results"
        ]
    },
    "arts_humanities": {
        "badge": "AESTHETIC & PHILOSOPHICAL INQUIRY",
        "subtitle": "Conceptual Architecture, Artistic Movements & Cultural Significance",
        "left_header": "Traditional Dogmas & Conventions:",
        "left_items": [
            "Rigid adherence to academic orthodoxy and narrow classical formulas",
            "Passive consumption of cultural artifacts without critical deconstruction",
            "Siloed boundaries separating fine art, philosophy, and societal discourse"
        ],
        "right_header": "Avant-Garde & Philosophical Synthesis:",
        "right_items": [
            "Disruption of aesthetic conventions through bold conceptual experimentation",
            "Active engagement interrogating meaning, perception, and the human condition",
            "Cross-pollination across literature, visual media, architecture, and music"
        ],
        "core_bullets": [
            "Aesthetic Philosophy: The nature of beauty, sublime experience, and moral meaning",
            "Compositional Rigor: Harmony, negative space, rhythm, tension, and release",
            "Cultural Dialogue: How artistic movements respond to economic and political upheaval",
            "Enduring Influence: Shaping subsequent generations of creators and thinkers"
        ],
        "stats": [
            ("100+", "Years of Continuing Influence", "Timeless Precedent"),
            ("10x", "Expansion of Expressive Form", "Boundary Breaking"),
            ("3+", "Major Cultural Eras Bridged", "Trans-Historical"),
            ("Universal", "Human Condition Impact", "Resonates Globally")
        ],
        "table_headers": ["Aesthetic Dimension", "Academic Formalism", "Avant-Garde Synthesis", "Philosophical Resonance"],
        "table_rows": [
            ["Form & Structure", "Strict geometric symmetry", "Organic, asymmetrical dynamism", "Liberation of creative impulse"],
            ["Subject Matter", "Mythological and aristocratic glorification", "Ordinary human emotion and existential angst", "Universal human empathy"],
            ["Color & Tone", "Chiaroscuro academic rendering", "Vibrant, expressive emotive palettes", "Direct emotional resonance"],
            ["Viewer Engagement", "Detached intellectual appreciation", "Visceral immersive participation", "Deep self-reflection"]
        ],
        "case_bullets": [
            "Creative Genesis: The initial flash of intuition and notebook sketch conceptualization",
            "Material Exploration: Pushing physical mediums beyond their traditional expressive limits",
            "Public Reception: Navigating initial critical controversy before ultimate celebration",
            "Cultural Infiltration: How the movement's aesthetic permeated fashion, architecture, and thought"
        ],
        "phases": [
            "Phase 1: Early Incubation & Rebellion Against Classical Academicism",
            "Phase 2: Collaborative Manifestos & Avant-Garde Experimentation",
            "Phase 3: Public Exhibition, Controversy & Cultural Breakthrough",
            "Phase 4: Institutional Canonical Recognition & Lasting Cultural Legacy"
        ],
        "conclusion": [
            "Transcendent Vision: Re-examines everyday reality through a transformative creative lens",
            "Emotional Catharsis: Provides profound language for unspoken human experiences",
            "Intellectual Courage: Proves that daring to disrupt tradition propels human culture forward",
            "Living Inspiration: Continues to spark curiosity, dialogue, and creation for modern audiences"
        ]
    },
    "education_learning": {
        "badge": "PEDAGOGICAL INNOVATION",
        "subtitle": "Cognitive Science, Student-Centered Learning & Modern Curriculum Design",
        "left_header": "Industrial Factory Model:",
        "left_items": [
            "Passive rote memorization and standardized one-size-fits-all testing",
            "Disengaged students lacking intrinsic curiosity and practical application",
            "Isolated classroom environments detached from real-world collaborative contexts"
        ],
        "right_header": "Active Mastery & Cognitive Architecture:",
        "right_items": [
            "Project-based inquiry cultivating deep conceptual comprehension and problem-solving",
            "Personalized learning pathways adapting to student strengths and pacing",
            "Collaborative studio environments mirroring modern multidisciplinary challenges"
        ],
        "core_bullets": [
            "Cognitive Science Foundations: Spaced repetition, active retrieval, and scaffolding",
            "Inquiry-Based Design: Framing curricula around compelling real-world challenges",
            "Formative Telemetry: Continuous feedback loops replacing stressful high-stakes exams",
            "Inclusive Accessibility: Designing for diverse neuro-types and equitable access"
        ],
        "stats": [
            ("+45%", "Long-Term Concept Retention", "Active Retrieval"),
            ("3.8x", "Student Engagement Multiplier", "Project-Based Learning"),
            ("92%", "Core Competency Mastery", "Personalized Pacing"),
            ("-60%", "Learning Disparity Gap", "Inclusive Scaffolding")
        ],
        "table_headers": ["Pedagogical Vector", "Traditional Lecture Model", "Active Inquiry Learning", "Student Advantage"],
        "table_rows": [
            ["Knowledge Transfer", "Passive listening and transcribing", "Hands-on collaborative problem solving", "Deep conceptual ownership"],
            ["Assessment Mode", "High-stakes multiple choice tests", "Continuous formative portfolios", "Holistic mastery demonstration"],
            ["Role of Educator", "Sole authoritative lecturer", "Facilitator, coach, and research mentor", "Empowered student agency"],
            ["Pacing", "Rigid synchronous calendar deadlines", "Adaptive competency-based progression", "Zero students left behind"]
        ],
        "case_bullets": [
            "Curriculum Re-architecture: Transitioning from textbook chapters to real-world thematic quests",
            "Classroom Transformation: Redesigning physical and digital spaces into interactive creative hubs",
            "Educator Enablement: Training teaching teams in cognitive coaching and formative feedback",
            "Measurable Student Flourishing: Demonstrating dramatic improvements in analytical thought and passion"
        ],
        "phases": [
            "Phase 1: Pedagogical Needs Assessment & Cognitive Framework Design",
            "Phase 2: Curriculum Prototyping & Teacher Training Workshops",
            "Phase 3: Classroom Pilot Implementation & Formative Telemetry",
            "Phase 4: District-Wide Scaling & Continuous Pedagogical Evolution"
        ],
        "conclusion": [
            "Empowered Lifelong Learners: Fosters curiosity, grit, and critical thinking over memorization",
            "Equitable Outcomes: Closes historic achievement gaps by honoring individual learning styles",
            "Future-Ready Competencies: Prepares students for collaboration, creativity, and adaptability",
            "Joy in Discovery: Restores the natural human delight of learning and mastering new horizons"
        ]
    },
    "business_strategy": {
        "badge": "EXECUTIVE STRATEGY",
        "subtitle": "Market Positioning, Operational Velocity & Sustainable Moats",
        "left_header": "Legacy Organizational Friction:",
        "left_items": [
            "Fragmented departmental silos impeding cross-functional velocity",
            "Escalating customer acquisition costs and margin compression",
            "Slow iteration cycles leaving the business vulnerable to agile competitors"
        ],
        "right_header": "High-Velocity Strategic Moat:",
        "right_items": [
            "Unified operational flywheel with automated telemetry and real-time execution",
            "High-retention product experiences driving negative net churn and expanding LTV",
            "Scalable modular infrastructure enabling rapid continuous innovation"
        ],
        "core_bullets": [
            "Market Opportunity: Total addressable market expansion and customer segment dynamics",
            "Product Differentiation: Proprietary capabilities that establish a defensible moat",
            "Go-to-Market Engine: High-efficiency acquisition channels and partner ecosystems",
            "Financial Flywheel: Unit economics, recurring revenue, and cash-flow generation"
        ],
        "stats": [
            ("$24.5M", "Annual Recurring Revenue", "+82% YoY Growth"),
            ("142%", "Net Revenue Retention", "Enterprise Stickiness"),
            ("4.8x", "LTV / CAC Efficiency", "Top Decile Benchmark"),
            ("74%", "Gross Margin Profile", "Software Leverage")
        ],
        "table_headers": ["Strategic Pillar", "Status Quo / Competitors", "Our Accelerated Paradigm", "Competitive Advantage"],
        "table_rows": [
            ["Delivery Velocity", "Quarterly release cadences with high friction", "Continuous autonomous deployment", "10x faster market iteration"],
            ["Customer Experience", "Complex disjointed onboarding", "Zero-touch intuitive product adoption", "Industry-leading NPS (+72)"],
            ["Unit Economics", "High manual overhead eroding margins", "High operating leverage and automation", "65%+ EBITDA margin potential"],
            ["Defensible Moat", "Easily replicable feature sets", "Proprietary data flywheel & network effects", "High customer switching costs"]
        ],
        "case_bullets": [
            "Market Validation: Early enterprise customer cohorts confirming product-market fit",
            "Scaling Operational Rhythms: Instituting cross-functional execution squads with clear OKRs",
            "Channel Expansion: Activating tier-1 strategic partnerships and direct sales pipelines",
            "Capital Allocation: Reinvesting free cash flow into high-ROI R&D and market leadership"
        ],
        "phases": [
            "Phase 1: Foundation, Product-Market Validation & Core Unit Economics",
            "Phase 2: Channel Acceleration & Strategic Tier-1 Enterprise Wins",
            "Phase 3: Multi-Product Platform Expansion & International Growth",
            "Phase 4: Market Category Domination & Free Cash Flow Compounding"
        ],
        "conclusion": [
            "Proven Category Leadership: Rapidly outperforming incumbent alternatives across all metrics",
            "Defensible Long-Term Moat: Network effects and proprietary architecture ensure staying power",
            "Exceptional Capital Efficiency: Generates compounding returns on invested capital",
            "Clear Execution Pathway: Experienced leadership team primed to capture the market opportunity"
        ]
    },
    "finance_economics": {
        "badge": "FINANCIAL & CAPITAL ARCHITECTURE",
        "subtitle": "Market Dynamics, Capital Allocation & Multi-Vector Value Creation",
        "left_header": "Capital Constraints & Inefficiencies:",
        "left_items": [
            "Volatile macroeconomic headwinds and rising cost of capital",
            "Sub-optimal asset allocation with elevated downside exposure",
            "Opaque risk modeling and delayed portfolio telemetry"
        ],
        "right_header": "Disciplined Capital Compounding:",
        "right_items": [
            "Asymmetric risk-reward structuring protecting downside while capturing upside",
            "High-conviction allocation in durable, cash-flow generative assets",
            "Real-time quantitative risk monitoring and automated rebalancing"
        ],
        "core_bullets": [
            "Macroeconomic Landscape: Interest rate trajectories, liquidity, and sectoral shifts",
            "Valuation Frameworks: Discounted cash flows, multiples analysis, and scenario modeling",
            "Risk Management: Hedging downside volatility and maintaining liquidity reserves",
            "Capital Optimization: Reinvestment thresholds, debt service coverage, and shareholder yield"
        ],
        "stats": [
            ("+28.4%", "Annualized Return on Equity", "Top Decile Performance"),
            ("3.6x", "Invested Capital Multiple (MOIC)", "Durable Compounding"),
            ("< 0.45", "Beta to Market Volatility", "Asymmetric Downside Protection"),
            ("$120M+", "Total Capital Under Stewardship", "Disciplined Growth")
        ],
        "table_headers": ["Financial Vector", "Traditional Benchmark", "Our Capital Strategy", "Risk-Adjusted Payoff"],
        "table_rows": [
            ["Yield Profile", "Constrained fixed-income returns", "High-conviction cash-flow compounding", "+450 bps spread"],
            ["Drawdown Resilience", "Deep drawdowns during market corrections", "Systematic downside risk collars", "-60% peak-to-trough drop"],
            ["Capital Efficiency", "Idle cash drag in zero-yield vehicles", "Dynamically optimized liquidity buffers", "Fully utilized capital stack"],
            ["Information Edge", "Lagging retrospective reports", "Real-time quantitative telemetry", "Rapid asymmetric positioning"]
        ],
        "case_bullets": [
            "Opportunity Identification: Screening undervalued market dislocations through proprietary models",
            "Structuring & Execution: Securing favorable capital terms and mitigating downside risks",
            "Active Stewardship: Driving operational efficiencies and margin expansion in target holdings",
            "Value Realization: Disciplined harvesting of gains across optimal market windows"
        ],
        "phases": [
            "Phase 1: Macro Environment Analysis & Capital Sourcing",
            "Phase 2: High-Conviction Deployment & Asymmetric Structuring",
            "Phase 3: Active Operational Stewardship & Value Acceleration",
            "Phase 4: Liquidity Realization, Capital Return & Re-investment"
        ],
        "conclusion": [
            "Durable Wealth Creation: Focus on structural cash flows over speculative momentum",
            "Asymmetric Protection: Rigorous risk management shields capital during downturns",
            "Consistent Outperformance: Disciplined execution generates sustainable alpha over time",
            "Strategic Alignment: Fiduciary rigor ensuring long-term partner and stakeholder success"
        ]
    },
    "technology_ai": {
        "badge": "TECHNICAL ARCHITECTURE",
        "subtitle": "Autonomous Infrastructure, Neural Intelligence & Scalable Engineering",
        "left_header": "Legacy Architecture Bottlenecks:",
        "left_items": [
            "Brittle monolithic systems with cascading failure risks and high latency",
            "Manual release processes slowing developer velocity and team iteration",
            "Fragmented monitoring and telemetry leaving security and performance blind spots"
        ],
        "right_header": "Autonomous Distributed Platform:",
        "right_items": [
            "Decoupled microservices with self-healing auto-scaling and zero-downtime canary rollouts",
            "Automated CI/CD pipelines accelerating deployment velocity by orders of magnitude",
            "Unified end-to-end observability with real-time telemetry and automated anomaly detection"
        ],
        "core_bullets": [
            "Decoupled System Architecture: High-throughput, event-driven distributed microservices",
            "Neural Engine & Intelligence: Context-aware models delivering real-time inferences",
            "Zero-Trust Security: End-to-end cryptographic verification, role isolation, and auditability",
            "Scalability & Resilience: Multi-region redundancy engineered for five-nines availability"
        ],
        "stats": [
            ("99.99%", "High Availability SLA", "Enterprise Resilient"),
            ("< 15ms", "P99 Response Latency", "Edge Accelerated"),
            ("4.6x", "Deployment Velocity Multiplier", "Automated Pipelines"),
            ("68%", "Infrastructure Cost Reduction", "Resource Optimized")
        ],
        "table_headers": ["Technical Dimension", "Legacy Monolithic State", "Modern Distributed Architecture", "Engineering Advantage"],
        "table_rows": [
            ["Deployment Frequency", "Bi-weekly scheduled maintenance windows", "Continuous autonomous canary releases", "Zero user downtime"],
            ["System Latency", "350ms+ database bottleneck latency", "< 15ms distributed edge caching", "20x snappier experience"],
            ["Fault Tolerance", "Single component failure halts the application", "Decoupled circuit breakers and auto-healing", "99.99% uptime"],
            ["Security Stance", "Perimeter firewall with open internal trust", "Zero-trust identity verification at every node", "Zero lateral threat propagation"]
        ],
        "case_bullets": [
            "Migration Strategy: Strangler-fig pattern decomposing legacy services without downtime",
            "Concurrency Stress-Testing: Validating stability under 100,000+ concurrent requests",
            "Observability Telemetry: Tracing distributed requests across microservice boundaries",
            "Production Validation: Smooth failover simulations confirming self-healing capabilities"
        ],
        "phases": [
            "Phase 1: Architecture Blueprint, API Contracts & Core Foundations",
            "Phase 2: Microservice Decoupling, Pipeline Automation & Data Ingestion",
            "Phase 3: Security Hardening, Synthetic Stress-Testing & Pilot Migration",
            "Phase 4: Full Multi-Region Production Cutover & Continuous Optimization"
        ],
        "conclusion": [
            "Architectural Rigor: Modern foundation built to scale effortlessly with exponential growth",
            "Developer Velocity: Eliminates operational friction and lets engineering teams innovate rapidly",
            "Enterprise Reliability: Five-nines resilience ensures uninterrupted global mission-critical uptime",
            "Continuous Evolution: Modular decoupled design allows ongoing enhancement without rewrites"
        ]
    },
    "law_governance": {
        "badge": "GOVERNANCE & POLICY BRIEF",
        "subtitle": "Institutional Frameworks, Constitutional Principles & Civic Accountability",
        "left_header": "Regulatory Fragmentation & Gaps:",
        "left_items": [
            "Outdated statutes failing to address rapid modern technological and societal shifts",
            "Opaque administrative mechanisms diminishing public trust and transparency",
            "Jurisdictional friction and inconsistent enforcement mechanisms"
        ],
        "right_header": "Adaptive Rule of Law Framework:",
        "right_items": [
            "Evidence-based legislative design protecting fundamental rights and equity",
            "Transparent open-governance telemetry providing public oversight and accountability",
            "Harmonized cross-jurisdictional standards promoting legal certainty and trust"
        ],
        "core_bullets": [
            "Constitutional Anchors: Fundamental liberties, checks and balances, and statutory limits",
            "Policy Formulation: Data-driven regulatory frameworks calibrated to public welfare",
            "Compliance & Enforcement: Transparent procedural safeguards and equitable adjudication",
            "Global Governance: Multilateral treaties, international law, and diplomatic harmonization"
        ],
        "stats": [
            ("100%", "Constitutional Compliance", "Verified Precedent"),
            ("3.5x", "Regulatory Transparency Index", "Open Government"),
            ("-48%", "Procedural Dispute Latency", "Streamlined Courts"),
            ("Universal", "Equity & Protection Mandate", "Equal Justice")
        ],
        "table_headers": ["Governance Vector", "Legacy Bureaucracy", "Modern Adaptive Framework", "Public Benefit"],
        "table_rows": [
            ["Regulatory Design", "Rigid, outdated command-and-control rules", "Dynamic, outcome-oriented adaptive policy", "Fosters innovation while protecting rights"],
            ["Public Oversight", "Opaque closed-door administrative decrees", "Real-time open data and public hearings", "Restores civic trust"],
            ["Adjudication Speed", "Multi-year case backlogs and delay", "Digital case management and specialized panels", "Swift access to justice"],
            ["Global Alignment", "Conflicting national regulatory barriers", "Harmonized bilateral and multilateral pacts", "Frictionless international cooperation"]
        ],
        "case_bullets": [
            "Stakeholder Consultation: Engaging civic leaders, legal scholars, and affected communities",
            "Statutory Drafting: Formulating clear, precise language that resists ambiguity and overreach",
            "Institutional Implementation: Establishing oversight ombudsmen and training regulatory bodies",
            "Judicial Review: Demonstrating alignment with constitutional guarantees and human rights charters"
        ],
        "phases": [
            "Phase 1: Policy Research, Stakeholder Hearing & Constitutional Scoping",
            "Phase 2: Statutory Drafting, Impact Assessment & Legislative Debate",
            "Phase 3: Regulatory Enactment, Agency Guidelines & Compliance Training",
            "Phase 4: Ongoing Judicial Review, Oversight Audits & Evolutionary Reform"
        ],
        "conclusion": [
            "Defending the Rule of Law: Anchors democratic governance in fairness and accountability",
            "Future-Proofed Protection: Balances public safety and rights amidst technological change",
            "Institutional Trust: Transparent open processes rebuild crucial public confidence",
            "Lasting Civic Legacy: Creates dependable, just frameworks for generations to come"
        ]
    },
    "general": {
        "badge": "KEYNOTE BRIEFING",
        "subtitle": "Foundational Principles, Strategic Insights & Comprehensive Overview",
        "left_header": "Traditional Constraints & Historical Status Quo:",
        "left_items": [
            "Legacy approaches constrained by outdated assumptions and fragmented execution",
            "Friction points slowing down progress, comprehension, and cross-team alignment",
            "Unaddressed complexities creating unnecessary obstacles to long-term success"
        ],
        "right_header": "Modern Advanced Synthesis:",
        "right_items": [
            "Integrated modern methodology engineered for clarity, rigor, and high impact",
            "Streamlined mechanisms eliminating operational friction and accelerating progress",
            "Holistic, forward-looking perspective driving sustainable excellence and growth"
        ],
        "core_bullets": [
            "Core Foundations: Essential definitions, principles, and historical background",
            "Key Mechanisms: How the primary drivers function and interact with one another",
            "Best Practices: Proven methodologies validated through experience and observation",
            "Future Directions: Emerging opportunities and strategic priorities for the horizon ahead"
        ],
        "stats": [
            ("98.4%", "Foundational Alignment", "Validated Standard"),
            ("3.8x", "Impact Multiplier", "Efficiency Gain"),
            ("4 Core", "Strategic Pillars", "Comprehensive Scope"),
            ("100%", "Quality & Rigor Standard", "Excellence Driven")
        ],
        "table_headers": ["Key Dimension", "Conventional Baseline", "Modern Advanced Approach", "Measurable Advantage"],
        "table_rows": [
            ["Approach & Mindset", "Reactive, fragmented problem-solving", "Proactive, holistic strategic synthesis", "Consistent high-impact results"],
            ["Execution Velocity", "Slow, friction-filled progress", "Streamlined, iterative development", "4x faster turnaround"],
            ["Quality & Depth", "Superficial checklist mentality", "Deep, rigorous mastery of nuances", "Defensible long-term excellence"],
            ["Long-Term Impact", "Diminishing returns over time", "Compounding benefits and sustained growth", "Lasting institutional value"]
        ],
        "case_bullets": [
            "Contextual Framing: Identifying the core challenges, opportunities, and initial conditions",
            "Methodological Execution: Implementing proven principles with discipline and attention to detail",
            "Telemetry & Feedback: Monitoring progress and fine-tuning variables for optimal results",
            "Realized Outcomes: Documenting verifiable improvements in performance, clarity, and satisfaction"
        ],
        "phases": [
            "Phase 1: Discovery, Scoping & Foundational Alignment",
            "Phase 2: Core Formulation, Strategy & Initial Prototyping",
            "Phase 3: Validation, Refinement & Broad Implementation",
            "Phase 4: Maturation, Long-Term Impact & Ongoing Excellence"
        ],
        "conclusion": [
            "Clear Strategic Value: Delivers immediate clarity and actionable insights for all stakeholders",
            "Tested Methodology: Combines theoretical rigor with practical, repeatable execution",
            "Compounding Benefits: Builds lasting capability and defensible advantage over time",
            "Call to Action: Establishes clear ownership and immediate next steps for forward momentum"
        ]
    }
}


class SemanticContentSynthesizer:
    """Synthesizes rich, publication-ready slide decks directly grounded in prompt details, web reference facts, and neural layout planning."""

    @staticmethod
    def synthesize_deck(
        profile: SemanticProfile,
        slide_count: int = 8,
        theme_id: str = "google-gemini",
        template_id: str = "",
        audience: str = "distinguished leadership",
        tone: str = "authoritative & data-driven"
    ) -> Outline:
        """Construct a complete, highly structured presentation outline matching requested slide count and user input."""
        from .neural_engine import plan_deck_archetypes_from_prompt

        slides: List[Slide] = []
        target_count = max(3, min(slide_count, 20))

        # Retrieve domain knowledge base for fallback framing
        dom_data = DOMAIN_KNOWLEDGE.get(profile.domain, DOMAIN_KNOWLEDGE["general"])

        # Extract verified web reference facts and source document sentences
        web_facts = profile.web_facts or {}
        wiki_title = web_facts.get("title") or profile.topic_title
        wiki_desc = web_facts.get("description") or ""
        wiki_facts: List[str] = [f.strip() for f in web_facts.get("key_facts", []) if f and len(f.strip()) > 15]
        wiki_sections: List[Dict[str, Any]] = web_facts.get("sections", []) or []
        wiki_timeline: List[str] = web_facts.get("timeline_events", []) or []
        wiki_quant: List[str] = web_facts.get("quantitative_facts", []) or []

        source_sents: List[str] = []
        if profile.source_text:
            for raw_s in re.split(r'(?<=[.!?])\s+|\n+', profile.source_text):
                s_clean = raw_s.strip().lstrip("•-* ")
                if 20 <= len(s_clean) <= 220 and not s_clean.startswith("---"):
                    source_sents.append(s_clean)

        # Combine all topic-specific factual statements
        all_topic_facts: List[str] = []
        for s in wiki_facts + source_sents:
            if s not in all_topic_facts:
                all_topic_facts.append(s)

        # Neural archetype planning directly from user prompt & subtopics
        neural_plan = plan_deck_archetypes_from_prompt(
            prompt=profile.raw_prompt,
            slide_count=target_count,
            subtopics=profile.key_phrases
        )

        # ----------------------------------------------------------------------
        # Slide 1: Title Slide
        # ----------------------------------------------------------------------
        if wiki_desc and len(wiki_desc) > 10:
            pillars_suffix = f" — {' • '.join(profile.key_phrases[:3])}" if profile.key_phrases else ""
            subtitle_text = f"{wiki_desc[:1].upper() + wiki_desc[1:]}{pillars_suffix}"
        elif profile.technical_pillars:
            pillars_str = " • ".join(profile.technical_pillars[:3])
            subtitle_text = f"Comprehensive Overview: {pillars_str}"
        elif profile.key_phrases:
            subtitle_text = f"Strategic Blueprint: {', '.join(profile.key_phrases[:3])}"
        elif all_topic_facts:
            subtitle_text = all_topic_facts[0][:140]
        else:
            subtitle_text = dom_data["subtitle"]

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="title",
            category=dom_data["badge"],
            title=profile.topic_title,
            subtitle=subtitle_text,
            bullets=[],
            notes=(
                f"Welcome distinguished attendees. Today's presentation examines '{profile.topic_title}'. "
                f"{all_topic_facts[0] if all_topic_facts else 'Over the course of this deck, we will review the foundational principles, empirical evidence, and strategic roadmap.'}"
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 2: Comparative Context & Foundations (Two Column)
        # ----------------------------------------------------------------------
        left_items: List[str] = []
        right_items: List[str] = []

        # Check if user explicitly asked for "A vs B" comparison
        vs_match = re.search(r'([A-Za-z0-9\s\-]{3,35})\s+(?:vs\.?|versus|compared\s+to|or)\s+([A-Za-z0-9\s\-]{3,35})', profile.raw_prompt, re.I)
        if vs_match:
            side_a = vs_match.group(1).strip().title()
            side_b = vs_match.group(2).strip().title()
            left_items.append(f"{side_a} Architecture: Foundational characteristics and baseline operating model")
            left_items.append(f"Primary Tradeoffs: Resource, scalability, and complexity considerations for {side_a}")
            left_items.append(f"Use-Case Fit: Scenarios where {side_a} remains the conventional choice")
            right_items.append(f"{side_b} Paradigm: Modern capabilities and differentiated performance profile")
            right_items.append(f"Strategic Advantages: Throughput, agility, and efficiency unlocked by {side_b}")
            right_items.append(f"Adoption Trajectory: Why organizations are standardizing on {side_b}")
            comp_title = f"Comparative Analysis: {side_a} vs. {side_b}"
        else:
            comp_title = f"{profile.topic_title}: Core Context & Strategic Evolution"
            if profile.pain_points:
                for p in profile.pain_points[:3]:
                    left_items.append(f"Core Challenge: {p.rstrip('.')}")
            elif all_topic_facts:
                left_items.append(f"Foundational Premise: {all_topic_facts[0]}")
                if len(all_topic_facts) > 1:
                    left_items.append(f"Historical Context: {all_topic_facts[1]}")
                left_items.append(f"Baseline Constraints: Traditional limits before modern advances in {profile.clean_topic}")
            elif profile.key_phrases:
                left_items.append(f"Baseline Constraint: Fragmented approaches to {profile.key_phrases[0]}")
                left_items.append(f"Legacy Ceiling: Traditional methods struggle to scale across {profile.clean_topic}")
                left_items.append("Complexity Barrier: Rising friction impeding rapid comprehension and execution")
            else:
                left_items = list(dom_data["left_items"])

            if profile.solutions:
                for s in profile.solutions[:3]:
                    right_items.append(f"Strategic Advance: {s.rstrip('.')}")
            elif len(all_topic_facts) >= 3:
                right_items.append(f"Key Mechanism: {all_topic_facts[2]}")
                if len(all_topic_facts) >= 4:
                    right_items.append(f"Empirical Insight: {all_topic_facts[3]}")
                right_items.append(f"Modern Synthesis: High-impact application of {profile.topic_title}")
            elif len(profile.key_phrases) >= 2:
                for kp in profile.key_phrases[:3]:
                    right_items.append(f"Strategic Focus — {kp.title()}: Integrated methodology tailored for {profile.clean_topic}")
            else:
                right_items = list(dom_data["right_items"])

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="two_column",
            category=f"{dom_data['badge']} - CONTEXT",
            title=comp_title,
            subtitle=f"Evaluating foundational principles and modern advances for {profile.clean_topic}",
            left=left_items[:4],
            right=right_items[:4],
            notes=(
                f"On this slide, contrast the foundational context with modern developments in {profile.topic_title}. "
                f"Highlight how each dimension directly addresses the priorities of {audience}."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 3: Core Architecture & Primary Mechanisms (Image & Text)
        # ----------------------------------------------------------------------
        arch_bullets: List[str] = []
        sec_0_title = f"Core Mechanisms & Foundational Principles of {profile.topic_title}"
        if wiki_sections:
            sec0 = wiki_sections[0]
            sec_0_title = f"{profile.topic_title}: {sec0['heading']}"
            arch_bullets.extend(sec0.get("bullets", [])[:4])

        if len(arch_bullets) < 4 and profile.key_phrases:
            for p in profile.key_phrases[:4]:
                candidate = f"{p.strip().title()}: Critical pillar driving capability and outcomes in {profile.clean_topic}"
                if candidate not in arch_bullets:
                    arch_bullets.append(candidate)

        if len(arch_bullets) < 4 and all_topic_facts:
            for f in all_topic_facts[:5]:
                if f not in arch_bullets:
                    arch_bullets.append(f)

        if not arch_bullets:
            arch_bullets = list(dom_data["core_bullets"])

        while len(arch_bullets) < 3:
            arch_bullets.append(f"Systemic Integration: Harmonizing execution variables across {profile.clean_topic}")

        from .architecture_engine import synthesize_diagram_spec, draw_architecture_diagram_png
        diag_spec = synthesize_diagram_spec(
            topic=profile.topic_title,
            prompt=profile.raw_prompt,
            bullets=arch_bullets[:4],
        )
        arch_png = draw_architecture_diagram_png(
            diagram=diag_spec,
            title=f"{profile.topic_title}: System Architecture",
            subtitle=f"End-to-End Component Topology & Dataflow for {profile.clean_topic}",
        )

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="diagram",
            category=f"{dom_data['badge']} - ARCHITECTURE",
            title=f"Architecture Blueprint & Component Topology: {profile.topic_title[:38]}",
            subtitle=f"Layered architecture, dataflow channels, and core mechanisms driving {profile.clean_topic}",
            bullets=arch_bullets[:4],
            visual=Visual(kind="architecture", diagram=diag_spec),
            image_url=arch_png.get("url", ""),
            image_id=arch_png.get("filename", ""),
            image_caption=f"Architecture Blueprint: {wiki_title}",
            notes=(
                f"Walk the {audience} through the multi-tier architecture of {profile.topic_title}, "
                f"explaining how requests flow across {', '.join(n.label for n in diag_spec.nodes[:4])}."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 4: Quantifiable Benchmarks & Empirical Proof (Metrics)
        # ----------------------------------------------------------------------
        stats_list: List[StatItem] = []
        if profile.numerical_entities:
            for val, lbl in profile.numerical_entities[:4]:
                stats_list.append(StatItem(value=val, label=lbl, change=f"{profile.topic_title[:22]} Metric"))

        # Extract numeric facts from Wikipedia quantitative sentences if available
        if len(stats_list) < 4 and (wiki_quant or all_topic_facts):
            for fact in (wiki_quant + all_topic_facts):
                if len(stats_list) >= 4:
                    break
                m = re.search(r'(\b\d+(?:\.\d+)?(?:\s*%|\s*billion|\s*million|\s*trillion|\s*GW|\s*MW|\s*km|\s*x|\b))', fact, re.I)
                if m:
                    val_str = m.group(1).strip()
                    # Build concise label from surrounding words
                    words_after = fact[m.end():].strip(" ,.;:()").split()[:4]
                    words_before = fact[:m.start()].strip(" ,.;:()").split()[-3:]
                    lbl_str = " ".join(words_after if len(words_after) >= 2 else words_before).title().strip()
                    if len(lbl_str) >= 4 and not any(s.value == val_str for s in stats_list):
                        stats_list.append(StatItem(
                            value=val_str[:14],
                            label=lbl_str[:34],
                            change=f"Verified ({wiki_title[:20]})"
                        ))

        for val, lbl, chg in dom_data["stats"]:
            if len(stats_list) >= 4:
                break
            if not any(s.label.lower() == lbl.lower() for s in stats_list):
                stats_list.append(StatItem(value=val, label=lbl, change=chg))

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="metrics",
            category=f"{dom_data['badge']} - EVIDENCE",
            title=f"Empirical Benchmarks & Key Indicators: {profile.topic_title[:42]}",
            subtitle=f"Validated figures and performance indicators characterizing {profile.clean_topic}",
            stats=stats_list[:4],
            notes=(
                f"Present these 4 core metrics to establish empirical credibility for {profile.topic_title}."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 5: Structural Comparison Matrix (Table)
        # ----------------------------------------------------------------------
        table_headers = [f"{profile.topic_title[:22]} Dimension", "Baseline / Legacy State", "Modern / Advanced State", "Strategic Impact"]
        table_rows: List[List[str]] = []

        if profile.key_phrases:
            for kp in profile.key_phrases[:4]:
                kp_title = kp.strip().title()[:32]
                table_rows.append([
                    kp_title,
                    f"Fragmented, manual constraints in {kp.lower()}",
                    f"Integrated, high-precision {kp.lower()} framework",
                    f"High-impact gain in {profile.clean_topic[:25]}"
                ])
        elif wiki_sections:
            for sec in wiki_sections[:4]:
                sec_head = sec["heading"][:32]
                first_b = sec["bullets"][0][:65] if sec.get("bullets") else f"Core aspect of {profile.clean_topic}"
                table_rows.append([
                    sec_head,
                    f"Early foundational stage of {sec_head.lower()}",
                    first_b,
                    f"Key driver for {profile.topic_title[:22]}"
                ])

        for r in dom_data["table_rows"]:
            if len(table_rows) >= 4:
                break
            table_rows.append(r)

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="table",
            category=f"{dom_data['badge']} - MATRIX",
            title=f"Structural Evaluation Matrix: {profile.topic_title[:45]}",
            subtitle=f"Multi-dimensional breakdown across core vectors of {profile.clean_topic}",
            table=TableSpec(headers=table_headers, rows=table_rows[:4]),
            notes=(
                f"Review this comparative evaluation matrix for {profile.topic_title} with the {audience}."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 6: Real-World Demonstration & Case Study (Image & Text)
        # ----------------------------------------------------------------------
        app_bullets: List[str] = []
        sec_1_title = f"Real-World Applications & Case Study: {profile.topic_title[:42]}"
        if len(wiki_sections) >= 2:
            sec1 = wiki_sections[1]
            sec_1_title = f"{profile.topic_title}: {sec1['heading']}"
            app_bullets.extend(sec1.get("bullets", [])[:4])

        if len(app_bullets) < 4 and profile.solutions:
            for s in profile.solutions:
                app_bullets.append(f"Applied Implementation: {s.rstrip('.')}")

        if len(app_bullets) < 4 and len(all_topic_facts) > 2:
            for f in all_topic_facts[2:6]:
                if f not in app_bullets:
                    app_bullets.append(f)

        if not app_bullets:
            app_bullets = list(dom_data["case_bullets"])

        while len(app_bullets) < 3:
            app_bullets.append(f"Operational Validation: Practical deployment across {profile.clean_topic}")

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="image_text",
            category=f"{dom_data['badge']} - CASE STUDY",
            title=sec_1_title[:85],
            subtitle=f"Field validation and real-world impact across {profile.clean_topic}",
            bullets=app_bullets[:4],
            image_caption=f"Operational Demonstration: {wiki_title}",
            notes=(
                f"Walk through these practical applications of {profile.topic_title} to ground the presentation in real-world evidence."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 7: Phased Milestones & Roadmap (Timeline)
        # ----------------------------------------------------------------------
        timeline_bullets: List[str] = []
        if wiki_timeline:
            for i, ev in enumerate(wiki_timeline[:4]):
                yr_m = re.search(r'\b(18\d\d|19\d\d|20\d\d)\b', ev)
                prefix = f"Milestone {yr_m.group(1)}" if yr_m else f"Phase {i + 1}"
                timeline_bullets.append(f"{prefix}: {ev[:110]}")
        elif len(profile.key_phrases) >= 3:
            for i, kp in enumerate(profile.key_phrases[:4]):
                timeline_bullets.append(f"Phase {i + 1} — {kp.strip().title()}: Structured execution and validation for {profile.clean_topic}")

        if len(timeline_bullets) < 4:
            for p in dom_data["phases"]:
                if len(timeline_bullets) >= 4:
                    break
                timeline_bullets.append(p)

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="timeline",
            category=f"{dom_data['badge']} - ROADMAP",
            title=f"Chronological Evolution & Phased Roadmap: {profile.topic_title[:38]}",
            subtitle=f"Key milestones and structured progression for {profile.clean_topic}",
            bullets=timeline_bullets[:4],
            notes=(
                f"Guide the {audience} through the chronological milestones and execution phases of {profile.topic_title}."
            )
        ))

        # ----------------------------------------------------------------------
        # Slide 8: Strategic Takeaways & Executive Summary (Conclusion)
        # ----------------------------------------------------------------------
        conclusion_bullets: List[str] = []
        if all_topic_facts:
            conclusion_bullets.append(f"Core Synthesis: {all_topic_facts[0]}")
        if profile.key_phrases:
            conclusion_bullets.append(
                f"Priority Focus Areas: Mastering {', '.join(profile.key_phrases[:3])} drives long-term success in {profile.clean_topic}."
            )
        for c_item in dom_data["conclusion"]:
            if len(conclusion_bullets) >= 4:
                break
            conclusion_bullets.append(c_item)

        slides.append(Slide(
            id=uuid.uuid4().hex[:10],
            type="conclusion",
            category=f"{dom_data['badge']} - TAKEAWAYS",
            title=f"Executive Summary & Strategic Takeaways: {profile.topic_title[:38]}",
            subtitle=f"Unlocking transformative outcomes and enduring impact for {profile.topic_title}",
            bullets=conclusion_bullets[:4],
            notes=(
                f"Conclude the presentation by reinforcing the core thesis on {profile.topic_title} and outlining immediate next steps."
            )
        ))

        # Adjust slides to match target_count while honoring neural archetype predictions
        if target_count < len(slides):
            # Always keep Title (0) and Conclusion (-1), and pick middle slides matching neural_plan archetypes
            middle_pool = slides[1:-1]
            selected_middle: List[Slide] = []
            needed_middle = target_count - 2
            for slot in neural_plan[1:-1]:
                if len(selected_middle) >= needed_middle:
                    break
                desired_arch = slot["archetype"]
                match = next(
                    (s for s in middle_pool if s not in selected_middle and (s.type == desired_arch or (desired_arch == "bullets" and s.type == "image_text"))),
                    None
                )
                if match:
                    selected_middle.append(match)
            for s in middle_pool:
                if len(selected_middle) >= needed_middle:
                    break
                if s not in selected_middle:
                    selected_middle.append(s)
            final_slides = [slides[0]] + selected_middle + [slides[-1]]
        elif target_count > len(slides):
            final_slides = list(slides)
            extra_needed = target_count - len(slides)

            # Insert Quote slide
            quote_text = (
                all_topic_facts[-1]
                if len(all_topic_facts) >= 3
                else (
                    f"Mastery in {profile.topic_title} is not an accident of fortune, "
                    f"but the natural result of disciplined inquiry, empirical rigor, and tireless execution."
                )
            )
            quote_slide = Slide(
                id=uuid.uuid4().hex[:10],
                type="quote",
                category=f"{dom_data['badge']} - PERSPECTIVE",
                title=f"Guiding Perspective on {profile.topic_title[:48]}",
                subtitle="Foundational wisdom shaping modern thought and execution",
                quote=quote_text,
                notes=f"Share this guiding perspective with attendees to frame the deeper impact of {profile.topic_title}."
            )
            final_slides.insert(4, quote_slide)
            extra_needed -= 1

            # Insert additional topic-specific section or subtopic slides up to target_count
            sec_cursor = 2
            while extra_needed > 0:
                idx = len(final_slides) - 1
                if sec_cursor < len(wiki_sections):
                    sec = wiki_sections[sec_cursor]
                    sec_cursor += 1
                    s_title = f"{profile.topic_title}: {sec['heading']}"
                    s_bullets = sec.get("bullets", [])[:4]
                else:
                    s_title = f"Deep Dive & Strategic Pillars: {profile.topic_title[:42]}"
                    s_bullets = [
                        f"Foundational Discipline: Ensuring strict fidelity to evidence-based principles in {profile.clean_topic}",
                        "Cross-Functional Alignment: Coordinating execution across key stakeholders",
                        "Risk Mitigation: Preemptive identification and hedging of systemic vulnerabilities",
                        "Continuous Evolution: Institutionalizing regular audits and iterative improvements"
                    ]
                new_s = Slide(
                    id=uuid.uuid4().hex[:10],
                    type="bullets",
                    category=f"{dom_data['badge']} - DEEP DIVE",
                    title=s_title[:85],
                    subtitle=f"Core operational imperatives and insights for {profile.clean_topic}",
                    bullets=s_bullets,
                    notes=f"Examine these key dimensions of {profile.topic_title} in detail."
                )
                final_slides.insert(idx, new_s)
                extra_needed -= 1
        else:
            final_slides = slides

        return Outline(
            title=profile.topic_title,
            subtitle=subtitle_text,
            theme_id=theme_id,
            template_id=template_id,
            slides=final_slides
        )


# ==============================================================================
# 3. Contextual Visual Asset Director
# ==============================================================================

class VisualAssetDirector:
    """Enriches presentation slides with tailored high-resolution imagery."""

    @staticmethod
    def enrich_deck_visuals(
        outline: Outline,
        topic: str,
        image_style: str = "3d",
        preferred_provider: str = "stock",
        api_key: str = ""
    ) -> Outline:
        """Scan slides and auto-generate hero and content visuals where appropriate."""
        if not outline.slides:
            return outline

        slides_to_visualize = []

        # Title slide hero visual
        if not outline.slides[0].image_url:
            slides_to_visualize.append((
                0,
                outline.slides[0].title,
                outline.slides[0].category or "HERO KEYNOTE"
            ))

        # Content Visuals: prioritize slides explicitly designed for imagery (image_text or custom LLM visual prompt)
        content_visual_count = 0
        for idx in range(1, len(outline.slides)):
            s = outline.slides[idx]
            # If slide is an architecture diagram, ensure its blueprint PNG is rendered without overriding slide.type
            if s.type == "diagram" or (s.visual and s.visual.diagram and s.visual.diagram.nodes):
                s.type = "diagram"
                if not s.image_url:
                    try:
                        from .architecture_engine import draw_architecture_diagram_png, synthesize_diagram_spec
                        dspec = (
                            s.visual.diagram
                            if (s.visual and s.visual.diagram and s.visual.diagram.nodes)
                            else synthesize_diagram_spec(s.title or topic, bullets=s.bullets)
                        )
                        s.visual = Visual(kind="architecture", diagram=dspec)
                        arch_img = draw_architecture_diagram_png(dspec, title=s.title or topic, subtitle=s.subtitle)
                        s.image_url = arch_img.get("url", "")
                        s.image_id = arch_img.get("filename", "")
                        s.image_caption = arch_img.get("caption", s.title)
                    except Exception as de:
                        print(f"[VisualAssetDirector] Diagram PNG render warning: {de}")
                continue

            # Protect structured multi-card/table layouts from being overridden
            if s.type in ("metrics", "table", "two_column", "timeline", "diagram"):
                continue

            has_llm_prompt = bool(s.visual and s.visual.image and s.visual.image.prompt)
            if (
                s.type == "image_text"
                or has_llm_prompt
                or "FOUNDATIONS" in s.category
                or "CASE STUDY" in s.category
                or (s.bullets and content_visual_count < 2)
            ):
                slides_to_visualize.append((idx, s.title, s.category or "VISUAL CONCEPT"))
                content_visual_count += 1
                if content_visual_count >= 3:
                    break

        # Generate and attach images
        for slide_idx, title_context, cat in slides_to_visualize:
            slide = outline.slides[slide_idx]
            if slide.image_url:
                continue

            llm_img_prompt = (
                slide.visual.image.prompt
                if (slide.visual and slide.visual.image and slide.visual.image.prompt)
                else ""
            )
            custom_prompt = llm_img_prompt or f"Keynote visual asset depicting {title_context} for {topic}"
            try:
                img_data = generate_slide_image(
                    slide_title=title_context,
                    topic=topic,
                    category=cat,
                    style=image_style or "3d",
                    custom_prompt=custom_prompt,
                    preferred_provider=preferred_provider,
                    api_key=api_key
                )
                if img_data and img_data.get("url"):
                    slide.image_url = img_data["url"]
                    slide.image_id = img_data.get("filename", "")
                    if not slide.image_caption:
                        slide.image_caption = img_data.get("caption", title_context)
                    if slide.type not in ("title", "image_text"):
                        slide.type = "image_text"
                    if slide.type == "image_text" and not slide.bullets:
                        if slide.left or slide.right:
                            slide.bullets = (slide.left or []) + (slide.right or [])
                        elif slide.subtitle:
                            slide.bullets = [slide.subtitle, "Foundational principles", "Verified implementation"]
            except Exception as e:
                print(f"[VisualAssetDirector] Image generation error on slide {slide_idx}: {e}")

        return outline


# ==============================================================================
# 4. Master AIPresentationAgent Facade
# ==============================================================================

class AIPresentationAgent:
    """Primary autonomous agent orchestrating strategic planning, content synthesis, and visual generation."""

    def __init__(self):
        self.synthesizer = SemanticContentSynthesizer()
        self.visual_director = VisualAssetDirector()

    def generate_presentation(self, request: ChatRequest) -> Tuple[Outline, str, Optional[int]]:
        """Synthesize a complete presentation deck grounded in prompt details and populated with visuals."""
        # 1. Parse prompt and attached context
        combined_sources = ""
        if request.attachments:
            combined_sources = "\n\n".join(
                f"--- Document: {a.filename} ---\n{a.extracted_text}"
                for a in request.attachments if a.extracted_text
            )

        # Detect slide count from user prompt if explicitly mentioned (e.g. "make a 5 slide presentation")
        count_match = re.search(r'(\d+)\s*[-_]?\s*slides?', request.prompt, re.IGNORECASE)
        effective_slide_count = int(count_match.group(1)) if count_match else request.slide_count
        effective_slide_count = max(3, min(effective_slide_count, 20))

        profile = extract_semantic_profile(request.prompt, combined_sources)

        # 1b. Ground in live web reference knowledge (Wikipedia & verified empirical facts)
        web_facts = None
        try:
            from .web_search_service import fetch_web_reference
            web_facts = fetch_web_reference(profile.clean_topic)
            if web_facts and web_facts.get("extract"):
                profile.web_facts = web_facts
                web_note = (
                    f"\n\n--- Verified Web Reference ({web_facts.get('title', profile.clean_topic)}) ---\n"
                    f"{web_facts.get('extract', '')}\nKey Empirical Facts:\n" +
                    "\n".join(f"• {f}" for f in web_facts.get("key_facts", []))
                )
                combined_sources = (combined_sources + web_note).strip()
        except Exception as e:
            print(f"[AIPresentationAgent] Web grounding fetch failed: {e}")

        # 2. Try LLM generation (OpenAI / Gemini / Claude / Grok / OpenAI Cloud Relay)
        outline, provider_used, model_used = self._try_llm_generation(
            request, combined_sources, profile, effective_slide_count
        )

        # 3. Autonomous Semantic Engine Fallback if LLM unavailable or failed
        if not outline or not outline.slides:
            outline = self.synthesizer.synthesize_deck(
                profile=profile,
                slide_count=effective_slide_count,
                theme_id=request.theme_id or "google-gemini",
                template_id=request.template_id,
                audience=request.audience,
                tone=request.tone
            )

        # 3b. Ensure architecture diagram is populated & drawn when requested or in multi-slide decks
        p_low = request.prompt.lower()
        wants_arch = any(
            k in p_low
            for k in ["architecture", "diagram", "draw", "blueprint", "flowchart", "system design", "plan", "ideas", "topology"]
        )
        has_diag_slide = any(
            s.type == "diagram" or (s.visual and s.visual.diagram and s.visual.diagram.nodes)
            for s in outline.slides
        )
        if not has_diag_slide and (wants_arch or len(outline.slides) >= 5):
            try:
                from .architecture_engine import synthesize_diagram_spec, draw_architecture_diagram_png
                target_idx = min(2, len(outline.slides) - 1)
                target_s = outline.slides[target_idx]
                dspec = synthesize_diagram_spec(
                    topic=outline.title or profile.topic_title,
                    prompt=request.prompt,
                    bullets=target_s.bullets or target_s.left,
                )
                arch_img = draw_architecture_diagram_png(
                    diagram=dspec,
                    title=f"{outline.title}: Architecture Blueprint",
                    subtitle=target_s.subtitle or f"End-to-End Topology & Dataflow",
                )
                if wants_arch:
                    target_s.type = "diagram"
                    target_s.category = "ARCHITECTURE BLUEPRINT"
                    if "architecture" not in target_s.title.lower():
                        target_s.title = f"System Architecture & Component Flow: {profile.topic_title[:36]}"
                    target_s.visual = Visual(kind="architecture", diagram=dspec)
                    target_s.image_url = arch_img.get("url", "")
                    target_s.image_id = arch_img.get("filename", "")
                else:
                    # Convert one middle bullets/image_text slide to diagram if deck has >= 6 slides
                    for cand_s in outline.slides[1:-1]:
                        if cand_s.type in ("bullets", "image_text"):
                            cand_s.type = "diagram"
                            cand_s.category = "SYSTEM ARCHITECTURE"
                            cand_s.visual = Visual(kind="architecture", diagram=dspec)
                            cand_s.image_url = arch_img.get("url", "")
                            cand_s.image_id = arch_img.get("filename", "")
                            break
            except Exception as arch_e:
                print(f"[AIPresentationAgent] Architecture enrichment note: {arch_e}")

        # 4. Visual Asset Enrichment (Auto-generate required hero and content visuals)
        if request.auto_generate_images:
            image_provider = request.preferred_image_provider or (
                "openai" if provider_used == "openai" and request.preferred_image_provider in ("openai", "dalle", "ai") else "web"
            )
            outline = self.visual_director.enrich_deck_visuals(
                outline=outline,
                topic=profile.topic_title,
                image_style=request.image_style or "3d",
                preferred_provider=image_provider,
                api_key=request.api_key or ""
            )

        # 5. Build response message (with Architecture Understanding, Plan & Ideas when applicable)
        slide_count = len(outline.slides)
        provider_badge = (
            f" [Synthesized with {'OpenAI' if provider_used == 'openai' else provider_used.upper()} ({model_used})]"
            if provider_used
            else ""
        )
        web_badge = f" [Grounded in {web_facts['title']} Web Reference]" if web_facts else ""
        response_msg = (
            f"✨ AI Presentation Agent has synthesized your {slide_count}-slide presentation "
            f"on '{outline.title}'{provider_badge}{web_badge} with architecture diagrams, domain narratives, empirical benchmarks, and visual assets."
        )

        if wants_arch:
            try:
                from .architecture_engine import generate_architecture_blueprint, format_architecture_chat_summary
                bp = generate_architecture_blueprint(
                    prompt=request.prompt,
                    topic=outline.title or profile.topic_title,
                    api_key=request.api_key,
                    provider=request.provider,
                    model=request.model,
                    base_url=request.base_url,
                    draw_image=False,
                )
                response_msg = f"{response_msg}\n\n{format_architecture_chat_summary(bp)}"
            except Exception as bp_e:
                print(f"[AIPresentationAgent] Summary formatting note: {bp_e}")

        return (outline, response_msg, 0)

    def _try_llm_generation(
        self,
        request: ChatRequest,
        combined_sources: str,
        profile: SemanticProfile,
        target_slide_count: int = 6
    ) -> Tuple[Optional[Outline], str, str]:
        """Attempt structured LLM synthesis via OpenAI, Gemini, Claude, Grok, or custom gateway."""
        template_hint = ""
        if request.template_id:
            try:
                from ..config import TEMPLATES_DIR
                from .reverse_engineering_engine import reverse_engineer_template
                matches = list(TEMPLATES_DIR.glob(f"{request.template_id}.*"))
                if matches:
                    tmeta = reverse_engineer_template(matches[0], request.template_id)
                    proto_summary = ", ".join(
                        f"Slide {p.slide_index + 1}: {p.archetype} ({p.shapes_count} shapes)"
                        for p in tmeta.all_slide_prototypes[:8]
                    )
                    template_hint = (
                        f"\nUPLOADED PPTX TEMPLATE DESIGN CONSTRAINTS:\n"
                        f"- Template Style: {'Dark background' if tmeta.is_dark_theme else 'Light background'}, "
                        f"Fonts: {tmeta.title_font} / {tmeta.body_font}\n"
                        f"- Available Prototype Archetypes: {proto_summary}\n"
                        f"- Craft concise, high-impact titles (<= 9 words) and crisp bullets (12-22 words each) "
                        f"so text fits the template's bounding boxes cleanly without overflow.\n"
                    )
            except Exception as te:
                print(f"[AIPresentationAgent] Template inspection hint skipped: {te}")

        neural_plan_hint = ""
        try:
            from .neural_engine import plan_deck_archetypes_from_prompt
            n_plan = plan_deck_archetypes_from_prompt(
                prompt=request.prompt,
                slide_count=target_slide_count,
                subtopics=profile.key_phrases
            )
            plan_lines = ", ".join(
                f"Slide {p['slide_index'] + 1}: {p['archetype']} ({p['confidence_percent']}% match)"
                for p in n_plan
            )
            neural_plan_hint = (
                f"\nNEURAL LAYOUT CLASSIFIER BLUEPRINT:\n"
                f"- Recommended Slide Archetype Sequence: {plan_lines}\n"
            )
            if profile.key_phrases:
                neural_plan_hint += f"- User-Requested Subtopics to Cover: {', '.join(profile.key_phrases[:8])}\n"
        except Exception:
            pass

        system_instruction = f"""You are an elite executive presentation strategist and keynote designer.
Create a deeply researched, publication-ready {target_slide_count}-slide PowerPoint presentation on: "{profile.topic_title}".
Audience: {request.audience or 'Executive & Technical Stakeholders'}
Tone: {request.tone or 'Authoritative, insightful, and clear'}
Visual Theme: {request.theme_id or 'google-gemini'}
{template_hint}{neural_plan_hint}
STRICT JSON OUTPUT SCHEMA:
Return ONLY a valid JSON object matching this exact structure (no markdown commentary):
{{
  "title": "Compelling Deck Main Title",
  "subtitle": "Executive framing subtitle (12-20 words)",
  "slides": [
    {{
      "type": "title | bullets | diagram | image_text | two_column | metrics | table | timeline | quote | conclusion",
      "category": "UPPERCASE BADGE TAG (e.g. STRATEGIC OVERVIEW, SYSTEM ARCHITECTURE)",
      "title": "Action-oriented Slide Headline",
      "subtitle": "Concise 1-sentence framing takeaway",
      "bullets": ["Lead Term: Specific factual insight with concrete details (14-24 words)", "..."],
      "left": ["Left Column Header / Point 1", "Point 2", "Point 3"],
      "right": ["Right Column Header / Point 1", "Point 2", "Point 3"],
      "stats": [
        {{"value": "3.8x", "label": "Metric Name", "change": "+42% YoY benchmark"}}
      ],
      "diagram": {{
        "direction": "LR",
        "clusters": [{{"id": "c1", "label": "1. Tier Name"}}],
        "nodes": [{{"id": "n1", "label": "Component Name", "shape": "user|process|cloud|database|queue|decision", "cluster": "c1"}}],
        "edges": [{{"source": "n1", "target": "n2", "label": "Flow / Protocol"}}]
      }},
      "table": {{
        "headers": ["Dimension", "Legacy / Baseline", "Modern / Proposed", "Impact"],
        "rows": [
          ["Row 1 Name", "Baseline detail", "Target detail", "Quantified gain"]
        ]
      }},
      "quote": "Memorable synthesis statement if type is quote",
      "image_caption": "Caption for visual slide",
      "image_prompt": "Detailed widescreen visual scene description for DALL-E 3 / diffusion (no text in image)",
      "notes": "2-4 sentences of natural executive speaker notes for presenting this slide"
    }}
  ]
}}

CONTENT & LAYOUT RULES:
1. Generate EXACTLY {target_slide_count} slides.
2. Slide 1 MUST have "type": "title" with a strong title, subtitle, category badge, and an "image_prompt" for the hero visual.
3. Use a rich variety of middle slide types across the deck: include at least one "image_text", one "metrics" (with 3-4 concrete stats), one "two_column" (populated "left" and "right" lists of 3-4 items each), and when {target_slide_count} >= 6 include a "table" (3-4 columns, 3-4 rows) or "timeline" (4 sequential milestone bullets formatted as "Phase 1 — Name: Outcome").
4. Final slide should be "conclusion" or strategic next-steps roadmap with concrete action items.
5. Every fact, metric, comparison, and bullet MUST be authentically tailored to "{profile.topic_title}" and grounded in the user's prompt & context documents — NEVER use generic filler or placeholder text.
6. Populate "image_prompt" on the title slide and any "image_text" slides with a vivid, topic-specific visual prompt."""

        user_prompt = f"""Topic: "{profile.topic_title}"
User Request: "{request.prompt}"
Target Slide Count: {target_slide_count}

Context & Grounding Reference:
{combined_sources if combined_sources else "(No external documents attached — synthesize authoritative domain knowledge, real-world metrics, and concrete examples directly relevant to the user's request.)"}

Return the complete {target_slide_count}-slide JSON presentation object now."""

        try:
            data, prov_used, mod_used = call_llm_json_with_meta(
                system_instruction=system_instruction,
                user_prompt=user_prompt,
                api_key=request.api_key,
                temperature=0.65,
                provider=request.provider,
                model=request.model,
                base_url=request.base_url,
            )

            if data and isinstance(data, dict):
                normalized = normalize_outline_payload(data, fallback_title=profile.topic_title)
                if normalized.get("slides"):
                    ai_outline = AIOutline(**normalized)
                    slides = [Slide(**s.model_dump(), id=uuid.uuid4().hex[:10]) for s in ai_outline.slides]
                    return (
                        Outline(
                            title=ai_outline.title or profile.topic_title,
                            subtitle=ai_outline.subtitle,
                            theme_id=request.theme_id or "google-gemini",
                            template_id=request.template_id or "",
                            slides=slides
                        ),
                        prov_used,
                        mod_used,
                    )
        except Exception as e:
            print(f"[AIPresentationAgent] LLM Gateway synthesis note: {e}. Activating Autonomous Domain Synthesis Engine.")

        return (None, "", "")


# Global singleton instance of the agent
presentation_agent = AIPresentationAgent()
