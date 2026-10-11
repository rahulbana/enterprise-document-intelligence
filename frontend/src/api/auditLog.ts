// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import type { AuditChainVerification, AuthAuditLogEntry, AuthEventType } from '../types'
import type { Page } from './client'
import { apiGet, requestPaged } from './client'

export function listAuditLog(params?: {
  q?: string
  eventType?: AuthEventType
  limit?: number
  offset?: number
}): Promise<Page<AuthAuditLogEntry>> {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 20),
    offset: String(params?.offset ?? 0),
  })
  if (params?.q) query.set('q', params.q)
  if (params?.eventType) query.set('event_type', params.eventType)
  return requestPaged<AuthAuditLogEntry>(`/audit-log?${query.toString()}`)
}

export function verifyAuditLog(): Promise<AuditChainVerification> {
  return apiGet<AuditChainVerification>('/audit-log/verify')
}
