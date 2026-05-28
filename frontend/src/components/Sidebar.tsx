/* ============================================
   Sidebar — conversation list & management
   ============================================ */

import { useState, useEffect } from 'react';
import type { ConversationSummary, HealthStatus } from '../types';
import { t, getLang } from '../i18n';
import { healthCheck } from '../api';
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
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </button>
          <button className="logout-btn" onClick={onLogout} title={t('sidebar.reconfigure')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
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
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
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
        {health && (
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
          <button
            className="collapse-btn"
            onClick={() => setSettingsOpen(!settingsOpen)}
            title={t('settings.title')}
            style={{ flex: 'none', width: 32 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
          <button className="collapse-btn" onClick={onToggleCollapse} title={collapsed ? t('sidebar.expand') : t('sidebar.collapse')} style={{ flex: 1 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {collapsed ? (
                <polyline points="9 18 15 12 9 6" />
              ) : (
                <polyline points="15 18 9 12 15 6" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Settings Panel */}
      {settingsOpen && (
        <SettingsPanel
          theme={theme}
          onToggleTheme={onToggleTheme}
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
