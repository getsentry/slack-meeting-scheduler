"""Meeting coordinator - orchestrates the entire workflow."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import sentry_sdk
from slack_bolt.app.async_app import AsyncApp

from ..config import get_config
from ..google.auth import GoogleAuth
from ..google.calendar_client import GoogleCalendarClient
from ..models import MeetingRequest, SchedulingMode, TimeSlot
from ..scheduling.engine import SchedulingEngine
from ..scheduling.parser import DateTimeParser
from ..scheduling.timezone_handler import TimezoneHandler
from ..slack.command_parser import CommandParameters
from ..slack.reactions import get_reaction_tracker
from ..slack import utils as slack_utils

logger = logging.getLogger(__name__)


class MeetingCoordinator:
    """Coordinates meeting scheduling workflow."""

    def __init__(self):
        """Initialize the meeting coordinator."""
        self._config = get_config()
        self._reaction_tracker = get_reaction_tracker()

        # Initialize Google Calendar client
        service_account_json = self._config.get_service_account_credentials()
        self._google_auth = GoogleAuth(service_account_json)
        self._calendar_client = GoogleCalendarClient(self._google_auth)

        logger.info("Meeting coordinator initialized")

    async def handle_meeting_request(
        self,
        params: CommandParameters,
        channel_id: str,
        user_id: str,
        app: AsyncApp
    ):
        """Handle a meeting scheduling request.

        Main workflow entry point.

        Args:
            params: Parsed command parameters
            channel_id: Slack channel ID
            user_id: User ID who initiated the request
            app: Slack AsyncApp instance
        """
        logger.info(
            f"Handling meeting request from user {user_id} in channel {channel_id}: "
            f"mode={params.scheduling_mode}, duration={params.duration_minutes}m"
        )

        # Set Sentry context for this request
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("scheduling_mode", str(params.scheduling_mode))
            scope.set_tag("channel_id", channel_id)
            scope.set_user({"id": user_id})
            scope.set_context("meeting_request", {
                "duration_minutes": params.duration_minutes,
                "min_reactions": params.min_reactions,
                "reaction_duration_seconds": params.reaction_duration_seconds,
            })

            # Post initial message
            message = await self._post_initial_message(
                app, channel_id, params, user_id
            )
            message_ts = message["ts"]

            # Create meeting request object
            request = MeetingRequest(
                request_id=str(uuid.uuid4()),
                channel_id=channel_id,
                message_ts=message_ts,
                initiator_user_id=user_id,
                reaction_duration_seconds=params.reaction_duration_seconds,
                scheduling_mode=params.scheduling_mode,
                duration_minutes=params.duration_minutes,
                min_reactions=params.min_reactions,
                created_at=datetime.utcnow(),
                specific_datetime=None,
                participants=[]
            )

            # Start reaction tracking (async callback)
            await self._reaction_tracker.start_tracking(
                request=request,
                app=app,
                callback=lambda req, parts: self._handle_reactions_complete(req, parts, app, params)
            )

    async def _post_initial_message(
        self,
        app: AsyncApp,
        channel_id: str,
        params: CommandParameters,
        user_id: str
    ) -> Dict:
        """Post initial message asking for reactions.

        Args:
            app: Slack AsyncApp instance
            channel_id: Channel ID
            params: Command parameters
            user_id: Initiating user ID

        Returns:
            Message response with timestamp
        """
        # Format duration for display
        duration_str = self._format_duration(params.reaction_duration_seconds)

        # Build message based on mode
        if params.scheduling_mode == SchedulingMode.SPECIFIC_TIME:
            mode_desc = f"specific time: *{params.specific_datetime_text}*"
        else:
            mode_desc = "automatically find the best time for everyone"

        message = (
            f":calendar: <@{user_id}> wants to schedule a *{params.duration_minutes}-minute meeting* ({mode_desc})!\n\n"
            f":white_check_mark: React with :{self._config.default_reaction_emoji}: if you're interested in attending.\n"
            f":alarm_clock: Collecting responses for *{duration_str}*...\n"
        )

        if params.min_reactions > 1:
            message += f":busts_in_silhouette: Minimum {params.min_reactions} people needed.\n"

        result = await app.client.chat_postMessage(
            channel=channel_id,
            text=message
        )

        logger.info(f"Posted initial message: {result['ts']}")
        return result

    async def _handle_reactions_complete(
        self,
        request: MeetingRequest,
        participants: List[str],
        app: AsyncApp,
        params: CommandParameters
    ):
        """Handle completion of reaction collection period.

        Args:
            request: MeetingRequest object
            participants: List of user IDs who reacted
            app: Slack AsyncApp instance
            params: Original command parameters
        """
        logger.info(
            f"Reactions complete for request {request.request_id}: "
            f"{len(participants)} participants"
        )

        # Set Sentry context for this callback (runs asynchronously after initial scope)
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("scheduling_mode", str(request.scheduling_mode))
            scope.set_tag("channel_id", request.channel_id)
            scope.set_tag("request_id", request.request_id)
            scope.set_user({"id": request.initiator_user_id})
            scope.set_context("meeting_request", {
                "duration_minutes": request.duration_minutes,
                "min_reactions": request.min_reactions,
                "participant_count": len(participants),
            })

            # Check minimum reactions
            if len(participants) < request.min_reactions:
                await self._post_insufficient_reactions(
                    app, request.channel_id, request.message_ts,
                    len(participants), request.min_reactions
                )
                return

            # Get participant details
            user_emails = await slack_utils.get_user_emails(app, participants)
            user_timezones = {}
            for user_id in participants:
                tz = await slack_utils.get_user_timezone(app, user_id)
                if tz:
                    user_timezones[user_id] = tz
                else:
                    user_timezones[user_id] = "UTC"  # Fallback

            # Ensure initiator's timezone is available (even if they didn't react)
            if request.initiator_user_id not in user_timezones:
                initiator_tz = await slack_utils.get_user_timezone(app, request.initiator_user_id)
                user_timezones[request.initiator_user_id] = initiator_tz if initiator_tz else "UTC"

            if not user_emails:
                await self._post_error(
                    app, request.channel_id, request.message_ts,
                    "Could not retrieve email addresses for participants."
                )
                return

            try:
                # Branch based on scheduling mode
                if request.scheduling_mode == SchedulingMode.SPECIFIC_TIME:
                    await self._schedule_specific_time(
                        app, request, params, participants,
                        user_emails, user_timezones
                    )
                else:
                    # Check if find-time feature is enabled
                    if not self._config.enable_find_time:
                        await self._post_error(
                            app, request.channel_id, request.message_ts,
                            "Automatic time finding is currently disabled."
                        )
                        return

                    await self._schedule_find_availability(
                        app, request, participants,
                        user_emails, user_timezones
                    )

            except Exception as e:
                logger.error(f"Error scheduling meeting: {e}", exc_info=True)
                # Capture exception in Sentry with context
                sentry_sdk.capture_exception(e)
                await self._post_error(
                    app, request.channel_id, request.message_ts,
                    f"Failed to schedule meeting: {str(e)}"
                )

    async def _schedule_specific_time(
        self,
        app: AsyncApp,
        request: MeetingRequest,
        params: CommandParameters,
        participants: List[str],
        user_emails: Dict[str, str],
        user_timezones: Dict[str, str]
    ):
        """Schedule meeting at a specific time.

        Args:
            app: Slack AsyncApp instance
            request: MeetingRequest object
            params: Command parameters
            participants: List of participant user IDs
            user_emails: Dictionary mapping user IDs to emails
            user_timezones: Dictionary mapping user IDs to timezones
        """
        logger.info("Scheduling meeting at specific time")

        # Parse the datetime using initiator's timezone
        initiator_tz = user_timezones.get(request.initiator_user_id, "UTC")
        parsed_dt = DateTimeParser.parse_with_fallback(
            params.specific_datetime_text,
            timezone=initiator_tz
        )

        if not parsed_dt:
            await self._post_error(
                app, request.channel_id, request.message_ts,
                f"Could not parse date/time: {params.specific_datetime_text}"
            )
            return

        # Validate it's in the future
        if not DateTimeParser.validate_future_datetime(parsed_dt, min_minutes_ahead=1):
            await self._post_error(
                app, request.channel_id, request.message_ts,
                "The specified time is in the past. Please provide a future date/time."
            )
            return

        # Calculate end time
        start_time = TimezoneHandler.convert_to_utc(parsed_dt)
        end_time = start_time + timedelta(minutes=request.duration_minutes)

        # Create calendar event
        event = await self._calendar_client.create_event(
            summary=f"Meeting (via Slack)",
            start_time=start_time,
            end_time=end_time,
            attendee_emails=list(user_emails.values()),
            description=f"Meeting scheduled via Slack by <@{request.initiator_user_id}>"
        )

        # Extract links
        meet_link = self._calendar_client.get_meet_link(event)
        event_link = self._calendar_client.get_event_link(event)

        # Post success message
        await self._post_success_message(
            app, request.channel_id, request.message_ts,
            start_time, request.duration_minutes,
            participants, meet_link, event_link,
            user_timezones
        )

    async def _schedule_find_availability(
        self,
        app: AsyncApp,
        request: MeetingRequest,
        participants: List[str],
        user_emails: Dict[str, str],
        user_timezones: Dict[str, str]
    ):
        """Schedule meeting by finding optimal availability.

        Args:
            app: Slack AsyncApp instance
            request: MeetingRequest object
            participants: List of participant user IDs
            user_emails: Dictionary mapping user IDs to emails
            user_timezones: Dictionary mapping user IDs to timezones
        """
        logger.info("Finding optimal availability for meeting")

        # Query freebusy for all participants
        search_start = datetime.now(timezone.utc)
        search_end = search_start + timedelta(days=self._config.max_days_ahead)

        freebusy_data = await self._calendar_client.get_freebusy(
            email_addresses=list(user_emails.values()),
            time_min=search_start,
            time_max=search_end
        )

        # Create timezone mapping for emails (needed by scheduling engine)
        email_timezones = {email: user_timezones[user_id]
                          for user_id, email in user_emails.items()}

        # Find optimal time (use initiator's timezone as reference for business hours)
        initiator_tz = user_timezones.get(request.initiator_user_id, "UTC")

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=list(user_emails.values()),
            duration_minutes=request.duration_minutes,
            search_start=search_start,
            search_days=self._config.max_days_ahead,
            business_start=self._config.get_business_hours_start(),
            business_end=self._config.get_business_hours_end(),
            freebusy_data=freebusy_data,
            user_timezones=email_timezones,
            min_attendees=request.min_reactions,
            reference_timezone=initiator_tz
        )

        if not result:
            await self._post_no_availability(
                app, request.channel_id, request.message_ts,
                request.min_reactions, self._config.max_days_ahead
            )
            return

        optimal_slot, availability, score = result

        # Create calendar event
        start_time = optimal_slot
        end_time = start_time + timedelta(minutes=request.duration_minutes)

        event = await self._calendar_client.create_event(
            summary=f"Meeting (via Slack)",
            start_time=start_time,
            end_time=end_time,
            attendee_emails=list(user_emails.values()),
            description=f"Meeting scheduled via Slack by <@{request.initiator_user_id}>"
        )

        # Extract links
        meet_link = self._calendar_client.get_meet_link(event)
        event_link = self._calendar_client.get_event_link(event)

        # Post success message
        await self._post_success_message(
            app, request.channel_id, request.message_ts,
            start_time, request.duration_minutes,
            participants, meet_link, event_link,
            user_timezones
        )

    async def _post_success_message(
        self,
        app: AsyncApp,
        channel_id: str,
        thread_ts: str,
        start_time: datetime,
        duration_minutes: int,
        participants: List[str],
        meet_link: str,
        event_link: str,
        user_timezones: Dict[str, str]
    ):
        """Post success message with meeting details.

        Args:
            app: Slack AsyncApp instance
            channel_id: Channel ID
            thread_ts: Thread timestamp
            start_time: Meeting start time (UTC)
            duration_minutes: Meeting duration
            participants: List of participant user IDs
            meet_link: Google Meet link
            event_link: Calendar event link
            user_timezones: Dictionary mapping user IDs to timezones
        """
        # Format time for first user's timezone (or UTC)
        sample_tz = list(user_timezones.values())[0] if user_timezones else "UTC"
        formatted_time = TimezoneHandler.format_for_user(start_time, sample_tz)

        participant_mentions = " ".join([f"<@{user_id}>" for user_id in participants])

        message = (
            f":white_check_mark: *Meeting Scheduled!*\n\n"
            f":calendar: *Time:* {formatted_time}\n"
            f":hourglass: *Duration:* {duration_minutes} minutes\n"
            f":busts_in_silhouette: *Attendees:* {participant_mentions}\n\n"
        )

        if meet_link:
            message += f":video_camera: *Google Meet:* {meet_link}\n"
        if event_link:
            message += f":link: *Calendar Event:* {event_link}\n"

        message += "\nCalendar invitations have been sent to all attendees!"

        await app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=message
        )

        logger.info(f"Posted success message for meeting at {start_time}")

    async def _post_insufficient_reactions(
        self,
        app: AsyncApp,
        channel_id: str,
        thread_ts: str,
        actual: int,
        required: int
    ):
        """Post message about insufficient reactions."""
        message = (
            f":information_source: Not enough people interested in this meeting.\n"
            f"Got {actual} reaction(s), but need at least {required}."
        )

        await app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=message
        )

        logger.info(f"Posted insufficient reactions message ({actual}/{required})")

    async def _post_no_availability(
        self,
        app: AsyncApp,
        channel_id: str,
        thread_ts: str,
        min_attendees: int,
        days_searched: int
    ):
        """Post message about no availability found."""
        message = (
            f":calendar: Could not find a time when {min_attendees}+ people are available "
            f"in the next {days_searched} days.\n\n"
            f"Try:\n"
            f"- Reducing the minimum attendees requirement\n"
            f"- Scheduling for a specific time instead\n"
            f"- Asking people to update their calendars"
        )

        await app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=message
        )

        logger.info(f"Posted no availability message")

    async def _post_error(
        self,
        app: AsyncApp,
        channel_id: str,
        thread_ts: str,
        error_message: str
    ):
        """Post error message."""
        message = f":x: *Error:* {error_message}"

        await app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=message
        )

        logger.error(f"Posted error message: {error_message}")

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 7200:  # Less than 2 hours - show in minutes
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
