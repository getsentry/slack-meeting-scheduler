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
    """Return a sample datetime in UTC (next weekday at 10:00 AM UTC)."""
    now = datetime.now(pytz.UTC)
    # Start with tomorrow at 10:00 AM
    future_date = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Skip to next weekday if it's a weekend
    while future_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        future_date += timedelta(days=1)

    return future_date


@pytest.fixture
def sample_datetime_pacific(pacific_tz):
    """Return a sample datetime in Pacific timezone (next weekday at 10:00 AM PST/PDT)."""
    now = datetime.now(pacific_tz)
    # Start with tomorrow at 10:00 AM
    future_date = now.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)

    # Skip to next weekday if it's a weekend
    while future_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
        future_date += timedelta(days=1)

    return future_date


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
