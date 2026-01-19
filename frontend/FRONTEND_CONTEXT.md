# Frontend Context

## Overview

This is a React + TypeScript frontend for a Notion-like block editor application. It communicates with a Python FastAPI backend running on port 8001.

## Tech Stack

- **React 18.3** with TypeScript
- **Vite** - Build tool and dev server (runs on port 5173)
- **Tailwind CSS** - Styling framework with @tailwindcss/typography plugin
- **TipTap** - Rich text editor (ProseMirror-based) with StarterKit, TaskList, TaskItem extensions
- **Zustand** - Lightweight state management
- **React Router** - Client-side routing

## Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── Editor.tsx       # Main TipTap editor component
│   │   ├── EditorToolbar.tsx
│   │   ├── Sidebar.tsx      # Document list and navigation
│   │   ├── SearchBar.tsx
│   │   ├── RevisionHistory.tsx
│   │   └── ImportExport.tsx
│   ├── pages/
│   │   ├── LoginPage.tsx    # Auth page with API URL config
│   │   └── AppPage.tsx      # Main app layout
│   ├── stores/              # Zustand state stores
│   │   ├── useSessionStore.ts    # Auth state
│   │   ├── useDocumentsStore.ts  # Document CRUD
│   │   └── useEditorStore.ts     # Editor content and save state
│   ├── lib/
│   │   └── apiClient.ts     # Centralized HTTP client wrapper
│   ├── types/
│   │   └── api.ts           # TypeScript interfaces
│   ├── App.tsx              # Root component with routing
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles
├── public/                  # Static assets
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

## API Integration

### Backend Connection

- **Base URL**: `http://127.0.0.1:8001` (configurable in login page)
- **Authentication**: JWT bearer tokens stored in localStorage
- **Storage Keys**:
  - `techno-notion-token` - JWT access token
  - `techno-notion-base-url` - API base URL

### API Client (`lib/apiClient.ts`)

Centralized HTTP wrapper with:
- Automatic JSON parsing
- Bearer token injection
- Error normalization
- Methods: get, post, put, patch, delete
- Returns `ApiResponse` with: ok, status, data, errorMessage, errorCode

### Backend API Endpoints

All endpoints use `/documents` prefix (not `/processes` - the database table name differs from API routes):

- `POST /auth/login` - Login (expects `login` and `password` fields)
- `POST /auth/register` - Register new user
- `GET /auth/me` - Get current user info
- `GET /documents` - List user's documents (limit param)
- `POST /documents` - Create new document
- `GET /documents/{id}` - Get document by ID
- `PATCH /documents/{id}` - Update document (title, etc.)
- `DELETE /documents/{id}` - Delete document
- `POST /documents/{id}/commit` - Save operations (DISABLED - see below)
- `GET /documents/{id}/revisions` - Get revision history
- `POST /documents/{id}/revisions/{rev}/restore` - Restore revision
- `GET /documents/{id}/export?format=markdown` - Export document
- `POST /documents/import?format=markdown` - Import document
- `POST /search` - Search documents by title

### Field Normalization

Backend returns `process_id` (integer), frontend normalizes to `id` (string):

```typescript
const normalizedDocs = documents.map((doc) => ({
  ...doc,
  id: doc.id || doc.process_id || '',
}))
```

Applied in: fetchDocuments, createDocument, fetchDocument, updateDocument

## State Management (Zustand)

### useSessionStore

Manages authentication:
- **State**: user, token, isAuthenticated, baseUrl
- **Actions**: login, logout, fetchMe, setBaseUrl, initialize
- Tolerant token extraction: access_token, token, or accessToken

### useDocumentsStore

Manages document list and current document:
- **State**: documents, currentDoc, currentDocId, loading, error
- **Actions**:
  - fetchDocuments - Get all documents
  - createDocument - Create new document
  - fetchDocument - Get document by ID
  - updateDocument - PATCH document (e.g., title)
  - setCurrentDoc - Set active document
  - updateLocalDoc - Update in-memory state only
- All responses normalized (process_id → id)

### useEditorStore

Manages editor content and save state:
- **State**: content, isDirty, saveStatus, error, lastSavedRevNumber
- **Actions**:
  - setContent - Update editor JSON
  - markDirty - Mark as unsaved
  - save - Save to localStorage (backend commits disabled)
  - reset - Clear editor state
- **Save behavior**: LocalStorage only (see Critical Notes)

## Components

### Editor.tsx

Main editor component:
- TipTap editor with StarterKit, TaskList, TaskItem extensions
- Title input with debounced backend update (1s delay)
- Autosave to localStorage (800ms debounce, 10s interval)
- Save status indicator shows "Saved (Local)"
- Loads content from localStorage first, then backend data
- Revision history and import/export modals

### Sidebar.tsx

Document navigation:
- Document list with click handlers
- Create new document button
- SearchBar integration
- Highlights selected document

### SearchBar.tsx

Search functionality:
- 300ms debounced search
- Searches document titles only (not content)
- Maps process_id to documents for display

### RevisionHistory.tsx

Modal for viewing and restoring document revisions:
- Lists all revisions with timestamps
- Restore button calls `/documents/{id}/revisions/{rev}/restore`
- **Note**: May not work properly since commits aren't being saved

### ImportExport.tsx

Tab-based modal for markdown import/export:
- Export: GET `/documents/{id}/export?format=markdown`
- Import: POST `/documents/import?format=markdown`

## Critical Notes

### Backend Commit System (DISABLED)

The backend uses an **operational transform pattern** with specific operation types:
- `insert_block`
- `delete_block`
- `move_block`
- `update_text`
- `update_props`

Frontend does **NOT** implement this pattern. Instead:

1. **Content saves to localStorage only**:
   ```typescript
   localStorage.setItem(`doc_${docId}_content`, JSON.stringify(state.content))
   ```

2. **Title saves to backend via PATCH**:
   ```typescript
   await updateDocument(currentDoc.id, { title: newTitle })
   ```

3. **Implications**:
   - Editor content persists client-side only
   - Title changes persist to database
   - Revision history may be incomplete
   - Multi-device editing not supported

### Known Issues

1. **Content not persisted to backend** - By design (operational transform not implemented)
2. **Revision history incomplete** - Backend commits disabled
3. **Import/Export untested** - May have endpoint issues

### Test User Credentials

- **Username**: testuser
- **Password**: password123
- **Email**: test@example.com

Created with `backend/create_test_user.py`

## Development

### Running Dev Server

```bash
cd frontend
npm install
npm run dev
```

Dev server runs on `http://localhost:5173`

### Building for Production

```bash
npm run build
npm run preview
```

### Type Checking

```bash
npm run typecheck
```

### Linting

```bash
npm run lint
```

## Environment

- **Platform**: Windows
- **Database**: PostgreSQL (installed directly, no Docker)
- **Backend**: Python FastAPI on port 8001
- **Frontend**: Vite dev server on port 5173

## Key Decisions

1. **LocalStorage over Backend Commits**: Practical solution to avoid implementing complex operational transforms
2. **Field Normalization**: Handles backend/frontend schema mismatches gracefully (process_id → id)
3. **Tolerant Parsing**: Makes frontend resilient to backend API changes
4. **No Backend Changes**: All work confined to frontend code only
5. **Debounced Updates**: Title changes debounced to 1s, editor autosave at 800ms

## Future Improvements (Not Implemented)

- Proper operational transform for backend commits
- Conflict resolution UI for simultaneous edits
- Full content persistence to backend
- Loading indicators for API operations
- Error boundary components
- Comprehensive test coverage
