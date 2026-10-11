// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Thin action bar shown above a table when one or more rows are selected —
// shared by Users, My Documents, and Department Documents so multi-select
// looks and behaves the same everywhere.

import type { ReactNode } from 'react'
import { Button } from 'react-bootstrap'

export function BulkActionBar({
  selectedCount,
  onClear,
  children,
}: {
  selectedCount: number
  onClear: () => void
  children: ReactNode
}) {
  if (selectedCount === 0) return null

  return (
    <div className="d-flex flex-wrap align-items-center gap-3 rounded border bg-primary-subtle px-3 py-2 small">
      <span className="fw-medium">{selectedCount} selected</span>
      <div className="d-flex flex-wrap align-items-center gap-2">{children}</div>
      <Button variant="link" size="sm" className="ms-auto text-decoration-none" onClick={onClear}>
        Clear
      </Button>
    </div>
  )
}
