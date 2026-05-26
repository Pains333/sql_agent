/* ============================================
   MessageBubble — single chat message
   ============================================ */

import { useState } from 'react';
import type { Message } from '../types';
import { paginateQuery } from '../api';
import { t } from '../i18n';
import './MessageBubble.css';

interface MessageBubbleProps {
  message: Message;
  onExecute?: (messageId: string, sql: string, action: string) => void;
  onCancel?: (messageId: string) => void;
}

const ACTION_LABELS: Record<string, string> = {
  create_table: 'CREATE TABLE',
  drop_table: 'DROP TABLE',
  alter_table: 'ALTER TABLE',
  create_db: 'CREATE DATABASE',
  drop_db: 'DROP DATABASE',
  query: 'QUERY',
  insert: 'INSERT',
  update: 'UPDATE',
  delete: 'DELETE',
  import_file: 'IMPORT FILE',
  other: 'SQL',
  chat: '',
};

const DDL_ACTIONS = new Set(['create_db', 'drop_db', 'create_table', 'drop_table', 'alter_table']);
const DANGEROUS_ACTIONS = new Set(['drop_db', 'drop_table']);

export default function MessageBubble({ message, onExecute, onCancel }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isPending = message.status === 'pending';
  const isCancelled = message.status === 'cancelled';
  const [editedSql, setEditedSql] = useState(message.sql || '');
  const [copied, setCopied] = useState(false);

  function handleCopy(text: string) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      {/* Avatar */}
      <div className={`avatar ${isUser ? 'avatar-user' : 'avatar-ai'}`}>
        {isUser ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><rect x="3" y="11" width="18" height="10" rx="2" /><circle cx="12" cy="5" r="3" /><line x1="8" y1="16" x2="8" y2="16.01" /><line x1="16" y1="16" x2="16" y2="16.01" /></svg>
        )}
      </div>

      {/* Bubble */}
      <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}>
        {/* Action badge */}
        {!isUser && message.action && message.action !== 'chat' && (
          <span className="action-badge">
            {ACTION_LABELS[message.action] ?? message.action}
          </span>
        )}

        {/* Content */}
        <div className="bubble-content">{message.content}</div>

        {/* DDL Warning for pending */}
        {isPending && message.action && DDL_ACTIONS.has(message.action) && (
          <div className={`ddl-warning ${DANGEROUS_ACTIONS.has(message.action) ? 'danger' : ''}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            {DANGEROUS_ACTIONS.has(message.action) ? t('sql.dangerWarning') : t('sql.confirmDDL')}
          </div>
        )}

        {/* SQL block — editable when pending, readonly otherwise */}
        {message.sql && (
          <div className="sql-block">
            <div className="sql-header">
              <span>SQL</span>
              {!isPending && (
                <button
                  className="copy-btn"
                  onClick={() => handleCopy(message.sql!)}
                  title="Copy SQL"
                >
                  {copied ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
                  )}
                </button>
              )}
            </div>
            {isPending ? (
              <textarea
                className="sql-edit-area"
                value={editedSql}
                onChange={(e) => setEditedSql(e.target.value)}
                rows={Math.max(3, editedSql.split('\n').length)}
              />
            ) : (
              <pre className="sql-code">{message.sql}</pre>
            )}
            {isPending && (
              <div className="sql-actions">
                <button
                  className="sql-execute-btn"
                  onClick={() => onExecute?.(message.id, editedSql, message.action || 'other')}
                >
                  {t('sql.execute')}
                </button>
                <button
                  className="sql-cancel-btn"
                  onClick={() => onCancel?.(message.id)}
                >
                  {t('sql.cancel')}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Cancelled badge */}
        {isCancelled && (
          <span className="cancelled-badge">{t('sql.cancelled')}</span>
        )}

        {/* Query result table */}
        {message.result && (
          <div className="result-block">
            <div className="result-header">
              <span>{t('schema.title') === '数据库结构' ? '执行结果' : 'Result'}</span>
              <div className="result-header-actions">
                <button className="export-btn" onClick={() => exportCSV(message.result!)}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  {t('export.csv')}
                </button>
              </div>
            </div>
            <div className="result-content">
              {message.result.includes('|') ? (
                <ResultTable markdown={message.result} sql={message.sql} />
              ) : (
                <span className="result-text">{message.result}</span>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {message.error && (
          <div className="error-block">
            <span className="error-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
            </span>
            {message.error}
          </div>
        )}

        {/* Timestamp */}
        <div className="bubble-time">
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
}

/* ---- CSV Export ---- */
function exportCSV(markdown: string) {
  const lines = markdown.trim().split('\n').filter((l) => l.trim());
  if (lines.length < 2) return;
  const parseRow = (line: string) => line.split('|').map((c) => c.trim()).filter(Boolean);
  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).filter((l) => !l.startsWith('_')).map(parseRow);
  const csv = [headers, ...rows]
    .map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'query_result.csv';
  a.click();
  URL.revokeObjectURL(url);
}

/* ---- Markdown table renderer with pagination ---- */
function ResultTable({ markdown, sql }: { markdown: string; sql?: string }) {
  const [pageData, setPageData] = useState<{ columns: string[]; rows: string[][]; page: number; total: number } | null>(null);
  const PAGE_SIZE = 50;

  const lines = markdown.trim().split('\n').filter((l) => l.trim());
  if (lines.length < 2) return <span className="result-text">{markdown}</span>;

  const parseRow = (line: string) =>
    line.split('|').map((c) => c.trim()).filter(Boolean);

  const origHeaders = parseRow(lines[0]);
  const origRows = lines.slice(2).filter((l) => !l.startsWith('_')).map(parseRow);
  const footer = lines.find((l) => l.startsWith('_'));

  const headers = pageData ? pageData.columns : origHeaders;
  const rows = pageData ? pageData.rows : origRows;
  const showPagination = sql && (origRows.length >= PAGE_SIZE || (pageData && pageData.total > PAGE_SIZE));

  async function loadPage(page: number) {
    if (!sql) return;
    try {
      const result = await paginateQuery(sql, page, PAGE_SIZE);
      setPageData({
        columns: result.columns,
        rows: result.rows.map((r) => r.map(String)),
        page: result.page,
        total: result.total,
      });
    } catch (err) {
      console.error('Pagination failed:', err);
    }
  }

  const currentPage = pageData?.page || 1;
  const totalPages = pageData ? Math.ceil(pageData.total / PAGE_SIZE) : 1;

  return (
    <>
      <div className="result-table-wrapper">
        <table className="result-table">
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer && !pageData && <div className="result-footer">{footer.replace(/_/g, '').trim()}</div>}
      {showPagination && (
        <div className="pagination-controls">
          <button
            className="pagination-btn"
            disabled={currentPage <= 1}
            onClick={() => loadPage(currentPage - 1)}
          >
            {t('pagination.prev')}
          </button>
          <span className="pagination-info">
            {currentPage} / {totalPages}
          </span>
          <button
            className="pagination-btn"
            disabled={currentPage >= totalPages}
            onClick={() => loadPage(currentPage + 1)}
          >
            {t('pagination.next')}
          </button>
        </div>
      )}
    </>
  );
}
