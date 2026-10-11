// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Text filter with a leading magnifier icon, shared by every list screen.

import { Search } from 'lucide-react'
import { Form, InputGroup } from 'react-bootstrap'

type SearchInputProps = {
  value: string
  onChange: (value: string) => void
  placeholder: string
}

export function SearchInput({ value, onChange, placeholder }: SearchInputProps) {
  return (
    <InputGroup size="sm" style={{ maxWidth: 320 }}>
      <InputGroup.Text className="bg-white">
        <Search size={14} className="text-body-secondary" />
      </InputGroup.Text>
      <Form.Control
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
    </InputGroup>
  )
}
