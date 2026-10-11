// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import {
  Building2,
  FileText,
  LayoutGrid,
  LogOut,
  MessageSquare,
  ScrollText,
  Sparkles,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Badge, Container, Dropdown, Nav as BsNav, Navbar } from 'react-bootstrap'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/)
  const initials = parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[1][0]
  return initials.toUpperCase()
}

function NavItem({
  to,
  icon: Icon,
  end,
  children,
}: {
  to: string
  icon: LucideIcon
  end?: boolean
  children: string
}) {
  return (
    <BsNav.Link as={NavLink} to={to} end={end} className="d-flex align-items-center gap-1">
      <Icon size={16} />
      {children}
    </BsNav.Link>
  )
}

export function Nav() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <Navbar
      bg="primary"
      data-bs-theme="dark"
      sticky="top"
      className="app-navbar shadow-sm"
    >
      <Container fluid className="px-4">
        <Navbar.Brand as={NavLink} to="/" className="d-flex align-items-center gap-2 fw-bold">
          <Sparkles size={20} />
          Document Intelligence
        </Navbar.Brand>

        {user && (
          <BsNav className="me-auto ms-3 flex-row align-items-center gap-1">
            <NavItem to="/" end icon={LayoutGrid}>
              Home
            </NavItem>
            <NavItem to="/documents" icon={FileText}>
              My Documents
            </NavItem>
            <NavItem to="/chat" icon={MessageSquare}>
              Chat
            </NavItem>

            {user.role === 'admin' && (
              <>
                <NavItem to="/admin/departments" icon={Building2}>
                  Departments
                </NavItem>
                <NavItem to="/admin/users" icon={Users}>
                  Users
                </NavItem>
                <NavItem to="/admin/documents" icon={FileText}>
                  Department Documents
                </NavItem>
                <NavItem to="/admin/audit-log" icon={ScrollText}>
                  Audit Log
                </NavItem>
              </>
            )}
          </BsNav>
        )}

        {user ? (
          <Dropdown align="end">
            <Dropdown.Toggle
              as="button"
              className="btn btn-light rounded-circle d-flex align-items-center justify-content-center p-0 fw-semibold text-primary"
              style={{ width: 36, height: 36 }}
              aria-label="Account menu"
            >
              {initialsOf(user.full_name)}
            </Dropdown.Toggle>
            <Dropdown.Menu data-bs-theme="light" style={{ minWidth: 240 }}>
              <Dropdown.ItemText>
                <div className="fw-medium">{user.full_name}</div>
                <div className="small text-body-secondary">{user.email}</div>
                <Badge bg="primary" className="mt-1 text-capitalize">
                  {user.role}
                </Badge>
              </Dropdown.ItemText>
              <Dropdown.Divider />
              <Dropdown.Item onClick={handleLogout} className="text-danger d-flex align-items-center gap-2">
                <LogOut size={16} />
                Log out
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        ) : (
          <BsNav className="ms-auto flex-row gap-3">
            <BsNav.Link as={NavLink} to="/login">
              Log in
            </BsNav.Link>
            <BsNav.Link as={NavLink} to="/register">
              Sign up
            </BsNav.Link>
          </BsNav>
        )}
      </Container>
    </Navbar>
  )
}
