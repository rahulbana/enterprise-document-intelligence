// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Read-only in-app preview: PDFs and images render natively (the browser
// does this for free via a blob URL — no reason to throw that away).
// Everything else (docx, pptx, xlsx, odt, txt, email formats, ...) has no
// browser-native renderer, so it falls back to the same chunked content
// chat citations are already drawn from — same text, same page/slide/sheet
// labels (see chunkLocationLabel), just reconstructed into one scrollable
// view instead of one match at a time. That's "click to read" for every
// format this app ingests, not just the two the browser happens to handle.

import { Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button, Modal } from 'react-bootstrap'

import { ApiError } from '../api/client'
import * as documentsApi from '../api/documents'
import { IngestionStatusBadge } from './IngestionStatusBadge'
import type { DocumentDetail, DocumentPreviewChunk } from '../types'
import { chunkLocationLabel } from '../utils/chunkLocationLabel'
import { triggerFileDownload } from '../utils/triggerFileDownload'

const NATIVE_IMAGE_EXTENSIONS = new Set([
  'png',
  'jpg',
  'jpeg',
  'gif',
  'bmp',
  'webp',
  'tif',
  'tiff',
])

type DocumentPreviewDialogProps = {
  documentId: number | null
  focusChunkIndex?: number | null
  onOpenChange: (open: boolean) => void
}

export function DocumentPreviewDialog({
  documentId,
  focusChunkIndex = null,
  onOpenChange,
}: DocumentPreviewDialogProps) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [chunks, setChunks] = useState<DocumentPreviewChunk[] | null>(null)
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const focusedChunkRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (documentId === null) return

    let cancelled = false
    let objectUrl: string | null = null
    setDetail(null)
    setChunks(null)
    setBlobUrl(null)
    setError(null)
    setIsLoading(true)

    async function load() {
      try {
        const doc = await documentsApi.getDocument(documentId!)
        if (cancelled) return
        setDetail(doc)

        const fileType = doc.active_version?.file_type.toLowerCase()
        const isNative = fileType === 'pdf' || (fileType && NATIVE_IMAGE_EXTENSIONS.has(fileType))

        if (isNative) {
          const { blob } = await documentsApi.downloadDocument(documentId!)
          if (cancelled) return
          objectUrl = URL.createObjectURL(blob)
          setBlobUrl(objectUrl)
        } else {
          const previewChunks = await documentsApi.getDocumentPreview(documentId!)
          if (cancelled) return
          setChunks(previewChunks)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load preview.')
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    load()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [documentId])

  useEffect(() => {
    if (chunks && focusChunkIndex !== null) {
      focusedChunkRef.current?.scrollIntoView({ block: 'center' })
    }
  }, [chunks, focusChunkIndex])

  async function handleDownload() {
    if (documentId === null) return
    setIsDownloading(true)
    try {
      const { blob, filename } = await documentsApi.downloadDocument(documentId)
      triggerFileDownload(blob, filename)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Download failed.')
    } finally {
      setIsDownloading(false)
    }
  }

  const activeVersion = detail?.active_version ?? null

  return (
    <Modal
      show={documentId !== null}
      onHide={() => onOpenChange(false)}
      size="xl"
      centered
      scrollable
    >
      <Modal.Header closeButton>
        <Modal.Title as="h5" className="text-truncate me-3">
          {detail?.title ?? 'Preview'}
        </Modal.Title>
        <Button
          variant="outline-primary"
          size="sm"
          className="ms-auto me-2 d-inline-flex align-items-center gap-1"
          onClick={handleDownload}
          disabled={isDownloading}
        >
          <Download size={14} />
          {isDownloading ? 'Downloading…' : 'Download'}
        </Button>
      </Modal.Header>
      <Modal.Body>
        {error && <p className="small text-danger">{error}</p>}

        {isLoading ? (
          <p className="small text-body-secondary mb-0">Loading preview…</p>
        ) : blobUrl ? (
          activeVersion?.file_type.toLowerCase() === 'pdf' ? (
            <iframe
              src={blobUrl}
              title={detail?.title}
              className="w-100 rounded border"
              style={{ height: '70vh' }}
            />
          ) : (
            <div
              className="d-flex align-items-center justify-content-center overflow-auto rounded border bg-light p-2"
              style={{ maxHeight: '70vh' }}
            >
              <img
                src={blobUrl}
                alt={detail?.title ?? 'Document preview'}
                className="img-fluid"
              />
            </div>
          )
        ) : chunks !== null ? (
          chunks.length === 0 ? (
            <p className="small text-body-secondary mb-0">
              {activeVersion && activeVersion.status !== 'ready' ? (
                <>
                  No preview yet — this document is <IngestionStatusBadge version={activeVersion} />.
                </>
              ) : (
                'No extractable text was found for this document.'
              )}
            </p>
          ) : (
            <div className="d-flex flex-column gap-3">
              {chunks.map((chunk) => {
                const label = chunkLocationLabel(chunk.metadata)
                const isFocused = chunk.chunk_index === focusChunkIndex
                return (
                  <div
                    key={chunk.chunk_index}
                    ref={isFocused ? focusedChunkRef : undefined}
                    className={`rounded border p-3 small ${
                      isFocused ? 'border-primary bg-primary-subtle' : ''
                    }`}
                    style={{ whiteSpace: 'pre-wrap' }}
                  >
                    {label && (
                      <p className="mb-1 text-uppercase fw-medium text-body-secondary small">
                        {label}
                      </p>
                    )}
                    {chunk.content}
                  </div>
                )
              })}
            </div>
          )
        ) : null}
      </Modal.Body>
    </Modal>
  )
}
