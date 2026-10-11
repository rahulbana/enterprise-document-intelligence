// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Redirects non-admins to home. Assumes it's nested under ProtectedRoute,
// so a missing user is already handled there.

import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

export function AdminRoute() {
  const { user } = useAuth()

  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
