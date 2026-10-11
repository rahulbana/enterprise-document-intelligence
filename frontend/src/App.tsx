// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import { Toaster } from 'sonner'
import { BrowserRouter } from 'react-router-dom'

import { AuthProvider } from './auth/AuthContext'
import { Nav } from './components/Nav'
import { AppRouter } from './routes/AppRouter'

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Nav />
        <AppRouter />
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </BrowserRouter>
  )
}
