"""User service layer - Business logic for user operations."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.security import get_password_hash, verify_password
from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
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
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_user(*, session: AsyncSession, db_user: User, user_in: UserUpdate) -> User:
    """Update a user."""
    user_data = user_in.model_dump(exclude_unset=True)

    # Hash password if provided
    if "password" in user_data and user_data["password"]:
        hashed_password = get_password_hash(user_data["password"])
        del user_data["password"]
        user_data["hashed_password"] = hashed_password

    for key, value in user_data.items():
        setattr(db_user, key, value)

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_refresh_token(*, session: AsyncSession, db_user: User, refresh_token: str) -> User:
    """Update user's refresh token."""
    db_user.refresh_token = refresh_token
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def get_user_by_email(*, session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    return result.scalars().first()


async def get_user_by_id(*, session: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return await session.get(User, user_id)


async def get_user_by_oauth(
    *, session: AsyncSession, provider: str, provider_id: str
) -> Optional[User]:
    """Get user by OAuth provider and provider ID."""
    statement = select(User).where(
        User.oauth_provider == provider, User.oauth_provider_id == provider_id
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def authenticate_user(*, session: AsyncSession, email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password."""
    user = await get_user_by_email(session=session, email=email)
    if not user:
        return None
    if not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def delete_user(*, session: AsyncSession, user_id: int) -> Optional[User]:
    """Delete a user."""
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
        await session.commit()
    return user