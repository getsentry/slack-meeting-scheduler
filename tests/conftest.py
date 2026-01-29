"""Shared pytest fixtures for tests."""

import pytest
from datetime import datetime, time, timedelta
import pytz


@pytest.fixture
def utc_now():
    """Return current datetime in UTC."""
    return datetime.now(pytz.UTC)


@pytest.fixture
def pacific_tz():
    """Return Pacific timezone."""
    return pytz.timezone("America/Los_Angeles")


@pytest.fixture
def eastern_tz():
    """Return Eastern timezone."""
    return pytz.timezone("America/New_York")


@pytest.fixture
def sample_datetime_utc():
    """Return a sample datetime in UTC (Jan 15, 2026 10:00 AM UTC)."""
    return datetime(2026, 1, 15, 10, 0, 0, tzinfo=pytz.UTC)


@pytest.fixture
def sample_datetime_pacific(pacific_tz):
    """Return a sample datetime in Pacific timezone (Jan 15, 2026 10:00 AM PST)."""
    return pacific_tz.localize(datetime(2026, 1, 15, 10, 0, 0))


@pytest.fixture
def business_hours():
    """Return standard business hours (9 AM - 5 PM)."""
    return {
        "start": time(9, 0),
        "end": time(17, 0)
    }


@pytest.fixture
def sample_user_timezones():
    """Return sample user timezone mapping."""
    return {
        "user1@example.com": "America/Los_Angeles",
        "user2@example.com": "America/New_York",
        "user3@example.com": "America/Chicago"
    }


@pytest.fixture
def sample_attendee_emails():
    """Return sample attendee email list."""
    return [
        "user1@example.com",
        "user2@example.com",
        "user3@example.com"
    ]
