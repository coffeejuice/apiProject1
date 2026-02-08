# Frontend Development Notes

## Status
Frontend is implemented and ready for local testing.

## Rules
- Do not modify backend code from frontend tasks unless explicitly asked.
- Keep API logic in the API client and Zustand stores; avoid direct fetch calls in components.

## Local test checklist
1) Start backend on http://127.0.0.1:8001
2) cd frontend && npm install
3) npm run dev
4) Login
5) Create a document
6) Edit content and observe autosave
7) Search documents
8) View revision history
9) Import/export Markdown

## Known constraints
- If the backend does not support commits, editor content persists only in localStorage.
- CORS must allow the frontend origin.

## Debugging tips
- Add request/response logging in the API client when troubleshooting.
- Use React DevTools to inspect state changes.
