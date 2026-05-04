"""Google Calendar API client."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..models import TimeSlot
from .auth import GoogleAuth

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _handle_calendar_errors(operation: str):
    """Context manager for handling Google Calendar API errors.

    Args:
        operation: Description of the operation being performed

    Raises:
        Exception: Re-raises exceptions with appropriate logging
    """
    try:
        yield
    except HttpError as e:
        logger.error(f"HTTP error {operation}: {e}", exc_info=True)
        raise Exception(f"Failed to {operation}: {e}")
    except Exception as e:
        logger.error(f"Error {operation}: {e}", exc_info=True)
        raise


class GoogleCalendarClient:
    """Client for Google Calendar API operations."""

    def __init__(self, auth: GoogleAuth):
        """Initialize the calendar client.

        Args:
            auth: GoogleAuth instance
        """
        self._auth = auth
        self._service = None

    def _get_service(self):
        """Get or create the Calendar API service.

        Returns:
            Google Calendar API service
        """
        if self._service is None:
            credentials = self._auth.get_credentials()
            self._service = build("calendar", "v3", credentials=credentials)
            logger.debug("Calendar API service created")
        return self._service

    async def get_freebusy(
        self, email_addresses: List[str], time_min: datetime, time_max: datetime
    ) -> Dict[str, List[TimeSlot]]:
        """Query freebusy information for multiple calendars.

        Args:
            email_addresses: List of email addresses to check
            time_min: Start of time range (timezone-aware)
            time_max: End of time range (timezone-aware)

        Returns:
            Dictionary mapping email addresses to list of busy TimeSlots
        """
        if not email_addresses:
            logger.warning("No email addresses provided for freebusy query")
            return {}

        async with _handle_calendar_errors("querying freebusy"):
            service = self._get_service()

            # Prepare request body
            body = {
                "timeMin": time_min.isoformat(),
                "timeMax": time_max.isoformat(),
                "items": [{"id": email} for email in email_addresses],
            }

            logger.info(
                f"Querying freebusy for {len(email_addresses)} calendars "
                f"from {time_min} to {time_max}"
            )

            # Execute freebusy query in thread pool to avoid blocking event loop
            request = service.freebusy().query(body=body)
            response = await asyncio.to_thread(request.execute)

            # Parse response
            calendars = response.get("calendars", {})
            busy_times: Dict[str, List[TimeSlot]] = {}

            for email, calendar_data in calendars.items():
                busy_periods = calendar_data.get("busy", [])
                time_slots = []

                for period in busy_periods:
                    start = datetime.fromisoformat(
                        period["start"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
                    time_slots.append(TimeSlot(start=start, end=end))

                busy_times[email] = time_slots
                logger.debug(f"Found {len(time_slots)} busy periods for {email}")

            return busy_times

    async def create_event(
        self,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        attendee_emails: List[str],
        description: str = "",
        timezone: str = "UTC",
    ) -> Dict:
        """Create a calendar event with Google Meet link.

        Args:
            summary: Event title/summary
            start_time: Event start time (timezone-aware)
            end_time: Event end time (timezone-aware)
            attendee_emails: List of attendee email addresses
            description: Event description
            timezone: Timezone for the event (default: UTC)

        Returns:
            Created event object with 'htmlLink' and 'hangoutLink' fields

        Raises:
            Exception: If event creation fails
        """
        async with _handle_calendar_errors("creating event"):
            service = self._get_service()

            # Prepare event body
            event = {
                "summary": summary,
                "description": description,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": timezone,
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": timezone,
                },
                "attendees": [{"email": email} for email in attendee_emails],
                "conferenceData": {
                    "createRequest": {
                        "requestId": str(uuid.uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
                "reminders": {"useDefault": True},
                # Send invitations to attendees
                "guestsCanSeeOtherGuests": True,
                "guestsCanInviteOthers": False,
                # Make event visible to the entire organization
                # This allows org-wide access to recordings when they're stored in Google Drive
                "visibility": "default",
                "guestsCanModify": False,
            }

            logger.info(
                f"Creating calendar event '{summary}' from {start_time} to {end_time} "
                f"with {len(attendee_emails)} attendees"
            )

            # Create the event with conferenceDataVersion=1 to create Meet link
            request = service.events().insert(
                calendarId="primary",
                body=event,
                conferenceDataVersion=1,
                sendUpdates="all",  # Send email invitations to all attendees
            )
            # Run in thread pool to avoid blocking event loop
            created_event = await asyncio.to_thread(request.execute)

            # Extract useful information
            event_link = created_event.get("htmlLink")
            meet_link = self.get_meet_link(created_event)

            logger.info(
                f"Event created successfully: {event_link}\nMeet link: {meet_link}"
            )

            return created_event

    def get_meet_link(self, event: Dict) -> Optional[str]:
        """Extract Google Meet link from an event.

        Args:
            event: Event object from Calendar API

        Returns:
            Google Meet link or None if not found
        """
        # Try hangoutLink first (deprecated but still works)
        meet_link = event.get("hangoutLink")
        if meet_link:
            return meet_link

        # Try conferenceData
        conference_data = event.get("conferenceData", {})
        entry_points = conference_data.get("entryPoints", [])
        for entry_point in entry_points:
            if entry_point.get("entryPointType") == "video":
                return entry_point.get("uri")

        logger.warning("No Meet link found in event")
        return None

    def get_event_link(self, event: Dict) -> Optional[str]:
        """Extract calendar event link from an event.

        Args:
            event: Event object from Calendar API

        Returns:
            Calendar event link or None if not found
        """
        return event.get("htmlLink")
