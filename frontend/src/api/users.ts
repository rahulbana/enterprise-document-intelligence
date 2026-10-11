// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import type { User, UserRole } from '../types'
import type { Page } from './client'
import { apiPatch, apiPost, apiPut, requestPaged } from './client'

export function listUsers(params?: {
  q?: string
  role?: UserRole
  isActive?: boolean
  limit?: number
  offset?: number
}): Promise<Page<User>> {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 20),
    offset: String(params?.offset ?? 0),
  })
  if (params?.q) query.set('q', params.q)
  if (params?.role) query.set('role', params.role)
  if (params?.isActive !== undefined) query.set('is_active', String(params.isActive))
  return requestPaged<User>(`/users?${query.toString()}`)
}

export function updateUser(id: number, fields: { role?: UserRole; is_active?: boolean }): Promise<User> {
  return apiPatch<User>(`/users/${id}`, fields)
}

export function bulkSetActive(userIds: number[], isActive: boolean): Promise<User[]> {
  return apiPost<User[]>('/users/bulk-status', { user_ids: userIds, is_active: isActive })
}

export function setUserDepartments(id: number, departmentIds: number[]): Promise<User> {
  return apiPut<User>(`/users/${id}/departments`, { department_ids: departmentIds })
}
