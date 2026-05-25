/* ============================================
   App — Root component with setup wizard
   ============================================ */

import { useState, useEffect, useCallback } from 'react';
import type { Conversation, ConversationSummary } from './types';
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  getSetupStatus,
  resetSetup,
} from './api';
import SetupWizard from './components/SetupWizard';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import './App.css';

export default function App() {
  const [setupDone, setSetupDone] = useState<boolean | null>(null); // null = loading
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);

  /* ---- Check setup status on mount (with retry) ---- */
  useEffect(() => {
    let cancelled = false;
    async function checkStatus() {
      const maxRetries = 3;
      for (let i = 0; i < maxRetries; i++) {
        try {
          const res = await getSetupStatus();
          if (!cancelled) setSetupDone(res.setup_done);
          return;
        } catch {
          // Backend might not be ready yet, wait and retry
          if (i < maxRetries - 1) {
            await new Promise((r) => setTimeout(r, 2000));
          }
        }
      }
      // All retries failed
      if (!cancelled) setSetupDone(false);
    }
    checkStatus();
    return () => { cancelled = true; };
  }, []);

  /* ---- Load conversation list ---- */
  const refreshList = useCallback(async () => {
    try {
      const list = await listConversations();
      setConversations(list);
    } catch (err) {
      console.error('获取对话列表失败:', err);
    }
  }, []);

  useEffect(() => {
    if (setupDone) {
      refreshList();
    }
  }, [setupDone, refreshList]);

  /* ---- Load active conversation ---- */
  const loadConversation = useCallback(async (id: string) => {
    try {
      const conv = await getConversation(id);
      setActiveConv(conv);
      setActiveId(id);
    } catch (err) {
      console.error('获取对话详情失败:', err);
    }
  }, []);

  /* ---- Create & activate a new conversation (shared logic) ---- */
  async function _createAndActivate(): Promise<string | null> {
    try {
      const conv = await createConversation();
      await refreshList();
      setActiveId(conv.id);
      setActiveConv({ ...conv, messages: [] });
      return conv.id;
    } catch (err) {
      console.error('创建对话失败:', err);
      return null;
    }
  }

  /* ---- Create new conversation ---- */
  async function handleNew() {
    await _createAndActivate();
  }

  /* ---- Select conversation ---- */
  function handleSelect(id: string) {
    loadConversation(id);
  }

  /* ---- Delete conversation ---- */
  async function handleDelete(id: string) {
    try {
      await deleteConversation(id);
      if (activeId === id) {
        setActiveId(null);
        setActiveConv(null);
      }
      await refreshList();
    } catch (err) {
      console.error('删除对话失败:', err);
    }
  }

  /* ---- Auto-create conversation when sending first message ---- */
  async function handleAutoCreate(_firstMessage: string): Promise<string | null> {
    return _createAndActivate();
  }

  /* ---- Message sent callback ---- */
  async function handleMessageSent(convId: string) {
    await loadConversation(convId);
    await refreshList();
  }

  /* ---- Setup complete ---- */
  function handleSetupComplete() {
    setSetupDone(true);
  }

  /* ---- Logout / Reconfigure ---- */
  async function handleLogout() {
    try {
      await resetSetup();
      // Reset all frontend state
      setSetupDone(false);
      setActiveId(null);
      setActiveConv(null);
      setConversations([]);
    } catch (err) {
      console.error('重置配置失败:', err);
    }
  }

  // Loading state
  if (setupDone === null) {
    return (
      <div className="app-loading">
        <div className="loading-spinner" />
      </div>
    );
  }

  // Setup wizard
  if (!setupDone) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  // Main app
  return (
    <div className="app-layout">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
        onLogout={handleLogout}
      />
      <ChatArea
        conversation={activeConv}
        onMessageSent={handleMessageSent}
        onAutoCreate={handleAutoCreate}
      />
    </div>
  );
}
