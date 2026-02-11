"""CLI for testing meeting scheduling without Slack."""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .config import get_config
from .google.auth import GoogleAuth
from .google.calendar_client import GoogleCalendarClient
from .scheduling.engine import SchedulingEngine
from .scheduling.parser import DateTimeParser
from .scheduling.timezone_handler import TimezoneHandler


def setup_logging(verbose: bool = False):
    """Setup logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Reduce noise from external libraries
    if not verbose:
        logging.getLogger('googleapiclient').setLevel(logging.WARNING)
        logging.getLogger('google.auth').setLevel(logging.WARNING)


def parse_attendees(attendees_arg: str) -> List[Dict[str, str]]:
    """Parse attendees from command line argument.

    Format: email1:tz1,email2:tz2
    Example: alice@example.com:America/New_York,bob@example.com:Europe/London

    Args:
        attendees_arg: Comma-separated list of email:timezone pairs

    Returns:
        List of dicts with 'email' and 'timezone' keys
    """
    attendees = []
    for part in attendees_arg.split(','):
        if ':' in part:
            email, tz = part.split(':', 1)
            attendees.append({'email': email.strip(), 'timezone': tz.strip()})
        else:
            # Default to UTC if no timezone specified
            attendees.append({'email': part.strip(), 'timezone': 'UTC'})
    return attendees


async def schedule_specific_time(
    calendar_client: GoogleCalendarClient,
    attendees: List[Dict[str, str]],
    specific_time: str,
    duration: int,
    reference_timezone: str,
    dry_run: bool = False
) -> None:
    """Schedule a meeting at a specific time.

    Args:
        calendar_client: Google Calendar client
        attendees: List of attendee dicts with email and timezone
        specific_time: Natural language datetime string
        duration: Meeting duration in minutes
        reference_timezone: Timezone for parsing the datetime
        dry_run: If True, don't actually create the event
    """
    logger = logging.getLogger(__name__)

    logger.info(f"Scheduling meeting at specific time: {specific_time}")
    logger.info(f"Reference timezone: {reference_timezone}")
    logger.info(f"Duration: {duration} minutes")
    logger.info(f"Attendees: {[a['email'] for a in attendees]}")

    # Parse the datetime
    parsed_dt = DateTimeParser.parse_with_fallback(specific_time, timezone=reference_timezone)
    if not parsed_dt:
        logger.error(f"Could not parse date/time: {specific_time}")
        sys.exit(1)

    # Validate it's in the future
    if not DateTimeParser.validate_future_datetime(parsed_dt, min_minutes_ahead=1):
        logger.error("The specified time is in the past")
        sys.exit(1)

    # Convert to UTC
    start_time = TimezoneHandler.convert_to_utc(parsed_dt)
    end_time = start_time + timedelta(minutes=duration)

    logger.info(f"Meeting time (UTC): {start_time.isoformat()} - {end_time.isoformat()}")

    # Show time in each attendee's timezone
    print("\nMeeting time for each attendee:")
    for attendee in attendees:
        local_time = TimezoneHandler.convert_to_timezone(start_time, attendee['timezone'])
        formatted = TimezoneHandler.format_for_user(start_time, attendee['timezone'])
        print(f"  {attendee['email']: <30} {formatted}")

    if dry_run:
        print("\n[DRY RUN] Would create calendar event (use --execute to actually create)")
        return

    # Create calendar event
    print("\nCreating calendar event...")
    event = await calendar_client.create_event(
        summary="Test Meeting (CLI)",
        start_time=start_time,
        end_time=end_time,
        attendee_emails=[a['email'] for a in attendees],
        description="Meeting scheduled via CLI test tool"
    )

    # Extract links
    meet_link = calendar_client.get_meet_link(event)
    event_link = calendar_client.get_event_link(event)

    print("\n✓ Meeting scheduled successfully!")
    print(f"  Event ID: {event.get('id')}")
    if meet_link:
        print(f"  Google Meet: {meet_link}")
    if event_link:
        print(f"  Calendar Event: {event_link}")


async def find_optimal_time(
    calendar_client: GoogleCalendarClient,
    attendees: List[Dict[str, str]],
    duration: int,
    search_days: int,
    min_attendees: int,
    reference_timezone: str,
    dry_run: bool = False
) -> None:
    """Find optimal meeting time based on availability.

    Args:
        calendar_client: Google Calendar client
        attendees: List of attendee dicts with email and timezone
        duration: Meeting duration in minutes
        search_days: Number of days ahead to search
        min_attendees: Minimum number of attendees required
        reference_timezone: Timezone for business hours reference
        dry_run: If True, don't actually create the event
    """
    logger = logging.getLogger(__name__)
    config = get_config()

    logger.info("Finding optimal time for meeting")
    logger.info(f"Duration: {duration} minutes")
    logger.info(f"Search period: {search_days} days")
    logger.info(f"Min attendees: {min_attendees}")
    logger.info(f"Attendees: {[a['email'] for a in attendees]}")

    # Query freebusy for all attendees
    search_start = datetime.now(timezone.utc)
    search_end = search_start + timedelta(days=search_days)

    print(f"\nQuerying calendar availability for {len(attendees)} attendees...")
    freebusy_data = await calendar_client.get_freebusy(
        email_addresses=[a['email'] for a in attendees],
        time_min=search_start,
        time_max=search_end
    )

    # Build timezone mapping
    user_timezones = {a['email']: a['timezone'] for a in attendees}

    # Find optimal time
    print("Finding optimal time slot...")
    result = SchedulingEngine.find_optimal_time(
        attendee_emails=[a['email'] for a in attendees],
        duration_minutes=duration,
        search_start=search_start,
        search_days=search_days,
        business_start=config.get_business_hours_start(),
        business_end=config.get_business_hours_end(),
        freebusy_data=freebusy_data,
        user_timezones=user_timezones,
        min_attendees=min_attendees,
        reference_timezone=reference_timezone
    )

    if not result:
        logger.error(
            f"No suitable time found with {min_attendees}+ attendees in {search_days} days"
        )
        print("\n✗ Could not find a time when enough people are available")
        print("  Try:")
        print("    - Reducing minimum attendees (--min-attendees)")
        print("    - Extending search period (--search-days)")
        print("    - Adjusting business hours in .env")
        sys.exit(1)

    optimal_slot, availability, score = result
    num_available = sum(1 for avail in availability.values() if avail)

    print(f"\n✓ Found optimal time slot!")
    print(f"  Score: {score}")
    print(f"  Available: {num_available}/{len(attendees)} attendees")

    # Show time in each attendee's timezone
    print("\nMeeting time for each attendee:")
    for attendee in attendees:
        local_time = TimezoneHandler.convert_to_timezone(optimal_slot, attendee['timezone'])
        formatted = TimezoneHandler.format_for_user(optimal_slot, attendee['timezone'])
        is_available = availability.get(attendee['email'], False)
        status = "✓" if is_available else "✗"
        print(f"  {status} {attendee['email']: <30} {formatted}")

    if dry_run:
        print("\n[DRY RUN] Would create calendar event (use --execute to actually create)")
        return

    # Create calendar event
    print("\nCreating calendar event...")
    start_time = optimal_slot
    end_time = start_time + timedelta(minutes=duration)

    event = await calendar_client.create_event(
        summary="Test Meeting (CLI)",
        start_time=start_time,
        end_time=end_time,
        attendee_emails=[a['email'] for a in attendees],
        description="Meeting scheduled via CLI test tool"
    )

    # Extract links
    meet_link = calendar_client.get_meet_link(event)
    event_link = calendar_client.get_event_link(event)

    print("\n✓ Meeting scheduled successfully!")
    print(f"  Event ID: {event.get('id')}")
    if meet_link:
        print(f"  Google Meet: {meet_link}")
    if event_link:
        print(f"  Calendar Event: {event_link}")


async def main_async():
    """Main async entry point."""
    parser = argparse.ArgumentParser(
        description="Test meeting scheduling without Slack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Schedule at a specific time (dry run)
  python -m src.cli schedule \\
    --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \\
    --time "tomorrow 2pm" \\
    --duration 30 \\
    --timezone "America/New_York"

  # Find optimal time (dry run)
  python -m src.cli find \\
    --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \\
    --duration 60 \\
    --search-days 7 \\
    --min-attendees 2

  # Actually create the event (not a dry run)
  python -m src.cli schedule \\
    --attendees "alice@example.com:America/New_York" \\
    --time "tomorrow 3pm" \\
    --timezone "America/New_York" \\
    --execute
        """
    )

    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')

    subparsers = parser.add_subparsers(dest='command', help='Command to run', required=True)

    # Schedule command (specific time)
    schedule_parser = subparsers.add_parser('schedule', help='Schedule at specific time')
    schedule_parser.add_argument(
        '--attendees', required=True,
        help='Comma-separated list of email:timezone pairs (e.g., alice@example.com:America/New_York,bob@example.com:UTC)'
    )
    schedule_parser.add_argument(
        '--time', required=True,
        help='Meeting time in natural language (e.g., "tomorrow 2pm", "Jan 20 at 3:30pm")'
    )
    schedule_parser.add_argument(
        '--timezone', default='UTC',
        help='Timezone for interpreting the time (default: UTC)'
    )
    schedule_parser.add_argument(
        '--duration', type=int, default=30,
        help='Meeting duration in minutes (default: 30)'
    )
    schedule_parser.add_argument(
        '--execute', dest='dry_run', action='store_false', default=True,
        help='Actually create the calendar event (default: dry run)'
    )

    # Find command (optimal time)
    find_parser = subparsers.add_parser('find', help='Find optimal time')
    find_parser.add_argument(
        '--attendees', required=True,
        help='Comma-separated list of email:timezone pairs (e.g., alice@example.com:America/New_York,bob@example.com:UTC)'
    )
    find_parser.add_argument(
        '--duration', type=int, default=30,
        help='Meeting duration in minutes (default: 30)'
    )
    find_parser.add_argument(
        '--search-days', type=int, default=14,
        help='Number of days ahead to search (default: 14)'
    )
    find_parser.add_argument(
        '--min-attendees', type=int, default=1,
        help='Minimum attendees required (default: 1)'
    )
    find_parser.add_argument(
        '--timezone', default='UTC',
        help='Reference timezone for business hours (default: UTC)'
    )
    find_parser.add_argument(
        '--execute', dest='dry_run', action='store_false', default=True,
        help='Actually create the calendar event (default: dry run)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Load config
    try:
        config = get_config()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("Make sure you have a .env file with required environment variables.")
        print("Note: SLACK_BOT_TOKEN and SLACK_APP_TOKEN are not needed for CLI mode.")
        sys.exit(1)

    # Initialize Google Calendar client
    try:
        service_account_json = config.get_service_account_credentials()
        google_auth = GoogleAuth(service_account_json)
        calendar_client = GoogleCalendarClient(google_auth)
        logger.info("Google Calendar client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Google Calendar client: {e}", exc_info=True)
        print(f"\nError: Could not initialize Google Calendar client")
        print(f"  {e}")
        print("\nMake sure:")
        print("  - GOOGLE_SERVICE_ACCOUNT_PATH is set in .env")
        print("  - The service account JSON file exists and is valid")
        print("  - Calendar API is enabled in Google Cloud Console")
        sys.exit(1)

    # Parse attendees
    attendees = parse_attendees(args.attendees)
    logger.info(f"Parsed {len(attendees)} attendees")

    # Execute command
    try:
        if args.command == 'schedule':
            await schedule_specific_time(
                calendar_client=calendar_client,
                attendees=attendees,
                specific_time=args.time,
                duration=args.duration,
                reference_timezone=args.timezone,
                dry_run=args.dry_run
            )
        elif args.command == 'find':
            await find_optimal_time(
                calendar_client=calendar_client,
                attendees=attendees,
                duration=args.duration,
                search_days=args.search_days,
                min_attendees=args.min_attendees,
                reference_timezone=args.timezone,
                dry_run=args.dry_run
            )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        sys.exit(1)


def main():
    """Synchronous entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
