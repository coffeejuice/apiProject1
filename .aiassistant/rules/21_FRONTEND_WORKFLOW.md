# Frontend Workflow

## Setup
1) Install Node.js 18+.
2) cd frontend
3) npm install
4) npm run dev  # http://localhost:5173

## Build and checks
- npm run build
- npm run preview
- npm run lint
- npm run typecheck

## UI layout guidelines
- Two-pane layout: sidebar (documents/search) + editor area.
- Keep business logic in stores; components should be mostly presentational.
- Use Tailwind for layout and styling; avoid heavy UI frameworks.

## Integration notes
- Default API base URL: http://127.0.0.1:8001
- CORS must allow the frontend origin.
