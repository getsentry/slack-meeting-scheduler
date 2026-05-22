"""Timezone handling utilities."""

import logging
from datetime import datetime, time
from typing import Optional

import pytz

logger = logging.getLogger(__name__)


class TimezoneHandler:
    """Handles timezone conversions and business hours checking."""

    @staticmethod
    def convert_to_utc(dt: datetime) -> datetime:
        """Convert datetime to UTC.

        Args:
            dt: Timezone-aware datetime

        Returns:
            Datetime in UTC

        Raises:
            ValueError: If datetime is naive (no timezone info)
        """
        if dt.tzinfo is None:
            raise ValueError("Cannot convert naive datetime to UTC")

        return dt.astimezone(pytz.UTC)

    @staticmethod
    def convert_to_timezone(dt: datetime, target_tz: str) -> datetime:
        """Convert datetime to target timezone.

        Args:
            dt: Timezone-aware datetime
            target_tz: Target timezone string (e.g., "America/Los_Angeles")

        Returns:
            Datetime in target timezone

        Raises:
            ValueError: If datetime is naive or timezone is invalid
        """
        if dt.tzinfo is None:
            raise ValueError("Cannot convert naive datetime")

        try:
            target_timezone = pytz.timezone(target_tz)
            return dt.astimezone(target_timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {target_tz}")

    @staticmethod
    def is_within_business_hours(
        dt: datetime,
        business_start: time,
        business_end: time,
        timezone: Optional[str] = None,
    ) -> bool:
        """Check if datetime falls within business hours.

        Args:
            dt: Datetime to check (should be timezone-aware)
            business_start: Business hours start time
            business_end: Business hours end time
            timezone: If provided, convert dt to this timezone first

        Returns:
            True if datetime is within business hours
        """
        if dt.tzinfo is None:
            raise ValueError("Cannot check business hours for naive datetime")

        # Convert to target timezone if specified
        if timezone:
            dt = TimezoneHandler.convert_to_timezone(dt, timezone)

        # Extract time component
        dt_time = dt.time()

        # Check if within business hours
        is_within = business_start <= dt_time <= business_end

        logger.debug(
            f"Checking business hours for {dt.isoformat()}: "
            f"{business_start} <= {dt_time} <= {business_end} = {is_within}"
        )

        return is_within

    @staticmethod
    def is_weekend(dt: datetime) -> bool:
        """Check if datetime falls on a weekend.

        Args:
            dt: Datetime to check

        Returns:
            True if Saturday (5) or Sunday (6)
        """
        return dt.weekday() >= 5

    @staticmethod
    def is_business_day(
        dt: datetime,
        business_start: time,
        business_end: time,
        timezone: Optional[str] = None,
    ) -> bool:
        """Check if datetime is on a business day and within business hours.

        Args:
            dt: Datetime to check
            business_start: Business hours start time
            business_end: Business hours end time
            timezone: If provided, convert dt to this timezone first

        Returns:
            True if it's a weekday within business hours
        """
        # Convert to target timezone if specified
        check_dt = dt
        if timezone:
            check_dt = TimezoneHandler.convert_to_timezone(dt, timezone)

        # Check if weekend
        if TimezoneHandler.is_weekend(check_dt):
            return False

        # Check if within business hours
        return TimezoneHandler.is_within_business_hours(
            check_dt,
            business_start,
            business_end,
            timezone=None,  # Already converted
        )

    @staticmethod
    def format_for_user(dt: datetime, user_tz: str) -> str:
        """Format datetime for display to user in their timezone.

        Args:
            dt: Datetime to format (UTC or timezone-aware)
            user_tz: User's timezone string

        Returns:
            Formatted string like "Jan 20, 2026 at 2:00 PM PST"
        """
        try:
            # Convert to user's timezone
            user_dt = TimezoneHandler.convert_to_timezone(dt, user_tz)

            # Format the datetime
            formatted = user_dt.strftime("%b %d, %Y at %I:%M %p %Z")

            return formatted
        except Exception as e:
            logger.error(f"Error formatting datetime for user: {e}")
            # Fallback to ISO format
            return dt.isoformat()

    @staticmethod
    def get_timezone_offset_hours(timezone_str: str) -> float:
        """Get the UTC offset in hours for a timezone.

        Args:
            timezone_str: Timezone string (e.g., "America/Los_Angeles")

        Returns:
            Offset in hours (e.g., -8.0 for PST)
        """
        try:
            timezone = pytz.timezone(timezone_str)
            now = datetime.now(timezone)
            offset_seconds = now.utcoffset().total_seconds()
            return offset_seconds / 3600
        except Exception as e:
            logger.error(f"Error getting timezone offset for {timezone_str}: {e}")
            return 0.0

    @staticmethod
    def validate_timezone(timezone_str: str) -> bool:
        """Validate that a timezone string is valid.

        Args:
            timezone_str: Timezone string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False

    @staticmethod
    def get_common_timezones() -> list[str]:
        """Get list of common timezones.

        Returns:
            List of common timezone strings
        """
        return pytz.common_timezones
