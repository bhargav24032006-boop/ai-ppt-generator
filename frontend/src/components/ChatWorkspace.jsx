import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles, Send, Paperclip, FileText, Image as ImageIcon,
  Presentation, Download, Play, Loader2, X, Plus, Layers,
  ChevronRight, ArrowRight, Wand2, RefreshCw, Layout, Upload,
  Globe, Trash2, Clock, Check, ChevronDown, Monitor, MessageSquare
} from 'lucide-react';
import SlideCanvas from './SlideCanvas';
import SlideEditor from './SlideEditor';
import { getThemeById } from '../themes';

export default function ChatWorkspace({
  messages,
  isLoading,
  onSendMessage,
  activeDeck,
  activeThemeId,
  downloadUrl,
  isSidebarOpen = true,
  onToggleSidebar,
  viewMode = 'split',
  onChangeViewMode,
  recentProjects = [],
  onSelectProject,
  onDeleteProject,
  onOpenThemes,
  onOpenSettings,
  onOpenPresentation,
  apiKey,
  aiProvider = 'openai',
  aiModel = 'gpt-4o-mini',
  serverHasOpenAiKey = false,
  activeSlideIndex = 0,
  setActiveSlideIndex,
  onUpdateSlide,
  onAddSlide,
  onDeleteSlide,
  onDuplicateSlide,
  onMoveSlide,
  onOpenImageModal,
  onQuickAiPolish,
  onStartBlank,
  onOpenNewDeckModal,
  onOpenTemplates,
  onImportJson
}) {
  const [prompt, setPrompt] = useState('');
  const [slideCount, setSlideCount] = useState(8);
  const [imageStyle, setImageStyle] = useState('3d');
  const [useWebGrounding, setUseWebGrounding] = useState(true);
  const [attachments, setAttachments] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);
  
  const fileInputRef = useRef(null);
  const jsonUploadRef = useRef(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const addMenuRef = useRef(null);

  const theme = getThemeById(activeThemeId);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (addMenuRef.current && !addMenuRef.current.contains(e.target)) {
        setShowAddMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleTextareaChange = (e) => {
    setPrompt(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setIsUploading(true);

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch('/api/upload', {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Upload failed');
        }

        const data = await res.json();
        setAttachments((prev) => [...prev, data]);
      } catch (err) {
        console.error('File upload error:', err);
        alert(`Failed to upload ${file.name}: ${err.message}`);
      }
    }

    setIsUploading(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleJsonFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target.result);
        onImportJson(parsed);
      } catch (err) {
        alert('Invalid JSON file format: ' + err.message);
      }
    };
    reader.readAsText(file);
    if (jsonUploadRef.current) jsonUploadRef.current.value = '';
  };

  const removeAttachment = (index) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = () => {
    const trimmed = prompt.trim();
    if ((!trimmed && attachments.length === 0) || isLoading) return;

    let finalPrompt = trimmed || (attachments.length > 0 ? `Generate presentation based on attached ${attachments.map(a => a.filename).join(', ')}` : '');
    if (useWebGrounding && !finalPrompt.toLowerCase().includes('reference') && !finalPrompt.toLowerCase().includes('web')) {
      finalPrompt = `${finalPrompt} (Ground in verified web reference facts)`;
    }

    onSendMessage({
      prompt: finalPrompt,
      attachments: attachments,
      slideCount: slideCount,
      imageStyle: imageStyle,
      preferred_image_provider: useWebGrounding ? 'web' : 'diffusion'
    });

    setPrompt('');
    setAttachments([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleStarterPrompt = (topicText) => {
    setPrompt(topicText);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const handleQuickChip = (instruction) => {
    onSendMessage({
      prompt: instruction,
      attachments: [],
      slideCount: slideCount,
      imageStyle: imageStyle,
      preferred_image_provider: useWebGrounding ? 'web' : 'diffusion'
    });
  };

  const activeSlide = activeDeck && activeDeck.slides && activeDeck.slides[activeSlideIndex]
    ? activeDeck.slides[activeSlideIndex]
    : (activeDeck && activeDeck.slides ? activeDeck.slides[0] : null);

  // Render bottom input bar (Gemini capsule design)
  const renderInputBar = (isSidebar = false) => {
    const isReady = (prompt.trim().length > 0 || attachments.length > 0) && !isLoading;
    return (
      <div className={isSidebar ? 'sidebar-input-container' : 'welcome-input-container'}>
        {/* Uploaded attachments pills */}
        {attachments.length > 0 && (
          <div className="input-attachments-rail">
            {attachments.map((att, idx) => (
              <div key={idx} className="input-att-pill">
                {att.file_type === 'image' ? (
                  <img src={att.url} alt={att.filename} className="input-att-thumb" />
                ) : att.file_type === 'template' ? (
                  <Presentation size={13} className="text-accent" />
                ) : (
                  <FileText size={13} className="text-accent" />
                )}
                <span className="input-att-name">{att.filename}</span>
                <button
                  type="button"
                  className="input-att-remove"
                  onClick={() => removeAttachment(idx)}
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Gemini Input Capsule Card */}
        <div className="gemini-input-capsule">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt,.pptx,.png,.jpg,.jpeg,.webp"
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />

          <textarea
            ref={textareaRef}
            rows={1}
            className="gemini-textarea"
            placeholder={
              activeDeck
                ? `Ask ${aiProvider === 'openai' ? 'OpenAI' : 'AI'} to refine slides, add metrics, generate DALL·E visuals, or add a table...`
                : `Ask ${aiProvider === 'openai' ? 'OpenAI' : 'AI'} to generate a presentation (e.g., Pitch Deck for an AI Startup)...`
            }
            value={prompt}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />

          <div className="gemini-input-toolbar">
            <div className="gemini-tools-left">
              {/* Attach File Button */}
              <button
                type="button"
                className="btn-gemini-tool"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading || isUploading}
                title="Attach PDF, Word doc, TXT, PPTX or Image"
              >
                {isUploading ? (
                  <Loader2 size={16} className="animate-spin text-accent" />
                ) : (
                  <Paperclip size={16} />
                )}
              </button>

              {/* Web Grounding Toggle */}
              <button
                type="button"
                className={`btn-gemini-tool web-toggle ${useWebGrounding ? 'active' : ''}`}
                onClick={() => setUseWebGrounding(!useWebGrounding)}
                title={useWebGrounding ? "Web Reference Grounding: Active" : "Click to enable Web Reference Grounding"}
              >
                <Globe size={14} />
                <span>Web Facts</span>
              </button>

              {/* Slide Count Selector */}
              <div className="gemini-select-pill" title="Target Slide Count">
                <Layers size={13} className="text-muted" />
                <select
                  value={slideCount}
                  onChange={(e) => setSlideCount(Number(e.target.value))}
                  disabled={isLoading}
                >
                  <option value={5}>5 slides</option>
                  <option value={8}>8 slides</option>
                  <option value={10}>10 slides</option>
                  <option value={12}>12 slides</option>
                  <option value={15}>15 slides</option>
                </select>
              </div>

              {/* Visual Style Selector */}
              <div className="gemini-select-pill" title="AI Image Visual Style">
                <Sparkles size={13} className="text-muted" />
                <select
                  value={imageStyle}
                  onChange={(e) => setImageStyle(e.target.value)}
                  disabled={isLoading}
                >
                  <option value="3d">3D Isometric</option>
                  <option value="photo">Real Photo</option>
                  <option value="cyberpunk">Cyberpunk Neon</option>
                  <option value="vector">Flat Vector</option>
                  <option value="abstract">Abstract Wave</option>
                </select>
              </div>
            </div>

            {/* Send Button */}
            <button
              type="button"
              className={`btn-gemini-send ${isReady ? 'active' : ''}`}
              onClick={handleSend}
              disabled={!isReady}
              title="Send to Gemini"
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Sparkles size={16} />
              )}
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`gemini-chat-workspace ${isSidebarOpen ? 'sidebar-expanded' : 'sidebar-collapsed'}`}>
      {/* Hidden JSON file input for Import */}
      <input
        ref={jsonUploadRef}
        type="file"
        accept=".json"
        style={{ display: 'none' }}
        onChange={handleJsonFileChange}
      />

      {/* ----------------- 1. GEMINI LEFT SIDEBAR ----------------- */}
      <aside className={`gemini-sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
        <div className="sidebar-top">
          {/* New Presentation Button */}
          <button
            className="btn-sidebar-new"
            onClick={onStartBlank || onOpenNewDeckModal}
            title="Start New Presentation with Gemini"
          >
            <Sparkles size={16} className="text-accent" />
            <span>New Presentation</span>
          </button>
        </div>

        {/* Recent Presentations List */}
        <div className="sidebar-recent-section">
          <div className="sidebar-section-header">
            <Clock size={13} />
            <span>Recent Presentations</span>
          </div>

          <div className="recent-decks-list">
            {recentProjects && recentProjects.length > 0 ? (
              recentProjects.map((proj) => {
                const isSelected = activeDeck && activeDeck.title === proj.title;
                const slideCount = proj.deck?.slides?.length || 6;
                return (
                  <div
                    key={proj.id || proj.title}
                    className={`recent-deck-item ${isSelected ? 'active' : ''}`}
                    onClick={() => onSelectProject && onSelectProject(proj)}
                  >
                    <div className="recent-deck-info">
                      <div className="recent-deck-title" title={proj.title}>
                        {proj.title || 'Untitled Presentation'}
                      </div>
                      <div className="recent-deck-meta">
                        <span className="recent-badge">{slideCount} slides</span>
                        <span className="recent-time">{proj.timeAgo || 'Recent'}</span>
                      </div>
                    </div>

                    <button
                      className="btn-recent-delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteProject && onDeleteProject(proj.id || proj.title);
                      }}
                      title="Delete presentation"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })
            ) : (
              <div className="recent-empty-state">
                <p>No saved presentations yet.</p>
                <span>Ask Gemini to create your first deck!</span>
              </div>
            )}
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="sidebar-footer">
          {/* Design Theme Picker */}
          <button className="sidebar-footer-btn" onClick={onOpenThemes} title="Change Presentation Design Theme">
            <div className="theme-color-dot" style={{ backgroundColor: theme.accentPrimary }} />
            <div className="footer-btn-info">
              <span className="footer-label">Design Theme</span>
              <span className="footer-val">{theme.name}</span>
            </div>
          </button>

          {/* AI Engine Status Badge */}
          <div
            className="sidebar-model-badge"
            onClick={onOpenSettings}
            style={{ cursor: 'pointer' }}
            title="Click to configure OpenAI / LLM API key & model"
          >
            <span className={`pulse-dot ${(apiKey || serverHasOpenAiKey) ? 'green' : ''}`} />
            <span>
              {aiProvider === 'openai' ? 'OpenAI' : aiProvider.toUpperCase()}{' '}
              {aiModel || 'gpt-4o-mini'} • {(apiKey || serverHasOpenAiKey) ? 'Connected' : 'Configure Key'}
            </span>
          </div>

          {/* Template Lab & Settings Buttons */}
          <div className="sidebar-actions-row">
            {onOpenTemplates && (
              <button className="sidebar-sub-btn" onClick={onOpenTemplates} title="PowerPoint Templates Lab">
                <Layout size={14} />
                <span>Templates</span>
              </button>
            )}
            <button className="sidebar-sub-btn" onClick={onOpenSettings} title="Settings & API Keys">
              <Wand2 size={14} />
              <span>Settings</span>
            </button>
          </div>
        </div>
      </aside>

      {/* ----------------- 2. MAIN WORKSPACE ----------------- */}
      <main className="gemini-main-stage">
        {/* CASE A: Active Deck Exists -> Studio Workspace */}
        {activeDeck ? (
          <div className={`gemini-studio-layout mode-${viewMode}`}>
            {/* LEFT PANE: Conversational Stream (shown in 'split' or 'chat' mode) */}
            {viewMode !== 'canvas' && (
              <div className="gemini-chat-column">
                <div className="chat-column-header">
                  <div className="chat-header-brand">
                    <Sparkles size={16} className="text-accent" />
                    <span>{aiProvider === 'openai' ? 'OpenAI' : aiProvider.toUpperCase()} Presentation Copilot</span>
                  </div>
                  <span className="live-status-pill" onClick={onOpenSettings} style={{ cursor: 'pointer' }}>
                    <span className="pulse-dot" /> {aiModel || 'gpt-4o-mini'}
                  </span>
                </div>

                {/* Messages Feed */}
                <div className="gemini-messages-feed">
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`gemini-msg-row ${msg.role}`}>
                      {msg.role === 'assistant' && (
                        <div className="gemini-avatar">
                          <Sparkles size={16} />
                        </div>
                      )}

                      <div className="gemini-msg-bubble">
                        {/* Attachments within message */}
                        {msg.attachments && msg.attachments.length > 0 && (
                          <div className="bubble-attachments">
                            {msg.attachments.map((att, i) => (
                              <div key={i} className="bubble-attachment-pill">
                                {att.file_type === 'image' ? (
                                  <img src={att.url} alt={att.filename} className="bubble-att-thumb" />
                                ) : (
                                  <FileText size={13} className="text-accent" />
                                )}
                                <span>{att.filename}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="msg-text-content">{msg.content}</div>
                      </div>
                    </div>
                  ))}

                  {isLoading && (
                    <div className="gemini-msg-row assistant">
                      <div className="gemini-avatar">
                        <Sparkles size={16} className="animate-spin text-accent" />
                      </div>
                      <div className="gemini-msg-bubble loading-bubble">
                        <div className="gemini-loading-dots">
                          <span />
                          <span />
                          <span />
                        </div>
                        <span className="loading-label">
                          {aiProvider === 'openai' ? 'OpenAI' : aiProvider.toUpperCase()} ({aiModel || 'gpt-4o-mini'}) is synthesizing slides & visuals...
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Quick NLP Action Chips */}
                <div className="gemini-quick-chips">
                  <button
                    className="gemini-chip"
                    onClick={() => handleQuickChip("Generate and draw a complete system architecture diagram, understand how it works, and give execution plans and strategic ideas")}
                  >
                    <Layers size={12} />
                    <span>+ Architecture, Plan & Ideas</span>
                  </button>

                  <button
                    className="gemini-chip"
                    onClick={() => handleQuickChip(`Regenerate visual image for slide ${activeSlideIndex + 1}`)}
                  >
                    <Wand2 size={12} />
                    <span>AI Visual for Slide {activeSlideIndex + 1}</span>
                  </button>

                  <button
                    className="gemini-chip"
                    onClick={() => handleQuickChip("Add an Executive Metrics & KPI slide to the deck")}
                  >
                    <Layers size={12} />
                    <span>+ Metrics Slide</span>
                  </button>

                  <button
                    className="gemini-chip"
                    onClick={() => handleQuickChip("Add a Comparative Analysis table slide")}
                  >
                    <Layout size={12} />
                    <span>+ Comparison Table</span>
                  </button>

                  <button
                    className="gemini-chip"
                    onClick={() => handleQuickChip("Add a Phased Execution Timeline roadmap slide")}
                  >
                    <Plus size={12} />
                    <span>+ Roadmap Slide</span>
                  </button>
                </div>

                {/* Bottom Input Capsule in Sidebar */}
                {renderInputBar(true)}
              </div>
            )}

            {/* RIGHT PANE: Interactive 16:9 Slide Canvas Studio (shown in 'split' or 'canvas' mode) */}
            {viewMode !== 'chat' && (
              <div className="gemini-canvas-column">
                {/* Main Interactive Slide Canvas Editor */}
                <div className="slide-editor-stage">
                  <SlideEditor
                    slide={activeSlide}
                    themeId={activeThemeId}
                    slideIndex={activeSlideIndex}
                    totalSlides={activeDeck.slides.length}
                    downloadUrl={downloadUrl}
                    onUpdateSlide={onUpdateSlide}
                    onDeleteSlide={() => onDeleteSlide(activeSlideIndex)}
                    onDuplicateSlide={() => onDuplicateSlide(activeSlideIndex)}
                    onMoveSlide={onMoveSlide}
                    onOpenImageModal={() => onOpenImageModal(activeSlide)}
                    onQuickAiPolish={onQuickAiPolish}
                  />
                </div>

                {/* Bottom Slide Thumbnail Strip (Canva-style) */}
                <div className="gemini-thumbnail-rail">
                  <div className="thumbnail-track">
                    {activeDeck.slides.map((s, idx) => (
                      <div
                        key={s.id || idx}
                        className={`slide-thumb-card ${idx === activeSlideIndex ? 'active' : ''}`}
                        onClick={() => setActiveSlideIndex(idx)}
                        title={`Slide ${idx + 1}: ${s.title}`}
                        style={{
                          borderColor: idx === activeSlideIndex ? theme.accentPrimary : 'transparent'
                        }}
                      >
                        <div className="thumb-num">{idx + 1}</div>
                        <div className="thumb-body">
                          <div className="thumb-cat">{s.category || s.type}</div>
                          <div className="thumb-name">{s.title || `Slide ${idx + 1}`}</div>
                        </div>
                        {s.image_url && (
                          <div className="thumb-image-badge" title="AI Visual Attached">
                            <ImageIcon size={10} />
                          </div>
                        )}
                      </div>
                    ))}

                    {/* Add Slide Dropdown Button */}
                    <div className="add-slide-container" ref={addMenuRef}>
                      <button
                        className="btn-add-slide-rail"
                        onClick={() => setShowAddMenu(!showAddMenu)}
                        title="Add New Slide"
                      >
                        <Plus size={16} />
                        <span>Add Slide</span>
                      </button>

                      {showAddMenu && (
                        <div className="add-slide-dropdown-menu">
                          <div className="menu-heading">Choose Slide Layout</div>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('diagram'); }}>
                            🏗️ Architecture Diagram & Blueprint
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('bullets'); }}>
                            • Bullets / Key Pillars
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('two_column'); }}>
                            ⚎ Two Columns Comparison
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('metrics'); }}>
                            📊 Metrics & KPIs
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('timeline'); }}>
                            🚀 Process & Timeline Roadmap
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('table'); }}>
                            📋 Structured Comparison Table
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('image_text'); }}>
                            🖼️ Image & Narrative Text
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('quote'); }}>
                            ❝ Executive Quote
                          </button>
                          <button className="menu-layout-item" onClick={() => { setShowAddMenu(false); onAddSlide('section'); }}>
                            🏷️ Section Header Divider
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* CASE B: No Active Deck Yet -> Google Gemini Welcome Screen */
          <div className="gemini-welcome-container">
            <div className="gemini-welcome-hero">
              {/* Animated 4-Point Gemini Star Icon */}
              <div className="gemini-luminous-star">
                <Sparkles size={38} className="star-icon" />
              </div>

              <h1 className="gemini-hero-heading">
                Hello, <span className="gemini-gradient-text">what shall we present?</span>
              </h1>
              <p className="gemini-hero-subtext">
                Ask Gemini to generate an executive presentation on any topic, grounded in live web reference facts,
                enriched with neural diffusion visuals, and editable in real time.
              </p>

              {/* Quick Hub Action Pills */}
              <div className="gemini-quick-actions">
                <button className="gemini-action-pill primary" onClick={onStartBlank}>
                  <Layout size={15} />
                  <span>Start from Blank Canvas</span>
                </button>
                <button className="gemini-action-pill" onClick={() => jsonUploadRef.current?.click()}>
                  <Upload size={15} />
                  <span>Import Saved Project (.json)</span>
                </button>
                <button className="gemini-action-pill" onClick={onOpenNewDeckModal}>
                  <Presentation size={15} />
                  <span>Keynote Starter Templates</span>
                </button>
              </div>

              {/* 8 Gemini Prompt Starter Tiles Grid */}
              <div className="gemini-starters-grid">
                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Generate a complete System Architecture for an Autonomous AI Agent Platform, draw the architecture diagram, explain how it works, and give phased plans and strategic ideas')}
                >
                  <div className="starter-card-tag">🏗️ Architecture & Plan</div>
                  <div className="starter-card-title">AI System Architecture & Ideas</div>
                  <p className="starter-card-p">Draws multi-tier architecture topology, explains dataflow, and gives execution plans & ideas.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Executive Business Review: Q3 Performance, Key Metrics, Growth Vectors, and Strategic Risks')}
                >
                  <div className="starter-card-tag">📊 Executive Review</div>
                  <div className="starter-card-title">Quarterly Performance Review</div>
                  <p className="starter-card-p">Executive summary, YoY metrics, operational hurdles, and Q4 targets.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Deep Space Exploration: Artemis Lunar Gateway, Heavy-Lift Rocketry, and Mars Human Missions')}
                >
                  <div className="starter-card-tag">🌌 Space Science</div>
                  <div className="starter-card-title">Deep Space Exploration</div>
                  <p className="starter-card-p">Lunar architecture, heavy-lift rocketry, in-situ resources, and deep space habitats.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Global Renewable Energy Transition: Grid Battery Storage, Solar Parity, and Carbon Reduction')}
                >
                  <div className="starter-card-tag">🌿 Clean Tech</div>
                  <div className="starter-card-title">Renewable Energy Transition</div>
                  <p className="starter-card-p">Grid storage, wind & solar parity, circular economy, and carbon reduction milestones.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Precision Medicine & Genomics: CRISPR Gene Editing, Clinical Trial Efficacy, and Patient Care')}
                >
                  <div className="starter-card-tag">🧬 Healthcare</div>
                  <div className="starter-card-title">Precision Medicine & Genomics</div>
                  <p className="starter-card-p">CRISPR gene editing, targeted immunotherapy, clinical trials, and early biomarker care.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('The Science of Sourdough & Artisanal Baking: Wild Fermentation Biochemistry and Flavor Profiles')}
                >
                  <div className="starter-card-tag">🍞 Culinary Arts</div>
                  <div className="starter-card-title">The Science of Sourdough</div>
                  <p className="starter-card-p">Wild fermentation biochemistry, dough hydration ratios, gluten network, and hearth baking.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Strategic Scaling & High-Velocity Business Models: Product-Led Growth, Unit Economics, and Moats')}
                >
                  <div className="starter-card-tag">📈 Growth Strategy</div>
                  <div className="starter-card-title">High-Velocity Business Models</div>
                  <p className="starter-card-p">Product-led growth, unit economics, net retention, and sustainable competitive moats.</p>
                </div>

                <div
                  className="gemini-starter-card"
                  onClick={() => handleStarterPrompt('Mindfulness, Neuroscience & Peak Cognitive Performance: Stress Regulation and Habit Architecture')}
                >
                  <div className="starter-card-tag">🧠 Neuroscience</div>
                  <div className="starter-card-title">Mindfulness & Peak Performance</div>
                  <p className="starter-card-p">Neuroplasticity, stress regulation mechanisms, sleep optimization, and daily focus rituals.</p>
                </div>
              </div>
            </div>

            {/* Bottom Input Capsule in Welcome View */}
            <div ref={messagesEndRef} />
            {renderInputBar(false)}
          </div>
        )}
      </main>
    </div>
  );
}
