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

export type WorkflowSimulationStatus = 'stop' | 'run' | 'pause' | 'error' | 'done'

export interface DocumentWorkflowRecord {
  document_id: number
  document_version_id?: number | null
  parent_document_version_id?: number | null
  document_fixed: boolean
  workflow_state: string
  preprocess_requested: boolean
  automation_active: boolean
  is_editable?: boolean | null
  simulation_status?: WorkflowSimulationStatus | null
  document_priority_enum?: string | null
  simulation_priority?: number | null
  operations_count?: number | null
  simulation_percent?: number | null
  simulation_expected_duration_days?: number | null
  simulation_server_id?: number | null
  created_at?: string | null
  last_modified?: string | null
  ran_at?: string | null
  finished_at?: string | null
}

export interface WorkflowDocumentStatusRow {
  document_id: number
  document_name: string
  project_id: number
  project_name: string
  owner_user_id: number
  owner_login: string
  source_document_id?: number | null
  document_version_id?: number | null
  workflow_state: string
  document_fixed: boolean
  preprocess_requested: boolean
  automation_active: boolean
  is_editable?: boolean | null
  simulation_status?: WorkflowSimulationStatus | null
  simulation_priority?: number | null
  queue_position?: number | null
  operations_count?: number | null
  simulation_percent?: number | null
  last_modified?: string | null
}

export interface WorkflowDocumentStatusListResponse {
  documents: WorkflowDocumentStatusRow[]
}

export interface WorkflowSimulationStatusRow {
  document_version_id: number
  document_id: number
  document_name: string
  version_name: string
  project_id: number
  project_name: string
  owner_user_id: number
  owner_login: string
  workflow_state: string
  document_fixed: boolean
  preprocess_requested: boolean
  automation_active: boolean
  is_editable: boolean
  simulation_status: WorkflowSimulationStatus
  simulation_priority?: number | null
  queue_position?: number | null
  operations_count?: number | null
  simulation_percent?: number | null
  simulation_expected_duration_days?: number | null
  simulation_server_id?: number | null
  simulation_server_name?: string | null
  last_modified?: string | null
  ran_at?: string | null
  finished_at?: string | null
}

export interface WorkflowSimulationStatusListResponse {
  simulations: WorkflowSimulationStatusRow[]
}

export interface WorkflowSolverPcStatusRow {
  server_id: number
  name: string
  hostname: string
  ip: string
  is_active: boolean
  worker_state: 'offline' | 'idle' | 'busy' | string
  document_version_id?: number | null
  document_name?: string | null
  version_name?: string | null
  time_started?: string | null
  time_updated?: string | null
  time_finished?: string | null
  version: string
  cpu_count?: number | null
  max_threads_count?: number | null
  ram_free_size_gb?: number | null
  hdd_free_size_gb?: number | null
  timeout_counter: number
}

export interface WorkflowSolverPcStatusListResponse {
  solver_pcs: WorkflowSolverPcStatusRow[]
}

export interface WorkflowQueueRequest {
  simulation_priority?: number
  document_priority_enum?: string
}

export interface WorkflowPriorityUpdateRequest {
  simulation_priority?: number
  document_priority_enum?: string
}

export interface WorkflowSimulationReorderRequest {
  ordered_document_version_ids: number[]
}

export interface WorkflowSimulationReorderResponse {
  updated_document_version_ids: number[]
}

export interface WorkflowForkRequest {
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
  op_type: 'insert_block' | 'delete_block' | 'move_block' | 'update_props'
  data: Record<string, unknown>
}

export interface CommitRequest {
  ops: Operation[]
}

export interface CommitResponse {
  success: boolean
  message?: string
}

export interface DocumentOperationRecord {
  document_operation_id: number
  document_id: number
  source_block_id: string
  source_block_type_id: string
  operation_order: number
  operation_order_in_block: number
  operation_template_id?: string | null
  operation_kind: string
  label_snapshot?: string | null
  target: Record<string, any>
  parse_status: string
  parse_errors: Array<Record<string, any>>
  parse_warnings: Array<Record<string, any>>
}

export interface DocumentOperationListResponse {
  document_id: number
  operations: DocumentOperationRecord[]
}

// Library DB tables
export interface OperationBlockTypeRecord {
  type_id: number
  parent_type_id?: number | null
  row: number
  process_fixed_row?: number | null
  allow_copies: boolean
  text_id: string
  library_name: string
  process_name: string
  labels: string[]
  db_column_names: string[]
  foreign_keys: string[]
  is_simulation: boolean
  is_geometry: boolean
  is_die_assembly: boolean
  is_custom_die_assembly: boolean
  is_press: boolean
  is_feed: boolean
  is_top_die: boolean
  is_bottom_die: boolean
  is_speed: boolean
  is_billet_category: boolean
  is_heating_category: boolean
  is_forming_category: boolean
  is_forming_operation: boolean
  is_surface_treatment_operation: boolean
  deformation_type?: string | null
  speed_column_name?: string | null
  trigger?: string | null
  is_initialize: boolean
  is_accumulate: boolean
  is_keep: boolean
  is_obsolete: boolean
  has_children: boolean
  insertable: boolean
}

export interface OperationTemplateFieldRecord {
  path: string
  type: string
  label: string
  unit?: string | null
  default?: unknown
  options?: Array<Record<string, unknown>>
}

export interface OperationTemplateRecord {
  id: string
  version: number
  label: string
  display_name: string
  category: string
  operation_kind: string
  compiler_handler: string
  insertable: boolean
  materialize: boolean
  target_schema: OperationTemplateFieldRecord[]
}

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

export interface MaterialStandardCatalogItemRecord {
  standard_id: number
  standard_number: string
  issue_organization?: string | null
  country_or_region?: string | null
  geographic_level?: string | null
  label: string
}

export interface MaterialWorkspaceDesignationRecord {
  designation_id: number
  designation: string
  standard_id?: number | null
  standard_label?: string | null
  country?: string | null
  note?: string | null
  is_main_designation: boolean
}

export interface MaterialWorkspaceTestRecordSummaryRecord {
  test_record_id: number
  designation_id?: number | null
  designation?: string | null
  publication_id?: number | null
  publication_title?: string | null
  heat_number?: string | null
  batch_number?: string | null
  sample_label?: string | null
  note?: string | null
  chemistry_results_count: number
  property_tables_count: number
}

export interface MaterialWorkspaceRecord {
  material_id: number
  name: string
  deform_file_name?: string | null
  note?: string | null
  classifications: Record<string, string[]>
  designations: MaterialWorkspaceDesignationRecord[]
  test_records: MaterialWorkspaceTestRecordSummaryRecord[]
  is_obsolete: boolean
  owner_id?: number | null
}

export interface MaterialWorkspaceDesignationInput {
  designation_id?: number | null
  designation: string
  standard_id?: number | null
  note?: string | null
  is_main_designation: boolean
}

export interface MaterialWorkspaceUpsertRequest {
  name: string
  deform_file_name?: string | null
  note?: string | null
  classifications: Record<string, string[]>
  designations: MaterialWorkspaceDesignationInput[]
  is_obsolete: boolean
}

export interface MaterialCopyRequest {
  source_material_id: number
  target_material_id: number
  copy_identity_fields: string[]
  copy_classifications: boolean
  replace_classifications: boolean
  copy_designations: boolean
  designation_ids: number[]
  replace_designations: boolean
  copy_test_records: boolean
  test_record_ids: number[]
}

export interface MaterialCopyResponse {
  target_material_id: number
  copied_identity_fields: string[]
  copied_designations_count: number
  copied_test_records_count: number
  copied_classification_assignments_count: number
}

export interface MaterialDeleteRequest {
  material_ids: number[]
}

export interface MaterialDeleteResponse {
  deleted_material_ids: number[]
  deleted_count: number
}

export interface MaterialDeformFileUploadResponse {
  file_name: string
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
  classification_path?: string | null
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
  classification_path?: string | null
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
