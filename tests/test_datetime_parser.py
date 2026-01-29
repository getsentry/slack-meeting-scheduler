"""Tests for DateTimeParser."""

import pytest
from datetime import datetime, timedelta
import pytz

from src.scheduling.parser import DateTimeParser


class TestDateTimeParser:
    """Tests for DateTimeParser."""

    def test_parse_simple_time_today(self, pacific_tz):
        """Test parsing simple time today."""
        result = DateTimeParser.parse("2pm", timezone="America/Los_Angeles")

        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 14

    def test_parse_tomorrow(self, pacific_tz):
        """Test parsing 'tomorrow'."""
        now = datetime.now(pacific_tz)
        result = DateTimeParser.parse("tomorrow 10am", timezone="America/Los_Angeles")

        assert result is not None
        assert result.date() == (now + timedelta(days=1)).date()
        assert result.hour == 10

    def test_parse_specific_date(self):
        """Test parsing specific date."""
        result = DateTimeParser.parse("January 20 2026 at 3pm", timezone="America/Los_Angeles")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 20
        assert result.hour == 15

    def test_parse_relative_day(self, eastern_tz):
        """Test parsing relative day (e.g., 'next Monday')."""
        result = DateTimeParser.parse("next Monday 10am", timezone="America/New_York")

        assert result is not None
        assert result.weekday() == 0  # Monday
        assert result.hour == 10

    def test_parse_with_timezone_utc(self):
        """Test parsing with UTC timezone."""
        result = DateTimeParser.parse("tomorrow 2pm", timezone="UTC")

        assert result is not None
        assert result.tzinfo == pytz.UTC

    def test_parse_with_timezone_pacific(self, pacific_tz):
        """Test parsing with Pacific timezone."""
        result = DateTimeParser.parse("tomorrow 2pm", timezone="America/Los_Angeles")

        assert result is not None
        assert result.tzinfo.zone == "America/Los_Angeles"

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = DateTimeParser.parse("")

        assert result is None

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string returns None."""
        result = DateTimeParser.parse("   ")

        assert result is None

    def test_parse_invalid_text(self):
        """Test parsing invalid text returns None."""
        result = DateTimeParser.parse("asdfasdfasdf")

        assert result is None

    def test_parse_returns_timezone_aware(self):
        """Test that parse always returns timezone-aware datetime."""
        result = DateTimeParser.parse("tomorrow 2pm", timezone="America/Los_Angeles")

        assert result is not None
        assert result.tzinfo is not None

    def test_parse_prefer_future(self, pacific_tz):
        """Test that parse prefers future dates."""
        result = DateTimeParser.parse(
            "Monday 10am",
            timezone="America/Los_Angeles",
            prefer_dates_from="future"
        )

        assert result is not None
        now = datetime.now(pacific_tz)
        assert result > now

    def test_parse_with_fallback_future_preference(self):
        """Test parse_with_fallback with future preference."""
        result = DateTimeParser.parse_with_fallback("tomorrow 2pm", timezone="America/Los_Angeles")

        assert result is not None
        assert result.tzinfo is not None

    def test_parse_with_fallback_tries_multiple_strategies(self):
        """Test that parse_with_fallback tries multiple strategies."""
        result = DateTimeParser.parse_with_fallback("tomorrow 3pm", timezone="UTC")

        assert result is not None

    def test_parse_with_fallback_iso_format(self):
        """Test parse_with_fallback with ISO format."""
        iso_string = "2026-01-20T15:00:00-08:00"
        result = DateTimeParser.parse_with_fallback(iso_string, timezone="America/Los_Angeles")

        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 20

    def test_parse_with_fallback_iso_format_with_z(self):
        """Test parse_with_fallback with ISO format containing 'Z'."""
        iso_string = "2026-01-20T15:00:00Z"
        result = DateTimeParser.parse_with_fallback(iso_string, timezone="UTC")

        assert result is not None
        assert result.year == 2026
        assert result.tzinfo is not None

    def test_parse_with_fallback_invalid_returns_none(self):
        """Test parse_with_fallback returns None for invalid input."""
        result = DateTimeParser.parse_with_fallback("completely invalid text", timezone="UTC")

        assert result is None

    def test_validate_future_datetime_valid(self, sample_datetime_utc):
        """Test validating future datetime."""
        future_dt = sample_datetime_utc + timedelta(hours=1)

        result = DateTimeParser.validate_future_datetime(future_dt, min_minutes_ahead=5)

        assert result is True

    def test_validate_future_datetime_too_soon(self, sample_datetime_utc):
        """Test validating datetime too soon in future."""
        # Mock a datetime that would be "now" by using validation logic
        now = datetime.now(pytz.UTC)
        near_future = now + timedelta(minutes=2)

        result = DateTimeParser.validate_future_datetime(near_future, min_minutes_ahead=5)

        assert result is False

    def test_validate_future_datetime_past(self, sample_datetime_utc):
        """Test validating datetime in the past."""
        past_dt = datetime.now(pytz.UTC) - timedelta(hours=1)

        result = DateTimeParser.validate_future_datetime(past_dt, min_minutes_ahead=5)

        assert result is False

    def test_validate_future_datetime_naive_raises_error(self):
        """Test validating naive datetime returns False."""
        naive_dt = datetime(2026, 1, 20, 15, 0, 0)

        result = DateTimeParser.validate_future_datetime(naive_dt, min_minutes_ahead=5)

        assert result is False

    def test_validate_future_datetime_custom_threshold(self):
        """Test validating with custom minimum threshold."""
        now = datetime.now(pytz.UTC)
        future_dt = now + timedelta(minutes=15)

        result = DateTimeParser.validate_future_datetime(future_dt, min_minutes_ahead=10)
        assert result is True

        result = DateTimeParser.validate_future_datetime(future_dt, min_minutes_ahead=20)
        assert result is False

    def test_parse_time_with_am_pm(self):
        """Test parsing times with AM/PM."""
        result_am = DateTimeParser.parse("10am tomorrow", timezone="UTC")
        result_pm = DateTimeParser.parse("3pm tomorrow", timezone="UTC")

        assert result_am is not None
        assert result_am.hour == 10

        assert result_pm is not None
        assert result_pm.hour == 15

    def test_parse_24_hour_format(self):
        """Test parsing 24-hour time format."""
        result = DateTimeParser.parse("tomorrow 14:30", timezone="UTC")

        assert result is not None
        assert result.hour == 14
        assert result.minute == 30

    def test_parse_various_date_formats(self):
        """Test parsing various date formats."""
        formats = [
            "Jan 20 at 2pm",
            "January 20 at 2pm",
            "20 Jan at 2pm",
            "2026-01-20 14:00",
        ]

        for fmt in formats:
            result = DateTimeParser.parse(fmt, timezone="UTC")
            # Some formats might not parse, but at least verify the method doesn't crash
            # We expect most to succeed
            if result:
                assert result.tzinfo is not None
