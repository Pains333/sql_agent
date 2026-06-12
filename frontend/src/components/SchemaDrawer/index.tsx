import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { TableColumn } from '../../types';
import { listDatabases, listTables, describeTable, previewTable } from '../../api';
import DataPreviewModal from '../DataPreviewModal';
import ERDiagramModal from '../ERDiagramModal';
import { t } from '../../i18n';
import { X, Database, ChevronDown, ChevronRight, Table2, Eye, Network } from 'lucide-react';
import './index.css';

interface SchemaDrawerProps {
  onClose: () => void;
  refreshKey?: string | number;
}

export default function SchemaDrawer({ onClose, refreshKey }: SchemaDrawerProps) {
  const [databases, setDatabases] = useState<string[]>([]);
  const [tablesByDb, setTablesByDb] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [expandedDbs, setExpandedDbs] = useState<Set<string>>(new Set());
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [columns, setColumns] = useState<Record<string, TableColumn[]>>({});
  const [previewData, setPreviewData] = useState<{ database: string; table: string; columns: string[]; rows: any[][] } | null>(null);
  const [loadingTable, setLoadingTable] = useState<string | null>(null);
  const [erModalDb, setErModalDb] = useState<string | null>(null);

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

  // Keep track of expanded items for refresh
  const expandedStateRef = useRef({ expandedDbs, expandedTables });
  useEffect(() => {
    expandedStateRef.current = { expandedDbs, expandedTables };
  }, [expandedDbs, expandedTables]);

  useEffect(() => {
    let cancelled = false;
    async function refreshData() {
      setLoading(true);
      try {
        const res = await listDatabases();
        if (cancelled) return;
        setDatabases(res.databases);

        // Refetch tables for currently expanded databases
        const dbs = Array.from(expandedStateRef.current.expandedDbs);
        if (dbs.length > 0) {
          const newTables: Record<string, string[]> = {};
          await Promise.all(dbs.map(async (db) => {
            try {
              const r = await listTables(db);
              newTables[db] = r.tables;
            } catch {
              newTables[db] = [];
            }
          }));
          if (!cancelled) setTablesByDb(prev => ({ ...prev, ...newTables }));
        }

        // Refetch columns for currently expanded tables
        const tables = Array.from(expandedStateRef.current.expandedTables);
        if (tables.length > 0) {
          const newCols: Record<string, TableColumn[]> = {};
          await Promise.all(tables.map(async (key) => {
            const [db, tbl] = key.split('::');
            try {
              const r = await describeTable(db, tbl);
              newCols[key] = r.columns;
            } catch {
              newCols[key] = [];
            }
          }));
          if (!cancelled) setColumns(prev => ({ ...prev, ...newCols }));
        }
      } catch (e) {
        if (!cancelled) setDatabases([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    refreshData();
    return () => { cancelled = true; };
  }, [refreshKey]);

  async function toggleDb(db: string) {
    setExpandedDbs(prev => {
      const next = new Set(prev);
      if (next.has(db)) {
        next.delete(db);
      } else {
        next.add(db);
      }
      return next;
    });

    if (!tablesByDb[db]) {
      try {
        const res = await listTables(db);
        setTablesByDb(prev => ({ ...prev, [db]: res.tables }));
      } catch {
        setTablesByDb(prev => ({ ...prev, [db]: [] }));
      }
    }
  }

  async function toggleTable(db: string, tableName: string) {
    const key = `${db}::${tableName}`;
    setExpandedTables(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });

    if (!columns[key]) {
      setLoadingTable(key);
      try {
        const res = await describeTable(db, tableName);
        setColumns((prev) => ({ ...prev, [key]: res.columns }));
      } catch {
        setColumns((prev) => ({ ...prev, [key]: [] }));
      } finally {
        setLoadingTable(null);
      }
    }
  }

  async function handlePreview(e: React.MouseEvent, db: string, table: string) {
    e.stopPropagation();
    try {
      const res = await previewTable(db, table);
      setPreviewData({ database: db, table: res.table, columns: res.columns, rows: res.rows });
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

      <div className="schema-drawer-body">
        {loading && (
          <div className="schema-loading">{t('schema.loading')}</div>
        )}
        {!loading && databases.length === 0 && (
          <div className="schema-empty">{t('schema.noTables')}</div>
        )}
        {databases.map((db) => (
          <div key={db} className="schema-db-node" style={{ marginBottom: 12 }}>
            <div
              className={`schema-table-btn ${expandedDbs.has(db) ? 'expanded' : ''}`}
              onClick={() => toggleDb(db)}
              style={{ fontWeight: 600, padding: '8px 12px' }}
            >
              {expandedDbs.has(db) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Database size={16} />
              <span style={{ flex: 1, textAlign: 'left' }}>{db}</span>
              <button 
                className="schema-er-btn"
                onClick={(e) => { e.stopPropagation(); setErModalDb(db); }}
                title="查看数据库结构ER图"
                style={{ marginLeft: 8 }}
              >
                <Network size={14} />
              </button>
            </div>
            
            {expandedDbs.has(db) && (
              <div className="schema-tables-list" style={{ marginLeft: 16 }}>
                {!tablesByDb[db] ? (
                  <div className="schema-col-loading">{t('schema.loading')}</div>
                ) : tablesByDb[db].length === 0 ? (
                  <div className="schema-empty">{t('schema.noTables')}</div>
                ) : (
                  tablesByDb[db].map((table) => {
                    const tKey = `${db}::${table}`;
                    return (
                      <div key={table} className="schema-table-node">
                        <div
                          className={`schema-table-btn ${expandedTables.has(tKey) ? 'expanded' : ''}`}
                          onClick={() => toggleTable(db, table)}
                        >
                          {expandedTables.has(tKey) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          <Table2 size={14} />
                          <span style={{ flex: 1, textAlign: 'left' }}>{table}</span>
                          <button 
                            className="schema-preview-btn" 
                            onClick={(e) => handlePreview(e, db, table)}
                            title="Preview Data"
                          >
                            <Eye size={14} />
                          </button>
                        </div>
                        {expandedTables.has(tKey) && (
                          <div className="schema-columns">
                            {loadingTable === tKey && (
                              <div className="schema-col-loading">{t('schema.loading')}</div>
                            )}
                            {columns[tKey]?.map((col) => (
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
                    );
                  })
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {previewData && (
        <DataPreviewModal
          database={previewData.database}
          table={previewData.table}
          columns={previewData.columns}
          rows={previewData.rows}
          onClose={() => setPreviewData(null)}
        />
      )}

      {erModalDb && (
        <ERDiagramModal 
          database={erModalDb} 
          onClose={() => setErModalDb(null)} 
        />
      )}
    </div>
  );
}
