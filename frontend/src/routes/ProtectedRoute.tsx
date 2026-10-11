// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Redirects to /login when there's no authenticated user.

import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return null
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
