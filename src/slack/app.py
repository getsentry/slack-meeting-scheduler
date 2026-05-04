"""Slack Bolt app initialization."""

import logging
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from ..config import get_config

logger = logging.getLogger(__name__)


def create_slack_app() -> AsyncApp:
    """Create and configure the Slack Bolt app.

    Returns:
        Configured AsyncApp instance
    """
    config = get_config()

    # Initialize the Slack app
    app = AsyncApp(
        token=config.slack_bot_token,
        # Socket mode doesn't need signing secret
    )

    logger.info("Slack app initialized successfully")
    return app


def create_socket_mode_handler(app: AsyncApp) -> AsyncSocketModeHandler:
    """Create Socket Mode handler for the Slack app.

    Args:
        app: The Slack AsyncApp instance

    Returns:
        AsyncSocketModeHandler instance
    """
    config = get_config()

    handler = AsyncSocketModeHandler(app=app, app_token=config.slack_app_token)

    logger.info("Socket Mode handler created successfully")
    return handler


async def start_slack_app(app: AsyncApp):
    """Start the Slack app with Socket Mode.

    Args:
        app: The Slack AsyncApp instance
    """
    handler = create_socket_mode_handler(app)

    logger.info("Starting Slack app in Socket Mode...")
    await handler.start_async()
