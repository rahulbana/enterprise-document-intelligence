// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import { Badge } from 'react-bootstrap'

import type { DocumentVersion } from '../types'

const STYLES: Record<DocumentVersion['status'], { bg: string; text?: string }> = {
  pending: { bg: 'light', text: 'dark' },
  processing: { bg: 'warning' },
  ready: { bg: 'success' },
  failed: { bg: 'danger' },
}

export function IngestionStatusBadge({ version }: { version: DocumentVersion }) {
  const style = STYLES[version.status]
  return (
    <Badge
      bg={style.bg}
      text={style.text}
      className="border"
      title={version.status === 'failed' ? (version.status_message ?? undefined) : undefined}
    >
      {version.status === 'ready' ? `ready (${version.chunk_count} chunks)` : version.status}
    </Badge>
  )
}
