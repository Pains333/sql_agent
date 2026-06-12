
import { useState, useEffect, useCallback, useRef } from 'react';
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
import DictionaryPanel from './components/DictionaryPanel';
import LineagePanel from './components/LineagePanel';
import './App.css';

export default function App() {
  const [setupDone, setSetupDone] = useState<boolean | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDictionaryOpen, setIsDictionaryOpen] = useState(false);
  const [isLineageOpen, setIsLineageOpen] = useState(false);

  // Keep a ref to the latest activeId to avoid jumping back
  // to an old conversation when a background stream finishes.
  const activeIdRef = useRef<string | null>(null);
  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

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
      
      // @ts-ignore
      if (!document.startViewTransition) {
        setActiveConv(conv);
        setActiveId(id);
        return;
      }
      
      // @ts-ignore
      document.startViewTransition(() => {
        setActiveConv(conv);
        setActiveId(id);
      });
    } catch (err) {
      console.error('获取对话详情失败:', err);
    }
  }, []);

  async function _createAndActivate(): Promise<string | null> {
    try {
      const conv = await createConversation('新对话');
      await refreshList();
      
      // @ts-ignore
      if (!document.startViewTransition) {
        setActiveId(conv.id);
        setActiveConv({ ...conv, messages: [] });
        return conv.id;
      }
      
      // @ts-ignore
      document.startViewTransition(() => {
        setActiveId(conv.id);
        setActiveConv({ ...conv, messages: [] });
      });
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
    if (activeIdRef.current === convId) {
      await loadConversation(convId);
    }
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
        onOpenDictionary={() => {
          setIsDictionaryOpen(prev => {
            if (!prev) setIsLineageOpen(false);
            return !prev;
          });
        }}
        onOpenLineage={() => {
          setIsLineageOpen(prev => {
            if (!prev) setIsDictionaryOpen(false);
            return !prev;
          });
        }}
      />
      <ChatArea
        key={activeConv?.id || 'new'}
        conversation={activeConv}
        onMessageSent={handleMessageSent}
        onAutoCreate={handleAutoCreate}
        sidebarCollapsed={!sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        lang={lang}
      />
      <DictionaryPanel isOpen={isDictionaryOpen} onClose={() => setIsDictionaryOpen(false)} />
      <LineagePanel isOpen={isLineageOpen} onClose={() => setIsLineageOpen(false)} />
    </div>
  );
}
