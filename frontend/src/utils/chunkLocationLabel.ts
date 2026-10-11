// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
// Repo: https://github.com/rahulbana/enterprise-document-intelligence
//
// Mirrors chat_service._location_label (backend) so a chunk's label reads
// the same in the document preview pane as it does in a chat citation.

export function chunkLocationLabel(metadata: Record<string, unknown>): string | null {
  let label: string
  if ('page' in metadata) {
    label = `page ${metadata.page}`
  } else if ('slide' in metadata) {
    label = `slide ${metadata.slide}`
  } else if ('sheet' in metadata) {
    label = `sheet '${metadata.sheet}'`
  } else if ('heading' in metadata && metadata.heading) {
    label = `section '${metadata.heading}'`
  } else if ('folder' in metadata) {
    label = `folder '${metadata.folder}'`
  } else if ('path' in metadata) {
    label = `element ${metadata.path}`
  } else {
    return null
  }

  const kind = metadata.kind
  if (kind && !['text', 'sheet', 'body'].includes(String(kind))) {
    label += ` (${kind})`
  }
  return label
}
