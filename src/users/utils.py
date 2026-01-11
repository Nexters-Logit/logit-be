"""User utility functions."""

from src.users.models import User


def get_user_display_name(user: User) -> str:
    """Get user's display name (full_name or email)."""
    return user.full_name or user.email.split("@")[0]


def is_oauth_user(user: User) -> bool:
    """Check if user is registered via OAuth."""
    return user.oauth_provider is not None


def can_change_password(user: User) -> bool:
    """Check if user can change password (non-OAuth users)."""
    return user.hashed_password is not None and not is_oauth_user(user)
