import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Sparkles, Upload, Wand2, Download, Eye, Palette, CheckCircle2,
  Globe, Sliders, FileText, Plus, RefreshCw, Trash2, Layout,
  ArrowRight, Cpu, Check
} from 'lucide-react';
import { THEMES } from '../themes';

export default function TemplateDesignGenerator({
  apiKey,
  aiProvider = 'openai',
  aiModel = 'gpt-4o-mini',
  aiBaseUrl = '',
  onOpenStudio,
  onOpenThemes,
  onOpenSettings,
  onStartBlank,
  onSelectProject,
  onDeleteProject,
  recentProjects = [],
  onPresentationGenerated,
  activeThemeId = 'google-gemini',
  onSelectTheme
}) {
  const TOPIC_PRESETS = [
    {
      label: '🤖 AI & Automation',
      topic: 'Artificial Intelligence & The Future of Human Work',
      prompt: 'Autonomous reasoning agents, human-AI collaboration, cognitive augmentation, productivity leaps, and workforce evolution.',
      audience: 'executive C-suite stakeholders & board',
      tone: 'authoritative, technical & data-driven'
    },
    {
      label: '🌿 Clean Tech & Energy',
      topic: 'The Global Renewable Energy Transition',
      prompt: 'Grid-scale battery storage, wind and solar parity, circular economy design, carbon reduction targets, and clean infrastructure.',
      audience: 'executive C-suite stakeholders & board',
      tone: 'visionary, high-growth & inspiring'
    },
    {
      label: '🏛️ World History',
      topic: 'The French Revolution: Catalysts, Upheaval & Modern Legacy',
      prompt: 'Origins in societal disparity and fiscal crisis, the storming of the Bastille, Declaration of the Rights of Man, and enduring democratic ideals.',
      audience: 'university faculty and research peers',
      tone: 'educational, structured & comprehensive'
    },
    {
      label: '🧬 Medicine & Genomics',
      topic: 'Precision Medicine & Genomic Breakthroughs',
      prompt: 'CRISPR gene editing, targeted immunotherapy, clinical trial efficacy, early biomarker diagnostics, and personalized patient care.',
      audience: 'technical architects & engineering leadership',
      tone: 'authoritative, technical & data-driven'
    },
    {
      label: '🚀 Deep Space',
      topic: 'Humanity’s Return to the Moon and Journey to Mars',
      prompt: 'Lunar Gateway architecture, reusable heavy-lift rocketry, in-situ resource utilization, and deep space human habitats.',
      audience: 'general audience',
      tone: 'visionary, high-growth & inspiring'
    },
    {
      label: '🍞 Culinary Arts',
      topic: 'The Science of Sourdough & Artisanal Baking',
      prompt: 'Wild fermentation biochemistry, dough hydration ratios, gluten network development, hearth steam baking, and complex flavor profiles.',
      audience: 'general audience',
      tone: 'educational, structured & comprehensive'
    },
    {
      label: '📈 Business Strategy',
      topic: 'Strategic Scaling & High-Velocity Business Models',
      prompt: 'Product-led growth, expanding net revenue retention, unit economics, sustainable competitive moats, and operational leverage.',
      audience: 'venture capital investors',
      tone: 'persuasive, punchy & high-impact'
    },
    {
      label: '🧠 Mindfulness & Brain',
      topic: 'Mindfulness, Neuroscience & Peak Cognitive Performance',
      prompt: 'Neuroplasticity, stress regulation mechanisms, habit architecture, sleep optimization, and sustainable daily focus rituals.',
      audience: 'general audience',
      tone: 'clean, minimal & executive concise'
    }
  ];

  // Templates state
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('JobBridge_Cleaned');
  const [templateMeta, setTemplateMeta] = useState(null);
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false);

  // Design Theme state
  const [selectedThemeId, setSelectedThemeId] = useState(activeThemeId || 'google-gemini');
  const [imageSource, setImageSource] = useState('internet'); // 'internet' | 'ai'
  const [imageStyle, setImageStyle] = useState('3d'); // '3d' | 'photo' | 'vector' | 'cyberpunk' | 'abstract'

  // Content form state
  const [topic, setTopic] = useState('Artificial Intelligence & The Future of Human Work');
  const [prompt, setPrompt] = useState('Autonomous reasoning agents, human-AI collaboration, cognitive augmentation, productivity leaps, and workforce evolution.');
  const [slideCount, setSlideCount] = useState(6);
  const [audience, setAudience] = useState('executive C-suite stakeholders & board');
  const [tone, setTone] = useState('authoritative, technical & data-driven');
  const [attachments, setAttachments] = useState([]);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);

  // Execution state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [generatedDeckResult, setGeneratedDeckResult] = useState(null);
  const [previewSlideIdx, setPreviewSlideIdx] = useState(0);

  const templateFileInputRef = useRef(null);
  const docFileInputRef = useRef(null);

  const GENERATION_STEPS = [
    'AI Presentation Agent: Analyzing topic & deconstructing domain concepts...',
    'AI Presentation Agent: Synthesizing slide narratives & technical benchmarks...',
    'Visual Asset Agent: Generating & embedding high-resolution slide images...',
    'Deck Compiler: Assembling PowerPoint (.pptx) with exact template styling...'
  ];

  const reverseEngineerTemplate = useCallback(async (tmplId) => {
    if (!tmplId || tmplId === 'blank') {
      setTemplateMeta(null);
      return;
    }
    const formData = new FormData();
    formData.append('template_id', tmplId);

    try {
      const res = await fetch('/api/reverse-engineer', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setTemplateMeta(data.template);
      }
    } catch (err) {
      console.warn('Reverse engineering error:', err);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await fetch('/api/templates');
      if (res.ok) {
        const data = await res.json();
        setTemplates(data);
        if (data.length > 0 && !selectedTemplateId) {
          const defaultId = data[0].template_id;
          setSelectedTemplateId(defaultId);
          reverseEngineerTemplate(defaultId);
        } else if (selectedTemplateId && selectedTemplateId !== 'blank') {
          reverseEngineerTemplate(selectedTemplateId);
        }
      }
    } catch (err) {
      console.warn('Could not fetch templates:', err);
    }
  }, [selectedTemplateId, reverseEngineerTemplate]);

  // Load available templates on mount
  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);
  const handleSelectTemplate = (id) => {
    setSelectedTemplateId(id);
    if (id === 'blank') {
      setTemplateMeta(null);
    } else {
      reverseEngineerTemplate(id);
    }
  };

  const handleTemplateFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploadingTemplate(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/reverse-engineer', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setTemplateMeta(data.template);
        setSelectedTemplateId(data.template.template_id);
        fetchTemplates();
      } else {
        alert('Failed to analyze uploaded PowerPoint template.');
      }
    } catch (err) {
      alert('Upload error: ' + err.message);
    } finally {
      setIsUploadingTemplate(false);
    }
  };

  const handleDocFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setIsUploadingDoc(true);
    for (const f of files) {
      const formData = new FormData();
      formData.append('file', f);
      try {
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });
        if (res.ok) {
          const data = await res.json();
          setAttachments(prev => [...prev, data]);
        }
      } catch (err) {
        console.error('Doc upload error:', err);
      }
    }
    setIsUploadingDoc(false);
  };

  const removeAttachment = (idx) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx));
  };

  const handleThemeChange = (id) => {
    setSelectedThemeId(id);
    onSelectTheme?.(id);
  };

  const handleGenerate = async () => {
    if (!topic.trim()) {
      alert('Please enter a presentation topic or title.');
      return;
    }

    setIsGenerating(true);
    setGeneratedDeckResult(null);
    setCurrentStepIndex(0);

    // Multi-phase step timer
    const stepInterval = setInterval(() => {
      setCurrentStepIndex(prev => {
        if (prev < GENERATION_STEPS.length - 1) return prev + 1;
        return prev;
      });
    }, 1200);

    try {
      let finalPrompt = prompt.trim();
      if (!finalPrompt) {
        finalPrompt = `Create an authoritative, high-impact keynote presentation on ${topic.trim()}`;
      }
      if (attachments.length > 0) {
        const docTexts = attachments.map(a => a.extracted_text || '').filter(Boolean).join('\n\n');
        if (docTexts) {
          finalPrompt += `\n\nReference Material from attached documents:\n${docTexts.slice(0, 3000)}`;
        }
      }

      const res = await fetch('/api/generate-from-template', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: apiKey,
          provider: aiProvider,
          model: aiModel,
          base_url: aiBaseUrl,
          template_id: selectedTemplateId,
          theme_id: selectedThemeId,
          topic: topic.trim(),
          prompt: finalPrompt,
          slide_count: Number(slideCount),
          image_source: imageSource,
          image_style: imageStyle,
          audience: audience,
          tone: tone
        })
      });

      clearInterval(stepInterval);

      if (res.ok) {
        const data = await res.json();
        setGeneratedDeckResult(data);
        setPreviewSlideIdx(0);
        
        // Notify parent to save to history & update active deck
        if (data.deck && onPresentationGenerated) {
          onPresentationGenerated(data.deck, data.file_id, data.download_url);
        }
      } else {
        const err = await res.json().catch(() => ({}));
        alert('Presentation generation failed: ' + (err.detail || 'Server error. Please verify backend logs.'));
      }
    } catch (err) {
      clearInterval(stepInterval);
      alert('Generation error: ' + err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  const currentThemeObj = THEMES.find(t => t.id === selectedThemeId) || THEMES[0];

  return (
    <div className="template-generator-dashboard">
      <input
        type="file"
        ref={templateFileInputRef}
        onChange={handleTemplateFileUpload}
        style={{ display: 'none' }}
        accept=".pptx"
      />
      <input
        type="file"
        ref={docFileInputRef}
        onChange={handleDocFileUpload}
        style={{ display: 'none' }}
        multiple
        accept=".pdf,.docx,.doc,.txt,.pptx"
      />

      {/* Top Header */}
      <header className="app-top-header">
        <div className="header-left">
          <div className="brand-logo-pill">
            <Sparkles size={18} className="brand-sparkle" />
            <span className="brand-text">SlideCraft AI</span>
          </div>
          <span className="platform-tag">Presentation Template & Design Studio</span>
        </div>

        <div className="header-actions">
          <button className="header-btn" onClick={onOpenThemes} title="Browse Color Themes">
            <Palette size={15} />
            <span>Theme Library</span>
          </button>
          <button className="header-btn" onClick={onOpenSettings} title="Configure API Keys">
            <Sliders size={15} />
            <span>Settings</span>
          </button>
          {recentProjects.length > 0 && (
            <button className="header-btn primary" onClick={onOpenStudio} title="Switch to Slide Studio">
              <Eye size={15} />
              <span>Open Studio</span>
            </button>
          )}
        </div>
      </header>

      {/* Main Container */}
      <main className="generator-main-container">
        {/* Hero Section */}
        <div className="generator-hero">
          <div className="hero-pill-badge">
            <Wand2 size={14} className="text-accent" />
            <span>AI-Driven Presentation Generation</span>
          </div>
          <h1 className="hero-title">
            Generate Presentations Exactly to Your <span className="gradient-text">Template & Design</span>
          </h1>
          <p className="hero-subtitle">
            Provide any PowerPoint template (.pptx) or select a modern design theme. SlideCraft extracts layout archetypes,
            preserves original branding and typography, and synthesizes high-impact slides with high-res imagery.
          </p>
        </div>

        {/* Wizard Card */}
        <div className="generator-card">
          {/* STEP 1: Template Selection */}
          <section className="generator-section">
            <div className="section-label-row">
              <span className="step-num">1</span>
              <div>
                <h3>Select or Upload PowerPoint Template (.pptx)</h3>
                <p className="section-subtext">Choose an existing layout archetype or upload your organization's custom PPTX master</p>
              </div>
            </div>

            <div className="templates-selector-grid">
              {/* Option: SlideCraft Modern Theme (Blank Canvas) */}
              <div
                className={`template-select-item ${selectedTemplateId === 'blank' ? 'active' : ''}`}
                onClick={() => handleSelectTemplate('blank')}
              >
                <div className="tmpl-preview-strip native-theme" />
                <div className="tmpl-info-col">
                  <div className="tmpl-title-row">
                    <span className="tmpl-title">SlideCraft Native Pro</span>
                    <span className="badge-pill">NEW</span>
                  </div>
                  <span className="tmpl-desc">Adaptive Modern Layouts • 16:9 • Design Theme Pure</span>
                </div>
                {selectedTemplateId === 'blank' && <CheckCircle2 size={18} className="check-icon" />}
              </div>

              {/* Dynamic Templates from Backend */}
              {templates.map((tmpl) => (
                <div
                  key={tmpl.template_id}
                  className={`template-select-item ${selectedTemplateId === tmpl.template_id ? 'active' : ''}`}
                  onClick={() => handleSelectTemplate(tmpl.template_id)}
                >
                  <div
                    className="tmpl-preview-strip"
                    style={{
                      background: `linear-gradient(135deg, ${tmpl.primary_color || '#6366F1'} 0%, ${tmpl.secondary_color || '#0EA5E9'} 100%)`
                    }}
                  />
                  <div className="tmpl-info-col">
                    <span className="tmpl-title">{tmpl.filename || tmpl.template_id}</span>
                    <span className="tmpl-desc">
                      {tmpl.aspect_ratio || '16:9'} • {tmpl.slide_count || 6} Slides • {tmpl.title_font || 'Calibri'}
                    </span>
                  </div>
                  {selectedTemplateId === tmpl.template_id && <CheckCircle2 size={18} className="check-icon" />}
                </div>
              ))}

              {/* Upload Custom Template Card */}
              <div
                className="template-select-item upload-box"
                onClick={() => templateFileInputRef.current?.click()}
              >
                {isUploadingTemplate ? (
                  <RefreshCw size={24} className="spin text-accent" />
                ) : (
                  <Upload size={24} className="upload-icon" />
                )}
                <div className="tmpl-info-col">
                  <span className="tmpl-title">Upload Custom .pptx</span>
                  <span className="tmpl-desc">Clones exact master slides, vector art & fonts</span>
                </div>
              </div>
            </div>

            {/* Extracted Template DNA Banner */}
            {templateMeta && selectedTemplateId !== 'blank' && (
              <div className="template-dna-banner">
                <div className="dna-title">
                  <Cpu size={15} className="text-accent" />
                  <span>Reverse-Engineered Template DNA:</span>
                </div>
                <div className="dna-badges">
                  <span className="dna-badge">
                    <strong>Dimensions:</strong> {templateMeta.slide_width_in}" × {templateMeta.slide_height_in}" ({templateMeta.aspect_ratio})
                  </span>
                  <span className="dna-badge">
                    <strong>Typography:</strong> {templateMeta.title_font} / {templateMeta.body_font}
                  </span>
                  <div className="dna-colors">
                    <span className="color-chip" style={{ background: `#${templateMeta.primary_color}` }} title={`Primary: #${templateMeta.primary_color}`} />
                    <span className="color-chip" style={{ background: `#${templateMeta.secondary_color}` }} title={`Secondary: #${templateMeta.secondary_color}`} />
                    <span className="color-chip" style={{ background: `#${templateMeta.background_color}` }} title={`Background: #${templateMeta.background_color}`} />
                  </div>
                  <span className="dna-badge highlight">
                    <strong>Archetypes:</strong> {templateMeta.archetypes_available?.slice(0, 4).join(', ') || 'Title, Bullets, Metrics'}
                  </span>
                </div>
              </div>
            )}
          </section>

          {/* STEP 2: Design Theme & Visual Style */}
          <section className="generator-section">
            <div className="section-label-row">
              <span className="step-num">2</span>
              <div>
                <h3>Select Design Theme & Visual Imagery Style</h3>
                <p className="section-subtext">Choose color harmony, card elevation, typography tokens, and visual generation mode</p>
              </div>
            </div>

            {/* Theme Selector Grid */}
            <div className="design-themes-grid">
              {THEMES.map((th) => {
                const isSelected = selectedThemeId === th.id;
                return (
                  <div
                    key={th.id}
                    className={`design-theme-card ${isSelected ? 'active' : ''}`}
                    onClick={() => handleThemeChange(th.id)}
                    style={{
                      background: th.cardBg,
                      borderColor: isSelected ? th.accentPrimary : 'rgba(255,255,255,0.08)'
                    }}
                  >
                    <div className="theme-card-header">
                      <span className="theme-card-name" style={{ color: th.textPrimary }}>
                        {th.name}
                      </span>
                      {isSelected && (
                        <div className="theme-selected-pill" style={{ background: th.accentPrimary }}>
                          <Check size={12} color="#fff" />
                        </div>
                      )}
                    </div>

                    <p className="theme-card-desc" style={{ color: th.textSecondary }}>
                      {th.description}
                    </p>

                    <div className="theme-swatches-row">
                      <span className="theme-swatch" style={{ background: th.bgColor }} title="Background" />
                      <span className="theme-swatch" style={{ background: th.accentPrimary }} title="Primary Accent" />
                      <span className="theme-swatch" style={{ background: th.accentSecondary }} title="Secondary Accent" />
                      <span className="theme-mode-tag">
                        {th.darkMode ? 'Dark' : 'Light'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Image Style Selection */}
            <div className="image-style-section">
              <label className="sub-label">Visual & Image Generation Mode</label>
              <div className="image-source-options">
                <label
                  className={`image-source-card ${imageSource === 'internet' ? 'active' : ''}`}
                  onClick={() => setImageSource('internet')}
                >
                  <div className="card-radio-head">
                    <input
                      type="radio"
                      name="image_source"
                      checked={imageSource === 'internet'}
                      onChange={() => setImageSource('internet')}
                    />
                    <Globe size={18} className="source-icon blue" />
                    <strong>Internet Stock CDN (Unsplash)</strong>
                  </div>
                  <p>High-resolution real-world editorial photography and verified technical visuals.</p>
                </label>

                <label
                  className={`image-source-card ${imageSource === 'ai' ? 'active' : ''}`}
                  onClick={() => setImageSource('ai')}
                >
                  <div className="card-radio-head">
                    <input
                      type="radio"
                      name="image_source"
                      checked={imageSource === 'ai'}
                      onChange={() => setImageSource('ai')}
                    />
                    <Sparkles size={18} className="source-icon purple" />
                    <strong>AI Neural Diffusion Visuals</strong>
                  </div>
                  <p>Custom-generated 3D conceptual renders, vectors, or cinematic imagery tailored to slide context.</p>
                </label>

                <label
                  className={`image-source-card ${imageSource === 'openai' ? 'active' : ''}`}
                  onClick={() => setImageSource('openai')}
                >
                  <div className="card-radio-head">
                    <input
                      type="radio"
                      name="image_source"
                      checked={imageSource === 'openai'}
                      onChange={() => setImageSource('openai')}
                    />
                    <Sparkles size={18} className="source-icon green" />
                    <strong>OpenAI DALL·E 3 Visuals</strong>
                  </div>
                  <p>Widescreen 16:9 HD slide illustrations generated directly with OpenAI DALL·E 3.</p>
                </label>
              </div>

              {(imageSource === 'ai' || imageSource === 'openai') && (
                <div className="image-style-pills-row">
                  <span className="sub-caption">AI Visual Style:</span>
                  {[
                    { id: '3d', label: '3D Isometric Render' },
                    { id: 'photo', label: 'Cinematic Photo' },
                    { id: 'vector', label: 'Minimalist Vector' },
                    { id: 'cyberpunk', label: 'Cyberpunk Neon' },
                    { id: 'abstract', label: 'Abstract Gradients' }
                  ].map(st => (
                    <button
                      key={st.id}
                      type="button"
                      className={`style-pill-btn ${imageStyle === st.id ? 'active' : ''}`}
                      onClick={() => setImageStyle(st.id)}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* STEP 3: Presentation Topic & Content */}
          <section className="generator-section">
            <div className="section-label-row">
              <span className="step-num">3</span>
              <div>
                <h3>Presentation Topic & Content Requirements</h3>
                <p className="section-subtext">Define the title, target audience, strategic tone, and specific talking points</p>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group full">
                <label className="input-label">Keynote or Topic Title *</label>
                <input
                  type="text"
                  className="generator-input"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Distributed Cloud Networks, The French Revolution, Quantum Algorithms, Sourdough Baking"
                />

                {/* Quick Topic Inspiration Badges */}
                <div style={{ marginTop: '0.6rem', display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    <Sparkles size={12} color="#818cf8" /> Topic Inspiration:
                  </span>
                  {TOPIC_PRESETS.map((p, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        setTopic(p.topic);
                        setPrompt(p.prompt);
                        if (p.audience) setAudience(p.audience);
                        if (p.tone) setTone(p.tone);
                      }}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: topic === p.topic ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                        border: topic === p.topic ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.1)',
                        color: topic === p.topic ? '#fff' : '#cbd5e1',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group full">
                <label className="input-label">Content Guidelines & Specific Requirements (Optional)</label>
                <textarea
                  className="generator-textarea"
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Leave blank for autonomous AI topic synthesis, or enter specific talking points, numbers, or sections..."
                />
              </div>
            </div>

            <div className="form-grid-3">
              <div className="form-group">
                <label className="input-label">Slide Count</label>
                <select
                  className="generator-select"
                  value={slideCount}
                  onChange={(e) => setSlideCount(Number(e.target.value))}
                >
                  <option value={4}>4 Slides (Executive Brief)</option>
                  <option value={6}>6 Slides (Standard Keynote)</option>
                  <option value={8}>8 Slides (Detailed Deck)</option>
                  <option value={10}>10 Slides (Comprehensive)</option>
                  <option value={12}>12 Slides (Deep Dive)</option>
                  <option value={15}>15 Slides (Full Masterclass)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="input-label">Target Audience</label>
                <select
                  className="generator-select"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                >
                  <option value="general audience">General Public & Community</option>
                  <option value="students & educational peers">Students & Classroom</option>
                  <option value="conference & keynote attendees">Conference & Keynote Attendees</option>
                  <option value="technical architects & engineering leadership">Engineering & Technical Leadership</option>
                  <option value="executive C-suite stakeholders & board">Executive Board / Leadership</option>
                  <option value="venture capital investors">Investors & Pitch Meeting</option>
                  <option value="university faculty and research peers">Academic & Research Peers</option>
                  <option value="enterprise prospective clients">Enterprise B2B Clients</option>
                </select>
              </div>

              <div className="form-group">
                <label className="input-label">Tone & Presentation Style</label>
                <select
                  className="generator-select"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                >
                  <option value="authoritative, technical & data-driven">Authoritative & Technical</option>
                  <option value="visionary, high-growth & inspiring">Visionary & Inspiring</option>
                  <option value="clean, minimal & executive concise">Clean & Minimalist</option>
                  <option value="persuasive, punchy & high-impact">Persuasive & High-Impact</option>
                  <option value="educational, structured & comprehensive">Educational & Structured</option>
                  <option value="warm, engaging & accessible">Warm, Engaging & Storytelling</option>
                </select>
              </div>
            </div>

            {/* Optional File Attachment */}
            <div className="form-attach-row">
              <button
                type="button"
                className="btn-attach-doc"
                onClick={() => docFileInputRef.current?.click()}
                disabled={isUploadingDoc}
              >
                {isUploadingDoc ? <RefreshCw size={14} className="spin text-accent" /> : <Upload size={14} />}
                <span>Attach Reference Documents (PDF, Word, TXT)</span>
              </button>

              {attachments.length > 0 && (
                <div className="attachments-list-pill">
                  {attachments.map((att, idx) => (
                    <div key={idx} className="doc-pill">
                      <FileText size={12} className="text-accent" />
                      <span>{att.filename}</span>
                      <button type="button" onClick={() => removeAttachment(idx)}>×</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Action Footer */}
          <div className="generator-footer-row">
            {isGenerating && (
              <div className="generation-progress-box">
                <RefreshCw size={18} className="spin text-accent" />
                <span className="progress-step-text">{GENERATION_STEPS[currentStepIndex]}</span>
              </div>
            )}

            <button
              className="generate-deck-btn"
              onClick={handleGenerate}
              disabled={isGenerating || !topic.trim()}
            >
              {isGenerating ? (
                <>
                  <RefreshCw size={18} className="spin" />
                  <span>Generating {slideCount} Slides...</span>
                </>
              ) : (
                <>
                  <Wand2 size={18} />
                  <span>Generate Presentation ({slideCount} Slides)</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </div>
        </div>

        {/* Generated Deck Result Card */}
        {generatedDeckResult && (
          <div className="generated-result-card">
            <div className="result-header">
              <div className="result-meta-left">
                <CheckCircle2 size={32} className="text-success" />
                <div>
                  <h2 className="result-title">{generatedDeckResult.deck?.title || topic}</h2>
                  <p className="result-desc">
                    Successfully compiled <strong>{generatedDeckResult.deck?.slides?.length || slideCount} slides</strong> adhering strictly to{' '}
                    <strong>{templateMeta?.filename || selectedTemplateId}</strong> with design theme <strong>{currentThemeObj.name}</strong>.
                  </p>
                </div>
              </div>

              <div className="result-actions">
                <a
                  className="download-pptx-btn"
                  href={generatedDeckResult.download_url || `/api/download/${generatedDeckResult.file_id}`}
                  download={`presentation_${generatedDeckResult.file_id}.pptx`}
                >
                  <Download size={18} />
                  <span>Download .pptx</span>
                </a>

                <button
                  className="open-studio-btn"
                  onClick={() => {
                    if (generatedDeckResult.deck) {
                      onSelectProject({
                        title: generatedDeckResult.deck.title,
                        deck: generatedDeckResult.deck,
                        file_id: generatedDeckResult.file_id
                      });
                    }
                  }}
                >
                  <Eye size={18} />
                  <span>Open in Slide Studio</span>
                </button>
              </div>
            </div>

            {/* Slide Carousel Preview */}
            {generatedDeckResult.deck?.slides && (
              <div className="result-slide-preview-area">
                <div className="preview-nav-bar">
                  <span>
                    Slide {previewSlideIdx + 1} of {generatedDeckResult.deck.slides.length}:{' '}
                    <strong>{generatedDeckResult.deck.slides[previewSlideIdx]?.title}</strong>
                  </span>
                  <span className="archetype-badge">
                    Layout: {generatedDeckResult.deck.slides[previewSlideIdx]?.type?.toUpperCase()}
                  </span>
                </div>

                <div
                  className="slide-canvas-display"
                  style={{
                    backgroundColor: currentThemeObj.bgColor,
                    color: currentThemeObj.textPrimary,
                    fontFamily: currentThemeObj.fontFamily
                  }}
                >
                  <div className="slide-content-wrap">
                    <span
                      className="slide-cat-tag"
                      style={{
                        borderColor: currentThemeObj.accentPrimary,
                        color: currentThemeObj.accentSecondary,
                        background: currentThemeObj.badgeBg
                      }}
                    >
                      {generatedDeckResult.deck.slides[previewSlideIdx]?.category || 'EXECUTIVE KEYNOTE'}
                    </span>
                    <h2
                      className="slide-display-title"
                      style={{ color: currentThemeObj.textPrimary }}
                    >
                      {generatedDeckResult.deck.slides[previewSlideIdx]?.title}
                    </h2>
                    {generatedDeckResult.deck.slides[previewSlideIdx]?.subtitle && (
                      <p className="slide-display-sub" style={{ color: currentThemeObj.textSecondary }}>
                        {generatedDeckResult.deck.slides[previewSlideIdx]?.subtitle}
                      </p>
                    )}

                    <div className="slide-display-body">
                      {generatedDeckResult.deck.slides[previewSlideIdx]?.left && generatedDeckResult.deck.slides[previewSlideIdx]?.right ? (
                        <div className="slide-display-two-col">
                          <div className="preview-col-card" style={{ background: currentThemeObj.cardBg, borderColor: currentThemeObj.cardBorder }}>
                            <div className="col-header" style={{ color: currentThemeObj.accentSecondary }}>Strategic Context</div>
                            <ul>
                              {generatedDeckResult.deck.slides[previewSlideIdx].left.map((item, i) => (
                                <li key={i}>{item.replace(/^•\s*/, '')}</li>
                              ))}
                            </ul>
                          </div>
                          <div className="preview-col-card" style={{ background: currentThemeObj.cardBg, borderColor: currentThemeObj.accentPrimary }}>
                            <div className="col-header" style={{ color: currentThemeObj.accentPrimary }}>Target Paradigm</div>
                            <ul>
                              {generatedDeckResult.deck.slides[previewSlideIdx].right.map((item, i) => (
                                <li key={i}>{item.replace(/^•\s*/, '')}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      ) : generatedDeckResult.deck.slides[previewSlideIdx]?.table ? (
                        <div className="slide-display-table-wrap">
                          <table className="preview-table">
                            <thead>
                              <tr>
                                {generatedDeckResult.deck.slides[previewSlideIdx].table.headers?.map((h, i) => (
                                  <th key={i} style={{ background: currentThemeObj.badgeBg, color: currentThemeObj.accentSecondary }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {generatedDeckResult.deck.slides[previewSlideIdx].table.rows?.map((row, rI) => (
                                <tr key={rI}>
                                  {row.map((cell, cI) => (
                                    <td key={cI} style={{ borderColor: currentThemeObj.cardBorder }}>{cell}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <>
                          {generatedDeckResult.deck.slides[previewSlideIdx]?.bullets && (
                            <ul className="slide-display-bullets">
                              {generatedDeckResult.deck.slides[previewSlideIdx].bullets.map((b, i) => (
                                <li key={i}>{b}</li>
                              ))}
                            </ul>
                          )}
                          {generatedDeckResult.deck.slides[previewSlideIdx]?.stats && (
                            <div className="slide-display-stats-row">
                              {generatedDeckResult.deck.slides[previewSlideIdx].stats.map((s, i) => (
                                <div key={i} className="stat-preview-card" style={{ background: currentThemeObj.cardBg, borderColor: currentThemeObj.cardBorder }}>
                                  <span className="stat-preview-val" style={{ color: currentThemeObj.accentSecondary }}>{s.value}</span>
                                  <span className="stat-preview-lbl" style={{ color: currentThemeObj.textSecondary }}>{s.label}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {generatedDeckResult.deck.slides[previewSlideIdx]?.image_url && (
                    <div className="slide-display-image-box">
                      <img
                        src={generatedDeckResult.deck.slides[previewSlideIdx].image_url}
                        alt="Slide preview visual"
                        className="slide-display-img"
                      />
                    </div>
                  )}
                </div>

                {/* Thumbnails Navigator */}
                <div className="thumbnails-strip">
                  {generatedDeckResult.deck.slides.map((s, idx) => (
                    <button
                      key={s.id || idx}
                      className={`thumb-btn ${previewSlideIdx === idx ? 'active' : ''}`}
                      onClick={() => setPreviewSlideIdx(idx)}
                      style={{
                        borderColor: previewSlideIdx === idx ? currentThemeObj.accentPrimary : 'transparent'
                      }}
                    >
                      <span>Slide {idx + 1}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Recent Presentations Section */}
        <div className="recent-decks-section">
          <div className="section-title-row">
            <div>
              <h2>Your Presentations</h2>
              <p className="section-subtext">Manage, re-open in Slide Studio, or download previously generated PowerPoint decks</p>
            </div>
            <button className="new-deck-shortcut" onClick={onStartBlank}>
              <Plus size={16} />
              <span>Start from Blank Canvas</span>
            </button>
          </div>

          {recentProjects.length === 0 ? (
            <div className="empty-projects-card">
              <Layout size={32} className="text-muted" />
              <h3>No Presentations Generated Yet</h3>
              <p>Configure your template and design above, then click "Generate Presentation" to create your first deck!</p>
            </div>
          ) : (
            <div className="recent-decks-grid">
              {recentProjects.map((project, idx) => (
                <div
                  key={project.id || idx}
                  className="deck-card"
                  onClick={() => onSelectProject(project)}
                >
                  <div className="deck-card-preview">
                    <div className="deck-preview-inner">
                      <span className="deck-type-tag">{project.badge || 'PRESENTATION'}</span>
                      <h4 className="deck-preview-title">{project.title}</h4>
                      <span className="deck-preview-sub">
                        {project.deck?.slides?.length ? `${project.deck.slides.length} slides` : 'Executive Keynote Deck'}
                      </span>
                    </div>
                  </div>

                  <div className="deck-card-info">
                    <div className="deck-name-row">
                      <span className="deck-name" title={project.title}>{project.title}</span>
                    </div>
                    <div className="deck-meta-row">
                      <span className="deck-dims">{project.dimensions || '16:9 • 1920x1080'}</span>
                      <span className="deck-dot">•</span>
                      <span className="deck-time">{project.timeAgo || 'Recently generated'}</span>
                    </div>
                  </div>

                  <div className="deck-hover-bar" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="hover-btn primary"
                      onClick={() => onSelectProject(project)}
                      title="Open in Slide Studio"
                    >
                      Edit
                    </button>
                    {project.file_id && (
                      <button
                        className="hover-btn"
                        onClick={() => window.open(`/api/download/${project.file_id}`, '_blank')}
                        title="Download .pptx"
                      >
                        <Download size={14} />
                      </button>
                    )}
                    <button
                      className="hover-btn danger"
                      onClick={() => onDeleteProject?.(project.id || idx)}
                      title="Delete"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
