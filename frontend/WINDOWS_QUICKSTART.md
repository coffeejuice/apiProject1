# Frontend Windows Quickstart

## Prerequisites
- Node.js 18+
- Backend running at http://127.0.0.1:8001

## Start backend (Terminal 1)
cd C:\Users\alext\ProgrammingProjects\apiProject1\backend
.venv\Scripts\activate
python run.py

## Install frontend deps (Terminal 2)
cd C:\Users\alext\ProgrammingProjects\apiProject1\frontend
npm install

## Start frontend (Terminal 2)
npm run dev

Frontend: http://localhost:5173

## Basic test
- Login with existing backend credentials
- Create a document
- Edit content and observe autosave
- Test search and revision history

## Common issues
- Port 5173 in use: free the port and retry
- npm install errors: ensure Node.js is installed and terminal restarted
