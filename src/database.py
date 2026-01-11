from sqlmodel import Session, create_engine, select

from src.config import settings

# Create database engine
engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=True)


def init_db(session: Session) -> None:
    """
    Initialize database with initial data.
    Tables should be created with Alembic migrations.
    """
    # Import all models here to ensure they are registered
    from app import models  # noqa: F401

    # Create tables (use Alembic migrations in production)
    # from sqlmodel import SQLModel
    # SQLModel.metadata.create_all(engine)

    # Create initial data if needed
    pass
