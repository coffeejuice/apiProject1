from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.document.document import Role
from app.models.library.library_item import LibraryType
from app.models.settings import SettingScope


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


class LibraryDbDieTypeResponse(BaseModel):
    id: int
    name: Any

    class Config:
        from_attributes = True


class LibraryDbMaterialResponse(BaseModel):
    material_id: int
    name: Any
    source: str
    source_version: str
    file_name: str
    properties: Any
    is_obsolete: bool
    created_at: datetime
    obsolete_at: Optional[datetime]
    owner_id: Optional[int]

    class Config:
        from_attributes = True


class LibraryDbDieResponse(BaseModel):
    id: int
    name: Any
    die_type_id: int
    owner_user_id: Optional[int]
    die_template_file_name: Optional[str]
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
