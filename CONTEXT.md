# Project Context

This repository is a monorepo for a Notion-like block editor with a FastAPI backend and a React frontend.

## Structure
- backend/          FastAPI API server (port 8001)
- frontend/         React + TypeScript web app (Vite, port 5173)
- frontend_obsolete/  Archived Qt/QML client (do not edit unless asked)

## Rules, guidelines, best practices
Authoritative rules live under `.aiassistant/rules/`:
- 00_INDEX.md (read order)
- 01_PROJECT_RULES.md
- 02_PROJECT_WORKFLOW.md
- 10_BACKEND_RULES.md
- 11_BACKEND_WORKFLOW.md
- 20_FRONTEND_RULES.md
- 21_FRONTEND_WORKFLOW.md

Key rules (short):
- Use port 8001 for the backend; avoid 8000 on Windows.
- API routes use `/documents`; the DB table is `documents`.
- Keep `frontend_obsolete/` unchanged unless explicitly requested.

Best practices:
- Keep schemas, models, and docs in sync.
- Avoid hard-coded secrets; use `.env` or environment variables.
