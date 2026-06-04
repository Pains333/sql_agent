
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sql?: string;
  action?: string;
  result?: string;
  error?: string;
  status?: 'pending' | 'executed' | 'cancelled';
  plan?: {
    action: string;
    sql: string;
    explanation: string;
    target_db?: string;
    upload_id?: string;
    target_table?: string;
    filename?: string;
  };
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface DatabaseInfo {
  databases: string[];
  current: string;
}

export interface SetupConfig {
  language: string;
  model_type: 'local' | 'api';
  model_name: string;
  api_base_url: string;
  api_key: string;
  api_model: string;
  db_type: 'postgresql' | 'mysql' | 'oracle';
  db_host: string;
  db_port: number;
  db_user: string;
  db_password: string;
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
}

export interface SetupResult {
  success: boolean;
  message: string;
  current_db: string;
  skill_summary: string;
}

export interface UploadResult {
  upload_id: string;
  filename: string;
  columns: string[];
  row_count: number;
  preview: Record<string, unknown>[];
}

export interface HealthStatus {
  db_connected: boolean;
  llm_connected: boolean;
  current_db: string;
}

export interface TableColumn {
  name: string;
  type: string;
  constraints: string;
}

export interface PaginatedResult {
  columns: string[];
  rows: unknown[][];
  total: number;
  page: number;
  page_size: number;
}

export interface ERDiagramData {
  database: string;
  tables: {
    name: string;
    columns: TableColumn[];
  }[];
  relationships: {
    source_table: string;
    source_column: string;
    target_table: string;
    target_column: string;
  }[];
}
