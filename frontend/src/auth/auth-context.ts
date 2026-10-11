// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// The raw context object, kept in its own module (not a component file) so
// AuthContext.tsx only exports the provider component and useAuth.ts only
// exports the hook — needed for Fast Refresh to treat both as pure component
// modules.

import { createContext } from 'react'

import type { User } from '../types'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
