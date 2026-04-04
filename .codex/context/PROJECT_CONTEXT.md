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
  - `Library`: selector for `Dies`, `Die Assemblies`, `Presses`, `Materials` main editor views
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
  - shows one material card per `materials` record
  - supports text filtering by `material_id`, localized `name`, `source`, `source_version`, and `file_name`
  - supports the shared owner filter used by other library views
  - selected material cards expand to show the raw `properties` JSON payload
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
- Document model:
  - `document_id`, required `project_id`, optional `source_document_id`, optional `editor_user_id`, `first_block_id`, `name`, `notes`, timestamps, soft delete
  - supports inheritance/lineage through `source_document_id`
- Block model:
  - linked-list ordering with `previous_block_id` and `next_block_id`
  - block type is stored as `block_type_id`
  - metadata flags: `is_system`, `is_removable`, `fixed_position`
- Legacy ACL/share/version/server/log tables remain in models and DB for compatibility and existing flows.

## DB consistency snapshot (updated 2026-03-23)
- Alembic code state:
  - new head migration file: `3a4d8f2c1b90_reshape_materials_table.py`
  - baseline remains `9ac4e7b1d2f3_squashed_current_schema_baseline.py`
- Expected schema change in this turn:
  - `materials` now stores `name`, `source`, `source_version`, `file_name`, `properties`, `is_obsolete`, `created_at`, `obsolete_at`, `owner_id`
  - `projects.material_id` now points to `materials.material_id`
- Frontend status: `npm run typecheck` passes after the materials update.
- Backend verification: `python3 -m compileall backend/app backend/alembic/versions/3a4d8f2c1b90_reshape_materials_table.py backend/db_setup/reinit_db.py` passes.
- Backend tests: `pytest` is not installed in `backend/.venv`, so automated backend test execution is unavailable.

## DB tables and columns (public schema)
- Tables currently present:
  - `alembic_version`, `blocks`, `config`, `devices`, `die_assemblies`, `die_types`, `dies`, `document_acl`, `document_edit_sessions`, `document_versions`, `documents`, `library`, `logs`, `materials`, `operations_library`, `physical_machines`, `press_die_map`, `press_modes`, `presses`, `projects`, `servers`, `settings`, `share_links`, `time_between_operations`, `users`
- Core editor/auth tables:
  - `users`: `user_id`, `login`, `email`, `password_hashed`, `signal_clear_token`, `supervisor_id`, `full_name`, `language_code`, `user_settings`, `user_priority_enum`, `created_at`
  - `projects`: `project_id`, `user_id` (FK `users.user_id`), `material_id` (FK `materials.material_id`), `name`, `notes`, `created_at`, `updated_at`, `deleted_at`
  - `documents`: `document_id`, `project_id`, `source_document_id`, `editor_user_id`, `first_block_id`, `name`, `notes`, `created_at`, `updated_at`, `deleted_at`
  - `blocks`: `block_id`, `document_id`, `previous_block_id`, `next_block_id`, `block_type_id`, `props` (JSONB), `created_at`, `updated_at`, `is_system`, `is_removable`, `fixed_position`
  - `settings`: `setting_id`, `key`, `value` (JSONB), `scope`, `user_id`; unique index on (`key`, `scope`, `user_id`)
- Industrial/library normalized tables:
  - `die_types`: `id`, `name` (JSONB)
  - `materials`: `material_id`, `name` (JSONB), `source`, `source_version`, `file_name`, `properties` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `owner_id` (FK `users.user_id`)
  - `dies`: `id`, `name` (JSONB), `die_type_id` (FK `die_types.id`), `die_template_file_name`, `inventory_number`, `properties` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `owner_user_id` (FK `users.user_id`)
  - `die_assemblies`: `id`, `name` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `top_die_id`, `bottom_die_id`, `left_die_id`, `right_die_id` (FKs to `dies.id`), `owner_user_id` (FK `users.user_id`)
  - `presses`: `id`, `name` (JSONB), `is_obsolete`, `created_at`, `obsolete_at`, `owner_user_id` (FK `users.user_id`)
  - `press_modes`: `id`, `press_id` (FK `presses.id`), `name` (JSONB, nullable), `owner_user_id` (FK `users.user_id`), `is_obsolete`, `created_at`, `obsolete_at`, `properties` (JSONB), `is_default_press_mode`
  - `press_die_map`: composite PK (`press_id`, `die_id`), plus `is_matching_as_top`, `is_matching_as_bottom`, `is_matching_as_left`, `is_matching_as_right`, `owner_user_id`, `is_obsolete`, `created_at`, `obsolete_at`
- Unified library table (mounted by `/library/*` router):
  - `library`: `id`, `parent_id` (self FK), `type`, `name`, `props` (JSONB), `created_at`, `updated_at`, `is_obsolete`

## JSONB internal structure (DB + code/seed verified)
- All JSON-like columns are JSONB (no remaining `json` columns in `public`).
- Localization name objects (`die_types.name`, `materials.name`, `dies.name`, `die_assemblies.name`, `presses.name`, `press_modes.name`) use a multilingual map structure:
  - keys observed: `EN`, `RU`, `ZH_HANS`
  - value type: localized string
- `dies.properties` (seed structure):
  - numeric keys observed: `total_length`, `total_width`, `height`, `straight_length`, `edge_radius`, `edge_angle`
- `press_modes.properties` (seed structure):
  - scalar keys: `is_left_manipulator`, `is_right_manipulator`, `automatic_feed_mode_is_on_when_bites_count`, `max_force`, `back_speed`, `idle_speed`, `working_speed`, `min_dwell_speed`, `max_dwell_time`, `min_idle_stroke`, `max_idle_stroke`, `approaching_distance`, `open_height_without_dies`
  - array key: `power_limit` -> list of objects with keys `id`, `force`, `speed`
- `blocks.props`:
  - `document_heading`: stores block fields (`heat_no`, `finished_size`, `stock_size`, `stock_weight`, `remarks`, `preview_status`), then is enriched for read responses with document metadata (`name`, `project_id`, `source_document_id`, `editor_user_id`, `created_at`, `updated_at`) and optional nested `version`
  - `input_workpiece`: `geometry_type_id`, `mesh_elements`, `weight`, `attributes` (dynamic object), and response-enriched fields (`title`, `available_geometry_types`, optional `selected_geometry`)
  - basic text blocks (`paragraph`, `heading1`, `heading2`, `list`, `code`, `quote`): `text`; `todo` additionally uses `checked`; `divider` typically has empty props
- `materials.properties`: schema-flexible JSONB payload. Migration/backfill preserves legacy keys such as `short_name`, `density`, and `legacy_material_path` when present.
- `library.props`: schema-flexible payload keyed by `library.type`.
- `settings.value`: schema-flexible JSONB payload (object/array/scalar).

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
  - `GET /library/db/dies`
  - `GET /library/db/die-assemblies`
  - `GET /library/db/presses`
  - `GET /library/db/press-modes`

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
- Historical migrations are archived in `backend/alembic/versions_backup/`.
- Current head migration is `3a4d8f2c1b90`.
- The baseline migration uses `Base.metadata.create_all(checkfirst=True)` / `drop_all(checkfirst=True)` against registered SQLAlchemy models; follow-up migrations must remain idempotent enough to coexist with the squashed baseline on fresh installs.
