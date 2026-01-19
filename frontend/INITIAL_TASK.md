Build a web frontend from scratch for a SaaS “block note editor” (Notion-like) that will talk to an existing Python FastAPI backend via REST. You must implement the full frontend repo (files, folders, configs) with clean architecture, minimal bugs, and runnable locally.

TECH STACK (must use)
- React + TypeScript
- Vite (SPA) (NOT Next.js)
- Tailwind CSS + @tailwindcss/typography (prose)
- TipTap editor (ProseMirror-based)
- State: Zustand
- HTTP: fetch wrapper (no axios required)
- Tooling: ESLint + Prettier; scripts for dev/build/typecheck/lint
- No backend code changes.

REPO STRUCTURE (monorepo)
- Frontend must live in: repo/frontend/
- Do not touch repo/backend/
- Create/modify only under repo/frontend/ (and optionally repo/contracts/ for types, but frontend must not require it)

FRONTEND REQUIREMENTS (MVP but complete)
1) Auth + Session
- Pages: /login and /app
- Login form: username/email + password.
- Store bearer token in local storage.
- After login, fetch /auth/me and keep session state.
- Include a settings screen (modal or page) where user can set base API URL (default http://127.0.0.1:8000).

2) Document List
- Page: /app shows documents list + create document + open document.
- API endpoints assumed (bearer required):
    - POST /auth/login  { email_or_username, password } -> { access_token } (field name may vary; handle common variants)
    - GET /auth/me
    - GET /documents?limit=&cursor=
    - POST /documents { title }
    - GET /documents/{doc_id}
- UI: left sidebar list of documents; main area shows editor when a document is opened.

3) Block Editor (TipTap)
- Use TipTap with StarterKit.
- Must support basic blocks: paragraph, headings, bullet list, ordered list, task list, code block, blockquote.
- Toolbar buttons for these commands.
- Display read-only rendering for preview areas using Tailwind `prose` classes.
- Document title editable (simple input).

4) Autosave + Commit model
- Maintain a local “pending changes” flag.
- Autosave triggers:
    - after 800ms idle after edits
    - and at least every 10s if continuously editing
- Save by calling:
    - POST /documents/{doc_id}/commit
      body: { device_id, base_rev_number, client_batch_id, ops: [...] }
- For this MVP, do NOT implement full operational transform. Instead:
    - Treat “ops” as a single operation representing full document content state:
        - op_type: "set_document_content"
        - payload contains: { content_json: <tiptap JSON> }
    - Send one op per autosave batch.
- Keep track of:
    - device_id (generate and persist UUID in local storage)
    - base_rev_number (from document meta; if not available, default 0 and update from server response)
- Show save status: Saved / Saving / Error.
- If server returns conflict (HTTP 409 or error_code=CONFLICT), show a modal:
    - options: “Reload server version” (discard local) or “Force overwrite” (send again with updated base_rev_number)
    - Implement “Force overwrite” as: refetch document meta to get current head, then commit again with that base.

5) Revision history (basic UI)
- Button “History”
- Fetch and show list of revisions:
    - GET /documents/{doc_id}/revisions
- Allow user to restore:
    - POST /documents/{doc_id}/revisions/{rev}/restore
- After restore, refetch and update editor content.

6) Import/Export Markdown (basic)
- Export: GET /documents/{doc_id}/export?format=markdown -> download file
- Import: POST /documents/import?format=markdown { title, content_markdown }
- Provide simple UI buttons for import/export.

7) Search (basic)
- Search bar in /app:
    - GET /search?q=... (global) OR GET /documents/{doc_id}/search?q=...
- Display results list (doc title + snippet). Clicking result opens the doc.

API CLIENT REQUIREMENTS
- Implement ApiClient with:
    - baseUrl
    - token
    - request(method, path, {params, body})
    - automatic JSON parsing
    - error normalization: return { ok, status, data, errorMessage, errorCode }
- All API calls must go through ApiClient.
- No direct fetch calls in React components.

STATE & ARCHITECTURE RULES
- Keep global state in Zustand stores:
    - useSessionStore: token, user, baseUrl, login/logout
    - useDocumentsStore: list, currentDocId, currentDocMeta
    - useEditorStore: tiptap JSON content, dirty flag, save status, lastSavedRevNumber
- React components should be mostly dumb; business logic in stores/services.

UI REQUIREMENTS
- Clean, simple layout: 2 panes
    - Left: docs list + search + create doc button
    - Right: editor with toolbar, title, status bar
- Use Tailwind for layout and styling. No heavy UI frameworks required.
- Use `prose` for read-only render blocks/snippets.

QUALITY / DELIVERABLES
- Must run with:
    - cd frontend
    - npm install
    - npm run dev
- Provide scripts: dev, build, preview, lint, typecheck.
- Provide README with setup instructions and configuration (API URL, login, etc.)
- Ensure TypeScript types exist for all API DTOs you use.
- Handle loading states and errors.

ASSUMPTIONS / FALLBACKS
- If exact response fields differ, implement tolerant parsing:
    - token field: access_token | token | accessToken
    - docs list field: items | documents | data
- For document content:
    - If backend does not support set_document_content op yet, keep client-side content persistence in local storage as fallback and show a warning. Still implement the commit call.

IMPLEMENTATION STEPS (agent should follow)
1) Scaffold Vite React TS app in frontend/
2) Add Tailwind + typography plugin
3) Add routing (react-router)
4) Implement ApiClient and stores
5) Implement Login page
6) Implement App layout + documents list
7) Implement TipTap editor + toolbar + autosave commit
8) Implement History modal + restore
9) Implement Import/Export + Search
10) Polish error handling, README, scripts

Do not ask questions; make reasonable defaults and implement end-to-end runnable frontend.
