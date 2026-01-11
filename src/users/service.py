"""User service layer - Business logic for user operations."""

from sqlmodel import Session, select

from src.security import get_password_hash, verify_password
from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    """Create a new user with password."""
    db_obj = User(
        email=user_create.email,
        full_name=user_create.full_name,
        hashed_password=get_password_hash(user_create.password)
        if user_create.password
        else None,
        is_active=user_create.is_active,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    """Update a user."""
    user_data = user_in.model_dump(exclude_unset=True)

    # Hash password if provided
    if "password" in user_data and user_data["password"]:
        hashed_password = get_password_hash(user_data["password"])
        del user_data["password"]
        user_data["hashed_password"] = hashed_password

    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def update_refresh_token(*, session: Session, db_user: User, refresh_token: str) -> User:
    """Update user's refresh token."""
    db_user.refresh_token = refresh_token
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """Get user by email."""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_user_by_id(*, session: Session, user_id: int) -> User | None:
    """Get user by ID."""
    return session.get(User, user_id)


def get_user_by_oauth(
    *, session: Session, provider: str, provider_id: str
) -> User | None:
    """Get user by OAuth provider and provider ID."""
    statement = select(User).where(
        User.oauth_provider == provider, User.oauth_provider_id == provider_id
    )
    return session.exec(statement).first()


def authenticate_user(*, session: Session, email: str, password: str) -> User | None:
    """Authenticate a user with email and password."""
    user = get_user_by_email(session=session, email=email)
    if not user:
        return None
    if not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def delete_user(*, session: Session, user_id: int) -> User | None:
    """Delete a user."""
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()
    return user
