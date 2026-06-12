---
apply: never
---

# Windows New PC Setup Runbook

## Usage Policy
- This is a manual runbook for setting up ForgeLab on a new Windows PC from a GitHub repository checkout.
- Read this file only when the user asks about Windows setup, a new PC, GitHub clone/authentication, local environment provisioning, or migration/bootstrap work.
- Do not treat this file as programming architecture context.
- Source code and current `.env.example` remain authoritative if they conflict with this runbook.

## Scope
This runbook starts from a clean Windows 11 PC and covers:
- GitHub HTTPS clone using token authentication safely.
- Local repository creation.
- Python/backend dependency setup.
- Node/frontend dependency setup.
- PostgreSQL initialization.
- Project `.env` creation.
- Database migration, seeding, admin password recovery, and dev launcher verification.

It does not cover production deployment, Windows services, NSSM/sc.exe, cloud hosting, or solver fleet deployment.

## Secret Rules
- Never commit `backend/.env`.
- Never put a GitHub token into this file, `.env`, `AGENTS.md`, shell history, screenshots, logs, or a Git remote URL.
- Prefer Git Credential Manager or GitHub CLI for GitHub authentication.
- If a setup recovery token is added to `backend/.env`, remove or blank it after the admin password has been reset.

## 1. Install Prerequisites
Install these on Windows:
- Git for Windows, with Git Credential Manager enabled.
- Python 3.12.
- Node.js/npm.
- PostgreSQL, matching the local major version you want to standardize on.
- Optional: GitHub CLI (`gh`) for easier repository login/clone.
- Optional: PyCharm and Codex.

Verify in a new PowerShell:

```powershell
git --version
git credential-manager version
py -3.12 --version
node --version
npm --version
psql --version
```

If `psql` is not found, add the PostgreSQL `bin` directory to `Path`, not the `psql.exe` file itself:

```powershell
C:\Program Files\PostgreSQL\18\bin
```

Open a new PowerShell after changing `Path`.

## 2. Create A GitHub Token
Use a GitHub fine-grained personal access token when HTTPS token auth is required.

Recommended minimum repository permissions:
- Clone only: selected repository, `Contents: Read-only`.
- Clone and push: selected repository, `Contents: Read and write`.
- GitHub may also require `Metadata: Read-only`.

Use an expiration date. Copy the token once and store it in a password manager. Do not paste it into commands that will be saved in history.

## 3. Clone The Repository
Recommended project location:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projects" | Out-Null
Set-Location "$env:USERPROFILE\Projects"
```

Clone with HTTPS and Git Credential Manager:

```powershell
git clone https://github.com/coffeejuice/apiProject1.git
Set-Location .\apiProject1
```

When prompted:
- Username: your GitHub username.
- Password: paste the GitHub personal access token.

Git Credential Manager should store the credential in Windows Credential Manager so future `git fetch`, `git pull`, and `git push` do not require retyping the token.

If using GitHub CLI instead:

```powershell
gh auth login --hostname github.com --git-protocol https
gh repo clone coffeejuice/apiProject1 "$env:USERPROFILE\Projects\apiProject1"
Set-Location "$env:USERPROFILE\Projects\apiProject1"
```

If the remote is SSH but HTTPS token auth is desired:

```powershell
git remote set-url origin https://github.com/coffeejuice/apiProject1.git
git remote -v
```

Do not clone with a token embedded in the URL, such as `https://TOKEN@github.com/...`.

## 4. Create Backend Virtual Environment
Run from the repository root:

```powershell
py -3.12 -m venv .\backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
```

Quick backend import/syntax check:

```powershell
.\backend\.venv\Scripts\python.exe -m compileall .\backend\app
```

## 5. Install Frontend Dependencies
Run from the repository root:

```powershell
npm.cmd --prefix .\frontend install
npm.cmd --prefix .\frontend run typecheck
```

Use `npm.cmd` in automation on Windows. The `dev.py` launcher resolves this automatically.

## 6. Create Backend Environment File
Create `backend/.env` from the template:

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

Generate secrets:

```powershell
.\backend\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Edit `backend/.env`:

```text
DB_ADMIN_URL=postgresql+psycopg://postgres:<postgres_password>@127.0.0.1:5432/postgres
DATABASE_URL=postgresql+psycopg://notion_sys_user:<app_db_password>@127.0.0.1:5432/notion_db
SECRET_KEY=<generated_secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
SETUP_ADMIN_RESET_TOKEN=<optional_generated_token_for_first_local_reset_only>
LIBRARY_FILES_ROOT=C:\Users\<you>\Projects\apiProject1\backend\data
NAS_MOUNT_ROOT=C:\Users\<you>\Projects\apiProject1\backend\data
LOGS_FILES_ROOT=C:\Users\<you>\Projects\apiProject1\backend\logs
TEMP_FILES_ROOT=C:\Users\<you>\Projects\apiProject1\backend\tmp
```

Use unique passwords. Do not reuse GitHub tokens, Windows passwords, or old project passwords.

## 7. Configure PostgreSQL
Install PostgreSQL and remember the `postgres` superuser password.

Confirm the service is running:

```powershell
Get-Service *postgres*
```

Confirm `psql` works:

```powershell
psql -h 127.0.0.1 -U postgres -d postgres
```

If `psql` prompts for a password and reaches the `postgres=#` prompt, type:

```sql
\q
```

If the password is unknown, reset it in pgAdmin or through PostgreSQL's Windows authentication recovery flow before running project database setup.

## 8. Initialize Project Database
Run from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\setup_database.py
```

Expected result:
- PostgreSQL admin connection works.
- Role `notion_sys_user` exists.
- Database `notion_db` exists.
- App user can connect.
- Privileges are ensured.

Run migrations from `backend/`:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
Pop-Location
```

`alembic check` should end with:

```text
No new upgrade operations detected.
```

## 9. Verify Dev Launcher Configuration
Run from the repository root:

```powershell
py dev.py --check-only core
```

Expected selected processes:
- `front`: Vite on `127.0.0.1:5173`.
- `api`: FastAPI on `127.0.0.1:8001`.
- `pre`: Pre worker.

Start the core stack:

```powershell
py dev.py core
```

Verify in another PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-WebRequest http://127.0.0.1:5173/ -UseBasicParsing
```

Stop with `Ctrl+C` in the terminal running `dev.py`.

## 10. Seed Library And Set Admin Password
Open:

```text
http://127.0.0.1:5173/setup
```

If the database has no users yet, the setup page can run library seeding without login.

If admin password is unknown or the seed default is not usable:
1. Set `SETUP_ADMIN_RESET_TOKEN` in `backend/.env` to a generated token.
2. Restart `py dev.py core`.
3. Open `/setup`.
4. Paste the setup reset token into the token field.
5. Set a new admin password for login `admin`.
6. Blank or remove `SETUP_ADMIN_RESET_TOKEN` from `backend/.env`.
7. Restart `py dev.py core`.

Then login at:

```text
http://127.0.0.1:5173/login
```

## 11. Common Windows Problems
### `psql` Is Not Recognized
`Path` must contain the PostgreSQL `bin` directory:

```text
C:\Program Files\PostgreSQL\18\bin
```

Do not add:

```text
C:\Program Files\PostgreSQL\18\bin\psql.exe
```

### npm Cannot Find `frontend/package.json`
Run commands from the repository root:

```powershell
Set-Location C:\Users\<you>\Projects\apiProject1
npm.cmd --prefix .\frontend install
```

### Ports 5173 Or 8001 Are Already In Use
Check listeners:

```powershell
Get-NetTCPConnection -LocalPort 5173,8001 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,State,OwningProcess
```

If a previous `dev.py` stack is still running, stop it with `Ctrl+C` in that terminal. If it is orphaned, inspect and stop the owning process carefully:

```powershell
Get-Process -Id <pid>
Stop-Process -Id <pid>
```

### `python` Resolves To MSYS Or The Wrong Python
Use the Python launcher explicitly:

```powershell
py -3.12 --version
py dev.py core
```

The backend app itself should run through `backend\.venv\Scripts\python.exe`, which `dev.py` selects automatically.

## 12. Optional Codex And MCP Setup
For Codex/MCP setup, read:

```text
.codex/context/MCP_SERVERS_SETUP.md
```

GitHub MCP uses `GITHUB_PERSONAL_ACCESS_TOKEN`, but that is separate from Git clone credentials. Keep MCP tokens out of project files and set them only in the shell or user environment that launches Codex.

## 13. Minimum Final Verification Checklist
Run:

```powershell
git status --short
.\backend\.venv\Scripts\python.exe -m compileall .\backend\app
npm.cmd --prefix .\frontend run typecheck
Push-Location .\backend
.\.venv\Scripts\python.exe -m alembic check
Pop-Location
py dev.py --check-only core
py dev.py core
```

Then verify:
- `http://127.0.0.1:8001/health` returns healthy.
- `http://127.0.0.1:5173/` loads the frontend.
- `/setup/status` returns `200`.
- Admin login works after seeding/reset.

## References
- GitHub credential caching: https://docs.github.com/en/get-started/git-basics/caching-your-github-credentials-in-git
- GitHub personal access tokens: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- GitHub authentication overview: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github
