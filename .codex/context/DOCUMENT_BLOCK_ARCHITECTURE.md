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

## Block type enum and implementation status
Defined in `backend/app/models/document/block.py`.

- Enum values:
  - `paragraph`
  - `heading1`
  - `heading2`
  - `list`
  - `todo`
  - `code`
  - `quote`
  - `divider`
  - `document_heading`
  - `input_workpiece`
- Active handler-backed types:
  - `document_heading`
  - `input_workpiece`
- Frontend-registered block components:
  - `document_heading` -> `DocumentHeadingBlock`
  - `input_workpiece` -> `InputWorkpieceBlock`
- Enum-only types currently have no active handler registration and no dedicated frontend component registration.

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

### Frontend payload metadata for handler-backed blocks
`enrich_block_data_for_frontend` returns:
- `editable_fields`: editable prop names from `handler.get_editable_fields()`
- `field_limits`: per-field max string lengths from `handler.get_field_limits()`

`field_limits` is consumed by frontend to enforce DB-aligned limits during input and draft updates.

## Document editing model (frontend, current)
Implemented in `frontend/src/components/BlockEditor.tsx` and block components.

- All rendered block types are always in editable mode.
- Per-block `Edit`, `Save`, `Cancel` controls do not exist.
- Editing is draft-first:
  - `savedBlocks` = backend snapshot
  - `draftBlocks` = local editable state
- Document-level controls above blocks:
  - `Save`: commits all changed blocks in one cumulative batch
  - `Cancel`: discards all drafts and restores backend snapshot
- Dirty UX:
  - changed fields are highlighted with light red background
  - each dirty field has a square `↺` button to reset only that field
- Save/cancel flow preserves editor scroll position.
- String length limits are enforced without visible counters:
  - input-level `maxLength` where field mapping exists
  - centralized clamping in `applyFieldLengthLimits(...)` before state update

## Virtual common block standard (documentation-only)
### `draft_synced_props_block`
This is a virtual standard type. It is not part of the DB enum and is not instantiated in documents.
It defines common behavior expected from active document-building block types.

Common characteristics:
- Backed by a `blocks` row with JSON `props` and linked-list placement metadata.
- Participates in document-level draft editing (`draftBlocks`) and cumulative save/cancel.
- Updates are propagated via `onUpdate(blockId, props)` and committed through `update_props` ops.
- Supports baseline-vs-draft dirty comparison per editable field.
- Supports per-field reset to backend baseline (`↺` button behavior).
- Accepts optional backend-supplied `editable_fields` metadata.
- Accepts optional backend-supplied `field_limits` metadata; frontend enforces string limits even if a specific UI control does not declare `maxLength`.

## Existing handler-backed block types as deltas from `draft_synced_props_block`

### `document_heading` delta
- System-only placement constraints:
  - `is_system = true`
  - `is_removable = false`
  - `fixed_position = 0`
  - `allow_multiple_instances = false`
- Cross-entity enrichment and writes:
  - props are enriched with document metadata (`name`, project/source/editor IDs, timestamps)
  - optional latest `document_versions` payload is embedded as `version`
  - updates to `props.name` also update `documents.name`
  - updates to `props.version` map to selected latest-version fields
- Adds block-specific string limits through `get_field_limits()`:
  - `name`, `heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`

### `input_workpiece` delta
- System-only placement constraints:
  - `is_system = true`
  - `is_removable = false`
  - `fixed_position = 1`
  - `allow_multiple_instances = false`
- Domain-specific geometry model:
  - geometry selector keyed by `geometry_type_id`
  - dynamic `attributes` schema derived from geometry definition
  - generated display `title` from geometry and attributes
  - serialized geometry metadata (`available_geometry_types`, optional `selected_geometry`)
- Numeric/domain validation in handler:
  - `geometry_type_id` must exist and be known when non-empty
  - `mesh_elements` must be integer-compatible
  - `weight` must be numeric-compatible
- No explicit block-specific `field_limits` currently returned by handler.

### Enum-only editor block types delta (`paragraph`, `heading1`, `heading2`, `list`, `todo`, `code`, `quote`, `divider`)
- Currently no handler registration in `backend/app/models/document/block_types/__init__.py`.
- Currently no dedicated frontend component registration in `frontend/src/components/blocks/index.ts`.
- As a result, these types do not yet implement the full `draft_synced_props_block` behavior contract in the active UI path.

## System block lifecycle
- For non-copy document creation:
  - `POST /documents` calls `initialize_system_blocks(...)`.
- System handlers are created in `fixed_position` order.
- Current default system order:
  1. `document_heading` (`fixed_position = 0`)
  2. `input_workpiece` (`fixed_position = 1`)
- Both are non-removable and single-instance per document.

## Fixed leading block rules
- The first two blocks of any document are:
  1. `document_heading`
  2. `input_workpiece`
- These two block types are treated as fixed blocks with:
  - `is_removable = false`
  - `is_fixed = true` (documentation alias; implemented via non-null `fixed_position`)
- Inserting new blocks in front of block types with `is_fixed = true` is not allowed.

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

## Notes for future updates
- For every new handler-backed block type:
  - update `BlockType` enum
  - register handler in block type registry
  - include initialization and constraints logic if it is a system block
  - register frontend block component if it must render in editor
  - define `get_editable_fields()` and `get_field_limits()` when applicable
  - keep behavior aligned with `draft_synced_props_block` standard unless there is an explicit delta
  - update this file and `PROJECT_CONTEXT.md`
