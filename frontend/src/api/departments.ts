// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import type { Department } from '../types'
import type { Page } from './client'
import { apiDelete, apiPatch, apiPost, requestPaged } from './client'

export function listDepartments(params?: {
  q?: string
  limit?: number
  offset?: number
}): Promise<Page<Department>> {
  const query = new URLSearchParams({
    limit: String(params?.limit ?? 20),
    offset: String(params?.offset ?? 0),
  })
  if (params?.q) query.set('q', params.q)
  return requestPaged<Department>(`/departments?${query.toString()}`)
}

// Used as a lookup/picker (department checkboxes on user rows, document
// sharing) rather than a paginated table — those need the whole list, not
// one page of it. 200 is the backend's own max page size.
export async function listAllDepartments(): Promise<Department[]> {
  return (await listDepartments({ limit: 200 })).items
}

export function createDepartment(name: string, description: string): Promise<Department> {
  return apiPost<Department>('/departments', { name, description: description || null })
}

export function updateDepartment(
  id: number,
  fields: { name?: string; description?: string },
): Promise<Department> {
  return apiPatch<Department>(`/departments/${id}`, fields)
}

export function deleteDepartment(id: number): Promise<void> {
  return apiDelete<void>(`/departments/${id}`)
}
