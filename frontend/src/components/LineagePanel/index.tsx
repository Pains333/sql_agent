import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Network, X, Plus, Edit2, Trash2, Search, ArrowRight, LayoutTemplate, Key, Bot } from 'lucide-react';
import { listLineage, addLineage, updateLineage, deleteLineage, startParseSqlLineage, getParseTaskStatus } from '../../api';
import { LineageEntry } from '../../types';
import { t } from '../../i18n';
import LineageGraphModal from '../LineageGraphModal';
import './index.css';

interface LineagePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LineagePanel({ isOpen, onClose }: LineagePanelProps) {
  const [entries, setEntries] = useState<LineageEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingEntry, setEditingEntry] = useState<Partial<LineageEntry> | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [graphModalOpen, setGraphModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [parseModalOpen, setParseModalOpen] = useState(false);
  const [parseSql, setParseSql] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      loadEntries();
    }
  }, [isOpen]);

  async function loadEntries() {
    try {
      setLoading(true);
      const data = await listLineage();
      setEntries(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const filteredEntries = entries.filter(e =>
    e.source_table.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.target_table.toLowerCase().includes(searchTerm.toLowerCase()) ||
    e.transform_logic?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  function handleEdit(entry?: LineageEntry) {
    setEditingEntry(entry || { source_table: '', source_column: '', target_table: '', target_column: '', transform_logic: '' });
  }

  async function handleSave() {
    if (!editingEntry) return;
    setSaving(true);
    setSaveError('');
    try {
      if (editingEntry.id) {
        await updateLineage(editingEntry.id, editingEntry as LineageEntry);
      } else {
        await addLineage(editingEntry as Omit<LineageEntry, 'id'>);
      }
      setEditingEntry(null);
      loadEntries();
    } catch (e: any) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function handleDeleteClick(id: string) {
    setDeletingId(id);
  }

  async function confirmDelete() {
    if (!deletingId) return;
    try {
      await deleteLineage(deletingId);
      setDeletingId(null);
      loadEntries();
    } catch (e: any) {
      setError(t('dict.deleteFailed' as any) + e.message);
    }
  }

  async function handleParseSql() {
    if (!parseSql.trim()) return;
    setParsing(true);
    setParseError('');
    try {
      const res = await startParseSqlLineage(parseSql);
      pollParseTask(res.task_id);
    } catch (e: any) {
      setParseError(e.message);
      setParsing(false);
    }
  }

  const handleTextareaResize = (e: React.FormEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = 'auto';
    target.style.height = Math.min(target.scrollHeight, 300) + 'px';
  };

  async function pollParseTask(taskId: string) {
    try {
      const task = await getParseTaskStatus(taskId);
      if (task.status === 'success') {
        setParsing(false);
        setParseModalOpen(false);
        setParseSql('');
        loadEntries();
      } else if (task.status === 'error') {
        setParseError(task.error || t('lineage.parseFailed' as any));
        setParsing(false);
      } else {
        setTimeout(() => pollParseTask(taskId), 2000);
      }
    } catch (e: any) {
      setParseError(e.message);
      setParsing(false);
    }
  }

  if (!isOpen) return null;

  return createPortal(
    <div className="lineage-panel-overlay" onClick={onClose}>
      <div className="lineage-panel" onClick={e => e.stopPropagation()} ref={panelRef}>
        <div className="lineage-header">
          <div className="lineage-title">
            <Network size={18} />
            <h2>{t('lineage.title' as any)}</h2>
          </div>
          <button className="lineage-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="lineage-toolbar">
          <div className="lineage-search">
            <Search size={14} className="search-icon" />
            <input 
              type="text" 
              placeholder={t('dict.search' as any)} 
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="lineage-graph-btn" onClick={() => setGraphModalOpen(true)} title={t('lineage.viewGraph' as any)}>
              <Network size={14} />
            </button>
            <button className="lineage-parse-btn" onClick={() => setParseModalOpen(true)}>
              <Bot size={14} />
              {t('lineage.parse' as any)}
            </button>
            <button className="lineage-add-btn" onClick={() => handleEdit()}>
              <Plus size={14} />
              {t('lineage.add' as any)}
            </button>
          </div>
        </div>

        <div className="lineage-content">
          {error && <div className="error-msg">{error}</div>}
          
          {loading ? (
            <div className="lineage-loading">
              <div className="spinner" />
              <span>{t('dict.loading' as any)}</span>
            </div>
          ) : filteredEntries.length === 0 ? (
            <div className="lineage-empty">
              <Network size={32} />
              <span>{searchTerm ? t('dict.noResults' as any) : t('lineage.empty' as any)}</span>
            </div>
          ) : (
            <div className="lineage-list">
              {filteredEntries.map(entry => (
                <div key={entry.id} className="lineage-card">
                  <div className="lineage-card-header">
                    <span className="lineage-id">#{entry.id}</span>
                    <div className="lineage-actions">
                      <button onClick={() => handleEdit(entry)} title={t('dict.edit' as any)}><Edit2 size={14} /></button>
                      <button className="delete-btn" onClick={() => handleDeleteClick(entry.id!)} title={t('dict.delete' as any)}><Trash2 size={14} /></button>
                    </div>
                  </div>
                  
                  <div className="lineage-flow">
                    <div className="lineage-node source">
                      <div className="node-title"><LayoutTemplate size={12}/> {entry.source_table}</div>
                      <div className="node-col"><Key size={12}/> {entry.source_column}</div>
                    </div>
                    
                    <div className="lineage-arrow">
                      <ArrowRight size={16} />
                    </div>
                    
                    <div className="lineage-node target">
                      <div className="node-title"><LayoutTemplate size={12}/> {entry.target_table}</div>
                      <div className="node-col"><Key size={12}/> {entry.target_column}</div>
                    </div>
                  </div>

                  {entry.transform_logic && (
                    <div className="lineage-logic">
                      <div className="logic-label">{t('lineage.logic' as any)}</div>
                      <code>{entry.transform_logic}</code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editingEntry && (
        <div className="lineage-modal-overlay" onClick={(e) => { e.stopPropagation(); setEditingEntry(null); }}>
          <div className="lineage-modal" onClick={e => e.stopPropagation()}>
            <div className="lineage-modal-header">
              <h3>{editingEntry.id ? t('lineage.editTitle' as any) : t('lineage.addTitle' as any)}</h3>
              <button className="modal-close" onClick={() => setEditingEntry(null)}><X size={18} /></button>
            </div>
            <div className="lineage-modal-body">
              
              <div className="lineage-form-section">
                <h4>{t('lineage.source' as any)}</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>{t('dict.table' as any)} <span className="req">*</span></label>
                    <input 
                      type="text" 
                      value={editingEntry.source_table} 
                      onChange={e => setEditingEntry({...editingEntry, source_table: e.target.value})} 
                    />
                  </div>
                  <div className="form-group">
                    <label>{t('dict.column' as any)} <span className="req">*</span></label>
                    <input 
                      type="text" 
                      value={editingEntry.source_column} 
                      onChange={e => setEditingEntry({...editingEntry, source_column: e.target.value})} 
                    />
                  </div>
                </div>
              </div>

              <div className="lineage-form-section">
                <h4>{t('lineage.target' as any)}</h4>
                <div className="form-row">
                  <div className="form-group">
                    <label>{t('dict.table' as any)} <span className="req">*</span></label>
                    <input 
                      type="text" 
                      value={editingEntry.target_table} 
                      onChange={e => setEditingEntry({...editingEntry, target_table: e.target.value})} 
                    />
                  </div>
                  <div className="form-group">
                    <label>{t('dict.column' as any)} <span className="req">*</span></label>
                    <input 
                      type="text" 
                      value={editingEntry.target_column} 
                      onChange={e => setEditingEntry({...editingEntry, target_column: e.target.value})} 
                    />
                  </div>
                </div>
              </div>

              <div className="lineage-form-section">
                <h4>{t('lineage.logic' as any)}</h4>
                <div className="form-group">
                  <textarea 
                    className="logic-input"
                    value={editingEntry.transform_logic} 
                    onChange={e => setEditingEntry({...editingEntry, transform_logic: e.target.value})} 
                    onInput={handleTextareaResize}
                    rows={1}
                    placeholder={t('lineage.logicPlaceholder' as any)}
                    style={{ minHeight: '80px', overflowY: 'auto' }}
                  />
                </div>
              </div>

              {saveError && <div className="error-msg">{saveError}</div>}
            </div>
            <div className="lineage-modal-footer">
              <button className="lineage-btn-cancel" onClick={() => setEditingEntry(null)} disabled={saving}>{t('dict.cancel' as any)}</button>
              <button 
                className="lineage-btn-save" 
                onClick={handleSave} 
                disabled={saving || !editingEntry.source_table || !editingEntry.source_column || !editingEntry.target_table || !editingEntry.target_column}
              >
                {saving ? '...' : t('dict.save' as any)}
              </button>
            </div>
          </div>
        </div>
      )}

      {deletingId && (
        <div className="lineage-modal-overlay" onClick={(e) => { e.stopPropagation(); setDeletingId(null); }}>
          <div className="lineage-modal confirm-modal" onClick={e => e.stopPropagation()}>
            <h3>{t('lineage.deleteConfirm' as any)}</h3>
            <div className="lineage-modal-footer">
              <button className="lineage-btn-cancel" onClick={() => setDeletingId(null)}>
                {t('dict.cancel' as any)}
              </button>
              <button className="lineage-btn-save delete-confirm-btn" onClick={confirmDelete}>
                <Trash2 size={16} /> 删除
              </button>
            </div>
          </div>
        </div>
      )}

      {parseModalOpen && (
        <div className="lineage-modal-overlay" onClick={(e) => { e.stopPropagation(); if(!parsing) setParseModalOpen(false); }}>
          <div className="lineage-modal" onClick={e => e.stopPropagation()}>
            <div className="lineage-modal-header">
              <h3>{t('lineage.parseTitle' as any)}</h3>
              <button className="modal-close" onClick={() => !parsing && setParseModalOpen(false)} disabled={parsing}><X size={18} /></button>
            </div>
            <div className="lineage-modal-body">
              <div className="lineage-form" style={{ padding: 20 }}>
                <div className="form-group">
                  <textarea 
                    className="logic-input"
                    value={parseSql} 
                    onChange={e => setParseSql(e.target.value)} 
                    onInput={handleTextareaResize}
                    rows={1}
                    placeholder={t('lineage.parseSqlPlaceholder' as any)}
                    disabled={parsing}
                    style={{ fontFamily: 'var(--font-mono)', minHeight: '120px', overflowY: 'auto' }}
                  />
                </div>
                {parseError && <div className="error-msg">{parseError}</div>}
              </div>
            </div>
            <div className="lineage-modal-footer">
              <button className="lineage-btn-cancel" onClick={() => setParseModalOpen(false)} disabled={parsing}>{t('dict.cancel' as any)}</button>
              <button 
                className="lineage-parse-btn" 
                onClick={handleParseSql} 
                disabled={parsing || !parseSql.trim()}
                style={{ padding: '8px 16px', height: '36px', border: 'none' }}
              >
                {parsing ? (
                  <>
                    <div className="spinner" style={{width: 14, height: 14, borderWidth: 2}}></div>
                    {t('lineage.parsing' as any)}
                  </>
                ) : (
                  <>
                    <Bot size={14} />
                    {t('lineage.parse' as any)}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {graphModalOpen && (
        <LineageGraphModal 
          entries={entries} 
          onClose={() => setGraphModalOpen(false)} 
        />
      )}
    </div>,
    document.body
  );
}
