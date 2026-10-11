// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// "My Documents": everything the current user can read — their own private
// uploads plus department documents from departments they belong to.
// Uploading here always creates a private document; department-visibility
// uploads happen on the admin Department Documents page.

import { Download, Eye, MoreVertical, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, Badge, Button, Card, Dropdown, Form, Table } from 'react-bootstrap'
import { toast } from 'sonner'

import { ApiError } from '../../api/client'
import * as documentsApi from '../../api/documents'
import { useAuth } from '../../auth/useAuth'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { BulkActionBar } from '../../components/BulkActionBar'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { DocumentPreviewDialog } from '../../components/DocumentPreviewDialog'
import { DocumentVersionsDialog } from '../../components/DocumentVersionsDialog'
import { FileDropZone } from '../../components/FileDropZone'
import { IngestionStatusBadge } from '../../components/IngestionStatusBadge'
import { LoadingBar } from '../../components/LoadingBar'
import { PageSizeSelect } from '../../components/PageSizeSelect'
import { TablePager } from '../../components/TablePager'
import { Checkbox } from '../../components/Checkbox'
import { SearchInput } from '../../components/SearchInput'
import type { Document, DocumentVisibility, IngestionStatus } from '../../types'
import { ACCEPTED_DOCUMENT_EXTENSIONS } from '../../utils/acceptedFileTypes'
import { canWriteDocument } from '../../utils/documentPermissions'
import { formatBytes } from '../../utils/formatBytes'
import { triggerFileDownload } from '../../utils/triggerFileDownload'

export function MyDocumentsPage() {
  const { user } = useAuth()
  const [documents, setDocuments] = useState<Document[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [addingVersionFor, setAddingVersionFor] = useState<number | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Document | null>(null)
  const [versionsFor, setVersionsFor] = useState<number | null>(null)
  const [previewDocId, setPreviewDocId] = useState<number | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [isBulkDeleteConfirmOpen, setIsBulkDeleteConfirmOpen] = useState(false)
  const [isBulkDeleting, setIsBulkDeleting] = useState(false)
  // "New version" lives in the row's dropdown menu, but the file input it
  // triggers is rendered outside the menu (so it isn't unmounted when the
  // menu closes) — keyed by document id since each row needs its own.
  const versionInputRefs = useRef<Record<number, HTMLInputElement | null>>({})

  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput)
  const [visibilityFilter, setVisibilityFilter] = useState<DocumentVisibility | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<IngestionStatus | 'all'>('all')

  function loadDocuments(options?: { background?: boolean }) {
    if (!options?.background) setIsLoading(true)
    documentsApi
      .listDocuments({
        visibility: visibilityFilter === 'all' ? undefined : visibilityFilter,
        q: search || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit: pageSize,
        offset,
      })
      .then(({ items, total }) => {
        setDocuments(items)
        setTotal(total)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load documents.'))
      .finally(() => {
        if (!options?.background) setIsLoading(false)
      })
  }

  useEffect(() => loadDocuments(), [offset, pageSize, search, visibilityFilter, statusFilter])
  useEffect(() => setOffset(0), [pageSize, search, visibilityFilter, statusFilter])
  // Only cleared when the page/filters change the row set, not on every
  // `documents` update (a single-row action replaces that array too and
  // would otherwise wipe an unrelated in-progress bulk selection).
  useEffect(
    () => setSelectedIds(new Set()),
    [offset, pageSize, search, visibilityFilter, statusFilter],
  )

  // Ingestion runs in the background (Celery); poll while anything is still
  // pending/processing so the status column updates without a manual reload.
  // Background polls skip the loading flag so the table doesn't flash empty
  // every 3s — this also means a document stuck PENDING forever (e.g. Celery
  // disabled) polls quietly instead of flickering the page.
  useEffect(() => {
    const hasInFlight = documents.some(
      (doc) => doc.active_version && ['pending', 'processing'].includes(doc.active_version.status),
    )
    if (!hasInFlight) return
    const timeoutId = setTimeout(() => loadDocuments({ background: true }), 3000)
    return () => clearTimeout(timeoutId)
  }, [documents])

  async function handleUpload(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setError(null)
    setIsUploading(true)
    try {
      await documentsApi.uploadDocument(file, { title, visibility: 'private' })
      setTitle('')
      setFile(null)
      loadDocuments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed.')
    } finally {
      setIsUploading(false)
    }
  }

  async function handleAddVersion(doc: Document, newFile: File) {
    setError(null)
    setAddingVersionFor(doc.id)
    try {
      await documentsApi.uploadDocument(newFile, { documentId: doc.id })
      loadDocuments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to upload new version.')
    } finally {
      setAddingVersionFor(null)
    }
  }

  async function handleDownload(doc: Document) {
    setError(null)
    try {
      const { blob, filename } = await documentsApi.downloadDocument(doc.id)
      triggerFileDownload(blob, filename)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Download failed.')
    }
  }

  async function handleDelete(doc: Document) {
    setError(null)
    try {
      await documentsApi.deleteDocument(doc.id)
      setPendingDelete(null)
      // Deleting the last row on a page (that isn't page 1) would otherwise
      // leave the pager stuck on a now-empty page.
      if (documents.length === 1 && offset > 0) {
        setOffset(Math.max(0, offset - pageSize))
      } else {
        loadDocuments()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Delete failed.')
    }
  }

  function toggleSelected(documentId: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(documentId)
      else next.delete(documentId)
      return next
    })
  }

  async function handleBulkDelete() {
    setError(null)
    setIsBulkDeleting(true)
    const count = selectedIds.size
    try {
      await documentsApi.bulkDeleteDocuments([...selectedIds])
      toast.success(`${count} document${count === 1 ? '' : 's'} deleted`)
      setIsBulkDeleteConfirmOpen(false)
      setSelectedIds(new Set())
      if (count === documents.length && offset > 0) {
        setOffset(Math.max(0, offset - pageSize))
      } else {
        loadDocuments()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk delete failed.')
    } finally {
      setIsBulkDeleting(false)
    }
  }

  if (!user) return null

  const writableDocumentIds = documents.filter((doc) => canWriteDocument(user, doc)).map((d) => d.id)

  return (
    <main className="app-page d-flex flex-column gap-4">
      <div>
        <h1 className="h3 text-primary mb-1">My Documents</h1>
        <p className="text-body-secondary mb-0">
          Your own uploads, plus documents shared with departments you belong to.
        </p>
      </div>

      <Card className="shadow-sm">
        <Card.Header className="bg-white fw-medium">Upload a document</Card.Header>
        <Card.Body>
          <Form onSubmit={handleUpload} className="d-flex flex-column gap-3">
            <Form.Group controlId="upload-title">
              <Form.Label>Title</Form.Label>
              <Form.Control
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Q3 Vacation Policy"
              />
            </Form.Group>
            <div>
              <Form.Label>File</Form.Label>
              <FileDropZone
                accept={ACCEPTED_DOCUMENT_EXTENSIONS}
                file={file}
                onFileSelected={setFile}
                disabled={isUploading}
                helperText="or drag and drop — documents, presentations, spreadsheets, images, email (40+ formats)"
              />
            </div>
            <Button
              type="submit"
              disabled={isUploading || !file}
              className="align-self-start d-inline-flex align-items-center gap-2"
            >
              <Upload size={16} />
              {isUploading ? 'Uploading…' : 'Upload'}
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {error && (
        <Alert variant="danger" className="py-2 small mb-0">
          {error}
        </Alert>
      )}

      <BulkActionBar selectedCount={selectedIds.size} onClear={() => setSelectedIds(new Set())}>
        <Button
          variant="outline-danger"
          size="sm"
          disabled={isBulkDeleting}
          onClick={() => setIsBulkDeleteConfirmOpen(true)}
          className="d-inline-flex align-items-center gap-1"
        >
          <Trash2 size={14} />
          Delete
        </Button>
      </BulkActionBar>

      <div className="d-flex flex-wrap align-items-center gap-2">
        <PageSizeSelect value={pageSize} onChange={setPageSize} />
        <SearchInput value={searchInput} onChange={setSearchInput} placeholder="Search by title…" />
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={visibilityFilter}
          aria-label="Visibility filter"
          onChange={(e) => setVisibilityFilter(e.target.value as DocumentVisibility | 'all')}
        >
          <option value="all">All visibilities</option>
          <option value="private">Private</option>
          <option value="department">Department</option>
        </Form.Select>
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={statusFilter}
          aria-label="Status filter"
          onChange={(e) => setStatusFilter(e.target.value as IngestionStatus | 'all')}
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="processing">Processing</option>
          <option value="ready">Ready</option>
          <option value="failed">Failed</option>
        </Form.Select>
      </div>

      {isLoading ? (
        <LoadingBar label="Loading documents…" />
      ) : (
        <Card className="shadow-sm">
          <Table hover responsive className="align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th style={{ width: 40 }}>
                  <Checkbox
                    checked={
                      writableDocumentIds.length > 0 &&
                      writableDocumentIds.every((id) => selectedIds.has(id))
                        ? true
                        : selectedIds.size > 0
                          ? 'indeterminate'
                          : false
                    }
                    disabled={writableDocumentIds.length === 0}
                    onCheckedChange={(checked) =>
                      setSelectedIds(checked ? new Set(writableDocumentIds) : new Set())
                    }
                    aria-label="Select all"
                  />
                </th>
                <th>Title</th>
                <th>Visibility</th>
                <th>File</th>
                <th>Size</th>
                <th>Version</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const writable = canWriteDocument(user, doc)
                return (
                  <tr key={doc.id}>
                    <td>
                      <Checkbox
                        checked={selectedIds.has(doc.id)}
                        disabled={!writable}
                        onCheckedChange={(checked) => toggleSelected(doc.id, checked === true)}
                        aria-label={`Select ${doc.title}`}
                        title={writable ? undefined : "You don't have permission to delete this document"}
                      />
                    </td>
                    <td className="fw-medium">{doc.title}</td>
                    <td>
                      <Badge bg={doc.visibility === 'private' ? 'secondary' : 'info'} text={doc.visibility === 'private' ? 'dark' : undefined} className={doc.visibility === 'private' ? 'border' : ''}>
                        {doc.visibility}
                      </Badge>
                    </td>
                    <td className="text-body-secondary">
                      {doc.active_version?.original_filename ?? '—'}
                    </td>
                    <td className="text-body-secondary">
                      {doc.active_version ? formatBytes(doc.active_version.size_bytes) : '—'}
                    </td>
                    <td className="text-body-secondary">
                      {doc.version_count > 1 ? (
                        <button
                          type="button"
                          onClick={() => setVersionsFor(doc.id)}
                          className="btn btn-link btn-sm p-0"
                        >
                          v{doc.active_version?.version_no ?? 0} ({doc.version_count} total)
                        </button>
                      ) : (
                        <span>v{doc.active_version?.version_no ?? 0} ({doc.version_count} total)</span>
                      )}
                    </td>
                    <td>
                      {doc.active_version ? <IngestionStatusBadge version={doc.active_version} /> : '—'}
                    </td>
                    <td className="text-end">
                      <Dropdown align="end">
                        <Dropdown.Toggle
                          variant="link"
                          size="sm"
                          className="no-caret p-1 text-body-secondary"
                          aria-label="Actions"
                        >
                          <MoreVertical size={16} />
                        </Dropdown.Toggle>
                        <Dropdown.Menu popperConfig={{ strategy: 'fixed' }}>
                          <Dropdown.Item
                            onClick={() => setPreviewDocId(doc.id)}
                            className="d-flex align-items-center gap-2"
                          >
                            <Eye size={14} />
                            Preview
                          </Dropdown.Item>
                          <Dropdown.Item
                            onClick={() => handleDownload(doc)}
                            className="d-flex align-items-center gap-2"
                          >
                            <Download size={14} />
                            Download
                          </Dropdown.Item>
                          {writable && (
                            <>
                              <Dropdown.Item
                                disabled={addingVersionFor === doc.id}
                                onClick={() => versionInputRefs.current[doc.id]?.click()}
                                className="d-flex align-items-center gap-2"
                              >
                                <Upload size={14} />
                                {addingVersionFor === doc.id ? 'Uploading…' : 'New version'}
                              </Dropdown.Item>
                              <Dropdown.Divider />
                              <Dropdown.Item
                                onClick={() => setPendingDelete(doc)}
                                className="d-flex align-items-center gap-2 text-danger"
                              >
                                <Trash2 size={14} />
                                Delete
                              </Dropdown.Item>
                            </>
                          )}
                        </Dropdown.Menu>
                      </Dropdown>
                      <input
                        ref={(el) => {
                          versionInputRefs.current[doc.id] = el
                        }}
                        type="file"
                        accept={ACCEPTED_DOCUMENT_EXTENSIONS}
                        className="d-none"
                        onChange={(e) => {
                          const newFile = e.target.files?.[0]
                          if (newFile) handleAddVersion(doc, newFile)
                          e.target.value = ''
                        }}
                      />
                    </td>
                  </tr>
                )
              })}
              {documents.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-4 text-center text-body-secondary">
                    {search || visibilityFilter !== 'all' || statusFilter !== 'all'
                      ? 'No documents match your filters.'
                      : 'No documents yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          <TablePager offset={offset} limit={pageSize} total={total} onOffsetChange={setOffset} />
        </Card>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Delete this document?"
        description={
          pendingDelete ? `"${pendingDelete.title}" will be permanently removed.` : ''
        }
        onConfirm={() => pendingDelete && handleDelete(pendingDelete)}
      />

      <ConfirmDialog
        open={isBulkDeleteConfirmOpen}
        onOpenChange={setIsBulkDeleteConfirmOpen}
        title={`Delete ${selectedIds.size} document${selectedIds.size === 1 ? '' : 's'}?`}
        description="These documents will be permanently removed. This can't be undone."
        onConfirm={handleBulkDelete}
      />

      <DocumentVersionsDialog
        documentId={versionsFor}
        onOpenChange={(open) => !open && setVersionsFor(null)}
      />

      <DocumentPreviewDialog
        documentId={previewDocId}
        onOpenChange={(open) => !open && setPreviewDocId(null)}
      />
    </main>
  )
}
