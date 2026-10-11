// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Reads a fetch Response's body as newline-delimited SSE "data: {json}"
// events and yields each parsed payload. Good enough for our single-event-
// type-per-line backend (see chat_service._sse_event) — not a full SSE
// parser (no "event:"/"id:"/retry handling, since we don't send those).

export async function* parseSseStream<T>(response: Response): AsyncGenerator<T> {
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          yield JSON.parse(line.slice('data: '.length)) as T
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
