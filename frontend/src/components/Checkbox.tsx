// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Bootstrap-styled checkbox with the one thing react-bootstrap's Form.Check
// lacks: a tri-state "indeterminate" (used by the select-all header boxes).

import { useEffect, useRef } from 'react'

type CheckboxProps = {
  checked: boolean | 'indeterminate'
  onCheckedChange?: (checked: boolean) => void
  disabled?: boolean
  title?: string
  'aria-label'?: string
}

export function Checkbox({ checked, onCheckedChange, disabled, title, ...rest }: CheckboxProps) {
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (ref.current) ref.current.indeterminate = checked === 'indeterminate'
  }, [checked])

  return (
    <input
      ref={ref}
      type="checkbox"
      className="form-check-input m-0"
      checked={checked === true}
      disabled={disabled}
      title={title}
      aria-label={rest['aria-label']}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
    />
  )
}
