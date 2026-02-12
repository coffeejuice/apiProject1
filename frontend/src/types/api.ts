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

export interface RegisterRequest {
  login: string
  email: string
  password: string
}

export interface User {
  user_id: number
  login: string
  email: string
}

// Projects
export interface Project {
  id: string
  project_id?: number
  user_id: number
  material_id?: number | null
  name: string
  notes?: string | null
  created_at?: string
  updated_at?: string
  deleted_at?: string | null
}

export interface ProjectListResponse {
  projects?: Project[]
  items?: Project[]
  data?: Project[]
}

export interface CreateProjectRequest {
  name: string
  notes?: string
  material_id?: number
}

// Documents
export interface Document {
  id: string
  document_id?: number
  project_id: number
  source_document_id?: number | null
  editor_user_id?: number | null
  first_block_id?: string | null
  name: string
  notes?: string | null
  created_at?: string
  updated_at?: string
  deleted_at?: string | null
}

export interface DocumentListResponse {
  documents?: Document[]
  items?: Document[]
  data?: Document[]
}

export interface CreateDocumentRequest {
  project_id: number
  name: string
  notes?: string
  source_document_id?: number
  editor_user_id?: number
}

export interface CopyDocumentRequest {
  name?: string
  notes?: string
  editor_user_id?: number
}

// Blocks
export interface BlockData {
  block_id: string
  document_id: number
  previous_block_id: string | null
  next_block_id: string | null
  block_type_id: string
  props: Record<string, any>
  is_system: boolean
  is_removable: boolean
  fixed_position: number | null
  editable_fields?: string[]
}

export interface Operation {
  op_type: 'insert_block' | 'delete_block' | 'move_block' | 'update_text' | 'update_props'
  data: Record<string, unknown>
}

export interface CommitRequest {
  ops: Operation[]
}

export interface CommitResponse {
  success: boolean
  message?: string
}

// Lineage + diff
export interface LineageNode {
  document_id: number
  source_document_id?: number | null
  name: string
  created_at: string
}

export interface DocumentLineageResponse {
  target_document_id: number
  ancestors: LineageNode[]
  descendants: LineageNode[]
}

export interface BlockDiffEntry {
  index: number
  change_type: 'added' | 'removed' | 'modified'
  left_block_id?: string | null
  right_block_id?: string | null
  left_block_type_id?: string | null
  right_block_type_id?: string | null
  left_props?: Record<string, unknown> | null
  right_props?: Record<string, unknown> | null
}

export interface DocumentDiffResponse {
  left_document_id: number
  right_document_id: number
  left_name: string
  right_name: string
  total_changes: number
  changes: BlockDiffEntry[]
}

// Edit sessions
export interface EditSession {
  session_id: string
  document_id: number
  editor_user_id: number
  started_at: string
  ended_at?: string | null
}

export interface EditSessionListResponse {
  sessions: EditSession[]
  total: number
}

// Search
export interface SearchResult {
  block_id: string
  document_id: number
  snippet: string
  block_type_id: string
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
}
