import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import TemplateDesignGenerator from './components/TemplateDesignGenerator';
import ChatWorkspace from './components/ChatWorkspace';
import PresentationModal from './components/PresentationModal';
import NewDeckModal from './components/NewDeckModal';
import ThemeModal from './components/ThemeModal';
import SettingsModal from './components/SettingsModal';
import ImageGenModal from './components/ImageGenModal';
import './App.css';

const LEGACY_DEMO_GROK_KEY = 'grok_46580b20988b83a360d82699b8e2cf39_a6b20bd9ec170814e3a38176c18d669f51f80a893d345a2cf0fbeeda1798e256';

export default function App() {
  const [currentView, setCurrentView] = useState('studio'); // 'studio' | 'generator'
  const [viewMode, setViewMode] = useState('split'); // 'split' | 'canvas' | 'chat'
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeDeck, setActiveDeck] = useState(null);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [activeThemeId, setActiveThemeId] = useState('google-gemini');
  const [downloadUrl, setDownloadUrl] = useState(null);

  // Conversational chat state
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  // User Decks History (persisted in localStorage)
  const [recentProjects, setRecentProjects] = useState(() => {
    try {
      const saved = localStorage.getItem('slidecraft_user_decks_v1');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {
      console.warn('Error reading recent projects:', e);
    }
    return [];
  });

  const saveRecentProjects = (projects) => {
    setRecentProjects(projects);
    try {
      localStorage.setItem('slidecraft_user_decks_v1', JSON.stringify(projects));
    } catch (e) {
      console.warn('Error saving recent projects:', e);
    }
  };

  // Modals state
  const [isPresentationOpen, setIsPresentationOpen] = useState(false);
  const [presentationSlideIndex, setPresentationSlideIndex] = useState(0);
  const [isThemeModalOpen, setIsThemeModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isNewDeckModalOpen, setIsNewDeckModalOpen] = useState(false);
  const [isImageModalOpen, setIsImageModalOpen] = useState(false);
  const [imageModalSlide, setImageModalSlide] = useState(null);

  // API Key & OpenAI/LLM Provider state
  const [apiKey, setApiKey] = useState(() => {
    const raw =
      localStorage.getItem('slidecraft_api_key') ||
      localStorage.getItem('openai_api_key') ||
      localStorage.getItem('gemini_api_key') ||
      localStorage.getItem('grok_api_key') ||
      '';
    return raw === LEGACY_DEMO_GROK_KEY ? '' : raw;
  });

  const [aiProvider, setAiProvider] = useState(() => {
    const saved = localStorage.getItem('slidecraft_provider');
    if (saved) return saved;
    const raw = localStorage.getItem('slidecraft_api_key') || '';
    if (raw.startsWith('AIza')) return 'gemini';
    if (raw.startsWith('sk-ant-')) return 'claude';
    if (raw.startsWith('sk-or-')) return 'custom';
    if ((raw.startsWith('grok_') || raw.startsWith('xai-')) && raw !== LEGACY_DEMO_GROK_KEY) return 'grok';
    return 'openai';
  });

  const [aiModel, setAiModel] = useState(() => {
    const prov = localStorage.getItem('slidecraft_provider') || 'openai';
    return localStorage.getItem(`slidecraft_model_${prov}`) || (prov === 'openai' ? 'gpt-4o-mini' : '');
  });

  const [aiBaseUrl, setAiBaseUrl] = useState(() => {
    return localStorage.getItem('slidecraft_custom_base_url') || '';
  });

  const [serverHasOpenAiKey, setServerHasOpenAiKey] = useState(false);

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.has_openai_key) {
          setServerHasOpenAiKey(true);
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveApiKey = (key, provider = 'openai', model = 'gpt-4o-mini', baseUrl = '') => {
    const cleanKey = (key || '').trim();
    setApiKey(cleanKey);
    setAiProvider(provider || 'openai');
    setAiModel(model || 'gpt-4o-mini');
    setAiBaseUrl(baseUrl || '');

    localStorage.setItem('slidecraft_api_key', cleanKey);
    localStorage.setItem('slidecraft_provider', provider || 'openai');
    if (model) {
      localStorage.setItem(`slidecraft_model_${provider || 'openai'}`, model);
    }
    if (cleanKey.startsWith('sk-') && !cleanKey.startsWith('sk-ant-') && !cleanKey.startsWith('sk-or-')) {
      localStorage.setItem('openai_api_key', cleanKey);
    } else if (cleanKey.startsWith('grok_') || cleanKey.startsWith('xai-')) {
      localStorage.setItem('grok_api_key', cleanKey);
    } else if (cleanKey.startsWith('AIza')) {
      localStorage.setItem('gemini_api_key', cleanKey);
    }
  };

  // Sync export with backend to keep PPTX updated when slide content changes
  const syncExport = async (deckToExport) => {
    if (!deckToExport) return;
    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deck: deckToExport,
          theme_id: deckToExport.theme_id || activeThemeId,
          template_id: deckToExport.template_id || ''
        })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.download_url) {
          setDownloadUrl(data.download_url);
        }
      }
    } catch (err) {
      console.warn('Sync export error:', err);
    }
  };

  // Upsert deck into user history
  const upsertRecentProject = (deck, fileId, dlUrl) => {
    if (!deck) return;
    const existingIdx = recentProjects.findIndex(p => p.title === deck.title);
    const updated = [...recentProjects];
    const projectItem = {
      id: `deck-${Date.now()}`,
      title: deck.title,
      dimensions: '16:9 • 1920x1080',
      timeAgo: 'Just now',
      badge: (deck.theme_id || activeThemeId).toUpperCase().replace('-', ' '),
      deck: deck,
      file_id: fileId || (existingIdx >= 0 ? updated[existingIdx].file_id : null),
      download_url: dlUrl || (fileId ? `/api/download/${fileId}` : null)
    };

    if (existingIdx >= 0) {
      updated[existingIdx] = {
        ...updated[existingIdx],
        ...projectItem,
        timeAgo: 'Updated just now'
      };
    } else {
      updated.unshift(projectItem);
    }
    saveRecentProjects(updated);
  };

  // Handle deck generation from TemplateDesignGenerator
  const handlePresentationGenerated = (deck, fileId, dlUrl) => {
    setActiveDeck(deck);
    if (deck.theme_id) {
      setActiveThemeId(deck.theme_id);
    }
    setDownloadUrl(dlUrl || (fileId ? `/api/download/${fileId}` : null));
    setActiveSlideIndex(0);
    upsertRecentProject(deck, fileId, dlUrl);
    setCurrentView('studio');
  };

  // Select project from history
  const handleSelectProject = (project) => {
    setActiveDeck(project.deck);
    setActiveThemeId(project.deck.theme_id || 'google-gemini');
    setActiveSlideIndex(0);
    if (project.file_id) {
      setDownloadUrl(`/api/download/${project.file_id}`);
    } else if (project.download_url) {
      setDownloadUrl(project.download_url);
    } else {
      syncExport(project.deck);
    }
    setCurrentView('studio');
  };

  const handleDeleteProject = (projId) => {
    const updated = recentProjects.filter(p => (p.id || p.title) !== projId);
    saveRecentProjects(updated);
  };

  // Start with clean blank presentation
  const handleStartBlank = () => {
    const blankDeck = {
      title: 'Executive Presentation',
      subtitle: 'Strategic Overview & Key Initiatives',
      theme_id: activeThemeId,
      template_id: '',
      slides: [
        {
          id: `slide-${Date.now()}-1`,
          type: 'title',
          category: 'EXECUTIVE OVERVIEW',
          title: 'Executive Keynote Presentation',
          subtitle: 'Click any text or use the controls to customize this deck',
          bullets: [],
          notes: 'Opening remarks and welcome.'
        },
        {
          id: `slide-${Date.now()}-2`,
          type: 'bullets',
          category: 'CORE PILLARS',
          title: 'Strategic Priorities & Objectives',
          subtitle: 'Foundational imperatives for modern growth and scaling',
          bullets: [
            'Operational Velocity: Accelerating delivery cycles and eliminating friction',
            'Architecture Modernization: Upgrading infrastructure to distributed cloud',
            'Data-Driven Decision Making: Real-time telemetry across all systems'
          ],
          notes: 'Highlight three foundational pillars.'
        },
        {
          id: `slide-${Date.now()}-3`,
          type: 'metrics',
          category: 'MEASURED IMPACT',
          title: 'Key Performance Indicators',
          subtitle: 'Verified quarterly metrics and operational performance',
          stats: [
            { value: '99.4%', label: 'Platform Availability', change: '+18% YoY' },
            { value: '3.8x', label: 'Processing Velocity', change: 'Top Decile' },
            { value: '< 45ms', label: 'Average Latency', change: 'Optimized' }
          ],
          notes: 'Review the KPI performance numbers.'
        }
      ]
    };

    setActiveDeck(blankDeck);
    setActiveSlideIndex(0);
    upsertRecentProject(blankDeck);
    syncExport(blankDeck);
    setCurrentView('studio');
  };

  // Conversational AI messaging (OpenAI / Gemini / Claude / Grok)
  const handleSendMessage = async ({ prompt, attachments, slideCount, imageStyle }) => {
    setCurrentView('studio');
    const userMsg = {
      role: 'user',
      content: prompt,
      attachments: attachments || []
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const historyItems = messages.map(m => ({
        role: m.role,
        content: m.content,
        attachments: m.attachments || []
      }));

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt,
          history: historyItems,
          attachments: attachments || [],
          theme_id: activeThemeId,
          template_id: activeDeck?.template_id || '',
          slide_count: slideCount || 6,
          api_key: apiKey,
          provider: aiProvider,
          model: aiModel,
          base_url: aiBaseUrl,
          current_deck: activeDeck,
          auto_generate_images: true,
          image_style: imageStyle || '3d',
          preferred_image_provider: 'diffusion'
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to update presentation');
      }

      const data = await res.json();

      if (data.deck) {
        setActiveDeck(data.deck);
        upsertRecentProject(data.deck, data.file_id, data.download_url);
        if (data.modified_slide_index !== undefined && data.modified_slide_index !== null) {
          setActiveSlideIndex(data.modified_slide_index);
        }
      }
      if (data.theme_id && data.theme_id !== activeThemeId) {
        setActiveThemeId(data.theme_id);
      }
      if (data.download_url) {
        setDownloadUrl(data.download_url);
      }

      const assistantMsg = {
        role: 'assistant',
        content: data.message || data.response_message || `Updated presentation "${data.deck?.title || 'Keynote'}".`
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Note: ${err.message}. SlideCraft is operating in resilient fallback mode.`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Slide Modification Handlers
  const handleUpdateSlide = (updatedSlide) => {
    if (!activeDeck) return;
    const newSlides = [...activeDeck.slides];
    newSlides[activeSlideIndex] = updatedSlide;
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
  };

  const handleAddSlide = (slideType = 'bullets') => {
    if (!activeDeck) return;
    const newSlideId = `slide-${Date.now().toString(36)}`;
    let newSlide = {
      id: newSlideId,
      type: slideType,
      category: 'NEW SECTION',
      title: 'Untitled Slide',
      subtitle: 'Click here or use the editor to add content',
      bullets: ['Key takeaway or observation', 'Supporting analysis point'],
      left: [],
      right: [],
      stats: [],
      quote: '',
      notes: 'Presenter speaking notes for this slide.'
    };

    if (slideType === 'metrics') {
      newSlide.stats = [
        { value: '98%', label: 'Efficiency Gain', change: '+14%' },
        { value: '3.5x', label: 'Velocity Multiplier', change: 'Top Decile' }
      ];
    } else if (slideType === 'two_column') {
      newSlide.left = ['• Traditional constraints and overhead', '• Manual synchronization lag'];
      newSlide.right = ['• Automated distributed intelligence', '• Sub-second real-time delivery'];
    } else if (slideType === 'table') {
      newSlide.table = {
        headers: ['Dimension', 'Baseline', 'Target', 'Impact'],
        rows: [
          ['Performance', '92%', '99.5%', 'High'],
          ['Cost Efficiency', 'Standard', '-35%', 'Optimal']
        ]
      };
    } else if (slideType === 'timeline') {
      newSlide.bullets = [
        'Phase 1 — Architecture & Design: Requirements, blueprints and protocol',
        'Phase 2 — Global Deployment: Zero-downtime container rollout'
      ];
      newSlide.timeline = [
        { phase: 'Phase 1', title: 'Architecture & Design', desc: 'Requirements, blueprints and protocol' },
        { phase: 'Phase 2', title: 'Global Deployment', desc: 'Zero-downtime container rollout' }
      ];
    } else if (slideType === 'diagram') {
      newSlide.category = 'SYSTEM ARCHITECTURE BLUEPRINT';
      newSlide.title = `${activeDeck.title || 'System'}: Architecture & Dataflow Topology`;
      newSlide.subtitle = 'Multi-tier component interactions, orchestration, and persistence layers';
      newSlide.bullets = [
        'End-to-end layered architecture decoupling client ingress, policy routing, core engine, and storage.',
        'High-availability event-driven dataflow with real-time telemetry and fault isolation.'
      ];
      newSlide.visual = {
        kind: 'architecture',
        diagram: {
          direction: 'LR',
          clusters: [
            { id: 'c1', label: '1. Ingress & Interface' },
            { id: 'c2', label: '2. Orchestration & Routing' },
            { id: 'c3', label: '3. Core Intelligence Engine' },
            { id: 'c4', label: '4. Data & Telemetry Layer' }
          ],
          nodes: [
            { id: 'n1', label: 'Client & Edge Portal', shape: 'user', cluster: 'c1' },
            { id: 'n2', label: 'API & Policy Gateway', shape: 'decision', cluster: 'c2' },
            { id: 'n3', label: `${(activeDeck.title || 'Core').slice(0, 18)} Engine`, shape: 'cloud', cluster: 'c3' },
            { id: 'n4', label: 'Async Workflow Bus', shape: 'queue', cluster: 'c3' },
            { id: 'n5', label: 'Vector & State Store', shape: 'database', cluster: 'c4' }
          ],
          edges: [
            { source: 'n1', target: 'n2', label: 'Request / Auth' },
            { source: 'n2', target: 'n3', label: 'Orchestrate' },
            { source: 'n3', target: 'n4', label: 'Event Stream' },
            { source: 'n4', target: 'n5', label: 'Persist & Index' }
          ]
        }
      };
    }

    const newSlides = [...activeDeck.slides, newSlide];
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    setActiveSlideIndex(newSlides.length - 1);
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
  };

  const handleDeleteSlide = (idxToDelete) => {
    if (!activeDeck || activeDeck.slides.length <= 1) return;
    const newSlides = activeDeck.slides.filter((_, i) => i !== idxToDelete);
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    if (activeSlideIndex >= newSlides.length) {
      setActiveSlideIndex(newSlides.length - 1);
    }
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
  };

  const handleDuplicateSlide = (idxToDup) => {
    if (!activeDeck) return;
    const orig = activeDeck.slides[idxToDup];
    const dup = {
      ...orig,
      id: `slide-${Date.now().toString(36)}`,
      title: `${orig.title} (Copy)`
    };
    const newSlides = [...activeDeck.slides];
    newSlides.splice(idxToDup + 1, 0, dup);
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    setActiveSlideIndex(idxToDup + 1);
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
  };

  const handleMoveSlide = (fromIndex, deltaOrTarget) => {
    if (!activeDeck) return;
    const toIndex = (deltaOrTarget === -1 || deltaOrTarget === 1)
      ? fromIndex + deltaOrTarget
      : deltaOrTarget;
    if (toIndex < 0 || toIndex >= activeDeck.slides.length) return;
    const newSlides = [...activeDeck.slides];
    const [moved] = newSlides.splice(fromIndex, 1);
    newSlides.splice(toIndex, 0, moved);
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    setActiveSlideIndex(toIndex);
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
  };

  const handleQuickAiPolish = (styleOption) => {
    if (!activeDeck || !activeDeck.slides[activeSlideIndex]) return;
    if (typeof styleOption === 'string' && styleOption.length > 20) {
      handleSendMessage({ prompt: styleOption });
      return;
    }
    const currentSlide = activeDeck.slides[activeSlideIndex];
    let polished = { ...currentSlide };
    if (styleOption === 'executive') {
      polished.title = `Executive Overview: ${currentSlide.title}`;
      polished.subtitle = `Strategic imperatives, leadership priorities, and quantifiable objectives`;
      polished.category = 'EXECUTIVE BRIEF';
    } else if (styleOption === 'concise') {
      polished.bullets = (polished.bullets || []).map(b => b.split(':')[0] || b).slice(0, 3);
    } else if (styleOption === 'data') {
      polished.type = 'metrics';
      polished.stats = [
        { value: '99.4%', label: 'Operational Accuracy', change: '+18% YoY' },
        { value: '4.2x', label: 'Throughput Multiplier', change: 'Top Decile' },
        { value: '< 30ms', label: 'Response Latency', change: 'Optimized' }
      ];
    }
    handleUpdateSlide(polished);
  };

  const handleExportJson = () => {
    if (!activeDeck) return;
    const jsonStr = JSON.stringify(activeDeck, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(activeDeck.title || 'presentation').toLowerCase().replace(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportJson = (importedDeck) => {
    if (!importedDeck || !importedDeck.slides) return;
    setActiveDeck(importedDeck);
    if (importedDeck.theme_id) setActiveThemeId(importedDeck.theme_id);
    setActiveSlideIndex(0);
    setCurrentView('studio');
    upsertRecentProject(importedDeck);
    syncExport(importedDeck);
  };

  const handlePrintPdf = () => {
    window.print();
  };

  const handleOpenImageModal = (slide) => {
    setImageModalSlide(slide);
    setIsImageModalOpen(true);
  };

  const handleImageApplied = (imagePayload, captionParam) => {
    if (!activeDeck || !imageModalSlide) return;
    const url = typeof imagePayload === 'object' && imagePayload !== null 
      ? (imagePayload.imageUrl || imagePayload.url || '') 
      : (imagePayload || '');
    const caption = typeof imagePayload === 'object' && imagePayload !== null
      ? (imagePayload.caption || captionParam || '')
      : (captionParam || '');

    const newSlides = activeDeck.slides.map(s => {
      if (s.id === imageModalSlide.id) {
        return { 
          ...s, 
          image_url: url, 
          image_caption: caption || s.image_caption,
          type: s.type === 'title' ? 'title' : 'image_text'
        };
      }
      return s;
    });
    const updatedDeck = { ...activeDeck, slides: newSlides };
    setActiveDeck(updatedDeck);
    upsertRecentProject(updatedDeck);
    syncExport(updatedDeck);
    setIsImageModalOpen(false);
  };

  const handleStartNewDeck = () => {
    setActiveDeck(null);
    setActiveSlideIndex(0);
    setCurrentView('studio');
  };

  const handleOpenPresentation = (slideIdx = 0) => {
    setPresentationSlideIndex(slideIdx);
    setIsPresentationOpen(true);
  };

  return (
    <>
      {currentView === 'generator' ? (
        <TemplateDesignGenerator
          apiKey={apiKey}
          aiProvider={aiProvider}
          aiModel={aiModel}
          aiBaseUrl={aiBaseUrl}
          onOpenStudio={() => setCurrentView('studio')}
          onOpenThemes={() => setIsThemeModalOpen(true)}
          onOpenSettings={() => setIsSettingsModalOpen(true)}
          onStartBlank={handleStartBlank}
          onSelectProject={handleSelectProject}
          onDeleteProject={handleDeleteProject}
          recentProjects={recentProjects}
          onPresentationGenerated={handlePresentationGenerated}
          activeThemeId={activeThemeId}
          onSelectTheme={(id) => {
            setActiveThemeId(id);
            if (activeDeck) {
              const updated = { ...activeDeck, theme_id: id };
              setActiveDeck(updated);
              upsertRecentProject(updated);
              syncExport(updated);
            }
          }}
        />
      ) : (
        <div className="app-layout studio-active">
          <Navbar
            activeDeck={activeDeck}
            activeThemeId={activeThemeId}
            downloadUrl={downloadUrl}
            activeSlideIndex={activeSlideIndex}
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
            viewMode={viewMode}
            onChangeViewMode={setViewMode}
            onStartNewDeck={handleStartNewDeck}
            onOpenThemes={() => setIsThemeModalOpen(true)}
            onOpenSettings={() => setIsSettingsModalOpen(true)}
            onOpenPresentation={handleOpenPresentation}
            onOpenNewDeckModal={() => setIsNewDeckModalOpen(true)}
            onOpenTemplates={() => setCurrentView('generator')}
            onExportJson={handleExportJson}
            onPrintPdf={handlePrintPdf}
          />

          <main className="main-content">
            <ChatWorkspace
              messages={messages}
              isLoading={isLoading}
              onSendMessage={handleSendMessage}
              activeDeck={activeDeck}
              activeThemeId={activeThemeId}
              downloadUrl={downloadUrl}
              isSidebarOpen={isSidebarOpen}
              onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
              viewMode={viewMode}
              onChangeViewMode={setViewMode}
              recentProjects={recentProjects}
              onSelectProject={handleSelectProject}
              onDeleteProject={handleDeleteProject}
              onOpenThemes={() => setIsThemeModalOpen(true)}
              onOpenSettings={() => setIsSettingsModalOpen(true)}
              onOpenPresentation={handleOpenPresentation}
              apiKey={apiKey}
              aiProvider={aiProvider}
              aiModel={aiModel}
              serverHasOpenAiKey={serverHasOpenAiKey}
              activeSlideIndex={activeSlideIndex}
              setActiveSlideIndex={setActiveSlideIndex}
              onUpdateSlide={handleUpdateSlide}
              onAddSlide={handleAddSlide}
              onDeleteSlide={handleDeleteSlide}
              onDuplicateSlide={handleDuplicateSlide}
              onMoveSlide={handleMoveSlide}
              onOpenImageModal={handleOpenImageModal}
              onQuickAiPolish={handleQuickAiPolish}
              onStartBlank={handleStartBlank}
              onOpenNewDeckModal={() => setIsNewDeckModalOpen(true)}
              onOpenTemplates={() => setCurrentView('generator')}
              onImportJson={handleImportJson}
            />
          </main>
        </div>
      )}

      {/* Fullscreen Keynote Presentation Modal */}
      <PresentationModal
        deck={activeDeck}
        themeId={activeThemeId}
        downloadUrl={downloadUrl}
        isOpen={isPresentationOpen}
        onClose={() => setIsPresentationOpen(false)}
        initialSlideIndex={presentationSlideIndex}
      />

      {/* New Deck Modal */}
      <NewDeckModal
        isOpen={isNewDeckModalOpen}
        onClose={() => setIsNewDeckModalOpen(false)}
        onGenerateFromPrompt={handleSendMessage}
        onStartBlank={handleStartBlank}
        onImportJson={handleImportJson}
      />

      {/* AI Image Generation Modal */}
      <ImageGenModal
        isOpen={isImageModalOpen}
        onClose={() => setIsImageModalOpen(false)}
        slide={imageModalSlide}
        deckTitle={activeDeck?.title}
        apiKey={apiKey}
        onImageApplied={handleImageApplied}
      />

      {/* Themes Modal */}
      <ThemeModal
        isOpen={isThemeModalOpen}
        onClose={() => setIsThemeModalOpen(false)}
        activeThemeId={activeThemeId}
        onSelectTheme={(id) => {
          setActiveThemeId(id);
          if (activeDeck) {
            const updated = { ...activeDeck, theme_id: id };
            setActiveDeck(updated);
            upsertRecentProject(updated);
            syncExport(updated);
          }
        }}
      />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        apiKey={apiKey}
        initialProvider={aiProvider}
        initialModel={aiModel}
        onSaveApiKey={handleSaveApiKey}
      />
    </>
  );
}
