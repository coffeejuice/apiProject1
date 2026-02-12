---
apply: never
---

# MCP Servers Setup Runbook (Manual Use Only)

## Usage policy
- This file is a manual runbook.
- Do not auto-ingest this file in normal Codex sessions.
- Use this file only on direct user request to set up, repair, or verify MCP servers.

## Scope
- Workspace path:
  - `/home/alextub/Documents/apiProject1`
- Global Codex config path:
  - `~/.codex/config.toml`
- Servers covered:
  - `filesystem`
  - `terminal` (custom Python MCP server)
  - `postgres`
  - `playwright`
  - `github`
  - `fastapi_bridge` (custom Python MCP server)
  - `context7`
- Not included in this runbook:
  - `figma` (intentionally excluded for this setup)

## Current architecture context (important for validation)
This project now follows:
- `Project -> Document -> Block` hierarchy
- Project-scoped document listing: `/projects/{project_id}/documents`
- Linked-list block editing:
  - `/documents/{document_id}/blocks/root`
  - `/documents/{document_id}/commit`

When validating MCP tooling (especially `fastapi_bridge`), prefer these endpoints and do not expect old document-first/revision routes to exist in `main.py`.

## Prerequisites
1. Codex CLI is installed and authenticated.
2. `node`, `npm`, `npx` are available in `PATH`.
3. Repo exists at `/home/alextub/Documents/apiProject1`.
4. Python venv exists:
   - `/home/alextub/Documents/apiProject1/backend/.venv`
5. Backend env file exists:
   - `/home/alextub/Documents/apiProject1/backend/.env`
6. GitHub token available in shell:
   - `GITHUB_PERSONAL_ACCESS_TOKEN`

## Required environment variables
1. `GITHUB_PERSONAL_ACCESS_TOKEN`
   - Used by GitHub MCP via bearer token auth.
   - Example (current shell only):
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN="github_pat_..."
   ```
2. DB URL in `backend/.env` (any one of):
   - `POSTGRES_CONNECTION_STRING`
   - `DATABASE_URL`
   - `DB_ADMIN_URL`
   - `postgres` MCP wrapper resolves in that order.

## Step 1: Validate local custom MCP scripts

### 1.1 Required scripts
- `/home/alextub/Documents/apiProject1/backend/scripts/terminal_mcp.py`
- `/home/alextub/Documents/apiProject1/backend/scripts/fastapi_bridge_mcp.py`

### 1.2 Compile check
```bash
/home/alextub/Documents/apiProject1/backend/.venv/bin/python -m py_compile \
  /home/alextub/Documents/apiProject1/backend/scripts/terminal_mcp.py \
  /home/alextub/Documents/apiProject1/backend/scripts/fastapi_bridge_mcp.py
```

## Step 2: Remove old MCP entries (clean reinstall)
```bash
codex mcp remove filesystem || true
codex mcp remove terminal || true
codex mcp remove postgres || true
codex mcp remove playwright || true
codex mcp remove github || true
codex mcp remove fastapi_bridge || true
codex mcp remove context7 || true
```

## Step 3: Add MCP servers

### 3.1 Filesystem
```bash
codex mcp add filesystem -- \
  npx -y @modelcontextprotocol/server-filesystem \
  /home/alextub/Documents/apiProject1 /tmp
```

### 3.2 Terminal (custom local script)
```bash
codex mcp add terminal -- \
  bash -lc 'exec /home/alextub/Documents/apiProject1/backend/.venv/bin/python /home/alextub/Documents/apiProject1/backend/scripts/terminal_mcp.py'
```

### 3.3 Postgres (read DB URL from `backend/.env`)
```bash
codex mcp add postgres -- \
  bash -lc 'set -euo pipefail; set -a; source /home/alextub/Documents/apiProject1/backend/.env; set +a; db="${POSTGRES_CONNECTION_STRING:-${DATABASE_URL:-${DB_ADMIN_URL:-}}}"; if [ -z "$db" ]; then echo "No DB URL found in backend/.env" >&2; exit 1; fi; db="${db/postgresql+psycopg:/postgresql:}"; db="${db/postgresql+asyncpg:/postgresql:}"; exec npx -y @modelcontextprotocol/server-postgres "$db"'
```

### 3.4 Playwright
```bash
codex mcp add playwright -- npx -y @playwright/mcp@latest
```

### 3.5 GitHub (HTTP MCP endpoint)
```bash
codex mcp add github \
  --url https://api.githubcopilot.com/mcp/ \
  --bearer-token-env-var GITHUB_PERSONAL_ACCESS_TOKEN
```

### 3.6 FastAPI bridge (custom local script)
```bash
codex mcp add fastapi_bridge -- \
  bash -lc 'exec /home/alextub/Documents/apiProject1/backend/.venv/bin/python /home/alextub/Documents/apiProject1/backend/scripts/fastapi_bridge_mcp.py --openapi-url http://127.0.0.1:8001/openapi.json --base-url http://127.0.0.1:8001'
```

### 3.7 Context7
```bash
codex mcp add context7 -- npx -y @upstash/context7-mcp
```

## Step 4: Confirm configuration
```bash
codex mcp list
codex mcp get filesystem
codex mcp get terminal
codex mcp get postgres
codex mcp get playwright
codex mcp get github
codex mcp get fastapi_bridge
codex mcp get context7
```

## Step 5: Runtime health checks

### 5.1 Start backend (required for `fastapi_bridge`)
```bash
cd /home/alextub/Documents/apiProject1/backend
.venv/bin/python run.py
```

### 5.2 Generic MCP smoke checks
1. Filesystem:
```bash
codex exec "Call filesystem MCP and list allowed directories."
```
2. Terminal:
```bash
codex exec "Call terminal.run_command with cmd='echo terminal_mcp_ok'."
```
3. Postgres:
```bash
codex exec "Use postgres MCP and run: select 1 as ok"
```
4. GitHub:
```bash
codex exec "Use github MCP and call get_me."
```
5. Playwright:
```bash
codex exec "Use playwright MCP and list browser tabs."
```
6. FastAPI bridge:
```bash
codex exec "Use fastapi_bridge MCP and call list_endpoints, then call_endpoint GET /health."
```
7. Context7:
```bash
codex exec "Use context7 MCP and resolve library id for react."
```

### 5.3 Architecture-aware FastAPI bridge checks
Verify that endpoint inventory reflects current project flow:
```bash
codex exec "Use fastapi_bridge MCP and call list_endpoints. Confirm routes include /projects, /projects/{project_id}/documents, /documents, /documents/{document_id}/blocks/root, /documents/{document_id}/commit."
```

Expected current route groups from `backend/app/main.py`:
- `auth`
- `projects`
- `document`
- `blocks`
- `search` + `document_search_router`
- `settings`

If `/projects` or `/documents/{document_id}/commit` are missing, treat as backend/bridge mismatch.

## Step 6: Quick failure diagnosis map

### GitHub MCP fails
- Cause:
  - `GITHUB_PERSONAL_ACCESS_TOKEN` not set in the shell that launched Codex.
- Check:
```bash
echo "${GITHUB_PERSONAL_ACCESS_TOKEN:+set}"
```

### Postgres MCP fails
- Causes:
  - No DB URL in `backend/.env`
  - Invalid DB credentials/host
  - DB server not running
- Check:
```bash
rg -n "^(POSTGRES_CONNECTION_STRING|DATABASE_URL|DB_ADMIN_URL)=" /home/alextub/Documents/apiProject1/backend/.env
```

### FastAPI bridge starts but endpoint calls fail
- Common cause:
  - Backend is down or not reachable at `127.0.0.1:8001`.
- Check:
```bash
curl -s -o /tmp/openapi_check.json -w "HTTP %{http_code}\n" http://127.0.0.1:8001/openapi.json
```

### Playwright MCP first-run errors
- Cause:
  - Browser binaries not installed.
- Fix:
```bash
npx playwright install
```

## Optional reset
```bash
codex mcp remove filesystem
codex mcp remove terminal
codex mcp remove postgres
codex mcp remove playwright
codex mcp remove github
codex mcp remove fastapi_bridge
codex mcp remove context7
```

Re-run Step 3 onward.

## Minimal known-good command snapshot
- `filesystem`:
  - `npx -y @modelcontextprotocol/server-filesystem /home/alextub/Documents/apiProject1 /tmp`
- `terminal`:
  - `bash -lc exec /home/alextub/Documents/apiProject1/backend/.venv/bin/python /home/alextub/Documents/apiProject1/backend/scripts/terminal_mcp.py`
- `postgres`:
  - `bash -lc` wrapper sourcing `backend/.env` and running `@modelcontextprotocol/server-postgres`
- `playwright`:
  - `npx -y @playwright/mcp@latest`
- `github`:
  - `https://api.githubcopilot.com/mcp/` + bearer env var `GITHUB_PERSONAL_ACCESS_TOKEN`
- `fastapi_bridge`:
  - `bash -lc exec /home/alextub/Documents/apiProject1/backend/.venv/bin/python /home/alextub/Documents/apiProject1/backend/scripts/fastapi_bridge_mcp.py --openapi-url http://127.0.0.1:8001/openapi.json --base-url http://127.0.0.1:8001`
- `context7`:
  - `npx -y @upstash/context7-mcp`
