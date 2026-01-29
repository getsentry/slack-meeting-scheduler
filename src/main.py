"""Main entry point for the meeting scheduler application."""

import asyncio
import logging
import sys

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from .config import get_config
from .coordinator.meeting_coordinator import MeetingCoordinator
from .slack.app import create_slack_app
from .slack.handlers import register_handlers

# Setup Sentry
def setup_sentry(config):
    """Configure Sentry error tracking.

    Args:
        config: Application configuration
    """
    if not config.sentry_dsn:
        return

    # Configure logging integration
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        environment=config.sentry_environment,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        integrations=[sentry_logging],
        # Set release version from package version
        release=f"slack-meeting-scheduler@0.1.0",
        # Attach stack traces to all messages
        attach_stacktrace=True,
        # Send default PII (personally identifiable information)
        send_default_pii=False,
    )

    logging.info(f"Sentry initialized for environment: {config.sentry_environment}")


# Setup logging
def setup_logging(log_level: str):
    """Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from external libraries
    logging.getLogger('slack_bolt').setLevel(logging.WARNING)
    logging.getLogger('slack_sdk').setLevel(logging.WARNING)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)


async def main():
    """Main application entry point."""
    # Load configuration
    try:
        config = get_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("Make sure you have a .env file with required environment variables.")
        print("See .env.example for reference.")
        sys.exit(1)

    # Setup logging
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    # Setup Sentry error tracking
    setup_sentry(config)

    logger.info("Starting Meeting Scheduler application")
    logger.info(f"Configuration: duration={config.default_meeting_duration}m, "
                f"min_reactions={config.min_reactions}, "
                f"business_hours={config.business_hours_start}-{config.business_hours_end}")

    # Create Slack app
    app = create_slack_app()

    # Create meeting coordinator
    coordinator = MeetingCoordinator()

    # Register handlers
    register_handlers(app, coordinator)

    logger.info("Handlers registered, starting Socket Mode connection...")

    # Start the app
    try:
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        handler = AsyncSocketModeHandler(app, config.slack_app_token)
        await handler.start_async()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error running application: {e}", exc_info=True)
        sys.exit(1)


def run():
    """Synchronous entry point for running the async main function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
