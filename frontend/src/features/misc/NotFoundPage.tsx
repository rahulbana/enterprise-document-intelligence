// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence

import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main
      className="container d-flex flex-column align-items-center justify-content-center gap-3 text-center"
      style={{ maxWidth: 460, minHeight: 'calc(100vh - var(--app-nav-height))' }}
    >
      <span className="feature-icon bg-primary">
        <Compass size={22} />
      </span>
      <h1 className="h3 text-primary mb-0">Page not found</h1>
      <p className="text-body-secondary mb-0">The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn btn-primary mt-2">
        Back to home
      </Link>
    </main>
  )
}
