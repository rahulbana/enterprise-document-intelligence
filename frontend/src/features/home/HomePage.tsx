// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import {
  ArrowRight,
  Building2,
  FileText,
  Globe,
  MessageSquare,
  ScrollText,
  Sparkles,
  Users,
  XCircle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Badge, Card, Col, Row } from 'react-bootstrap'
import { Link } from 'react-router-dom'

import { getHealth } from '../../api/health'
import type { HealthResponse } from '../../api/health'
import { useAuth } from '../../auth/useAuth'

const CAPABILITIES = ['Hybrid search', 'Re-ranking', 'Web search', 'Cited answers']

interface FeatureTile {
  to: string
  title: string
  description: string
  icon: LucideIcon
  // Bootstrap theme colour name for the icon tile — each destination gets
  // its own colour.
  color: string
}

const MAIN_TILES: FeatureTile[] = [
  {
    to: '/chat',
    title: 'Chat',
    description: 'Ask questions and get answers grounded in your uploaded documents.',
    icon: MessageSquare,
    color: 'primary',
  },
  {
    to: '/documents',
    title: 'My Documents',
    description: "Upload, browse, and manage your own and your department's documents.",
    icon: FileText,
    color: 'success',
  },
]

const ADMIN_TILES: FeatureTile[] = [
  {
    to: '/admin/departments',
    title: 'Departments',
    description: 'Organise teams and control who can see which documents.',
    icon: Building2,
    color: 'warning',
  },
  {
    to: '/admin/users',
    title: 'Users',
    description: 'Manage accounts, roles, and access in bulk.',
    icon: Users,
    color: 'info',
  },
  {
    to: '/admin/audit-log',
    title: 'Audit Log',
    description: 'A tamper-evident trail of sign-ins and account changes.',
    icon: ScrollText,
    color: 'danger',
  },
]

function TileLink({ tile }: { tile: FeatureTile }) {
  const Icon = tile.icon
  return (
    <Link to={tile.to} className="feature-tile d-block h-100">
      <Card
        className="h-100 shadow-sm"
        style={{ borderTop: `4px solid var(--bs-${tile.color})` }}
      >
        <Card.Body>
          <span className={`feature-icon bg-${tile.color} mb-3`}>
            <Icon size={22} />
          </span>
          <Card.Title className="d-flex align-items-center gap-2 h6">
            {tile.title}
            <ArrowRight size={16} className="text-primary" />
          </Card.Title>
          <Card.Text className="text-body-secondary small">{tile.description}</Card.Text>
        </Card.Body>
      </Card>
    </Link>
  )
}

export function HomePage() {
  const { user } = useAuth()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setError('Could not reach the API. Is the backend running?'))
  }, [])

  return (
    <main className="app-page d-flex flex-column gap-4">
      <section className="rounded-3 bg-primary text-white p-4 p-md-5 shadow-sm">
        <div className="d-inline-flex align-items-center gap-2 rounded-pill bg-white bg-opacity-25 px-3 py-1 small fw-medium mb-3">
          <Sparkles size={14} />
          Agentic RAG
        </div>
        <h1 className="h2 fw-bold mb-2">Welcome, {user?.full_name}</h1>
        <p className="mb-3" style={{ maxWidth: 720, opacity: 0.9 }}>
          Ask questions across your documents, or manage what's been uploaded. The assistant
          decides when to search your files and when to look things up on the web, and cites what
          it used.
        </p>
        <div className="d-flex flex-wrap gap-2 mb-4">
          {CAPABILITIES.map((capability) => (
            <span
              key={capability}
              className="d-inline-flex align-items-center gap-1 rounded-pill bg-white bg-opacity-25 px-3 py-1 small"
            >
              {capability === 'Web search' && <Globe size={12} />}
              {capability}
            </span>
          ))}
        </div>
        <Link
          to="/chat"
          className="btn btn-light d-inline-flex align-items-center gap-2 text-primary fw-medium"
        >
          Start chatting
          <ArrowRight size={16} />
        </Link>
      </section>

      <Row className="g-4">
        {MAIN_TILES.map((tile) => (
          <Col key={tile.to} sm={6}>
            <TileLink tile={tile} />
          </Col>
        ))}
      </Row>

      {user?.role === 'admin' && (
        <>
          <h2 className="h6 text-uppercase text-body-secondary mb-0 mt-2">Administration</h2>
          <Row className="g-4">
            {ADMIN_TILES.map((tile) => (
              <Col key={tile.to} sm={4}>
                <TileLink tile={tile} />
              </Col>
            ))}
          </Row>
        </>
      )}

      <Card className="shadow-sm">
        <Card.Body className="d-flex align-items-center gap-2 small">
          {error && (
            <>
              <XCircle size={16} className="text-danger" />
              <span className="text-danger">{error}</span>
            </>
          )}
          {!error && !health && <span className="text-body-secondary">Checking API status…</span>}
          {health && (
            <>
              <span className="d-inline-block rounded-circle bg-success" style={{ width: 10, height: 10 }} />
              <span>
                API status: <Badge bg="success">{health.status}</Badge> ({health.app}, {health.env})
              </span>
            </>
          )}
        </Card.Body>
      </Card>
    </main>
  )
}
