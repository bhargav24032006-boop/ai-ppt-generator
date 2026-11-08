import React, { useState, useEffect, useRef } from 'react';
import {
  X, ChevronLeft, ChevronRight, Maximize2, Minimize2,
  Download, Volume2, BookOpen, Clock, Crosshair
} from 'lucide-react';
import SlideCanvas from './SlideCanvas';
import { getThemeById } from '../themes';

export default function PresentationModal({
  deck,
  themeId,
  downloadUrl,
  isOpen,
  onClose,
  initialSlideIndex = 0
}) {
  const [currentIndex, setCurrentIndex] = useState(initialSlideIndex);
  const [showNotes, setShowNotes] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLaserPointer, setIsLaserPointer] = useState(false);
  const [laserPos, setLaserPos] = useState({ x: -100, y: -100 });
  const [timerSeconds, setTimerSeconds] = useState(0);
  const [isTimerRunning, setIsTimerRunning] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    setCurrentIndex(initialSlideIndex);
    setTimerSeconds(0);
    setIsTimerRunning(true);
  }, [initialSlideIndex, isOpen]);

  // Presentation stopwatch timer
  useEffect(() => {
    if (!isOpen || !isTimerRunning) return;
    const interval = setInterval(() => {
      setTimerSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isOpen, isTimerRunning]);

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
        e.preventDefault();
        nextSlide();
      } else if (e.key === 'ArrowLeft' || e.key === 'Backspace' || e.key === 'PageUp') {
        e.preventDefault();
        prevSlide();
      } else if (e.key === 'Escape') {
        if (document.fullscreenElement) {
          document.exitFullscreen();
        } else {
          onClose();
        }
      } else if (e.key === 'f' || e.key === 'F') {
        toggleFullscreen();
      } else if (e.key === 'n' || e.key === 'N') {
        setShowNotes((prev) => !prev);
      } else if (e.key === 'l' || e.key === 'L') {
        setIsLaserPointer((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, deck]);

  const handleMouseMove = (e) => {
    if (isLaserPointer && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setLaserPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
      });
    }
  };

  if (!isOpen || !deck || !deck.slides || deck.slides.length === 0) {
    return null;
  }

  const slides = deck.slides;
  const currentSlide = slides[currentIndex] || slides[0];
  const theme = getThemeById(themeId || deck.theme_id);

  const nextSlide = () => {
    if (currentIndex < slides.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const prevSlide = () => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen().catch((err) => {
        console.error('Fullscreen error:', err);
      });
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch((err) => console.error(err));
      setIsFullscreen(false);
    }
  };

  return (
    <div
      className={`presentation-backdrop ${isLaserPointer ? 'laser-mode' : ''}`}
      ref={containerRef}
      onMouseMove={handleMouseMove}
    >
      {/* Laser Pointer Dot */}
      {isLaserPointer && (
        <div
          className="laser-pointer-dot"
          style={{
            left: `${laserPos.x}px`,
            top: `${laserPos.y}px`
          }}
        />
      )}

      {/* Top Floating Control Bar */}
      <div className="presentation-header">
        <div className="header-left">
          <span className="deck-title-badge">{deck.title}</span>
          <span className="slide-counter">
            Slide {currentIndex + 1} of {slides.length}
          </span>
          <span className="theme-tag" style={{ color: theme.accentSecondary }}>
            {theme.name}
          </span>
          {/* Stopwatch Timer */}
          <div className="presentation-timer" onClick={() => setIsTimerRunning(!isTimerRunning)} title="Click to Pause/Resume Timer">
            <Clock size={14} className={isTimerRunning ? 'text-accent' : 'text-muted'} />
            <span>{formatTimer(timerSeconds)}</span>
          </div>
        </div>

        <div className="header-right">
          {/* Laser Pointer Mode Toggle */}
          <button
            className={`btn-control ${isLaserPointer ? 'active' : ''}`}
            onClick={() => setIsLaserPointer(!isLaserPointer)}
            title="Toggle Laser Pointer Mode (L)"
          >
            <Crosshair size={17} />
            <span>Laser</span>
          </button>

          {/* Speaker Notes Toggle */}
          <button
            className={`btn-control ${showNotes ? 'active' : ''}`}
            onClick={() => setShowNotes(!showNotes)}
            title="Toggle Speaker Notes (N)"
          >
            <BookOpen size={17} />
            <span>Notes</span>
          </button>

          {downloadUrl && (
            <a
              href={downloadUrl}
              download
              className="btn-control highlight"
              title="Download PowerPoint Presentation"
            >
              <Download size={17} />
              <span>PPTX</span>
            </a>
          )}

          <button
            className="btn-control"
            onClick={toggleFullscreen}
            title="Toggle Fullscreen (F)"
          >
            {isFullscreen ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </button>

          <button className="btn-control close-btn" onClick={onClose} title="Exit Presentation (Esc)">
            <X size={19} />
          </button>
        </div>
      </div>

      {/* Main Slide Presentation Stage */}
      <div className="presentation-stage">
        <button
          className="nav-arrow left"
          onClick={prevSlide}
          disabled={currentIndex === 0}
          title="Previous Slide (Left Arrow / PageUp)"
        >
          <ChevronLeft size={36} />
        </button>

        <div className="slide-viewport">
          <SlideCanvas
            slide={currentSlide}
            themeId={themeId || deck.theme_id}
            isThumbnail={false}
          />
        </div>

        <button
          className="nav-arrow right"
          onClick={nextSlide}
          disabled={currentIndex === slides.length - 1}
          title="Next Slide (Right Arrow / Space / PageDown)"
        >
          <ChevronRight size={36} />
        </button>
      </div>

      {/* Presenter Speaker Notes Drawer */}
      {showNotes && (
        <div className="speaker-notes-drawer">
          <div className="notes-header">
            <div className="notes-title">
              <Volume2 size={18} style={{ color: theme.accentPrimary }} />
              <span>Speaker Script & Keynote Talking Points</span>
            </div>
            <button className="close-notes" onClick={() => setShowNotes(false)}>
              <X size={16} />
            </button>
          </div>
          <div className="notes-content">
            {currentSlide.notes ? (
              <p>{currentSlide.notes}</p>
            ) : (
              <p className="no-notes">
                No specific speaker notes for this slide. Speak naturally around the key points!
              </p>
            )}
          </div>
        </div>
      )}

      {/* Bottom Thumbnail Navigation Rail */}
      <div className="thumbnail-rail">
        {slides.map((s, idx) => (
          <div
            key={s.id || idx}
            className={`thumb-card ${idx === currentIndex ? 'active' : ''}`}
            onClick={() => setCurrentIndex(idx)}
            style={{
              borderColor: idx === currentIndex ? theme.accentPrimary : 'transparent'
            }}
          >
            <div className="thumb-index">{idx + 1}</div>
            <div className="thumb-title">{s.title || `Slide ${idx + 1}`}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
