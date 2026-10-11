// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Styled replacement for a bare <input type="file"> — click-to-browse or
// drag-and-drop, selected filename shown with a remove button instead of
// the browser's native "Choose file / No file chosen" chrome. The native
// input still backs it (for real drag/drop + picker behavior); only its
// default rendering is hidden.

import { Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from 'react-bootstrap'

type FileDropZoneProps = {
  accept: string
  file: File | null
  onFileSelected: (file: File | null) => void
  disabled?: boolean
  helperText?: string
}

export function FileDropZone({
  accept,
  file,
  onFileSelected,
  disabled,
  helperText,
}: FileDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  // The native input can't be set to a specific File programmatically, but
  // it can be cleared — needed so a parent's post-submit `setFile(null)`
  // actually lets the same filename be re-selected afterward.
  useEffect(() => {
    if (file === null && inputRef.current) inputRef.current.value = ''
  }, [file])

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragOver(false)
        if (disabled) return
        onFileSelected(e.dataTransfer.files?.[0] ?? null)
      }}
      className={`file-drop-zone d-flex align-items-center gap-3 px-3 py-2 small ${
        isDragOver ? 'dragging' : ''
      } ${disabled ? 'opacity-50' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        disabled={disabled}
        className="d-none"
        onChange={(e) => onFileSelected(e.target.files?.[0] ?? null)}
      />
      <Button
        type="button"
        variant="outline-primary"
        size="sm"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="flex-shrink-0 d-inline-flex align-items-center gap-1"
      >
        <Upload size={14} />
        Choose file
      </Button>
      {file ? (
        <div className="d-flex align-items-center gap-2 flex-grow-1 overflow-hidden">
          <span className="text-truncate">{file.name}</span>
          <button
            type="button"
            onClick={() => onFileSelected(null)}
            disabled={disabled}
            className="btn btn-link btn-sm p-0 text-danger flex-shrink-0"
            aria-label="Remove selected file"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <span className="flex-grow-1 text-truncate text-body-secondary">
          {helperText ?? 'or drag and drop a file here'}
        </span>
      )}
    </div>
  )
}
