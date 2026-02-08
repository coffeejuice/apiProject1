from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models.document.block import BlockType, FeedDirection
from pydantic import RootModel
from app.models.document.document import Role, Status
from app.models.document.revision import OperationType

# Auth schemas
class FeedDirectionInfo(RootModel):
    root: FeedDirection = Field(
        description="Left: -X direction, Right: +X direction, Alternating: -X first, then reverse"
    )

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

# Document schemas
class DocumentCreate(BaseModel):
    user_id: Optional[int] = None
    material_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=1024)

class DocumentUpdate(BaseModel):
    user_id: Optional[int] = None
    material_id: Optional[int] = None
    title: Optional[str] = Field(None, min_length=1, max_length=1024)

class DocumentResponse(BaseModel):
    document_id: int
    user_id: Optional[int]
    material_id: Optional[int]
    title: str
    created_at: datetime
    last_edit_at: datetime
    deleted_at: Optional[datetime]
    current_rev_number: int

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int

# Block schemas
class BlockResponse(BaseModel):
    block_id: UUID
    document_id: int
    parent_block_id: Optional[UUID]
    order_key: str
    block_type: BlockType
    text: str
    props: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Operation schemas
class InsertBlockOp(BaseModel):
    block_id: UUID
    parent_block_id: Optional[UUID]
    order_key: str
    block_type: BlockType
    text: str = ""
    props: Dict[str, Any] = Field(default_factory=dict)

class DeleteBlockOp(BaseModel):
    block_id: UUID

class MoveBlockOp(BaseModel):
    block_id: UUID
    parent_block_id: Optional[UUID]
    order_key: str

class UpdateTextOp(BaseModel):
    block_id: UUID
    text: str

class UpdatePropsOp(BaseModel):
    block_id: UUID
    props: Dict[str, Any]

class OpData(BaseModel):
    op_type: OperationType
    data: Dict[str, Any]

class CommitRequest(BaseModel):
    device_id: UUID
    base_rev_number: int
    client_batch_id: UUID
    ops: List[OpData]

class ConflictInfo(BaseModel):
    block_id: UUID
    field: str
    server_value: Any
    client_value: Any

class CommitResponse(BaseModel):
    success: bool
    new_rev_number: Optional[int]
    conflicts: Optional[List[ConflictInfo]]

# Revision schemas
class RevisionResponse(BaseModel):
    revision_id: UUID
    document_id: int
    rev_number: int
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True

class RevisionListResponse(BaseModel):
    revisions: List[RevisionResponse]
    total: int

# Sharing schemas
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
    block_type: BlockType

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int

# Import/Export schemas
class ExportResponse(BaseModel):
    markdown: str

class ImportRequest(BaseModel):
    title: str
    markdown: str

class DiffResponse(BaseModel):
    from_rev: int
    to_rev: int
    changes: List[Dict[str, Any]]

# Setting schemas
from app.models.settings import SettingScope

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
