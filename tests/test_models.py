"""Tests for data models."""

import pytest
from datetime import datetime, timedelta
import pytz

from src.models import TimeSlot, SchedulingMode, MeetingRequest


class TestTimeSlot:
    """Tests for TimeSlot model."""

    def test_overlaps_full_overlap(self, sample_datetime_utc):
        """Test overlapping time slots."""
        slot1 = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        slot2 = TimeSlot(
            start=sample_datetime_utc + timedelta(minutes=30),
            end=sample_datetime_utc + timedelta(hours=1, minutes=30)
        )
        assert slot1.overlaps(slot2)
        assert slot2.overlaps(slot1)

    def test_overlaps_no_overlap(self, sample_datetime_utc):
        """Test non-overlapping time slots."""
        slot1 = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        slot2 = TimeSlot(
            start=sample_datetime_utc + timedelta(hours=2),
            end=sample_datetime_utc + timedelta(hours=3)
        )
        assert not slot1.overlaps(slot2)
        assert not slot2.overlaps(slot1)

    def test_overlaps_adjacent(self, sample_datetime_utc):
        """Test adjacent time slots (should not overlap)."""
        slot1 = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        slot2 = TimeSlot(
            start=sample_datetime_utc + timedelta(hours=1),
            end=sample_datetime_utc + timedelta(hours=2)
        )
        assert not slot1.overlaps(slot2)
        assert not slot2.overlaps(slot1)

    def test_overlaps_containment(self, sample_datetime_utc):
        """Test when one slot contains another."""
        slot1 = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=2)
        )
        slot2 = TimeSlot(
            start=sample_datetime_utc + timedelta(minutes=30),
            end=sample_datetime_utc + timedelta(hours=1)
        )
        assert slot1.overlaps(slot2)
        assert slot2.overlaps(slot1)

    def test_contains_datetime_inside(self, sample_datetime_utc):
        """Test datetime within time slot."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        dt = sample_datetime_utc + timedelta(minutes=30)
        assert slot.contains(dt)

    def test_contains_datetime_outside(self, sample_datetime_utc):
        """Test datetime outside time slot."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        dt = sample_datetime_utc + timedelta(hours=2)
        assert not slot.contains(dt)

    def test_contains_datetime_at_start(self, sample_datetime_utc):
        """Test datetime at start boundary."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        assert slot.contains(sample_datetime_utc)

    def test_contains_datetime_at_end(self, sample_datetime_utc):
        """Test datetime at end boundary (should not contain)."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        dt = sample_datetime_utc + timedelta(hours=1)
        assert not slot.contains(dt)

    def test_duration_minutes(self, sample_datetime_utc):
        """Test duration calculation."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1, minutes=30)
        )
        assert slot.duration_minutes() == 90

    def test_str_representation(self, sample_datetime_utc):
        """Test string representation."""
        slot = TimeSlot(
            start=sample_datetime_utc,
            end=sample_datetime_utc + timedelta(hours=1)
        )
        str_repr = str(slot)
        assert sample_datetime_utc.isoformat() in str_repr


class TestSchedulingMode:
    """Tests for SchedulingMode enum."""

    def test_specific_time_value(self):
        """Test SPECIFIC_TIME enum value."""
        assert SchedulingMode.SPECIFIC_TIME.value == "specific_time"

    def test_find_availability_value(self):
        """Test FIND_AVAILABILITY enum value."""
        assert SchedulingMode.FIND_AVAILABILITY.value == "find_availability"

    def test_str_representation(self):
        """Test string representation."""
        assert str(SchedulingMode.SPECIFIC_TIME) == "specific_time"
        assert str(SchedulingMode.FIND_AVAILABILITY) == "find_availability"


class TestMeetingRequest:
    """Tests for MeetingRequest model."""

    def test_creation_with_defaults(self, sample_datetime_utc):
        """Test creating MeetingRequest with default values."""
        request = MeetingRequest(
            request_id="test-123",
            channel_id="C12345",
            message_ts="1234567890.123456",
            initiator_user_id="U12345",
            reaction_duration_seconds=300,
            scheduling_mode=SchedulingMode.SPECIFIC_TIME,
            duration_minutes=30,
            min_reactions=1,
            created_at=sample_datetime_utc
        )
        assert request.request_id == "test-123"
        assert request.participants == []
        assert request.specific_datetime is None

    def test_creation_with_participants(self, sample_datetime_utc):
        """Test creating MeetingRequest with participants."""
        participants = ["user1@example.com", "user2@example.com"]
        request = MeetingRequest(
            request_id="test-123",
            channel_id="C12345",
            message_ts="1234567890.123456",
            initiator_user_id="U12345",
            reaction_duration_seconds=300,
            scheduling_mode=SchedulingMode.FIND_AVAILABILITY,
            duration_minutes=60,
            min_reactions=2,
            created_at=sample_datetime_utc,
            participants=participants
        )
        assert len(request.participants) == 2
        assert "user1@example.com" in request.participants

    def test_creation_with_specific_datetime(self, sample_datetime_utc):
        """Test creating MeetingRequest with specific datetime."""
        specific_time = sample_datetime_utc + timedelta(days=1)
        request = MeetingRequest(
            request_id="test-123",
            channel_id="C12345",
            message_ts="1234567890.123456",
            initiator_user_id="U12345",
            reaction_duration_seconds=300,
            scheduling_mode=SchedulingMode.SPECIFIC_TIME,
            duration_minutes=30,
            min_reactions=1,
            created_at=sample_datetime_utc,
            specific_datetime=specific_time
        )
        assert request.specific_datetime == specific_time

    def test_str_representation_specific_time(self, sample_datetime_utc):
        """Test string representation for specific time mode."""
        request = MeetingRequest(
            request_id="test-123",
            channel_id="C12345",
            message_ts="1234567890.123456",
            initiator_user_id="U12345",
            reaction_duration_seconds=300,
            scheduling_mode=SchedulingMode.SPECIFIC_TIME,
            duration_minutes=30,
            min_reactions=1,
            created_at=sample_datetime_utc,
            participants=["user1@example.com", "user2@example.com"]
        )
        str_repr = str(request)
        assert "test-123" in str_repr
        assert "specific time" in str_repr
        assert "2" in str_repr  # participant count
        assert "30m" in str_repr

    def test_str_representation_find_availability(self, sample_datetime_utc):
        """Test string representation for find availability mode."""
        request = MeetingRequest(
            request_id="test-456",
            channel_id="C12345",
            message_ts="1234567890.123456",
            initiator_user_id="U12345",
            reaction_duration_seconds=600,
            scheduling_mode=SchedulingMode.FIND_AVAILABILITY,
            duration_minutes=45,
            min_reactions=3,
            created_at=sample_datetime_utc,
            participants=["user1@example.com"]
        )
        str_repr = str(request)
        assert "test-456" in str_repr
        assert "find availability" in str_repr
        assert "45m" in str_repr
