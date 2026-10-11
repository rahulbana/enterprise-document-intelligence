// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Shared API resource shapes, mirroring the backend's Pydantic schemas.

export type UserRole = 'admin' | 'user'

export interface User {
  id: number
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
  department_ids: number[]
}

export interface Department {
  id: number
  name: string
  description: string | null
  created_at: string
}

export type AuthEventType =
  | 'register'
  | 'login_success'
  | 'login_failure'
  | 'account_activated'
  | 'account_deactivated'

export interface AuthAuditLogEntry {
  id: number
  created_at: string
  event_type: AuthEventType
  email: string
  user_id: number | null
  detail: string | null
  prev_hash: string | null
  entry_hash: string
}

export interface AuditChainVerification {
  valid: boolean
  broken_at_id: number | null
  total_entries: number
}

export type DocumentVisibility = 'private' | 'department'
export type IngestionStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface DocumentVersion {
  id: number
  version_no: number
  original_filename: string
  file_type: string
  size_bytes: number
  is_active: boolean
  uploaded_by: number | null
  uploaded_at: string
  status: IngestionStatus
  status_message: string | null
  chunk_count: number
}

export interface Document {
  id: number
  title: string
  owner_id: number
  visibility: DocumentVisibility
  department_ids: number[]
  created_at: string
  active_version: DocumentVersion | null
  version_count: number
}

export interface DocumentDetail extends Document {
  versions: DocumentVersion[]
}

export interface DocumentPreviewChunk {
  chunk_index: number
  content: string
  metadata: Record<string, unknown>
}

export type ChatMessageRole = 'user' | 'assistant'

export type DocumentCitation = {
  source: 'document'
  document_id: number
  document_title: string | null
  document_version_id: number
  chunk_index: number
}

export type MemoryCitation = {
  source: 'memory'
  session_id: number
}

export type WebCitation = {
  source: 'web'
  url: string
  title: string
}

export type Citation = DocumentCitation | MemoryCitation | WebCitation

export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  role: ChatMessageRole
  content: string
  citations: Citation[] | null
  duration_ms: number | null
  tools_used: string[] | null
  created_at: string
}
