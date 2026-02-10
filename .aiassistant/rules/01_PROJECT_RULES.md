---
apply: always
---

# Project Rules

## Purpose
Techno-Notion is a monorepo for a Notion-like block editor with a FastAPI backend and a React frontend.

## Monorepo layout (top level)
- backend/         FastAPI API server (port 8001)
- frontend/        React + TypeScript web app (Vite, port 5173)
- frontend_obsolete/  Archived Qt/QML client (do not edit unless asked)
- setup/           Setup and database utility scripts
- contracts/       API contracts and shared types (future)

## Global rules
- Backend runs on port 8001 (avoid 8000 on Windows).
- API routes use `/documents`; the DB table is `documents`.
- Keep `frontend_obsolete/` unchanged unless explicitly requested.
- `TODO.md` in the repo root is reserved for user-supplied tasks; ignore it unless the user explicitly asks to use it.

## Core concepts
- Documents: root entities (documents/pages).
- Blocks: polymorphic content components (text, tables, images).
- Revisions: immutable change history with version control.
- Library: industrial assets (materials, dies, presses).
- Users: table `users`.

## Cross-cutting best practices
- Keep schemas and docs aligned with code changes.
- Avoid hard-coded secrets; use `.env` or environment variables.
- If code and docs conflict, fix the docs or call it out clearly.
