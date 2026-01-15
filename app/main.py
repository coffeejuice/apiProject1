from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, process, blocks, revisions, sharing, search, import_export
from app.routers.sharing import share_router
from app.routers.search import document_search_router

app = FastAPI(
    title="Notion-style Block Editor API",
    description="Backend API for a Notion-style Markdown block editor with versioning and offline support",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(process.router)
app.include_router(blocks.router)
app.include_router(revisions.router)
app.include_router(sharing.router)
app.include_router(share_router)
app.include_router(search.router)
app.include_router(document_search_router)
app.include_router(import_export.router)
from app.routers import settings
app.include_router(settings.router)

@app.get("/")
def root():
    return {
        "message": "Notion-style Block Editor API",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
