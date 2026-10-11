// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import { apiDelete, apiGet, apiPost, postStream } from './client'
import type { ChatMessage, ChatSession } from '../types'

// Same pagination note as listMessages below — no session pager built yet.
export function listSessions(): Promise<ChatSession[]> {
  return apiGet<ChatSession[]>('/chat/sessions?limit=200')
}

export function createSession(title?: string): Promise<ChatSession> {
  return apiPost<ChatSession>('/chat/sessions', { title: title ?? null })
}

export function deleteSession(id: number): Promise<void> {
  return apiDelete<void>(`/chat/sessions/${id}`)
}

// The backend now paginates this endpoint (Phase 7), default 50/page. There's
// no history pager built yet, so request the max page size (200) to avoid
// silently truncating longer conversations until one exists.
export function listMessages(sessionId: number): Promise<ChatMessage[]> {
  return apiGet<ChatMessage[]>(`/chat/sessions/${sessionId}/messages?limit=200`)
}

export function sendMessage(sessionId: number, content: string): Promise<Response> {
  return postStream(`/chat/sessions/${sessionId}/messages`, { content })
}
