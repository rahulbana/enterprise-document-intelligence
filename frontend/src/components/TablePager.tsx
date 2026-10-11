// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Prev/Next pager for the offset/limit-paginated list endpoints (documents,
// departments, users — see PageParams on the backend). Plain client-side
// offset paging rather than URL-based page-number links.

import { Button } from 'react-bootstrap'

type TablePagerProps = {
  offset: number
  limit: number
  total: number
  onOffsetChange: (offset: number) => void
}

export function TablePager({ offset, limit, total, onOffsetChange }: TablePagerProps) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)

  return (
    <div className="d-flex align-items-center justify-content-between px-3 py-3 small text-body-secondary">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="d-flex gap-2">
        <Button
          variant="outline-primary"
          size="sm"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          variant="outline-primary"
          size="sm"
          disabled={offset + limit >= total}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
