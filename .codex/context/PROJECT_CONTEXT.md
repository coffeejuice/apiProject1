---
apply: always
---

# Project Cumulative Context (Codex)

## Purpose
ForgeLab is a monorepo for a project-scoped, Notion-like editor with a FastAPI backend and a React frontend.

## Authoritative sources
- Primary: source code in `backend/` and `frontend/`.
- If code and docs conflict, code is authoritative and context files must be updated.

## Explicit exclusions
- Do not modify JetBrains context in `.aiassistant/rules/`.

## Monorepo structure (current)
- `backend/`: FastAPI API, SQLAlchemy models, Alembic, services, scripts
- `frontend/`: React 19 + TypeScript SPA (Vite), Zustand state, block UI
- `.aiassistant/rules/`: JetBrains context
- `.codex/context/`: Codex context

## Runtime defaults
- Backend server: `http://127.0.0.1:8001` (`backend/run.py`)
- Frontend dev server: `http://127.0.0.1:5173` (`frontend/vite.config.ts`)
- Frontend default API base URL: `http://127.0.0.1:8001` (`frontend/src/lib/apiClient.ts`)
- Runtime logs for API/Pre/Post/Coordinator are local JSONL rotating files under `LOGS_FILES_ROOT`; Solver logs are intentionally excluded from the frontend local log viewer for now.

## Current document/block model override (updated 2026-04-29)
- Active document editor block types are semantic strings only:
  - `document`
  - `heating`
  - `deformation`
  - `furnace`
  - `operation`
- New documents auto-create one fixed, non-removable `document` root block plus one removable `deformation` section with one initial `operation` child.
- `heating` is a removable second-level section/container. Creating a `heating` section auto-creates one child `furnace` block. Multiple `furnace` children are allowed inside one heating section.
- `document_heading`, `input_workpiece`, and numeric editor block IDs are obsolete for active editor flow. Older notes in this file mentioning them are historical and must not be used for new work.
- Operation block templates are endpoint/service-owned code. `GET /operation-templates` exposes the editor-facing Operation block options; `backend/app/services/operation_blocks.py` owns Operation block defaults, selector payloads, and transient frontend metadata. The `Blocks` pane no longer exposes a block catalog.
- `document_blocks.props` stores explicit user-authored properties only, grouped by namespace: `document_properties`, `heating_properties`, `deformation_properties`, `furnace_properties`, and `operation_properties`.
- `document_properties.section_numbering_start` controls visual numbering of second-level Heating/Deformation sections and defaults to `2`.
- `deformation` props now include parser variables under `deformation_properties.deformation_variables`: `tail_chamfering_stroke` and `tail_flattening_stroke`; die selection settings under `deformation_properties.die_type_id`, `top_die_type_id`, `bottom_die_type_id`, `die_selection_mode`, `die_assembly_id`, `top_die_id`, and `bottom_die_id`; per-operation-type feed settings under `deformation_properties.feed_settings.<operation_type>.feed_direction_id`, `feed_first`, `feed_middle`, and `feed_last`; plus explicit old-project speed keys directly under `deformation_properties`: `speed_upsetting` and `speed_prolongation`.
- `furnace` props now expose `furnace_properties.temperature_program`, an ordered list of furnace-control segments. Each segment has `type` (`hold`, `heat`, or `unload`), with hold rows carrying `duration_min` and `temperature_c`. `furnace_class_id` and direct `temperature` inputs are obsolete in the active UI; `furnace_properties.temperature` can still be maintained internally as a compatibility mirror of the last non-empty hold temperature for the current preprocessor bridge.
- `operation` props store dynamic target values under nested JSON at `operation_properties.target`, with template metadata in `operation_template_id`, `operation_template_version`, `operation_kind`, and `template_snapshot`. Most operation types use `operation_properties.operation_text`, a multiline source parsed as right-arrow-separated sentences; `operation.rounding` uses `operation_properties.rounding_table` where one non-empty table row materializes one `document_operations` row.
- `document_operations` is the materialized technological-operation layer between editable `document_blocks` and compiled `simulation_steps`. It no longer stores inherited/effective namespace columns; each row stores final operation JSON in `operation_parameters`.
- Regeneration now creates a first `document_operations` row from the root `document` block with `operation_template_id = document_initial_data` and `operation_kind = billet`. Its `operation_parameters` uses nested namespaces that render as chained-dot parameters: `document_info`, `process_data`, `material`, `input_stock`, and `mesh`. The preprocessor maps this semantic row to the legacy billet/NewBillet compiler path.
- Furnace blocks materialize to `document_operations` rows with `operation_template_id = furnace`; `operation_parameters.temperature_program` contains the table rows from the Furnace block (`number`, `type`, `duration_min`, `temperature_c`).
- Operation rows copy Deformation parameters into `operation_parameters` by explicit materialization code in `backend/app/services/document_operations.py`: die ids are copied to every child operation; `speed_upsetting` is copied only to generated Upsetting rows; `speed_prolongation` is copied to all generated deformation operations except Upsetting and Rounding; feed rows copy `feed_direction_id`, `feed_first`, `feed_middle`, and `feed_last` only for Tail Flattening, Cogging, Radial Cogging, and Transverse Cogging. Copying is strict direct-parent behavior: a Deformation section never inherits missing values from a previous Deformation section during operation materialization.
- `simulation_steps.document_operation_id` is the primary key and required FK to `document_operations.document_operation_id` with cascade delete, enforcing one sibling simulation row per materialized operation row. Operation regeneration creates/removes sibling `simulation_steps` rows together with `document_operations`; valid operation rows set `simulation_steps.preprocess_ready = true`, and Pre later fills compiled output into the existing sibling rows. The active schema no longer has obsolete `simulation_step_id` or old operation-library `block_type_id`.
- Surface preview meshes for Steps are generated only by the active Pre compiler with the restored legacy Trimesh/STL mesh-state path in `backend/app/services/preprocessor/legacy_surface_mesh.py`. The compiler carries previous-row final meshes through billet, heating/furnace, upsetting, prolongation/radial/full-die, and cutting rows, and `backend/app/orchestration/runtime_backend.py` writes JSON/STL artifacts row-by-row under `TEMP_FILES_ROOT/runs/<document_version_id>/<execution_order>/surface/document_operation_<id>/`. `backend/app/services/preprocessor/surface_mesh.py` is only the API payload/container. Hidden geometry-JSON extrusion fallback is forbidden: if a legacy artifact is missing or unreadable, the backend returns an explicit error and the UI shows that error. Compact artifact references are stored under `simulation_steps.metrics.surface_artifacts`; old DB `BYTEA` STL columns are still not restored.
- `document_blocks_library` / `OperationsLibrary` was dropped. `time_between_operations` is keyed by semantic `operation_template_id` pairs plus `press_id`.
- Pre operation definitions are built from preprocessor-local semantic metadata in `backend/app/services/preprocessor/control_program_builder.py`, semantic built-ins for document geometry/heating, and current geometry metadata. Migrated deformation math dispatch is semantic-template based; old numeric operation IDs are not part of active runtime dispatch.
- The old `is_simulation` split was removed from active Pre metadata/compiled rows; every valid `document_operations` row is treated as a simulation/preprocessor row.
- The Pre worker persists compiled output into `simulation_steps` row-by-row. At Pre start, sibling rows are reset to `metrics.preprocessor_status = pending`; each successful row is committed in its own short transaction with `preprocessor_status = compiled` before the next row starts compiling; if a later row fails, previously compiled rows remain visible in the Steps view and the failed row receives diagnostics.
- Draft documents can be manually requeued for Pre from the Steps tool through `POST /documents/{document_id}/simulation-steps/preprocess`; the endpoint keeps the existing saved `document_operations`/`simulation_steps` rows, sets the latest editable `document_versions` row to `preprocess_status = queued` with `run_switch_status = true`, and emits the Pre worker notification. It must not regenerate operations because regeneration deletes current compiled `simulation_steps` output before the worker has produced replacement rows.
- Pre pipeline smoke checks live in `backend/scripts/check_preprocessor_pipeline.py`. Use `--list-support` for semantic adapter coverage, `--document-id <id>` for a dry run, and `--apply` to write compiled output into sibling `simulation_steps`. Current semantic Pre templates are expected to report real adapters only, with no intentional `generic_fallback`.
- Alembic history was compacted while the project is still pre-production. The active chain starts from metadata baseline `0001_current_schema_baseline.py` and continues with normal incremental migrations.

## Backend configuration (`.env`) for setup/install
- Backend settings are loaded by `backend/app/config.py` (`pydantic-settings`) from `backend/.env`.
- During initial setup/install, edit or generate `backend/.env` before starting backend services.
- Keep `backend/.env.example` as the editable template/snapshot for required keys.
- Current file-storage-related keys in `Settings`:
  - `LIBRARY_FILES_ROOT`
  - `NAS_MOUNT_ROOT`
  - `LOGS_FILES_ROOT`
  - `LOGGING_LEVEL`
  - `LOG_FILE_MAX_BYTES`
  - `LOG_FILE_BACKUP_COUNT`
  - `TEMP_FILES_ROOT`
- Keep secrets and machine-specific paths in `.env`; do not hardcode them in source files.

## Product flow (Project -> Document -> Block)
1. User authenticates via JWT (`/auth/login`) and frontend stores bearer token.
2. Frontend loads projects with `GET /projects` (`useDocumentsStore.fetchProjects`).
3. User selects a project; frontend loads that project's documents with `GET /projects/{project_id}/documents`.
4. New documents are created in a project (`POST /documents` with `project_id`), optionally copied from another document in the same project (`source_document_id`).
5. Editor loads ordered blocks with `GET /documents/{document_id}/blocks/root` (linked-list order from `first_block_id` and `next_block_id`).
6. Edits are persisted via `POST /documents/{document_id}/commit` operation batches (`insert_block`, `delete_block`, `move_block`, `update_props`, `update_text`).
7. Optional document relationship features use lineage and diff (`/documents/{id}/lineage`, `/documents/{id}/diff/{other_id}`).

## Backend architecture summary
- Framework: FastAPI
- Data layer: SQLAlchemy 2 ORM (sync), PostgreSQL
- Migrations: Alembic
- Validation: Pydantic models in `backend/app/schemas.py`
- Auth: JWT bearer (`/auth/login`, `/auth/me`)
- Active routers in `backend/app/main.py`:
  - `auth`
  - `projects`
  - `document`
  - `blocks`
  - `search` and `document_search_router`
  - `settings`
  - `library`
  - `logs`
  - `operation_templates`
  - `workflow`
- Not mounted in current `main.py`:
  - legacy `revisions`, `sharing`, `import_export`, `migration` routers

## Frontend architecture summary
- Stack: React 19, TypeScript, Vite, Tailwind
- Routing: `react-router-dom`
- State: Zustand stores, primarily `useDocumentsStore` for project/document flow
- API access rule: use `frontend/src/lib/apiClient.ts` (avoid direct `fetch` in components)
- Token and base URL persistence keys:
  - `forgelab-token`
  - `forgelab-base-url`
- Document resume persistence key:
  - `forgelab-document-resume`
  - stores last opened document/project, forces restore into `Blocks` view, restores document scroll offset, and restores selected block ids when the blocks still exist
- Main app screen (`frontend/src/pages/AppPage.tsx`) uses a split-pane layout:
  - `MenuBar` at top (full width, always visible)
  - below it: `ToolsSwitcher` (left, always visible), `ToolsPane` (middle, collapsible), right editor area
  - right editor area: optional inline library action strip + `MainEditorPane`
- `ToolsSwitcher` controls `ToolsPane` view visibility.
  - if no tool is active, `ToolsPane` is hidden
  - clicking the currently active tool button hides `ToolsPane` only and preserves the current `MainEditorPane` view
- `ToolsPane` provides views:
  - `Projects`: project list, filter, create modal
  - `Documents`: project-scoped document list, filter, new/copy modals
    - supports zero, one, or many selected documents
    - first opening the Documents tool selects the first document in the current list if no explicit selection exists
    - only exactly one selected document populates `currentDoc` and enables document-related views; zero or multiple selections make document-related views behave as if no document is selected
    - document selection is stored in `useDocumentsStore` and survives switching tool views
  - `Blocks`: shared pane with `Actions` and `Clipboard` tabs
    - `Actions` is the default tab and acts as a selected-block context menu; actions are available only when exactly one non-root block is selected
    - `Actions` provides copy, cut, remove, paste-after-selected, and clear-selection controls previously shown above the main document canvas
    - `Clipboard` is frontend-session-only memory for block cut/copy/paste; new cut/copy sessions open this tab automatically
  - `Operations`: no middle pane; selecting the tool opens a split main editor where the left side is the regular document editor and the right side is a read-only `document_operations` table
  - `Steps`: no middle pane; selecting the tool opens the `simulation_steps` inspector for the selected document and shows a narrow left step list; clicking the active `Steps` tool again hides only that left step list while keeping the main Steps inspector open
  - `Library`: narrow icon-only selector for `Dies`, `Die Assemblies`, `Presses`, and `Materials` main editor views; this pane omits a title/header and uses shared tooltips for labels
  - `Simulation`: no middle pane; selecting the tool switches the main editor area to a simulation dashboard
  - `Logs`: no middle pane; selecting the tool switches the main editor area to a local log viewer for API, Pre, Post, and Coordinator logs
    - selected service/worker log file can be cleared from the Logs toolbar via `DELETE /logs/{service}?worker_name=...`
  - `Users`: active user/session info
- `MainEditorPane` routes active content:
  - default main view: `BlockEditor` (for `Projects`, `Documents`, `Blocks`, `Users`)
  - operations main view: split `BlockEditor` plus `DocumentOperationsView` (for `Operations`)
  - steps main view: `SimulationStepsView` reading `GET /documents/{document_id}/simulation-steps` plus `GET /documents/{document_id}/blocks/root`; shows a narrow hideable left step list with visual-only Heating/Deformation/Furnace/Operation title cards, selected-step diagnostics, shared-scale 2D overlays, and outline-based 3D previews
  - library main views: `Dies`, `Die Assemblies`, `Presses`, `Materials` (for `Library`)
  - simulation main view: `Simulation` dashboard (for `Simulation`)
  - logs main view: `LogsView` reading `GET /logs/services` and `GET /logs/{service}/tail`; Solver is not included
- `BlockEditor` renders a visual document hierarchy over the flat `document_blocks` linked list:
  - the `document` block is shown as the document canvas/title area and contains Material, Input Workpiece, and Mesh setup properties
  - the `document` block groups setup fields into compact Notion/Word-like sections: `Process data`, `Material`, `Input stock size`, and `Mesh`; section titles use one visual tab and their parameter tables use a second deeper tab
  - `Heating` and `Deformation` semantic block types are shown as second-level sections inside the document canvas
  - `Furnace` blocks following a `Heating` block are visually nested under that Heating until the next Heating/Deformation section
  - `Operation` blocks following a `Deformation` block are visually nested under that Deformation until the next Heating/Deformation section
  - this hierarchy is visual only; DB storage remains a flat linked list with no `parent_block_id`
  - one non-title block can be the active block; it is shown with a strong outline and acts as the default insertion/paste anchor
  - direct block click, input focus/click/change inside a block, successful drag/drop, insert, and paste make a block active; selection checkbox clicks and drag-handle clicks alone do not
  - document block selection is separate from active state; exactly one selected block drives the `Blocks > Actions` context menu, while multi-selection remains useful for drag-group preparation
  - Heating and Deformation section titles are auto-numbered from `document_properties.section_numbering_start`; a Heating immediately followed by a Deformation is shown as `N.1 Heating` and `N.2 Deformation`, otherwise each Heating/Deformation uses simple `N.` numbering
  - the numbering start value is edited through a compact hover/focus control in the first Heating/Deformation title; subsequent section numbers are read-only
  - Deformation sections are visually ordered as title/header first, then a die selector parameter block, then child Operation blocks, then Deformation parameter fields as a footer after the child operations; the underlying linked-list order remains `deformation -> operation...`
  - the Deformation footer feed table is conditional: it renders only rows whose Operation type has feed and is present among that Deformation section's child Operation blocks; it excludes Upsetting, Tail Chamfering, Rounding, and Cutting; a new Deformation with no feed-consuming child operation types hides the feed table completely
  - Operation block titles are auto-numbered inside each Deformation section with simple `1.`, `2.`, `3.` numbering that restarts for every Deformation
  - operation blocks always show a title; empty operations are titled `Empty operation`, and after selecting/saving a type the title uses the endpoint-provided template `display_name`
  - furnace blocks render a diagram/table switch for `furnace_properties.temperature_program`; diagram mode visualizes hold, heat-up, and unload segments, while table mode edits rows with `--`, `/`, and `\` type controls plus hold duration/temperature fields
  - operation type selector visibility is stateful: empty operations show it until a type is selected and saved; saved operations hide it by default; double-clicking the title reopens it; deactivating the block hides it and discards unsaved type changes
  - during drag, dense zero-height insertion markers show a thin blue `Insert here` line at the current drop target; hovering a block previews insertion after that block without adding permanent document spacing
  - document block move uses optimistic local reorder plus lightweight `framer-motion` position animation on block wrappers, so lower blocks slide smoothly to new positions instead of waiting for a backend refresh jump
  - structural copy and clipboard paste keep a short-lived `Inserted here` confirmation line at the final anchor and briefly highlight the inserted block group so the actual new position stays visible after backend refresh
  - all block types render their editable layout all the time; active state only controls the strong outline plus insertion/action anchor behavior
  - editor resume state is frontend-local: the app reopens the last document in `Blocks` view and `BlockEditor` restores scroll position plus selected blocks from `forgelab-document-resume`
- `Simulation` main view characteristics:
  - owner filter uses icon-only controls for `Current user`, `All users`, or `Selected user`, with a dropdown shown only for the selected-user mode
  - renders three main tables: `Documents`, `Simulations`, and `Solver PCs`
  - `Documents` and `Simulations` rows include run/stop toggle, read-only workflow status, queue position, and pause/continue action where applicable
  - `Simulations` table supports drag-and-drop queue reordering by row grab handle and submits the reordered version list through the workflow API
  - `Solver PCs` table is read-only and summarizes worker occupancy and machine resource data
- `Operations` main view characteristics:
  - left pane reuses the current `BlockEditor` without changing document editing behavior
  - right pane calls `GET /documents/{document_id}/operations` and renders saved `document_operations` rows
  - a compact refresh icon in the Operations pane calls `POST /documents/{document_id}/operations/regenerate` to manually rebuild rows from saved block data
  - rows show operation order, operation type/label, compact chips for `operation_parameters`, and parse status
  - invalid rows show visible parse diagnostics with the source sentence/table row and parser message, not only a tooltip
  - the first row is the root Document-derived `document_initial_data` billet row, exposing `document_info.*`, `process_data.*`, `material.*`, `input_stock.*`, and `mesh.*` chips
  - array-valued target rows, such as Furnace `temperature_program`, are expanded into indexed chained-dot chips like `temperature_program.1.type`
  - hovering a Furnace or Operation block highlights rows generated directly from that block
  - hovering a Heating section highlights rows generated from its Furnace children; hovering a Deformation section highlights rows generated from its Operation children
  - activating an Operation or Furnace block filters the right pane to rows generated by that active block
  - when the document has unsaved block changes, the right pane warns that operations reflect saved document state until the user saves
- `Steps` main view characteristics:
  - calls `GET /documents/{document_id}/simulation-steps` for the currently selected single document
  - calls `GET /documents/{document_id}/blocks/root` to build a visual-only structure index for the left step list
  - its compact refresh icon is an active Pre command: it calls `POST /documents/{document_id}/simulation-steps/preprocess`, then reloads the step list; it does not regenerate `document_operations` or erase current compiled rows
  - renders a very narrow left list while the `Steps` tool button is active; clicking the active `Steps` button hides only this list and leaves the main Steps view open
  - the left list has independent vertical scrolling, so long step lists do not scroll the selected-step 2D/3D/detail workspace
  - the left list contains visual-only title cards for Heating/Deformation sections and Furnace/Operation child blocks with their visual numbers
  - step cards are nested under those title cards and show saved user-entered variables from `document_operations.operation_parameters`
  - the main list intentionally avoids a full raw DB-table layout
  - selecting a step card opens detail panels for user operation parameters, `parameter_values`, `control_parameters`, `step_specific_parameters`, `initial_geometry`, `final_geometry`, `metrics`, status, and typed columns
  - 2D visualization overlays `initial_geometry.cross_section_outline` and `final_geometry.cross_section_outline` with one shared proportional scale and small in-graphic tables for H/W/L/A and available strain/deformation metrics
  - 3D visualization lazy-loads JSON triangular surface meshes from `GET /documents/{document_id}/simulation-steps/{document_operation_id}/surface`; this endpoint reads only legacy Trimesh JSON/STL artifacts written during Pre row compilation. If artifacts are absent, unreadable, or generated by a non-legacy source, the endpoint returns an explicit error and the frontend displays that error instead of synthesizing a local geometry fallback. Round cross-sections must come from the migrated old-project STL path, not from rectangular-prism approximation. Compact artifact references live in `simulation_steps.metrics.surface_artifacts`.
  - selected-step artifact files can be downloaded through `/documents/{document_id}/simulation-steps/{document_operation_id}/surface/artifacts/{initial|final}/{json|stl}`.
- `Dies` library view characteristics:
  - die card layout: top row = die name; second row = square STL preview on the left and die metadata on the right
  - each die card includes a small interactive STL preview window (camera-only interaction)
  - `dies.classification_path` and `die_assemblies.classification_path` store open dot-separated classification keys such as `flat.top`, `vdie.bottom`, `gfm.left`, and `gfm.assembly`
  - controls: drag to rotate, right-drag to pan, wheel to zoom, and reset-view button
  - initial camera is isometric (Z up, X left-down, Y right-down), model centered and fitted to ~90% of viewport
  - STL source is derived from `dies.die_template_file_name` (`*.zip` stem -> `*.stl`) and served by backend endpoint `/library/db/dies/stl/{file_name}`
- `Presses` library view characteristics:
  - shows one press card per `presses` record
  - each press card combines related `press_modes` data into a single layout (no standalone press-mode cards)
  - top row inside a press card: `Power Limit Diagram` + `Power Limit Table`
  - bottom inside a press card: sortable, horizontally scrollable `Press Modes Table` with sticky left `Legend` column
  - `Power Limit Diagram` plots one curve per related press mode with engineering-style axes: X = `Force, MN`, Y = `Speed, mm/s`
  - diagram always includes `x=0` and `y=0` ticks; each axis starts at `0` when that axis has no negative values
  - exactly one press-mode curve/row is selected at a time; default selection is `is_default_press_mode = true` (fallback: first by `id`)
  - `Power Limit Table` shows values only for the currently selected press mode
  - `Press Modes Table` horizontal scroll is synchronized across all press cards to simplify cross-press comparison
- `Materials` library view characteristics:
  - this is the only active materials UI in the Library tool; it uses one mode-based workspace with `dashboard`, `editor`, and `copy` modes, and the older standalone `Materials` card view has been removed
  - it renders only parsed DEFORM source-file content referenced by `materials.deform_file_name`
  - it overlays the visible material set on shared dashboard charts built from `GET /library/db/materials/{material_id}/visuals`
  - left rail is a dense full-height scroll area that contains text filter, owner filters, classification filters, placeholder material actions, and simplified material name cards in one shared scroll flow
  - left-rail actions now open in-place workspace modes instead of placeholder buttons:
    - `New material` -> editor mode with an empty root-material draft
    - `Edit selected material` -> editor mode for the selected material
    - `Copy into selected material` -> copy-wizard mode with the selected material as target
  - when the Library tool is toggled closed while `Materials` remains active, the left material rail is hidden and the diagrams pane expands to the full main-pane width
  - supports dashboard-local multi-selection: click for single selection, repeated click to clear, Ctrl/Cmd-click to toggle, and Shift-click for range selection
  - highlighted charts are driven by the view's selected material set; a non-scrollable single-line abstract summary above the charts shows selected names with line colors, or all visible materials when nothing is selected, and explicitly labels the view as DEFORM materials
  - dashboard title/metadata details live in the diagrams pane, are shown only for a single active material, and render as a compact two-column key/value layout summarizing DEFORM file, owner, test-record count, note, and diagram load state
  - materials without `deform_file_name` remain visible in the material browser and editor/copy workflows, but they are excluded from DEFORM chart loading and dashboard plot overlays
  - material designations and linked standards in that single-material header are rendered as a compact table with `Designation`, `Standard`, `Country`, and dynamic chemistry-limit element columns; chemistry cells use compact display strings such as `min-max`, `<max`, `>min`, or `bal`
  - the classification section in that single-material header is a two-column comparison layout: axis labels on the left, all visible-set values on the right, with selected-material values highlighted and other visible-material values muted
  - classification axes are hierarchy-aware: level 1 = object type, level 2 = composition base, level 3 = all other categories
  - the level-3 classification axis `manufacturing_route` is restricted to the approved value set `cast`, `wrought`, `powder`, `additive`
  - material list filtering is classification-aware: no active classification chips means all visible materials remain included; within one axis values are ORed, across axes filters are ANDed
  - classification filter chips and the single-material comparison header are branch-scoped by hierarchy: level 2 values are limited by the active level 1 branch, and level 3 values are limited by the active level 1 + level 2 branch
  - materials filtering also includes a frontend-only pseudo category `Standard level`, derived from non-empty designation-country values exposed through `designation_links.country` (backed by `material_standards_catalog.country_or_region`); it is not stored in the normalized classification tables
  - `Standard level` is single-select, defaults to `None`, is treated as a minor branch under `Object type` + `Composition Base`, and is rendered below the regular classification categories in the material rail
  - when `Standard level = None`, material list cards and the dashboard summary line use the canonical `materials.name`; when a concrete standard-level value is active, they switch to a compound label built from the material's designation rows that match that selected country/level
  - dashboard lazily loads visuals for the visible filtered material set through repeated `GET /library/db/materials/{material_id}/visuals` calls
  - chart rendering is frontend-inline SVG and reuses the same backend diagram payload shape for all visible materials
  - each dashboard chart has `Auto / Manual / Reset` scale controls; in manual mode the first and last tick values on each axis become inline-editable
  - the inline library action strip is hidden for `Materials`; material-specific actions are rendered inside the material rail instead
  - editor mode currently saves the normalized material root, classification assignments, and designation rows in one workspace payload
  - in editor mode, `DEFORM file` is no longer a free-text input; it is shown as a read-only stored file name plus a staged local-file upload flow
  - the staged upload flow accepts one `.key` / `.KEY` file from the user’s local machine, requires explicit `Upload` / `Cancel`, and stores the uploaded file under `backend/data/materials/`; the returned stored file name is then written into `materials.deform_file_name` on save
  - copy mode currently copies selected normalized subtrees between materials:
    - note and/or `deform_file_name`
    - classification assignments
    - designation rows plus linked standard chemistry rows
    - test-record subtrees including chemistry results and property tables
- Inline library action strip:
  - rendered above `MainEditorPane` for `Dies`, `Die Assemblies`, and `Presses`
  - hidden for `BlockEditor`, `Materials`, and `Simulation`
  - `Materials` keeps its actions in the material rail because that view uses a dedicated workspace layout

## Frontend visual standard
- The frontend uses a compact Notion-like standard style across panes, controls, cards, lists, and modals.
- Source of truth for reusable visual primitives is `frontend/src/index.css` under `@layer components`.
- Global typography uses a Noto-first multilingual sans stack (`--ui-font-sans` in `frontend/src/index.css` and `fontFamily.sans` in `frontend/tailwind.config.js`) with fallbacks for Cyrillic, CJK Chinese/Japanese/Korean, Arabic, Hebrew, Indic, Thai, and emoji; do not replace it with Latin-only font stacks.
- Document editing uses a separate Word/Notion-like `doc-*` style family in `frontend/src/index.css`: clean page surface, borderless inputs, title-only block labels, indentation-based hierarchy, subtle hover tools, darker selected block background, and strong active block outline.
- Compact mutually exclusive mode selectors in document blocks use the shared `doc-segmented-control` / `doc-segmented-button` standard. These controls are hidden in resting state and shown only on block hover, active block state, or focus-within; current examples are Deformation `Pair / Separate`, Operation `Manual / Auto / Optimization`, and Furnace `Diagram / Table`.
- Required shared classes:
  - layout/panes: `ui-shell`, `ui-pane`, `ui-pane-header`, `ui-pane-body`
  - toolbar: `ui-toolbar`, `ui-toolbar-title`, `ui-toolbar-meta`
  - surfaces: `ui-card`, `ui-card-body`
  - controls: `ui-btn`, `ui-btn-primary`, `ui-btn-secondary`, `ui-btn-danger`
  - form fields: `ui-input`, `ui-select`, `ui-textarea`, `ui-field-readonly`, `ui-field-readonly-multiline`
  - lists/modals/status: `ui-list-item`, `ui-list-item-active`, `ui-modal-overlay`, `ui-modal`, `ui-badge`
- Text scale is centrally defined in `frontend/tailwind.config.js` (`fontSize`) with only four sizes:
  - `text-xs` = 11px/15px
  - `text-sm` = 12px/16px
  - `text-base` = 13px/18px
  - `text-lg` = 15px/20px
- Rule for future UI edits:
  - prefer shared `ui-*` classes and the 4-size text palette; avoid introducing ad-hoc spacing/button/input styles unless the standard itself is intentionally updated.
  - field-state standard is centralized in `frontend/src/index.css`: editable resting uses `ui-input` / `ui-select` / `ui-textarea`, focused editing uses their built-in accent border/ring state, and read-only values should render with `ui-field-readonly` (plus `ui-field-readonly-multiline` for wrapped content) instead of ad-hoc gray `span` / `div` styling
  - tooltip/hint standard is the shared `frontend/src/components/ui/Tooltip.tsx` component; do not introduce native `title` tooltips for new UI work
  - shared tooltip behavior must render above all panes via portal, use viewport-aware positioning, and avoid cursor overlap when possible

## Domain model summary
- Core runtime entities:
  - Users (`users`)
  - Projects (`projects`)
  - Documents (`documents`)
  - Document Blocks (`document_blocks`)
  - Settings (`settings`)
  - Unified library catalog (`library`)
- Project model:
  - `project_id`, `user_id`, optional `material_id` (FK to `materials.material_id`), `name`, `notes`, timestamps, soft delete
  - version-specific material state is now stored in `material_versions`; documents carry `material_version_id`
- Library API model (currently mounted):
  - table `library`: `id`, `parent_id`, `type`, `name`, `props` (JSONB), timestamps, `is_obsolete`
  - enum values in code: `die`, `die_assembly`, `press`, `press_mode`, `time_between_operations`, `material`
- Industrial normalized tables also exist in DB/models:
  - `die_types`, `materials`, `dies`, `die_assemblies`, `presses`, `press_modes`, `press_die_map`
  - mounted `/library/db/*` routes read from these normalized tables, while the older `/library/*` list/detail routes still serve from the unified `library` table
- `materials.name` is plain text; national/regional material naming is expected to live in `materials_designations`
- `backend/data/database_seeding/materials.json` now includes fully populated or partial normalized-material seed examples for Ti-6Al-4V, Ti80, Ti-10V-2Fe-3Al, Inconel 718, Inconel 600, Inconel 625, Inconel 690, Inconel 706, Haynes 188, Haynes 230, Haynes 282, Hastelloy X, Alloy 263, Waspaloy, Nimonic 90, GH4698, GH4720Li, A286, FGH96, FGH4097, Alloy 901, Incoloy 903, Incoloy 907, Incoloy 909, Incoloy 925, GH710, GH4780, K4169, K418B, K417G, K648, GH4099, and A-100 across the standards, designations, publications, standard chemistry, test-record, and property-table sections
- `backend_obsolete/GBT3620.1-2016_Table1.json`, `backend_obsolete/GBT3620.1-2016_Table2.json`, and `backend_obsolete/GBT3620.1-2016_Table3.json` are the current source-of-truth inputs for GB/T 3620.1 titanium designation chemistry; the corresponding designations and standard-chemistry rows in `materials.json` are now generated from those extracted tables, including all listed TA*, TB*, and TC* grades
- The `nominal_composition` column from those GB/T Table 1–3 extracts is also imported as additional `materials_designations` rows under `standard_id = 5`, attached to the same materials as the base GB/T designation rows
- `backend_obsolete/GBT3620.1-2016_TableB1.json` is the current source-of-truth cross-reference table for mapping GB/T commercially pure titanium grades to ASTM Grade / UNS designation pairs; the matching ASTM designation rows for `TA1G`, `TA2G`, `TA3G`, and `TA4G` are seeded from it
- The current batch also merged designation-only aliases into existing cards for `GH4738 -> Waspaloy`, `GH3625 -> Inconel 625`, `GH907 -> Incoloy 907`, and `GH4169G -> Inconel 718`, using explicit caveats where only secondary cross-reference evidence was accessible.
- Inconel 600, Inconel 625, Inconel 690, Inconel 706, Haynes 188, Haynes 230, Haynes 282, Hastelloy X, Alloy 263, Waspaloy, Nimonic 90, GH4698, GH4720Li, A286, FGH96, FGH4097, Alloy 901, Incoloy 903, Incoloy 907, Incoloy 909, Incoloy 925, GH710, GH4780, K4169, K418B, K417G, K648, GH4099, and A-100 are currently normalized seed-only materials with `deform_file_name = null`, so they do not contribute DEFORM charts until DEFORM source files are added
- Document model:
  - `document_id`, required `project_id`, optional `source_document_id`, optional `editor_user_id`, `first_block_id`, `name`, `notes`, timestamps, soft delete
  - supports inheritance/lineage through `source_document_id`
- Block model:
  - linked-list ordering with `previous_block_id` and `next_block_id`
  - active block types are semantic strings: `document`, `heating`, `deformation`, `furnace`, and `operation`
  - new documents auto-create one fixed non-removable `document` block, then one `deformation` bundle containing its first `operation`
  - `document` owns title/setup fields: `name`, `heat_no`, `finished_size`, `remarks`, `preview_status`, `material_id`, `geometry_type_id`, `weight`, `attributes`, `mesh_elements`, and `section_numbering_start`; these fields materialize to the `document_initial_data`/`billet` row in `document_operations`
  - `heating` is a second-level container with no active editable parameters
  - `furnace` is a child of `heating` and exposes the `temperature_program` used by the diagram/table editor; old direct `furnace_class_id` and `temperature` fields are not user-editable
  - `deformation` is a section/container block; die settings live under old-project-compatible `deformation_properties.die_assembly_id`, `top_die_id`, and `bottom_die_id`, parser variables live under `deformation_properties.deformation_variables`, per-operation-type feed settings live under `deformation_properties.feed_settings`, explicit forming speeds live under `deformation_properties.speed_upsetting` and `speed_prolongation`, and user-visible operation details live in child `operation` blocks
  - `operation` stores endpoint-provided template metadata, optional multiline operation text, optional rounding table rows, and nested dynamic `target` variables
  - operation block template metadata is owned by `backend/app/services/operation_blocks.py` and exposed through `GET /operation-templates`; operation text/table materialization rules are explicit code in `backend/app/services/document_operations.py`
  - metadata flags: `is_system`, `is_removable`, `fixed_position`
- Legacy ACL/share/version/server/log tables remain in models and DB for compatibility and existing flows.
- Full database schema, table inventory, key columns, JSONB payload notes, and seeding-layout details are tracked in `.codex/context/DB_SCHEMA.md`.

## Access model summary
- Project owner controls project CRUD and project-scoped document listing.
- Document access allows:
  - owner of the parent project, or
  - delegated editor (`documents.editor_user_id`)

## API surface (active key routes)
- System:
  - `GET /`
  - `GET /health`
- Auth:
  - `POST /auth/register`
  - `POST /auth/login`
  - `GET /auth/me`
- Projects:
  - `POST /projects`
  - `GET /projects`
  - `GET /projects/{project_id}`
  - `PATCH /projects/{project_id}`
  - `DELETE /projects/{project_id}`
  - `GET /projects/{project_id}/documents`
- Documents:
  - `POST /documents`
  - `GET /documents`
  - `GET /documents/{document_id}`
  - `PATCH /documents/{document_id}`
  - `DELETE /documents/{document_id}`
  - `POST /documents/{document_id}/restore`
  - `POST /documents/{document_id}/copy`
  - `GET /documents/{document_id}/lineage`
  - `GET /documents/{document_id}/diff/{other_document_id}`
  - `POST /documents/{document_id}/sessions/start`
  - `POST /documents/{document_id}/sessions/{session_id}/end`
  - `GET /documents/{document_id}/sessions`
- Blocks and commits:
  - `GET /documents/{document_id}/blocks/root`
  - `POST /documents/{document_id}/blocks`
  - `PATCH /blocks/{block_id}`
  - `POST /blocks/{block_id}/move`
  - `DELETE /blocks/{block_id}`
  - `POST /documents/{document_id}/commit`
- Search:
  - `GET /search?q=...`
  - `GET /documents/{document_id}/search?q=...`
- Settings:
  - `GET/POST /settings/`
  - `DELETE /settings/{setting_id}`
  - `GET /settings/resolve/{key}`
  - `POST /settings/provision/apply`
  - `POST /settings/provision/file/{filename}`
- Library:
  - `GET /library/dies`
  - `GET /library/dies/{item_id}`
  - `GET /library/die-assemblies`
  - `GET /library/die-assemblies/{item_id}`
  - `GET /library/presses`
  - `GET /library/presses/{item_id}`
  - `GET /library/press-modes`
  - `GET /library/press-modes/{item_id}`
  - `GET /library/time-between-operations`
  - `GET /library/time-between-operations/{item_id}`
  - `GET /library/db/users`
- `GET /library/db/die-types`
- `GET /library/db/materials`
  - returns only non-obsolete materials
- `GET /library/db/materials/{material_id}/workspace`
- `POST /library/db/materials/workspace`
- `PATCH /library/db/materials/{material_id}/workspace`
- `DELETE /library/db/materials`
  - soft-deletes the selected materials and marks nested designation / chemistry / test-record / property-table rows obsolete where those tables support `is_obsolete`
- `POST /library/db/materials/copy`
- `POST /library/db/materials/upload-deform-file`
- `GET /library/db/material-standards`
- `GET /library/db/material-classification`
- `GET /library/db/materials/{material_id}/visuals`
  - `GET /library/db/dies`
  - `GET /library/db/die-assemblies`
  - `GET /library/db/presses`
  - `GET /library/db/press-modes`

## Materials parser service
- Backend materials source-file parsing now lives under `backend/app/services/materials/`.
- The structure is vendor-neutral and organized for multiple software families:
  - `parsers/deform/`
  - `parsers/forge/`
  - `parsers/qform/`
  - `parsers/simufact/`
- Current implementation status:
  - `deform` parser is implemented for `*.key` / `*.KEY` source files
  - other parser directories are placeholders for future implementations
- `Materials` currently visualizes only DEFORM-backed material data; source material files are resolved from `materials.deform_file_name`, and parser selection is currently fixed to the DEFORM parser with case-insensitive file lookup under `backend/data/materials/deform/` and fallback to `backend/data/materials/`.
- Current DEFORM visual payloads are exposed via `GET /library/db/materials/{material_id}/visuals`.
- Current DEFORM diagrams include:
  - a default `Flow Stress vs Strain` slice derived from `FSTRES`
  - temperature-based line diagrams when available for `YOUNG`, `POISON`, `EXPAND`, `THRCND`, and `HEATCP`

## Global coding constraints for this repo
- Keep the primary product hierarchy as `Project -> Document -> Block`.
- Treat block ordering as linked-list based (`first_block_id`, `previous_block_id`, `next_block_id`); do not reintroduce `order_key` or parent-tree assumptions.
- New documents must remain project-scoped (`project_id` required).
- Respect soft delete on both projects and documents (`deleted_at`) unless endpoint explicitly includes deleted data.
- Keep schemas in `backend/app/schemas.py` aligned with model/router changes.
- `frontend_obsolete/` was removed after active React/Vite frontend became the only supported client.
- Prefer non-destructive changes and keep backend/frontend contract synchronized.

## Current testing reality
- Frontend has Playwright e2e scaffold (`frontend/e2e`).
- Backend `backend/tests/` currently has limited script-style coverage.
- Validate critical backend changes via focused manual checks and targeted tests when feasible.

## Migration policy
- Active migration chain in `backend/alembic/versions/` starts from the compact baseline:
  - `0001_current_schema_baseline.py`
  - `0002_simplify_document_operations_parameters.py`
  - `0003_require_simulation_step_document_operation.py`
  - `0004_use_document_operation_id_as_simulation_step_pk.py`
  - `0005_materialize_simulation_step_siblings.py`
- `backend/alembic/versions_backup/` was removed; active Alembic history is under `backend/alembic/versions/`.
- Current head migration is `0005_step_siblings`.
- Existing pre-compaction development databases should be stamped with `alembic stamp --purge head` after confirming their schema matches current models.
- The baseline migration uses `Base.metadata.create_all(checkfirst=True)` / `drop_all(checkfirst=True)` against registered SQLAlchemy models; follow-up migrations are normal incremental migrations from `0001_current_schema`.
