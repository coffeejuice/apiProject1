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

## Current semantic block model (updated 2026-04-29)
- Active block types are:
  - `document`: fixed root/canvas block, first in the linked list, non-removable.
  - `heating`: removable second-level section/container for furnace operations.
  - `deformation`: removable second-level section; a document must keep at least one.
  - `furnace`: property-only child block under a `heating`; multiple furnaces are allowed in one heating section.
  - `operation`: property-only child block under a `deformation`; each deformation must keep at least one operation.
- New documents auto-create `document`, then `deformation`, then the first `operation`.
- Creating a `heating` section auto-creates one initial `furnace` child.
- `document_heading`, `input_workpiece`, and numeric editor block IDs are obsolete in active code. Historical sections below that mention them are superseded by this section.
- There is no active runtime block-library table for the editor. Operation block template metadata and selector payloads are endpoint/service-owned code in `backend/app/services/operation_blocks.py` and are exposed by `GET /operation-templates`.
- Operation text/table materialization rules are explicit code in `backend/app/services/document_operations.py`.
- The old runtime rule files were removed; there is no active operation-template schema-file loader for editor block definitions.
- Creating an operation block uses `block_type_id = "operation"` and passes `props.operation_template_id`; backend expands defaults from endpoint/service-owned Operation block metadata.
- Dynamic operation variables use nested JSON under `document_blocks.props.operation_properties.target`, for example `target.rotation` is stored as `{ "operation_properties": { "target": { "rotation": "..." } } }`.
- `deformation_properties.deformation_variables` stores parser variables copied into generated Operation rows when needed: `tail_chamfering_stroke` and `tail_flattening_stroke`.
- `deformation_properties` stores die/tooling selection with old operation variable names: `die_assembly_id` for paired selection, or `top_die_id` and `bottom_die_id` for separate selection. UI-only helpers are `die_type_id`, `top_die_type_id`, `bottom_die_type_id`, and `die_selection_mode`; separate mode keeps independent top/bottom die-type filters.
- `deformation_properties.feed_settings.<operation_type>` stores old-project feed variable names per Operation type: `feed_direction_id`, `feed_first`, `feed_middle`, and `feed_last`. Feed direction values follow the old project dictionary: `2 = right`, `3 = left`, `4 = bidirectional`; the UI renders these as arrow icons and the default is `2`.
- `deformation_properties` also stores explicit old-project forming speed keys: `speed_upsetting` and `speed_prolongation`. `speed_full_die` is obsolete; transverse/full-die operations use `speed_prolongation`.
- `furnace_properties.temperature_program` stores the user-authored furnace-control diagram as ordered segments. Segment `type` is `hold`, `heat`, or `unload`; hold rows store `duration_min` and `temperature_c`, while heat/unload rows are visual/control transitions without direct duration or temperature fields. Old direct Furnace/Heating `furnace_class_id` and `temperature` inputs are removed from the active UI; `furnace_properties.temperature` may still be maintained internally as a single-value compatibility mirror until the preprocessor consumes the richer program directly.
- `operation_properties.operation_text` is an optional multiline operation source for non-rounding Operation types. Line breaks, tabs, and repeated spaces are visual only; the parser normalizes them to spaces and splits operations only by right-arrow separators, autoformatted to `→` in the frontend. Parser-backed selector entries include `operation.upsetting`, `operation.tail_flattening`, `operation.tail_chamfering`, `operation.cogging`, `operation.radial`, `operation.transversal`, and `operation.cut`; cutting currently emits parse errors until concrete formats are defined.
- `operation.rounding` uses `operation_properties.rounding_table` instead of text. The table columns are `Pass`, `Size`, `Feed`, `Angle`, `Rotations per Feed`, and `Speed`; one non-empty row materializes one `document_operations` row.
- Template fields retained on operation props:
  - `operation_template_id`
  - `operation_template_version`
  - `operation_kind`
  - `template_snapshot`
- The preprocessor bridge reads `document_operations.operation_parameters` directly and stores compiled runtime output in `simulation_steps` using semantic source fields. `simulation_steps.document_operation_id` is the primary key and required cascade FK to its source `document_operations` row; operation materialization creates/removes the sibling `simulation_steps` row immediately, and valid operation rows set `preprocess_ready = true` for Pre. Obsolete `simulation_step_id` is not part of the active schema.
- The root `document` block materializes into the first `document_operations` row with `operation_template_id = document_initial_data` and `operation_kind = billet`. Its target uses nested namespaces `document_info`, `production_data`, `material`, `input_stock`, and `mesh`; the Operations view displays these as chained-dot parameters. The Pre bridge maps this row to the legacy billet/NewBillet compiler path.
- Each `furnace` block materializes into a `document_operations` row with `operation_template_id = furnace`; its `operation_parameters.temperature_program` stores the editable Furnace table rows as `number`, `type`, `duration_min`, and `temperature_c`.
- Pre operation definitions are preprocessor-local semantic metadata plus semantic built-ins, not `document_blocks_library` rows. Compiler dispatch and timing lookup use semantic operation template IDs.
- Current semantic Pre compiler coverage should use real adapters for all active templates, including billet/document initial data, Furnace/Heating, Upsetting, axial/spiral/radial/full-die deformation, radial initial rotations, transverse/transversal cogging, and cutting. New semantic operation templates must update the adapter support map instead of silently falling back to generic compilation.
- The preprocessor no longer carries an `is_simulation` split; all valid materialized operation rows follow the same simulation-step path.
- Pre compile/parse failures include row context (`operation_id`, `document_operation_id`, `operation_template_id`, `source_block_id`) whenever available and are written to sibling `simulation_steps.calculations` diagnostics plus runtime `simulation_step_status.failed` so failed rows can be traced back to their source block.
- Pre worker output is persisted incrementally: before a run, current sibling `simulation_steps` rows are reset to pending output; every successfully compiled row is committed immediately; a later compile failure leaves earlier compiled rows available for troubleshooting and marks the failing row as failed.
- Worker loops are job-error-proofed: ordinary `Exception` from a claimed Pre/Solver/Post job is logged, persisted as a stage-specific failed runtime state, and the long-running worker returns to waiting for more work. Process-level stop signals and `BaseException` subclasses are still allowed to terminate the worker.
- For local development, Pre can be run with graceful source reload via `python -m app.workers.pre_dev_reload`; reload waits for the active Pre job to finish and then restarts only the Pre child process with changed code. Solver/Post reload is intentionally not implemented.
- `document_operations` is regenerated from `document_blocks` after structural and prop edits. It stores final per-row JSON in `operation_parameters`; direct parent Deformation values are copied there by explicit materialization rules and no inherited/effective namespace columns are stored. A Deformation section does not inherit missing copied values from previous Deformation sections.
- The Steps tool can explicitly requeue the latest editable document version for Pre with `POST /documents/{document_id}/simulation-steps/preprocess`; this is the active troubleshooting/retry path after a failed draft Pre run. The command uses existing saved operation/step rows and must not regenerate `document_operations`, because that would erase visible compiled `simulation_steps` data before the next Pre run writes replacements.

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
- Current active structures:
  - `document`: title/setup fields (`name`, `heat_no`, `finished_size`, `remarks`, `preview_status`, `material_id`, `geometry_type_id`, `weight`, `attributes`, `mesh_elements`, `section_numbering_start`) plus frontend enrichment for document metadata and billet geometry.
  - `heating`: no active editable properties.
  - `deformation`: `deformation_properties.die_type_id`, `deformation_properties.top_die_type_id`, `deformation_properties.bottom_die_type_id`, `deformation_properties.die_selection_mode`, `deformation_properties.die_assembly_id`, `deformation_properties.top_die_id`, `deformation_properties.bottom_die_id`, `deformation_properties.deformation_variables.tail_chamfering_stroke`, `deformation_properties.deformation_variables.tail_flattening_stroke`, `deformation_properties.feed_settings.<operation_type>.feed_direction_id`, `deformation_properties.feed_settings.<operation_type>.feed_first`, `deformation_properties.feed_settings.<operation_type>.feed_middle`, `deformation_properties.feed_settings.<operation_type>.feed_last`, `deformation_properties.speed_upsetting`, and `deformation_properties.speed_prolongation`.
  - `furnace`: `furnace_properties.temperature_program`; the frontend may receive an internal compatibility `temperature` mirror, but it is not user-editable.
  - `operation`: endpoint-provided template metadata, optional `operation_text`, optional `rounding_table`, and nested `operation_properties.target` variables.
- Handler-backed structures:
  - `document`: persisted/editable title/setup fields are `name`, `heat_no`, `finished_size`, `remarks`, `preview_status`, `material_id`, `geometry_type_id`, `weight`, `attributes`, `mesh_elements`, and `section_numbering_start`; read responses are enriched with document metadata, optional latest `version`, and billet geometry metadata
- Semantic non-handler structures:
  - `heating`: no active editable fields; the block acts as a visual container
  - `deformation`: section/container block with die settings under old-project-compatible `die_assembly_id`, `top_die_id`, and `bottom_die_id`, parser variables under `deformation_properties.deformation_variables`, per-operation-type feed settings under `deformation_properties.feed_settings`, and explicit old-project speed keys directly under `deformation_properties`
  - `furnace`: persisted/editable fields live under `furnace_properties`; the frontend provides a diagram/table editor for the `temperature_program` rows
  - `operation`: persisted/editable fields live under `operation_properties`; backend expands Operation block defaults and enriches responses with template metadata plus transient selector definitions for the generic frontend `OperationBlock`

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
  - `document`
  - `heating`
  - `deformation`
  - `furnace`
  - `operation`
- Active handler-backed types:
  - `document`
- Frontend-registered block components:
  - `document` -> `DocumentBlock`
  - `heating`, `deformation`, `furnace`, and `operation` -> generic `OperationBlock`

## Block handler architecture
- Base contract: `BlockTypeHandler` (`backend/app/models/document/block_types/base.py`)
- Registry: `backend/app/models/document/block_types/__init__.py`
- Active handlers:
  - `DocumentHandler`
- Integration service: `backend/app/services/block_type_service.py`
  - system block initialization
  - single-instance constraints
  - semantic block validation and placement rules
  - delete/reorder restrictions
  - frontend enrichment via handler serialization
  - frontend enrichment for Operation blocks via `backend/app/services/operation_blocks.py`

### Frontend payload metadata for handler-backed blocks
`enrich_block_data_for_frontend` returns:
- `editable_fields`: editable prop names from `handler.get_editable_fields()`
- `field_limits`: per-field max string lengths from `handler.get_field_limits()`

`field_limits` is consumed by frontend to enforce DB-aligned limits during input and draft updates.

## Document editing model (frontend, current)
Implemented in `frontend/src/pages/AppPage.tsx`, `frontend/src/components/BlockEditor.tsx`, `frontend/src/components/MenuBar.tsx`, `frontend/src/components/ToolsPane.tsx`, and `frontend/src/components/clipboard/ClipboardPane.tsx`.

- Main screen uses split-pane layout:
  - `MenuBar` (top, full width, always visible)
  - below: `ToolsSwitcher` (left, always visible), `ToolsPane` (middle, collapsible), right editor area
  - right editor area: optional inline library action strip + `MainEditorPane`
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
  - `Blocks` (shared `Actions` / `Clipboard` tab pane)
    - `Actions` is selected by default and acts as a selected-block context menu; it enables copy, cut, remove, paste-after-selected, and clear-selection only when appropriate
    - `Clipboard` is frontend-only session memory for structural block cut/copy/paste; clipboard state is not persisted in backend tables
  - `Operations` (no middle pane)
    - opens a split main workspace with the regular document editor on the left and a read-only `document_operations` table on the right
    - the right table shows saved materialized operation records and warns when unsaved document edits mean the table is not yet regenerated
  - `Steps` (no middle pane)
    - opens a Pre troubleshooting inspector for the selected document
    - the default response is grouped by provenance: `simulation_step` from `simulation_steps`, runtime `simulation_step_status`, and `diagnostics` from API/log context
    - selected-step related Pre log records are loaded separately from `GET /logs/pre/related`; the main steps response must stay a pure DB/status snapshot plus API metadata
    - when the `Steps` tool button is active, the view displays a very narrow left step list; clicking the active `Steps` button again hides only this list while keeping the Steps inspector open
    - the left step list scrolls independently from the right selected-step details/2D/3D workspace
    - the left step list is built from `GET /documents/{document_id}/blocks/root` plus `GET /documents/{document_id}/simulation-steps`
    - the left step list includes visual-only title cards for numbered Heating/Deformation sections and numbered Furnace/Operation children
    - step cards are nested under those visual title cards and show compact Pre-output chips from `simulation_steps.calculations` and `simulation_steps.pre_output`
    - the main detail area displays selected-step JSON diagnostics, related Pre log records, status errors, shared-scale 2D geometry overlays, and lazy-loaded legacy-STL surface-mesh 3D previews rendered with Three.js/WebGL plus visual-only sharp-edge overlays; Steps 3D view state is remembered in frontend session memory while browsing steps and can be restored to the default fitted view through the reset-view icon
    - selected-step surface artifacts are generated during Pre compilation by the restored legacy Trimesh/STL mesh-state path and stored as JSON/STL files outside the default list payload; only compact references are persisted in `simulation_steps.calculations.surface_artifacts`
    - if a selected row has no legacy Pre artifact yet, the backend surface endpoint returns an explicit error; hidden geometry synthesis from `simulation_steps` JSON is forbidden
  - `Library` (selector for `Dies`, `Die Assemblies`, `Presses`, `Materials`)
  - `Simulation` (no middle pane content; selecting it opens the Simulation dashboard in the main pane)
  - `Logs` (no middle pane content; selecting it opens local Frontend/API/Pre/Post/Solver/Coordinator log tailing in the main pane)
  - `Users` (current user/session information)
- `MenuBar` contains document-level controls (`Save`, `Cancel`, `Undo`, `Redo`, `Lineage`, `Sessions`), save/dirty status, and explicit `Preprocessor` / `Postprocessor` inline result toggles.
- `MainEditorPane` routes active content:
  - `BlockEditor` when current tool is `Projects`, `Documents`, `Blocks`, or `Users`
  - split `BlockEditor` + `DocumentOperationsView` when current tool is `Operations`
  - `SimulationStepsView` when current tool is `Steps`
  - `Dies`, `Die Assemblies`, `Presses`, `Materials` when current tool is `Library`
  - `Simulation` dashboard when current tool is `Simulation`
  - `LogsView` when current tool is `Logs`
- `BlockEditor` visual document format:
  - source data remains the flat `document_blocks` linked list; no `parent_block_id` is stored
  - document rendering intentionally uses borderless `doc-*` classes from `frontend/src/index.css` to keep the canvas close to a Microsoft Word / Notion page: blocks are identified by title text, hierarchy is shown by indentation, and regular form controls look like document text until hover/focus
  - the first `document` block is rendered as the document canvas/title area
  - inside the Document block, title/setup fields are grouped into compact sections: `Production data`, `Material`, `Input stock size`, and `Mesh`; section headings are indented one tab and parameter rows are indented one additional tab
  - `Heating` and `Deformation` semantic block types are rendered as second-level sections inside that canvas
  - `Furnace` blocks after a Heating section are rendered as children of that Heating until the next Heating/Deformation section appears
  - `Operation` blocks after a Deformation section are rendered as children of that Deformation until the next Heating/Deformation section appears
  - child blocks outside their valid section render in an `Unsectioned Operations` visual group until fixed by structural edits
  - one non-title block can be active at a time; `document` / title canvas cannot become active
  - active block state is independent from selected block state and is shown with a strong outline
  - clicking the document canvas outside activatable Heating/Deformation/Furnace/Operation block areas clears the active block
  - direct block click, input focus/click/change inside a block, successful drag/drop, insert, and paste make a block active
  - selection checkbox clicks and drag-handle clicks without a completed drop do not change active block state
  - exactly one selected block drives the `Blocks > Actions` context menu; multiple selected blocks remain useful for drag-group preparation
  - Heating and Deformation section titles are auto-numbered from `document_properties.section_numbering_start`
  - section numbering rule: a Heating immediately followed by a Deformation shares one base number as `N.1 Heating` and `N.2 Deformation`; every other Heating or Deformation gets simple `N.` numbering
  - the document-level `section_numbering_start` value is edited from a compact hover/focus control in the first Heating/Deformation section title; later section numbers are read-only, and the Document setup fields no longer show a separate numbering section
  - Deformation sections render with the section title/header, then a die selector parameter block, then Operation children, and finally the Deformation parameter editor as a footer below those children; this is visual-only and does not change linked-list ordering or materialization rules
  - the Deformation footer feed table shows only feed rows for selected operation types that actually consume feed: Tail Flattening, Cogging, Radial Cogging, and Transverse Cogging; Upsetting, Tail Chamfering, Rounding, and Cutting do not show feed rows
  - Operation block titles are auto-numbered within their containing Deformation section using simple `1.`, `2.`, `3.` numbering; numbering restarts at `1.` for each Deformation
  - drag/drop uses dense zero-height insertion markers: while dragging, a thin blue `Insert here` line previews the exact insertion target without adding permanent spacing to the document layout
  - `Alt+Shift+ArrowUp` / `Alt+Shift+ArrowDown` are keyboard alternatives to drag/drop:
    - selected blocks take precedence over the active block
    - with no selected blocks, the active block shifts one movement position
    - selected operation blocks shift in the flat operation lane, so they can cross Heating/Deformation boundaries and change visual parent
    - selected furnace blocks shift in the flat furnace lane, so they can cross Heating sections and change visual parent
    - selected top-level Heating/Deformation sections shift in the document section lane; moving a section includes its current child blocks
    - sparse selected groups consolidate first: `Alt+Shift+ArrowUp` keeps the first selected unit anchored, `Alt+Shift+ArrowDown` keeps the last selected unit anchored
    - the shortcut is ignored from text inputs, textareas, selects, buttons, contenteditable regions, and ARIA combobox/listbox/menu/textbox controls so native form navigation/dropdown shortcuts keep working
  - `Shift+Enter` inserts a new same-type block below the active block; `Alt+Shift+Enter` inserts it above:
    - these insert shortcuts are ignored from the same interactive controls as movement shortcuts, preserving multiline and native form editing behavior
    - selected blocks disable insert-by-shortcut; insertion uses the active block only
    - active operation insertion creates a fresh initialized operation with no selected operation type; it does not copy `operation_template_id` or edited target values from the active operation
    - active Heating/Deformation insertion below targets the end of that visual section, after its current child blocks
  - hovered block toolbar is Notion-like and floats at the upper-left of the block; it contains selection, `+` insert-same-type-below, and drag controls
    - inline `+` insertion uses the hovered block, not necessarily the active block, and is disabled while any block selection exists
    - normal click on `+` inserts below; Shift-click on `+` inserts above
  - all block types render their editable layout all the time
  - compact mutually exclusive mode controls use a shared pill-like segmented style and are hidden unless the block is hovered, active, or focused; this applies to Deformation `Pair / Separate`, Operation `Manual / Auto / Optimization`, and Furnace `Diagram / Table`
  - inline result display is opt-in from the `MenuBar` result toggles; with `Preprocessor` enabled, only the active block or exactly one selected block gets one inline result panel
  - inline Pre panels filter `simulation_steps` by direct source context: Operation/Furnace blocks use their own source rows, while Deformation/Heating sections use rows from their direct Operation/Furnace children
  - inline Pre panels reuse the same side-by-side 2D and 3D preview components as the Steps view and call the same selected-step surface endpoint, so missing legacy mesh artifacts remain explicit errors rather than hidden generated fallback geometry
  - inline Post panels currently show an explicit unavailable placeholder until Post migration defines real result payloads
  - operation blocks always show a title; empty operations use `Empty operation`, and selected operation types use the endpoint-provided `display_name`
  - operation type selector visibility is stateful:
    - empty operations show the selector until a type is selected and saved
    - saved operations hide the selector by default
    - double-clicking the title activates the block and reopens the selector
    - saving hides the selector after the selected type is persisted
    - deactivating the block hides the selector and reverts unsaved operation-type changes to the last saved type
  - operation blocks continue to show the compact horizontal parameters-calculation-mode selector, then either a multiline operation-text editor for non-rounding types or a dense rounding table for `operation.rounding`, plus selected template target fields
  - active block state controls the strong outline, insertion/action anchor behavior, and the temporary operation-type selector edit session; it does not switch the block into a separate alternate renderer
  - move operations are optimistic in the frontend: `draftBlocks` reorder locally first, block wrappers animate position with lightweight `framer-motion`, and backend move requests then persist the same order; failed moves revert and refresh
  - structural copy and clipboard paste keep a short-lived `Inserted here` confirmation line at the final anchor and briefly highlight the inserted block group after refresh so users can see which lower blocks moved down
  - frontend-local resume state uses `localStorage` key `forgelab-document-resume`; app startup switches to `Blocks`, restores the last document/project, and `BlockEditor` restores the saved scroll offset plus selected block ids if they still exist
- `Operations` view behavior:
  - API source is `GET /documents/{document_id}/operations`
  - manual regeneration uses `POST /documents/{document_id}/operations/regenerate`
  - rows show `operation_order`, operation type/label, compact `operation_parameters` chips, and parse status
  - invalid rows show visible parse diagnostics with the source sentence/table row and parser message
  - block hover is bridged from `BlockEditor` metadata to the operations panel
  - hovering an Operation or Furnace highlights rows with the same `source_block_id`
  - hovering a Deformation highlights rows whose source blocks are Operation children within that visual section
  - hovering a Heating highlights rows whose source blocks are Furnace children within that visual section
  - activating an Operation or Furnace filters the right panel to rows generated by that active block
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
  - the inline library action strip is not rendered for this view
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
- Inline library action strip:
  - rendered above `MainEditorPane` for `Dies`, `Die Assemblies`, and `Presses`
  - hidden for `BlockEditor`, `Materials`, and `Simulation`
  - `Materials` keeps its actions in the material rail because that view uses a dedicated workspace layout
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
- Structural edits from `BlockEditor`, `Blocks` Actions, and `Clipboard` are blocked while unsaved draft prop edits exist (user must save/cancel first).
- Frontend visual styling for document editing UI is standardized on a compact Notion-like system:
  - shared style primitives are defined in `frontend/src/index.css` (`ui-*` classes)
  - document-specific page styling is defined by `doc-*` classes; hovered/active/selected block backgrounds may darken, but editable fields/selects/textareas inside them must stay on a light surface so editable controls remain visible immediately
  - active editor-related components (`MenuBar`, `ToolsPane`, `ToolsSwitcher`, `BlockEditor`, clipboard, and block components) should consume `ui-*` classes instead of ad-hoc utility combinations for common controls/surfaces
  - document/editor typography must preserve the Noto-first multilingual sans stack from `frontend/src/index.css` / `frontend/tailwind.config.js`, covering Cyrillic, CJK Chinese/Japanese/Korean, Arabic, Hebrew, Indic, Thai, and emoji fallback
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

### `document` delta
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

### Semantic operation block delta
- Text/editor block types have been removed from the active UI and backend type enum.
- Operation block template metadata is defined in endpoint/service-owned code, not in a runtime block-library table.
- `operation` block creation validates the requested `operation_template_id`, expands defaults into nested `target` props, and stores template metadata for the preprocessor bridge.
- Frontend component registration uses one generic `OperationBlock` for `heating`, `deformation`, `furnace`, and `operation`.
- Operation props are sanitized on create/update/copy so transient render metadata is not persisted.

## System block lifecycle
- For non-copy document creation:
  - `POST /documents` calls `initialize_system_blocks(...)`.
- System blocks are created by explicit fixed prefix order in `backend/app/services/block_type_service.py`.
- Current default system order:
  1. `document` (`fixed_position = 0`)
- After the fixed prefix, non-copy document creation creates a `deformation` bundle containing the first `operation`.
- The fixed setup fields that used to be separate Material/Input Workpiece/Mesh blocks are now properties of `document`.
- The fixed title block is non-removable.

## Fixed leading block rules
- The first block of any new non-copy document is:
  1. `document`
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
- `document_versions` still exists and is used by `document` enrichment/update logic.

## Notes for future updates
- For every new handler-backed block type:
  - update `BlockType` enum
  - register handler in block type registry
  - include initialization and constraints logic if it is a system block
  - register frontend block component if it must render in editor
  - define `get_editable_fields()` and `get_field_limits()` when applicable
  - keep behavior aligned with `draft_synced_props_block` standard unless there is an explicit delta
  - update this file and `PROJECT_CONTEXT.md`
