
import { useState, useEffect } from 'react';
import type { TableColumn } from '../types';
import { listTables, describeTable } from '../api';
import { t } from '../i18n';
import { X, Database, ChevronDown, ChevronRight, Table2 } from 'lucide-react';
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
          <X size={16} />
        </button>
      </div>

      <div className="schema-drawer-db">
        <Database size={14} />
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
              {expandedTable === table ? (
                <ChevronDown size={12} />
              ) : (
                <ChevronRight size={12} />
              )}
              <Table2 size={14} />
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
