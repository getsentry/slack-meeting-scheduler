"""Availability checking and candidate slot generation."""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List

from ..models import TimeSlot
from .timezone_handler import TimezoneHandler

logger = logging.getLogger(__name__)


class AvailabilityChecker:
    """Checks availability and generates candidate meeting slots."""

    @staticmethod
    def generate_candidate_slots(
        start_date: datetime,
        num_days: int,
        duration_minutes: int,
        business_start: time,
        business_end: time,
        slot_increment_minutes: int = 30,
        reference_timezone: str = None
    ) -> List[datetime]:
        """Generate candidate time slots during business hours.

        Args:
            start_date: Starting date (should be timezone-aware)
            num_days: Number of days to search
            duration_minutes: Meeting duration in minutes
            business_start: Business hours start time
            business_end: Business hours end time
            slot_increment_minutes: Time between candidate slots (default: 30)
            reference_timezone: Timezone for interpreting business hours (e.g., "America/Los_Angeles").
                               If not provided, uses start_date's timezone.

        Returns:
            List of candidate slot start times (UTC)
        """
        if start_date.tzinfo is None:
            raise ValueError("start_date must be timezone-aware")

        # Determine the timezone for business hours
        import pytz
        if reference_timezone:
            biz_tz = pytz.timezone(reference_timezone)
        else:
            biz_tz = start_date.tzinfo

        # Convert start_date to reference timezone to get the correct starting date
        start_date_local = start_date.astimezone(biz_tz)

        candidates = []
        current_date = start_date_local.date()
        end_date = (start_date_local + timedelta(days=num_days)).date()

        logger.info(
            f"Generating candidate slots from {current_date} to {end_date}, "
            f"duration={duration_minutes}m, increment={slot_increment_minutes}m, "
            f"reference_tz={reference_timezone or 'start_date.tzinfo'}"
        )

        while current_date < end_date:
            # Create datetime for start of day in the reference timezone
            day_start = datetime.combine(current_date, business_start)
            day_start = biz_tz.localize(day_start)

            # Skip weekends
            if TimezoneHandler.is_weekend(day_start):
                logger.debug(f"Skipping weekend: {current_date}")
                current_date += timedelta(days=1)
                continue

            # Generate slots for this day
            day_end = datetime.combine(current_date, business_end)
            day_end = biz_tz.localize(day_end)

            current_slot = day_start
            while current_slot + timedelta(minutes=duration_minutes) <= day_end:
                # Check if slot is in the future (compared to original start_date)
                if current_slot >= start_date_local:
                    # Convert to UTC for consistency
                    utc_slot = TimezoneHandler.convert_to_utc(current_slot)
                    candidates.append(utc_slot)

                current_slot += timedelta(minutes=slot_increment_minutes)

            current_date += timedelta(days=1)

        logger.info(f"Generated {len(candidates)} candidate slots")
        return candidates

    @staticmethod
    def check_availability(
        slot_start: datetime,
        duration_minutes: int,
        freebusy_data: Dict[str, List[TimeSlot]]
    ) -> Dict[str, bool]:
        """Check who is available for a specific time slot.

        Args:
            slot_start: Start time of the slot (UTC)
            duration_minutes: Duration in minutes
            freebusy_data: Dictionary mapping user IDs/emails to their busy periods

        Returns:
            Dictionary mapping user IDs/emails to availability (True = available)
        """
        slot_end = slot_start + timedelta(minutes=duration_minutes)
        meeting_slot = TimeSlot(start=slot_start, end=slot_end)

        availability = {}

        for user_id, busy_periods in freebusy_data.items():
            # Check if any busy period overlaps with the meeting slot
            is_available = True
            for busy_period in busy_periods:
                if meeting_slot.overlaps(busy_period):
                    is_available = False
                    logger.debug(
                        f"{user_id} is busy: {busy_period.start} - {busy_period.end} "
                        f"overlaps with {slot_start} - {slot_end}"
                    )
                    break

            availability[user_id] = is_available

        num_available = sum(1 for avail in availability.values() if avail)
        logger.debug(
            f"Slot {slot_start.isoformat()}: {num_available}/{len(availability)} available"
        )

        return availability

    @staticmethod
    def filter_by_business_hours_multi_tz(
        slots: List[datetime],
        user_timezones: Dict[str, str],
        business_start: time,
        business_end: time,
        duration_minutes: int = 0
    ) -> List[datetime]:
        """Filter slots to ensure they're within business hours for ALL users.

        Args:
            slots: List of candidate slots (UTC)
            user_timezones: Dictionary mapping user IDs to timezone strings
            business_start: Business hours start time
            business_end: Business hours end time
            duration_minutes: Meeting duration in minutes (to check end time)

        Returns:
            Filtered list of slots that work for all timezones
        """
        if not user_timezones:
            logger.warning("No user timezones provided, returning all slots")
            return slots

        filtered_slots = []

        for slot in slots:
            # Check if slot is within business hours for ALL users
            valid_for_all = True
            slot_end = slot + timedelta(minutes=duration_minutes) if duration_minutes > 0 else None

            for user_id, user_tz in user_timezones.items():
                # Check start time is within business hours
                if not TimezoneHandler.is_business_day(
                    slot, business_start, business_end, timezone=user_tz
                ):
                    logger.debug(
                        f"Slot {slot.isoformat()} start not in business hours for {user_id} ({user_tz})"
                    )
                    valid_for_all = False
                    break

                # Check end time is within business hours (if duration provided)
                if slot_end is not None and not TimezoneHandler.is_within_business_hours(
                    slot_end, business_start, business_end, timezone=user_tz
                ):
                    logger.debug(
                        f"Slot {slot.isoformat()} end ({slot_end.isoformat()}) not in business hours for {user_id} ({user_tz})"
                    )
                    valid_for_all = False
                    break

            if valid_for_all:
                filtered_slots.append(slot)

        logger.info(
            f"Filtered to {len(filtered_slots)}/{len(slots)} slots valid for all timezones"
        )

        return filtered_slots

    @staticmethod
    def get_earliest_available_slot(
        slots: List[datetime],
        duration_minutes: int,
        freebusy_data: Dict[str, List[TimeSlot]],
        min_attendees: int = 1
    ) -> tuple[datetime, Dict[str, bool]] | None:
        """Find the earliest slot where enough people are available.

        Args:
            slots: List of candidate slots (UTC)
            duration_minutes: Meeting duration in minutes
            freebusy_data: Dictionary mapping user IDs to busy periods
            min_attendees: Minimum number of attendees required

        Returns:
            Tuple of (slot_start, availability_dict) or None if no suitable slot found
        """
        for slot in slots:
            availability = AvailabilityChecker.check_availability(
                slot, duration_minutes, freebusy_data
            )

            num_available = sum(1 for avail in availability.values() if avail)

            if num_available >= min_attendees:
                logger.info(
                    f"Found earliest available slot: {slot.isoformat()} "
                    f"({num_available} available)"
                )
                return (slot, availability)

        logger.warning(f"No slot found with {min_attendees}+ attendees")
        return None
