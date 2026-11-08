import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles, Image as ImageIcon, Plus, Trash2, Copy,
  TrendingUp, BookOpen, ChevronLeft, ChevronRight,
  Layers, Wand2, ArrowUp, ArrowDown, AlignLeft, AlignCenter,
  Download, RefreshCw, Eye, Edit3, CheckCircle2, ShieldCheck, AlertCircle
} from 'lucide-react';
import { getThemeById } from '../themes';
import ArchitectureDiagramView, { buildDefaultDiagramFromSlide } from './ArchitectureDiagramView';

function AutoResizeTextarea({
  value,
  onChange,
  className,
  style,
  placeholder,
  rows = 1
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [value]);

  const handleInput = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = `${e.target.scrollHeight}px`;
  };

  return (
    <textarea
      ref={textareaRef}
      rows={rows}
      className={className}
      style={{
        ...style,
        overflow: 'hidden',
        resize: 'none'
      }}
      value={value}
      placeholder={placeholder}
      onChange={onChange}
      onInput={handleInput}
    />
  );
}

const LAYOUT_OPTIONS = [
  { id: 'title', label: 'Hero Title' },
  { id: 'diagram', label: 'Architecture Diagram' },
  { id: 'bullets', label: 'Bullets / Pillars' },
  { id: 'two_column', label: 'Two Columns' },
  { id: 'metrics', label: 'Metrics & KPIs' },
  { id: 'timeline', label: 'Process & Timeline' },
  { id: 'table', label: 'Comparison Table' },
  { id: 'image_text', label: 'Image & Text' },
  { id: 'quote', label: 'Executive Quote' },
  { id: 'section', label: 'Section Divider' },
  { id: 'conclusion', label: 'Conclusion' }
];

export default function SlideEditor({
  slide,
  themeId = 'google-gemini',
  slideIndex = 0,
  totalSlides = 1,
  downloadUrl = null,
  deckTitle = '',
  onUpdateSlide,
  onDeleteSlide,
  onDuplicateSlide,
  onMoveSlide,
  onOpenImageModal,
  onQuickAiPolish
}) {
  const [showNotes, setShowNotes] = useState(false);
  const [showAiMenu, setShowAiMenu] = useState(false);
  const [viewMode, setViewMode] = useState('editor'); // 'editor' | 'rendered'
  const [imgTimestamp, setImgTimestamp] = useState(Date.now());
  const [imgLoading, setImgLoading] = useState(false);
  const [imgError, setImgError] = useState(false);
  const theme = getThemeById(themeId);

  useEffect(() => {
    setImgTimestamp(Date.now());
    setImgError(false);
  }, [slideIndex, downloadUrl]);

  if (!slide) return null;

  const cardStyle = {
    backgroundColor: theme.cardBg,
    borderColor: theme.cardBorder,
    color: theme.textPrimary
  };

  const handleFieldChange = (field, value) => {
    onUpdateSlide({
      ...slide,
      [field]: value
    });
  };

  // Metrics handlers
  const handleStatChange = (index, key, val) => {
    const updated = [...(slide.stats || [])];
    if (updated[index]) {
      updated[index] = { ...updated[index], [key]: val };
      handleFieldChange('stats', updated);
    }
  };

  const handleAddStat = () => {
    const updated = [...(slide.stats || [])];
    updated.push({ value: '99%', label: 'Key Vector', change: '+20% YoY' });
    handleFieldChange('stats', updated);
  };

  const handleRemoveStat = (index) => {
    const updated = (slide.stats || []).filter((_, i) => i !== index);
    handleFieldChange('stats', updated);
  };

  // Bullets handlers
  const handleBulletChange = (listName, index, val) => {
    const updated = [...(slide[listName] || [])];
    updated[index] = val;
    handleFieldChange(listName, updated);
  };

  const handleAddBullet = (listName) => {
    const updated = [...(slide[listName] || [])];
    updated.push('New strategic imperative or milestone');
    handleFieldChange(listName, updated);
  };

  const handleRemoveBullet = (listName, index) => {
    const updated = (slide[listName] || []).filter((_, i) => i !== index);
    handleFieldChange(listName, updated);
  };

  // Table handlers
  const handleTableHeaderChange = (idx, val) => {
    const currentTable = slide.table || {
      headers: ['Dimension', 'Baseline', 'Target', 'Impact'],
      rows: [['Dimension 1', 'Baseline Val', 'Target Val', 'Positive Impact']]
    };
    const newHeaders = [...currentTable.headers];
    newHeaders[idx] = val;
    handleFieldChange('table', { ...currentTable, headers: newHeaders });
  };

  const handleTableCellChange = (rowIdx, colIdx, val) => {
    const currentTable = slide.table || {
      headers: ['Dimension', 'Baseline', 'Target', 'Impact'],
      rows: [['Dimension 1', 'Baseline Val', 'Target Val', 'Positive Impact']]
    };
    const newRows = currentTable.rows.map((r, rI) => {
      if (rI !== rowIdx) return r;
      const copy = [...r];
      copy[colIdx] = val;
      return copy;
    });
    handleFieldChange('table', { ...currentTable, rows: newRows });
  };

  const handleAddTableRow = () => {
    const currentTable = slide.table || {
      headers: ['Dimension', 'Baseline', 'Target', 'Impact'],
      rows: []
    };
    const emptyRow = currentTable.headers.map((_, i) => i === 0 ? `Item ${currentTable.rows.length + 1}` : 'Details');
    handleFieldChange('table', { ...currentTable, rows: [...currentTable.rows, emptyRow] });
  };

  const handleRemoveTableRow = (rowIdx) => {
    const currentTable = slide.table || { headers: [], rows: [] };
    const newRows = currentTable.rows.filter((_, i) => i !== rowIdx);
    handleFieldChange('table', { ...currentTable, rows: newRows });
  };

  const handleLayoutSelect = (newType) => {
    const updated = { ...slide, type: newType };
    if (newType === 'table' && !slide.table) {
      updated.table = {
        headers: ['Dimension', 'Current State', 'Target Benchmark', 'Velocity Factor'],
        rows: [
          ['Operational Speed', '4-5 business days', 'Instant AI synthesis (< 2s)', '98% faster'],
          ['Visual Quality', 'Stock clip art', 'Tailored isometric 3D renders', '10x engagement'],
          ['Delivery Latency', 'Manual coordination', 'Autonomous pipeline', 'Zero friction']
        ]
      };
    } else if (newType === 'metrics' && (!slide.stats || slide.stats.length === 0)) {
      updated.stats = [
        { value: '99.4%', label: 'System Reliability', change: '+18% YoY' },
        { value: '3.8x', label: 'Execution Velocity', change: 'Top Decile' },
        { value: '$12.5M', label: 'Pipeline Value', change: '+45% Growth' }
      ];
    } else if (newType === 'timeline' && (!slide.bullets || slide.bullets.length === 0)) {
      updated.bullets = [
        'Phase 1: Architecture Blueprint & Technical Scoping',
        'Phase 2: Platform MVP & Multi-Agent Integration',
        'Phase 3: Security Validation & Pilot Rollout',
        'Phase 4: Global Deployment & Continuous Optimization'
      ];
    } else if (newType === 'diagram') {
      updated.visual = {
        ...(slide.visual || {}),
        kind: 'architecture',
        diagram: buildDefaultDiagramFromSlide(slide)
      };
      if (!updated.bullets || updated.bullets.length === 0) {
        updated.bullets = [
          'End-to-end layered architecture decoupling ingress, orchestration, core engine, and persistence.',
          'High-availability event-driven dataflow with real-time telemetry and fault isolation.'
        ];
      }
    }
    onUpdateSlide(updated);
  };

  return (
    <div className="slide-editor-container">
      {/* Top Slide Canvas Toolbar (Canva-style) */}
      <div className="editor-toolbar">
        <div className="toolbar-left">
          <div className="slide-nav-pill">
            Slide {slideIndex + 1} of {totalSlides}
          </div>

          {/* Move Slide Left/Up or Right/Down */}
          <div className="reorder-btns">
            <button
              className="toolbar-btn icon-only"
              onClick={() => onMoveSlide && onMoveSlide(slideIndex, -1)}
              disabled={slideIndex === 0}
              title="Move Slide Up / Earlier in Presentation"
            >
              <ArrowUp size={14} />
            </button>
            <button
              className="toolbar-btn icon-only"
              onClick={() => onMoveSlide && onMoveSlide(slideIndex, 1)}
              disabled={slideIndex >= totalSlides - 1}
              title="Move Slide Down / Later in Presentation"
            >
              <ArrowDown size={14} />
            </button>
          </div>

          {/* Layout Switcher Dropdown */}
          <div className="layout-select-wrap">
            <Layers size={14} className="text-accent" />
            <select
              className="layout-select"
              value={slide.type || 'bullets'}
              onChange={(e) => handleLayoutSelect(e.target.value)}
            >
              {LAYOUT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  Layout: {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* View Mode Toggle: Interactive Canvas vs PowerPoint Rendered Image */}
          {downloadUrl && (
            <div className="slide-view-mode-toggle">
              <button
                type="button"
                className={`view-toggle-btn ${viewMode === 'editor' ? 'active' : ''}`}
                onClick={() => setViewMode('editor')}
                title="Interactive Canvas Editor"
              >
                <Edit3 size={13} />
                <span>Live Canvas</span>
              </button>
              <button
                type="button"
                className={`view-toggle-btn ${viewMode === 'rendered' ? 'active' : ''}`}
                onClick={() => {
                  setViewMode('rendered');
                  setImgLoading(true);
                  setImgError(false);
                }}
                title="View Native PowerPoint Rendered 1920x1080 Image"
              >
                <Eye size={13} />
                <span>PowerPoint Slide</span>
              </button>
            </div>
          )}
        </div>

        <div className="toolbar-right">
          {/* Quick Slide PNG Download */}
          {downloadUrl && (
            <a
              href={`${downloadUrl.replace(/\/$/, '')}/slides/${slideIndex + 1}/image?download=true`}
              download
              className="toolbar-btn"
              title={`Download Slide ${slideIndex + 1} as 1920x1080 PNG image`}
              style={{ textDecoration: 'none' }}
            >
              <Download size={14} style={{ color: '#06b6d4' }} />
              <span>Slide PNG</span>
            </a>
          )}

          {/* Quick AI Polish / Copilot */}
          <div className="ai-polish-dropdown-wrap" style={{ position: 'relative' }}>
            <button
              className="toolbar-btn"
              onClick={() => setShowAiMenu(!showAiMenu)}
              title="AI Slide Copilot - Instant Refinement"
            >
              <Wand2 size={14} style={{ color: theme.accentSecondary }} />
              <span>AI Polish</span>
            </button>

            {showAiMenu && (
              <div className="ai-menu-dropdown" style={cardStyle}>
                <div className="ai-menu-header">AI Slide Copilot</div>
                <button
                  className="ai-menu-item"
                  onClick={() => {
                    setShowAiMenu(false);
                    onQuickAiPolish && onQuickAiPolish(`Sharpen and make the title and bullet points on slide ${slideIndex + 1} more punchy and executive.`);
                  }}
                >
                  ✨ Make more concise & punchy
                </button>
                <button
                  className="ai-menu-item"
                  onClick={() => {
                    setShowAiMenu(false);
                    onQuickAiPolish && onQuickAiPolish(`Expand slide ${slideIndex + 1} with high-impact metrics and verifiable examples.`);
                  }}
                >
                  📈 Add impact & data metrics
                </button>
                <button
                  className="ai-menu-item"
                  onClick={() => {
                    setShowAiMenu(false);
                    onQuickAiPolish && onQuickAiPolish(`Rewrite slide ${slideIndex + 1} in a formal, authoritative corporate keynote tone.`);
                  }}
                >
                  💼 Corporate keynote tone
                </button>
                <button
                  className="ai-menu-item"
                  onClick={() => {
                    setShowAiMenu(false);
                    onQuickAiPolish && onQuickAiPolish(`Generate and draw a complete system architecture diagram on slide ${slideIndex + 1}, explain how it works, and give execution plans and strategic ideas.`);
                  }}
                >
                  🏗️ Draw Architecture & Plan
                </button>
                <button
                  className="ai-menu-item"
                  onClick={() => {
                    setShowAiMenu(false);
                    onOpenImageModal();
                  }}
                >
                  🎨 Generate matching AI visual
                </button>
              </div>
            )}
          </div>

          {/* AI Image Button */}
          <button
            className={`toolbar-btn ${slide.image_url ? 'has-image' : 'primary-glow'}`}
            onClick={onOpenImageModal}
            title="Generate or change AI Visual for this slide"
          >
            <Sparkles size={14} />
            <span>{slide.image_url ? 'Regenerate Visual' : 'Add AI Visual'}</span>
          </button>

          {/* Duplicate Button */}
          <button
            className="toolbar-btn icon-only"
            onClick={onDuplicateSlide}
            title="Duplicate Slide"
          >
            <Copy size={15} />
          </button>

          {/* Delete Button */}
          <button
            className="toolbar-btn icon-only danger"
            onClick={onDeleteSlide}
            disabled={totalSlides <= 1}
            title="Delete Slide"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {/* Main View Area: Either PowerPoint Rendered Image or Interactive Live Canvas */}
      {viewMode === 'rendered' && downloadUrl ? (
        <div className="rendered-slide-container">
          <div className="rendered-slide-overlay-bar">
            <button
              className="overlay-btn"
              onClick={() => {
                setImgTimestamp(Date.now());
                setImgLoading(true);
              }}
              title="Refresh native PowerPoint render"
            >
              <RefreshCw size={13} className={imgLoading ? 'spin-animate' : ''} />
              <span>Refresh Render</span>
            </button>
            <a
              href={`${downloadUrl.replace(/\/$/, '')}/slides/${slideIndex + 1}/image?download=true`}
              download
              className="overlay-btn"
              title="Download 1920x1080 PNG"
            >
              <Download size={13} />
              <span>Download PNG</span>
            </a>
            <button
              className="overlay-btn"
              onClick={() => setViewMode('editor')}
              title="Switch back to interactive canvas editor"
            >
              <Edit3 size={13} />
              <span>Edit Slide</span>
            </button>
          </div>

          <div className="rendered-slide-badge">
            <CheckCircle2 size={13} />
            <span>PowerPoint 1920x1080 Native Render</span>
          </div>

          <img
            src={`${downloadUrl.replace(/\/$/, '')}/slides/${slideIndex + 1}/image?t=${imgTimestamp}`}
            alt={`Slide ${slideIndex + 1} Native PowerPoint Render`}
            onLoad={() => setImgLoading(false)}
            onError={() => {
              setImgLoading(false);
              setImgError(true);
            }}
          />

          {imgLoading && (
            <div style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(11, 15, 25, 0.85)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              zIndex: 4
            }}>
              <RefreshCw size={28} className="spin-animate text-accent" />
              <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                Rendering Slide {slideIndex + 1} with Microsoft PowerPoint...
              </div>
            </div>
          )}

          {imgError && (
            <div style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(11, 15, 25, 0.9)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              zIndex: 4,
              color: '#f87171'
            }}>
              <AlertCircle size={28} />
              <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>Could not load rendered slide image</div>
              <button
                className="overlay-btn"
                onClick={() => {
                  setImgTimestamp(Date.now());
                  setImgLoading(true);
                  setImgError(false);
                }}
              >
                Retry Render
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Main Interactive Slide Canvas */
        <div
          className="slide-canvas interactive-canvas"
          style={{
            backgroundColor: theme.bgColor,
            color: theme.textPrimary,
            fontFamily: theme.fontFamily
          }}
        >
          {/* Accent Bar */}
          <div
            className="slide-accent-bar"
            style={{
              background: `linear-gradient(90deg, ${theme.accentPrimary}, ${theme.accentSecondary})`
            }}
          />

          <div className="slide-inner">
            {/* Editable Category Badge */}
            <div className="badge-edit-wrap">
              <input
                type="text"
                className="editable-badge-input"
              size={Math.max((slide.category || '').length + 2, 16)}
              style={{
                backgroundColor: theme.badgeBg,
                color: theme.accentSecondary,
                borderColor: theme.accentPrimary
              }}
              value={slide.category || ''}
              placeholder="CATEGORY BADGE (e.g. EXECUTIVE STRATEGY)"
              onChange={(e) => handleFieldChange('category', e.target.value)}
            />
          </div>

          {/* Title Slide Layout */}
          {slide.type === 'title' ? (
            <div className="title-layout title-edit-layout">
              <div className="title-text-group">
                <AutoResizeTextarea
                  rows={1}
                  className="editable-hero-title"
                  style={{ color: theme.textPrimary }}
                  value={slide.title || ''}
                  placeholder="Enter Keynote Headline..."
                  onChange={(e) => handleFieldChange('title', e.target.value)}
                />

                <AutoResizeTextarea
                  rows={1}
                  className="editable-hero-subtitle"
                  style={{ color: theme.textSecondary }}
                  value={slide.subtitle || ''}
                  placeholder="Enter Subtitle or Strategic Thesis..."
                  onChange={(e) => handleFieldChange('subtitle', e.target.value)}
                />

                <div
                  className="hero-divider"
                  style={{ backgroundColor: theme.accentPrimary }}
                />
              </div>

              {/* Title Hero Visual Frame */}
              <div
                className="title-hero-frame"
                onClick={onOpenImageModal}
                style={cardStyle}
              >
                {slide.image_url ? (
                  <div className="hero-img-wrap">
                    <img src={slide.image_url} alt="Hero Visual" />
                    <div className="img-hover-overlay">
                      <Sparkles size={18} />
                      <span>Change AI Visual</span>
                    </div>
                  </div>
                ) : (
                  <div className="hero-img-placeholder">
                    <ImageIcon size={44} style={{ color: theme.accentPrimary, opacity: 0.8 }} />
                    <span className="placeholder-text">Click to Add Hero Visual</span>
                    <span className="placeholder-hint">Generated by Cloud Neural Diffusion</span>
                  </div>
                )}
              </div>
            </div>
          ) : slide.type === 'section' ? (
            /* Section Header Slide */
            <div className="section-layout title-edit-layout">
              <div className="title-text-group">
                <AutoResizeTextarea
                  rows={1}
                  className="editable-hero-title"
                  style={{ color: theme.textPrimary }}
                  value={slide.title || ''}
                  placeholder="Enter Section Headline..."
                  onChange={(e) => handleFieldChange('title', e.target.value)}
                />
                <AutoResizeTextarea
                  rows={1}
                  className="editable-hero-subtitle"
                  style={{ color: theme.textSecondary }}
                  value={slide.subtitle || ''}
                  placeholder="Enter section context or transition thesis..."
                  onChange={(e) => handleFieldChange('subtitle', e.target.value)}
                />
                <div
                  className="hero-divider"
                  style={{ backgroundColor: theme.accentPrimary }}
                />
              </div>
            </div>
          ) : (
            <>
              {/* Header for content slides */}
              <div className="content-header-edit">
                <input
                  type="text"
                  className="editable-slide-title"
                  style={{ color: theme.textPrimary }}
                  value={slide.title || ''}
                  placeholder="Enter Slide Title..."
                  onChange={(e) => handleFieldChange('title', e.target.value)}
                />

                <input
                  type="text"
                  className="editable-slide-subtitle"
                  style={{ color: theme.textSecondary }}
                  value={slide.subtitle || ''}
                  placeholder="Enter descriptive subtitle or core message..."
                  onChange={(e) => handleFieldChange('subtitle', e.target.value)}
                />
              </div>

              {/* Layout Specific Editors */}
              <div className="layout-body-edit">
                {/* 1. Metrics / KPI Layout */}
                {slide.type === 'metrics' ? (
                  <div className="metrics-editor-section">
                    <div className="metrics-grid">
                      {(slide.stats || []).map((st, i) => (
                        <div key={i} className="metric-card editable" style={cardStyle}>
                          <input
                            type="text"
                            className="stat-val-input"
                            style={{ color: theme.accentSecondary }}
                            value={st.value}
                            onChange={(e) => handleStatChange(i, 'value', e.target.value)}
                            placeholder="e.g. 99.4%"
                          />
                          <input
                            type="text"
                            className="stat-lbl-input"
                            style={{ color: theme.textPrimary }}
                            value={st.label}
                            onChange={(e) => handleStatChange(i, 'label', e.target.value)}
                            placeholder="e.g. Reliability"
                          />
                          <div className="stat-chg-wrap">
                            <TrendingUp size={13} style={{ color: theme.accentPrimary }} />
                            <input
                              type="text"
                              className="stat-chg-input"
                              style={{ color: theme.accentPrimary }}
                              value={st.change || ''}
                              onChange={(e) => handleStatChange(i, 'change', e.target.value)}
                              placeholder="+18% YoY"
                            />
                          </div>
                          <button
                            className="remove-stat-btn"
                            onClick={() => handleRemoveStat(i)}
                            title="Remove Metric"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    {(slide.stats || []).length < 4 && (
                      <button className="add-point-btn" onClick={handleAddStat}>
                        <Plus size={14} />
                        <span>Add Metric Card</span>
                      </button>
                    )}
                  </div>
                ) : (slide.type === 'timeline' || slide.type === 'process') ? (
                  /* 2. Timeline / Roadmap Layout */
                  <div className="timeline-editor-section">
                    <div className="timeline-grid">
                      {(slide.bullets || []).map((step, i) => (
                        <div key={i} className="timeline-step-card editable" style={cardStyle}>
                          <div className="step-pill" style={{ backgroundColor: theme.accentPrimary }}>
                            0{i + 1}
                          </div>
                          <div className="step-edit-box">
                            <AutoResizeTextarea
                              className="step-input"
                              style={{ color: theme.textPrimary }}
                              value={step}
                              placeholder="Phase title and key deliverables..."
                              onChange={(e) => handleBulletChange('bullets', i, e.target.value)}
                            />
                            <button
                              className="del-bullet-btn"
                              onClick={() => handleRemoveBullet('bullets', i)}
                              title="Delete Step"
                            >
                              ×
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                    {(slide.bullets || []).length < 5 && (
                      <button className="add-point-btn" onClick={() => handleAddBullet('bullets')}>
                        <Plus size={14} /> Add Timeline Phase
                      </button>
                    )}
                  </div>
                ) : (slide.type === 'diagram' || (slide.visual && slide.visual.diagram && slide.visual.diagram.nodes && slide.visual.diagram.nodes.length > 0)) ? (
                  /* 2b. Interactive Architecture Diagram & Topology Editor */
                  <ArchitectureDiagramView
                    slide={slide}
                    theme={theme}
                    editable={true}
                    onChangeDiagram={(newDiag) =>
                      handleFieldChange('visual', {
                        ...(slide.visual || {}),
                        kind: 'architecture',
                        diagram: newDiag,
                      })
                    }
                    onChangeBullets={(newBullets) => handleFieldChange('bullets', newBullets)}
                  />
                ) : (slide.type === 'table' || slide.table) ? (
                  /* 3. Structured Table Layout */
                  <div className="table-editor-section">
                    <div className="table-wrapper editable" style={cardStyle}>
                      <table className="slide-data-table">
                        <thead>
                          <tr>
                            {((slide.table?.headers) || ['Dimension', 'Baseline', 'Target', 'Impact']).map((h, i) => (
                              <th key={i} style={{ backgroundColor: theme.badgeBg, color: theme.accentSecondary }}>
                                <input
                                  type="text"
                                  className="table-header-input"
                                  value={h}
                                  onChange={(e) => handleTableHeaderChange(i, e.target.value)}
                                />
                              </th>
                            ))}
                            <th style={{ width: '40px', backgroundColor: theme.badgeBg }}></th>
                          </tr>
                        </thead>
                        <tbody>
                          {((slide.table?.rows) || [
                            ['Speed & Latency', '4-5 Days', 'Instant AI synthesis', '98% faster'],
                            ['Quality Score', 'Legacy template', 'Tailored isometric 3D', '10x engagement']
                          ]).map((row, rIdx) => (
                            <tr key={rIdx}>
                              {row.map((cell, cIdx) => (
                                <td key={cIdx} style={{ borderColor: theme.cardBorder }}>
                                  <input
                                    type="text"
                                    className="table-cell-input"
                                    style={{ color: theme.textPrimary }}
                                    value={cell}
                                    onChange={(e) => handleTableCellChange(rIdx, cIdx, e.target.value)}
                                  />
                                </td>
                              ))}
                              <td style={{ textAlign: 'center' }}>
                                <button
                                  className="del-bullet-btn"
                                  onClick={() => handleRemoveTableRow(rIdx)}
                                  title="Delete Row"
                                >
                                  ×
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <button className="add-point-btn" onClick={handleAddTableRow}>
                      <Plus size={14} /> Add Table Row
                    </button>
                  </div>
                ) : slide.type === 'two_column' ? (
                  /* 4. Two Column Layout */
                  <div className="two-column-grid editable">
                    <div className="column-card" style={cardStyle}>
                      <div className="column-header" style={{ color: theme.accentSecondary }}>
                        Primary Vector
                      </div>
                      <div className="bullet-edit-list">
                        {(slide.left || []).map((item, i) => (
                          <div key={i} className="bullet-edit-row">
                            <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                            <input
                              type="text"
                              className="bullet-input"
                              style={{ color: theme.textPrimary }}
                              value={item}
                              onChange={(e) => handleBulletChange('left', i, e.target.value)}
                            />
                            <button
                              className="del-bullet-btn"
                              onClick={() => handleRemoveBullet('left', i)}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button className="add-point-btn" onClick={() => handleAddBullet('left')}>
                          <Plus size={13} /> Add Point
                        </button>
                      </div>
                    </div>

                    <div className="column-card" style={cardStyle}>
                      <div className="column-header" style={{ color: theme.accentPrimary }}>
                        Comparative / Strategic Outcome
                      </div>
                      <div className="bullet-edit-list">
                        {(slide.right || []).map((item, i) => (
                          <div key={i} className="bullet-edit-row">
                            <span className="bullet-dot" style={{ backgroundColor: theme.accentSecondary }} />
                            <input
                              type="text"
                              className="bullet-input"
                              style={{ color: theme.textPrimary }}
                              value={item}
                              onChange={(e) => handleBulletChange('right', i, e.target.value)}
                            />
                            <button
                              className="del-bullet-btn"
                              onClick={() => handleRemoveBullet('right', i)}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button className="add-point-btn" onClick={() => handleAddBullet('right')}>
                          <Plus size={13} /> Add Point
                        </button>
                      </div>
                    </div>
                  </div>
                ) : slide.type === 'image_text' ? (
                  /* 5. Image & Text Layout */
                  <div className="image-text-grid editable">
                    <div className="image-text-content" style={cardStyle}>
                      <div className="bullet-edit-list">
                        {(slide.bullets || []).map((b, i) => (
                          <div key={i} className="bullet-edit-row">
                            <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                            <input
                              type="text"
                              className="bullet-input"
                              style={{ color: theme.textPrimary }}
                              value={b}
                              onChange={(e) => handleBulletChange('bullets', i, e.target.value)}
                            />
                            <button
                              className="del-bullet-btn"
                              onClick={() => handleRemoveBullet('bullets', i)}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button className="add-point-btn" onClick={() => handleAddBullet('bullets')}>
                          <Plus size={13} /> Add Bullet Point
                        </button>
                      </div>
                    </div>

                    <div
                      className="image-frame-wrap editable"
                      style={cardStyle}
                      onClick={onOpenImageModal}
                    >
                      {slide.image_url ? (
                        <div className="slide-img-box">
                          <img src={slide.image_url} alt="Slide Visual" className="slide-frame-img" />
                          <div className="img-hover-overlay">
                            <Sparkles size={18} />
                            <span>Regenerate with AI</span>
                          </div>
                        </div>
                      ) : (
                        <div className="image-placeholder">
                          <ImageIcon size={48} style={{ color: theme.accentPrimary, opacity: 0.8 }} />
                          <span className="placeholder-text">Click to Generate AI Visual</span>
                          <span className="placeholder-hint">Matches slide content automatically</span>
                        </div>
                      )}
                      <input
                        type="text"
                        className="caption-input"
                        style={{ color: theme.textSecondary }}
                        value={slide.image_caption || ''}
                        placeholder="Image Caption (e.g. Architecture Blueprint)"
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => handleFieldChange('image_caption', e.target.value)}
                      />
                    </div>
                  </div>
                ) : slide.type === 'quote' ? (
                  /* 6. Quote Layout */
                  <div className="quote-editor-wrap" style={cardStyle}>
                    <div
                      className="quote-bar"
                      style={{ backgroundColor: theme.accentPrimary }}
                    />
                    <div className="quote-text-col">
                      <AutoResizeTextarea
                        rows={2}
                        className="editable-quote-input"
                        style={{ color: theme.textPrimary }}
                        value={slide.quote || slide.subtitle || ''}
                        placeholder="Enter visionary executive quote or statement..."
                        onChange={(e) => handleFieldChange('quote', e.target.value)}
                      />
                    </div>
                  </div>
                ) : (
                  /* 7. Bullets / Strategic Takeaways Layout */
                  <div className="bullets-card editable" style={cardStyle}>
                    <div className="bullet-edit-list">
                      {(slide.bullets || []).map((b, i) => (
                        <div key={i} className="bullet-edit-row">
                          <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                          <input
                            type="text"
                            className="bullet-input"
                            style={{ color: theme.textPrimary }}
                            value={b}
                            onChange={(e) => handleBulletChange('bullets', i, e.target.value)}
                          />
                          <button
                            className="del-bullet-btn"
                            onClick={() => handleRemoveBullet('bullets', i)}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button className="add-point-btn" onClick={() => handleAddBullet('bullets')}>
                        <Plus size={13} /> Add Bullet Point
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Presenter Speaker Notes Drawer */}
          <div className="slide-notes-editor">
            <button
              className="notes-toggle-btn"
              onClick={() => setShowNotes(!showNotes)}
            >
              <BookOpen size={14} style={{ color: theme.accentPrimary }} />
              <span>{showNotes ? 'Hide Speaker Notes' : 'Edit Presenter Speaker Script'}</span>
            </button>
            {showNotes && (
              <AutoResizeTextarea
                rows={2}
                className="editable-notes-textarea"
                style={{
                  backgroundColor: theme.cardBg,
                  borderColor: theme.cardBorder,
                  color: theme.textPrimary
                }}
                value={slide.notes || ''}
                placeholder="Presenter talking points, keynote script, or spoken commentary for this slide..."
                onChange={(e) => handleFieldChange('notes', e.target.value)}
              />
            )}
          </div>

          {/* Running Slide Footer */}
          {slide.type !== 'title' && slide.type !== 'section' && (
            <div className="slide-footer-bar" style={{ borderColor: theme.cardBorder }}>
              <span className="slide-footer-left" style={{ color: theme.textSecondary }}>
                {deckTitle || 'Executive Presentation'}
              </span>
              <span className="slide-footer-right" style={{ color: theme.textSecondary }}>
                {String(slideIndex + 1).padStart(2, '0')} / {String(totalSlides).padStart(2, '0')}
              </span>
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
