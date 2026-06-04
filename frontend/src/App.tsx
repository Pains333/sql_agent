
import { useState, useEffect, useCallback } from 'react';
import type { Conversation, ConversationSummary } from './types';
import { setLang, getLang } from './i18n';
import type { Lang } from './i18n';
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
  const [setupDone, setSetupDone] = useState<boolean | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  const [lang, setLangState] = useState<Lang>(() => {
    const saved = localStorage.getItem('lang');
    if (saved === 'zh' || saved === 'en') {
      setLang(saved);
      return saved;
    }
    return getLang();
  });



  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    setLang(lang);
    localStorage.setItem('lang', lang);
  }, [lang]);



  function toggleTheme() {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }

  function handleLangChange(newLang: Lang) {
    setLang(newLang);
    setLangState(newLang);
  }

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
          if (i < maxRetries - 1) {
            await new Promise((r) => setTimeout(r, 2000));
          }
        }
      }
      if (!cancelled) setSetupDone(false);
    }
    checkStatus();
    return () => { cancelled = true; };
  }, []);

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

  const loadConversation = useCallback(async (id: string) => {
    try {
      const conv = await getConversation(id);
      setActiveConv(conv);
      setActiveId(id);
    } catch (err) {
      console.error('获取对话详情失败:', err);
    }
  }, []);

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

  async function handleNew() {
    await _createAndActivate();
  }

  function handleSelect(id: string) {
    loadConversation(id);
    if (window.innerWidth <= 768) {
      setSidebarOpen(false);
    }
  }

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


  async function handleAutoCreate(_firstMessage: string): Promise<string | null> {
    return _createAndActivate();
  }

  async function handleMessageSent(convId: string) {
    await loadConversation(convId);
    await refreshList();
  }

  function handleSetupComplete() {
    setSetupDone(true);
  }

  async function handleLogout() {
    try {
      await resetSetup();
      setSetupDone(false);
      setActiveId(null);
      setActiveConv(null);
      setConversations([]);
    } catch (err) {
      console.error('重置配置失败:', err);
    }
  }

  if (setupDone === null) {
    return (
      <div className="app-loading">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!setupDone) {
    return <SetupWizard onComplete={handleSetupComplete} />;
  }

  return (
    <div className="app-layout" key={lang}>
      {sidebarOpen && window.innerWidth <= 768 && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
        onLogout={handleLogout}
        collapsed={!sidebarOpen}
        onToggleCollapse={() => setSidebarOpen(!sidebarOpen)}
        theme={theme}
        onToggleTheme={toggleTheme}
        lang={lang}
        onLangChange={handleLangChange}
      />
      <ChatArea
        conversation={activeConv}
        onMessageSent={handleMessageSent}
        onAutoCreate={handleAutoCreate}
        sidebarCollapsed={!sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        lang={lang}
      />
    </div>
  );
}
