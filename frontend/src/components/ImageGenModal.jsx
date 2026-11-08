import React, { useState, useEffect } from 'react';
import {
  Sparkles, X, Wand2, Image as ImageIcon, Loader2,
  Check, RefreshCw, Cpu, Camera, Zap, Palette, Layers
} from 'lucide-react';

const STYLES = [
  { id: '3d', label: '3D Isometric', icon: BoxIcon, desc: 'Octane render, glassmorphism, clean lighting' },
  { id: 'photo', label: 'Editorial Photo', icon: Camera, desc: 'Cinematic studio lighting, high realism' },
  { id: 'cyberpunk', label: 'Cyberpunk Neon', icon: Zap, desc: 'Glowing neural streams, holographic vibes' },
  { id: 'vector', label: 'Flat Vector', icon: Palette, desc: 'Clean corporate tech, minimalist lines' },
  { id: 'abstract', label: 'Abstract Luxury', icon: Layers, desc: 'Dynamic iridescent silk waves, fluid gradients' }
];

function BoxIcon(props) {
  return <Cpu {...props} />;
}

export default function ImageGenModal({
  isOpen,
  onClose,
  slide,
  deckTitle,
  apiKey,
  onImageApplied
}) {
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('3d');
  const [provider, setProvider] = useState('diffusion');
  const [isGenerating, setIsGenerating] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (slide) {
      // Auto-suggest a high-converting prompt based on slide content
      const topicContext = deckTitle ? `${deckTitle} - ` : '';
      const defaultP = `${topicContext}${slide.title || 'Executive Keynote Visual'}`;
      setPrompt(defaultP);
      setPreviewImage(slide.image_url || null);
      setError(null);
    }
  }, [slide, deckTitle, isOpen]);

  if (!isOpen || !slide) return null;

  const handleGenerate = async () => {
    if (!prompt.trim() || isGenerating) return;
    setIsGenerating(true);
    setError(null);

    try {
      const res = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          slide_title: slide.title,
          topic: deckTitle || '',
          category: slide.category || '',
          style: style,
          custom_prompt: prompt.trim(),
          preferred_provider: provider,
          api_key: apiKey || '',
          slide_id: slide.id || ''
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to generate visual');
      }

      const data = await res.json();
      setPreviewImage(data.url);
      
      // Auto-apply or inform parent
      onImageApplied({
        slideId: slide.id,
        imageUrl: data.url,
        imageId: data.filename,
        caption: data.caption,
        prompt: data.prompt
      });
    } catch (err) {
      console.error('Image generation error:', err);
      setError(err.message || 'Image generation failed. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container image-gen-modal" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-header-title">
            <div className="icon-glow-badge">
              <Sparkles size={18} className="text-accent" />
            </div>
            <div>
              <h3>Generate AI Visual for Slide</h3>
              <p className="modal-subtitle">
                Powered by Cloud Diffusion Neural Networks & Deep Learning
              </p>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* Target Slide Context Pill */}
          <div className="context-pill">
            <span className="context-label">Target Slide:</span>
            <span className="context-title">{slide.title || 'Untitled Slide'}</span>
            <span className="context-badge">{slide.category || slide.type}</span>
          </div>

          {/* Prompt Input */}
          <div className="form-group">
            <div className="label-with-action">
              <label htmlFor="img-prompt">Visual Concept Prompt</label>
              <button
                type="button"
                className="btn-text-action"
                onClick={() => setPrompt(`${deckTitle || ''} ${slide.title}: modern futuristic concept visualization`)}
              >
                <Wand2 size={13} />
                <span>Auto-Refine</span>
              </button>
            </div>
            <textarea
              id="img-prompt"
              rows={3}
              className="modal-textarea"
              placeholder="Describe the visual you want (e.g., Futuristic cloud computing servers with neural data streams...)"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          {/* Style Selector Chips */}
          <div className="form-group">
            <label>Neural Visual Style</label>
            <div className="style-chips-grid">
              {STYLES.map((st) => {
                const IconComponent = st.icon;
                const isSelected = style === st.id;
                return (
                  <div
                    key={st.id}
                    className={`style-chip ${isSelected ? 'selected' : ''}`}
                    onClick={() => setStyle(st.id)}
                  >
                    <div className="chip-icon-wrap">
                      <IconComponent size={18} />
                    </div>
                    <div className="chip-info">
                      <div className="chip-label">{st.label}</div>
                      <div className="chip-desc">{st.desc}</div>
                    </div>
                    {isSelected && <Check size={14} className="chip-check" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Cloud Provider Alternative Selector */}
          <div className="form-group">
            <label>Visual Generation Engine</label>
            <div className="provider-options">
              <label className={`provider-radio ${provider === 'openai' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value="openai"
                  checked={provider === 'openai'}
                  onChange={() => setProvider('openai')}
                />
                <div>
                  <div className="p-title">OpenAI DALL·E 3 (Widescreen 16:9 HD)</div>
                  <div className="p-sub">OpenAI flagship image synthesis • Best for keynote visuals (uses OpenAI API key)</div>
                </div>
              </label>

              <label className={`provider-radio ${provider === 'diffusion' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value="diffusion"
                  checked={provider === 'diffusion'}
                  onChange={() => setProvider('diffusion')}
                />
                <div>
                  <div className="p-title">Cloud Neural Diffusion (FLUX / Turbo)</div>
                  <div className="p-sub">Generative AI visual models • High aesthetic quality • Fast</div>
                </div>
              </label>

              <label className={`provider-radio ${provider === 'web' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value="web"
                  checked={provider === 'web'}
                  onChange={() => setProvider('web')}
                />
                <div>
                  <div className="p-title">Verified Web Photography (Wikimedia & Web References)</div>
                  <div className="p-sub">Authentic real-world photography & scientific images from the web</div>
                </div>
              </label>

              <label className={`provider-radio ${provider === 'gemini' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value="gemini"
                  checked={provider === 'gemini'}
                  onChange={() => setProvider('gemini')}
                />
                <div>
                  <div className="p-title">Google Gemini / Imagen 3</div>
                  <div className="p-sub">Google Vertex AI • High-res generative art (requires Gemini key)</div>
                </div>
              </label>

              <label className={`provider-radio ${provider === 'stock' ? 'active' : ''}`}>
                <input
                  type="radio"
                  name="provider"
                  value="stock"
                  checked={provider === 'stock'}
                  onChange={() => setProvider('stock')}
                />
                <div>
                  <div className="p-title">Curated Stock Photography (Unsplash)</div>
                  <div className="p-sub">Studio lighting & editorial quality stock photos</div>
                </div>
              </label>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="modal-error-banner">
              {error}
            </div>
          )}

          {/* Live Preview Display */}
          {previewImage && (
            <div className="preview-image-section">
              <div className="preview-label">Active Image on Slide:</div>
              <div className="preview-img-frame">
                <img src={previewImage} alt="Generated Slide Visual" />
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={isGenerating}>
            Done
          </button>

          <button
            className="btn-primary"
            onClick={handleGenerate}
            disabled={isGenerating || !prompt.trim()}
          >
            {isGenerating ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Generating Neural Image...</span>
              </>
            ) : (
              <>
                <Sparkles size={16} />
                <span>{previewImage ? 'Regenerate Visual' : 'Generate Visual'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
