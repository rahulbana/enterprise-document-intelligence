// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Top-level route table.

import { Route, Routes } from 'react-router-dom'

import { AuditLogPage } from '../features/admin/AuditLogPage'
import { DepartmentDocumentsPage } from '../features/admin/DepartmentDocumentsPage'
import { DepartmentsPage } from '../features/admin/DepartmentsPage'
import { UsersPage } from '../features/admin/UsersPage'
import { LoginPage } from '../features/auth/LoginPage'
import { RegisterPage } from '../features/auth/RegisterPage'
import { ChatPage } from '../features/chat/ChatPage'
import { MyDocumentsPage } from '../features/documents/MyDocumentsPage'
import { HomePage } from '../features/home/HomePage'
import { NotFoundPage } from '../features/misc/NotFoundPage'
import { AdminRoute } from './AdminRoute'
import { ProtectedRoute } from './ProtectedRoute'

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/documents" element={<MyDocumentsPage />} />
        <Route path="/chat" element={<ChatPage />} />

        <Route element={<AdminRoute />}>
          <Route path="/admin/departments" element={<DepartmentsPage />} />
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/documents" element={<DepartmentDocumentsPage />} />
          <Route path="/admin/audit-log" element={<AuditLogPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
