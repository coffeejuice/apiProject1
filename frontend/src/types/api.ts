// API Response Types
export interface ApiResponse<T = unknown> {
  ok: boolean
  status: number
  data?: T
  errorMessage?: string
  errorCode?: string
}

// Auth
export interface LoginRequest {
  login: string
  password: string
}

export interface LoginResponse {
  access_token?: string
  token?: string
  accessToken?: string
}

export interface User {
  id: string
  username?: string
  login?: string
  email?: string
}

// Documents
export interface Document {
  id: string | number
  process_id?: number  // Backend field name
  title: string
  created_at?: string
  updated_at?: string
  deleted_at?: string | null
  rev_number?: number
  content?: unknown
}

export interface DocumentListResponse {
  items?: Document[]
  documents?: Document[]
  data?: Document[]
  cursor?: string
  has_more?: boolean
}

export interface CreateDocumentRequest {
  title: string
}

// Operations
export interface Operation {
  op_type: 'insert_block' | 'delete_block' | 'move_block' | 'update_text' | 'update_props'
  data: Record<string, unknown>
}

export interface CommitRequest {
  device_id: string
  base_rev_number: number
  client_batch_id: string
  ops: Operation[]
}

export interface CommitResponse {
  success: boolean
  new_rev_number: number
  conflicts?: unknown[]
}

// Revisions
export interface Revision {
  id: string
  rev_number: number
  created_at: string
  device_id?: string
  operations?: Operation[]
}

export interface RevisionListResponse {
  items?: Revision[]
  revisions?: Revision[]
  data?: Revision[]
}

// Search
export interface SearchResult {
  block_id: string
  process_id: number
  snippet: string
  block_type: string
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
}

// Import/Export
export interface ImportRequest {
  title: string
  content_markdown: string
}
