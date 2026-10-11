// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import type { User } from '../types'
import { apiGet, apiPost } from './client'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export function register(email: string, password: string, fullName: string): Promise<User> {
  return apiPost<User>(
    '/auth/register',
    { email, password, full_name: fullName },
    false,
  )
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiPost<TokenResponse>('/auth/login', { email, password }, false)
}

export function me(): Promise<User> {
  return apiGet<User>('/auth/me')
}
