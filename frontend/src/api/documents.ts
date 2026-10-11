// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import { apiDelete, apiGet, apiPatch, apiPost, apiUpload, download, requestPaged } from './client'
import type { DownloadedFile, Page } from './client'
import type {
  Document,
  DocumentDetail,
  DocumentPreviewChunk,
  DocumentVisibility,
  IngestionStatus,
} from '../types'

export interface ListDocumentsParams {
  visibility?: DocumentVisibility
  q?: string
  status?: IngestionStatus
  departmentId?: number
  limit?: number
  offset?: number
}

export function listDocuments(params?: ListDocumentsParams): Promise<Page<Document>> {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 20),
    offset: String(params?.offset ?? 0),
  })
  if (params?.visibility) query.set('visibility', params.visibility)
  if (params?.q) query.set('q', params.q)
  if (params?.status) query.set('status', params.status)
  if (params?.departmentId !== undefined) query.set('department_id', String(params.departmentId))
  return requestPaged<Document>(`/documents?${query.toString()}`)
}

export function getDocument(id: number): Promise<DocumentDetail> {
  return apiGet<DocumentDetail>(`/documents/${id}`)
}

export function getDocumentPreview(id: number): Promise<DocumentPreviewChunk[]> {
  return apiGet<DocumentPreviewChunk[]>(`/documents/${id}/preview`)
}

export interface UploadOptions {
  title?: string
  visibility?: DocumentVisibility
  departmentIds?: number[]
  documentId?: number
}

export function uploadDocument(file: File, options: UploadOptions): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  if (options.title) formData.append('title', options.title)
  if (options.visibility) formData.append('visibility', options.visibility)
  if (options.departmentIds?.length) {
    formData.append('department_ids', options.departmentIds.join(','))
  }
  if (options.documentId !== undefined) {
    formData.append('document_id', String(options.documentId))
  }
  return apiUpload<Document>('/documents', formData)
}

export function updateDocument(
  id: number,
  fields: { title?: string; department_ids?: number[] },
): Promise<DocumentDetail> {
  return apiPatch<DocumentDetail>(`/documents/${id}`, fields)
}

export function deleteDocument(id: number): Promise<void> {
  return apiDelete<void>(`/documents/${id}`)
}

export function bulkDeleteDocuments(documentIds: number[]): Promise<void> {
  return apiPost<void>('/documents/bulk-delete', { document_ids: documentIds })
}

export function downloadDocument(id: number, versionId?: number): Promise<DownloadedFile> {
  const query = versionId !== undefined ? `?version_id=${versionId}` : ''
  return download(`/documents/${id}/download${query}`)
}
