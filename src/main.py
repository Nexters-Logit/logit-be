"""
FastAPI application with domain-driven structure.

Inspired by fastapi-best-practices and Netflix Dispatch.
"""

import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from src.auth import router as auth_router
from src.config import settings
from src.database import init_qdrant_collection
from src.experience import router as experience_router
from src.projects import router as projects_router
from src.questions import router as questions_router
from src.users import router as users_router
from src.chats import router as chats_router

# HTTP Basic Auth for docs
security = HTTPBasic()


def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify credentials for docs access"""
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.DOCS_USERNAME.encode("utf-8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.DOCS_PASSWORD.encode("utf-8")
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Runs once on startup and cleanup on shutdown.
    """
    # Startup: Initialize Qdrant collection
    init_qdrant_collection()
    yield
    # Shutdown: cleanup if needed


# Docs authentication required for dev environment
docs_auth_required = settings.ENVIRONMENT == "dev"

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=None if docs_auth_required else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if docs_auth_required else "/docs",
    redoc_url=None if docs_auth_required else "/redoc",
    description="Domain-Driven FastAPI with OAuth, JWT, and Modern Stack",
    lifespan=lifespan,
)

# Custom docs endpoints with authentication (for dev/staging)
if docs_auth_required:
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json(username: str = Depends(verify_docs_credentials)):
        return get_openapi(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            description="Domain-Driven FastAPI with OAuth, JWT, and Modern Stack",
            routes=app.routes,
        )

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui(username: str = Depends(verify_docs_credentials)):
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.PROJECT_NAME} - Swagger UI",
        )

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc(username: str = Depends(verify_docs_credentials)):
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.PROJECT_NAME} - ReDoc",
        )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.all_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include domain routers
app.include_router(
    auth_router.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"],
)
app.include_router(
    users_router.router,
    prefix=f"{settings.API_V1_STR}/users",
    tags=["Users"],
)
app.include_router(
    projects_router.router,
    prefix=f"{settings.API_V1_STR}/projects",
    tags=["Projects"],
)
app.include_router(
    experience_router.router,
    prefix=f"{settings.API_V1_STR}/experiences",
    tags=["Experiences"],
)
app.include_router(
    questions_router.router,
    prefix=f"{settings.API_V1_STR}/projects/{{project_id}}/questions",
    tags=["Questions"],
)
app.include_router(
    chats_router.router,
    prefix=f"{settings.API_V1_STR}",
    tags=["Chats"],
)

@app.get("/")
async def root():
    """
    Root endpoint.
    Returns basic API information.
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "environment": settings.ENVIRONMENT,
        "architecture": "Domain-Driven Design",
        "stack": {
            "orm": "SQLModel + asyncpg",
            "vector_db": "Qdrant",
            "cache": "Redis",
            "package_manager": "uv",
        },
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Used by Docker and orchestration tools to verify service health.
    """
    return {"status": "healthy"}