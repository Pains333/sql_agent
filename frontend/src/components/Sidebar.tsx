/* ============================================
   Sidebar — conversation list & management
   ============================================ */

import { useState } from 'react';
import type { ConversationSummary } from '../types';
import { t, getLang } from '../i18n';
import ContextMenu from './ContextMenu';
import './Sidebar.css';

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onLogout,
}: SidebarProps) {
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    convId: string;
  } | null>(null);

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
    <aside className="sidebar">
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
            <div className="conv-icon">💬</div>
            <div className="conv-info">
              <div className="conv-title">{c.title}</div>
              <div className="conv-meta">{formatTime(c.updated_at)}</div>
            </div>
          </div>
        ))}
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
