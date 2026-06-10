import type { Conversation, ConversationSummary, Message, OllamaModel, SetupConfig, SetupResult, UploadResult, DatabaseInfo, HealthStatus, TableColumn, PaginatedResult, ERDiagramData } from './types';

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


export async function listConversations(dbName?: string): Promise<ConversationSummary[]> {
  const url = dbName ? `/conversations?db_name=${encodeURIComponent(dbName)}` : '/conversations';
  return request<ConversationSummary[]>(url);
}

export async function createConversation(title = '新对话', dbName?: string): Promise<Conversation> {
  return request<Conversation>('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title, database: dbName }),
  });
}

export async function getConversation(id: string): Promise<Conversation> {
  return request<Conversation>(`/conversations/${id}`);
}

export async function deleteConversation(id: string): Promise<void> {
  await request(`/conversations/${id}`, { method: 'DELETE' });
}


export async function sendMessage(convId: string, content: string, uploadId?: string, language: string = 'zh'): Promise<Message> {
  return request<Message>(`/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, upload_id: uploadId, language }),
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
  language: string = 'zh',
): AbortController {
  const controller = new AbortController();

  fetch(`${BASE}/conversations/${convId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, upload_id: uploadId, language }),
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

export async function getErDiagram(db: string): Promise<ERDiagramData> {
  return request<ERDiagramData>(`/databases/${encodeURIComponent(db)}/er-diagram`);
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

export async function explainQuery(sql: string, database?: string): Promise<{ columns: string[]; rows: any[][] }> {
  return request<{ columns: string[]; rows: any[][] }>('/query/explain', {
    method: 'POST',
    body: JSON.stringify({ sql, database }),
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
export async function previewTable(db: string, table: string): Promise<{ database: string; table: string; columns: string[]; rows: any[][] }> {
  const res = await fetch(`${BASE}/databases/${db}/tables/${table}/preview`);
  if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
  return res.json();
}

// Dictionary APIs
export async function listDictionary(): Promise<{ entries: any[] }> {
  return request<{ entries: any[] }>('/dictionary');
}

export async function addDictionary(data: { term: string; definition: string; sql_hint?: string; field_mappings?: Record<string, string> }): Promise<{ success: boolean; entry: any }> {
  return request<{ success: boolean; entry: any }>('/dictionary', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateDictionary(id: string, data: { term?: string; definition?: string; sql_hint?: string; field_mappings?: Record<string, string> }): Promise<{ success: boolean; entry: any }> {
  return request<{ success: boolean; entry: any }>(`/dictionary/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteDictionary(id: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/dictionary/${id}`, { method: 'DELETE' });
}

// Lineage APIs
import { LineageEntry } from './types';

export async function listLineage(): Promise<LineageEntry[]> {
  return request<LineageEntry[]>('/lineage');
}

export async function addLineage(data: { source_table: string; source_column: string; target_table: string; target_column: string; transform_logic: string }): Promise<{ success: boolean; data: LineageEntry }> {
  return request<{ success: boolean; data: LineageEntry }>('/lineage', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateLineage(id: string, data: { source_table: string; source_column: string; target_table: string; target_column: string; transform_logic: string }): Promise<{ success: boolean; data: LineageEntry }> {
  return request<{ success: boolean; data: LineageEntry }>(`/lineage/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteLineage(id: string): Promise<{ success: boolean }> {
  return request<{ success: boolean }>(`/lineage/${id}`, { method: 'DELETE' });
}

export async function startParseSqlLineage(sql: string): Promise<{ task_id: string }> {
  const res = await request<{ success: boolean; task_id: string }>('/lineage/parse', {
    method: 'POST',
    body: JSON.stringify({ sql }),
  });
  return res;
}

export async function getParseTaskStatus(taskId: string): Promise<{ status: string; data?: LineageEntry[]; error?: string }> {
  const res = await request<{ success: boolean; task: { status: string; data?: LineageEntry[]; error?: string } }>(`/lineage/task/${taskId}`);
  return res.task;
}
