import { useState, useEffect } from 'react';
import { listDictionary, addDictionary, updateDictionary, deleteDictionary } from '../api';
import { t } from '../i18n';
import { X, Plus, Edit2, Trash2, Search, BookOpen, Save } from 'lucide-react';
import './DictionaryPanel.css';

interface DictionaryPanelProps {
  onClose: () => void;
}

export default function DictionaryPanel({ onClose }: DictionaryPanelProps) {
  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  // Edit State
  const [editingId, setEditingId] = useState<string | null>(null);
  const [term, setTerm] = useState('');
  const [definition, setDefinition] = useState('');
  const [sqlHint, setSqlHint] = useState('');
  const [fieldMappings, setFieldMappings] = useState('');

  useEffect(() => {
    loadEntries();
  }, []);

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
      alert('保存失败: ' + e);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('确认删除该业务规则？')) return;
    try {
      await deleteDictionary(id);
      loadEntries();
    } catch (e) {
      console.error(e);
      alert('删除失败: ' + e);
    }
  }

  const filtered = entries.filter(e => 
    e.term.toLowerCase().includes(search.toLowerCase()) || 
    e.definition.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="dictionary-panel">
      <div className="dict-header">
        <div className="dict-title">
          <BookOpen size={20} />
          <h2>业务字典 & 知识库</h2>
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
            placeholder="搜索术语..." 
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <button className="dict-add-btn" onClick={handleAdd}>
          <Plus size={16} /> 新增规则
        </button>
      </div>

      <div className="dict-content">
        {loading ? (
          <div className="dict-loading">加载中...</div>
        ) : filtered.length === 0 ? (
          <div className="dict-empty">暂无业务规则</div>
        ) : (
          <div className="dict-list">
            {filtered.map(entry => (
              <div key={entry.id} className="dict-card">
                <div className="dict-card-header">
                  <h3>{entry.term}</h3>
                  <div className="dict-card-actions">
                    <button onClick={() => handleEdit(entry)}><Edit2 size={14} /></button>
                    <button className="delete" onClick={() => handleDelete(entry.id)}><Trash2 size={14} /></button>
                  </div>
                </div>
                <div className="dict-card-body">
                  <p className="dict-def">{entry.definition}</p>
                  {entry.sql_hint && (
                    <div className="dict-sql">
                      <span className="dict-label">SQL示例:</span>
                      <code>{entry.sql_hint}</code>
                    </div>
                  )}
                  {entry.field_mappings && Object.keys(entry.field_mappings).length > 0 && (
                    <div className="dict-mappings">
                      <span className="dict-label">映射:</span>
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
            <h3>{editingId === 'new' ? '新增业务规则' : '编辑业务规则'}</h3>
            <div className="dict-form">
              <div className="form-group">
                <label>业务术语 (必填)</label>
                <input type="text" value={term} onChange={e => setTerm(e.target.value)} placeholder="如: DAU, 活跃用户" />
              </div>
              <div className="form-group">
                <label>定义说明 (必填)</label>
                <textarea value={definition} onChange={e => setDefinition(e.target.value)} placeholder="详细解释该术语的计算逻辑或含义..." rows={3} />
              </div>
              <div className="form-group">
                <label>SQL 示例 / 提示 (选填)</label>
                <textarea value={sqlHint} onChange={e => setSqlHint(e.target.value)} placeholder="如: SELECT COUNT(DISTINCT user_id)..." rows={2} />
              </div>
              <div className="form-group">
                <label>字段枚举映射 (选填, 每行一个 key=value)</label>
                <textarea value={fieldMappings} onChange={e => setFieldMappings(e.target.value)} placeholder="status=1=有效\nstatus=0=无效" rows={3} />
              </div>
            </div>
            <div className="dict-modal-footer">
              <button className="dict-btn-cancel" onClick={() => setEditingId(null)}>取消</button>
              <button className="dict-btn-save" onClick={handleSave} disabled={!term || !definition}>
                <Save size={16} /> 保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
