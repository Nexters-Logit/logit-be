"""
FastAPI application with domain-driven structure.

Inspired by fastapi-best-practices and Netflix Dispatch.
"""

import secrets
import logging
from logging.config import fileConfig
from contextlib import asynccontextmanager
import time

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, status, Request
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
from src.common.slack import send_error_notification

# Load logging configuration
fileConfig('logging.ini', disable_existing_loggers=False)
logger = logging.getLogger(__name__)

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0 if settings.ENVIRONMENT == "dev" else 0.1,
        send_default_pii=False,
    )

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
    logger.info("🚀 Starting up Logit-server...")
    # Startup: Initialize Qdrant collection
    init_qdrant_collection()
    yield
    # Shutdown: cleanup if needed
    logger.info("👋 Shutting down Logit-server...")


# Docs configuration per environment
# - production: completely disabled (no openapi, docs, redoc)
# - dev: protected with HTTP Basic Auth
# - local: publicly accessible
is_production = settings.ENVIRONMENT == "production"
docs_auth_required = settings.ENVIRONMENT == "dev"

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=None if is_production else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if (is_production or docs_auth_required) else "/docs",
    redoc_url=None if (is_production or docs_auth_required) else "/redoc",
    description="Domain-Driven FastAPI with OAuth, JWT, and Modern Stack",
    lifespan=lifespan,
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer Auth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter the JWT token with the 'Bearer ' prefix, e.g., 'Bearer abcde12345'.",
        }
    }

    for path in openapi_schema["paths"].values():
        for operation in path.values():
            if "security" in operation:
                operation["security"] = [{"Bearer Auth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """로그 미들웨어"""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        logger.info(
            f'"{request.method} {request.url.path}" {response.status_code} {process_time:.2f}ms'
        )
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f'"{request.method} {request.url.path}" 500 {process_time:.2f}ms - Error: {e}',
            exc_info=True
        )
        send_error_notification(request, e)
        raise

if docs_auth_required:
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_json(username: str = Depends(verify_docs_credentials)):
        return app.openapi() # Call the custom openapi function to get the schema

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui(username: str = Depends(verify_docs_credentials)):
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.PROJECT_NAME} - Swagger UI",
            oauth2_redirect_url=None,
            init_oauth=None,
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