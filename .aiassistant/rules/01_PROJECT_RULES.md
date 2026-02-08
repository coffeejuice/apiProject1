# Project Rules

## Purpose
Techno-Notion is a monorepo for a Notion-like block editor with a FastAPI backend and a React frontend.

## Monorepo layout (top level)
- backend/         FastAPI API server (port 8001)
- frontend/        React + TypeScript web app (Vite, port 5173)
- frontend_obsolete/  Archived Qt/QML client (do not edit unless asked)
- scripts/         Shared automation
- contracts/       API contracts and shared types (future)

## Global rules
- Backend runs on port 8001 (avoid 8000 on Windows).
- API routes use `/documents`; the DB table is `documents`.
- Keep `frontend_obsolete/` unchanged unless explicitly requested.

## Domain model terminology
- Document: root entity (table `documents`, API `/documents`).
- Block: polymorphic content node with `block_type`, JSON `props`, and `order_key`.
- Revision: immutable change history for a document.
- User: table `users`.
- Library: industrial assets like material, die, and press.

## Cross-cutting best practices
- Keep schemas and docs aligned with code changes.
- Avoid hard-coded secrets; use `.env` or environment variables.
- If code and docs conflict, fix the docs or call it out clearly.
