// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Delays reflecting a fast-changing value (a search input) until it's been
// stable for `delayMs` — used so typing a search query doesn't fire a
// request per keystroke.

import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timeoutId)
  }, [value, delayMs])

  return debounced
}
