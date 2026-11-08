import React, { useState, useEffect } from 'react';
import {
  X, Key, ShieldCheck, Cpu, Sparkles, CheckCircle2,
  AlertCircle, Loader2, Globe, Server, Check, ArrowRight
} from 'lucide-react';

const DEFAULT_GROK_KEY = "grok_46580b20988b83a360d82699b8e2cf39_a6b20bd9ec170814e3a38176c18d669f51f80a893d345a2cf0fbeeda1798e256";

const PROVIDER_METADATA = {
  openai: {
    name: 'OpenAI',
    icon: Sparkles,
    color: '#10b981',
    placeholder: 'sk-proj-... or sk-...',
    models: [
      { id: 'gpt-4o-mini', label: 'GPT-4o Mini (Recommended — Fast & Structured JSON)' },
      { id: 'gpt-4o', label: 'GPT-4o (Flagship Multimodal Keynote Strategist)' },
      { id: 'gpt-4.1', label: 'GPT-4.1 (High-Precision Reasoning & Synthesis)' },
      { id: 'gpt-4.1-mini', label: 'GPT-4.1 Mini (Fast & High Fidelity)' },
      { id: 'o3-mini', label: 'o3-mini (Deep Reasoning Model)' }
    ],
    defaultModel: 'gpt-4o-mini',
    docsUrl: 'https://platform.openai.com/api-keys'
  },
  gemini: {
    name: 'Google Gemini',
    icon: Cpu,
    color: '#38bdf8',
    placeholder: 'AIzaSy...',
    models: [
      { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Fast)' },
      { id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
      { id: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro (Deep Reasoning)' },
      { id: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' }
    ],
    defaultModel: 'gemini-2.0-flash',
    docsUrl: 'https://aistudio.google.com/app/apikey'
  },
  claude: {
    name: 'Anthropic Claude',
    icon: Server,
    color: '#f59e0b',
    placeholder: 'sk-ant-...',
    models: [
      { id: 'claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku (Fast & Precise)' },
      { id: 'claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' }
    ],
    defaultModel: 'claude-3-5-haiku-20241022',
    docsUrl: 'https://console.anthropic.com/'
  },
  grok: {
    name: 'Grok / xAI',
    icon: Sparkles,
    color: '#818cf8',
    placeholder: 'grok_... or xai-...',
    models: [
      { id: 'grok-2-latest', label: 'Grok 2 Latest' },
      { id: 'grok-2-1212', label: 'Grok 2 (Dec 2024)' },
      { id: 'grok-beta', label: 'Grok Beta' }
    ],
    defaultModel: 'grok-2-latest',
    docsUrl: 'https://console.x.ai/'
  },
  custom: {
    name: 'Custom / OpenRouter',
    icon: Globe,
    color: '#a855f7',
    placeholder: 'sk-or-v1-... or your endpoint key',
    models: [
      { id: 'deepseek/deepseek-chat', label: 'DeepSeek Chat (OpenRouter)' },
      { id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B (OpenRouter)' },
      { id: 'gpt-4o-mini', label: 'Custom Endpoint Default' }
    ],
    defaultModel: 'deepseek/deepseek-chat',
    docsUrl: 'https://openrouter.ai/keys'
  }
};

function inferProviderFromKey(key, fallback = 'openai') {
  if (!key) return fallback;
  const k = key.trim();
  if (k.startsWith('AIza')) return 'gemini';
  if (k.startsWith('sk-ant-')) return 'claude';
  if (k.startsWith('sk-or-')) return 'custom';
  if (k.startsWith('grok_') || k.startsWith('xai-')) return 'grok';
  if (k.startsWith('sk-')) return 'openai';
  return fallback;
}

export default function SettingsModal({
  isOpen,
  onClose,
  apiKey,
  onSaveApiKey,
  initialProvider = 'openai',
  initialModel = 'gpt-4o-mini'
}) {
  const [provider, setProvider] = useState(() => {
    const savedProv = localStorage.getItem('slidecraft_provider');
    return inferProviderFromKey(apiKey, savedProv || initialProvider || 'openai');
  });

  const [inputKey, setInputKey] = useState(apiKey || '');
  const [selectedModel, setSelectedModel] = useState(
    initialModel || PROVIDER_METADATA.openai.defaultModel
  );
  const [baseUrl, setBaseUrl] = useState('');
  
  // Test connection state
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setInputKey(apiKey || '');
      const savedProv = localStorage.getItem('slidecraft_provider');
      const detected = inferProviderFromKey(apiKey, savedProv || initialProvider || 'openai');
      setProvider(detected);
      const savedModel = localStorage.getItem(`slidecraft_model_${detected}`);
      setSelectedModel(savedModel || PROVIDER_METADATA[detected]?.defaultModel || 'gpt-4o-mini');
    }
  }, [apiKey, isOpen, initialProvider]);

  // Load provider preferences from localStorage
  useEffect(() => {
    const savedModel = localStorage.getItem(`slidecraft_model_${provider}`);
    if (savedModel) setSelectedModel(savedModel);
    else setSelectedModel(PROVIDER_METADATA[provider]?.defaultModel || '');

    const savedBaseUrl = localStorage.getItem('slidecraft_custom_base_url');
    if (savedBaseUrl) setBaseUrl(savedBaseUrl);
  }, [provider]);

  if (!isOpen) return null;

  const handleProviderChange = (newProv) => {
    setProvider(newProv);
    setVerifyResult(null);
    const savedModel = localStorage.getItem(`slidecraft_model_${newProv}`);
    setSelectedModel(savedModel || PROVIDER_METADATA[newProv]?.defaultModel || '');
  };

  const handleVerifyKey = async () => {
    setIsVerifying(true);
    setVerifyResult(null);
    try {
      const res = await fetch('/api/verify-llm-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: inputKey.trim(),
          provider: provider,
          model: selectedModel,
          base_url: baseUrl.trim()
        })
      });
      const data = await res.json();
      setVerifyResult(data);
    } catch (err) {
      setVerifyResult({
        valid: false,
        message: `Network error verifying key: ${err.message}`
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSave = () => {
    const keyToSave = inputKey.trim();
    const effectiveProv = inferProviderFromKey(keyToSave, provider);
    localStorage.setItem('slidecraft_provider', effectiveProv);
    localStorage.setItem(`slidecraft_model_${effectiveProv}`, selectedModel);
    if (baseUrl.trim()) {
      localStorage.setItem('slidecraft_custom_base_url', baseUrl.trim());
    } else {
      localStorage.removeItem('slidecraft_custom_base_url');
    }
    onSaveApiKey(keyToSave, effectiveProv, selectedModel, baseUrl.trim());
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 700);
  };

  const handleUseAipptmakerKey = () => {
    setInputKey(DEFAULT_GROK_KEY);
    setProvider('grok');
    setVerifyResult(null);
  };

  const ActiveIcon = PROVIDER_METADATA[provider]?.icon || Key;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card"
        style={{ maxWidth: '580px', maxHeight: '90vh', overflowY: 'auto' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title-group">
            <Key size={20} className="text-accent" />
            <h3>AI Engine & LLM Provider Setup</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <p className="modal-desc">
          Connect your preferred Large Language Model to power autonomous presentation design, conversational slide refinement, and multi-domain outline generation.
        </p>

        {/* Provider Switcher Tabs */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
          gap: '6px',
          marginTop: '1.2rem'
        }}>
          {Object.entries(PROVIDER_METADATA).map(([key, meta]) => {
            const Icon = meta.icon;
            const isSelected = provider === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleProviderChange(key)}
                style={{
                  padding: '0.6rem 0.5rem',
                  borderRadius: '8px',
                  border: isSelected ? `1px solid ${meta.color}` : '1px solid rgba(255,255,255,0.08)',
                  background: isSelected ? 'rgba(99, 102, 241, 0.18)' : 'rgba(15, 23, 42, 0.6)',
                  color: isSelected ? '#fff' : '#94a3b8',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '4px',
                  fontWeight: isSelected ? 600 : 400,
                  fontSize: '0.78rem',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={16} color={isSelected ? meta.color : '#94a3b8'} />
                <span>{meta.name.split(' ')[0]}</span>
              </button>
            );
          })}
        </div>

        {/* API Key Input */}
        <div className="form-group" style={{ marginTop: '1.2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <label style={{ fontSize: '0.85rem', color: '#e2e8f0', fontWeight: 500 }}>
              {PROVIDER_METADATA[provider]?.name} API Key
            </label>
            <div style={{ display: 'flex', gap: '10px' }}>
              {provider === 'grok' && (
                <button
                  type="button"
                  onClick={handleUseAipptmakerKey}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#818cf8',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                >
                  Use default key
                </button>
              )}
              {PROVIDER_METADATA[provider]?.docsUrl && (
                <a
                  href={PROVIDER_METADATA[provider].docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#38bdf8',
                    fontSize: '0.75rem',
                    textDecoration: 'none'
                  }}
                >
                  Get Key ↗
                </a>
              )}
            </div>
          </div>
          <div style={{ position: 'relative' }}>
            <input
              type="password"
              placeholder={PROVIDER_METADATA[provider]?.placeholder || 'Enter API Key...'}
              value={inputKey}
              onChange={(e) => {
                const val = e.target.value;
                setInputKey(val);
                setVerifyResult(null);
                if (val.trim().length > 6) {
                  const inferred = inferProviderFromKey(val, provider);
                  if (inferred !== provider) {
                    setProvider(inferred);
                    const savedModel = localStorage.getItem(`slidecraft_model_${inferred}`);
                    setSelectedModel(savedModel || PROVIDER_METADATA[inferred]?.defaultModel || '');
                  }
                }
              }}
              style={{
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                border: '1px solid rgba(255,255,255,0.15)',
                background: 'rgba(15, 23, 42, 0.9)',
                color: '#fff',
                width: '100%',
                fontSize: '0.88rem',
                fontFamily: 'monospace'
              }}
            />
          </div>
        </div>

        {/* Model Selection */}
        <div className="form-group" style={{ marginTop: '0.8rem' }}>
          <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, display: 'block', marginBottom: '0.35rem' }}>
            Active AI Model
          </label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{
              padding: '0.65rem 0.9rem',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.15)',
              background: 'rgba(15, 23, 42, 0.9)',
              color: '#fff',
              width: '100%',
              fontSize: '0.85rem'
            }}
          >
            {PROVIDER_METADATA[provider]?.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* Custom Endpoint Base URL if custom provider */}
        {provider === 'custom' && (
          <div className="form-group" style={{ marginTop: '0.8rem' }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', fontWeight: 500, display: 'block', marginBottom: '0.35rem' }}>
              Base API URL (OpenAI-compatible)
            </label>
            <input
              type="text"
              placeholder="https://openrouter.ai/api/v1 or http://localhost:11434/v1"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              style={{
                padding: '0.65rem 0.9rem',
                borderRadius: '8px',
                border: '1px solid rgba(255,255,255,0.15)',
                background: 'rgba(15, 23, 42, 0.9)',
                color: '#fff',
                width: '100%',
                fontSize: '0.85rem'
              }}
            />
          </div>
        )}

        {/* Live Test Connection Section */}
        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={handleVerifyKey}
            disabled={isVerifying || !inputKey.trim()}
            style={{
              padding: '0.6rem 1rem',
              borderRadius: '8px',
              background: isVerifying ? 'rgba(99, 102, 241, 0.2)' : 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              color: '#818cf8',
              cursor: isVerifying || !inputKey.trim() ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.82rem',
              fontWeight: 600
            }}
          >
            {isVerifying ? (
              <>
                <Loader2 size={14} className="spin-animate" />
                <span>Testing Connection...</span>
              </>
            ) : (
              <>
                <ShieldCheck size={14} />
                <span>Test Connection</span>
              </>
            )}
          </button>
          <span style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Verify credentials before generating presentations
          </span>
        </div>

        {/* Verification Feedback Banner */}
        {verifyResult && (
          <div style={{
            marginTop: '0.8rem',
            padding: '0.75rem 0.9rem',
            borderRadius: '8px',
            background: verifyResult.valid ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: verifyResult.valid ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
            fontSize: '0.82rem',
            color: verifyResult.valid ? '#10b981' : '#f87171'
          }}>
            {verifyResult.valid ? (
              <CheckCircle2 size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            ) : (
              <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            )}
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>
                {verifyResult.valid
                  ? `Connected in ${verifyResult.latency_ms}ms`
                  : 'Authentication Notice'}
              </div>
              <div style={{ fontSize: '0.78rem', marginTop: '2px', opacity: 0.95 }}>
                {verifyResult.message}
              </div>
            </div>
          </div>
        )}

        {/* Resilient Fallback Notice */}
        <div style={{
          marginTop: '1.2rem',
          padding: '0.8rem',
          borderRadius: '8px',
          background: 'rgba(99, 102, 241, 0.06)',
          border: '1px solid rgba(99, 102, 241, 0.18)',
          fontSize: '0.8rem',
          color: '#94a3b8',
          lineHeight: '1.4'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#818cf8', fontWeight: 600, marginBottom: '3px' }}>
            <ShieldCheck size={15} />
            <span>Resilient Multi-Tier Pipeline</span>
          </div>
          SlideCraft automatically connects to your selected LLM. In case of API rate limits or network issues, our procedural neural engine synthesizes high-fidelity slides with zero downtime.
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '1.5rem' }}>
          <button
            onClick={onClose}
            style={{
              padding: '0.6rem 1.2rem',
              borderRadius: '8px',
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.1)',
              color: '#94a3b8',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="btn-primary"
            style={{
              width: 'auto',
              margin: 0,
              padding: '0.6rem 1.4rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            {saved ? (
              <>
                <Check size={16} />
                <span>Saved!</span>
              </>
            ) : (
              <span>Save & Apply</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
