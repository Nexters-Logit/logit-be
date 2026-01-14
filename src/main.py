"""
FastAPI application with domain-driven structure.

Inspired by fastapi-best-practices and Netflix Dispatch.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth import router as auth_router
from src.config import settings
from src.projects import router as projects_router
from src.users import router as users_router

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    description="Domain-Driven FastAPI with OAuth, JWT, and Modern Stack",
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
