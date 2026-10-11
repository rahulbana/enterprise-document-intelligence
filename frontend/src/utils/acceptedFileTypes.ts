// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Extensions the backend's parser factory actually registers (see
// backend/app/ingestion/parsers/factory.py) — kept in one place since every
// upload entry point (My Documents, Department Documents, chat attach) needs
// the same `accept` value.

export const ACCEPTED_DOCUMENT_EXTENSIONS =
  '.pdf,.docx,.rtf,.odt,.txt,.md,.markdown,.htm,.html,.xhtml,.mhtml,.mht,.xml,.epub,.json,.yaml,.yml,.pptx,.ppsx,.odp,.xlsx,.xlsm,.xls,.csv,.tsv,.ods,.jsonl,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.gif,.heic,.eml,.msg,.mbox,.pst'
