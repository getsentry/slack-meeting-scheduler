"""Tests for TimezoneHandler."""

import pytest
from datetime import datetime
import pytz

from src.scheduling.timezone_handler import TimezoneHandler


class TestTimezoneHandler:
    """Tests for TimezoneHandler."""

    def test_convert_to_utc(self):
        """Test converting datetime to UTC."""
        # Use a fixed date in PST season (January)
        pacific_tz = pytz.timezone("America/Los_Angeles")
        pacific_dt = pacific_tz.localize(datetime(2026, 1, 15, 10, 0, 0))

        utc_dt = TimezoneHandler.convert_to_utc(pacific_dt)

        assert utc_dt.tzinfo == pytz.UTC
        # Pacific Time (PST) is UTC-8, so 10:00 PST = 18:00 UTC
        assert utc_dt.hour == 18

    def test_convert_to_utc_already_utc(self, sample_datetime_utc):
        """Test converting UTC datetime to UTC (should be unchanged)."""
        utc_dt = TimezoneHandler.convert_to_utc(sample_datetime_utc)

        assert utc_dt.tzinfo == pytz.UTC
        assert utc_dt == sample_datetime_utc

    def test_convert_to_utc_naive_raises_error(self):
        """Test converting naive datetime raises ValueError."""
        naive_dt = datetime(2026, 1, 15, 10, 0, 0)

        with pytest.raises(ValueError, match="Cannot convert naive datetime to UTC"):
            TimezoneHandler.convert_to_utc(naive_dt)

    def test_convert_to_timezone(self):
        """Test converting to target timezone."""
        # Use a fixed date in PST season (January)
        utc_dt = datetime(2026, 1, 15, 10, 0, 0, tzinfo=pytz.UTC)

        pacific_dt = TimezoneHandler.convert_to_timezone(utc_dt, "America/Los_Angeles")

        assert pacific_dt.tzinfo.zone == "America/Los_Angeles"
        # 10:00 UTC = 02:00 PST (UTC-8)
        assert pacific_dt.hour == 2

    def test_convert_to_timezone_invalid_raises_error(self, sample_datetime_utc):
        """Test converting to invalid timezone raises ValueError."""
        with pytest.raises(ValueError, match="Unknown timezone"):
            TimezoneHandler.convert_to_timezone(sample_datetime_utc, "Invalid/Timezone")

    def test_convert_to_timezone_naive_raises_error(self):
        """Test converting naive datetime raises ValueError."""
        naive_dt = datetime(2026, 1, 15, 10, 0, 0)

        with pytest.raises(ValueError, match="Cannot convert naive datetime"):
            TimezoneHandler.convert_to_timezone(naive_dt, "America/Los_Angeles")

    def test_is_within_business_hours_true(self, business_hours):
        """Test datetime within business hours."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # 10 AM on a weekday
        dt = pacific_tz.localize(datetime(2026, 1, 15, 10, 0, 0))  # Wednesday

        result = TimezoneHandler.is_within_business_hours(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is True

    def test_is_within_business_hours_false_before(self, business_hours):
        """Test datetime before business hours."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # 8 AM (before 9 AM start)
        dt = pacific_tz.localize(datetime(2026, 1, 15, 8, 0, 0))

        result = TimezoneHandler.is_within_business_hours(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is False

    def test_is_within_business_hours_false_after(self, business_hours):
        """Test datetime after business hours."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # 6 PM (after 5 PM end)
        dt = pacific_tz.localize(datetime(2026, 1, 15, 18, 0, 0))

        result = TimezoneHandler.is_within_business_hours(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is False

    def test_is_within_business_hours_at_boundary(self, business_hours):
        """Test datetime at business hours boundaries."""
        pacific_tz = pytz.timezone("America/Los_Angeles")

        # Exactly 9 AM (start)
        dt_start = pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0))
        assert (
            TimezoneHandler.is_within_business_hours(
                dt_start, business_hours["start"], business_hours["end"]
            )
            is True
        )

        # Exactly 5 PM (end)
        dt_end = pacific_tz.localize(datetime(2026, 1, 15, 17, 0, 0))
        assert (
            TimezoneHandler.is_within_business_hours(
                dt_end, business_hours["start"], business_hours["end"]
            )
            is True
        )

    def test_is_within_business_hours_with_timezone_conversion(
        self, sample_datetime_utc, business_hours
    ):
        """Test business hours check with timezone conversion."""
        # 10:00 UTC = 02:00 PST (outside business hours)
        result = TimezoneHandler.is_within_business_hours(
            sample_datetime_utc,
            business_hours["start"],
            business_hours["end"],
            timezone="America/Los_Angeles",
        )

        assert result is False

    def test_is_weekend_saturday(self):
        """Test weekend detection for Saturday."""
        saturday = datetime(2026, 1, 17, 10, 0, 0, tzinfo=pytz.UTC)  # Saturday

        assert TimezoneHandler.is_weekend(saturday) is True

    def test_is_weekend_sunday(self):
        """Test weekend detection for Sunday."""
        sunday = datetime(2026, 1, 18, 10, 0, 0, tzinfo=pytz.UTC)  # Sunday

        assert TimezoneHandler.is_weekend(sunday) is True

    def test_is_weekend_weekday(self):
        """Test weekend detection for weekday."""
        wednesday = datetime(2026, 1, 15, 10, 0, 0, tzinfo=pytz.UTC)  # Wednesday

        assert TimezoneHandler.is_weekend(wednesday) is False

    def test_is_business_day_weekday_within_hours(self, business_hours):
        """Test business day check for weekday within hours."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # Wednesday 10 AM
        dt = pacific_tz.localize(datetime(2026, 1, 15, 10, 0, 0))

        result = TimezoneHandler.is_business_day(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is True

    def test_is_business_day_weekend(self, business_hours):
        """Test business day check for weekend."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # Saturday 10 AM
        dt = pacific_tz.localize(datetime(2026, 1, 17, 10, 0, 0))

        result = TimezoneHandler.is_business_day(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is False

    def test_is_business_day_weekday_outside_hours(self, business_hours):
        """Test business day check for weekday outside hours."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # Wednesday 8 AM (before business hours)
        dt = pacific_tz.localize(datetime(2026, 1, 15, 8, 0, 0))

        result = TimezoneHandler.is_business_day(
            dt, business_hours["start"], business_hours["end"]
        )

        assert result is False

    def test_format_for_user(self, sample_datetime_utc):
        """Test formatting datetime for user."""
        formatted = TimezoneHandler.format_for_user(
            sample_datetime_utc, "America/Los_Angeles"
        )

        # Check that it contains a date (don't hardcode the specific date)
        assert "2026" in formatted
        assert "AM" in formatted or "PM" in formatted
        assert "PST" in formatted or "PDT" in formatted

    def test_format_for_user_different_timezone(self, sample_datetime_utc):
        """Test formatting for different timezones."""
        pacific_formatted = TimezoneHandler.format_for_user(
            sample_datetime_utc, "America/Los_Angeles"
        )
        eastern_formatted = TimezoneHandler.format_for_user(
            sample_datetime_utc, "America/New_York"
        )

        # Different times for different timezones
        assert pacific_formatted != eastern_formatted

    def test_get_timezone_offset_hours_pacific(self):
        """Test getting timezone offset for Pacific."""
        offset = TimezoneHandler.get_timezone_offset_hours("America/Los_Angeles")

        # PST is UTC-8, PDT is UTC-7
        assert offset in [-8.0, -7.0]

    def test_get_timezone_offset_hours_utc(self):
        """Test getting timezone offset for UTC."""
        offset = TimezoneHandler.get_timezone_offset_hours("UTC")

        assert offset == 0.0

    def test_get_timezone_offset_hours_invalid(self):
        """Test getting timezone offset for invalid timezone."""
        offset = TimezoneHandler.get_timezone_offset_hours("Invalid/Timezone")

        # Should return 0.0 on error
        assert offset == 0.0

    def test_validate_timezone_valid(self):
        """Test validating valid timezone."""
        assert TimezoneHandler.validate_timezone("America/Los_Angeles") is True
        assert TimezoneHandler.validate_timezone("America/New_York") is True
        assert TimezoneHandler.validate_timezone("UTC") is True

    def test_validate_timezone_invalid(self):
        """Test validating invalid timezone."""
        assert TimezoneHandler.validate_timezone("Invalid/Timezone") is False
        assert TimezoneHandler.validate_timezone("Not/Real") is False

    def test_get_common_timezones(self):
        """Test getting common timezones list."""
        timezones = TimezoneHandler.get_common_timezones()

        assert isinstance(timezones, list)
        assert len(timezones) > 0
        assert "America/Los_Angeles" in timezones
        assert "America/New_York" in timezones
        assert "UTC" in timezones

    def test_convert_between_timezones(self):
        """Test converting between multiple timezones."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        eastern_tz = pytz.timezone("America/New_York")

        # Start with Pacific time
        pacific_dt = pacific_tz.localize(datetime(2026, 1, 15, 10, 0, 0))

        # Convert to UTC
        utc_dt = TimezoneHandler.convert_to_utc(pacific_dt)

        # Convert to Eastern
        eastern_dt = TimezoneHandler.convert_to_timezone(utc_dt, "America/New_York")

        # Pacific 10 AM = Eastern 1 PM (3 hour difference)
        assert eastern_dt.hour == 13
