// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana

import { CheckCircle2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, Button, Card, Form } from 'react-bootstrap'
import { Link } from 'react-router-dom'

import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/useAuth'

export function RegisterPage() {
  const { register } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(email, password, fullName)
      // New accounts start inactive and in no department (admin-approval
      // gate) — there's nothing to sign in to yet, so show a pending-review
      // confirmation instead of navigating into the app.
      setIsSubmitted(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create your account.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSubmitted) {
    return (
      <main className="container py-5 d-flex flex-column justify-content-center" style={{ maxWidth: 460, minHeight: 'calc(100vh - var(--app-nav-height))' }}>
        <Card className="shadow">
          <Card.Body className="p-4 text-center">
            <span className="feature-icon bg-success mb-3">
              <CheckCircle2 size={22} />
            </span>
            <h1 className="h4 text-success mb-2">Account created</h1>
            <p className="text-body-secondary small">
              An admin needs to approve your account and assign you to a department before you
              can sign in. Check back once that's done.
            </p>
            <Link to="/login" className="btn btn-primary w-100">
              Back to sign in
            </Link>
          </Card.Body>
        </Card>
      </main>
    )
  }

  return (
    <main className="container py-5 d-flex flex-column justify-content-center" style={{ maxWidth: 460, minHeight: 'calc(100vh - var(--app-nav-height))' }}>
      <Card className="shadow">
        <Card.Body className="p-4">
          <div className="text-center mb-4">
            <span className="feature-icon bg-primary mb-3">
              <Sparkles size={22} />
            </span>
            <h1 className="h4 text-primary mb-1">Create an account</h1>
            <p className="text-body-secondary small mb-0">
              New accounts need admin approval and a department assignment before you can sign in.
            </p>
          </div>

          <Form onSubmit={handleSubmit} className="d-flex flex-column gap-3">
            <Form.Group controlId="fullName">
              <Form.Label>Full name</Form.Label>
              <Form.Control
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </Form.Group>
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
                minLength={8}
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
              {isSubmitting ? 'Creating account…' : 'Sign up'}
            </Button>
          </Form>

          <p className="mt-4 mb-0 text-center small text-body-secondary">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </Card.Body>
      </Card>
    </main>
  )
}
