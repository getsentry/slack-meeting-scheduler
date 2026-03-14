"""Reaction tracking functionality."""

import asyncio
import logging
from typing import Dict, List

from slack_bolt.app.async_app import AsyncApp

from ..config import get_config
from ..models import MeetingRequest

logger = logging.getLogger(__name__)


class ReactionTracker:
    """Tracks reactions on Slack messages for meeting scheduling."""

    def __init__(self):
        """Initialize the reaction tracker."""
        self._active_requests: Dict[str, MeetingRequest] = {}
        self._config = get_config()

    async def start_tracking(
        self,
        request: MeetingRequest,
        app: AsyncApp,
        callback
    ):
        """Start tracking reactions for a meeting request.

        Args:
            request: MeetingRequest to track
            app: Slack AsyncApp instance
            callback: Async function to call when reaction period ends
                     Should accept (request, participants) as arguments
        """
        # Store the request
        key = f"{request.channel_id}:{request.message_ts}"
        self._active_requests[key] = request

        logger.info(
            f"Started tracking reactions for request {request.request_id} "
            f"(duration: {request.reaction_duration_seconds}s)"
        )

        try:
            # Add initial reaction to the message to show users what to click
            await app.client.reactions_add(
                channel=request.channel_id,
                timestamp=request.message_ts,
                name=self._config.default_reaction_emoji
            )
        except Exception as e:
            logger.warning(f"Failed to add initial reaction: {e}")

        # Wait for the reaction period
        await asyncio.sleep(request.reaction_duration_seconds)

        # Collect reactions
        try:
            participants = await self.get_participants(
                app,
                request.channel_id,
                request.message_ts
            )

            logger.info(
                f"Reaction period ended for request {request.request_id}. "
                f"Collected {len(participants)} participants"
            )

            # Update request with participants
            request.participants = participants

            # Call the callback
            await callback(request, participants)

        except Exception as e:
            logger.error(f"Error collecting reactions for request {request.request_id}: {e}", exc_info=True)
            # Still remove from active requests
        finally:
            # Remove from active requests
            self._active_requests.pop(key, None)

    async def get_participants(
        self,
        app: AsyncApp,
        channel_id: str,
        message_ts: str
    ) -> List[str]:
        """Get list of user IDs who reacted to the message.

        Args:
            app: Slack AsyncApp instance
            channel_id: Channel ID
            message_ts: Message timestamp

        Returns:
            List of user IDs who reacted (excluding bots)
        """
        try:
            # Get reactions on the message
            result = await app.client.reactions_get(
                channel=channel_id,
                timestamp=message_ts
            )

            if not result.get("ok"):
                logger.error(f"Failed to get reactions: {result.get('error')}")
                return []

            message = result.get("message", {})
            reactions = message.get("reactions", [])

            # Collect users from all reactions
            participants = []
            seen_users = set()  # Track unique users

            for reaction in reactions:
                users = reaction.get("users", [])
                # Filter out bots
                for user_id in users:
                    if user_id in seen_users:
                        continue
                    seen_users.add(user_id)

                    # Check if user is a bot by fetching user info
                    try:
                        user_info = await app.client.users_info(user=user_id)
                        if user_info.get("ok"):
                            user = user_info.get("user", {})
                            if not user.get("is_bot", False):
                                participants.append(user_id)
                    except Exception as e:
                        logger.warning(f"Failed to check if user {user_id} is bot: {e}")
                        # Include user anyway if we can't determine
                        participants.append(user_id)

            logger.debug(f"Found {len(participants)} participants (non-bot users)")
            return participants

        except Exception as e:
            logger.error(f"Error getting participants: {e}", exc_info=True)
            return []

    def get_active_request(self, channel_id: str, message_ts: str) -> MeetingRequest:
        """Get an active meeting request by channel and message.

        Args:
            channel_id: Channel ID
            message_ts: Message timestamp

        Returns:
            MeetingRequest if found, None otherwise
        """
        key = f"{channel_id}:{message_ts}"
        return self._active_requests.get(key)

    def get_all_active_requests(self) -> List[MeetingRequest]:
        """Get all active meeting requests.

        Returns:
            List of all active MeetingRequests
        """
        return list(self._active_requests.values())


# Global tracker instance
_reaction_tracker: ReactionTracker = None


def get_reaction_tracker() -> ReactionTracker:
    """Get the global reaction tracker instance.

    Returns:
        ReactionTracker instance
    """
    global _reaction_tracker
    if _reaction_tracker is None:
        _reaction_tracker = ReactionTracker()
    return _reaction_tracker
