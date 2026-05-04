"""Slack command and event handlers."""

import logging
from typing import TYPE_CHECKING

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.context.async_context import AsyncBoltContext

from ..config import get_config
from .command_parser import CommandParser

if TYPE_CHECKING:
    from ..coordinator.meeting_coordinator import MeetingCoordinator

logger = logging.getLogger(__name__)


async def _process_schedule_request(
    text: str,
    user_id: str,
    channel_id: str,
    respond_func,
    coordinator: "MeetingCoordinator",
    app: AsyncApp,
):
    """Common logic for processing schedule requests.

    Args:
        text: Command text to parse
        user_id: Slack user ID
        channel_id: Slack channel ID
        respond_func: Function to send responses (either 'respond' or 'say')
        coordinator: MeetingCoordinator instance
        app: Slack AsyncApp instance
    """
    config = get_config()

    # Handle help request
    if not text or text.lower() in ["help", "?"]:
        await respond_func(CommandParser.get_help_message())
        return

    try:
        # Parse command
        params = CommandParser.parse(
            text,
            default_duration=config.default_meeting_duration,
            default_min=config.min_reactions,
        )

        # Delegate to coordinator
        await coordinator.handle_meeting_request(
            params=params, channel_id=channel_id, user_id=user_id, app=app
        )

    except ValueError as e:
        # Invalid command format
        logger.warning(f"Invalid command format: {e}")
        await respond_func(
            f":warning: *Invalid command:* {str(e)}\n\n{CommandParser.get_help_message()}"
        )
    except Exception as e:
        logger.error(f"Error handling schedule request: {e}", exc_info=True)
        await respond_func(
            ":x: *Error:* An unexpected error occurred while processing your request. "
            "Please try again or contact support if the issue persists."
        )


def register_handlers(app: AsyncApp, coordinator: "MeetingCoordinator"):
    """Register all Slack command and event handlers.

    Args:
        app: Slack AsyncApp instance
        coordinator: MeetingCoordinator instance
    """

    @app.command("/schedule-meet")
    async def handle_schedule_command(ack, command, respond, context: AsyncBoltContext):
        """Handle /schedule-meet slash command.

        Args:
            ack: Acknowledge function
            command: Command payload
            respond: Response function
            context: Bolt context
        """
        await ack()

        user_id = command["user_id"]
        channel_id = command["channel_id"]
        command_text = command.get("text", "").strip()

        logger.info(
            f"Received /schedule-meet command from user {user_id} in channel {channel_id}"
        )

        await _process_schedule_request(
            text=command_text,
            user_id=user_id,
            channel_id=channel_id,
            respond_func=respond,
            coordinator=coordinator,
            app=app,
        )

    @app.event("app_mention")
    async def handle_app_mention(event, say, context: AsyncBoltContext):
        """Handle app mentions (e.g., @MeetingBot schedule...).

        Args:
            event: Event payload
            say: Say function
            context: Bolt context
        """
        user_id = event["user"]
        channel_id = event["channel"]
        text = event.get("text", "")

        logger.info(f"Received app mention from user {user_id} in channel {channel_id}")

        # Remove the bot mention from the text
        # Format is typically: "<@U123ABC> rest of command"
        bot_user_id = context.get("bot_user_id")
        if bot_user_id:
            text = text.replace(f"<@{bot_user_id}>", "").strip()

        await _process_schedule_request(
            text=text,
            user_id=user_id,
            channel_id=channel_id,
            respond_func=say,
            coordinator=coordinator,
            app=app,
        )

    logger.info("Slack handlers registered successfully")
