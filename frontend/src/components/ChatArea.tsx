import { useState, useRef, useEffect, useCallback } from 'react';
import type { Conversation, Message, UploadResult, DatabaseInfo } from '../types';
import { sendMessage, sendMessageStream, uploadFile, deleteUpload, executeSQL, cancelExecution, listDatabases, switchDatabase } from '../api';
import { t } from '../i18n';
import { Menu, LayoutGrid, Bot, Paperclip, X, Send } from 'lucide-react';
import MessageBubble from './MessageBubble';
import SchemaDrawer from './SchemaDrawer';
import './ChatArea.css';

interface ChatAreaProps {
  conversation: Conversation | null;
  onMessageSent: (convId: string) => void;
  onAutoCreate: (firstMessage: string) => Promise<string | null>;
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  lang?: string;
}

const ACCEPTED_FORMATS = '.xlsx,.xls,.csv,.pkl,.parquet,.json';

const COMMANDS = [
  { name: '/tables', desc: 'cmd.tables' as const, message: t('cmd.tablesMsg' as any) },
  { name: '/databases', desc: 'cmd.databases' as const, message: t('cmd.databasesMsg' as any) },
  { name: '/describe', desc: 'cmd.describe' as const, message: t('cmd.describeMsg' as any) },
];

export default function ChatArea({ conversation, onMessageSent, onAutoCreate, sidebarCollapsed, onToggleSidebar, lang = 'zh' }: ChatAreaProps) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [attachment, setAttachment] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [streamingContent, setStreamingContent] = useState('');
  const [showCommands, setShowCommands] = useState(false);
  const [selectedCmd, setSelectedCmd] = useState(0);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages, streamingContent]);



  useEffect(() => {
    inputRef.current?.focus();
  }, [conversation?.id]);

  // Load database list
  const refreshDatabases = useCallback(async () => {
    try {
      const info = await listDatabases();
      setDbInfo(info);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    refreshDatabases();
  }, [refreshDatabases]);

  async function handleSwitchDb(db: string) {
    try {
      await switchDatabase(db);
      await refreshDatabases();
    } catch (err) {
      console.error('Switch DB failed:', err);
    }
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError('');
    try {
      const result = await uploadFile(file);
      setAttachment(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('error.connectionFailed');
      setUploadError(message);
      setTimeout(() => setUploadError(''), 5000);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleRemoveAttachment() {
    if (attachment) {
      try { await deleteUpload(attachment.upload_id); } catch { /* ignore */ }
      setAttachment(null);
    }
  }

  async function handleSend() {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput('');
    setShowCommands(false);
    setLoading(true);
    setStreamingContent('');
    const currentUploadId = attachment?.upload_id;

    try {
      let convId = conversation?.id ?? null;
      if (!convId) {
        convId = await onAutoCreate(text);
        if (!convId) { setLoading(false); return; }
      }

      // Optimistic UI: show user message immediately
      const optimisticMsg: Message = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
      };
      setPendingUserMessage(optimisticMsg);

      // Streaming mode
      try {
        await new Promise<void>((resolve, reject) => {
          abortRef.current = sendMessageStream(convId!, text, currentUploadId, {
            onThinking: (token) => {
              setStreamingContent((prev) => prev + token);
            },
            onPlan: (_plan) => {
              setStreamingContent('');
              setAttachment(null);
              setPendingUserMessage(null);
              onMessageSent(convId!);
              resolve();
            },
            onResult: (_msg) => {
              setStreamingContent('');
              setAttachment(null);
              setPendingUserMessage(null);
              onMessageSent(convId!);
              resolve();
            },
            onError: (err) => {
              reject(new Error(err));
            },
            onDone: () => {
              setStreamingContent('');
              setPendingUserMessage(null);
              onMessageSent(convId!);
              resolve();
            },
          }, lang);
        });
      } catch {
        // Fallback to non-streaming
        setStreamingContent('');
        await sendMessage(convId!, text, currentUploadId, lang);
        setAttachment(null);
        setPendingUserMessage(null);
        onMessageSent(convId!);
      }
    } catch (err) {
      console.error('Send failed:', err);
    } finally {
      setLoading(false);
      setStreamingContent('');
      setPendingUserMessage(null);
      abortRef.current = null;
    }
  }

  async function handleExecute(messageId: string, sql: string, action: string, plan?: Record<string, unknown>) {
    if (!conversation) return;
    try {
      const uploadId = plan?.upload_id as string | undefined;
      const targetTable = plan?.target_table as string | undefined;
      const targetDb = plan?.target_db as string | undefined;
      await executeSQL(conversation.id, sql, action, messageId, targetDb, uploadId, targetTable);
      onMessageSent(conversation.id);
    } catch (err) {
      console.error('Execute failed:', err);
    }
  }

  async function handleCancel(messageId: string) {
    if (!conversation) return;
    try {
      await cancelExecution(conversation.id, messageId);
      onMessageSent(conversation.id);
    } catch (err) {
      console.error('Cancel failed:', err);
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setInput(val);
    if (val === '/') {
      setShowCommands(true);
      setSelectedCmd(0);
    } else if (val.startsWith('/') && val.length > 1) {
      setShowCommands(true);
    } else {
      setShowCommands(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (showCommands) {
      const filtered = COMMANDS.filter((c) => c.name.startsWith(input));
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedCmd((prev) => Math.min(prev + 1, filtered.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedCmd((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter' && !e.shiftKey && filtered.length > 0) {
        e.preventDefault();
        setInput(filtered[selectedCmd].message);
        setShowCommands(false);
        return;
      }
      if (e.key === 'Escape') {
        setShowCommands(false);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleExampleClick(text: string) {
    setInput(text);
    inputRef.current?.focus();
  }

  const hasMessages = conversation && conversation.messages.length > 0;
  const filteredCommands = COMMANDS.filter((c) => c.name.startsWith(input));

  return (
    <main className="chat-area">
      {/* Header with hamburger, DB switcher, schema toggle */}
      <div className="chat-header">
        <button
          className={`hamburger-btn ${sidebarCollapsed ? 'visible' : ''}`}
          onClick={onToggleSidebar}
        >
          <Menu size={18} />
        </button>

        {/* Database Switcher */}
        {dbInfo && (
          <select
            className="db-switcher"
            value={dbInfo.current}
            onChange={(e) => handleSwitchDb(e.target.value)}
            title={t('db.switch')}
            style={{
              padding: '5px 28px 5px 10px',
              border: '1px solid var(--border)',
              borderRadius: 8,
              background: 'var(--bg-surface)',
              color: 'var(--text-secondary)',
              fontSize: 13,
              fontFamily: "'Inter', sans-serif",
              cursor: 'pointer',
              outline: 'none',
              appearance: 'none' as const,
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpath fill='%239ca3af' d='M5 7L1 3h8z'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 8px center',
            }}
          >
            {dbInfo.databases.map((db) => (
              <option key={db} value={db}>{db}</option>
            ))}
          </select>
        )}

        <div className="chat-header-spacer" />

        <button
          className={`schema-toggle-btn ${schemaOpen ? 'active' : ''}`}
          onClick={() => setSchemaOpen(!schemaOpen)}
        >
          <LayoutGrid size={14} />
          {t('schema.title')}
        </button>
      </div>

      {/* Main content area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="messages-container">
            <div className="messages-inner">
              {!hasMessages && !streamingContent && !pendingUserMessage && (
                <div className="empty-state">
                  <h2 className="empty-title">{t('chat.title')}</h2>
                  <p className="empty-subtitle">{t('chat.subtitle')}</p>
                  <div className="empty-examples">
                    <div className="example-chip" onClick={() => handleExampleClick(t('chat.example1'))}>{t('chat.example1')}</div>
                    <div className="example-chip" onClick={() => handleExampleClick(t('chat.example2'))}>{t('chat.example2')}</div>
                    <div className="example-chip" onClick={() => handleExampleClick(t('chat.example3'))}>{t('chat.example3')}</div>
                  </div>
                </div>
              )}
              {conversation?.messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onExecute={handleExecute}
                  onCancel={handleCancel}
                />
              ))}
              {/* Optimistic user message (shown before server confirms) */}
              {pendingUserMessage && (
                <MessageBubble
                  key={pendingUserMessage.id}
                  message={pendingUserMessage}
                />
              )}
              {streamingContent && (
                <div className="message-row assistant">
                  <div className="avatar avatar-ai">
                    <Bot size={16} color="white" />
                  </div>
                  <div className="bubble bubble-ai">
                    <div className="streaming-content">
                      {streamingContent}
                      <span className="streaming-cursor" />
                    </div>
                  </div>
                </div>
              )}
              {loading && !streamingContent && (
                <div className="message-row assistant">
                  <div className="avatar avatar-ai">
                    <Bot size={16} color="white" />
                  </div>
                  <div className="bubble bubble-ai">
                    <div className="typing-indicator">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="input-container">
            {(attachment || uploading || uploadError) && (
              <div className="attachment-bar">
                {uploading && (
                  <div className="attachment-tag uploading">
                    <div className="attachment-spinner" />
                    <span>{t('chat.uploading')}</span>
                  </div>
                )}
                {uploadError && (
                  <div className="attachment-tag error">
                    <span className="attachment-error-icon">!</span>
                    <span>{uploadError}</span>
                  </div>
                )}
                {attachment && !uploading && (
                  <div className="attachment-tag">
                    <span className="attachment-icon">
                      <Paperclip size={14} />
                    </span>
                    <span className="attachment-name">{attachment.filename}</span>
                    <span className="attachment-meta">
                      {attachment.columns.length} {t('chat.columns')} · {attachment.row_count} {t('chat.rows')}
                    </span>
                    <button className="attachment-remove" onClick={handleRemoveAttachment} title={t('chat.removeAttachment')}>
                      <X size={10} strokeWidth={3} />
                    </button>
                  </div>
                )}
              </div>
            )}

            <div className="input-wrapper" style={{ position: 'relative' }}>
              {/* Command Palette */}
              {showCommands && filteredCommands.length > 0 && (
                <div className="command-palette">
                  {filteredCommands.map((cmd, i) => (
                    <button
                      key={cmd.name}
                      className={`command-item ${i === selectedCmd ? 'selected' : ''}`}
                      onClick={() => {
                        setInput(cmd.message);
                        setShowCommands(false);
                        inputRef.current?.focus();
                      }}
                    >
                      <span className="command-name">{cmd.name}</span>
                      <span className="command-desc">{t(cmd.desc)}</span>
                    </button>
                  ))}
                </div>
              )}

              <input ref={fileInputRef} type="file" accept={ACCEPTED_FORMATS} onChange={handleFileSelect} style={{ display: 'none' }} />
              <button
                className={`upload-btn ${attachment ? 'has-file' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || loading}
                title={t('chat.uploadTitle')}
              >
                <Paperclip size={20} />
              </button>
              <textarea
                ref={inputRef}
                className="chat-input"
                placeholder={attachment ? t('chat.placeholderWithFile') : t('chat.placeholder')}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                rows={1}
                disabled={loading}
              />
              <button className={`send-btn ${input.trim() && !loading ? 'active' : ''}`} onClick={handleSend} disabled={!input.trim() || loading}>
                {loading ? (
                  <div className="send-spinner" />
                ) : (
                  <Send size={20} />
                )}
              </button>
            </div>
            <div className="input-hint">{t('chat.inputHint')}</div>
          </div>
        </div>

        {/* Schema Drawer */}
        {schemaOpen && dbInfo && (
          <SchemaDrawer currentDb={dbInfo.current} onClose={() => setSchemaOpen(false)} />
        )}
      </div>
    </main>
  );
}
