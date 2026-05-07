/* ============================================
   API Client — wraps all backend REST calls
   ============================================ */

import type { Conversation, ConversationSummary, Message, OllamaModel, SetupConfig, SetupResult, UploadResult } from './types';

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

/* --- Setup --- */

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

/* --- Conversations --- */

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

/* --- Messages --- */

export async function sendMessage(convId: string, content: string, uploadId?: string): Promise<Message> {
  return request<Message>(`/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, upload_id: uploadId }),
  });
}

/* --- File Upload --- */

export async function uploadFile(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — browser sets it with boundary for multipart
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

/* --- Utilities --- */

export async function getSkill(): Promise<{ content: string }> {
  return request<{ content: string }>('/skill');
}
