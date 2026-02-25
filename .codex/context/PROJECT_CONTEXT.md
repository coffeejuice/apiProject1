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
- `frontend/`: React 18 + TypeScript SPA (Vite), Zustand state, block UI
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
- Stack: React, TypeScript, Vite, Tailwind
- Routing: `react-router-dom`
- State: Zustand stores, primarily `useDocumentsStore` for project/document flow
- API access rule: use `frontend/src/lib/apiClient.ts` (avoid direct `fetch` in components)
- Token and base URL persistence keys:
  - `forgelab-token`
  - `forgelab-base-url`
- Main app screen (`frontend/src/pages/AppPage.tsx`) uses a split-pane layout:
  - `MenuBar` at top (full width, always visible)
  - below it: `ToolsSwitcher` (left, always visible), `ToolsPane` (middle, collapsible), right editor stack
  - right editor stack: `VisualEditor` (top, collapsible) + `BlockEditor` (bottom, always visible)
- `ToolsSwitcher` controls `ToolsPane` view visibility; if no tool is active, `ToolsPane` is hidden.
- `ToolsPane` provides views:
  - `Projects`: project list, filter, create modal
  - `Documents`: project-scoped document list, filter, new/copy modals
  - `BlocksLibrary`: block icon palette for drag-and-drop or insert into `BlockEditor`
  - `Users`: active user/session info
- `VisualEditor` provides horizontal block-order visualization with:
  - when hidden/collapsed, it is fully removed from layout (no header/placeholder)
  - visibility is controlled from `MenuBar` (`Show VisualEditor` / `Hide VisualEditor`)
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
  - `text-xs` = 10px/14px
  - `text-sm` = 11px/15px
  - `text-base` = 12px/16px
  - `text-lg` = 14px/18px
- Rule for future UI edits:
  - prefer shared `ui-*` classes and the 4-size text palette; avoid introducing ad-hoc spacing/button/input styles unless the standard itself is intentionally updated.

## Domain model summary
- Core entities:
  - Users (`users`)
  - Projects (`projects`)
  - Documents (`documents`)
  - Blocks (`blocks`)
  - Settings (`settings`)
  - Unified library (`library`)
- Project model:
  - `project_id`, `user_id`, optional `material_id` (FK to `library.id`), `name`, `notes`, timestamps, soft delete
- Library model:
  - `id`, nullable `parent_id` self-reference, enum `type`, `name`, JSON `props`, timestamps, `is_obsolete`
  - `type` enum values: `die`, `die_assembly`, `press`, `press_mode`, `time_between_operations`, `material`, `operation_type`
- Document model:
  - `document_id`, required `project_id`, optional `source_document_id`, optional `editor_user_id`, `first_block_id`, `name`, `notes`, timestamps, soft delete
  - supports inheritance/lineage through `source_document_id`
- Block model:
  - linked-list ordering with `previous_block_id` and `next_block_id`
  - block type is stored as `block_type_id`
  - metadata flags: `is_system`, `is_removable`, `fixed_position`
- Additional industrial/library entities still exist as legacy model definitions (`material`, `operations_library`, `press`, `die`, etc.).
- Active API/library flows are routed through the unified `library` table and `/library/*` endpoints.
- Legacy ACL/share/version tables remain in models but are not primary mounted API flow.

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
- Repo currently keeps a consolidated active migration pattern in `backend/alembic/versions/`.
- Historical migrations are stored in `backend/alembic/versions_backup/`.
- Current head migration is `9b9c2f4e7c31`.
- `dd3aff7dab58_initial_complete_schema.py` creates a curated active table subset (not every legacy model table).
