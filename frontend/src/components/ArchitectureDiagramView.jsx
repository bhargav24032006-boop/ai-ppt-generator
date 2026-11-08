import React, { useState } from 'react';
import {
  Cpu, Database, Cloud, User, GitBranch, Layers, ArrowRight, Plus, Trash2, Image as ImageIcon, Network, Columns
} from 'lucide-react';

const SHAPE_CONFIG = {
  user: { label: 'CLIENT / INPUT', color: '#10b981', bg: 'rgba(16, 185, 129, 0.14)', Icon: User },
  cloud: { label: 'CLOUD / AI ENGINE', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)', Icon: Cloud },
  database: { label: 'DATA STORE / DB', color: '#22d3ee', bg: 'rgba(34, 211, 238, 0.14)', Icon: Database },
  decision: { label: 'ROUTER / GATEWAY', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.14)', Icon: GitBranch },
  queue: { label: 'EVENT STREAM / BUS', color: '#f472b6', bg: 'rgba(244, 114, 182, 0.14)', Icon: Layers },
  process: { label: 'CORE SERVICE', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.14)', Icon: Cpu },
  box: { label: 'COMPONENT', color: '#60a5fa', bg: 'rgba(96, 165, 250, 0.14)', Icon: Cpu },
};

export function buildDefaultDiagramFromSlide(slide) {
  const existing = slide?.visual?.diagram;
  if (existing && Array.isArray(existing.nodes) && existing.nodes.length >= 2) {
    return existing;
  }
  const title = slide?.title || 'System Architecture';
  const bullets = slide?.bullets || [];
  const extractedLabels = bullets.slice(0, 4).map((b, i) => {
    const clean = String(b).replace(/^[•▸\-*\d.]+\s*/, '');
    if (clean.includes(':')) return clean.split(':')[0].trim().slice(0, 26);
    return clean.slice(0, 26) || `Component ${i + 1}`;
  });

  const clusters = [
    { id: 'c1', label: '1. Ingress & Interface' },
    { id: 'c2', label: '2. Orchestration & Routing' },
    { id: 'c3', label: '3. Core Intelligence Engine' },
    { id: 'c4', label: '4. Data & Telemetry Layer' },
  ];
  const nodes = [
    { id: 'n1', label: extractedLabels[0] || 'Client & Edge Portal', shape: 'user', cluster: 'c1' },
    { id: 'n2', label: extractedLabels[1] || 'API & Policy Gateway', shape: 'decision', cluster: 'c2' },
    { id: 'n3', label: extractedLabels[2] || `${title.slice(0, 18)} Engine`, shape: 'cloud', cluster: 'c3' },
    { id: 'n4', label: 'Async Workflow Bus', shape: 'queue', cluster: 'c3' },
    { id: 'n5', label: extractedLabels[3] || 'Vector & State Store', shape: 'database', cluster: 'c4' },
  ];
  const edges = [
    { source: 'n1', target: 'n2', label: 'Request / Auth' },
    { source: 'n2', target: 'n3', label: 'Orchestrate' },
    { source: 'n3', target: 'n4', label: 'Event Stream' },
    { source: 'n4', target: 'n5', label: 'Persist & Index' },
  ];
  return { direction: 'LR', clusters, nodes, edges };
}

export default function ArchitectureDiagramView({
  slide,
  theme,
  editable = false,
  onChangeDiagram,
  onChangeBullets,
}) {
  const [displayMode, setDisplayMode] = useState('interactive'); // 'interactive' | 'blueprint_png' | 'split'
  const diagram = buildDefaultDiagramFromSlide(slide);
  const clusters = diagram.clusters || [];
  const nodes = diagram.nodes || [];
  const edges = diagram.edges || [];
  const bullets = slide?.bullets || [];
  const blueprintImageUrl = slide?.image_url || '';

  // Group nodes by cluster (or into 3-4 balanced tiers)
  const groupedColumns = [];
  if (clusters.length > 0) {
    const usedIds = new Set();
    clusters.forEach((cl) => {
      const cNodes = nodes.filter((n) => n.cluster === cl.id);
      if (cNodes.length > 0) {
        groupedColumns.push({ id: cl.id, label: cl.label, nodes: cNodes });
        cNodes.forEach((n) => usedIds.add(n.id));
      }
    });
    const leftover = nodes.filter((n) => !usedIds.has(n.id));
    if (leftover.length > 0) {
      if (groupedColumns.length > 0) {
        groupedColumns[groupedColumns.length - 1].nodes.push(...leftover);
      } else {
        groupedColumns.push({ id: 'core', label: 'Core Architecture', nodes: leftover });
      }
    }
  }
  if (groupedColumns.length === 0) {
    const chunkSize = Math.max(1, Math.ceil(nodes.length / 4));
    for (let i = 0; i < nodes.length; i += chunkSize) {
      groupedColumns.push({
        id: `tier_${i}`,
        label: `Tier ${groupedColumns.length + 1}`,
        nodes: nodes.slice(i, i + chunkSize),
      });
    }
  }

  const handleNodeLabelEdit = (nodeId, newLabel) => {
    if (!onChangeDiagram) return;
    const updatedNodes = nodes.map((n) => (n.id === nodeId ? { ...n, label: newLabel } : n));
    onChangeDiagram({ ...diagram, nodes: updatedNodes });
  };

  const handleNodeShapeEdit = (nodeId, newShape) => {
    if (!onChangeDiagram) return;
    const updatedNodes = nodes.map((n) => (n.id === nodeId ? { ...n, shape: newShape } : n));
    onChangeDiagram({ ...diagram, nodes: updatedNodes });
  };

  const handleAddNode = () => {
    if (!onChangeDiagram) return;
    const targetCluster = clusters[clusters.length - 1]?.id || 'c4';
    const newId = `n${nodes.length + 1}_${Date.now().toString().slice(-3)}`;
    const prevNode = nodes[nodes.length - 1];
    const updatedNodes = [
      ...nodes,
      { id: newId, label: 'New Service Node', shape: 'process', cluster: targetCluster },
    ];
    const updatedEdges = prevNode
      ? [...edges, { source: prevNode.id, target: newId, label: 'Data Flow' }]
      : edges;
    onChangeDiagram({ ...diagram, nodes: updatedNodes, edges: updatedEdges });
  };

  const handleRemoveNode = (nodeId) => {
    if (!onChangeDiagram || nodes.length <= 2) return;
    const updatedNodes = nodes.filter((n) => n.id !== nodeId);
    const updatedEdges = edges.filter((e) => e.source !== nodeId && e.target !== nodeId);
    onChangeDiagram({ ...diagram, nodes: updatedNodes, edges: updatedEdges });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', height: '100%', width: '100%' }}>
      {/* Optional View Mode Toggle when Drawn Blueprint PNG is available */}
      {blueprintImageUrl && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <span style={{ fontSize: '0.68rem', color: theme?.textSecondary || '#94a3b8', fontWeight: 600 }}>
            ARCHITECTURE RENDER MODE ({nodes.length} Components • {edges.length} Flows)
          </span>
          <div style={{ display: 'inline-flex', gap: '4px', background: 'rgba(15,23,42,0.75)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(148,163,184,0.18)' }}>
            <button
              type="button"
              onClick={() => setDisplayMode('interactive')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.66rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: displayMode === 'interactive' ? (theme?.accentPrimary || '#6366f1') : 'transparent',
                color: displayMode === 'interactive' ? '#fff' : '#94a3b8',
              }}
            >
              <Network size={11} /> Interactive Topology
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode('blueprint_png')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.66rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: displayMode === 'blueprint_png' ? (theme?.accentSecondary || '#06b6d4') : 'transparent',
                color: displayMode === 'blueprint_png' ? '#0f172a' : '#94a3b8',
              }}
            >
              <ImageIcon size={11} /> Drawn Blueprint PNG
            </button>
            <button
              type="button"
              onClick={() => setDisplayMode('split')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.66rem',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer',
                background: displayMode === 'split' ? 'rgba(129,140,248,0.28)' : 'transparent',
                color: displayMode === 'split' ? '#e2e8f0' : '#94a3b8',
              }}
            >
              <Columns size={11} /> Split View
            </button>
          </div>
        </div>
      )}

      {/* Main Diagram Area */}
      {displayMode === 'blueprint_png' && blueprintImageUrl ? (
        <div
          style={{
            flex: 1,
            minHeight: '220px',
            borderRadius: '14px',
            overflow: 'hidden',
            border: `1.5px solid ${theme?.accentSecondary || '#06b6d4'}55`,
            background: '#0b0f19',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <img
            src={blueprintImageUrl}
            alt="Drawn System Architecture Blueprint"
            style={{ width: '100%', height: '100%', maxHeight: '320px', objectFit: 'contain' }}
          />
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: displayMode === 'split' && blueprintImageUrl ? '1.35fr 1fr' : '1fr',
            gap: '12px',
            flex: 1,
            minHeight: '220px',
          }}
        >
          {/* Multi-Tier Interactive Architecture Blueprint Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${groupedColumns.length}, minmax(0, 1fr))`,
              gap: '12px',
              alignItems: 'stretch',
            }}
          >
            {groupedColumns.map((col, colIdx) => (
              <div
                key={col.id || colIdx}
                style={{
                  position: 'relative',
                  background: theme?.cardBg || 'rgba(15, 23, 42, 0.78)',
                  border: `1.5px solid ${colIdx % 2 === 0 ? (theme?.accentPrimary || '#6366f1') : (theme?.accentSecondary || '#06b6d4')}55`,
                  borderRadius: '14px',
                  padding: '10px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                {/* Tier / Cluster Header */}
                <div
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 800,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: colIdx % 2 === 0 ? (theme?.accentPrimary || '#818cf8') : (theme?.accentSecondary || '#22d3ee'),
                    background: 'rgba(255,255,255,0.04)',
                    padding: '6px 8px',
                    borderRadius: '8px',
                    textAlign: 'center',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {col.label}
                </div>

                {/* Nodes inside this tier */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', justifyContent: 'center', flex: 1 }}>
                  {col.nodes.map((node) => {
                    const cfg = SHAPE_CONFIG[node.shape] || SHAPE_CONFIG.process;
                    const IconComp = cfg.Icon;
                    const outEdge = edges.find((e) => e.source === node.id);

                    return (
                      <div
                        key={node.id}
                        style={{
                          background: 'rgba(11, 15, 25, 0.82)',
                          border: `1.5px solid ${cfg.color}`,
                          borderRadius: node.shape === 'database' ? '14px 14px 18px 18px' : '12px',
                          padding: '9px 11px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '5px',
                          position: 'relative',
                          boxShadow: `0 4px 16px ${cfg.bg}`,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px' }}>
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '5px',
                              fontSize: '0.6rem',
                              fontWeight: 700,
                              color: cfg.color,
                              background: cfg.bg,
                              padding: '2px 6px',
                              borderRadius: '6px',
                            }}
                          >
                            <IconComp size={11} />
                            {editable ? (
                              <select
                                value={node.shape || 'process'}
                                onChange={(e) => handleNodeShapeEdit(node.id, e.target.value)}
                                style={{
                                  background: 'transparent',
                                  color: cfg.color,
                                  border: 'none',
                                  fontSize: '0.6rem',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  outline: 'none',
                                }}
                              >
                                <option value="user" style={{ background: '#0f172a' }}>CLIENT / INPUT</option>
                                <option value="decision" style={{ background: '#0f172a' }}>ROUTER / GATEWAY</option>
                                <option value="cloud" style={{ background: '#0f172a' }}>CLOUD / AI</option>
                                <option value="process" style={{ background: '#0f172a' }}>CORE SERVICE</option>
                                <option value="queue" style={{ background: '#0f172a' }}>STREAM / BUS</option>
                                <option value="database" style={{ background: '#0f172a' }}>DATA STORE / DB</option>
                              </select>
                            ) : (
                              cfg.label
                            )}
                          </span>

                          {editable && nodes.length > 2 && (
                            <button
                              type="button"
                              onClick={() => handleRemoveNode(node.id)}
                              title="Remove Component"
                              style={{
                                background: 'transparent',
                                border: 'none',
                                color: '#94a3b8',
                                cursor: 'pointer',
                                padding: '2px',
                                lineHeight: 1,
                              }}
                            >
                              <Trash2 size={11} />
                            </button>
                          )}
                        </div>

                        {editable ? (
                          <input
                            type="text"
                            value={node.label}
                            onChange={(e) => handleNodeLabelEdit(node.id, e.target.value)}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              borderBottom: '1px dashed rgba(148,163,184,0.25)',
                              color: theme?.textPrimary || '#f8fafc',
                              fontSize: '0.82rem',
                              fontWeight: 700,
                              width: '100%',
                              outline: 'none',
                              padding: '2px 0',
                            }}
                          />
                        ) : (
                          <div
                            style={{
                              fontSize: '0.82rem',
                              fontWeight: 700,
                              color: theme?.textPrimary || '#f8fafc',
                              lineHeight: 1.25,
                            }}
                          >
                            {node.label}
                          </div>
                        )}

                        {outEdge && outEdge.label && (
                          <div
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.63rem',
                              color: '#38bdf8',
                              opacity: 0.9,
                            }}
                          >
                            <ArrowRight size={10} />
                            <span>{outEdge.label}</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Side-by-side Drawn PNG when in Split Mode */}
          {displayMode === 'split' && blueprintImageUrl && (
            <div
              style={{
                borderRadius: '14px',
                overflow: 'hidden',
                border: `1.5px solid ${theme?.accentSecondary || '#06b6d4'}55`,
                background: '#0b0f19',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img
                src={blueprintImageUrl}
                alt="Drawn System Architecture Blueprint"
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            </div>
          )}
        </div>
      )}

      {/* Bottom Architectural Understanding & Execution Insights Strip */}
      {(bullets.length > 0 || editable) && (
        <div
          style={{
            background: theme?.cardBg || 'rgba(15, 23, 42, 0.72)',
            border: `1px solid ${theme?.cardBorder || 'rgba(148,163,184,0.18)'}`,
            borderRadius: '10px',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1 }}>
            {bullets.slice(0, 2).map((b, bIdx) => (
              <div
                key={bIdx}
                style={{
                  fontSize: '0.75rem',
                  color: theme?.textPrimary || '#e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span style={{ color: theme?.accentSecondary || '#06b6d4', fontWeight: 700 }}>▸</span>
                {editable && onChangeBullets ? (
                  <input
                    type="text"
                    value={b}
                    onChange={(e) => {
                      const next = [...bullets];
                      next[bIdx] = e.target.value;
                      onChangeBullets(next);
                    }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: theme?.textPrimary || '#e2e8f0',
                      fontSize: '0.75rem',
                      width: '100%',
                      outline: 'none',
                    }}
                  />
                ) : (
                  <span>{String(b).replace(/^[•▸]\s*/, '')}</span>
                )}
              </div>
            ))}
          </div>

          {editable && nodes.length < 8 && (
            <button
              type="button"
              onClick={handleAddNode}
              className="add-point-btn"
              style={{ margin: 0, padding: '5px 10px', fontSize: '0.73rem' }}
            >
              <Plus size={12} /> Add Component Node
            </button>
          )}
        </div>
      )}
    </div>
  );
}
