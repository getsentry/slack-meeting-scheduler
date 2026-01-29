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


def register_handlers(app: AsyncApp, coordinator: 'MeetingCoordinator'):
    """Register all Slack command and event handlers.

    Args:
        app: Slack AsyncApp instance
        coordinator: MeetingCoordinator instance
    """
    config = get_config()

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

        logger.info(f"Received /schedule-meet command from user {user_id} in channel {channel_id}")

        # Handle help request
        if not command_text or command_text.lower() in ['help', '?']:
            await respond(CommandParser.get_help_message())
            return

        try:
            # Parse command
            params = CommandParser.parse(
                command_text,
                default_duration=config.default_meeting_duration,
                default_min=config.min_reactions
            )

            # Delegate to coordinator
            await coordinator.handle_meeting_request(
                params=params,
                channel_id=channel_id,
                user_id=user_id,
                app=app
            )

        except ValueError as e:
            # Invalid command format
            logger.warning(f"Invalid command format: {e}")
            await respond(f":warning: *Invalid command:* {str(e)}\n\n{CommandParser.get_help_message()}")
        except Exception as e:
            logger.error(f"Error handling schedule command: {e}", exc_info=True)
            await respond(
                ":x: *Error:* An unexpected error occurred while processing your request. "
                "Please try again or contact support if the issue persists."
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

        # Handle help request
        if not text or text.lower() in ['help', '?']:
            await say(CommandParser.get_help_message())
            return

        try:
            # Parse command
            params = CommandParser.parse(
                text,
                default_duration=config.default_meeting_duration,
                default_min=config.min_reactions
            )

            # Delegate to coordinator
            await coordinator.handle_meeting_request(
                params=params,
                channel_id=channel_id,
                user_id=user_id,
                app=app
            )

        except ValueError as e:
            # Invalid command format
            logger.warning(f"Invalid command format from mention: {e}")
            await say(f":warning: *Invalid command:* {str(e)}\n\n{CommandParser.get_help_message()}")
        except Exception as e:
            logger.error(f"Error handling app mention: {e}", exc_info=True)
            await say(
                ":x: *Error:* An unexpected error occurred while processing your request. "
                "Please try again or contact support if the issue persists."
            )

    logger.info("Slack handlers registered successfully")
