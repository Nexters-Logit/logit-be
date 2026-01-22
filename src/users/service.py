"""User service layer - Business logic for user operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


async def create_user(*, session: AsyncSession, user_create: UserCreate) -> User:
    """Create a new user (OAuth only - no password)."""
    db_obj = User(
        email=user_create.email,
        full_name=user_create.full_name,
        is_active=user_create.is_active,
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_user(*, session: AsyncSession, db_user: User, user_in: UserUpdate) -> User:
    """Update a user."""
    user_data = user_in.model_dump(exclude_unset=True)

    for key, value in user_data.items():
        setattr(db_user, key, value)

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_tokens(
    *, session: AsyncSession, db_user: User, access_token: str, refresh_token: str
) -> User:
    """Update user's access and refresh tokens."""
    db_user.access_token = access_token
    db_user.refresh_token = refresh_token
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def clear_tokens(*, session: AsyncSession, db_user: User) -> User:
    """Clear user's tokens on logout."""
    db_user.access_token = None
    db_user.refresh_token = None
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


async def get_user_by_id(*, session: AsyncSession, user_id: UUID) -> Optional[User]:
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


async def delete_user(*, session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Delete a user."""
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
        await session.commit()
    return user