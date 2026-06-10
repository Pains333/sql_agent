import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { X, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { getErDiagram } from '../../api';

import './index.css';

// Initialize mermaid
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
  er: {
    useMaxWidth: false,
  }
});

interface ERDiagramModalProps {
  database: string;
  onClose: () => void;
}

export default function ERDiagramModal({ database, onClose }: ERDiagramModalProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    async function loadDiagram() {
      try {
        setLoading(true);
        const data = await getErDiagram(database);
        
        if (data.tables.length === 0) {
          throw new Error('No tables found in database');
        }

        // Generate Mermaid ER syntax
        let md = 'erDiagram\n';
        for (const table of data.tables) {
          md += `  ${table.name} {\n`;
          for (const col of table.columns) {
            const isPk = col.constraints?.toUpperCase().includes('PRIMARY KEY') ? 'PK' : '';
            const isFk = col.constraints?.toUpperCase().includes('REFERENCES') ? 'FK' : '';
            const constraintMarker = [isPk, isFk].filter(Boolean).join(',');
            const safeType = col.type.replace(/[^a-zA-Z0-9_]/g, '_');
            const safeName = col.name.replace(/[^a-zA-Z0-9_]/g, '_');
            md += `    ${safeName} ${safeType} ${constraintMarker}\n`;
          }
          md += `  }\n`;
        }

        for (const rel of data.relationships) {
          // A ||--o{ B : "label"
          md += `  ${rel.target_table} ||--o{ ${rel.source_table} : "REFERENCES"\n`;
        }

        const id = `er-svg-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, md);
        
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Force SVG to render at its native resolution to prevent squishing
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
        setError(err.message || 'Failed to generate ER Diagram');
      } finally {
        setLoading(false);
      }
    }

    loadDiagram();
  }, [database]);

  const handleZoomIn = () => setZoom(z => Math.min(z + 0.2, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.2, 0.3));
  const handleResetZoom = () => setZoom(1);

  return (
    <div className="er-modal-overlay" onClick={onClose}>
      <div className="er-modal-container" onClick={e => e.stopPropagation()}>
        <div className="er-modal-header">
          <div className="er-modal-title">
            <span>{database}</span> 数据库结构ER图
          </div>
          <div className="er-modal-controls">
            <button onClick={handleZoomOut} title="Zoom Out"><ZoomOut size={16} /></button>
            <span className="er-zoom-level">{Math.round(zoom * 100)}%</span>
            <button onClick={handleResetZoom} title="Reset Zoom"><Maximize size={16} /></button>
            <button onClick={handleZoomIn} title="Zoom In"><ZoomIn size={16} /></button>
            <div className="er-modal-divider" />
            <button onClick={onClose} className="er-close-btn" title="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="er-modal-body">
          {loading && (
            <div className="er-loading">
              <div className="er-spinner" />
              <span>Generating Diagram...</span>
            </div>
          )}
          {error && (
            <div className="er-error">{error}</div>
          )}
          <div 
            className={`er-canvas-container ${loading || error ? 'hidden' : ''}`}
          >
            <div 
              className="er-canvas"
              ref={containerRef}
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
