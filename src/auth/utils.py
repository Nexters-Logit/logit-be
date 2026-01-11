"""Auth utility functions."""

from datetime import UTC, datetime


def get_oauth_state() -> str:
    """Generate random state for OAuth flow."""
    import secrets

    return secrets.token_urlsafe(32)


def format_oauth_error(error: str, description: str | None = None) -> str:
    """Format OAuth error message."""
    if description:
        return f"{error}: {description}"
    return error


def is_token_expired(exp: int) -> bool:
    """Check if token is expired."""
    return datetime.now(UTC).timestamp() > exp
