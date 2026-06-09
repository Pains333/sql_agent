import { useState, useEffect, useMemo } from 'react';
import { Network, X, Search, Plus, Save, Edit2, Trash2, ArrowRight, Zap } from 'lucide-react';
import { listLineage, addLineage, updateLineage, deleteLineage, startParseSqlLineage, getParseTaskStatus } from '../api';
import { LineageEntry } from '../types';
import { t } from '../i18n';
import LineageGraphModal from './LineageGraphModal';
import './LineagePanel.css';

interface LineagePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LineagePanel({ isOpen, onClose }: LineagePanelProps) {
  const [entries, setEntries] = useState<LineageEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Modals
  const [editingId, setEditingId] = useState<string | null>(null); // 'new', 'parse', or id
  const [sourceTable, setSourceTable] = useState('');
  const [sourceColumn, setSourceColumn] = useState('');
  const [targetTable, setTargetTable] = useState('');
  const [targetColumn, setTargetColumn] = useState('');
  const [transformLogic, setTransformLogic] = useState('');

  const [parseSql, setParseSql] = useState('');
  const [parsing, setParsing] = useState(false);
  const [showGraphModal, setShowGraphModal] = useState(false);

  useEffect(() => {
    loadEntries();
  }, []);

  async function loadEntries() {
    try {
      setLoading(true);
      const data = await listLineage();
      setEntries(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    if (!search) return entries;
    const lower = search.toLowerCase();
    return entries.filter(e =>
      e.source_table.toLowerCase().includes(lower) ||
      e.source_column.toLowerCase().includes(lower) ||
      e.target_table.toLowerCase().includes(lower) ||
      e.target_column.toLowerCase().includes(lower) ||
      e.transform_logic.toLowerCase().includes(lower)
    );
  }, [entries, search]);

  function handleAdd() {
    setEditingId('new');
    setSourceTable('');
    setSourceColumn('');
    setTargetTable('');
    setTargetColumn('');
    setTransformLogic('');
  }

  function handleEdit(e: LineageEntry) {
    setEditingId(e.id);
    setSourceTable(e.source_table);
    setSourceColumn(e.source_column);
    setTargetTable(e.target_table);
    setTargetColumn(e.target_column);
    setTransformLogic(e.transform_logic);
  }

  async function handleSave() {
    try {
      const data = {
        source_table: sourceTable,
        source_column: sourceColumn,
        target_table: targetTable,
        target_column: targetColumn,
        transform_logic: transformLogic,
      };
      if (editingId === 'new') {
        await addLineage(data);
      } else {
        await updateLineage(editingId!, data);
      }
      setEditingId(null);
      loadEntries();
    } catch (e) {
      console.error(e);
      alert(t('dict.saveFailed' as any) + e);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(t('dict.deleteConfirm' as any))) return;
    try {
      await deleteLineage(id);
      loadEntries();
    } catch (e) {
      console.error(e);
      alert(t('dict.deleteFailed' as any) + e);
    }
  }

  async function handleParse() {
    if (!parseSql.trim()) return;
    setParsing(true);
    try {
      const { task_id } = await startParseSqlLineage(parseSql);

      const pollInterval = setInterval(async () => {
        try {
          const res = await getParseTaskStatus(task_id);
          if (res.status === 'success') {
            clearInterval(pollInterval);
            alert(t('lineage.parseSuccess' as any).replace('{n}', String(res.data?.length || 0)));
            loadEntries();
            setEditingId(null);
            setParsing(false);
          } else if (res.status === 'error') {
            clearInterval(pollInterval);
            alert(`提取失败: ${res.error}`);
            setParsing(false);
          }
        } catch (pollErr) {
          console.error("Polling error:", pollErr);
        }
      }, 3000);

    } catch (e: any) {
      console.error(e);
      alert(t('lineage.parseFailed' as any) + '\n' + e);
      setParsing(false);
    }
  }

  return (
    <div className={`lineage-panel ${isOpen ? 'open' : ''}`}>
      <div className="lineage-header">
        <div className="lineage-title">
          <Network size={20} />
          <h2>{t('lineage.title' as any)}</h2>
        </div>
        <button className="lineage-close" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="lineage-toolbar">
        <div className="lineage-search">
          <Search size={16} />
          <input
            type="text"
            placeholder={t('lineage.search' as any)}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button className="lineage-graph-btn" onClick={() => setShowGraphModal(true)}>
          <Network size={16} /> 可视化图谱
        </button>
        <button className="lineage-parse-btn" onClick={() => { setEditingId('parse'); setParseSql(''); }}>
          <Zap size={16} /> {t('lineage.parse' as any)}
        </button>
        <button className="lineage-add-btn" onClick={handleAdd}>
          <Plus size={16} /> {t('lineage.add' as any)}
        </button>
      </div>

      <div className="lineage-content">
        {loading ? (
          <div className="dict-loading">{t('lineage.loading' as any)}</div>
        ) : filtered.length === 0 ? (
          <div className="dict-empty">{t('lineage.empty' as any)}</div>
        ) : (
          <div className="lineage-list">
            {filtered.map(entry => (
              <div key={entry.id} className="lineage-card">
                <div className="lineage-flow">
                  <span className="lineage-node">{entry.source_table}.{entry.source_column}</span>
                  <span className="lineage-arrow"><ArrowRight size={16} /></span>
                  <span className="lineage-node">{entry.target_table}.{entry.target_column}</span>
                </div>
                {entry.transform_logic && (
                  <div className="lineage-logic">
                    {entry.transform_logic}
                  </div>
                )}

                <div className="lineage-actions">
                  <button onClick={() => handleEdit(entry)}><Edit2 size={14} /></button>
                  <button className="delete-btn" onClick={() => handleDelete(entry.id)}><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {editingId === 'parse' && (
        <div className="lineage-modal-overlay">
          <div className="lineage-modal">
            <h3>{t('lineage.parseTitle' as any)}</h3>
            <div className="lineage-form">
              <div className="form-group">
                <textarea
                  value={parseSql}
                  onChange={e => setParseSql(e.target.value)}
                  placeholder={t('lineage.parseSqlPlaceholder' as any)}
                  rows={10}
                />
              </div>
            </div>
            <div className="lineage-modal-footer">
              <button className="lineage-btn-cancel" onClick={() => setEditingId(null)}>{t('dict.cancel' as any)}</button>
              <button className="lineage-btn-save" onClick={handleParse} disabled={!parseSql.trim() || parsing}>
                <Zap size={16} /> {parsing ? t('lineage.parsing' as any) : t('lineage.parse' as any)}
              </button>
            </div>
          </div>
        </div>
      )}

      {(editingId === 'new' || (editingId && editingId !== 'parse')) && (
        <div className="lineage-modal-overlay">
          <div className="lineage-modal">
            <h3>{editingId === 'new' ? t('lineage.addTitle' as any) : t('lineage.editTitle' as any)}</h3>
            <div className="lineage-form">
              <div className="form-group">
                <label>{t('lineage.sourceTable' as any)}</label>
                <input type="text" value={sourceTable} onChange={e => setSourceTable(e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('lineage.sourceColumn' as any)}</label>
                <input type="text" value={sourceColumn} onChange={e => setSourceColumn(e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('lineage.targetTable' as any)}</label>
                <input type="text" value={targetTable} onChange={e => setTargetTable(e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('lineage.targetColumn' as any)}</label>
                <input type="text" value={targetColumn} onChange={e => setTargetColumn(e.target.value)} />
              </div>
              <div className="form-group">
                <label>{t('lineage.transformLogic' as any)}</label>
                <textarea value={transformLogic} onChange={e => setTransformLogic(e.target.value)} rows={2} />
              </div>
            </div>
            <div className="lineage-modal-footer">
              <button className="lineage-btn-cancel" onClick={() => setEditingId(null)}>{t('dict.cancel' as any)}</button>
              <button className="lineage-btn-save" onClick={handleSave} disabled={!sourceTable || !sourceColumn || !targetTable || !targetColumn}>
                <Save size={16} /> {t('dict.save' as any)}
              </button>
            </div>
          </div>
        </div>
      )}

      {showGraphModal && (
        <LineageGraphModal 
          entries={entries} 
          onClose={() => setShowGraphModal(false)} 
        />
      )}
    </div>
  );
}
