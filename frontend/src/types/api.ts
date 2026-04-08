/* eslint-disable @typescript-eslint/no-explicit-any */

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

export interface SeedRunSummary {
  id: number
  seed_name: string
  file_hash: string
  status: string
  started_at?: string | null
  finished_at?: string | null
  details?: Record<string, unknown> | null
}

export interface SetupStatusResponse {
  file_exists: boolean
  file_path: string
  file_hash: string | null
  counts: Record<string, number>
  needs_seed: boolean
  is_seeded: boolean
  can_seed_without_auth: boolean
  last_run?: SeedRunSummary | null
}

export interface SeedLibraryResponse {
  ok: boolean
  run_id: number
  file_hash: string
  tables_processed: Record<string, number>
  only_missing: boolean
}

export interface ResetAdminPasswordRequest {
  new_password: string
}

export interface ResetAdminPasswordResponse {
  ok: boolean
  user_id: number
  login: string
  message: string
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
  field_limits?: Record<string, number>
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

// Library DB tables
export interface LibraryDbUserRecord {
  user_id: number
  login: string
  full_name?: string | null
}

export interface DieTypeRecord {
  id: number
  name: unknown
}

export interface MaterialRecord {
  material_id: number
  name: string
  deform_file_name?: string | null
  note?: string | null
  classifications: Record<string, string[]>
  designations: string[]
  standards: string[]
  designation_links: MaterialDesignationLinkRecord[]
  test_records_count: number
  is_obsolete: boolean
  owner_id?: number | null
}

export interface MaterialDesignationLinkRecord {
  designation: string
  standard?: string | null
  country?: string | null
  chemistry_limits: Record<string, string>
  is_main_designation: boolean
}

export interface MaterialClassificationValueRecord {
  value_id: number
  axis_id: number
  key: string
  name: unknown
  color?: string | null
  sort_order: number
  is_obsolete: boolean
  created_at: string
  created_by_user_id?: number | null
}

export interface MaterialClassificationAxisRecord {
  axis_id: number
  key: string
  name: unknown
  description?: unknown | null
  selection_mode: string
  hierarchy_level: number
  sort_order: number
  is_filter_visible: boolean
  is_obsolete: boolean
  created_at: string
  created_by_user_id?: number | null
  values: MaterialClassificationValueRecord[]
}

export interface MaterialClassificationCatalogRecord {
  axes: MaterialClassificationAxisRecord[]
}

export interface MaterialVisualAxisRecord {
  key: string
  label: string
  unit?: string | null
}

export interface MaterialVisualPointRecord {
  x: number
  y: number
}

export interface MaterialVisualSeriesRecord {
  key: string
  label: string
  points: MaterialVisualPointRecord[]
}

export interface MaterialVisualDiagramRecord {
  key: string
  title: string
  kind: string
  x_axis: MaterialVisualAxisRecord
  y_axis: MaterialVisualAxisRecord
  series: MaterialVisualSeriesRecord[]
  controls?: Record<string, unknown> | null
}

export interface MaterialVisualRecord {
  material_id: number
  source: string
  file_name: string
  diagrams: MaterialVisualDiagramRecord[]
}

export interface DieRecord {
  id: number
  name: unknown
  die_type_id: number
  owner_user_id?: number | null
  die_template_file_name?: string | null
  stl_file_name?: string | null
  stl_file_url?: string | null
  stl_file_exists?: boolean
  inventory_number?: string | null
  properties?: unknown
  is_obsolete: boolean
  created_at: string
  obsolete_at?: string | null
}

export interface DieAssemblyRecord {
  id: number
  name: unknown
  owner_user_id?: number | null
  top_die_id?: number | null
  bottom_die_id?: number | null
  left_die_id?: number | null
  right_die_id?: number | null
  is_obsolete?: boolean | null
  created_at: string
  obsolete_at?: string | null
}

export interface PressRecord {
  id: number
  owner_user_id?: number | null
  name: unknown
  is_obsolete: boolean
  created_at: string
  obsolete_at?: string | null
}

export interface PowerLimitPoint {
  id?: number | null
  force?: number | null
  speed?: number | null
}

export interface PressModeRecord {
  id: number
  press_id?: number | null
  owner_user_id?: number | null
  name?: unknown
  properties: Record<string, unknown>
  is_default_press_mode: boolean
  is_obsolete: boolean
  created_at: string
  obsolete_at?: string | null
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
