---
apply: always
---

# Development Launcher

## Purpose
`dev.py` is a root-level development-only launcher for a solo developer working on one home-lab PC, often through a remote terminal session.

It starts the normal local development processes together, records child stdout/stderr into local JSONL files, prints only error-level child output to the terminal, and stops all selected child processes on `Ctrl+C`.

It is not a production process manager and must not replace Windows services, NSSM/sc.exe, system services, or deployment scripts.

On Windows, shutdown uses `taskkill /T /F` for each selected root process so child
processes spawned by tools such as Uvicorn reload and npm/Vite do not keep ports
open after the launcher exits.

## Recommended Remote Workflow
Use `tmux` on the home-lab PC so the dev stack survives SSH disconnects:

```bash
cd /home/alextub/Documents/apiProject1
tmux new -s forgelab
python dev.py all
```

Reconnect later:

```bash
tmux attach -t forgelab
```

Stop the dev stack from inside the tmux pane:

```bash
Ctrl+C
```

## Profiles
Default profile:

```bash
python dev.py
```

Equivalent to:

```bash
python dev.py all
```

Available profiles:

```bash
python dev.py all       # frontend + FastAPI + Pre + Post + Solver
python dev.py core      # frontend + FastAPI + Pre
python dev.py frontend  # Vite dev server only
python dev.py api       # FastAPI only
python dev.py pre       # Pre worker only
python dev.py post      # Post worker only
python dev.py solver    # Solver worker only
python dev.py workers   # Pre + Post + Solver
python dev.py api-pre   # FastAPI + Pre
```

Profiles can be combined. Duplicates are removed:

```bash
python dev.py frontend pre
```

## Started Commands
Frontend:

```bash
cd frontend
npm run dev
```

On Windows, `dev.py` resolves the frontend command to the command-shell entry point
(`npm.cmd` when available). This is required because Python `subprocess.Popen`
does not launch the extensionless `npm` shim reliably with `shell=False`.

FastAPI:

```bash
cd backend
.venv/bin/python run.py
```

Pre worker in normal development mode:

```bash
cd backend
FORGELAB_WORKER_NAME=pre-1 .venv/bin/python -m app.workers.pre_dev_reload
```

The Pre launcher uses `app.workers.pre_dev_reload` by default. This runner watches backend Python files and gracefully restarts only the Pre child process after source changes. It sends a normal stop signal, waits for the active Pre job to finish, then starts a fresh child.

Post worker:

```bash
cd backend
FORGELAB_WORKER_NAME=post-1 .venv/bin/python -m app.workers.post_worker
```

Solver worker:

```bash
cd backend
FORGELAB_WORKER_NAME=solver-1 .venv/bin/python -m app.workers.solver_worker
```

## Launcher Log Policy
`dev.py` intentionally keeps the remote terminal quiet:
- child process stdout/stderr is written to JSONL files under `LOGS_FILES_ROOT` or the local fallback `backend/logs`;
- terminal output from child processes is filtered to `ERROR` and `CRITICAL` only;
- launcher lifecycle messages such as `started`, `stopping`, and prerequisite errors are still printed.

Console-output log files created by the launcher use `*-console.jsonl` worker names, for example:
- `frontend/frontend.jsonl`
- `api/api-console.jsonl`
- `pre/pre-1-console.jsonl`
- `post/post-1-console.jsonl`
- `solver/solver-1-console.jsonl`

Backend Python processes still keep their native structured log files too, for example `api/api.jsonl`, `pre/pre-1.jsonl`, `post/post-1.jsonl`, and `solver/solver-1.jsonl`.

## Useful Flags
Check configuration without starting processes:

```bash
python dev.py --check-only all
```

Run Pre without graceful source reload:

```bash
python dev.py pre --no-pre-reload
```

Use a different Pre worker name:

```bash
python dev.py pre --pre-worker-name pre-2
```

Use different Post/Solver worker names:

```bash
python dev.py post --post-worker-name post-2
python dev.py solver --solver-worker-name solver-2
```

Allow already-used frontend/API ports:

```bash
python dev.py all --allow-used-ports
```

Set a force-kill timeout after `Ctrl+C`:

```bash
python dev.py all --shutdown-timeout 30
```

By default shutdown waits indefinitely. This is intentional for Pre because a graceful stop may wait for the active Pre job to finish.

## IDE Debugging
Use the launcher for everything except the process being debugged.

Debug FastAPI in PyCharm:

```bash
python dev.py frontend pre
```

Then start the FastAPI run configuration from PyCharm.

Debug Pre in PyCharm:

```bash
python dev.py frontend api
```

Then start the Pre run configuration from PyCharm.

## Prerequisites Checked By Launcher
For frontend:
- `npm` exists in `PATH`; on Windows the launcher prefers `npm.cmd`.
- `frontend/node_modules` exists.
- port `5173` is free unless `--allow-used-ports` is used.

For backend/API/Pre/Post/Solver:
- `backend/.venv/bin/python` or `backend/.venv/Scripts/python.exe` exists.
- `backend/.env` exists.
- API port `8001` is free unless `--allow-used-ports` is used.

## Networking Note
The active development defaults bind frontend and API to loopback:
- frontend: `127.0.0.1:5173`
- API: `127.0.0.1:8001`

This matches SSH tunnel or remote-desktop workflows. Direct browser access from another machine by LAN IP is a separate frontend/API configuration task because the current frontend development API base URL is loopback-oriented.

## Troubleshooting
If the launcher reports `frontend/node_modules was not found`, run:

```bash
cd frontend
npm install
```

If the launcher reports `backend/.env was not found`, create it from the backend environment template before starting backend processes.

If a port is already in use, either stop the old process or explicitly allow the existing port:

```bash
python dev.py all --allow-used-ports
```

Use `--allow-used-ports` only when you intentionally run that component elsewhere, for example from PyCharm/WebStorm.
