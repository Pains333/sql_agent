
import { useState } from 'react';
import type { Message } from '../types';
import { paginateQuery } from '../api';
import { t } from '../i18n';
import { User, Bot, AlertTriangle, Check, Copy, Download, XCircle } from 'lucide-react';
import './MessageBubble.css';

interface MessageBubbleProps {
  message: Message;
  onExecute?: (messageId: string, sql: string, action: string, plan?: Record<string, unknown>) => void;
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

const DDL_ACTIONS = new Set(['create_db', 'drop_db', 'create_table', 'drop_table', 'alter_table', 'import_file']);
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
          <User size={16} color="white" />
        ) : (
          <Bot size={16} color="white" />
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
            <AlertTriangle size={14} />
            {DANGEROUS_ACTIONS.has(message.action) ? t('sql.dangerWarning') : message.action === 'import_file' ? t('sql.confirmImport') : t('sql.confirmDDL')}
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
                    <Check size={14} />
                  ) : (
                    <Copy size={14} />
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
                  onClick={() => onExecute?.(message.id, editedSql, message.action || 'other', message.plan)}
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
                {message.result!.includes('|') && (
                  <button className="export-btn" onClick={() => exportCSV(message.result!)}>
                    <Download size={12} />
                    {t('export.csv')}
                  </button>
                )}
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
              <XCircle size={14} />
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
