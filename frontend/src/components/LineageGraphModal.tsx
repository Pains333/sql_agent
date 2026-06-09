import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { X, ZoomIn, ZoomOut, Maximize, Network } from 'lucide-react';
import { LineageEntry } from '../types';
import { t } from '../i18n';
import './LineageGraphModal.css';

interface LineageGraphModalProps {
  entries: LineageEntry[];
  onClose: () => void;
}

export default function LineageGraphModal({ entries, onClose }: LineageGraphModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: {
        fontFamily: "'Inter', sans-serif",
        primaryColor: '#f8fafc',
        primaryTextColor: '#1e293b',
        primaryBorderColor: '#cbd5e1',
        lineColor: '#3b82f6',
        secondaryColor: '#e2e8f0',
        tertiaryColor: '#ffffff'
      },
      flowchart: {
        useMaxWidth: false
      }
    });
  }, []);

  useEffect(() => {
    async function loadDiagram() {
      if (!containerRef.current || entries.length === 0) return;

      try {
        setError(null);
        let md = 'graph LR\n';
        
        // Group nodes by table
        const tableNodes = new Map<string, Map<string, string>>();
        const edges: string[] = [];
        
        entries.forEach(e => {
          const srcId = `${e.source_table}_${e.source_column}`.replace(/[^a-zA-Z0-9]/g, '_');
          const dstId = `${e.target_table}_${e.target_column}`.replace(/[^a-zA-Z0-9]/g, '_');
          
          if (!tableNodes.has(e.source_table)) tableNodes.set(e.source_table, new Map());
          if (!tableNodes.has(e.target_table)) tableNodes.set(e.target_table, new Map());
          
          tableNodes.get(e.source_table)!.set(srcId, e.source_column);
          tableNodes.get(e.target_table)!.set(dstId, e.target_column);
          
          let logic = e.transform_logic || '';
          logic = logic.replace(/[\n\r]/g, ' ').replace(/"/g, "'");
          let edgeText = logic ? `|"${logic.substring(0, 30)}${logic.length > 30 ? '...' : ''}"|` : '';
          edges.push(`  ${srcId} -->${edgeText} ${dstId}`);
        });

        // Output subgraphs for tables
        for (const [tableName, nodes] of tableNodes.entries()) {
          const safeTableId = tableName.replace(/[^a-zA-Z0-9]/g, '_');
          md += `  subgraph ${safeTableId}["${tableName}"]\n`;
          md += `    direction TB\n`;
          for (const [id, label] of nodes.entries()) {
            md += `    ${id}("${label}")\n`;
          }
          md += `  end\n`;
        }

        // Apply styles to subgraphs and nodes
        md += `\n  classDef default fill:#ffffff,stroke:#cbd5e1,stroke-width:1px,color:#1e293b,rx:4,ry:4\n`;
        md += `  classDef cluster fill:#f8fafc,stroke:#94a3b8,stroke-width:1px,stroke-dasharray: 4 4\n`;
        
        md += '\n' + edges.join('\n') + '\n';

        // Use a unique ID to prevent conflicts in React Strict Mode (which runs effects twice)
        const id = `lineage-svg-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, md);
        
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.maxWidth = 'none';
            const viewBox = svgEl.getAttribute('viewBox');
            if (viewBox) {
              const [, , width, height] = viewBox.split(' ').map(Number);
              if (width && height) {
                svgEl.style.width = `${width}px`;
                svgEl.style.height = `${height}px`;
              }
            } else {
              svgEl.style.width = 'auto';
              svgEl.style.height = 'auto';
            }
          }
        }
      } catch (err: any) {
        console.error("Failed to render mermaid graph:", err);
        setError(err.message || String(err));
      }
    }

    loadDiagram();
  }, [entries]);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.3));
  const handleResetZoom = () => setZoom(1);

  return (
    <div className="lineage-modal-overlay" onClick={onClose}>
      <div className="lineage-graph-modal-container" onClick={e => e.stopPropagation()}>
        <div className="lineage-graph-modal-header">
          <div className="lineage-graph-modal-title">
            <Network size={18} />
            数据血缘可视化图谱
          </div>
          <div className="lineage-graph-modal-controls">
            <button onClick={handleZoomOut} title="Zoom Out"><ZoomOut size={16} /></button>
            <button onClick={handleResetZoom} title="Reset Zoom"><Maximize size={16} /></button>
            <button onClick={handleZoomIn} title="Zoom In"><ZoomIn size={16} /></button>
            <button className="close-btn" onClick={onClose}><X size={18} /></button>
          </div>
        </div>
        
        <div className="lineage-graph-modal-body">
          {error ? (
            <div style={{ padding: '20px', color: '#ef4444', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
              <h3>{t('dict.deleteFailed' as any)}</h3>
              {error}
            </div>
          ) : (
            <div 
              className="lineage-graph-wrapper"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
            >
              <div ref={containerRef} className="lineage-mermaid-container" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
