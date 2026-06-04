import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { X, ZoomIn, ZoomOut, Maximize } from 'lucide-react';
import { getErDiagram } from '../api';

import './ERDiagramModal.css';

// Initialize mermaid
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    fontFamily: "'Inter', sans-serif",
    primaryColor: '#f3f4f6',
    primaryTextColor: '#1f2937',
    primaryBorderColor: '#d1d5db',
    lineColor: '#6366f1',
    secondaryColor: '#e0e7ff',
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

        const { svg } = await mermaid.render('er-diagram-svg', md);
        
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Clean up the max-width to allow zooming
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.maxWidth = 'none';
            svgEl.style.height = 'auto';
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
            <span>{database}</span> ER Diagram
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
