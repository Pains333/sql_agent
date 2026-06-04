import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { TableColumn } from '../types';
import { listTables, describeTable, previewTable } from '../api';
import DataPreviewModal from './DataPreviewModal';
import ERDiagramModal from './ERDiagramModal';
import { t } from '../i18n';
import { X, Database, ChevronDown, ChevronRight, Table2, Eye, Network } from 'lucide-react';
import './SchemaDrawer.css';

interface SchemaDrawerProps {
  currentDb: string;
  onClose: () => void;
}

export default function SchemaDrawer({ currentDb, onClose }: SchemaDrawerProps) {
  const [tables, setTables] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [columns, setColumns] = useState<Record<string, TableColumn[]>>({});
  const [previewData, setPreviewData] = useState<{ table: string; columns: string[]; rows: any[][] } | null>(null);
  const [loadingTable, setLoadingTable] = useState<string | null>(null);
  const [erModalOpen, setErModalOpen] = useState(false);

  // Resize state
  const [drawerWidth, setDrawerWidth] = useState(350);
  const isResizing = useRef(false);

  const startResizing = useCallback((e: React.MouseEvent) => {
    isResizing.current = true;
    e.preventDefault();
  }, []);

  const stopResizing = useCallback(() => {
    isResizing.current = false;
  }, []);

  const resize = useCallback((e: MouseEvent) => {
    if (isResizing.current) {
      // Since it's on the right, width = window width - mouse X
      const newWidth = window.innerWidth - e.clientX;
      if (newWidth > 200 && newWidth < 800) {
        setDrawerWidth(newWidth);
      }
    }
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  useEffect(() => {
    setLoading(true);
    listTables(currentDb)
      .then((res) => setTables(res.tables))
      .catch(() => setTables([]))
      .finally(() => setLoading(false));
  }, [currentDb]);

  async function toggleTable(tableName: string) {
    setExpandedTables(prev => {
      const next = new Set(prev);
      if (next.has(tableName)) {
        next.delete(tableName);
      } else {
        next.add(tableName);
      }
      return next;
    });

    if (!columns[tableName]) {
      setLoadingTable(tableName);
      try {
        const res = await describeTable(currentDb, tableName);
        setColumns((prev) => ({ ...prev, [tableName]: res.columns }));
      } catch {
        setColumns((prev) => ({ ...prev, [tableName]: [] }));
      } finally {
        setLoadingTable(null);
      }
    }
  }

  async function handlePreview(e: React.MouseEvent, table: string) {
    e.stopPropagation();
    try {
      const res = await previewTable(currentDb, table);
      setPreviewData(res);
    } catch (err) {
      console.error('Failed to preview table:', err);
    }
  }

  return (
    <div className="schema-drawer" style={{ width: drawerWidth }}>
      <div 
        className="schema-resizer" 
        onMouseDown={startResizing} 
      />
      <div className="schema-drawer-header">
        <span className="schema-drawer-title">{t('schema.title')}</span>
        <button className="schema-drawer-close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      <div className="schema-drawer-db">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Database size={14} />
          {currentDb}
        </div>
        <button 
          className="schema-er-btn"
          onClick={() => setErModalOpen(true)}
          title="View ER Diagram"
        >
          <Network size={14} />
          ER
        </button>
      </div>

      <div className="schema-drawer-body">
        {loading && (
          <div className="schema-loading">{t('schema.loading')}</div>
        )}
        {!loading && tables.length === 0 && (
          <div className="schema-empty">{t('schema.noTables')}</div>
        )}
        {tables.map((table) => (
          <div key={table} className="schema-table-node">
            <div
              className={`schema-table-btn ${expandedTables.has(table) ? 'expanded' : ''}`}
              onClick={() => toggleTable(table)}
            >
              {expandedTables.has(table) ? (
                <ChevronDown size={12} />
              ) : (
                <ChevronRight size={12} />
              )}
              <Table2 size={14} />
              <span style={{ flex: 1, textAlign: 'left' }}>{table}</span>
              <button 
                className="schema-preview-btn" 
                onClick={(e) => handlePreview(e, table)}
                title="Preview Data"
              >
                <Eye size={14} />
              </button>
            </div>
            {expandedTables.has(table) && (
              <div className="schema-columns">
                {loadingTable === table && (
                  <div className="schema-col-loading">{t('schema.loading')}</div>
                )}
                {columns[table]?.map((col) => (
                  <div key={col.name} className="schema-col-item">
                    <span className="schema-col-name" title={col.name}>{col.name}</span>
                    <span className="schema-col-type" title={col.type}>{col.type}</span>
                    {col.constraints && (
                      <span className="schema-col-constraint" title={col.constraints}>{col.constraints}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {previewData && (
        <DataPreviewModal
          database={currentDb}
          table={previewData.table}
          columns={previewData.columns}
          rows={previewData.rows}
          onClose={() => setPreviewData(null)}
        />
      )}

      {erModalOpen && (
        <ERDiagramModal 
          database={currentDb} 
          onClose={() => setErModalOpen(false)} 
        />
      )}
    </div>
  );
}
