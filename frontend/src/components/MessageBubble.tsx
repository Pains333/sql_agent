/* ============================================
   MessageBubble — single chat message
   ============================================ */

import type { Message } from '../types';
import './MessageBubble.css';

interface MessageBubbleProps {
  message: Message;
}

/** Map action types to human-readable labels */
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

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      {/* Avatar */}
      <div className={`avatar ${isUser ? 'avatar-user' : 'avatar-ai'}`}>
        {isUser ? '👤' : '🤖'}
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

        {/* SQL block */}
        {message.sql && (
          <div className="sql-block">
            <div className="sql-header">
              <span>SQL</span>
              <button
                className="copy-btn"
                onClick={() => navigator.clipboard.writeText(message.sql!)}
                title="复制 SQL"
              >
                📋
              </button>
            </div>
            <pre className="sql-code">{message.sql}</pre>
          </div>
        )}

        {/* Query result table */}
        {message.result && (
          <div className="result-block">
            <div className="result-header">📊 执行结果</div>
            <div className="result-content">
              {message.result.includes('|') ? (
                <ResultTable markdown={message.result} />
              ) : (
                <span className="result-text">{message.result}</span>
              )}
            </div>
          </div>
        )}

        {/* Error */}
        {message.error && (
          <div className="error-block">
            <span className="error-icon">❌</span>
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

/* ---- Markdown table renderer ---- */

function ResultTable({ markdown }: { markdown: string }) {
  const lines = markdown.trim().split('\n').filter((l) => l.trim());
  if (lines.length < 2) return <span className="result-text">{markdown}</span>;

  const parseRow = (line: string) =>
    line
      .split('|')
      .map((c) => c.trim())
      .filter(Boolean);

  const headers = parseRow(lines[0]);
  // skip separator line (lines[1])
  const rows = lines.slice(2).filter((l) => !l.startsWith('_')).map(parseRow);
  // footer (record count etc.)
  const footer = lines.find((l) => l.startsWith('_'));

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
      {footer && <div className="result-footer">{footer.replace(/_/g, '').trim()}</div>}
    </>
  );
}
