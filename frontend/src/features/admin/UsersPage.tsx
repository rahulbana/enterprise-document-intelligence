// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Admin screen: list users, toggle role/active status, assign departments.

import { useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Form, Table } from 'react-bootstrap'
import { toast } from 'sonner'

import { ApiError } from '../../api/client'
import * as departmentsApi from '../../api/departments'
import * as usersApi from '../../api/users'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { BulkActionBar } from '../../components/BulkActionBar'
import { LoadingBar } from '../../components/LoadingBar'
import { PageSizeSelect } from '../../components/PageSizeSelect'
import { TablePager } from '../../components/TablePager'
import { Checkbox } from '../../components/Checkbox'
import { SearchInput } from '../../components/SearchInput'
import type { Department, User, UserRole } from '../../types'

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [pageSize, setPageSize] = useState(20)
  const [departments, setDepartments] = useState<Department[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingUserId, setSavingUserId] = useState<number | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [isBulkSaving, setIsBulkSaving] = useState(false)

  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput)
  const [roleFilter, setRoleFilter] = useState<UserRole | 'all'>('all')
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all')

  function loadData() {
    setIsLoading(true)
    Promise.all([
      usersApi.listUsers({
        q: search || undefined,
        role: roleFilter === 'all' ? undefined : roleFilter,
        isActive: activeFilter === 'all' ? undefined : activeFilter === 'active',
        limit: pageSize,
        offset,
      }),
      departmentsApi.listAllDepartments(),
    ])
      .then(([userPage, departmentList]) => {
        setUsers(userPage.items)
        setTotal(userPage.total)
        setDepartments(departmentList)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load users.'))
      .finally(() => setIsLoading(false))
  }

  useEffect(loadData, [offset, pageSize, search, roleFilter, activeFilter])
  useEffect(() => setOffset(0), [pageSize, search, roleFilter, activeFilter])
  // Clear selection when the page/filters change the row set underneath it
  // — but NOT on every `users` update, since a single-row edit (role toggle,
  // etc.) replaces that array too and would otherwise wipe an unrelated
  // in-progress bulk selection.
  useEffect(() => setSelectedIds(new Set()), [offset, pageSize, search, roleFilter, activeFilter])

  function toggleSelected(userId: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(userId)
      else next.delete(userId)
      return next
    })
  }

  async function handleBulkSetActive(isActive: boolean) {
    setError(null)
    setIsBulkSaving(true)
    try {
      const updated = await usersApi.bulkSetActive([...selectedIds], isActive)
      toast.success(`${updated.length} user${updated.length === 1 ? '' : 's'} ${isActive ? 'activated' : 'deactivated'}`)
      setSelectedIds(new Set())
      loadData()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Bulk update failed.')
    } finally {
      setIsBulkSaving(false)
    }
  }

  async function handleRoleChange(user: User, role: User['role']) {
    setError(null)
    setSavingUserId(user.id)
    try {
      const updated = await usersApi.updateUser(user.id, { role })
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      toast.success(`${updated.full_name} role set to ${updated.role}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update role.')
    } finally {
      setSavingUserId(null)
    }
  }

  async function handleActiveToggle(user: User) {
    setError(null)
    setSavingUserId(user.id)
    try {
      const updated = await usersApi.updateUser(user.id, { is_active: !user.is_active })
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      toast.success(`${updated.full_name} is now ${updated.is_active ? 'active' : 'inactive'}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update status.')
    } finally {
      setSavingUserId(null)
    }
  }

  async function handleDepartmentToggle(user: User, departmentId: number, checked: boolean) {
    setError(null)
    setSavingUserId(user.id)
    const nextIds = checked
      ? [...user.department_ids, departmentId]
      : user.department_ids.filter((id) => id !== departmentId)
    try {
      const updated = await usersApi.setUserDepartments(user.id, nextIds)
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
      const departmentName = departments.find((d) => d.id === departmentId)?.name ?? 'department'
      toast.success(
        checked
          ? `${departmentName} assigned to ${updated.full_name}`
          : `${departmentName} removed from ${updated.full_name}`,
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update departments.')
    } finally {
      setSavingUserId(null)
    }
  }

  return (
    <main className="app-page d-flex flex-column gap-4">
      <h1 className="h3 text-primary mb-0">Users</h1>

      {error && (
        <Alert variant="danger" className="py-2 small mb-0">
          {error}
        </Alert>
      )}

      <BulkActionBar selectedCount={selectedIds.size} onClear={() => setSelectedIds(new Set())}>
        <Button
          variant="outline-primary"
          size="sm"
          disabled={isBulkSaving}
          onClick={() => handleBulkSetActive(true)}
        >
          Activate
        </Button>
        <Button
          variant="outline-primary"
          size="sm"
          disabled={isBulkSaving}
          onClick={() => handleBulkSetActive(false)}
        >
          Deactivate
        </Button>
      </BulkActionBar>

      <div className="d-flex flex-wrap align-items-center gap-2">
        <PageSizeSelect value={pageSize} onChange={setPageSize} />
        <SearchInput
          value={searchInput}
          onChange={setSearchInput}
          placeholder="Search by name or email…"
        />
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={roleFilter}
          aria-label="Role filter"
          onChange={(e) => setRoleFilter(e.target.value as UserRole | 'all')}
        >
          <option value="all">All roles</option>
          <option value="user">User</option>
          <option value="admin">Admin</option>
        </Form.Select>
        <Form.Select
          size="sm"
          style={{ width: 'auto' }}
          value={activeFilter}
          aria-label="Status filter"
          onChange={(e) => setActiveFilter(e.target.value as 'all' | 'active' | 'inactive')}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </Form.Select>
      </div>

      {isLoading ? (
        <LoadingBar label="Loading users…" />
      ) : (
        <Card className="shadow-sm">
          <Table hover responsive className="mb-0">
            <thead className="table-light">
              <tr>
                <th style={{ width: 40 }}>
                  <Checkbox
                    checked={
                      users.length > 0 && selectedIds.size === users.length
                        ? true
                        : selectedIds.size > 0
                          ? 'indeterminate'
                          : false
                    }
                    onCheckedChange={(checked) =>
                      setSelectedIds(checked ? new Set(users.map((u) => u.id)) : new Set())
                    }
                    aria-label="Select all"
                  />
                </th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Active</th>
                <th>Departments</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <Checkbox
                      checked={selectedIds.has(user.id)}
                      onCheckedChange={(checked) => toggleSelected(user.id, checked === true)}
                      aria-label={`Select ${user.full_name}`}
                    />
                  </td>
                  <td className="fw-medium">{user.full_name}</td>
                  <td className="text-body-secondary">{user.email}</td>
                  <td>
                    <Form.Select
                      size="sm"
                      style={{ width: 'auto' }}
                      value={user.role}
                      disabled={savingUserId === user.id}
                      aria-label={`Role for ${user.full_name}`}
                      onChange={(e) => handleRoleChange(user, e.target.value as User['role'])}
                    >
                      <option value="user">user</option>
                      <option value="admin">admin</option>
                    </Form.Select>
                  </td>
                  <td>
                    <div className="d-flex align-items-center gap-2">
                      <Checkbox
                        checked={user.is_active}
                        disabled={savingUserId === user.id}
                        onCheckedChange={() => handleActiveToggle(user)}
                        aria-label={`Active: ${user.full_name}`}
                      />
                      {!user.is_active && <Badge bg="warning">inactive</Badge>}
                    </div>
                  </td>
                  <td>
                    <div className="d-flex flex-column gap-1">
                      {departments.map((department) => (
                        <label key={department.id} className="d-flex align-items-center gap-2 small">
                          <Checkbox
                            checked={user.department_ids.includes(department.id)}
                            disabled={savingUserId === user.id}
                            onCheckedChange={(checked) =>
                              handleDepartmentToggle(user, department.id, checked === true)
                            }
                          />
                          {department.name}
                        </label>
                      ))}
                      {departments.length === 0 && (
                        <span className="text-body-secondary">No departments yet</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-body-secondary">
                    {search || roleFilter !== 'all' || activeFilter !== 'all'
                      ? 'No users match your filters.'
                      : 'No users yet.'}
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
