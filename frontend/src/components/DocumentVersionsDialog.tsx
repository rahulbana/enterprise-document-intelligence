// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Version history for one document: every past upload stays on the server
// (only is_active flips on a new upload — see DocumentVersion model) but
// nothing in the UI surfaced them, so re-uploading looked like it silently
// discarded v1. Lists every version with a per-version download, backed by
// the download endpoint's existing (already-implemented) version_id param.

import { Download } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Button, Modal, Table } from 'react-bootstrap'

import { ApiError } from '../api/client'
import * as documentsApi from '../api/documents'
import { IngestionStatusBadge } from './IngestionStatusBadge'
import type { DocumentDetail } from '../types'
import { formatBytes } from '../utils/formatBytes'
import { triggerFileDownload } from '../utils/triggerFileDownload'

type DocumentVersionsDialogProps = {
  documentId: number | null
  onOpenChange: (open: boolean) => void
}

export function DocumentVersionsDialog({ documentId, onOpenChange }: DocumentVersionsDialogProps) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)

  useEffect(() => {
    if (documentId === null) {
      setDetail(null)
      return
    }
    setIsLoading(true)
    setError(null)
    documentsApi
      .getDocument(documentId)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load versions.'))
      .finally(() => setIsLoading(false))
  }, [documentId])

  async function handleDownload(versionId: number) {
    if (documentId === null) return
    setDownloadingId(versionId)
    try {
      const { blob, filename } = await documentsApi.downloadDocument(documentId, versionId)
      triggerFileDownload(blob, filename)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Download failed.')
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <Modal show={documentId !== null} onHide={() => onOpenChange(false)} size="lg" centered>
      <Modal.Header closeButton>
        <Modal.Title as="h5">
          {detail ? `Version history — ${detail.title}` : 'Version history'}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && <p className="small text-danger">{error}</p>}

        {isLoading ? (
          <p className="small text-body-secondary mb-0">Loading…</p>
        ) : (
          detail && (
            <Table hover responsive className="align-middle mb-0">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>File</th>
                  <th>Size</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {[...detail.versions]
                  .sort((a, b) => b.version_no - a.version_no)
                  .map((version) => (
                    <tr key={version.id}>
                      <td className="fw-medium">
                        <div className="d-flex align-items-center gap-2">
                          v{version.version_no}
                          {version.is_active && <Badge bg="primary">active</Badge>}
                        </div>
                      </td>
                      <td className="text-body-secondary">{version.original_filename}</td>
                      <td className="text-body-secondary">{formatBytes(version.size_bytes)}</td>
                      <td className="text-body-secondary text-nowrap">
                        {new Date(`${version.uploaded_at}Z`).toLocaleString()}
                      </td>
                      <td>
                        <IngestionStatusBadge version={version} />
                      </td>
                      <td>
                        <Button
                          variant="link"
                          size="sm"
                          className="p-1"
                          onClick={() => handleDownload(version.id)}
                          disabled={downloadingId === version.id}
                          aria-label={`Download version ${version.version_no}`}
                        >
                          <Download size={16} />
                        </Button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </Table>
          )
        )}
      </Modal.Body>
    </Modal>
  )
}
