import React from 'react';
import { X, Check, Palette } from 'lucide-react';
import { THEMES } from '../themes';

export default function ThemeModal({ isOpen, onClose, activeThemeId, onSelectTheme }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <Palette size={20} className="text-accent" />
            <h3>Presentation Design Themes</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <p className="modal-desc">
          Choose a visual design language for your slides. Applied automatically to your PPTX and live presentation mode.
        </p>

        <div className="theme-grid">
          {THEMES.map((theme) => {
            const isSelected = activeThemeId === theme.id;
            return (
              <div
                key={theme.id}
                className={`theme-card ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  onSelectTheme(theme.id);
                  onClose();
                }}
                style={{
                  border: isSelected
                    ? `2px solid ${theme.accentPrimary}`
                    : '1px solid rgba(255, 255, 255, 0.1)'
                }}
              >
                <div
                  className="theme-card-preview"
                  style={{
                    background: theme.gradient,
                    color: theme.textPrimary
                  }}
                >
                  <div
                    className="preview-mini-badge"
                    style={{ backgroundColor: theme.badgeBg, color: theme.accentSecondary }}
                  >
                    {theme.darkMode ? 'DARK' : 'LIGHT'}
                  </div>
                  <div className="preview-mini-title">Sample Deck Title</div>
                  <div className="preview-mini-bullets">
                    <span style={{ backgroundColor: theme.accentPrimary }} />
                    <span style={{ backgroundColor: theme.accentSecondary }} />
                  </div>
                </div>

                <div className="theme-card-body">
                  <div className="theme-card-title-row">
                    <span className="theme-name">{theme.name}</span>
                    {isSelected && (
                      <span className="selected-tag" style={{ color: theme.accentPrimary }}>
                        <Check size={16} />
                      </span>
                    )}
                  </div>
                  <p className="theme-desc">{theme.description}</p>

                  <div className="color-swatches">
                    <div className="swatch" style={{ backgroundColor: theme.bgColor }} title="Background" />
                    <div className="swatch" style={{ backgroundColor: theme.cardBg }} title="Cards" />
                    <div className="swatch" style={{ backgroundColor: theme.accentPrimary }} title="Accent Primary" />
                    <div className="swatch" style={{ backgroundColor: theme.accentSecondary }} title="Accent Secondary" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
