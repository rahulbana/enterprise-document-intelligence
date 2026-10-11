// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Admin screen: create, list, rename, and delete departments.

import { Pencil, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, Button, Card, Form, Table } from 'react-bootstrap'
import { toast } from 'sonner'

import { ApiError } from '../../api/client'
import * as departmentsApi from '../../api/departments'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { LoadingBar } from '../../components/LoadingBar'
import { PageSizeSelect } from '../../components/PageSizeSelect'
import { TablePager } from '../../components/TablePager'
import { SearchInput } from '../../components/SearchInput'
import type { Department } from '../../types'

export function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [pendingDelete, setPendingDelete] = useState<Department | null>(null)

  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput)

  function loadDepartments() {
    setIsLoading(true)
    departmentsApi
      .listDepartments({ q: search || undefined, limit: pageSize, offset })
      .then(({ items, total }) => {
        setDepartments(items)
        setTotal(total)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load departments.'))
      .finally(() => setIsLoading(false))
  }

  useEffect(loadDepartments, [offset, pageSize, search])
  useEffect(() => setOffset(0), [pageSize, search])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsCreating(true)
    try {
      await departmentsApi.createDepartment(newName, newDescription)
      toast.success(`Department "${newName}" created`)
      setNewName('')
      setNewDescription('')
      loadDepartments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create department.')
    } finally {
      setIsCreating(false)
    }
  }

  function startEditing(department: Department) {
    setEditingId(department.id)
    setEditName(department.name)
    setEditDescription(department.description ?? '')
  }

  async function handleSaveEdit(id: number) {
    setError(null)
    try {
      await departmentsApi.updateDepartment(id, { name: editName, description: editDescription })
      toast.success(`Department "${editName}" updated`)
      setEditingId(null)
      loadDepartments()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update department.')
    }
  }

  async function handleDelete(id: number) {
    setError(null)
    try {
      await departmentsApi.deleteDepartment(id)
      setPendingDelete(null)
      if (departments.length === 1 && offset > 0) {
        setOffset(Math.max(0, offset - pageSize))
      } else {
        loadDepartments()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete department.')
    }
  }

  return (
    <main className="app-page d-flex flex-column gap-4">
      <h1 className="h3 text-primary mb-0">Departments</h1>

      <Card className="shadow-sm">
        <Card.Body>
          <Form onSubmit={handleCreate} className="d-flex flex-wrap align-items-end gap-3">
            <Form.Group controlId="dept-name">
              <Form.Label>Name</Form.Label>
              <Form.Control required value={newName} onChange={(e) => setNewName(e.target.value)} />
            </Form.Group>
            <Form.Group controlId="dept-description" className="flex-grow-1">
              <Form.Label>Description</Form.Label>
              <Form.Control
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </Form.Group>
            <Button type="submit" disabled={isCreating}>
              {isCreating ? 'Creating…' : 'Create'}
            </Button>
          </Form>
        </Card.Body>
      </Card>

      {error && (
        <Alert variant="danger" className="py-2 small mb-0">
          {error}
        </Alert>
      )}

      <div className="d-flex flex-wrap align-items-center gap-2">
        <PageSizeSelect value={pageSize} onChange={setPageSize} />
        <SearchInput value={searchInput} onChange={setSearchInput} placeholder="Search departments…" />
      </div>

      {isLoading ? (
        <LoadingBar label="Loading departments…" />
      ) : (
        <Card className="shadow-sm">
          <Table hover responsive className="align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {departments.map((department) => (
                <tr key={department.id}>
                  {editingId === department.id ? (
                    <>
                      <td>
                        <Form.Control
                          size="sm"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                        />
                      </td>
                      <td>
                        <Form.Control
                          size="sm"
                          value={editDescription}
                          onChange={(e) => setEditDescription(e.target.value)}
                        />
                      </td>
                      <td>
                        <div className="d-flex gap-2">
                          <Button variant="link" size="sm" onClick={() => handleSaveEdit(department.id)}>
                            Save
                          </Button>
                          <Button variant="link" size="sm" className="text-body-secondary" onClick={() => setEditingId(null)}>
                            Cancel
                          </Button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="fw-medium">{department.name}</td>
                      <td className="text-body-secondary">{department.description ?? '—'}</td>
                      <td className="text-end">
                        <Button
                          variant="link"
                          size="sm"
                          className="p-1 text-body-secondary"
                          onClick={() => startEditing(department)}
                          aria-label="Edit"
                        >
                          <Pencil size={16} />
                        </Button>
                        <Button
                          variant="link"
                          size="sm"
                          className="p-1 text-danger"
                          onClick={() => setPendingDelete(department)}
                          aria-label="Delete"
                        >
                          <Trash2 size={16} />
                        </Button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
              {departments.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-4 text-center text-body-secondary">
                    {search ? 'No departments match your search.' : 'No departments yet.'}
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
        title="Delete this department?"
        description={
          pendingDelete
            ? `"${pendingDelete.name}" will be removed. This can't be undone.`
            : ''
        }
        onConfirm={() => pendingDelete && handleDelete(pendingDelete.id)}
      />
    </main>
  )
}
