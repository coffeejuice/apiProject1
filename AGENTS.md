# Codex Context Entry

This repository uses Codex-specific context files in `.codex/context/`.

Read order for every session:
1. `.codex/context/PROJECT_CONTEXT.md`
2. `.codex/context/DOCUMENT_BLOCK_ARCHITECTURE.md`

Scope:
- Backend rules apply to `backend/`.
- Frontend rules apply to `frontend/`.
- `frontend_obsolete/` is archived; do not edit unless explicitly requested.

Important:
- Environment provisioning instructions are intentionally excluded from Codex context.
- Specifically, do not ingest `.aiassistant/rules/02_PROJECT_SETUP.md` as programming context.
- If source code conflicts with context docs, treat source code as authoritative and update context docs.
