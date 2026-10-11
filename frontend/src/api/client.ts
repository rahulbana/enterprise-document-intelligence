// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Fetch wrapper shared by every resource client: attaches the bearer token,
// and on a 401 tries exactly one silent refresh-and-retry before giving up.

import { tokenStorage } from '../auth/tokenStorage'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export class AuthSessionExpiredError extends Error {
  constructor() {
    super('Session expired, please sign in again.')
    this.name = 'AuthSessionExpiredError'
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  formData?: FormData
  auth?: boolean
}

let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  refreshPromise ??= doRefresh().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

async function doRefresh(): Promise<string> {
  const refreshToken = tokenStorage.getRefreshToken()
  if (!refreshToken) {
    throw new AuthSessionExpiredError()
  }

  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!response.ok) {
    tokenStorage.clear()
    throw new AuthSessionExpiredError()
  }

  const data = (await response.json()) as { access_token: string }
  tokenStorage.setAccessToken(data.access_token)
  return data.access_token
}

function rawRequest(path: string, options: RequestOptions, accessToken: string | null) {
  const headers: Record<string, string> = {}
  if (options.auth !== false && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }

  // FormData sets its own multipart Content-Type (with boundary) — only set
  // one explicitly for JSON bodies.
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  return fetch(`${API_BASE_URL}${path}`, { method: options.method ?? 'GET', headers, body })
}

// FastAPI's `detail` is a plain string for HTTPException, but a list of
// {loc, msg, type} objects for 422 validation errors — String() on that list
// renders "[object Object]".
function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return null

  const messages = detail
    .map((item) => {
      if (!item || typeof item !== 'object' || typeof item.msg !== 'string') return null
      const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null
      return typeof field === 'string' && field !== 'body' ? `${field}: ${item.msg}` : item.msg
    })
    .filter((message): message is string => message !== null)

  return messages.length > 0 ? messages.join('; ') : null
}

async function authorizedFetch(path: string, options: RequestOptions): Promise<Response> {
  let response = await rawRequest(path, options, tokenStorage.getAccessToken())

  if (response.status === 401 && options.auth !== false) {
    const newAccessToken = await refreshAccessToken()
    response = await rawRequest(path, options, newAccessToken)
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new ApiError(
      response.status,
      formatErrorDetail(detail) ??
        `${options.method ?? 'GET'} ${path} failed with status ${response.status}`,
    )
  }

  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await authorizedFetch(path, options)
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export interface DownloadedFile {
  blob: Blob
  filename: string
}

export async function download(path: string): Promise<DownloadedFile> {
  const response = await authorizedFetch(path, {})
  const blob = await response.blob()
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)
  const filename = match ? decodeURIComponent(match[1]) : 'download'
  return { blob, filename }
}

export interface Page<T> {
  items: T[]
  total: number
}

// For the offset/limit-paginated list endpoints (documents, departments,
// users — see backend's PageParams): same auth/retry handling as request(),
// but also reads the X-Total-Count header the backend sets on every one of
// them, since the JSON body itself stays a plain array.
export async function requestPaged<T>(path: string, auth = true): Promise<Page<T>> {
  const response = await authorizedFetch(path, { auth })
  const items = (await response.json()) as T[]
  const total = Number(response.headers.get('X-Total-Count') ?? items.length)
  return { items, total }
}

export const apiGet = <T>(path: string, auth = true) => request<T>(path, { auth })
export const apiPost = <T>(path: string, body?: unknown, auth = true) =>
  request<T>(path, { method: 'POST', body, auth })
export const apiPatch = <T>(path: string, body?: unknown, auth = true) =>
  request<T>(path, { method: 'PATCH', body, auth })
export const apiPut = <T>(path: string, body?: unknown, auth = true) =>
  request<T>(path, { method: 'PUT', body, auth })
export const apiDelete = <T>(path: string, auth = true) =>
  request<T>(path, { method: 'DELETE', auth })
export const apiUpload = <T>(path: string, formData: FormData) =>
  request<T>(path, { method: 'POST', formData })

// For SSE endpoints: same bearer-token + one-retry-on-401 handling as
// request(), but returns the raw Response so the caller can read
// response.body as a stream instead of parsing it as JSON.
export const postStream = (path: string, body: unknown) =>
  authorizedFetch(path, { method: 'POST', body })
