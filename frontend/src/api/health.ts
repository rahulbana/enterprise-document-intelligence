// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import { apiGet } from './client'

export interface HealthResponse {
  status: string
  app: string
  env: string
}

export function getHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health', false)
}
