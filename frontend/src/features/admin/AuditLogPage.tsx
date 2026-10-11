// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Admin screen: read-only view of the auth audit log (register/login/
// activation events), plus an on-demand tamper check that recomputes the
// whole hash chain server-side.

import { ChevronsRight, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Form, Table } from 'react-bootstrap'

import * as auditLogApi from '../../api/auditLog'
import { ApiError } from '../../api/client'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { LoadingBar } from '../../components/LoadingBar'
import { PageSizeSelect } from '../../components/PageSizeSelect'
import { TablePager } from '../../components/TablePager'
import { SearchInput } from '../../components/SearchInput'
import type { AuditChainVerification, AuthAuditLogEntry, AuthEventType } from '../../types'

const EVENT_BADGE: Record<AuthEventType, { label: string; bg: string }> = {
  register: { label: 'register', bg: 'info' },
  login_success: { label: 'login success', bg: 'success' },
  login_failure: { label: 'login failure', bg: 'danger' },
  account_activated: { label: 'activated', bg: 'success' },
  account_deactivated: { label: 'deactivated', bg: 'warning' },
}

function shortHash(hash: string | null): string {
  return hash ? `${hash.slice(0, 10)}…` : '—'
}

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuthAuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput)
  const [eventTypeFilter, setEventTypeFilter] = useState<AuthEventType | 'all'>('all')

  const [verification, setVerification] = useState<AuditChainVerification | null>(null)
  const [isVerifying, setIsVerifying] = useState(false)

  function loadData() {
    setIsLoading(true)
    auditLogApi
      .listAuditLog({
        q: search || undefined,
        eventType: eventTypeFilter === 'all' ? undefined : eventTypeFilter,
        limit: pageSize,
        offset,
      })
      .then((page) => {
        setEntries(page.items)
        setTotal(page.total)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load audit log.'))
      .finally(() => setIsLoading(false))
  }

  useEffect(loadData, [offset, pageSize, search, eventTypeFilter])
  useEffect(() => setOffset(0), [pageSize, search, eventTypeFilter])

  function handleVerify() {
    setIsVerifying(true)
    setError(null)
    auditLogApi
      .verifyAuditLog()
      .then(setVerification)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to verify chain.'))
      .finally(() => setIsVerifying(false))
  }

  useEffect(handleVerify, [])

  return (
    <main className="app-page d-flex flex-column gap-4">
      <h1 className="h3 text-primary mb-0">Auth Audit Log</h1>

      <Card className="shadow-sm">
        <Card.Body className="d-flex flex-wrap align-items-center justify-content-between gap-3">
          {verification ? (
            <div className="d-flex align-items-center gap-2">
              {verification.valid ? (
                <Badge bg="success" className="d-inline-flex align-items-center gap-1">
                  <ShieldCheck size={14} />
                  Chain intact
                </Badge>
              ) : (
                <Badge bg="danger" className="d-inline-flex align-items-center gap-1">
                  <ShieldAlert size={14} />
                  Tampering detected at entry #{verification.broken_at_id}
                </Badge>
              )}
              <span className="small text-body-secondary">
                {verification.total_entries} total entries
              </span>
            </div>
          ) : (
            <span />
          )}
          <Button
            variant="outline-primary"
            size="sm"
            className="d-inline-flex align-items-center gap-1"
            onClick={handleVerify}
            disabled={isVerifying}
          >
            <RefreshCw size={14} className={isVerifying ? 'spin' : ''} />
            {isVerifying ? 'Verifying…' : 'Re-verify chain'}
          </Button>
        </Card.Body>
      </Card>

      {error && (
        <Alert variant="danger" className="py-2 small mb-0">
          {error}
        </Alert>
      )}

      <div className="d-flex flex-wrap align-items-center gap-2">
        <PageSizeSelect value={pageSize} onChange={setPageSize} />
        <SearchInput value={searchInput} onChange={setSearchInput} placeholder="Search by email…" />
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={eventTypeFilter}
          aria-label="Event type filter"
          onChange={(e) => setEventTypeFilter(e.target.value as AuthEventType | 'all')}
        >
          <option value="all">All events</option>
          <option value="register">Register</option>
          <option value="login_success">Login success</option>
          <option value="login_failure">Login failure</option>
          <option value="account_activated">Activated</option>
          <option value="account_deactivated">Deactivated</option>
        </Form.Select>
      </div>

      {isLoading ? (
        <LoadingBar label="Loading audit log…" />
      ) : (
        <Card className="shadow-sm">
          <Table hover responsive className="align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Email</th>
                <th>Detail</th>
                <th>Hash chain</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="text-body-secondary text-nowrap">
                    {new Date(`${entry.created_at}Z`).toLocaleString()}
                  </td>
                  <td>
                    <Badge bg={EVENT_BADGE[entry.event_type].bg}>
                      {EVENT_BADGE[entry.event_type].label}
                    </Badge>
                  </td>
                  <td>{entry.email}</td>
                  <td className="text-body-secondary">{entry.detail ?? '—'}</td>
                  <td className="font-monospace small text-body-secondary text-nowrap">
                    <div className="d-flex align-items-center gap-1">
                      {shortHash(entry.prev_hash)}
                      <ChevronsRight size={12} />
                      {shortHash(entry.entry_hash)}
                    </div>
                  </td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-body-secondary">
                    {search || eventTypeFilter !== 'all'
                      ? 'No audit entries match your filters.'
                      : 'No audit entries yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
          <TablePager offset={offset} limit={pageSize} total={total} onOffsetChange={setOffset} />
        </Card>
      )}
    </main>
  )
}
