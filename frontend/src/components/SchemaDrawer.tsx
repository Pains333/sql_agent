/* ============================================
   SchemaDrawer — database structure browser
   ============================================ */

import { useState, useEffect } from 'react';
import type { TableColumn } from '../types';
import { listTables, describeTable } from '../api';
import { t } from '../i18n';
import './SchemaDrawer.css';

interface SchemaDrawerProps {
  currentDb: string;
  onClose: () => void;
}

export default function SchemaDrawer({ currentDb, onClose }: SchemaDrawerProps) {
  const [tables, setTables] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedTable, setExpandedTable] = useState<string | null>(null);
  const [columns, setColumns] = useState<Record<string, TableColumn[]>>({});
  const [loadingTable, setLoadingTable] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    listTables(currentDb)
      .then((res) => setTables(res.tables))
      .catch(() => setTables([]))
      .finally(() => setLoading(false));
  }, [currentDb]);

  async function toggleTable(tableName: string) {
    if (expandedTable === tableName) {
      setExpandedTable(null);
      return;
    }
    setExpandedTable(tableName);
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

  return (
    <div className="schema-drawer">
      <div className="schema-drawer-header">
        <span className="schema-drawer-title">{t('schema.title')}</span>
        <button className="schema-drawer-close" onClick={onClose}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="schema-drawer-db">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
        </svg>
        {currentDb}
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
            <button
              className={`schema-table-btn ${expandedTable === table ? 'expanded' : ''}`}
              onClick={() => toggleTable(table)}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {expandedTable === table ? (
                  <polyline points="6 9 12 15 18 9" />
                ) : (
                  <polyline points="9 18 15 12 9 6" />
                )}
              </svg>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" />
              </svg>
              <span>{table}</span>
            </button>
            {expandedTable === table && (
              <div className="schema-columns">
                {loadingTable === table && (
                  <div className="schema-col-loading">{t('schema.loading')}</div>
                )}
                {columns[table]?.map((col) => (
                  <div key={col.name} className="schema-col-item">
                    <span className="schema-col-name">{col.name}</span>
                    <span className="schema-col-type">{col.type}</span>
                    {col.constraints && (
                      <span className="schema-col-constraint">{col.constraints}</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
