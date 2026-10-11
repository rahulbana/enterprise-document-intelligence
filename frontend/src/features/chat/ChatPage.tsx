// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// ChatGPT-style chat: a sidebar of the user's conversations plus the active
// conversation's message thread. Sending a message streams the assistant's
// reply token-by-token over SSE (see api/chat.ts + parseSseStream), then
// reloads history from the server once the stream finishes so the shown
// state always matches what's persisted.

import 'katex/dist/katex.min.css'

import { FileSearch, Globe, MessageSquare, Paperclip, Plus, SendHorizontal, Sparkles, Wrench, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Alert, Badge, Button, Form } from 'react-bootstrap'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

import { ApiError } from '../../api/client'
import * as chatApi from '../../api/chat'
import * as documentsApi from '../../api/documents'
import { DocumentPreviewDialog } from '../../components/DocumentPreviewDialog'
import { IngestionStatusBadge } from '../../components/IngestionStatusBadge'
import type { ChatMessage, ChatSession, Citation, Document } from '../../types'
import { ACCEPTED_DOCUMENT_EXTENSIONS } from '../../utils/acceptedFileTypes'
import { parseSseStream } from '../../utils/parseSseStream'

function titleFromFilename(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  return lastDot > 0 ? filename.slice(0, lastDot) : filename
}

type ChatStreamEvent =
  | { type: 'token'; content: string }
  | { type: 'status'; message: string }
  | {
      type: 'done'
      message_id: number
      citations: Citation[]
      duration_ms: number
      tools_used: string[] | null
    }
  | { type: 'error'; message: string }

// The backend serializes datetimes without a timezone suffix (e.g.
// "2026-09-25T14:01:27", always UTC on the wire). `new Date(...)` on a
// string like that is parsed as *local* time per the ES spec, so on any
// browser not in UTC every timestamp would silently be off by the local
// offset (a session created seconds ago showing as hours old). Appending
// "Z" when there's no timezone marker already forces the correct UTC read.
function parseServerDate(iso: string): Date {
  const hasTimezone = /Z$|[+-]\d{2}:\d{2}$/.test(iso)
  return new Date(hasTimezone ? iso : `${iso}Z`)
}

function formatClockTime(iso: string): string {
  return parseServerDate(iso).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  })
}

const TOOL_STYLES: Record<string, { label: string; icon: LucideIcon; bg: string }> = {
  web_search: { label: 'Web search', icon: Globe, bg: 'primary' },
  search_documents: { label: 'Document search', icon: FileSearch, bg: 'success' },
}

const FALLBACK_TOOL_STYLE = { icon: Wrench, bg: 'warning' }

function toolStyle(name: string) {
  return TOOL_STYLES[name] ?? { label: name, ...FALLBACK_TOOL_STYLE }
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - parseServerDate(iso).getTime()
  const diffMinutes = Math.round(diffMs / 60_000)
  if (diffMinutes < 1) return 'just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.round(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`
  return parseServerDate(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`
}

export function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [streamingContent, setStreamingContent] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chatUploads, setChatUploads] = useState<Document[]>([])
  const [isAttaching, setIsAttaching] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [previewCitation, setPreviewCitation] = useState<{
    documentId: number
    chunkIndex: number
  } | null>(null)
  const dragDepthRef = useRef(0)

  function handleOpenCitation(documentId: number, chunkIndex: number) {
    setPreviewCitation({ documentId, chunkIndex })
  }
  const threadEndRef = useRef<HTMLDivElement>(null)
  const attachInputRef = useRef<HTMLInputElement>(null)

  function loadSessions() {
    chatApi
      .listSessions()
      .then(setSessions)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load chats.'))
  }

  useEffect(loadSessions, [])

  useEffect(() => {
    // Attachment chips are ephemeral UI feedback for the session that was
    // active when the upload happened — switching sessions (including
    // starting a new one) must drop them, or a document uploaded in one
    // chat keeps showing as "attached" in an unrelated one.
    setChatUploads([])
    if (activeSessionId === null) {
      setMessages([])
      return
    }
    chatApi
      .listMessages(activeSessionId)
      .then(setMessages)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Failed to load chat.'))
  }, [activeSessionId])

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  // Chat-attached uploads ingest in the background same as My Documents —
  // poll each one still pending/processing so its badge updates without a
  // manual refresh, so the user can tell when it's actually searchable.
  useEffect(() => {
    const inFlight = chatUploads.filter(
      (doc) => doc.active_version && ['pending', 'processing'].includes(doc.active_version.status),
    )
    if (inFlight.length === 0) return
    const timeoutId = setTimeout(() => {
      Promise.all(inFlight.map((doc) => documentsApi.getDocument(doc.id)))
        .then((updated) => {
          setChatUploads((prev) =>
            prev.map((doc) => updated.find((u) => u.id === doc.id) ?? doc),
          )
        })
        .catch(() => {
          /* transient — next poll retries */
        })
    }, 3000)
    return () => clearTimeout(timeoutId)
  }, [chatUploads])

  async function handleAttachFile(file: File) {
    setError(null)
    setIsAttaching(true)
    try {
      const document = await documentsApi.uploadDocument(file, {
        title: titleFromFilename(file.name),
        visibility: 'private',
      })
      setChatUploads((prev) => [document, ...prev])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to upload document.')
    } finally {
      setIsAttaching(false)
      if (attachInputRef.current) attachInputRef.current.value = ''
    }
  }

  function dismissUpload(id: number) {
    setChatUploads((prev) => prev.filter((doc) => doc.id !== id))
  }

  async function handleNewChat() {
    setError(null)
    try {
      const session = await chatApi.createSession()
      setSessions((prev) => [session, ...prev])
      setActiveSessionId(session.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start a new chat.')
    }
  }

  async function handleDeleteSession(id: number) {
    if (!confirm('Delete this conversation?')) return
    setError(null)
    try {
      await chatApi.deleteSession(id)
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSessionId === id) setActiveSessionId(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete chat.')
    }
  }

  async function handleSend(event: FormEvent) {
    event.preventDefault()
    const content = draft.trim()
    if (!content || activeSessionId === null || isStreaming) return

    setError(null)
    setDraft('')
    setMessages((prev) => [
      ...prev,
      {
        id: -1,
        role: 'user',
        content,
        citations: null,
        duration_ms: null,
        tools_used: null,
        created_at: new Date().toISOString(),
      },
    ])
    setIsStreaming(true)
    setStreamingContent('')
    setStatusMessage(null)

    try {
      const response = await chatApi.sendMessage(activeSessionId, content)
      for await (const chatEvent of parseSseStream<ChatStreamEvent>(response)) {
        if (chatEvent.type === 'token') {
          setStatusMessage(null)
          setStreamingContent((prev) => (prev ?? '') + chatEvent.content)
        } else if (chatEvent.type === 'status') {
          setStatusMessage(chatEvent.message)
        } else if (chatEvent.type === 'error') {
          setError(chatEvent.message)
        }
      }
      const refreshed = await chatApi.listMessages(activeSessionId)
      setMessages(refreshed)
      loadSessions() // updated_at changed, so ordering may too
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send message.')
    } finally {
      setIsStreaming(false)
      setStreamingContent(null)
      setStatusMessage(null)
    }
  }

  return (
    <main className="chat-layout d-flex gap-3">
      <aside className="chat-sidebar d-flex flex-column gap-2 rounded bg-white p-3 shadow-sm">
        <Button onClick={handleNewChat} className="w-100 d-inline-flex align-items-center justify-content-center gap-2">
          <Plus size={16} />
          New chat
        </Button>
        <div className="d-flex flex-column gap-1">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`session-item d-flex align-items-center justify-content-between px-3 py-2 small ${
                session.id === activeSessionId ? 'active' : ''
              }`}
            >
              <button
                onClick={() => setActiveSessionId(session.id)}
                className="btn btn-link p-0 text-start text-decoration-none d-flex align-items-center gap-2 flex-grow-1 overflow-hidden"
                style={{ color: 'inherit' }}
              >
                <MessageSquare size={14} className="flex-shrink-0 opacity-75" />
                <span className="overflow-hidden">
                  <span className="d-block text-truncate">{session.title}</span>
                  <span
                    className={`d-block ${
                      session.id === activeSessionId ? 'text-white-50' : 'text-body-secondary'
                    }`}
                    style={{ fontSize: '0.75rem' }}
                  >
                    {formatRelativeTime(session.updated_at)}
                  </span>
                </span>
              </button>
              <button
                onClick={() => handleDeleteSession(session.id)}
                className="session-delete btn btn-link p-1 ms-2 flex-shrink-0"
                style={{ color: 'inherit' }}
                aria-label="Delete conversation"
              >
                <X size={14} />
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="px-3 py-2 small text-body-secondary mb-0">No conversations yet.</p>
          )}
        </div>
      </aside>

      <section
        className="position-relative d-flex flex-column flex-grow-1 rounded bg-white shadow-sm overflow-hidden"
        style={{ minWidth: 0 }}
        onDragEnter={(e) => {
          if (activeSessionId === null || !e.dataTransfer.types.includes('Files')) return
          e.preventDefault()
          dragDepthRef.current += 1
          setIsDragOver(true)
        }}
        onDragOver={(e) => {
          if (activeSessionId === null || !e.dataTransfer.types.includes('Files')) return
          e.preventDefault()
        }}
        onDragLeave={(e) => {
          if (activeSessionId === null || !e.dataTransfer.types.includes('Files')) return
          e.preventDefault()
          dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
          if (dragDepthRef.current === 0) setIsDragOver(false)
        }}
        onDrop={(e) => {
          if (activeSessionId === null) return
          e.preventDefault()
          dragDepthRef.current = 0
          setIsDragOver(false)
          const file = e.dataTransfer.files?.[0]
          if (file) handleAttachFile(file)
        }}
      >
        {isDragOver && (
          <div className="chat-drop-overlay d-flex flex-column align-items-center justify-content-center gap-2 fw-medium">
            <Paperclip size={24} />
            Drop to upload
          </div>
        )}

        {error && (
          <Alert variant="danger" className="rounded-0 border-0 border-bottom mb-0 py-2 small">
            {error}
          </Alert>
        )}

        {activeSessionId === null ? (
          <div className="d-flex flex-grow-1 flex-column align-items-center justify-content-center gap-3 small text-body-secondary">
            <span className="feature-icon bg-primary">
              <MessageSquare size={24} />
            </span>
            Select a conversation or start a new one.
          </div>
        ) : (
          <>
            <div className="chat-thread flex-grow-1 d-flex flex-column gap-3 p-3">
              {messages.map((message) => (
                <ChatBubble key={message.id} message={message} onOpenCitation={handleOpenCitation} />
              ))}
              {streamingContent !== null && (
                <ChatBubble
                  message={{
                    id: -2,
                    role: 'assistant',
                    content: streamingContent || (statusMessage ? `_${statusMessage}_` : '…'),
                    citations: null,
                    duration_ms: null,
                    tools_used: null,
                    created_at: new Date().toISOString(),
                  }}
                  onOpenCitation={handleOpenCitation}
                />
              )}
              <div ref={threadEndRef} />
            </div>

            <div className="border-top p-3">
              {chatUploads.length > 0 && (
                <div className="d-flex flex-wrap gap-2 mb-2">
                  {chatUploads.map((doc) => (
                    <div
                      key={doc.id}
                      className="d-flex align-items-center gap-2 rounded bg-light px-2 py-1 small"
                    >
                      <Paperclip size={12} className="flex-shrink-0 text-body-secondary" />
                      <span className="text-truncate" style={{ maxWidth: 160 }}>
                        {doc.title}
                      </span>
                      {doc.active_version && <IngestionStatusBadge version={doc.active_version} />}
                      <button
                        onClick={() => dismissUpload(doc.id)}
                        className="btn btn-link btn-sm p-0 text-body-secondary"
                        aria-label="Dismiss"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <Form onSubmit={handleSend} className="d-flex gap-2">
                <input
                  ref={attachInputRef}
                  type="file"
                  accept={ACCEPTED_DOCUMENT_EXTENSIONS}
                  className="d-none"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) handleAttachFile(file)
                  }}
                />
                <Button
                  type="button"
                  variant="outline-primary"
                  disabled={isAttaching}
                  onClick={() => attachInputRef.current?.click()}
                  aria-label="Attach a document"
                >
                  <Paperclip size={16} />
                </Button>
                <Form.Control
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Ask about your documents…"
                  disabled={isStreaming}
                  className="flex-grow-1"
                />
                <Button
                  type="submit"
                  disabled={isStreaming || !draft.trim()}
                  className="d-inline-flex align-items-center gap-2"
                >
                  <SendHorizontal size={16} />
                  {isStreaming ? 'Thinking…' : 'Send'}
                </Button>
              </Form>
            </div>
          </>
        )}
      </section>

      <DocumentPreviewDialog
        documentId={previewCitation?.documentId ?? null}
        focusChunkIndex={previewCitation?.chunkIndex ?? null}
        onOpenChange={(open) => !open && setPreviewCitation(null)}
      />
    </main>
  )
}

// A single answer can cite several chunks from the same document — collapse
// those to one citation so "Sources" doesn't repeat the same title.
function dedupeCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>()
  return citations.filter((c) => {
    const key =
      c.source === 'memory'
        ? `memory:${c.session_id}`
        : c.source === 'web'
          ? `web:${c.url}`
          : `document:${c.document_id}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

// The model reliably uses LaTeX but not reliably the same delimiters —
// often \[ ... \] / \( ... \) (real example seen in production: "[
// \text{LCM of fractions} = \frac{...}{...} ]") rather than the $$ .. $$ /
// $ .. $ that remark-math actually recognizes. Normalize the backslash
// forms to dollar forms before markdown parses it, skipping fenced code
// blocks so a literal \[ in a code sample isn't rewritten.
function normalizeLatexDelimiters(content: string): string {
  return content
    .split(/(```[\s\S]*?```)/g)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : part
            .replace(/\\\[([\s\S]*?)\\\]/g, (_, expr: string) => `$$${expr}$$`)
            .replace(/\\\(([\s\S]*?)\\\)/g, (_, expr: string) => `$${expr}$`),
    )
    .join('')
}

function ChatBubble({
  message,
  onOpenCitation,
}: {
  message: ChatMessage
  onOpenCitation: (documentId: number, chunkIndex: number) => void
}) {
  const isUser = message.role === 'user'
  return (
    <div className={`d-flex align-items-start gap-2 ${isUser ? 'justify-content-end' : ''}`}>
      {!isUser && (
        <span className="chat-avatar mt-1">
          <Sparkles size={14} />
        </span>
      )}
      <div
        className={`chat-bubble px-3 py-2 small ${
          isUser ? 'chat-bubble-user' : 'chat-bubble-assistant border shadow-sm'
        }`}
      >
        <div className="markdown-body">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
            components={{
              a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
            }}
          >
            {normalizeLatexDelimiters(message.content)}
          </ReactMarkdown>
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 border-top pt-2 small text-body-secondary">
            <span className="fw-medium">Sources:</span>
            <ul className="list-unstyled mb-0 mt-1">
              {dedupeCitations(message.citations).map((c) => (
                <li
                  key={
                    c.source === 'memory'
                      ? `memory-${c.session_id}`
                      : c.source === 'web'
                        ? `web-${c.url}`
                        : `document-${c.document_id}`
                  }
                  className="text-truncate"
                >
                  {c.source === 'memory' ? (
                    'your chat history'
                  ) : c.source === 'web' ? (
                    <a href={c.url} target="_blank" rel="noopener noreferrer">
                      {c.title}
                    </a>
                  ) : (
                    <button
                      type="button"
                      onClick={() => onOpenCitation(c.document_id, c.chunk_index)}
                      className="btn btn-link btn-sm p-0 align-baseline"
                    >
                      {c.document_title ?? `Document #${c.document_id}`}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {message.tools_used && message.tools_used.length > 0 && (
          <div className="d-flex flex-wrap gap-1 mt-2">
            {message.tools_used.map((name) => {
              const style = toolStyle(name)
              const Icon = style.icon
              return (
                <Badge
                  key={name}
                  bg={style.bg}
                  className="d-inline-flex align-items-center gap-1 fw-medium"
                >
                  <Icon size={12} />
                  {style.label}
                </Badge>
              )
            })}
          </div>
        )}
        <p className={`mt-1 mb-0 ${isUser ? 'text-white-50' : 'text-body-secondary'}`} style={{ fontSize: '0.75rem' }}>
          {formatClockTime(message.created_at)}
          {message.duration_ms != null && ` · ${formatDuration(message.duration_ms)}`}
        </p>
      </div>
    </div>
  )
}
