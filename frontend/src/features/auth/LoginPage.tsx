// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, Button, Card, Form } from 'react-bootstrap'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/useAuth'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="container py-5 d-flex flex-column justify-content-center" style={{ maxWidth: 460, minHeight: 'calc(100vh - var(--app-nav-height))' }}>
      <Card className="shadow">
        <Card.Body className="p-4">
          <div className="text-center mb-4">
            <span className="feature-icon bg-primary mb-3">
              <Sparkles size={22} />
            </span>
            <h1 className="h4 text-primary mb-1">Sign in</h1>
            <p className="text-body-secondary small mb-0">Welcome back to Document Intelligence.</p>
          </div>

          <Form onSubmit={handleSubmit} className="d-flex flex-column gap-3">
            <Form.Group controlId="email">
              <Form.Label>Email</Form.Label>
              <Form.Control
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Form.Group>
            <Form.Group controlId="password">
              <Form.Label>Password</Form.Label>
              <Form.Control
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Form.Group>

            {error && (
              <Alert variant="danger" className="py-2 small mb-0">
                {error}
              </Alert>
            )}

            <Button type="submit" disabled={isSubmitting} className="w-100">
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </Form>

          <p className="mt-4 mb-0 text-center small text-body-secondary">
            No account? <Link to="/register">Sign up</Link>
          </p>
        </Card.Body>
      </Card>
    </main>
  )
}
