import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { listDictionary, addDictionary, updateDictionary, deleteDictionary } from '../../api';
import { t } from '../../i18n';
import { X, Plus, Edit2, Trash2, Search, BookOpen, Save, Database, LayoutTemplate, Key } from 'lucide-react';
import './index.css';

interface DictionaryPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DictionaryPanel({ isOpen, onClose }: DictionaryPanelProps) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);
  
  // Edit State
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [term, setTerm] = useState('');
  const [definition, setDefinition] = useState('');
  const [sqlHint, setSqlHint] = useState('');
  const [fieldMappings, setFieldMappings] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadEntries();
    }
  }, [isOpen]);

  async function loadEntries() {
    setLoading(true);
    try {
      const res = await listDictionary();
      setEntries(res.entries || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  function handleAdd() {
    setEditingId('new');
    setTerm('');
    setDefinition('');
    setSqlHint('');
    setFieldMappings('');
  }

  function handleEdit(entry: any) {
    setEditingId(entry.id);
    setTerm(entry.term);
    setDefinition(entry.definition);
    setSqlHint(entry.sql_hint || '');
    const mappings = entry.field_mappings || {};
    setFieldMappings(Object.entries(mappings).map(([k, v]) => `${k}=${v}`).join('\n'));
  }

  async function handleSave() {
    if (!term || !definition) return;
    
    // Parse mappings
    const mappings: Record<string, string> = {};
    if (fieldMappings.trim()) {
      fieldMappings.split('\n').forEach(line => {
        const parts = line.split('=');
        if (parts.length >= 2) {
          mappings[parts[0].trim()] = parts.slice(1).join('=').trim();
        }
      });
    }

    const data = {
      term,
      definition,
      sql_hint: sqlHint,
      field_mappings: mappings
    };

    try {
      if (editingId === 'new') {
        await addDictionary(data);
      } else {
        await updateDictionary(editingId!, data);
      }
      setEditingId(null);
      loadEntries();
    } catch (e) {
      console.error(e);
      alert(t('dict.saveFailed' as any) + e);
    }
  }

  function handleDeleteClick(id: string) {
    setDeletingId(id);
  }

  async function confirmDelete() {
    if (!deletingId) return;
    try {
      await deleteDictionary(deletingId);
      setDeletingId(null);
      loadEntries();
    } catch (e) {
      console.error(e);
      alert(t('dict.deleteFailed' as any) + e);
    }
  }

  const filtered = entries.filter(e => 
    e.term.toLowerCase().includes(search.toLowerCase()) || 
    e.definition.toLowerCase().includes(search.toLowerCase())
  );

  if (!isOpen) return null;

  return createPortal(
    <div className="dictionary-panel-overlay" onClick={onClose}>
      <div className="dictionary-panel" onClick={e => e.stopPropagation()} ref={panelRef}>
        <div className="dict-header">
          <div className="dict-title">
            <BookOpen size={20} />
            <h2>{t('dict.title' as any)}</h2>
          </div>
          <button className="dict-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="dict-toolbar">
          <div className="dict-search">
            <Search size={16} />
            <input 
              type="text" 
              placeholder={t('dict.search' as any)} 
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <button className="dict-add-btn" onClick={handleAdd}>
            <Plus size={16} /> {t('dict.add' as any)}
          </button>
        </div>

        <div className="dict-content">
          {loading ? (
            <div className="dict-loading">{t('dict.loading' as any)}</div>
          ) : filtered.length === 0 ? (
            <div className="dict-empty">{t('dict.empty' as any)}</div>
          ) : (
            <div className="dict-list">
              {filtered.map(entry => (
                <div key={entry.id} className="dict-card">
                  <div className="dict-card-header">
                    <h3>{entry.term}</h3>
                    <div className="dict-card-actions">
                      <button onClick={() => handleEdit(entry)}><Edit2 size={14} /></button>
                      <button className="delete" onClick={() => handleDeleteClick(entry.id)}><Trash2 size={14} /></button>
                    </div>
                  </div>
                  <div className="dict-card-body">
                    <p className="dict-def">{entry.definition}</p>
                    {entry.sql_hint && (
                      <div className="dict-sql">
                        <span className="dict-label">{t('dict.sqlHint' as any)}</span>
                        <code>{entry.sql_hint}</code>
                      </div>
                    )}
                    {entry.field_mappings && Object.keys(entry.field_mappings).length > 0 && (
                      <div className="dict-mappings">
                        <span className="dict-label">{t('dict.mapping' as any)}</span>
                        <div className="mapping-tags">
                          {Object.entries(entry.field_mappings).map(([k, v]) => (
                            <span key={k} className="mapping-tag">{k} → {v as string}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {editingId && (
          <div className="dict-modal-overlay">
            <div className="dict-modal">
              <h3>{editingId === 'new' ? t('dict.addTitle' as any) : t('dict.editTitle' as any)}</h3>
              <div className="dict-form">
                <div className="form-group">
                  <label>{t('dict.termLabel' as any)}</label>
                  <input type="text" value={term} onChange={e => setTerm(e.target.value)} placeholder={t('dict.termPlaceholder' as any)} />
                </div>
                <div className="form-group">
                  <label>{t('dict.defLabel' as any)}</label>
                  <textarea value={definition} onChange={e => setDefinition(e.target.value)} placeholder={t('dict.defPlaceholder' as any)} rows={3} />
                </div>
                <div className="form-group">
                  <label>{t('dict.sqlLabel' as any)}</label>
                  <textarea value={sqlHint} onChange={e => setSqlHint(e.target.value)} placeholder={t('dict.sqlPlaceholder' as any)} rows={2} />
                </div>
                <div className="form-group">
                  <label>{t('dict.mapLabel' as any)}</label>
                  <textarea value={fieldMappings} onChange={e => setFieldMappings(e.target.value)} placeholder={t('dict.mapPlaceholder' as any).replace(/\\n/g, '\n')} rows={3} />
                </div>
              </div>
              <div className="dict-modal-footer">
                <button className="dict-btn-cancel" onClick={() => setEditingId(null)}>{t('dict.cancel' as any)}</button>
                <button className="dict-btn-save" onClick={handleSave} disabled={!term || !definition}>
                  <Save size={16} /> {t('dict.save' as any)}
                </button>
              </div>
            </div>
          </div>
        )}

        {deletingId && (
          <div className="dict-modal-overlay">
            <div className="dict-modal confirm-modal">
              <h3>{t('dict.deleteConfirm' as any)}</h3>
              <div className="dict-modal-footer">
                <button className="dict-btn-cancel" onClick={() => setDeletingId(null)}>
                  {t('dict.cancel' as any)}
                </button>
                <button className="dict-btn-save delete-confirm-btn" onClick={confirmDelete}>
                  <Trash2 size={16} /> 删除
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
