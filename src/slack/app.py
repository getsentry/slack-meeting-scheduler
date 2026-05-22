"""Slack Bolt app initialization."""

import logging

from slack_bolt.app.async_app import AsyncApp

from ..config import get_config

logger = logging.getLogger(__name__)


def create_slack_app() -> AsyncApp:
    """Create and configure the Slack Bolt app.

    Returns:
        Configured AsyncApp instance
    """
    config = get_config()

    app = AsyncApp(
        token=config.slack_bot_token,
    )

    logger.info("Slack app initialized successfully")
    return app
