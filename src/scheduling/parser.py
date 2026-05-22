"""Natural language date/time parsing."""

import logging
from datetime import datetime
from typing import Optional

import dateparser
import pytz

logger = logging.getLogger(__name__)


class DateTimeParser:
    """Parser for natural language date/time strings."""

    @staticmethod
    def parse(
        text: str, timezone: str = "UTC", prefer_dates_from: str = "future"
    ) -> Optional[datetime]:
        """Parse natural language date/time text.

        Args:
            text: Natural language date/time string
                 Examples: "tomorrow 2pm", "next Monday 10am", "Jan 20 at 3:30pm"
            timezone: Timezone string (e.g., "America/Los_Angeles")
            prefer_dates_from: Whether to prefer past or future dates (default: "future")

        Returns:
            Timezone-aware datetime object or None if parsing fails
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for date parsing")
            return None

        try:
            # Preprocess text to handle dateparser limitations
            processed_text = text.strip()

            # Skip preprocessing for ISO format strings (e.g., "2026-01-20T15:00:00-08:00")
            # ISO formats contain YYYY-MM-DD pattern
            is_iso_format = (
                len(processed_text) > 10
                and processed_text[4] == "-"
                and processed_text[7] == "-"
            )

            if not is_iso_format:
                # Handle time-only inputs (e.g., "2pm", "3:30pm")
                # If text looks like just a time, prepend "today"
                if processed_text and not any(
                    word in processed_text.lower()
                    for word in [
                        "today",
                        "tomorrow",
                        "yesterday",
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                        "jan",
                        "feb",
                        "mar",
                        "apr",
                        "may",
                        "jun",
                        "jul",
                        "aug",
                        "sep",
                        "oct",
                        "nov",
                        "dec",
                        "next",
                        "last",
                        "this",
                    ]
                ):
                    # Check if it contains time indicators (am/pm or colon)
                    if (
                        "am" in processed_text.lower()
                        or "pm" in processed_text.lower()
                        or ":" in processed_text
                    ):
                        processed_text = f"today {processed_text}"
                        logger.debug(
                            f"Prepended 'today' to time-only input: {processed_text}"
                        )

                # Handle "next <day>" by removing "next" (dateparser handles days better without it)
                # Only strip when followed by a day name to avoid corrupting
                # "next week Tuesday 2pm" or "next month 15th at 3pm"
                _day_names = (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
                if processed_text.lower().startswith("next "):
                    rest = processed_text[5:].strip().lower()
                    if any(rest.startswith(day) for day in _day_names):
                        processed_text = processed_text[5:]
                        logger.debug(f"Removed 'next' prefix: {processed_text}")

            # Configure dateparser settings
            settings = {
                "TIMEZONE": timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": prefer_dates_from,
                "RELATIVE_BASE": datetime.now(pytz.timezone(timezone)).replace(
                    tzinfo=None
                ),
            }

            logger.debug(
                f"Parsing '{processed_text}' (original: '{text}') with timezone {timezone}"
            )

            # Parse the date/time
            parsed_dt = dateparser.parse(processed_text, settings=settings)

            if parsed_dt is None:
                logger.warning(f"Failed to parse date/time from: {text}")
                return None

            # Ensure it's timezone-aware
            if parsed_dt.tzinfo is None:
                logger.debug("Parsed datetime is naive, adding timezone")
                tz = pytz.timezone(timezone)
                parsed_dt = tz.localize(parsed_dt)

            logger.info(f"Successfully parsed '{text}' to {parsed_dt.isoformat()}")
            return parsed_dt

        except Exception as e:
            logger.error(f"Error parsing date/time '{text}': {e}", exc_info=True)
            return None

    @staticmethod
    def parse_with_fallback(text: str, timezone: str = "UTC") -> Optional[datetime]:
        """Parse with multiple strategies for better success rate.

        Tries multiple parsing approaches:
        1. Standard parsing with future preference
        2. Parsing with past preference (for "yesterday", etc.)
        3. ISO format parsing

        Args:
            text: Natural language date/time string
            timezone: Timezone string

        Returns:
            Timezone-aware datetime object or None if all strategies fail
        """
        # Try future preference first
        result = DateTimeParser.parse(text, timezone, prefer_dates_from="future")
        if result:
            return result

        # Try past preference
        result = DateTimeParser.parse(text, timezone, prefer_dates_from="past")
        if result:
            return result

        # Try ISO format parsing
        try:
            tz = pytz.timezone(timezone)
            # Try parsing as ISO format
            parsed_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            # Convert to target timezone
            if parsed_dt.tzinfo:
                parsed_dt = parsed_dt.astimezone(tz)
            else:
                parsed_dt = tz.localize(parsed_dt)
            logger.info(f"Parsed ISO format: {parsed_dt.isoformat()}")
            return parsed_dt
        except Exception:
            pass

        logger.warning(f"All parsing strategies failed for: {text}")
        return None

    @staticmethod
    def validate_future_datetime(dt: datetime, min_minutes_ahead: int = 5) -> bool:
        """Validate that datetime is in the future.

        Args:
            dt: Datetime to validate
            min_minutes_ahead: Minimum minutes in the future required

        Returns:
            True if datetime is sufficiently in the future
        """
        if dt.tzinfo is None:
            logger.error("Cannot validate naive datetime")
            return False

        now = datetime.now(dt.tzinfo)
        time_diff = (dt - now).total_seconds() / 60  # Convert to minutes

        is_valid = time_diff >= min_minutes_ahead
        if not is_valid:
            logger.warning(
                f"Datetime {dt.isoformat()} is not far enough in the future "
                f"({time_diff:.1f} minutes ahead, need {min_minutes_ahead})"
            )

        return is_valid
