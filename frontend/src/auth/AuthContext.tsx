// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// App-wide auth state provider: current user, sign in/up/out. On mount,
// restores the session from a stored access token by calling /auth/me
// (client.ts silently refreshes it first if it's expired).

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import * as authApi from '../api/auth'
import type { User } from '../types'
import { AuthContext } from './auth-context'
import { tokenStorage } from './tokenStorage'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!tokenStorage.getAccessToken()) {
      setIsLoading(false)
      return
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStorage.clear())
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authApi.login(email, password)
    tokenStorage.setTokens(tokens.access_token, tokens.refresh_token)
    setUser(await authApi.me())
  }, [])

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    // Deliberately does not chain a login() afterward: new accounts are
    // created inactive and in no department (admin-approval gate, see
    // backend/app/services/auth_service.py), so login would just fail
    // immediately after every registration. RegisterPage shows a "pending
    // approval" message instead of signing the user in.
    await authApi.register(email, password, fullName)
  }, [])

  const logout = useCallback(() => {
    tokenStorage.clear()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
