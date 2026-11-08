import React from 'react';
import { getThemeById } from '../themes';
import { TrendingUp, Sparkles, Image as ImageIcon } from 'lucide-react';
import ArchitectureDiagramView from './ArchitectureDiagramView';
import '../slides.css';

export default function SlideCanvas({
  slide,
  themeId = 'google-gemini',
  isThumbnail = false,
  slideIndex = 0,
  totalSlides = 1,
  deckTitle = ''
}) {
  const theme = getThemeById(themeId);

  if (!slide) return null;

  const {
    type = 'bullets',
    category = '',
    title = '',
    subtitle = '',
    bullets = [],
    left = [],
    right = [],
    stats = [],
    table = null,
    image_url = '',
    image_caption = '',
  } = slide;

  const cardStyle = {
    backgroundColor: theme.cardBg,
    borderColor: theme.cardBorder,
    color: theme.textPrimary
  };

  return (
    <div
      className={`slide-canvas ${isThumbnail ? 'thumbnail' : ''}`}
      style={{
        backgroundColor: theme.bgColor,
        color: theme.textPrimary,
        fontFamily: theme.fontFamily
      }}
    >
      {/* Top accent glow line */}
      <div 
        className="slide-accent-bar" 
        style={{ 
          background: `linear-gradient(90deg, ${theme.accentPrimary}, ${theme.accentSecondary})` 
        }} 
      />

      {/* Main Slide Body */}
      <div className="slide-inner">
        {/* Category Badge */}
        {category && (
          <div
            className="slide-badge"
            style={{
              backgroundColor: theme.badgeBg,
              color: theme.accentSecondary,
              borderColor: theme.accentPrimary
            }}
          >
            <Sparkles size={12} style={{ marginRight: '6px' }} />
            {category.toUpperCase()}
          </div>
        )}

        {/* 1. Title Slide Layout */}
        {type === 'title' ? (
          <div className={`title-layout ${image_url ? 'has-hero-image' : ''}`}>
            <div className="title-text-group">
              <h1 className="hero-title" style={{ color: theme.textPrimary }}>
                {title || 'Keynote Presentation'}
              </h1>
              {subtitle && (
                <p className="hero-subtitle" style={{ color: theme.textSecondary }}>
                  {subtitle}
                </p>
              )}
              <div 
                className="hero-divider" 
                style={{ backgroundColor: theme.accentPrimary }} 
              />
            </div>
            {image_url && (
              <div className="hero-image-wrap" style={cardStyle}>
                <img src={image_url} alt="Hero Visual" />
                {image_caption && (
                  <div className="hero-caption" style={{ color: theme.textSecondary }}>
                    {image_caption}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : type === 'section' ? (
          /* 2. Section Header Divider Slide */
          <div className="section-layout">
            <h1 className="section-hero-title" style={{ color: theme.textPrimary }}>
              {title}
            </h1>
            {subtitle && (
              <p className="section-hero-subtitle" style={{ color: theme.textSecondary }}>
                {subtitle}
              </p>
            )}
            <div 
              className="section-hero-divider" 
              style={{ backgroundColor: theme.accentPrimary }} 
            />
          </div>
        ) : (
          <>
            {/* Header for content slides */}
            <div className="content-header">
              <h2 className="slide-title" style={{ color: theme.textPrimary }}>
                {title}
              </h2>
              {subtitle && (
                <p className="slide-subtitle" style={{ color: theme.textSecondary }}>
                  {subtitle}
                </p>
              )}
            </div>

            {/* Layout Specific Rendering */}
            <div className="layout-body">
              {/* 3. Metrics / KPI Layout */}
              {(type === 'metrics' || (stats && stats.length > 0)) ? (
                <div className="metrics-grid">
                  {stats.map((st, i) => (
                    <div key={i} className="metric-card" style={cardStyle}>
                      <div className="metric-value" style={{ color: theme.accentSecondary }}>
                        {st.value}
                      </div>
                      <div className="metric-label" style={{ color: theme.textPrimary }}>
                        {st.label}
                      </div>
                      {st.change && (
                        <div className="metric-change" style={{ color: theme.accentPrimary }}>
                          <TrendingUp size={14} style={{ marginRight: '4px' }} />
                          {st.change}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (type === 'timeline' || type === 'process') ? (
                /* 4. Timeline / Process Roadmap Layout */
                <div className="timeline-grid">
                  {(bullets && bullets.length > 0 ? bullets : ['Phase 1', 'Phase 2', 'Phase 3', 'Phase 4']).slice(0, 4).map((step, i) => (
                    <div key={i} className="timeline-step-card" style={cardStyle}>
                      <div className="step-pill" style={{ backgroundColor: theme.accentPrimary }}>
                        0{i + 1}
                      </div>
                      <div className="step-content">
                        <div className="step-text" style={{ color: theme.textPrimary }}>
                          {step.replace(/^•\s*/, '')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (type === 'diagram' || (slide.visual && slide.visual.diagram && slide.visual.diagram.nodes && slide.visual.diagram.nodes.length > 0)) ? (
                /* 4b. System Architecture & Component Topology Layout */
                <ArchitectureDiagramView slide={slide} theme={theme} editable={false} />
              ) : (type === 'table' || table) ? (
                /* 5. Structured Table Layout */
                <div className="table-wrapper" style={cardStyle}>
                  <table className="slide-data-table">
                    <thead>
                      <tr>
                        {((table && table.headers) || ['Dimension', 'Baseline', 'Target', 'Impact']).map((h, i) => (
                          <th key={i} style={{ backgroundColor: theme.badgeBg, color: theme.accentSecondary }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {((table && table.rows) || [
                        ['Performance', 'Legacy 4-5 days', 'Instant AI synthesis', '98% faster'],
                        ['Visual Quality', 'Generic clip art', 'Tailored isometric 3D', '10x engagement'],
                        ['Governance', 'Fragmented manual checks', 'Strict schema validation', '100% reliable']
                      ]).map((row, rIdx) => (
                        <tr key={rIdx} style={{ backgroundColor: rIdx % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                          {row.map((cell, cIdx) => (
                            <td key={cIdx} style={{ color: theme.textPrimary, borderColor: theme.cardBorder }}>
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : type === 'two_column' || (left.length > 0 && right.length > 0) ? (
                /* 6. Two Column Comparison Layout */
                <div className="two-column-grid">
                  <div className="column-card" style={cardStyle}>
                    <div className="column-header" style={{ color: theme.accentSecondary }}>
                      Key Analysis
                    </div>
                    <ul className="bullet-list">
                      {left.map((item, i) => (
                        <li key={i} style={{ color: theme.textPrimary }}>
                          <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                          <span>{item.replace(/^•\s*/, '')}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="column-card" style={cardStyle}>
                    <div className="column-header" style={{ color: theme.accentPrimary }}>
                      Strategic Outcomes
                    </div>
                    <ul className="bullet-list">
                      {right.map((item, i) => (
                        <li key={i} style={{ color: theme.textPrimary }}>
                          <span className="bullet-dot" style={{ backgroundColor: theme.accentSecondary }} />
                          <span>{item.replace(/^•\s*/, '')}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : type === 'image_text' || image_url ? (
                /* 7. Image & Text Layout */
                <div className="image-text-grid">
                  <div className="image-text-content" style={cardStyle}>
                    <ul className="bullet-list">
                      {bullets.map((b, i) => (
                        <li key={i} style={{ color: theme.textPrimary }}>
                          <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                          <span>{b.replace(/^•\s*/, '')}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="image-frame-wrap" style={cardStyle}>
                    {image_url ? (
                      <img src={image_url} alt="Slide Visual" className="slide-frame-img" />
                    ) : (
                      <div className="image-placeholder">
                        <ImageIcon size={48} style={{ color: theme.accentPrimary, opacity: 0.7 }} />
                        <span>{image_caption || 'Visual Asset'}</span>
                      </div>
                    )}
                    {image_caption && (
                      <div className="image-caption" style={{ color: theme.textSecondary }}>
                        {image_caption}
                      </div>
                    )}
                  </div>
                </div>
              ) : (type === 'quote' || slide.quote) ? (
                /* 8. Executive Quote Layout */
                <div className="quote-display-card" style={cardStyle}>
                  <div className="quote-vertical-bar" style={{ backgroundColor: theme.accentPrimary }} />
                  <div className="quote-text-content">
                    <p className="quote-large-text" style={{ color: theme.textPrimary }}>
                      "{slide.quote || subtitle || (bullets && bullets[0]) || 'Strategic Vision'}"
                    </p>
                  </div>
                </div>
              ) : (
                /* 9. Bullets / Strategic Takeaways Layout */
                <div className="bullets-card" style={cardStyle}>
                  <ul className="bullet-list">
                    {bullets.map((b, i) => (
                      <li key={i} style={{ color: theme.textPrimary }}>
                        <span className="bullet-dot" style={{ backgroundColor: theme.accentPrimary }} />
                        <span>{b.replace(/^•\s*/, '')}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Running Slide Footer */}
            {!isThumbnail && (
              <div className="slide-footer-bar" style={{ borderColor: theme.cardBorder }}>
                <span className="slide-footer-left" style={{ color: theme.textSecondary }}>
                  {deckTitle || 'Executive Presentation'}
                </span>
                <span className="slide-footer-right" style={{ color: theme.textSecondary }}>
                  {String(slideIndex + 1).padStart(2, '0')} / {String(totalSlides).padStart(2, '0')}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
