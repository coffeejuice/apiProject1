# Codex Context Entry

This repository uses Codex-specific context files in `.codex/context/`.

Always-on read order for every session:
1. `.codex/context/PROJECT_CONTEXT.md`
2. `.codex/context/DOCUMENT_BLOCK_ARCHITECTURE.md`
3. `.codex/context/DB_SCHEMA.md`

Task-specific context files:
- Read `.codex/context/DEV_LAUNCHER.md` when starting, debugging, or changing `dev.py`, local dev processes, worker startup, or local runtime logs.
- Read `.codex/context/TODO_BACKEND_PREPROCESSOR_REWORK.md` for Pre/Solver/Post, Steps, workflow runtime, `document_operations`, `simulation_steps`, or worker pipeline work.
- Read `.codex/context/PRE_OUTPUT_INVENTORY.md` with the Pre rework TODO when preserving or comparing old Pre-generated output.
- Read `.codex/context/OLD_BACKEND_MIGRATION_MAP.md` only when porting, auditing, or comparing legacy code from `backend_old/`.
- Read `.codex/context/WINDOWS_NEW_PC_SETUP.md` only on direct user request to set up or document a new Windows PC, GitHub clone/authentication, local environment provisioning, or bootstrap/migration steps.
- Read `.codex/context/MCP_SERVERS_SETUP.md` only on direct user request to set up, repair, or verify MCP servers. Do not auto-ingest it in normal sessions.

Scope:
- Backend rules apply to `backend/`.
- Frontend rules apply to `frontend/`.
- `backend_old/` is legacy reference material; do not edit unless a task explicitly targets legacy migration or source comparison.

Important:
- Environment provisioning instructions are intentionally excluded from Codex context.
- Specifically, do not ingest `.aiassistant/rules/02_PROJECT_SETUP.md` as programming context.
- If source code conflicts with context docs, treat source code as authoritative and update context docs.

Autonomy preference for this repo:
- Unless explicitly told otherwise, execute user requests end-to-end autonomously.
- Treat file edits, local script execution, tests, and database changes needed for the task as preapproved.
- Ask only when blocked by Codex runtime limits, missing required external access, or when an action is unusually destructive and not clearly required.
- This preference does not override higher-priority system/developer instructions or the active Codex CLI sandbox/approval mode.
