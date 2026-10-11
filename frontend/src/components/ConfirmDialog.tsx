// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Shared destructive-action confirmation dialog — replaces window.confirm()
// across the delete flows (documents, departments) with something that
// matches the rest of the UI.

import { Button, Modal } from 'react-bootstrap'

type ConfirmDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm: () => void
  confirmLabel?: string
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  confirmLabel = 'Delete',
}: ConfirmDialogProps) {
  return (
    <Modal show={open} onHide={() => onOpenChange(false)} centered>
      <Modal.Header closeButton>
        <Modal.Title as="h5">{title}</Modal.Title>
      </Modal.Header>
      <Modal.Body className="text-body-secondary">{description}</Modal.Body>
      <Modal.Footer>
        <Button variant="light" onClick={() => onOpenChange(false)}>
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={() => {
            onConfirm()
            onOpenChange(false)
          }}
        >
          {confirmLabel}
        </Button>
      </Modal.Footer>
    </Modal>
  )
}
