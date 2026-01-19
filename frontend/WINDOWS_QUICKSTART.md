# Windows Quick Start Guide

## Prerequisites

✅ PostgreSQL installed directly on Windows (you have this)
✅ Python 3.10+ with backend virtual environment (you have this)
⚠️ **Node.js 18+** - Download from https://nodejs.org/ and install

## Step-by-Step Setup

### 1. Install Node.js (if not already installed)

1. Download from: https://nodejs.org/
2. Run the installer (.msi file)
3. Accept all defaults (includes npm and PATH setup)
4. **Restart your terminal** after installation

Verify installation:
```powershell
node --version
npm --version
```

### 2. Start PostgreSQL

If PostgreSQL service isn't running:

**Option A: Services GUI**
- Press `Win + R`, type `services.msc`
- Find "postgresql-x64-xx" service
- Right-click → Start

**Option B: PowerShell (Run as Administrator)**
```powershell
net start postgresql-x64-14
```
*(Adjust version number to match your installation)*

### 3. Start Backend API

Open PowerShell or Git Bash:

```powershell
cd C:\Users\alext\PycharmProjects\apiProject1\backend
.venv\Scripts\activate
python run.py
```

Backend should start on: `http://127.0.0.1:8001`

Keep this terminal open.

### 4. Install Frontend Dependencies

Open a **NEW** PowerShell or Git Bash terminal:

```powershell
cd C:\Users\alext\PycharmProjects\apiProject1\frontend
npm install
```

This will take 2-3 minutes to download all packages.

### 5. Start Frontend Dev Server

```powershell
npm run dev
```

Frontend will start on: `http://localhost:5173`

## 🎯 Testing the Application

### First Login

1. Open browser: http://localhost:5173
2. You'll be redirected to the login page
3. Default API URL is already set to: `http://127.0.0.1:8001`
4. Login with your existing backend credentials

If you need to create a test user in the backend:

```powershell
# In backend directory
.venv\Scripts\activate
python
```

```python
from app.database import SessionLocal
from app.models.user import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

# Create test user
user = User(
    login="testuser",
    email="test@example.com",
    hashed_password=pwd_context.hash("password123")
)
db.add(user)
db.commit()
print(f"Created user: {user.login}")
```

Then login with:
- Username: `testuser`
- Password: `password123`

### Feature Checklist

- [ ] Login successfully
- [ ] Create a new document
- [ ] Edit with various formatting (bold, lists, headings)
- [ ] Watch autosave indicator (should say "Saved" after 800ms)
- [ ] Create another document
- [ ] Use search bar to find documents
- [ ] Click "History" to view revisions
- [ ] Test "Import/Export" → Export as Markdown
- [ ] Logout and login again

## 🔧 Common Windows Issues

### Port 8001 Already in Use

If backend won't start:

```powershell
# Find process using port 8001
netstat -ano | findstr :8001

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### Port 5173 Already in Use

If frontend won't start:

```powershell
# Find process using port 5173
netstat -ano | findstr :5173

# Kill the process
taskkill /PID <PID> /F
```

### npm install Fails

If you get permission errors:

```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try `npm install` again.

### Git Bash vs PowerShell

Both work! Use whichever you prefer:

**Git Bash:**
```bash
cd /c/Users/alext/PycharmProjects/apiProject1/frontend
npm run dev
```

**PowerShell:**
```powershell
cd C:\Users\alext\PycharmProjects\apiProject1\frontend
npm run dev
```

## 📁 Directory Structure Reminder

```
C:\Users\alext\PycharmProjects\apiProject1\
├── backend\              # Python FastAPI (port 8001)
│   ├── .venv\           # Python virtual environment
│   ├── app\             # Backend code
│   └── run.py           # Start backend
│
└── frontend\            # React TypeScript (port 5173)
    ├── node_modules\    # Installed packages (after npm install)
    ├── src\             # Frontend code
    └── package.json     # Dependencies
```

## 🚀 Daily Development Workflow

### Morning Startup

1. **Start PostgreSQL** (if not auto-started)
   ```powershell
   # Check if running
   Get-Service postgresql*
   ```

2. **Terminal 1 - Backend**
   ```powershell
   cd C:\Users\alext\PycharmProjects\apiProject1\backend
   .venv\Scripts\activate
   python run.py
   ```

3. **Terminal 2 - Frontend**
   ```powershell
   cd C:\Users\alext\PycharmProjects\apiProject1\frontend
   npm run dev
   ```

4. Open browser: http://localhost:5173

### Evening Shutdown

Just close the terminals (Ctrl+C stops the servers).

PostgreSQL can keep running or stop it via Services.

## 🔍 Debugging on Windows

### Check What's Running

```powershell
# Check if backend is responding
curl http://127.0.0.1:8001/docs

# Check if frontend is running
curl http://localhost:5173
```

### View Logs

**Backend logs**: In the terminal where you ran `python run.py`

**Frontend logs**:
- Browser console (F12 → Console tab)
- Terminal where you ran `npm run dev`

### Database Connection Issues

Check PostgreSQL connection in backend `.env` file:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/yourdbname
```

Test connection:
```powershell
cd backend
.venv\Scripts\activate
python -c "from app.database import engine; print(engine.connect())"
```

## 📦 Production Build (Optional)

When ready to deploy:

```powershell
cd C:\Users\alext\PycharmProjects\apiProject1\frontend
npm run build
```

Creates optimized files in `dist\` folder.

Serve with any static server:
```powershell
npm run preview
```

## ✅ You're All Set!

Once Node.js is installed and `npm install` completes, you have a fully functional application:

- 🔐 Secure authentication
- 📝 Rich text editing with TipTap
- 💾 Automatic saving
- 🔍 Search functionality
- 📜 Revision history
- 📤 Import/Export Markdown
- 🎨 Beautiful UI with Tailwind

Happy coding on Windows! 🚀
