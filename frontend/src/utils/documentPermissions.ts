// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Mirrors the backend's can_write rule (app/services/document_service.py)
// so the UI can hide actions the API would reject anyway. The API is still
// the source of truth/enforcement — this is only for a cleaner UI.

import type { Document, User } from '../types'

export function canWriteDocument(user: User, doc: Document): boolean {
  if (doc.owner_id === user.id) return true
  return doc.visibility === 'department' && user.role === 'admin'
}
