# Frontend Rules

## Stack
- React 18 + TypeScript
- Vite (SPA) on port 5173
- Tailwind CSS + typography plugin
- TipTap editor (StarterKit, TaskList, TaskItem)
- Zustand for state management
- React Router for routing

## Structure
- frontend/src/components/   UI components
- frontend/src/pages/        Route pages
- frontend/src/stores/       Zustand stores
- frontend/src/types/        API types

## State and API rules
- All HTTP requests go through the API client (expected at src/lib/apiClient.ts).
- Avoid direct fetch calls in components.
- Store token and base URL in localStorage:
  - techno-notion-token
  - techno-notion-base-url
- Tolerant parsing for tokens: access_token | token | accessToken.
- Normalize documents: map document_id -> id.

## Editor and persistence
- Title updates are persisted to the backend via PATCH /documents/{id}.
- Editor content is committed via /documents/{id}/commit when supported.
- If commit fails or backend does not support it, fall back to localStorage:
  - key: doc_<id>_content
- Autosave after idle edits and on a timed interval; show save status.

## API endpoints used
- POST /auth/login, GET /auth/me, POST /auth/register
- GET/POST/PATCH/DELETE /documents
- GET /documents/{id}/revisions
- POST /documents/{id}/revisions/{rev}/restore
- GET /documents/{id}/export?format=markdown
- POST /documents/import?format=markdown
- GET /search?q=<query>
