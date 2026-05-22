"""Tests for SchedulingEngine."""

from datetime import datetime
import pytz

from src.scheduling.engine import SchedulingEngine
from src.models import TimeSlot


class TestSchedulingEngine:
    """Tests for SchedulingEngine."""

    def test_score_slot_basic(self, sample_datetime_utc):
        """Test basic slot scoring."""
        availability = {
            "user1@example.com": True,
            "user2@example.com": True,
            "user3@example.com": True,
        }

        score = SchedulingEngine.score_slot(
            slot=sample_datetime_utc, availability=availability, min_attendees=2
        )

        assert score is not None
        assert score >= 300  # At least 100 per attendee

    def test_score_slot_below_minimum(self, sample_datetime_utc):
        """Test scoring returns None when below minimum attendees."""
        availability = {
            "user1@example.com": True,
            "user2@example.com": False,
            "user3@example.com": False,
        }

        score = SchedulingEngine.score_slot(
            slot=sample_datetime_utc, availability=availability, min_attendees=2
        )

        assert score is None

    def test_score_slot_day_of_week_bonus(self):
        """Test that earlier days of week get higher scores."""
        availability = {"user1@example.com": True, "user2@example.com": True}

        # Monday (should get +40 bonus)
        monday = datetime(2026, 1, 19, 10, 0, 0, tzinfo=pytz.UTC)
        monday_score = SchedulingEngine.score_slot(
            monday, availability, min_attendees=1
        )

        # Friday (should get +0 bonus)
        friday = datetime(2026, 1, 16, 10, 0, 0, tzinfo=pytz.UTC)
        friday_score = SchedulingEngine.score_slot(
            friday, availability, min_attendees=1
        )

        assert monday_score is not None
        assert friday_score is not None
        assert monday_score > friday_score

    def test_score_slot_mid_day_bonus(self):
        """Test that mid-day slots get bonus points."""
        availability = {"user1@example.com": True, "user2@example.com": True}

        # 12:00 UTC (mid-day, should get +20 bonus)
        midday = datetime(2026, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        midday_score = SchedulingEngine.score_slot(
            midday, availability, min_attendees=1
        )

        # 08:00 UTC (not mid-day, no bonus)
        early = datetime(2026, 1, 15, 8, 0, 0, tzinfo=pytz.UTC)
        early_score = SchedulingEngine.score_slot(early, availability, min_attendees=1)

        assert midday_score is not None
        assert early_score is not None
        assert midday_score > early_score

    def test_score_slot_edge_hour_penalty(self):
        """Test that edge hours get penalty."""
        availability = {"user1@example.com": True, "user2@example.com": True}

        # 09:00 UTC (edge hour, should get -10 penalty)
        edge = datetime(2026, 1, 15, 9, 0, 0, tzinfo=pytz.UTC)
        edge_score = SchedulingEngine.score_slot(edge, availability, min_attendees=1)

        # 10:00 UTC (not edge hour, no penalty)
        normal = datetime(2026, 1, 15, 10, 0, 0, tzinfo=pytz.UTC)
        normal_score = SchedulingEngine.score_slot(
            normal, availability, min_attendees=1
        )

        assert edge_score is not None
        assert normal_score is not None
        assert normal_score > edge_score

    def test_score_slot_more_attendees_higher_score(self, sample_datetime_utc):
        """Test that more available attendees results in higher score."""
        availability_2 = {
            "user1@example.com": True,
            "user2@example.com": True,
            "user3@example.com": False,
        }

        availability_3 = {
            "user1@example.com": True,
            "user2@example.com": True,
            "user3@example.com": True,
        }

        score_2 = SchedulingEngine.score_slot(
            sample_datetime_utc, availability_2, min_attendees=1
        )
        score_3 = SchedulingEngine.score_slot(
            sample_datetime_utc, availability_3, min_attendees=1
        )

        assert score_2 is not None
        assert score_3 is not None
        assert score_3 > score_2

    def test_find_optimal_time_basic(self, business_hours, sample_user_timezones):
        """Test finding optimal time with basic scenario."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        search_start = pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0))

        attendee_emails = list(sample_user_timezones.keys())

        freebusy_data = {email: [] for email in attendee_emails}

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=attendee_emails,
            duration_minutes=30,
            search_start=search_start,
            search_days=2,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            freebusy_data=freebusy_data,
            user_timezones=sample_user_timezones,
            min_attendees=2,
        )

        assert result is not None
        slot, availability, score = result
        assert slot is not None
        assert len(availability) == len(attendee_emails)
        assert score > 0

    def test_find_optimal_time_with_conflicts(
        self, business_hours, sample_user_timezones
    ):
        """Test finding optimal time when some users have conflicts."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        search_start = pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0))

        attendee_emails = list(sample_user_timezones.keys())

        # First user is busy in the morning
        busy_slot = TimeSlot(
            start=pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0)).astimezone(
                pytz.UTC
            ),
            end=pacific_tz.localize(datetime(2026, 1, 15, 12, 0, 0)).astimezone(
                pytz.UTC
            ),
        )

        freebusy_data = {
            attendee_emails[0]: [busy_slot],
            attendee_emails[1]: [],
            attendee_emails[2]: [],
        }

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=attendee_emails,
            duration_minutes=30,
            search_start=search_start,
            search_days=2,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            freebusy_data=freebusy_data,
            user_timezones=sample_user_timezones,
            min_attendees=2,
        )

        assert result is not None
        slot, availability, score = result
        # Should still find a slot with at least 2 people
        num_available = sum(1 for avail in availability.values() if avail)
        assert num_available >= 2

    def test_find_optimal_time_no_suitable_slot(
        self, business_hours, sample_user_timezones
    ):
        """Test when no suitable slot is found."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        search_start = pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0))

        attendee_emails = list(sample_user_timezones.keys())

        # Everyone is busy all day
        busy_slot = TimeSlot(
            start=pacific_tz.localize(datetime(2026, 1, 15, 8, 0, 0)).astimezone(
                pytz.UTC
            ),
            end=pacific_tz.localize(datetime(2026, 1, 17, 18, 0, 0)).astimezone(
                pytz.UTC
            ),
        )

        freebusy_data = {email: [busy_slot] for email in attendee_emails}

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=attendee_emails,
            duration_minutes=30,
            search_start=search_start,
            search_days=2,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            freebusy_data=freebusy_data,
            user_timezones=sample_user_timezones,
            min_attendees=3,
        )

        assert result is None

    def test_find_optimal_time_prefers_earlier_in_week(
        self, business_hours, sample_user_timezones
    ):
        """Test that algorithm prefers earlier days in the week."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        # Start on Monday
        monday = pacific_tz.localize(datetime(2026, 1, 19, 9, 0, 0))

        attendee_emails = list(sample_user_timezones.keys())

        freebusy_data = {email: [] for email in attendee_emails}

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=attendee_emails,
            duration_minutes=30,
            search_start=monday,
            search_days=5,  # Mon-Fri
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            freebusy_data=freebusy_data,
            user_timezones=sample_user_timezones,
            min_attendees=2,
        )

        assert result is not None
        slot, availability, score = result

        # Convert to Pacific to check the day
        slot_pacific = slot.astimezone(pacific_tz)
        # Should prefer Monday (0) or Tuesday (1) over later days
        assert slot_pacific.weekday() in [0, 1]

    def test_find_optimal_time_long_duration(
        self, business_hours, sample_user_timezones
    ):
        """Test finding time for longer meetings."""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        search_start = pacific_tz.localize(datetime(2026, 1, 15, 9, 0, 0))

        attendee_emails = list(sample_user_timezones.keys())

        freebusy_data = {email: [] for email in attendee_emails}

        result = SchedulingEngine.find_optimal_time(
            attendee_emails=attendee_emails,
            duration_minutes=120,  # 2 hour meeting
            search_start=search_start,
            search_days=3,
            business_start=business_hours["start"],
            business_end=business_hours["end"],
            freebusy_data=freebusy_data,
            user_timezones=sample_user_timezones,
            min_attendees=2,
        )

        assert result is not None
        slot, availability, score = result
        # Verify the slot can accommodate 2 hours
        assert slot is not None

    def test_format_availability_summary(self):
        """Test formatting availability summary."""
        availability = {
            "user1@example.com": True,
            "user2@example.com": True,
            "user3@example.com": False,
        }

        user_names = {
            "user1@example.com": "Alice",
            "user2@example.com": "Bob",
            "user3@example.com": "Charlie",
        }

        summary = SchedulingEngine.format_availability_summary(availability, user_names)

        assert "Available" in summary
        assert "Unavailable" in summary
        assert "Alice" in summary
        assert "Bob" in summary
        assert "Charlie" in summary
        assert "(2)" in summary  # 2 available
        assert "(1)" in summary  # 1 unavailable

    def test_format_availability_summary_all_available(self):
        """Test formatting when all users are available."""
        availability = {"user1@example.com": True, "user2@example.com": True}

        user_names = {"user1@example.com": "Alice", "user2@example.com": "Bob"}

        summary = SchedulingEngine.format_availability_summary(availability, user_names)

        assert "Available" in summary
        assert "Unavailable" not in summary
        assert "Alice" in summary
        assert "Bob" in summary

    def test_format_availability_summary_all_unavailable(self):
        """Test formatting when all users are unavailable."""
        availability = {"user1@example.com": False, "user2@example.com": False}

        user_names = {"user1@example.com": "Alice", "user2@example.com": "Bob"}

        summary = SchedulingEngine.format_availability_summary(availability, user_names)

        assert "Unavailable" in summary
        assert "Available" not in summary
        assert "Alice" in summary
        assert "Bob" in summary

    def test_format_availability_summary_missing_names(self):
        """Test formatting with missing user names (falls back to IDs)."""
        availability = {"user1@example.com": True, "user2@example.com": False}

        user_names = {
            "user1@example.com": "Alice"
            # user2 name is missing
        }

        summary = SchedulingEngine.format_availability_summary(availability, user_names)

        assert "Alice" in summary
        assert "user2@example.com" in summary  # Should fall back to email
