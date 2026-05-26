/* ============================================
   Sidebar — conversation list & management
   ============================================ */

import { useState, useEffect } from 'react';
import type { ConversationSummary, HealthStatus } from '../types';
import { t, getLang } from '../i18n';
import { healthCheck } from '../api';
import ContextMenu from './ContextMenu';
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
          <button className="theme-btn" onClick={onToggleTheme} title={theme === 'light' ? t('theme.dark') : t('theme.light')}>
            {theme === 'light' ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            )}
          </button>
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

      {/* Footer: Status + Collapse */}
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
        <button className="collapse-btn" onClick={onToggleCollapse} title={collapsed ? t('sidebar.expand') : t('sidebar.collapse')}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {collapsed ? (
              <polyline points="9 18 15 12 9 6" />
            ) : (
              <polyline points="15 18 9 12 15 6" />
            )}
          </svg>
        </button>
      </div>

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
