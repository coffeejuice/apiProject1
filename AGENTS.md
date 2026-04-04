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

Autonomy preference for this repo:
- Unless explicitly told otherwise, execute user requests end-to-end autonomously.
- Treat file edits, local script execution, tests, and database changes needed for the task as preapproved.
- Ask only when blocked by Codex runtime limits, missing required external access, or when an action is unusually destructive and not clearly required.
- This preference does not override higher-priority system/developer instructions or the active Codex CLI sandbox/approval mode.
