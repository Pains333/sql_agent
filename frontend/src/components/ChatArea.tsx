/* ============================================
   ChatArea — main chat interface with file upload
   ============================================ */

import { useState, useRef, useEffect } from 'react';
import type { Conversation, UploadResult } from '../types';
import { sendMessage, uploadFile, deleteUpload } from '../api';
import { t } from '../i18n';
import MessageBubble from './MessageBubble';
import './ChatArea.css';

interface ChatAreaProps {
  conversation: Conversation | null;
  onMessageSent: (convId: string) => void;
  onAutoCreate: (firstMessage: string) => Promise<string | null>;
}

const ACCEPTED_FORMATS = '.xlsx,.xls,.csv,.pkl,.parquet,.json';

export default function ChatArea({ conversation, onMessageSent, onAutoCreate }: ChatAreaProps) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [attachment, setAttachment] = useState<UploadResult | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [conversation?.id]);

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
    setLoading(true);
    const currentUploadId = attachment?.upload_id;
    try {
      let convId = conversation?.id ?? null;
      if (!convId) {
        convId = await onAutoCreate(text);
        if (!convId) { setLoading(false); return; }
      }
      await sendMessage(convId, text, currentUploadId);
      setAttachment(null);
      onMessageSent(convId);
    } catch (err) {
      console.error('Send failed:', err);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const hasMessages = conversation && conversation.messages.length > 0;

  return (
    <main className="chat-area">
      <div className="messages-container">
        <div className="messages-inner">
          {!hasMessages && (
            <div className="empty-state">
              <h2 className="empty-title">{t('chat.title')}</h2>
              <p className="empty-subtitle">{t('chat.subtitle')}</p>
              <div className="empty-examples">
                <div className="example-chip">{t('chat.example1')}</div>
                <div className="example-chip">{t('chat.example2')}</div>
                <div className="example-chip">{t('chat.example3')}</div>
              </div>
            </div>
          )}
          {conversation?.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {loading && (
            <div className="message-row assistant">
              <div className="avatar avatar-ai">🤖</div>
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
                <span className="attachment-error-icon">❌</span>
                <span>{uploadError}</span>
              </div>
            )}
            {attachment && !uploading && (
              <div className="attachment-tag">
                <span className="attachment-icon">📎</span>
                <span className="attachment-name">{attachment.filename}</span>
                <span className="attachment-meta">
                  {attachment.columns.length} {t('chat.columns')} · {attachment.row_count} {t('chat.rows')}
                </span>
                <button className="attachment-remove" onClick={handleRemoveAttachment} title={t('chat.removeAttachment')}>✕</button>
              </div>
            )}
          </div>
        )}

        <div className="input-wrapper">
          <input ref={fileInputRef} type="file" accept={ACCEPTED_FORMATS} onChange={handleFileSelect} style={{ display: 'none' }} />
          <button
            className={`upload-btn ${attachment ? 'has-file' : ''}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || loading}
            title={t('chat.uploadTitle')}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={attachment ? t('chat.placeholderWithFile') : t('chat.placeholder')}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button className={`send-btn ${input.trim() && !loading ? 'active' : ''}`} onClick={handleSend} disabled={!input.trim() || loading}>
            {loading ? (
              <div className="send-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 2L11 13" />
                <path d="M22 2L15 22L11 13L2 9L22 2Z" />
              </svg>
            )}
          </button>
        </div>
        <div className="input-hint">{t('chat.inputHint')}</div>
      </div>
    </main>
  );
}
