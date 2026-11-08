import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles, Play, Download, Palette, Settings, Plus,
  ChevronDown, Layout, PanelLeft, SplitSquareVertical,
  Maximize2, MessageSquare, Monitor, SlidersHorizontal, Image as ImageIcon
} from 'lucide-react';
import { getThemeById } from '../themes';

export default function Navbar({
  activeDeck,
  activeThemeId,
  downloadUrl,
  activeSlideIndex = 0,
  isSidebarOpen,
  onToggleSidebar,
  viewMode = 'split',
  onChangeViewMode,
  onStartNewDeck,
  onOpenThemes,
  onOpenSettings,
  onOpenPresentation,
  onOpenNewDeckModal,
  onOpenTemplates,
  onExportJson,
  onPrintPdf
}) {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const theme = getThemeById(activeThemeId);
  const exportMenuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="navbar">
      <div className="navbar-left">
        {/* Sidebar Toggle Button */}
        <button
          className={`nav-btn btn-sidebar-toggle ${isSidebarOpen ? 'active' : ''}`}
          onClick={onToggleSidebar}
          title={isSidebarOpen ? "Collapse Gemini Sidebar" : "Expand Gemini Sidebar"}
        >
          <PanelLeft size={17} />
        </button>

        {/* Gemini Brand */}
        <div
          onClick={onStartNewDeck}
          className="brand-container"
          title="Google Gemini AI Presentation Studio"
        >
          <div className="gemini-star-badge">
            <Sparkles className="gemini-star-icon" size={17} />
          </div>
          <div className="brand-text">
            <span className="brand-title">Gemini</span>
            <span className="brand-tag">Slides</span>
          </div>
        </div>

        {/* Active Presentation Title */}
        {activeDeck && (
          <div className="active-deck-pill">
            <span className="deck-dot" style={{ backgroundColor: theme.accentPrimary }} />
            <span className="deck-title-truncate">{activeDeck.title}</span>
            <span className="deck-slide-count">{activeDeck.slides.length} slides</span>
          </div>
        )}
      </div>

      {/* Center: View Switcher (when active deck exists) */}
      {activeDeck && onChangeViewMode && (
        <div className="navbar-center">
          <div className="view-mode-tabs">
            <button
              className={`view-tab-btn ${viewMode === 'split' ? 'active' : ''}`}
              onClick={() => onChangeViewMode('split')}
              title="Split View: Gemini Chat on Left, Slide Editor on Right"
            >
              <SplitSquareVertical size={14} />
              <span>Split Studio</span>
            </button>
            <button
              className={`view-tab-btn ${viewMode === 'canvas' ? 'active' : ''}`}
              onClick={() => onChangeViewMode('canvas')}
              title="Canvas Focus: Full Slide Editing Workspace"
            >
              <Monitor size={14} />
              <span>Canvas Focus</span>
            </button>
            <button
              className={`view-tab-btn ${viewMode === 'chat' ? 'active' : ''}`}
              onClick={() => onChangeViewMode('chat')}
              title="Chat Focus: Conversational Feed with Gemini"
            >
              <MessageSquare size={14} />
              <span>Gemini Chat</span>
            </button>
          </div>
        </div>
      )}

      {/* Right Controls */}
      <div className="navbar-right">
        {/* + New Presentation Button */}
        <button
          className="nav-btn btn-new-deck"
          onClick={onStartNewDeck || onOpenNewDeckModal}
          title="Create New Presentation with Gemini"
        >
          <Plus size={15} />
          <span>New Deck</span>
        </button>

        {/* Theme Picker */}
        <button className="nav-btn" onClick={onOpenThemes} title="Select Design Theme">
          <Palette size={15} />
          <span>{theme.name}</span>
        </button>

        {/* Template Lab option */}
        {onOpenTemplates && (
          <button className="nav-btn" onClick={onOpenTemplates} title="PowerPoint Templates & Reverse Engineering Lab">
            <Layout size={15} />
            <span>Templates</span>
          </button>
        )}

        {/* Settings */}
        <button className="nav-btn icon-only" onClick={onOpenSettings} title="Settings & API Keys">
          <Settings size={16} />
        </button>

        {activeDeck && (
          <>
            {/* Fullscreen Present (F5) */}
            <button
              className="nav-btn btn-present"
              onClick={() => onOpenPresentation(0)}
              title="Enter Fullscreen Presentation Mode"
            >
              <Play size={14} fill="currentColor" />
              <span>Present</span>
            </button>

            {/* Direct Download .pptx Primary Button */}
            {downloadUrl ? (
              <a
                href={downloadUrl}
                download
                className="nav-btn btn-download primary-download"
                title="Download Microsoft PowerPoint (.pptx)"
              >
                <Download size={14} />
                <span>Export PPTX</span>
              </a>
            ) : null}

            {/* Export Dropdown Menu */}
            <div className="export-dropdown-wrapper" ref={exportMenuRef} style={{ position: 'relative' }}>
              <button
                className="nav-btn btn-export-options"
                onClick={() => setShowExportMenu(!showExportMenu)}
                title="More Export Options"
              >
                <span>Export</span>
                <ChevronDown size={14} style={{ marginLeft: '2px' }} />
              </button>

              {showExportMenu && (
                <div className="export-menu-dropdown">
                  {downloadUrl && (
                    <>
                      <a
                        href={downloadUrl}
                        download
                        className="export-menu-item"
                        onClick={() => setShowExportMenu(false)}
                        title="Download as Microsoft PowerPoint presentation"
                      >
                        <Download size={16} className="text-accent" />
                        <div>
                          <div className="menu-item-title">PowerPoint (.pptx)</div>
                          <div className="menu-item-desc">Native Microsoft Office slides with graphics</div>
                        </div>
                      </a>

                      <a
                        href={`${downloadUrl.replace(/\/$/, '')}/slides/zip`}
                        download
                        className="export-menu-item"
                        onClick={() => setShowExportMenu(false)}
                        title="Download all slides as 1920x1080 PNG images in a ZIP bundle"
                      >
                        <ImageIcon size={16} style={{ color: '#10b981' }} />
                        <div>
                          <div className="menu-item-title">Slide Images (.zip)</div>
                          <div className="menu-item-desc">All slides exported as high-res 1920x1080 PNGs</div>
                        </div>
                      </a>

                      <a
                        href={`${downloadUrl.replace(/\/$/, '')}/slides/${(activeSlideIndex || 0) + 1}/image?download=true`}
                        download
                        className="export-menu-item"
                        onClick={() => setShowExportMenu(false)}
                        title={`Download Slide ${(activeSlideIndex || 0) + 1} as 1920x1080 PNG`}
                      >
                        <Download size={16} style={{ color: '#06b6d4' }} />
                        <div>
                          <div className="menu-item-title">Current Slide (PNG)</div>
                          <div className="menu-item-desc">Export Slide {(activeSlideIndex || 0) + 1} as high-res PNG image</div>
                        </div>
                      </a>

                      <a
                        href={`${downloadUrl.replace(/\/$/, '')}/pdf`}
                        download
                        className="export-menu-item"
                        onClick={() => setShowExportMenu(false)}
                        title="Download as PDF"
                      >
                        <Monitor size={16} />
                        <div>
                          <div className="menu-item-title">PDF (.pdf)</div>
                          <div className="menu-item-desc">Exact vector copy of the PowerPoint slides</div>
                        </div>
                      </a>
                    </>
                  )}

                  <button
                    className="export-menu-item"
                    onClick={() => {
                      setShowExportMenu(false);
                      onExportJson && onExportJson();
                    }}
                  >
                    <Download size={16} />
                    <div>
                      <div className="menu-item-title">JSON Deck Schema</div>
                      <div className="menu-item-desc">Raw structured slide outline & metadata</div>
                    </div>
                  </button>

                  <button
                    className="export-menu-item"
                    onClick={() => {
                      setShowExportMenu(false);
                      onPrintPdf && onPrintPdf();
                    }}
                  >
                    <Monitor size={16} />
                    <div>
                      <div className="menu-item-title">Print / Save as PDF</div>
                      <div className="menu-item-desc">Browser print-ready handout view</div>
                    </div>
                  </button>

                </div>
              )}
            </div>
          </>
        )}
      </div>
    </header>
  );
}
