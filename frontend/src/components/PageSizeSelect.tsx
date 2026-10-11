// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// "Rows per page" dropdown shared by every paginated table.

import { Form } from 'react-bootstrap'

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

type PageSizeSelectProps = {
  value: number
  onChange: (value: number) => void
}

export function PageSizeSelect({ value, onChange }: PageSizeSelectProps) {
  return (
    <Form.Select
      size="sm"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      aria-label="Rows per page"
      style={{ width: 'auto' }}
    >
      {PAGE_SIZE_OPTIONS.map((size) => (
        <option key={size} value={size}>
          {size} / page
        </option>
      ))}
    </Form.Select>
  )
}
