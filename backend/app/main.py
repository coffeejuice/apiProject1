from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.logging_config import configure_logging
from app.routers import auth, document, blocks, search, projects, library, logs, operation_templates, setup, workflow
from app.routers.search import document_search_router
from app.routers import settings

configure_logging(service="api", worker_name="api")

app = FastAPI(
    title="ForgeLab API",
    description="Projects, inheritable documents, and linked-list block editing API",
    version="2.0.0",
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
app.include_router(projects.router)
app.include_router(document.router)
app.include_router(blocks.router)
app.include_router(search.router)
app.include_router(document_search_router)
app.include_router(settings.router)
app.include_router(library.router)
app.include_router(logs.router)
app.include_router(operation_templates.router)
app.include_router(setup.router)
app.include_router(workflow.router)

@app.get("/")
def root():
    return {
        "message": "ForgeLab API",
        "docs": "/docs",
        "version": "2.0.0",
    }

@app.get("/health")
def health_check():
    return {"status": "healthy"}
