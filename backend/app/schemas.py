from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.document.document import Role, SimulationStatus
from app.models.library.library_item import LibraryType
from app.models.settings import SettingScope
from app.models.user import UserPriority


# Auth schemas
class UserRegister(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    login: str
    password: str


class UserResponse(BaseModel):
    user_id: int
    login: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# Project schemas
class ProjectCreate(BaseModel):
    material_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=1024)
    notes: Optional[str] = None


class ProjectUpdate(BaseModel):
    material_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    notes: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: int
    user_id: int
    material_id: Optional[int]
    name: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int


# Document schemas
class DocumentCreate(BaseModel):
    project_id: int
    source_document_id: Optional[int] = None
    editor_user_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=1024)
    notes: Optional[str] = None


class DocumentUpdate(BaseModel):
    editor_user_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=1024)
    notes: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: int
    project_id: int
    source_document_id: Optional[int]
    editor_user_id: Optional[int]
    first_block_id: Optional[UUID]
    material_version_id: Optional[int] = None
    name: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class DocumentCopyRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=1024)
    notes: Optional[str] = None
    editor_user_id: Optional[int] = None


class DocumentLineageNode(BaseModel):
    document_id: int
    source_document_id: Optional[int]
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentLineageResponse(BaseModel):
    target_document_id: int
    ancestors: List[DocumentLineageNode]
    descendants: List[DocumentLineageNode]


class BlockDiffEntry(BaseModel):
    index: int
    change_type: str  # added | removed | modified
    left_block_id: Optional[UUID] = None
    right_block_id: Optional[UUID] = None
    left_block_type_id: Optional[str] = None
    right_block_type_id: Optional[str] = None
    left_props: Optional[Dict[str, Any]] = None
    right_props: Optional[Dict[str, Any]] = None


class DocumentDiffResponse(BaseModel):
    left_document_id: int
    right_document_id: int
    left_name: str
    right_name: str
    total_changes: int
    changes: List[BlockDiffEntry]


class DocumentWorkflowResponse(BaseModel):
    document_id: int
    document_version_id: Optional[int] = None
    parent_document_version_id: Optional[int] = None
    document_fixed: bool
    workflow_state: str
    preprocess_requested: bool
    automation_active: bool
    is_editable: Optional[bool] = None
    simulation_status: Optional[SimulationStatus] = None
    document_priority_enum: Optional[UserPriority] = None
    simulation_priority: Optional[int] = None
    operations_count: Optional[int] = None
    simulation_percent: Optional[int] = None
    simulation_expected_duration_days: Optional[float] = None
    simulation_server_id: Optional[int] = None
    created_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    ran_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class DocumentQueueRequest(BaseModel):
    simulation_priority: Optional[int] = Field(default=None, ge=1, le=32767)
    document_priority_enum: Optional[UserPriority] = None


class DocumentVersionPriorityUpdate(BaseModel):
    simulation_priority: Optional[int] = Field(default=None, ge=1, le=32767)
    document_priority_enum: Optional[UserPriority] = None


class DocumentForkRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=1024)
    notes: Optional[str] = None
    editor_user_id: Optional[int] = None


class WorkflowDocumentStatusRow(BaseModel):
    document_id: int
    document_name: str
    project_id: int
    project_name: str
    owner_user_id: int
    owner_login: str
    source_document_id: Optional[int] = None
    document_version_id: Optional[int] = None
    workflow_state: str
    document_fixed: bool
    preprocess_requested: bool
    automation_active: bool
    is_editable: Optional[bool] = None
    simulation_status: Optional[SimulationStatus] = None
    simulation_priority: Optional[int] = None
    queue_position: Optional[int] = None
    operations_count: Optional[int] = None
    simulation_percent: Optional[int] = None
    last_modified: Optional[datetime] = None


class WorkflowSimulationStatusRow(BaseModel):
    document_version_id: int
    document_id: int
    document_name: str
    version_name: str
    project_id: int
    project_name: str
    owner_user_id: int
    owner_login: str
    workflow_state: str
    document_fixed: bool
    preprocess_requested: bool
    automation_active: bool
    is_editable: bool
    simulation_status: SimulationStatus
    simulation_priority: Optional[int] = None
    queue_position: Optional[int] = None
    operations_count: Optional[int] = None
    simulation_percent: Optional[int] = None
    simulation_expected_duration_days: Optional[float] = None
    simulation_server_id: Optional[int] = None
    simulation_server_name: Optional[str] = None
    last_modified: Optional[datetime] = None
    ran_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class WorkflowSolverPcStatusRow(BaseModel):
    server_id: int
    name: str
    hostname: str
    ip: str
    is_active: bool
    worker_state: str
    document_version_id: Optional[int] = None
    document_name: Optional[str] = None
    version_name: Optional[str] = None
    time_started: Optional[datetime] = None
    time_updated: Optional[datetime] = None
    time_finished: Optional[datetime] = None
    version: str
    cpu_count: Optional[int] = None
    max_threads_count: Optional[int] = None
    ram_free_size_gb: Optional[float] = None
    hdd_free_size_gb: Optional[float] = None
    timeout_counter: int


class WorkflowDocumentStatusListResponse(BaseModel):
    documents: List[WorkflowDocumentStatusRow]


class WorkflowSimulationStatusListResponse(BaseModel):
    simulations: List[WorkflowSimulationStatusRow]


class WorkflowSolverPcStatusListResponse(BaseModel):
    solver_pcs: List[WorkflowSolverPcStatusRow]


class WorkflowSimulationReorderRequest(BaseModel):
    ordered_document_version_ids: List[int]


class WorkflowSimulationReorderResponse(BaseModel):
    updated_document_version_ids: List[int]


# Block schemas
class BlockResponse(BaseModel):
    block_id: UUID
    document_id: int
    previous_block_id: Optional[UUID]
    next_block_id: Optional[UUID]
    block_type_id: str
    props: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    is_system: bool
    is_removable: bool
    fixed_position: Optional[int]
    editable_fields: Optional[List[str]] = None
    field_limits: Optional[Dict[str, int]] = None

    class Config:
        from_attributes = True


class BlockCreate(BaseModel):
    block_type_id: str = Field(min_length=1, max_length=100)
    props: Dict[str, Any] = Field(default_factory=dict)
    previous_block_id: Optional[UUID] = None


class BlockUpdate(BaseModel):
    props: Dict[str, Any]


class BlockMove(BaseModel):
    previous_block_id: Optional[UUID] = None


# Document edit sessions
class EditSessionStartRequest(BaseModel):
    editor_user_id: Optional[int] = None


class EditSessionResponse(BaseModel):
    session_id: UUID
    document_id: int
    editor_user_id: int
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class EditSessionListResponse(BaseModel):
    sessions: List[EditSessionResponse]
    total: int


# Operations (revision-free commit)
class OperationPayload(BaseModel):
    op_type: str
    data: Dict[str, Any]


class CommitRequest(BaseModel):
    ops: List[OperationPayload]


class CommitResponse(BaseModel):
    success: bool
    message: Optional[str] = None


# Sharing schemas (kept for compatibility)
class InviteRequest(BaseModel):
    email: str
    role: Role


class ACLResponse(BaseModel):
    acl_id: UUID
    user_id: int
    role: Role
    created_at: datetime

    class Config:
        from_attributes = True


class ShareLinkResponse(BaseModel):
    link_id: UUID
    token: str
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


# Search schemas
class SearchResult(BaseModel):
    block_id: UUID
    document_id: int
    snippet: str
    block_type_id: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int


# Import/Export schemas
class ExportResponse(BaseModel):
    markdown: str


class ImportRequest(BaseModel):
    project_id: int
    name: str
    markdown: str


# Setting schemas
class SettingBase(BaseModel):
    key: str = Field(min_length=1, max_length=255)
    value: Any
    scope: SettingScope = SettingScope.GLOBAL
    user_id: Optional[int] = None


class SettingCreate(SettingBase):
    pass


class SettingUpdate(BaseModel):
    value: Any


class SettingResponse(SettingBase):
    setting_id: int

    class Config:
        from_attributes = True


class LibraryListItemResponse(BaseModel):
    id: int
    parent_id: Optional[int]
    name: str

    class Config:
        from_attributes = True


class LibraryResponse(LibraryListItemResponse):
    type: LibraryType
    props: Any
    created_at: datetime
    updated_at: datetime
    is_obsolete: bool

    class Config:
        from_attributes = True


class LibraryDbUserResponse(BaseModel):
    user_id: int
    login: str
    full_name: Optional[str]

    class Config:
        from_attributes = True


class OperationTemplateFieldResponse(BaseModel):
    path: str
    type: str = "string"
    label: str
    unit: Optional[str] = None
    default: Any = None
    options: List[Dict[str, Any]] = Field(default_factory=list)


class OperationTemplateResponse(BaseModel):
    id: str
    version: int
    label: str
    display_name: str
    category: str
    operation_kind: str
    compiler_handler: str
    insertable: bool = True
    materialize: bool = True
    target_schema: List[OperationTemplateFieldResponse] = Field(default_factory=list)


class LibraryDbDieTypeResponse(BaseModel):
    id: int
    name: Any

    class Config:
        from_attributes = True


class LibraryDbMaterialResponse(BaseModel):
    material_id: int
    name: str
    deform_file_name: Optional[str]
    note: Optional[str]
    classifications: Dict[str, List[str]] = Field(default_factory=dict)
    designations: List[str] = Field(default_factory=list)
    standards: List[str] = Field(default_factory=list)
    designation_links: List["MaterialDesignationLinkResponse"] = Field(default_factory=list)
    test_records_count: int = 0
    is_obsolete: bool
    owner_id: Optional[int]

    class Config:
        from_attributes = True


class MaterialDesignationLinkResponse(BaseModel):
    designation: str
    standard: Optional[str] = None
    country: Optional[str] = None
    chemistry_limits: Dict[str, str] = Field(default_factory=dict)
    is_main_designation: bool = False


class MaterialStandardCatalogItemResponse(BaseModel):
    standard_id: int
    standard_number: str
    issue_organization: Optional[str] = None
    country_or_region: Optional[str] = None
    geographic_level: Optional[str] = None
    label: str


class MaterialWorkspaceDesignationResponse(BaseModel):
    designation_id: int
    designation: str
    standard_id: Optional[int] = None
    standard_label: Optional[str] = None
    country: Optional[str] = None
    note: Optional[str] = None
    is_main_designation: bool = False


class MaterialWorkspaceTestRecordSummaryResponse(BaseModel):
    test_record_id: int
    designation_id: Optional[int] = None
    designation: Optional[str] = None
    publication_id: Optional[int] = None
    publication_title: Optional[str] = None
    heat_number: Optional[str] = None
    batch_number: Optional[str] = None
    sample_label: Optional[str] = None
    note: Optional[str] = None
    chemistry_results_count: int = 0
    property_tables_count: int = 0


class MaterialWorkspaceResponse(BaseModel):
    material_id: int
    name: str
    deform_file_name: Optional[str] = None
    note: Optional[str] = None
    classifications: Dict[str, List[str]] = Field(default_factory=dict)
    designations: List[MaterialWorkspaceDesignationResponse] = Field(default_factory=list)
    test_records: List[MaterialWorkspaceTestRecordSummaryResponse] = Field(default_factory=list)
    is_obsolete: bool = False
    owner_id: Optional[int] = None


class MaterialWorkspaceDesignationInput(BaseModel):
    designation_id: Optional[int] = None
    designation: str = Field(min_length=1, max_length=255)
    standard_id: Optional[int] = None
    note: Optional[str] = None
    is_main_designation: bool = False


class MaterialWorkspaceUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=1023)
    deform_file_name: Optional[str] = Field(default=None, max_length=1023)
    note: Optional[str] = None
    classifications: Dict[str, List[str]] = Field(default_factory=dict)
    designations: List[MaterialWorkspaceDesignationInput] = Field(default_factory=list)
    is_obsolete: bool = False


class MaterialCopyRequest(BaseModel):
    source_material_id: int
    target_material_id: int
    copy_identity_fields: List[str] = Field(default_factory=list)
    copy_classifications: bool = False
    replace_classifications: bool = False
    copy_designations: bool = False
    designation_ids: List[int] = Field(default_factory=list)
    replace_designations: bool = False
    copy_test_records: bool = False
    test_record_ids: List[int] = Field(default_factory=list)


class MaterialCopyResponse(BaseModel):
    target_material_id: int
    copied_identity_fields: List[str] = Field(default_factory=list)
    copied_designations_count: int = 0
    copied_test_records_count: int = 0
    copied_classification_assignments_count: int = 0


class MaterialDeleteRequest(BaseModel):
    material_ids: List[int] = Field(min_length=1)


class MaterialDeleteResponse(BaseModel):
    deleted_material_ids: List[int] = Field(default_factory=list)
    deleted_count: int = 0


class MaterialDeformFileUploadResponse(BaseModel):
    file_name: str


class MaterialVisualAxisResponse(BaseModel):
    key: str
    label: str
    unit: Optional[str] = None


class MaterialVisualPointResponse(BaseModel):
    x: float
    y: float


class MaterialVisualSeriesResponse(BaseModel):
    key: str
    label: str
    points: List[MaterialVisualPointResponse]


class MaterialVisualDiagramResponse(BaseModel):
    key: str
    title: str
    kind: str
    x_axis: MaterialVisualAxisResponse
    y_axis: MaterialVisualAxisResponse
    series: List[MaterialVisualSeriesResponse]
    controls: Optional[Dict[str, Any]] = None


class LibraryDbMaterialVisualResponse(BaseModel):
    material_id: int
    source: str
    file_name: str
    diagrams: List[MaterialVisualDiagramResponse]


class MaterialClassificationValueResponse(BaseModel):
    value_id: int
    axis_id: int
    key: str
    name: Any
    color: Optional[str]
    sort_order: int
    is_obsolete: bool
    created_at: datetime
    created_by_user_id: Optional[int]

    class Config:
        from_attributes = True


class MaterialClassificationAxisResponse(BaseModel):
    axis_id: int
    key: str
    name: Any
    description: Optional[Any]
    selection_mode: str
    hierarchy_level: int
    sort_order: int
    is_filter_visible: bool
    is_obsolete: bool
    created_at: datetime
    created_by_user_id: Optional[int]
    values: List[MaterialClassificationValueResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class LibraryDbMaterialClassificationResponse(BaseModel):
    axes: List[MaterialClassificationAxisResponse] = Field(default_factory=list)


class LibraryDbDieResponse(BaseModel):
    id: int
    name: Any
    die_type_id: int
    owner_user_id: Optional[int]
    die_template_file_name: Optional[str]
    classification_path: Optional[str] = None
    stl_file_name: Optional[str] = None
    stl_file_url: Optional[str] = None
    stl_file_exists: bool = False
    inventory_number: Optional[str]
    properties: Optional[Any]
    is_obsolete: bool
    created_at: datetime
    obsolete_at: Optional[datetime]

    class Config:
        from_attributes = True


class LibraryDbDieAssemblyResponse(BaseModel):
    id: int
    name: Any
    owner_user_id: Optional[int]
    top_die_id: Optional[int]
    bottom_die_id: Optional[int]
    left_die_id: Optional[int]
    right_die_id: Optional[int]
    classification_path: Optional[str] = None
    is_obsolete: Optional[bool]
    created_at: datetime
    obsolete_at: Optional[datetime]

    class Config:
        from_attributes = True


class LibraryDbPressResponse(BaseModel):
    id: int
    owner_user_id: Optional[int]
    name: Any
    is_obsolete: bool
    created_at: datetime
    obsolete_at: Optional[datetime]

    class Config:
        from_attributes = True


class LibraryDbPressModeResponse(BaseModel):
    id: int
    press_id: Optional[int]
    owner_user_id: Optional[int]
    name: Optional[Any]
    properties: Dict[str, Any]
    is_default_press_mode: bool
    is_obsolete: bool
    created_at: datetime
    obsolete_at: Optional[datetime]

    class Config:
        from_attributes = True
