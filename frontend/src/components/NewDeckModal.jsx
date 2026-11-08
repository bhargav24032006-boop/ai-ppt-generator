import React, { useState, useRef } from 'react';
import {
  Sparkles, FileText, Layout, Presentation, Upload,
  Plus, ArrowRight, X, Check, BookOpen, Rocket, LineChart, Cpu, Layers
} from 'lucide-react';

const STARTER_TEMPLATES = [
  {
    id: 'startup-pitch',
    icon: Rocket,
    title: 'Startup Investor Pitch',
    category: 'VENTURE CAPITAL',
    badgeColor: '#6366f1',
    description: 'Problem statement, market TAM/SAM, competitive advantage, unit economics, metrics, and funding ask.',
    prompt: 'Pitch Deck for an Autonomous AI Startup: problem statement, market size, secret sauce, revenue model, KPI traction, and $5M seed round.'
  },
  {
    id: 'executive-qbr',
    icon: LineChart,
    title: 'Quarterly Business Review',
    category: 'EXECUTIVE LEADERSHIP',
    badgeColor: '#10b981',
    description: 'Q3 performance review, revenue targets, operational velocity, risk matrix, and Q4 strategic OKRs.',
    prompt: 'Quarterly Business Review: Q3 milestones, YoY revenue metrics, customer retention, operational hurdles, and Q4 targets.'
  },
  {
    id: 'tech-architecture',
    icon: Cpu,
    title: 'Engineering & Architecture Deep Dive',
    category: 'TECHNICAL KEYNOTE',
    badgeColor: '#06b6d4',
    description: 'System blueprint, high-throughput microservices, latency benchmarks, resilience, and security protocols.',
    prompt: 'System Architecture Keynote: distributed microservices, low-latency message streaming, data consistency, and fault tolerance.'
  },
  {
    id: 'product-roadmap',
    icon: Layers,
    title: 'Product Strategy & Roadmap',
    category: 'PRODUCT MANAGEMENT',
    badgeColor: '#f59e0b',
    description: 'User personas, phased milestone roadmap, comparative matrix, feature priorities, and go-to-market plan.',
    prompt: 'Product Roadmap & GTM Strategy: user needs, phased release timeline, competitive differentiation table, and adoption targets.'
  }
];

export default function NewDeckModal({
  isOpen,
  onClose,
  onGenerateFromPrompt,
  onStartBlank,
  onImportJson
}) {
  const [activeTab, setActiveTab] = useState('templates'); // 'templates' | 'prompt' | 'blank'
  const [promptText, setPromptText] = useState('');
  const [slideCount, setSlideCount] = useState(8);
  const [imageStyle, setImageStyle] = useState('3d');
  const jsonFileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleJsonUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target.result);
        onImportJson(parsed);
        onClose();
      } catch (err) {
        alert('Invalid presentation JSON file: ' + err.message);
      }
    };
    reader.readAsText(file);
  };

  const handleGenerateSubmit = (e) => {
    e.preventDefault();
    if (!promptText.trim()) return;
    onGenerateFromPrompt({
      prompt: promptText.trim(),
      slideCount,
      imageStyle
    });
    onClose();
  };

  const handleTemplateClick = (template) => {
    onGenerateFromPrompt({
      prompt: template.prompt,
      slideCount: 8,
      imageStyle: '3d'
    });
    onClose();
  };

  const handleBlankClick = () => {
    onStartBlank();
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card new-deck-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="icon-glow-badge">
              <Sparkles size={20} className="text-accent" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800 }}>Create New Presentation</h2>
              <p className="modal-sub">Choose a creation method just like Canva & PowerPoint</p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Tabs */}
        <div className="new-deck-tabs">
          <button
            className={`new-deck-tab ${activeTab === 'templates' ? 'active' : ''}`}
            onClick={() => setActiveTab('templates')}
          >
            <Presentation size={15} />
            <span>Keynote Templates</span>
          </button>
          <button
            className={`new-deck-tab ${activeTab === 'prompt' ? 'active' : ''}`}
            onClick={() => setActiveTab('prompt')}
          >
            <Sparkles size={15} />
            <span>AI Prompt Generator</span>
          </button>
          <button
            className={`new-deck-tab ${activeTab === 'blank' ? 'active' : ''}`}
            onClick={() => setActiveTab('blank')}
          >
            <Layout size={15} />
            <span>Blank Canvas & Import</span>
          </button>
        </div>

        {/* Tab 1: Starter Keynote Templates */}
        {activeTab === 'templates' && (
          <div className="tab-content-templates">
            <div className="templates-grid">
              {STARTER_TEMPLATES.map((tmpl) => {
                const IconComponent = tmpl.icon;
                return (
                  <div
                    key={tmpl.id}
                    className="template-card"
                    onClick={() => handleTemplateClick(tmpl)}
                  >
                    <div className="template-card-header">
                      <div className="template-icon-box" style={{ color: tmpl.badgeColor, backgroundColor: `${tmpl.badgeColor}20` }}>
                        <IconComponent size={20} />
                      </div>
                      <span className="template-category-badge" style={{ color: tmpl.badgeColor }}>
                        {tmpl.category}
                      </span>
                    </div>
                    <div className="template-title">{tmpl.title}</div>
                    <p className="template-desc">{tmpl.description}</p>
                    <div className="template-footer">
                      <span>Click to generate deck</span>
                      <ArrowRight size={14} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Tab 2: AI Prompt Generator */}
        {activeTab === 'prompt' && (
          <form onSubmit={handleGenerateSubmit} className="tab-content-prompt">
            <div className="form-group">
              <label className="form-label">Presentation Topic & Instructions</label>
              <textarea
                rows={3}
                className="form-textarea"
                placeholder="e.g. Executive Strategy for entering European markets with risk factors, TAM metrics, and quarterly milestones..."
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                autoFocus
              />
            </div>

            <div className="prompt-options-row">
              <div className="form-group flex-1">
                <label className="form-label">Target Slide Count</label>
                <select
                  className="form-select"
                  value={slideCount}
                  onChange={(e) => setSlideCount(Number(e.target.value))}
                >
                  <option value={5}>5 slides (Executive Brief)</option>
                  <option value={8}>8 slides (Standard Keynote)</option>
                  <option value={10}>10 slides (Detailed Pitch)</option>
                  <option value={12}>12 slides (Comprehensive Review)</option>
                  <option value={15}>15 slides (Deep Dive)</option>
                </select>
              </div>

              <div className="form-group flex-1">
                <label className="form-label">AI Visual Style</label>
                <select
                  className="form-select"
                  value={imageStyle}
                  onChange={(e) => setImageStyle(e.target.value)}
                >
                  <option value="3d">3D Isometric Render</option>
                  <option value="photo">Cinematic Photo</option>
                  <option value="cyberpunk">Cyberpunk Neon</option>
                  <option value="vector">Clean Vector Graphic</option>
                  <option value="abstract">Luxurious Abstract Wave</option>
                </select>
              </div>
            </div>

            <div className="modal-actions-right">
              <button type="button" className="btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button
                type="submit"
                className="btn-primary"
                disabled={!promptText.trim()}
              >
                <Sparkles size={16} />
                <span>Generate Presentation</span>
              </button>
            </div>
          </form>
        )}

        {/* Tab 3: Blank Canvas & Import JSON */}
        {activeTab === 'blank' && (
          <div className="tab-content-blank">
            <div className="blank-options-grid">
              {/* Option A: Start Blank */}
              <div className="blank-card" onClick={handleBlankClick}>
                <div className="blank-card-icon">
                  <Plus size={32} />
                </div>
                <div className="blank-card-title">Start from Blank Canvas</div>
                <p className="blank-card-desc">
                  Design your own presentation from scratch. Add text, tables, stat cards, images, and timelines with total manual control.
                </p>
                <button className="btn-blank-action" type="button">
                  <span>Create Blank Deck</span>
                  <ArrowRight size={14} />
                </button>
              </div>

              {/* Option B: Import JSON project */}
              <div className="blank-card" onClick={() => jsonFileInputRef.current?.click()}>
                <input
                  ref={jsonFileInputRef}
                  type="file"
                  accept=".json"
                  style={{ display: 'none' }}
                  onChange={handleJsonUpload}
                />
                <div className="blank-card-icon import-icon">
                  <Upload size={32} />
                </div>
                <div className="blank-card-title">Import Saved Project (.json)</div>
                <p className="blank-card-desc">
                  Load an existing SlideCraft presentation file (.json) to continue editing, refining, or exporting.
                </p>
                <button className="btn-blank-action" type="button">
                  <span>Upload JSON File</span>
                  <Upload size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
