---
apply: always
---

# Document and Block Architecture

## Scope
This file is the source of truth for document/block architecture, block types, and block behavior.

Configuration/setup details (including `.env` editing during install) are tracked in `.codex/context/PROJECT_CONTEXT.md`.

## Current hierarchy
- Product data flow is `Project -> Document -> Block`.
- Documents are project-scoped (`documents.project_id` is required).
- Block ordering is linked-list based (no `order_key`, no block tree).

## Cross-domain note
- `projects.material_id` now references `materials.material_id` (dedicated `materials` table).
- This does not change document/block storage, linked-list ordering, commit operations, or block handler behavior.

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
  - `props` (JSONB dict)
  - `created_at`, `updated_at`
- System metadata:
  - `is_system` (bool)
  - `is_removable` (bool)
  - `fixed_position` (smallint, nullable)
- Indexes:
  - `(document_id, previous_block_id)`
  - `(document_id, next_block_id)`

## `blocks.props` JSONB contract
- `props` is schema-flexible JSONB, but active handlers/components impose de facto structures.
- Handler-backed structures:
  - `document_heading`:
    - persisted/editable fields: `name`, `heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`, `preview_status`
    - response enrichment fields: `project_id`, `source_document_id`, `editor_user_id`, `created_at`, `updated_at`
    - optional nested object: `version` with `document_version_id`, `name`, `is_editable`, `execution_order`, `operations_count`, `created_at`, `last_modified`
  - `input_workpiece`:
    - persisted/editable fields: `geometry_type_id`, `mesh_elements`, `weight`, `attributes`
    - response enrichment fields: `title`, `available_geometry_types`, optional `selected_geometry`
    - `available_geometry_types[]` item shape: `id`, `name`, `labels[]`, `columns[]`
- Enum-only editor blocks (frontend `BasicContentBlock`) use lightweight props:
  - `paragraph`, `heading1`, `heading2`, `list`, `code`, `quote`: usually `text`
  - `todo`: `text` + boolean `checked`
  - `divider`: typically empty object

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
  - `paragraph` -> `BasicContentBlock`
  - `heading1` -> `BasicContentBlock`
  - `heading2` -> `BasicContentBlock`
  - `list` -> `BasicContentBlock`
  - `todo` -> `BasicContentBlock`
  - `code` -> `BasicContentBlock`
  - `quote` -> `BasicContentBlock`
  - `divider` -> `BasicContentBlock`

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
Implemented in `frontend/src/pages/AppPage.tsx`, `frontend/src/components/BlockEditor.tsx`, `frontend/src/components/MenuBar.tsx`, `frontend/src/components/ToolsPane.tsx`, and `frontend/src/components/VisualEditor.tsx`.

- Main screen uses split-pane layout:
  - `MenuBar` (top, full width, always visible)
  - below: `ToolsSwitcher` (left, always visible), `ToolsPane` (middle, collapsible), right editor stack
  - right editor stack: `TopEditorPane` (conditional) + `MainEditorPane` (conditional)
- `ToolsSwitcher` toggles current `ToolsPane` view.
  - if no view is active, `ToolsPane` is hidden
  - clicking the currently active tool hides `ToolsPane` only and does not change the current `MainEditorPane` view
- `ToolsPane` views:
  - `Projects` (list/filter/create modal)
  - `Documents` (project-scoped list/filter/new/copy modals)
  - `Blocks` (drag-and-drop/insert block palette)
  - `Library` (selector for `Dies`, `Die Assemblies`, `Presses`, `Materials`)
  - `Users` (current user/session information)
- `MenuBar` contains document-level controls (`Save`, `Cancel`, `Undo`, `Redo`, `Lineage`, `Sessions`) and save/dirty status.
- `MainEditorPane` routes active content:
  - `BlockEditor` when current tool is `Projects`, `Documents`, `Blocks`, or `Users`
  - `Dies`, `Die Assemblies`, `Presses`, `Materials` when current tool is `Library`
- `Dies` view behavior:
  - one die card per `dies` record after active filters
  - die card layout: top row = die name; second row = square STL preview (left) + die metadata block (right)
  - each die card includes an interactive STL preview window (camera-only)
  - STL source is derived from `die_template_file_name` (`*.zip` stem -> `*.stl`) and loaded through `/library/db/dies/stl/{file_name}`
  - interactions: rotate, pan, zoom, and reset view without changing model coordinates
  - initial camera is isometric (Z up, X left-down, Y right-down); model is centered and fitted to ~90% of viewport
- `Presses` view behavior:
  - one press card per `presses` record
  - each press card contains combined related `press_modes` data
  - layout inside press card:
    - top row: `Power Limit Diagram` + `Power Limit Table`
    - bottom: `Press Modes Table`
  - `Power Limit Diagram`:
    - one curve per related press mode
    - engineering-style axes with X = `Force, MN`, Y = `Speed, mm/s`
    - always renders `x=0` and `y=0` scale ticks
    - axis minimum snaps to `0` when there are no negative values on that axis
    - exactly one curve is selected at any time; default selection is press mode with `is_default_press_mode = true` (fallback: first by `id`)
  - `Power Limit Table`:
    - shows data for the currently selected curve/press mode only
  - `Press Modes Table`:
    - one row per related `press_modes` record
    - includes `press_modes.properties` fields except `power_limit`
    - left legend column is sticky
    - rows are sortable by clicking column headers (default sort by `id`)
    - horizontal scroll is synchronized across all press cards
- `Materials` view behavior:
  - this is the only active materials view; it uses a dashboard-style comparison layout and the old standalone `Materials` card view has been removed
  - it shows only parsed DEFORM file content from the file path referenced by `materials.deform_file_name`
  - it preloads visuals for the visible filtered material set and overlays them on shared comparison charts
  - left rail is a single shared scroll area containing text filter, owner filters, classification filters, placeholder material action buttons, and simplified material name cards
  - if the Library tool pane is toggled hidden while `Materials` stays active, the left material rail is hidden and the charts expand to fill the main pane
  - supports dashboard-local multi-selection with click, repeated-click clear, Ctrl/Cmd-toggle, and Shift-range selection
  - selected material names are shown in a dense non-scrollable one-line summary above the charts; when nothing is selected it summarizes all visible materials as highlighted and labels the view as DEFORM materials
  - dashboard title and active-material metadata live in the diagrams pane, render only for a single selected material, and scroll away with the diagram grid
  - the single-material details section uses a compact two-column key/value layout for DEFORM file, owner, test count, note, and diagram load state
  - designations and linked standards are rendered in that section as a compact table sorted by the standard column, with `Designation` / `Standard` / `Country` plus dynamic chemistry-limit element columns populated from designation standard-chemistry rows
  - the classification subsection is rendered as a two-column axis/value comparison: selected-material values are highlighted and values present only on other currently visible materials are muted
  - classification axes are hierarchy-aware: level 1 = object type, level 2 = composition base, level 3 = all other categories
  - classification filter behavior is OR within one axis and AND across axes; when no classification chips are active, all materials that pass text/owner filters remain visible
  - classification filter chips and comparison values are branch-scoped by hierarchy, so lower-level values are hidden when they do not belong to the currently active higher-level branch
  - each dashboard chart supports `Auto / Manual / Reset` scaling; when manual mode is active, the first and last tick labels on each axis can be clicked and edited inline
  - `TopEditorPane` does not render the shared library action strip for this view
- `TopEditorPane` routes top content:
  - `VisualEditor` when `BlockEditor` is active
  - library action menu when a library view is active
- `VisualEditor` view in `TopEditorPane` renders a horizontal block icon strip in the same order as `BlockEditor` and supports:
  - full hide/show behavior: when collapsed it is not rendered at all
  - visibility toggle is provided by `MenuBar` in block-editor mode
  - click-to-scroll navigation to block anchors inside `BlockEditor`
  - viewer mode type visibility toggles (hide/show per block type)
  - editor mode with multi-selection, drag-drop reordering, Ctrl/Cmd-drop copy, insert, and delete
- Structural edits from `VisualEditor` and `Blocks` are blocked while unsaved draft prop edits exist (user must save/cancel first).
- Frontend visual styling for document editing UI is standardized on a compact VisualEditor-derived system:
  - shared style primitives are defined in `frontend/src/index.css` (`ui-*` classes)
  - active editor-related components (`MenuBar`, `ToolsPane`, `ToolsSwitcher`, `VisualEditor`, `BlockEditor`, and block components) should consume `ui-*` classes instead of ad-hoc utility combinations for common controls/surfaces
  - typography scale is constrained by `frontend/tailwind.config.js` to `text-xs`, `text-sm`, `text-base`, `text-lg`

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
- Frontend component registration exists in `frontend/src/components/blocks/index.ts` via `BasicContentBlock`.
- These types are renderable/editable in the active UI path, but still do not have backend handler hooks beyond generic block persistence.

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
- Library:
  - `GET /library/db/materials`
  - `GET /library/db/material-classification`
  - `GET /library/db/materials/{material_id}/visuals`

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
