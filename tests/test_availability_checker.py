"""Tests for AvailabilityChecker."""

import pytest
from datetime import datetime, timedelta
import pytz

from src.scheduling.availability import AvailabilityChecker
from src.models import TimeSlot


class TestAvailabilityChecker:
    """Tests for AvailabilityChecker."""

    def test_generate_candidate_slots_basic(self, sample_datetime_utc, business_hours):
        """Test generating basic candidate slots."""
        slots = AvailabilityChecker.generate_candidate_slots(
            start_date=sample_datetime_utc,
            num_days=1,
            duration_minutes=30,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            reference_timezone="America/Los_Angeles",
        )

        assert len(slots) > 0
        # Each slot should be in UTC
        for slot in slots:
            assert slot.tzinfo == pytz.UTC

    def test_generate_candidate_slots_skip_weekends(self, business_hours):
        """Test that weekends are skipped."""
        # Start on a Friday
        pacific_tz = pytz.timezone("America/Los_Angeles")
        friday = pacific_tz.localize(datetime(2026, 1, 16, 9, 0, 0))  # Friday Jan 16

        slots = AvailabilityChecker.generate_candidate_slots(
            start_date=friday,
            num_days=5,  # Friday through Tuesday
            duration_minutes=30,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            reference_timezone="America/Los_Angeles",
        )

        # Convert slots back to check days
        for slot in slots:
            slot_pacific = slot.astimezone(pacific_tz)
            # Should not be Saturday (5) or Sunday (6)
            assert slot_pacific.weekday() not in [5, 6]

    def test_generate_candidate_slots_respects_business_hours(
        self, sample_datetime_utc, business_hours
    ):
        """Test that slots are within business hours."""
        reference_tz = "America/Los_Angeles"
        slots = AvailabilityChecker.generate_candidate_slots(
            start_date=sample_datetime_utc,
            num_days=2,
            duration_minutes=30,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            reference_timezone=reference_tz,
        )

        # Convert to reference timezone to check business hours
        pacific_tz = pytz.timezone(reference_tz)
        for slot in slots:
            # Convert to reference timezone to check
            slot_in_tz = slot.astimezone(pacific_tz)
            slot_time = slot_in_tz.time()

            # Slot should start at or after business start
            assert slot_time >= business_hours["start"]

            # Slot end (slot + duration) should be at or before business end
            slot_end = slot_in_tz + timedelta(minutes=30)
            assert slot_end.time() <= business_hours["end"]

    def test_generate_candidate_slots_custom_increment(
        self, sample_datetime_utc, business_hours
    ):
        """Test generating slots with custom increment."""
        slots_30min = AvailabilityChecker.generate_candidate_slots(
            start_date=sample_datetime_utc,
            num_days=1,
            duration_minutes=30,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            slot_increment_minutes=30,
            reference_timezone="America/Los_Angeles",
        )

        slots_60min = AvailabilityChecker.generate_candidate_slots(
            start_date=sample_datetime_utc,
            num_days=1,
            duration_minutes=30,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            slot_increment_minutes=60,
            reference_timezone="America/Los_Angeles",
        )

        # 60-minute increments should produce fewer slots
        assert len(slots_60min) < len(slots_30min)

    def test_generate_candidate_slots_naive_datetime_raises_error(self, business_hours):
        """Test that naive datetime raises error."""
        naive_dt = datetime(2026, 1, 15, 10, 0, 0)

        with pytest.raises(ValueError, match="must be timezone-aware"):
            AvailabilityChecker.generate_candidate_slots(
                start_date=naive_dt,
                num_days=1,
                duration_minutes=30,
                business_start=business_hours["start"],
                business_end=business_hours["end"],
            )

    def test_check_availability_all_available(self, sample_datetime_utc):
        """Test checking availability when all users are free."""
        freebusy_data = {
            "user1@example.com": [],
            "user2@example.com": [],
            "user3@example.com": [],
        }

        availability = AvailabilityChecker.check_availability(
            slot_start=sample_datetime_utc,
            duration_minutes=30,
            freebusy_data=freebusy_data,
        )

        assert len(availability) == 3
        assert all(availability.values())  # All should be True

    def test_check_availability_one_busy(self, sample_datetime_utc):
        """Test checking availability when one user is busy."""
        busy_slot = TimeSlot(
            start=sample_datetime_utc, end=sample_datetime_utc + timedelta(hours=1)
        )

        freebusy_data = {
            "user1@example.com": [],
            "user2@example.com": [busy_slot],
            "user3@example.com": [],
        }

        availability = AvailabilityChecker.check_availability(
            slot_start=sample_datetime_utc,
            duration_minutes=30,
            freebusy_data=freebusy_data,
        )

        assert availability["user1@example.com"] is True
        assert availability["user2@example.com"] is False
        assert availability["user3@example.com"] is True

    def test_check_availability_partial_overlap(self, sample_datetime_utc):
        """Test checking availability with partial overlap."""
        # Meeting slot: 10:00-10:30
        # Busy period: 10:15-10:45 (overlaps)
        busy_slot = TimeSlot(
            start=sample_datetime_utc + timedelta(minutes=15),
            end=sample_datetime_utc + timedelta(minutes=45),
        )

        freebusy_data = {"user1@example.com": [busy_slot]}

        availability = AvailabilityChecker.check_availability(
            slot_start=sample_datetime_utc,
            duration_minutes=30,
            freebusy_data=freebusy_data,
        )

        assert availability["user1@example.com"] is False

    def test_check_availability_no_overlap(self, sample_datetime_utc):
        """Test checking availability with no overlap."""
        # Meeting slot: 10:00-10:30
        # Busy period: 11:00-12:00 (no overlap)
        busy_slot = TimeSlot(
            start=sample_datetime_utc + timedelta(hours=1),
            end=sample_datetime_utc + timedelta(hours=2),
        )

        freebusy_data = {"user1@example.com": [busy_slot]}

        availability = AvailabilityChecker.check_availability(
            slot_start=sample_datetime_utc,
            duration_minutes=30,
            freebusy_data=freebusy_data,
        )

        assert availability["user1@example.com"] is True

    def test_check_availability_multiple_busy_periods(self, sample_datetime_utc):
        """Test checking availability with multiple busy periods."""
        busy_slot1 = TimeSlot(
            start=sample_datetime_utc - timedelta(hours=1),
            end=sample_datetime_utc - timedelta(minutes=30),
        )
        busy_slot2 = TimeSlot(
            start=sample_datetime_utc + timedelta(hours=1),
            end=sample_datetime_utc + timedelta(hours=2),
        )

        freebusy_data = {"user1@example.com": [busy_slot1, busy_slot2]}

        availability = AvailabilityChecker.check_availability(
            slot_start=sample_datetime_utc,
            duration_minutes=30,
            freebusy_data=freebusy_data,
        )

        assert availability["user1@example.com"] is True

    def test_filter_by_business_hours_multi_tz(self, business_hours):
        """Test filtering slots by business hours across timezones."""
        # Create a slot at 10:00 UTC (2:00 AM PST, 5:00 AM EST)
        early_slot = datetime(2026, 1, 15, 10, 0, 0, tzinfo=pytz.UTC)

        # Create a slot at 18:00 UTC (10:00 AM PST, 1:00 PM EST)
        good_slot = datetime(2026, 1, 15, 18, 0, 0, tzinfo=pytz.UTC)

        slots = [early_slot, good_slot]

        user_timezones = {
            "user1@example.com": "America/Los_Angeles",
            "user2@example.com": "America/New_York",
        }

        filtered = AvailabilityChecker.filter_by_business_hours_multi_tz(
            slots=slots,
            user_timezones=user_timezones,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
        )

        # Only the good_slot should pass (within business hours for both timezones)
        assert len(filtered) >= 1
        assert good_slot in filtered

    def test_filter_by_business_hours_multi_tz_empty_timezones(
        self, sample_datetime_utc, business_hours
    ):
        """Test filtering with no user timezones returns all slots."""
        slots = [sample_datetime_utc]

        filtered = AvailabilityChecker.filter_by_business_hours_multi_tz(
            slots=slots,
            user_timezones={},
            business_start=business_hours["start"],
            business_end=business_hours["end"],
        )

        assert filtered == slots

    def test_get_earliest_available_slot_found(self, sample_datetime_utc):
        """Test finding earliest available slot."""
        slot1 = sample_datetime_utc
        slot2 = sample_datetime_utc + timedelta(hours=1)
        slot3 = sample_datetime_utc + timedelta(hours=2)

        slots = [slot1, slot2, slot3]

        freebusy_data = {"user1@example.com": [], "user2@example.com": []}

        result = AvailabilityChecker.get_earliest_available_slot(
            slots=slots,
            duration_minutes=30,
            freebusy_data=freebusy_data,
            min_attendees=2,
        )

        assert result is not None
        (
            slot_start,
            availability,
        ) = result
        assert slot_start == slot1
        assert len(availability) == 2

    def test_get_earliest_available_slot_skip_busy(self, sample_datetime_utc):
        """Test finding earliest slot skips busy times."""
        slot1 = sample_datetime_utc
        slot2 = sample_datetime_utc + timedelta(hours=1)

        slots = [slot1, slot2]

        # First slot is busy for user1
        busy_slot = TimeSlot(
            start=sample_datetime_utc, end=sample_datetime_utc + timedelta(hours=1)
        )

        freebusy_data = {"user1@example.com": [busy_slot], "user2@example.com": []}

        result = AvailabilityChecker.get_earliest_available_slot(
            slots=slots,
            duration_minutes=30,
            freebusy_data=freebusy_data,
            min_attendees=2,
        )

        assert result is not None
        slot_start, availability = result
        # Should pick slot2 since slot1 doesn't have enough available people
        assert slot_start == slot2

    def test_get_earliest_available_slot_not_found(self, sample_datetime_utc):
        """Test when no suitable slot is found."""
        slots = [sample_datetime_utc]

        # All users are busy
        busy_slot = TimeSlot(
            start=sample_datetime_utc, end=sample_datetime_utc + timedelta(hours=1)
        )

        freebusy_data = {
            "user1@example.com": [busy_slot],
            "user2@example.com": [busy_slot],
        }

        result = AvailabilityChecker.get_earliest_available_slot(
            slots=slots,
            duration_minutes=30,
            freebusy_data=freebusy_data,
            min_attendees=2,
        )

        assert result is None

    def test_get_earliest_available_slot_min_attendees(self, sample_datetime_utc):
        """Test minimum attendees threshold."""
        slots = [sample_datetime_utc]

        busy_slot = TimeSlot(
            start=sample_datetime_utc, end=sample_datetime_utc + timedelta(hours=1)
        )

        freebusy_data = {
            "user1@example.com": [],
            "user2@example.com": [busy_slot],
            "user3@example.com": [busy_slot],
        }

        # With min_attendees=1, should find the slot
        result = AvailabilityChecker.get_earliest_available_slot(
            slots=slots,
            duration_minutes=30,
            freebusy_data=freebusy_data,
            min_attendees=1,
        )
        assert result is not None

        # With min_attendees=2, should not find the slot
        result = AvailabilityChecker.get_earliest_available_slot(
            slots=slots,
            duration_minutes=30,
            freebusy_data=freebusy_data,
            min_attendees=2,
        )
        assert result is None
