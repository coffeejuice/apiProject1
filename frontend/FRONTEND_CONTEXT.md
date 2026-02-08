# Frontend Context

## Overview
React + TypeScript frontend for a Notion-like block editor. It connects to the FastAPI backend running on port 8001.

## Stack
- React 18 + TypeScript
- Vite (dev server on port 5173)
- Tailwind CSS + typography plugin
- TipTap editor (StarterKit, TaskList, TaskItem)
- Zustand for state management
- React Router

## Project structure
- src/components/   UI components (editor, toolbar, sidebar, search, modals)
- src/pages/        Login and App pages
- src/stores/       Zustand stores
- src/types/        API types

## API integration
- Base URL default: http://127.0.0.1:8001 (configurable in login settings)
- Auth tokens stored in localStorage
  - techno-notion-token
  - techno-notion-base-url
- All HTTP calls should go through the API client (expected at src/lib/apiClient.ts)
- Tolerant parsing for tokens: access_token | token | accessToken
- Normalize documents: map document_id -> id

### Key endpoints
- POST /auth/login
- GET /auth/me
- POST /auth/register
- GET /documents
- POST /documents
- GET /documents/{id}
- PATCH /documents/{id}
- DELETE /documents/{id}
- POST /documents/{id}/commit
- GET /documents/{id}/revisions
- POST /documents/{id}/revisions/{rev}/restore
- GET /documents/{id}/export?format=markdown
- POST /documents/import?format=markdown
- GET /search?q=<query>

## State management (Zustand)
- useSessionStore: token, user, baseUrl, login/logout, initialize
- useDocumentsStore: documents list, currentDoc, CRUD
- useEditorStore: TipTap JSON, dirty flag, save status, revision tracking

## Editor behavior
- Title updates are persisted to backend via PATCH /documents/{id}.
- Editor content is committed via POST /documents/{id}/commit.
- If commit fails or backend does not support it, content falls back to localStorage:
  - doc_<id>_content
- Autosave after idle edits and on a periodic interval.
- Revision history and import/export use backend endpoints.

## Known gaps and assumptions
- Revision history depends on backend commit support.
- Import/export endpoints should be verified against backend router behavior.
