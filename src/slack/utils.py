"""Slack utility functions."""

import logging
from typing import Dict, Optional

from slack_bolt.app.async_app import AsyncApp

logger = logging.getLogger(__name__)


class SlackUserCache:
    """Cache for Slack user information."""

    def __init__(self):
        """Initialize the cache."""
        self._timezone_cache: Dict[str, str] = {}
        self._email_cache: Dict[str, str] = {}

    def clear(self):
        """Clear all caches."""
        self._timezone_cache.clear()
        self._email_cache.clear()


# Global cache instance
_user_cache = SlackUserCache()


async def _fetch_user_info(app: AsyncApp, user_id: str) -> Optional[Dict]:
    """Fetch user info from Slack API with error handling.

    Args:
        app: Slack AsyncApp instance
        user_id: Slack user ID

    Returns:
        User info dictionary or None if failed
    """
    try:
        result = await app.client.users_info(user=user_id)
        if result.get("ok"):
            return result.get("user", {})
        else:
            logger.warning(f"Failed to get user info for {user_id}: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error fetching user info for {user_id}: {e}")

    return None


async def get_user_timezone(app: AsyncApp, user_id: str) -> Optional[str]:
    """Get a Slack user's timezone from their profile.

    Args:
        app: Slack AsyncApp instance
        user_id: Slack user ID

    Returns:
        Timezone string (e.g., "America/Los_Angeles") or None if not found
    """
    # Check cache first
    if user_id in _user_cache._timezone_cache:
        return _user_cache._timezone_cache[user_id]

    user = await _fetch_user_info(app, user_id)
    if user:
        timezone = user.get("tz")
        if timezone:
            # Cache the result
            _user_cache._timezone_cache[user_id] = timezone
            logger.debug(f"Retrieved timezone for user {user_id}: {timezone}")
            return timezone

    return None


async def get_user_email(app: AsyncApp, user_id: str) -> Optional[str]:
    """Get a Slack user's email address.

    Args:
        app: Slack AsyncApp instance
        user_id: Slack user ID

    Returns:
        Email address or None if not found
    """
    # Check cache first
    if user_id in _user_cache._email_cache:
        return _user_cache._email_cache[user_id]

    user = await _fetch_user_info(app, user_id)
    if user:
        profile = user.get("profile", {})
        email = profile.get("email")
        if email:
            # Cache the result
            _user_cache._email_cache[user_id] = email
            logger.debug(f"Retrieved email for user {user_id}")
            return email

    return None


async def get_user_emails(app: AsyncApp, user_ids: list[str]) -> Dict[str, str]:
    """Get email addresses for multiple users.

    Args:
        app: Slack AsyncApp instance
        user_ids: List of Slack user IDs

    Returns:
        Dictionary mapping user IDs to email addresses (excludes users without emails)
    """
    emails = {}
    for user_id in user_ids:
        email = await get_user_email(app, user_id)
        if email:
            emails[user_id] = email
    return emails


async def get_user_name(app: AsyncApp, user_id: str) -> str:
    """Get a Slack user's display name.

    Args:
        app: Slack AsyncApp instance
        user_id: Slack user ID

    Returns:
        User's display name or user ID if not found
    """
    user = await _fetch_user_info(app, user_id)
    if user:
        profile = user.get("profile", {})
        # Try display_name first, fall back to real_name
        name = profile.get("display_name") or profile.get("real_name") or user.get("name")
        if name:
            return name

    return user_id


def clear_user_cache():
    """Clear the user information cache."""
    _user_cache.clear()
    logger.info("User cache cleared")
