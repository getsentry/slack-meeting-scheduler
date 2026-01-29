"""Command parser for meeting scheduler commands."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models import SchedulingMode

logger = logging.getLogger(__name__)


@dataclass
class CommandParameters:
    """Parsed command parameters."""

    reaction_duration_seconds: int
    scheduling_mode: SchedulingMode
    specific_datetime_text: Optional[str] = None
    duration_minutes: Optional[int] = None
    min_reactions: Optional[int] = None


class CommandParser:
    """Parser for slash command and mention text."""

    # Regex patterns
    DURATION_PATTERN = r'^(\d+)([smh])(?:\s+|$)'  # e.g., "5m", "1h", "30s"
    FIND_TIME_PATTERN = r'\bfind-?time\b'
    DURATION_PARAM_PATTERN = r'\bduration:(\d+)m?\b'
    MIN_PARAM_PATTERN = r'\bmin:(\d+)\b'

    @classmethod
    def parse(cls, command_text: str, default_duration: int = 30, default_min: int = 1) -> CommandParameters:
        """Parse command text into structured parameters.

        Command format:
            [reaction-time] [mode] [options]

        Examples:
            - "5m tomorrow 2pm"
            - "1h find-time duration:60m"
            - "30m Jan 20 at 3:30pm min:3"

        Args:
            command_text: The command text to parse
            default_duration: Default meeting duration in minutes
            default_min: Default minimum reactions

        Returns:
            CommandParameters with parsed values

        Raises:
            ValueError: If command format is invalid
        """
        if not command_text or not command_text.strip():
            raise ValueError("Command text cannot be empty")

        text = command_text.strip()
        logger.debug(f"Parsing command: {text}")

        # 1. Extract reaction duration (required)
        duration_match = re.match(cls.DURATION_PATTERN, text, re.IGNORECASE)
        if not duration_match:
            raise ValueError(
                "Missing reaction duration. Command must start with duration like '5m', '1h', or '30s'\n"
                "Example: /schedule-meet 5m tomorrow 2pm"
            )

        value = int(duration_match.group(1))
        unit = duration_match.group(2).lower()

        # Convert to seconds
        if unit == 's':
            reaction_duration_seconds = value
        elif unit == 'm':
            reaction_duration_seconds = value * 60
        elif unit == 'h':
            reaction_duration_seconds = value * 3600
        else:
            raise ValueError(f"Invalid duration unit: {unit}")

        # Remove the reaction duration from the text
        text = text[duration_match.end():].strip()

        # 2. Check for find-time mode
        find_time_match = re.search(cls.FIND_TIME_PATTERN, text, re.IGNORECASE)
        if find_time_match:
            scheduling_mode = SchedulingMode.FIND_AVAILABILITY
            # Remove "find-time" from text
            text = text[:find_time_match.start()] + text[find_time_match.end():]
            text = text.strip()
            specific_datetime_text = None
        else:
            scheduling_mode = SchedulingMode.SPECIFIC_TIME
            # The rest is the datetime text
            specific_datetime_text = text

        # 3. Extract optional parameters
        duration_minutes = None
        duration_param_match = re.search(cls.DURATION_PARAM_PATTERN, text, re.IGNORECASE)
        if duration_param_match:
            duration_minutes = int(duration_param_match.group(1))
            # Remove from specific_datetime_text if it was set
            if specific_datetime_text:
                specific_datetime_text = specific_datetime_text.replace(duration_param_match.group(0), '').strip()

        min_reactions = None
        min_param_match = re.search(cls.MIN_PARAM_PATTERN, text, re.IGNORECASE)
        if min_param_match:
            min_reactions = int(min_param_match.group(1))
            # Remove from specific_datetime_text if it was set
            if specific_datetime_text:
                specific_datetime_text = specific_datetime_text.replace(min_param_match.group(0), '').strip()

        # Apply defaults
        if duration_minutes is None:
            duration_minutes = default_duration
        if min_reactions is None:
            min_reactions = default_min

        # Validate specific datetime text
        if scheduling_mode == SchedulingMode.SPECIFIC_TIME:
            if not specific_datetime_text:
                raise ValueError(
                    "Missing date/time for specific time scheduling.\n"
                    "Example: /schedule-meet 5m tomorrow 2pm\n"
                    "Or use 'find-time' to search for availability: /schedule-meet 5m find-time"
                )

        logger.info(
            f"Parsed command: reaction={reaction_duration_seconds}s, mode={scheduling_mode}, "
            f"duration={duration_minutes}m, min={min_reactions}"
        )

        return CommandParameters(
            reaction_duration_seconds=reaction_duration_seconds,
            scheduling_mode=scheduling_mode,
            specific_datetime_text=specific_datetime_text,
            duration_minutes=duration_minutes,
            min_reactions=min_reactions,
        )

    @classmethod
    def get_help_message(cls) -> str:
        """Get help message for command usage.

        Returns:
            Help message string
        """
        return """*Meeting Scheduler Help*

*Usage:*
`/schedule-meet [reaction-time] [mode] [options]`

*Reaction Time:* (required)
How long to collect reactions before scheduling
- Format: `5m`, `1h`, `30s` (minutes, hours, or seconds)

*Scheduling Modes:*

1. *Specific Time:* Schedule at a specific date/time
   Example: `/schedule-meet 5m tomorrow 2pm`
   Example: `/schedule-meet 1h Jan 20 at 3:30pm`

2. *Find Availability:* Find optimal time when most people are available
   Example: `/schedule-meet 5m find-time`
   Example: `/schedule-meet 1h find-time duration:60m`

*Optional Parameters:*
- `duration:Xm` - Meeting duration in minutes (default: 30)
- `min:N` - Minimum reactions required (default: 1)

*Full Examples:*
- `/schedule-meet 5m tomorrow 2pm` - Schedule for tomorrow at 2pm, collect reactions for 5 minutes
- `/schedule-meet 1h find-time min:3` - Find best time for 3+ people, collect reactions for 1 hour
- `/schedule-meet 30m next Monday 10am duration:60m` - 60-minute meeting next Monday at 10am
- `/schedule-meet 2h find-time duration:45m min:2` - Find 45-minute slot for 2+ people

You can also mention the bot: `@MeetingBot 5m tomorrow 3pm`
"""
