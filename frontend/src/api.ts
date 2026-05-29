
import type { Conversation, ConversationSummary, Message, OllamaModel, SetupConfig, SetupResult, UploadResult, DatabaseInfo, HealthStatus, TableColumn, PaginatedResult } from './types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}


export async function getSetupStatus(): Promise<{ setup_done: boolean }> {
  return request<{ setup_done: boolean }>('/setup/status');
}

export async function getOllamaModels(): Promise<{ models: OllamaModel[]; error?: string }> {
  return request<{ models: OllamaModel[]; error?: string }>('/ollama/models');
}

export async function submitSetup(config: SetupConfig): Promise<SetupResult> {
  return request<SetupResult>('/setup', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

export async function resetSetup(): Promise<void> {
  await request('/setup/reset', { method: 'POST' });
}


export async function listConversations(): Promise<ConversationSummary[]> {
  return request<ConversationSummary[]>('/conversations');
}

export async function createConversation(title = '新对话'): Promise<Conversation> {
  return request<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export async function getConversation(id: string): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}`);
}

export async function deleteConversation(id: string): Promise<void> {
  await request(`/conversations/${id}`, { method: 'DELETE' });
}


export async function sendMessage(convId: string, content: string, uploadId?: string): Promise<Message> {
  return request<Message>(`/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, upload_id: uploadId }),
  });
}


export async function executeSQL(
  convId: string,
  sql: string,
  action: string,
  messageId: string,
  targetDb?: string,
  uploadId?: string,
  targetTable?: string,
): Promise<Message> {
  return request<Message>(`/conversations/${convId}/execute`, {
    method: 'POST',
    body: JSON.stringify({
      sql,
      action,
      message_id: messageId,
      target_db: targetDb,
      upload_id: uploadId,
      target_table: targetTable,
    }),
  });
}

export async function cancelExecution(convId: string, messageId: string): Promise<void> {
  await request(`/conversations/${convId}/cancel/${messageId}`, { method: 'POST' });
}


export function sendMessageStream(
  convId: string,
  content: string,
  uploadId: string | undefined,
  callbacks: {
    onThinking: (token: string) => void;
    onPlan: (plan: Message) => void;
    onResult: (msg: Message) => void;
    onError: (err: string) => void;
    onDone: () => void;
  },
): AbortController {
  const controller = new AbortController();

  fetch(`${BASE}/conversations/${convId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, upload_id: uploadId }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        callbacks.onError(body.detail || `HTTP ${res.status}`);
        callbacks.onDone();
        return;
      }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ') && eventType) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventType === 'thinking') callbacks.onThinking(data.token || '');
              else if (eventType === 'plan') callbacks.onPlan(data);
              else if (eventType === 'result') callbacks.onResult(data);
              else if (eventType === 'error') callbacks.onError(data.message || 'Unknown error');
              else if (eventType === 'done') callbacks.onDone();
            } catch {
              /* skip malformed JSON */
            }
            eventType = '';
          } else if (line === '') {
            eventType = '';
          }
        }
      }
      callbacks.onDone();
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        callbacks.onError(err.message || 'Connection failed');
        callbacks.onDone();
      }
    });

  return controller;
}


export async function listDatabases(): Promise<DatabaseInfo> {
  return request<DatabaseInfo>('/databases');
}

export async function switchDatabase(database: string): Promise<{ success: boolean; message: string; current: string }> {
  return request('/databases/switch', {
    method: 'POST',
    body: JSON.stringify({ database }),
  });
}

export async function listTables(db: string): Promise<{ database: string; tables: string[] }> {
  return request(`/databases/${encodeURIComponent(db)}/tables`);
}

export async function describeTable(db: string, table: string): Promise<{ database: string; table: string; columns: TableColumn[] }> {
  return request(`/databases/${encodeURIComponent(db)}/tables/${encodeURIComponent(table)}`);
}


export async function healthCheck(): Promise<HealthStatus> {
  return request<HealthStatus>('/health');
}


export async function paginateQuery(sql: string, page: number, pageSize: number): Promise<PaginatedResult> {
  return request<PaginatedResult>('/query/paginate', {
    method: 'POST',
    body: JSON.stringify({ sql, page, page_size: pageSize }),
  });
}


export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function deleteUpload(uploadId: string): Promise<void> {
  await request(`/upload/${uploadId}`, { method: 'DELETE' });
}


export async function getSkill(): Promise<{ content: string }> {
  return request<{ content: string }>('/skill');
}
