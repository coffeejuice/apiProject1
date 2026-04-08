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
- `frontend_obsolete/`: archived clients, no changes unless explicitly requested
- `.aiassistant/rules/`: JetBrains context
- `.codex/context/`: Codex context

## Runtime defaults
- Backend server: `http://127.0.0.1:8001` (`backend/run.py`)
- Frontend dev server: `http://127.0.0.1:5173` (`frontend/vite.config.ts`)
- Frontend default API base URL: `http://127.0.0.1:8001` (`frontend/src/lib/apiClient.ts`)

## Backend configuration (`.env`) for setup/install
- Backend settings are loaded by `backend/app/config.py` (`pydantic-settings`) from `backend/.env`.
- During initial setup/install, edit or generate `backend/.env` before starting backend services.
- Keep `backend/.env.example` as the editable template/snapshot for required keys.
- Current file-storage-related keys in `Settings`:
  - `LIBRARY_FILES_ROOT`
  - `NAS_MOUNT_ROOT`
  - `LOGS_FILES_ROOT`
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
- Main app screen (`frontend/src/pages/AppPage.tsx`) uses a split-pane layout:
  - `MenuBar` at top (full width, always visible)
  - below it: `ToolsSwitcher` (left, always visible), `ToolsPane` (middle, collapsible), right editor stack
  - right editor stack: `TopEditorPane` (conditional) + `MainEditorPane` (conditional)
- `ToolsSwitcher` controls `ToolsPane` view visibility.
  - if no tool is active, `ToolsPane` is hidden
  - clicking the currently active tool button hides `ToolsPane` only and preserves the current `MainEditorPane` view
- `ToolsPane` provides views:
  - `Projects`: project list, filter, create modal
  - `Documents`: project-scoped document list, filter, new/copy modals
  - `Blocks`: block icon palette for drag-and-drop or insert into `BlockEditor`
  - `Library`: selector for `Dies`, `Die Assemblies`, `Presses`, and `Materials` main editor views
  - `Users`: active user/session info
- `MainEditorPane` routes active content:
  - default main view: `BlockEditor` (for `Projects`, `Documents`, `Blocks`, `Users`)
  - library main views: `Dies`, `Die Assemblies`, `Presses`, `Materials` (for `Library`)
- `Dies` library view characteristics:
  - die card layout: top row = die name; second row = square STL preview on the left and die metadata on the right
  - each die card includes a small interactive STL preview window (camera-only interaction)
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
  - this is the only active materials UI in the Library tool; it uses a dashboard-style comparison layout and the older standalone `Materials` card view has been removed
  - it renders only parsed DEFORM source-file content referenced by `materials.deform_file_name`
  - it overlays the visible material set on shared dashboard charts built from `GET /library/db/materials/{material_id}/visuals`
  - left rail is a dense full-height scroll area that contains text filter, owner filters, classification filters, placeholder material actions, and simplified material name cards in one shared scroll flow
  - when the Library tool is toggled closed while `Materials` remains active, the left material rail is hidden and the diagrams pane expands to the full main-pane width
  - supports dashboard-local multi-selection: click for single selection, repeated click to clear, Ctrl/Cmd-click to toggle, and Shift-click for range selection
  - highlighted charts are driven by the view's selected material set; a non-scrollable single-line abstract summary above the charts shows selected names with line colors, or all visible materials when nothing is selected, and explicitly labels the view as DEFORM materials
  - dashboard title/metadata details live in the diagrams pane, are shown only for a single active material, and render as a compact two-column key/value layout summarizing DEFORM file, owner, test-record count, note, and diagram load state
  - material designations and linked standards in that single-material header are rendered as a compact table with `Designation`, `Standard`, `Country`, and dynamic chemistry-limit element columns; chemistry cells use compact display strings such as `min-max`, `<max`, `>min`, or `bal`
  - the classification section in that single-material header is a two-column comparison layout: axis labels on the left, all visible-set values on the right, with selected-material values highlighted and other visible-material values muted
  - classification axes are hierarchy-aware: level 1 = object type, level 2 = composition base, level 3 = all other categories
  - material list filtering is classification-aware: no active classification chips means all visible materials remain included; within one axis values are ORed, across axes filters are ANDed
  - classification filter chips and the single-material comparison header are branch-scoped by hierarchy: level 2 values are limited by the active level 1 branch, and level 3 values are limited by the active level 1 + level 2 branch
  - dashboard lazily loads visuals for the visible filtered material set through repeated `GET /library/db/materials/{material_id}/visuals` calls
  - chart rendering is frontend-inline SVG and reuses the same backend diagram payload shape for all visible materials
  - each dashboard chart has `Auto / Manual / Reset` scale controls; in manual mode the first and last tick values on each axis become inline-editable
  - the shared library action strip in `TopEditorPane` is hidden for `Materials`; its placeholder buttons are rendered inside the material rail instead
- `TopEditorPane` routes top content:
  - `VisualEditor` view when `BlockEditor` is active in `MainEditorPane`
  - library action menu when a library main view is active
- `VisualEditor` view in `TopEditorPane` provides horizontal block-order visualization with:
  - when hidden/collapsed, it is fully removed from layout (no header/placeholder)
  - visibility is controlled from `MenuBar` (`Show TopEditorPane` / `Hide TopEditorPane`) for block-editor mode
  - click-to-scroll navigation into `BlockEditor`
  - viewer/editor modes
  - multi-select, move/copy (Ctrl/Cmd-drop), insert, delete for block structure edits

## Frontend visual standard (VisualEditor-based)
- The frontend uses a compact, VisualEditor-derived standard style across panes, controls, cards, lists, and modals.
- Source of truth for reusable visual primitives is `frontend/src/index.css` under `@layer components`.
- Required shared classes:
  - layout/panes: `ui-shell`, `ui-pane`, `ui-pane-header`, `ui-pane-body`
  - toolbar: `ui-toolbar`, `ui-toolbar-title`, `ui-toolbar-meta`
  - surfaces: `ui-card`, `ui-card-body`
  - controls: `ui-btn`, `ui-btn-primary`, `ui-btn-secondary`, `ui-btn-danger`
  - form fields: `ui-input`, `ui-select`, `ui-textarea`
  - lists/modals/status: `ui-list-item`, `ui-list-item-active`, `ui-modal-overlay`, `ui-modal`, `ui-badge`
- Text scale is centrally defined in `frontend/tailwind.config.js` (`fontSize`) with only four sizes:
  - `text-xs` = 11px/15px
  - `text-sm` = 12px/16px
  - `text-base` = 13px/18px
  - `text-lg` = 15px/20px
- Rule for future UI edits:
  - prefer shared `ui-*` classes and the 4-size text palette; avoid introducing ad-hoc spacing/button/input styles unless the standard itself is intentionally updated.

## Domain model summary
- Core runtime entities:
  - Users (`users`)
  - Projects (`projects`)
  - Documents (`documents`)
  - Blocks (`blocks`)
  - Settings (`settings`)
  - Unified library catalog (`library`)
- Project model:
  - `project_id`, `user_id`, optional `material_id` (FK to `materials.material_id`), `name`, `notes`, timestamps, soft delete
- Library API model (currently mounted):
  - table `library`: `id`, `parent_id`, `type`, `name`, `props` (JSONB), timestamps, `is_obsolete`
  - enum values in code: `die`, `die_assembly`, `press`, `press_mode`, `time_between_operations`, `material`, `operation_type`
- Industrial normalized tables also exist in DB/models:
  - `die_types`, `materials`, `dies`, `die_assemblies`, `presses`, `press_modes`, `press_die_map`
  - mounted `/library/db/*` routes read from these normalized tables, while the older `/library/*` list/detail routes still serve from the unified `library` table
- `materials.name` is plain text; national/regional material naming is expected to live in `materials_designations`
- `backend/data/database_seeding/materials.json` now includes fully populated normalized-material seed examples for Ti-6Al-4V, Inconel 718, and Waspaloy across the standards, designations, publications, standard chemistry, test-record, and property-table sections
- Waspaloy is currently a normalized seed-only material with `deform_file_name = null`, so it does not contribute DEFORM charts until a DEFORM source file is added
- Document model:
  - `document_id`, required `project_id`, optional `source_document_id`, optional `editor_user_id`, `first_block_id`, `name`, `notes`, timestamps, soft delete
  - supports inheritance/lineage through `source_document_id`
- Block model:
  - linked-list ordering with `previous_block_id` and `next_block_id`
  - block type is stored as `block_type_id`
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
  - `GET /library/operation-types`
  - `GET /library/operation-types/{item_id}`
  - `GET /library/db/users`
- `GET /library/db/die-types`
- `GET /library/db/materials`
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
- Preserve `frontend_obsolete/` untouched unless user asks.
- Prefer non-destructive changes and keep backend/frontend contract synchronized.

## Current testing reality
- Frontend has Playwright e2e scaffold (`frontend/e2e`).
- Backend `backend/tests/` currently has limited script-style coverage.
- Validate critical backend changes via focused manual checks and targeted tests when feasible.

## Migration policy
- Active migration chain in `backend/alembic/versions/` is:
  - `9ac4e7b1d2f3_squashed_current_schema_baseline.py`
  - `3a4d8f2c1b90_reshape_materials_table.py`
  - `7f7f9945c6f1_add_material_classification_tables.py`
  - `b8c2e4f6a1d0_add_material_classification_hierarchy.py`
  - `c1f4e28b9a7d_add_material_standards_tables.py`
  - `e5d9c3a1b4f7_add_material_chemistry_tables.py`
- `f7a2d4c8e1b3_add_material_property_tables.py`
- `a3d7f1c2e9b4_slim_materials_root_table.py`
- Historical migrations are archived in `backend/alembic/versions_backup/`.
- Current head migration is `a3d7f1c2e9b4`.
- The baseline migration uses `Base.metadata.create_all(checkfirst=True)` / `drop_all(checkfirst=True)` against registered SQLAlchemy models; follow-up migrations must remain idempotent enough to coexist with the squashed baseline on fresh installs.
