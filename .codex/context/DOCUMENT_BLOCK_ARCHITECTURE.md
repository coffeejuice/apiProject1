---
apply: always
---

# Document and Block Architecture

## Scope
This file is the source of truth for document/block architecture, block types, and block behavior.

## Current hierarchy
- Product data flow is `Project -> Document -> Block`.
- Documents are project-scoped (`documents.project_id` is required).
- Block ordering is linked-list based (no `order_key`, no block tree).

## Document model (`backend/app/models/document/document.py`)
- Table: `documents`
- Primary key: `document_id` (BigInteger)
- Core fields:
  - `project_id` (required FK to `projects.project_id`)
  - `source_document_id` (nullable self-reference for copy lineage)
  - `editor_user_id` (nullable delegated editor)
  - `first_block_id` (nullable head pointer into `blocks`)
  - `name` (required)
  - `notes` (nullable)
  - `created_at`, `updated_at`
  - `deleted_at` (soft delete)
- Relationships:
  - `project`
  - `blocks`
  - `first_block`
  - `source_document` / `derived_documents`
  - `versions` (`document_versions`)
  - `edit_sessions` (`document_edit_sessions`)
  - legacy compatibility: `acl` and `share_links`

## Document access model (`backend/app/routers/document.py`)
- Access check is centralized in `check_document_access`.
- A user can access a document if:
  - user owns the parent project, or
  - user is the delegated editor (`documents.editor_user_id`).
- Project deletion hides associated documents through project lookup checks.

## Block model (`backend/app/models/document/block.py`)
- Table: `blocks`
- Primary key: `block_id` (UUID)
- Core fields:
  - `document_id`
  - `previous_block_id` (nullable UUID)
  - `next_block_id` (nullable UUID)
  - `block_type_id` (string)
  - `props` (JSON dict)
  - `created_at`, `updated_at`
- System metadata:
  - `is_system` (bool)
  - `is_removable` (bool)
  - `fixed_position` (smallint, nullable)
- Indexes:
  - `(document_id, previous_block_id)`
  - `(document_id, next_block_id)`

## Linked-list ordering behavior (`backend/app/services/block_service.py`)
- Document order root is `documents.first_block_id`.
- Traversal follows `next_block_id` to produce ordered root blocks.
- Insert operations:
  - at head (`previous_block_id = null`), or
  - after a specific block.
- Move operations relink neighbors and update head pointer when needed.
- Delete operations relink neighbors and update head pointer if head is removed.
- `GET /documents/{document_id}/blocks/root` returns this ordered linear list.

## Block type enum (current)
Defined in `backend/app/models/document/block.py`.

General/editor block types:
- `paragraph`
- `heading1`
- `heading2`
- `list`
- `todo`
- `code`
- `quote`
- `divider`

System block types:
- `document_heading`
- `input_workpiece`

## Block handler architecture
- Base contract: `BlockTypeHandler` (`backend/app/models/document/block_types/base.py`)
- Registry: `backend/app/models/document/block_types/__init__.py`
- Active handlers:
  - `DocumentHeadingHandler`
  - `InputWorkpieceHandler`
- Integration service: `backend/app/services/block_type_service.py`
  - system block initialization
  - single-instance constraints
  - delete/reorder restrictions
  - frontend enrichment via handler serialization

## System block lifecycle
- For non-copy document creation:
  - `POST /documents` calls `initialize_system_blocks(...)`.
- System handlers are created in `fixed_position` order.
- Current default system order:
  1. `document_heading` (`fixed_position = 0`)
  2. `input_workpiece` (`fixed_position = 1`)
- Both are non-removable and single-instance per document.

## System block: `document_heading`
Handler: `backend/app/models/document/block_types/document_heading.py`

Behavior:
- `is_system = true`
- `is_removable = false`
- `fixed_position = 0`
- `allow_multiple_instances = false`

Default `props`:
- `heat_no`
- `finished_size`
- `stock_size`
- `stock_weight`
- `remarks`
- `preview_status` (default `"empty"`)

Frontend serialization enriches props with document metadata:
- `name`
- `project_id`
- `source_document_id`
- `editor_user_id`
- `created_at`, `updated_at`
- optional latest `version` from `document_versions`

Update behavior:
- Validates field length limits for editable strings.
- If `props.name` is provided, updates `documents.name`.
- If `props.version` is provided, updates selected latest-version fields.

Editable fields:
- `name`
- `heat_no`
- `finished_size`
- `stock_size`
- `stock_weight`
- `remarks`
- `preview_status`

## System block: `input_workpiece`
Handler: `backend/app/models/document/block_types/input_workpiece.py`

Behavior:
- `is_system = true`
- `is_removable = false`
- `fixed_position = 1`
- `allow_multiple_instances = false`

Default `props`:
- `geometry_type_id`
- `mesh_elements`
- `weight`
- `attributes` (dynamic key-value map)

Validation rules:
- `geometry_type_id` must exist in payload and be known when non-empty.
- `mesh_elements` must be integer-compatible.
- `weight` must be numeric-compatible.

Frontend serialization includes:
- generated `title`
- `available_geometry_types` metadata list
- `selected_geometry` metadata when selected

Supported geometry IDs:
- `68`, `69`, `70`, `71`, `72`, `73`, `74`, `75`, `76`, `77`, `78`, `79`

Editable fields:
- `geometry_type_id`
- `mesh_elements`
- `weight`
- `attributes`

## Active API routes affecting document/block architecture
- Projects:
  - `GET /projects`
  - `GET /projects/{project_id}/documents`
- Documents:
  - `POST /documents` (requires `project_id`, optional `source_document_id`)
  - `POST /documents/{document_id}/copy`
  - `GET /documents/{document_id}/lineage`
  - `GET /documents/{document_id}/diff/{other_document_id}`
  - session routes under `/documents/{document_id}/sessions/*`
- Blocks:
  - `GET /documents/{document_id}/blocks/root`
  - `POST /documents/{document_id}/blocks`
  - `PATCH /blocks/{block_id}`
  - `POST /blocks/{block_id}/move`
  - `DELETE /blocks/{block_id}`
  - `POST /documents/{document_id}/commit`

## Commit operation model (`backend/app/services/commit_service.py`)
- Commit endpoint accepts `ops[]` batches (revision-free commit pipeline).
- Supported `op_type` values:
  - `insert_block`
  - `delete_block`
  - `move_block`
  - `update_props`
  - `update_text`
- Constraint enforcement:
  - insert: single-instance checks for constrained block types
  - delete: rejects non-removable system blocks
  - move: rejects fixed-position blocks
  - update: triggers handler `on_update` hooks

## Revisions and versioning status
- `backend/app/models/document/revision.py` is not present in current code.
- Block commit persistence is handled directly by `commit_service`.
- `document_versions` still exists and is used by `document_heading` enrichment/update logic.

## Frontend rendering architecture
- Registry:
  - `frontend/src/components/blocks/BlockRegistry.ts`
  - `frontend/src/components/blocks/index.ts`
- Registered system components:
  - `document_heading` -> `DocumentHeadingBlock`
  - `input_workpiece` -> `InputWorkpieceBlock`
- Editor (`frontend/src/components/BlockEditor.tsx`) loads ordered root blocks and submits `update_props` commit operations.

## Notes for future updates
- If new system blocks are added:
  - update `BlockType` enum
  - register handler in block type registry
  - include initialization and constraints logic
  - register frontend block component
  - update this file and `PROJECT_CONTEXT.md`
