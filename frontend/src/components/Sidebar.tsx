
import { useState, useEffect } from 'react';
import type { ConversationSummary, HealthStatus } from '../types';
import type { Lang } from '../i18n';
import { t, getLang } from '../i18n';
import { healthCheck } from '../api';
import { Plus, LogOut, MessageSquare, Settings, ChevronLeft, ChevronRight, BookOpen } from 'lucide-react';
import ContextMenu from './ContextMenu';
import SettingsPanel from './SettingsPanel';
import './Sidebar.css';

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  onOpenDictionary: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onLogout,
  collapsed,
  onToggleCollapse,
  theme,
  onToggleTheme,
  lang,
  onLangChange,
  onOpenDictionary,
}: SidebarProps) {
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    convId: string;
  } | null>(null);

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Poll health every 30s
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const s = await healthCheck();
        if (!cancelled) setHealth(s);
      } catch {
        if (!cancelled) setHealth(null);
      }
    }
    check();
    const interval = setInterval(check, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  function handleContextMenu(e: React.MouseEvent, convId: string) {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, convId });
  }

  function formatTime(iso: string) {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('sidebar.justNow');
    if (diffMin < 60) return `${diffMin} ${t('sidebar.minutesAgo')}`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr} ${t('sidebar.hoursAgo')}`;
    const diffDay = Math.floor(diffHr / 24);
    if (diffDay < 7) return `${diffDay} ${t('sidebar.daysAgo')}`;
    const locale = getLang() === 'en' ? 'en-US' : 'zh-CN';
    return d.toLocaleDateString(locale);
  }

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      {/* Logo / Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <span className="logo-text">SQL Agent</span>
        </div>
        <div className="header-btns">
          <button className="new-chat-btn" onClick={onNew} title={t('sidebar.newChat')}>
            <Plus size={18} />
          </button>
          <button className="logout-btn" onClick={onLogout} title={t('sidebar.reconfigure')}>
            <LogOut size={16} />
          </button>
        </div>
      </div>

      {/* Conversation List */}
      <div className="conversation-list">
        {conversations.length === 0 && (
          <div className="empty-hint">{t('sidebar.empty')}</div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conversation-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
            onContextMenu={(e) => handleContextMenu(e, c.id)}
          >
            <div className="conv-icon">
              <MessageSquare size={16} />
            </div>
            <div className="conv-info">
              <div className="conv-title">{c.title}</div>
              <div className="conv-meta">{formatTime(c.updated_at)}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer: Status + Settings + Collapse */}
      <div className="sidebar-footer">
        {health && !collapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: health.db_connected ? 'var(--success)' : 'var(--error)', display: 'inline-block' }} />
              DB
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: health.llm_connected ? 'var(--success)' : 'var(--error)', display: 'inline-block' }} />
              LLM
            </span>
          </div>
        )}
        <div style={{ display: 'flex', gap: 4 }}>
          {!collapsed && (
            <>
              <button
                className="collapse-btn"
                onClick={onOpenDictionary}
                title="业务字典"
                style={{ flex: 'none', width: 32 }}
              >
                <BookOpen size={16} />
              </button>
              <button
                className="collapse-btn"
                onClick={() => setSettingsOpen(!settingsOpen)}
                title={t('settings.title')}
                style={{ flex: 'none', width: 32 }}
              >
                <Settings size={16} />
              </button>
            </>
          )}
          <button className="collapse-btn" onClick={onToggleCollapse} title={collapsed ? t('sidebar.expand') : t('sidebar.collapse')} style={{ flex: 1 }}>
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </div>

      {/* Settings Panel */}
      {settingsOpen && (
        <SettingsPanel
          theme={theme}
          onToggleTheme={onToggleTheme}
          lang={lang}
          onLangChange={onLangChange}
          onClose={() => setSettingsOpen(false)}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onDelete={() => {
            onDelete(contextMenu.convId);
            setContextMenu(null);
          }}
          onClose={() => setContextMenu(null)}
        />
      )}
    </aside>
  );
}
