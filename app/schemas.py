from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from app.models import BlockType, Role, OperationType

# Auth schemas
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: UUID
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Document schemas
class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)

class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)

class DocumentResponse(BaseModel):
    document_id: UUID
    owner_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
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
    document_id: UUID
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
    document_id: UUID
    rev_number: int
    created_at: datetime
    created_by: UUID

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
    user_id: UUID
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
    document_id: UUID
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
