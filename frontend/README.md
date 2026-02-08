# Techno-Notion Frontend

React + TypeScript web client for the Techno-Notion API. This app provides a Notion-like editor that integrates with the FastAPI backend.

## Features
- Authentication with JWT
- Document list and CRUD
- TipTap editor with common blocks
- Autosave and save status
- Revision history and restore
- Markdown import/export
- Global search
- Configurable API base URL

## Prerequisites
- Node.js 18+
- Backend API running on http://127.0.0.1:8001

## Quick start
cd frontend
npm install
npm run dev

Open http://localhost:5173

## Scripts
- npm run dev
- npm run build
- npm run preview
- npm run lint
- npm run typecheck

## Configuration
### API Base URL
Default: http://127.0.0.1:8001

You can change it in the login settings or set a build-time variable:
VITE_API_BASE_URL=http://127.0.0.1:8001

### Local storage keys
- techno-notion-token
- techno-notion-base-url

## Key concepts
- Zustand stores manage session, documents, and editor state.
- Autosave commits to /documents/{id}/commit when supported.
- If commits are unavailable, editor content falls back to localStorage.
- Document IDs normalize document_id to id.

## Troubleshooting
- Ensure the backend is running and CORS allows http://localhost:5173.
- Verify the API base URL on the login page.
- Check the browser console for request errors.

## Support
See frontend/FRONTEND_CONTEXT.md and .aiassistant/rules for detailed guidance.
