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
  - `first_block_id` (nullable head pointer into `document_blocks`)
  - `material_version_id` (nullable FK to `material_versions.material_version_id`)
  - `name` (required)
  - `notes` (nullable)
  - `created_at`, `updated_at`
  - `deleted_at` (soft delete)
- Relationships:
  - `project`
  - `material_version`
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
- Table: `document_blocks`
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

## `document_blocks.props` JSONB contract
- `props` is schema-flexible JSONB, but active handlers/components impose de facto structures.
- Handler-backed structures:
  - `document_heading`:
    - persisted/editable title fields: `name`, `heat_no`, `finished_size`, `remarks`, `preview_status`
    - persisted/editable setup fields merged from old setup blocks: `material_id`, `geometry_type_id`, `weight`, `attributes`, `mesh_elements`
    - response enrichment for billet geometry: `input_workpiece_title`, `available_geometry_types`, optional `selected_geometry`
    - response enrichment fields: `project_id`, `source_document_id`, `editor_user_id`, `material_version_id`, `created_at`, `updated_at`
    - optional nested object: `version` with `document_version_id`, `name`, `is_editable`, `execution_order`, `operations_count`, `created_at`, `last_modified`
  - `input_workpiece`:
    - legacy compatibility block only; new documents no longer auto-create it
    - persisted/editable fields: `geometry_type_id`, `weight`, `attributes`
    - response enrichment fields: `title`, `available_geometry_types`, optional `selected_geometry`
    - `available_geometry_types[]` item shape: `id`, `name`, `labels[]`, `columns[]`
  - operation type `84` (`Mesh`):
    - obsolete compatibility row; `mesh_elements` now lives on `document_heading`
  - operation type `10` (`Furnace`):
    - persisted/editable fields: `furnace_class_id`, `temperature`
    - replaces the old split operation rows `10` (`Furnace class`) plus `62` (`Temperature at 0 min`)
    - compiler carries furnace class and initial furnace temperature forward into following type `23` heating steps
  - operation type `24` (`Deformation`):
    - persisted/editable fields: `press_id`, `feed_direction_prolongation_id`, `speed_prolongation`, `feed_direction_upsetting_id`, `speed_upsetting`, `feed_direction_transversal_cogging_id`, `speed_transversal_cogging`, `feed_first`, `feed_middle`, `feed_last`
    - frontend renders those fields as merged `Press`, empty `Die`, grouped feed-direction/speed rows, and a visually separated first/middle/last feed-length row
  - operation type `26` (`Press`):
    - obsolete compatibility row; `press_id` now lives on operation type `24`
  - operation type `8` (`Die`):
    - obsolete compatibility row; the empty Die section is rendered inside operation type `24`
  - operation type `15` (`Prolongation feed and speed`):
    - obsolete compatibility row; fields now live on operation type `24`
  - operation type `13` (`Upsetting feed and speed`):
    - obsolete compatibility row; fields now live on operation type `24`
  - operation type `14` (`Transversal cogging feed and speed`):
    - obsolete compatibility row; fields now live on operation type `24`
  - feed direction fields:
    - use old feed-direction ids rendered as arrow buttons: `3` = `<--`, `4` = `<->`, `2` = `-->`; default is `3`
  - Deformation insert behavior:
    - direct insertion of `26`, `8`, `15`, `13`, or `14` is blocked because those rows are obsolete; only `24` is user-insertable
- Generic operation blocks:
  - `block_type_id` is a numeric string matching `document_blocks_library.type_id`
  - persisted/editable fields are exactly the operation's `db_column_names`
  - response enrichment fields are transient: `title` and `operation_type`
  - `operation_type` includes cleaned old-catalog metadata such as `library_name`, `process_name`, `labels[]`, `db_column_names[]`, category flags, `deformation_type`, `trigger`, and optional `field_options`

## Linked-list ordering behavior (`backend/app/services/block_service.py`)
- Document order root is `documents.first_block_id`.
- Traversal follows `next_block_id` to produce ordered root blocks.
- Insert operations:
  - after a specific block.
  - user/API insertion at head or between fixed system blocks is rejected once a fixed system prefix exists.
- Move operations relink neighbors and update head pointer when needed.
- Delete operations relink neighbors and update head pointer if head is removed.
- `GET /documents/{document_id}/blocks/root` returns this ordered linear list.

## Block type enum and implementation status
Defined in `backend/app/models/document/block.py`.

- Enum values:
  - `document_heading`
  - `input_workpiece`
  - numeric operation ids are not enum values; they are validated against `document_blocks_library`
- Active handler-backed types:
  - `document_heading`
  - `input_workpiece` for legacy compatibility only
- Frontend-registered block components:
  - `document_heading` -> `DocumentHeadingBlock`
  - `input_workpiece` -> `InputWorkpieceBlock`
  - numeric operation ids -> generic `OperationBlock`

## Block handler architecture
- Base contract: `BlockTypeHandler` (`backend/app/models/document/block_types/base.py`)
- Registry: `backend/app/models/document/block_types/__init__.py`
- Active handlers:
  - `DocumentHeadingHandler`
  - `InputWorkpieceHandler`
- Integration service: `backend/app/services/block_type_service.py`
  - system block initialization
  - single-instance constraints
  - numeric operation-block validation against `document_blocks_library`
  - delete/reorder restrictions
  - frontend enrichment via handler serialization
  - frontend enrichment for generic operation blocks via `backend/app/services/operation_blocks.py`

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
    - document rows are toggle-selected; zero, one, or many documents may be selected
    - the first document is selected on first opening the Documents view if no user selection exists yet
    - selected document ids live in `useDocumentsStore.selectedDocIds`, so selection survives switching tools
    - `currentDoc/currentDocId` are populated only when exactly one document is selected; zero or multiple selections intentionally hide document-specific content in other views
  - `Blocks` (shared `Catalog` / `Clipboard` tab pane)
    - `Catalog` is selected by default and provides the operation catalog loaded from `GET /library/db/document-block-types?insertable_only=true`; each whole catalog card is draggable, and double-click inserts the operation after the active document block
    - `Clipboard` is frontend-only session memory for structural block cut/copy/paste; clipboard state is not persisted in backend tables
  - `Library` (selector for `Dies`, `Die Assemblies`, `Presses`, `Materials`)
  - `Simulation` (no middle pane content; selecting it opens the Simulation dashboard in the main pane)
  - `Users` (current user/session information)
- `MenuBar` contains document-level controls (`Save`, `Cancel`, `Undo`, `Redo`, `Lineage`, `Sessions`) and save/dirty status.
- `MainEditorPane` routes active content:
  - `BlockEditor` when current tool is `Projects`, `Documents`, `Blocks`, or `Users`
  - `Dies`, `Die Assemblies`, `Presses`, `Materials` when current tool is `Library`
  - `Simulation` dashboard when current tool is `Simulation`
- `BlockEditor` visual document format:
  - source data remains the flat `document_blocks` linked list; no `parent_block_id` is stored
  - the first `document_heading` block is rendered as the document canvas/title area
  - operation type `10` (`Furnace`) and operation type `24` (`Deformation`) are rendered as second-level sections inside that canvas
  - operation blocks after a Deformation section are rendered as children of that Deformation until the next Furnace/Deformation section appears
  - operation blocks outside any Deformation section render in an `Unsectioned Operations` visual group
  - dropping a catalog block onto a visual section inserts it after the section's last visual child, preserving the flat linked-list model
  - one non-title block can be active at a time; `document_heading` / title canvas cannot become active
  - active block state is independent from selected block state and is shown with a strong outline
  - direct block click, input focus/click/change inside a block, successful drag/drop, insert, and paste make a block active
  - selection checkbox clicks and drag-handle clicks without a completed drop do not change active block state
  - selected blocks are used for batch copy, cut, remove, and drag-group preparation
  - drag/drop uses dense zero-height insertion markers: while dragging, a thin blue `Insert here` line previews the exact insertion target without adding permanent spacing to the document layout
  - move operations are optimistic in the frontend: `draftBlocks` reorder locally first, block wrappers animate position with lightweight `framer-motion`, and backend move requests then persist the same order; failed moves revert and refresh
  - catalog insert, structural copy, and clipboard paste keep a short-lived `Inserted here` confirmation line at the final anchor and briefly highlight the inserted block group after refresh so users can see which lower blocks moved down
- `Simulation` dashboard behavior:
  - owner scope filter defaults to current user and can switch to all users or one selected user via icon controls and a dropdown
  - `Documents` table shows latest version workflow state and per-row run/stop plus pause/continue controls
  - `Simulations` table shows fixed runs with queue position and supports drag-and-drop reordering to change queue priority
  - `Solver PCs` table shows read-only server state, current simulation assignment, and machine resource summary
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
  - this is the only active materials view; it is now a mode-based workspace with `dashboard`, `editor`, and `copy` modes, and the old standalone `Materials` card view has been removed
  - it shows only parsed DEFORM file content from the file path referenced by `materials.deform_file_name`
  - it preloads visuals for the visible filtered material set and overlays them on shared comparison charts
  - left rail is a single shared scroll area containing text filter, owner filters, classification filters, placeholder material action buttons, and simplified material name cards
  - those left-rail material actions now open in-place workspace modes:
    - `New material` opens editor mode with an empty draft
    - `Edit selected material` opens editor mode for the selected material
    - `Copy into selected material` opens copy mode with the selected material as target
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
  - materials filtering also has a frontend-only pseudo category `Standard level`, derived from non-empty designation-country values (`designation_links.country`) rather than normalized classification rows
  - `Standard level` is single-select with default `None`, is scoped under the currently active `Object type` + `Composition base` branch, and is displayed below the regular classification filters
  - when a concrete `Standard level` value is active, material cards in the left rail and the dashboard summary line show a compound label made from the matching designation rows instead of the canonical material name
  - materials without `deform_file_name` still appear in the browser/editor/copy workflows, but are skipped by DEFORM chart loading and comparison plotting
  - each dashboard chart supports `Auto / Manual / Reset` scaling; when manual mode is active, the first and last tick labels on each axis can be clicked and edited inline
  - `TopEditorPane` does not render the shared library action strip for this view
  - editor mode currently saves:
    - `materials`
    - `material_classification_assignments`
    - `materials_designations`
  - in editor mode, `DEFORM file` is presented as a read-only stored file name with an `Upload...` picker, followed by explicit `Upload` / `Cancel` actions for a single local `.key` / `.KEY` file
  - successful upload stores the file under `backend/data/materials/` and writes the returned stored file name into the editor draft for later save to `materials.deform_file_name`
  - copy mode currently transfers selected normalized subtrees between two materials:
    - note / `deform_file_name`
    - classification assignments
    - designation rows plus linked standard chemistry rows
    - test-record subtrees including chemistry results and property tables
- `TopEditorPane` routes top content:
  - `VisualEditor` when `BlockEditor` is active
  - library action menu when a library view is active
- `VisualEditor` view in `TopEditorPane` renders a horizontal block icon strip in the same order as `BlockEditor` and supports:
  - full hide/show behavior: when collapsed it is not rendered at all
  - visibility toggle is provided by `MenuBar` in block-editor mode
  - click-to-scroll navigation to block anchors inside `BlockEditor`
  - viewer mode type visibility toggles (hide/show per block type)
  - editor mode with multi-selection, drag-drop reordering, Ctrl/Cmd-drop copy, operation insert, delete, and frontend clipboard copy/cut/paste
- Active document block behavior:
  - paste and default insert use the active document block as the insertion anchor
  - paste is disabled/error-blocked when there is no active document block
  - after paste succeeds, the last newly pasted block becomes active, enabling repeated paste directly after the previous paste
  - after insert or Ctrl/Cmd-drop copy, the last newly inserted/copied block becomes active
  - after move, the last moved block becomes active
  - deleting the active block clears active state
- Frontend block clipboard behavior:
  - implemented in `frontend/src/stores/useBlockClipboardStore.ts` and rendered by `frontend/src/components/clipboard/ClipboardPane.tsx`
  - every copy or cut action creates a new clipboard container at the top and makes it the active container
  - exactly one active container exists when clipboard entries exist; active is used by the `Paste active` command
  - selected containers are independent checkboxes and may be none, one, or many; selection is used only by `Remove selected`
  - clipboard memory defaults to 10 containers and is user-adjustable in the pane; trimming keeps the newest entries
  - paste never consumes/removes a clipboard container, so the same copied/cut block set can be inserted multiple times
  - pasted block props are sanitized so transient frontend metadata such as `title` and `operation_type` is not written back to `document_blocks.props`
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
- Backed by a `document_blocks` row with JSON `props` and linked-list placement metadata.
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
  - `name`, `heat_no`, `finished_size`, `remarks`

### `input_workpiece` delta
- System-only placement constraints:
  - `is_system = true`
  - `is_removable = false`
  - `fixed_position = 2`
  - `allow_multiple_instances = false`
- Domain-specific geometry model:
  - geometry selector keyed by `geometry_type_id`
  - dynamic `attributes` schema derived from geometry definition
  - generated display `title` from geometry and attributes
  - serialized geometry metadata (`available_geometry_types`, optional `selected_geometry`)
- Numeric/domain validation in handler:
  - `geometry_type_id` must exist and be known when non-empty
  - `weight` must be numeric-compatible
- No explicit block-specific `field_limits` currently returned by handler.

### Generic operation block delta
- Text/editor block types have been removed from the active UI and backend type enum.
- Numeric operation block types are validated against active leaf rows in `document_blocks_library`; unknown, obsolete, and parent/category rows are rejected on create.
- Fixed setup operation types `5` (`Material`) and `84` (`Mesh`) are obsolete; their data now lives on `document_heading`.
- Operation type `10` (`Furnace`) merges the old furnace-class and initial-temperature cards; operation type `62` is obsolete/hidden.
- Operation type `24` (`Deformation`) is the user-insertable merged Deformation block for Press, empty Die, Prolongation feed/speed, Upsetting feed/speed, Transversal cogging feed/speed, and first/middle/last feed length; old operation types `26`, `8`, `15`, `13`, `14`, old combined `Feed` (`12`), old combined `Speed` (`9`), and old feed leaf operation types `16`-`18` are obsolete/hidden.
- Generic operation fields with backend-provided `operation_type.field_options[column]` render as one-click mutually exclusive option-button rows in the frontend.
- Frontend component registration uses one fallback `OperationBlock` for all numeric operation ids.
- Operation props are sanitized on create/update/copy so transient render metadata is not persisted.

## System block lifecycle
- For non-copy document creation:
  - `POST /documents` calls `initialize_system_blocks(...)`.
- System blocks are created by explicit fixed prefix order in `backend/app/services/block_type_service.py`.
- Current default system order:
  1. `document_heading` (`fixed_position = 0`)
- The fixed setup fields that used to be separate Material/Input Workpiece/Mesh blocks are now properties of `document_heading`.
- The fixed title block is non-removable; Material and Mesh cannot be manually inserted as duplicates because their catalog rows are obsolete.

## Fixed leading block rules
- The first block of any new non-copy document is:
  1. `document_heading`
- This block is treated as fixed with:
  - `is_removable = false`
  - `is_fixed = true` (documentation alias; implemented via non-null `fixed_position`)
- Inserting or moving blocks in front of the fixed title block is not allowed.

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
  - `DELETE /library/db/materials`
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
