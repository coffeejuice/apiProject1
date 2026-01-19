# Techno-Notion Frontend

A modern web-based block editor (Notion-like) built with React, TypeScript, and TipTap. This frontend connects to the FastAPI backend to provide a complete document editing experience with versioning and collaboration features.

## 🚀 Features

- **Authentication**: Secure login with JWT tokens
- **Document Management**: Create, edit, and manage multiple documents
- **Rich Text Editing**: TipTap editor with support for:
  - Headings (H1, H2, H3)
  - Text formatting (bold, italic, strikethrough, code)
  - Lists (bullet, ordered, task lists)
  - Code blocks and blockquotes
- **Autosave**: Automatic saving every 800ms of idle time or every 10 seconds
- **Revision History**: View and restore previous document versions
- **Import/Export**: Markdown import and export functionality
- **Search**: Global search across all documents
- **Configurable API**: Easy API endpoint configuration

## 🛠 Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **TipTap** - Rich text editor (ProseMirror-based)
- **Zustand** - State management
- **React Router** - Client-side routing

## 📋 Prerequisites

- **Node.js** 18+ and npm
- **Backend API** running on `http://127.0.0.1:8001` (or configured URL)

## 🏃 Quick Start

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### 3. Login

Use your existing backend credentials to log in. If you need to configure a different API URL, click "⚙️ API Settings" on the login page.

## 📦 Available Scripts

```bash
npm run dev        # Start development server
npm run build      # Build for production
npm run preview    # Preview production build
npm run lint       # Run ESLint
npm run typecheck  # Run TypeScript type checking
```

## ⚙️ Configuration

### API Base URL

The default API URL is `http://127.0.0.1:8001`. You can change this:

1. On the login page, click "⚙️ API Settings"
2. Enter your custom API URL
3. Click "Save Settings"

The setting is persisted in browser local storage.

### Environment Variables

For build-time configuration, you can create a `.env` file:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

## 🏗 Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # React components
│   │   ├── Editor.tsx           # Main TipTap editor
│   │   ├── EditorToolbar.tsx    # Formatting toolbar
│   │   ├── Sidebar.tsx          # Document list sidebar
│   │   ├── SearchBar.tsx        # Search functionality
│   │   ├── RevisionHistory.tsx  # Revision modal
│   │   └── ImportExport.tsx     # Import/Export modal
│   ├── lib/             # Utilities
│   │   ├── apiClient.ts         # HTTP client wrapper
│   │   └── utils.ts             # Helper functions
│   ├── pages/           # Route pages
│   │   ├── LoginPage.tsx        # Authentication
│   │   └── AppPage.tsx          # Main application
│   ├── stores/          # Zustand state stores
│   │   ├── useSessionStore.ts   # Auth & session
│   │   ├── useDocumentsStore.ts # Document list
│   │   └── useEditorStore.ts    # Editor state
│   ├── types/           # TypeScript definitions
│   │   └── api.ts               # API types
│   ├── App.tsx          # Root component with routing
│   ├── main.tsx         # App entry point
│   └── index.css        # Global styles
├── index.html           # HTML template
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
├── vite.config.ts       # Vite config
└── tailwind.config.js   # Tailwind config
```

## 🔑 Key Concepts

### State Management

The app uses three main Zustand stores:

- **useSessionStore**: Authentication, user info, API configuration
- **useDocumentsStore**: Document list and current document
- **useEditorStore**: Editor content, autosave, and revision tracking

### Autosave Mechanism

Documents are automatically saved:
- After 800ms of idle time following edits
- Every 10 seconds during continuous editing
- Saves are sent as commit operations to `/documents/{id}/commit`

### Revision System

Each save creates a new revision on the backend. The editor tracks:
- `base_rev_number`: The revision the current edits are based on
- `device_id`: Unique identifier for this client (persisted in localStorage)
- `client_batch_id`: Unique ID for each save operation

### Tolerant API Parsing

The API client handles various response formats:
- Token fields: `access_token`, `token`, or `accessToken`
- List fields: `items`, `documents`, `data`, etc.

This ensures compatibility even if the backend response format changes slightly.

## 🐛 Troubleshooting

### Can't connect to backend

1. Ensure the backend is running on port 8001
2. Check the API URL in settings (⚙️ icon on login page)
3. Verify CORS is enabled on the backend

### Login fails

1. Verify your credentials are correct
2. Check browser console for detailed error messages
3. Ensure the backend `/auth/login` endpoint is working

### Documents not loading

1. Check authentication (token might have expired)
2. Verify the `/documents` endpoint returns valid data
3. Check browser console and network tab for errors

### Autosave not working

1. The backend must support the `/documents/{id}/commit` endpoint
2. Check the save status indicator in the editor header
3. If the endpoint doesn't exist yet, edits will be stored locally but not persisted

## 🔒 Security Notes

- Tokens are stored in browser `localStorage`
- All API requests include `Authorization: Bearer {token}` header
- Device IDs are generated once per browser and persisted

## 🚢 Production Deployment

### Build

```bash
npm run build
```

This creates an optimized build in the `dist/` folder.

### Serve

You can serve the built files with any static file server:

```bash
npm run preview  # Preview locally
```

Or deploy to:
- Vercel
- Netlify
- AWS S3 + CloudFront
- Any static hosting service

Make sure to configure the API base URL for production.

## 📝 License

This project is part of the Techno-Notion monorepo.

## 🤝 Contributing

1. Make changes in the `frontend/` directory only
2. Do not modify `backend/` code
3. Run `npm run typecheck` and `npm run lint` before committing
4. Test thoroughly with the backend running

## 📞 Support

For issues or questions:
1. Check the browser console for errors
2. Verify backend API is accessible
3. Review this README for configuration help
