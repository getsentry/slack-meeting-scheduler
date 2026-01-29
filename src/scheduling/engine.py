"""Scheduling engine with scoring algorithm."""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from ..models import TimeSlot
from .availability import AvailabilityChecker
from .timezone_handler import TimezoneHandler

logger = logging.getLogger(__name__)


class SchedulingEngine:
    """Core scheduling engine with optimal time finding."""

    @staticmethod
    def score_slot(
        slot: datetime,
        availability: Dict[str, bool],
        min_attendees: int
    ) -> Optional[int]:
        """Score a time slot based on availability and time preferences.

        Scoring:
        - Base: 100 points per available attendee
        - Bonus: +10 per day earlier in the week (Monday = +40, Friday = 0)
        - Bonus: +20 for mid-day slots (11am-2pm)
        - Penalty: -10 for edge hours (9-10am or 4-5pm)

        Args:
            slot: Slot start time (UTC)
            availability: Dictionary mapping user IDs to availability
            min_attendees: Minimum attendees required

        Returns:
            Score (integer) or None if below minimum attendees
        """
        num_available = sum(1 for avail in availability.values() if avail)

        # Check minimum threshold
        if num_available < min_attendees:
            return None

        # Base score: 100 points per available attendee
        score = num_available * 100

        # Day of week bonus (prefer earlier in week)
        # Monday = 0, Tuesday = 1, ..., Friday = 4
        day_of_week = slot.weekday()
        if day_of_week < 5:  # Weekday
            # Monday gets +40, Tuesday +30, ..., Friday +0
            day_bonus = (4 - day_of_week) * 10
            score += day_bonus

        # Time of day preferences (use UTC hour for now, could be improved)
        hour = slot.hour

        # Mid-day preference (11am-2pm) - Note: This is simplified, real impl would check user timezones
        if 11 <= hour <= 14:
            score += 20

        # Edge hour penalty (9-10am or 4-5pm)
        if hour in [9, 16, 17]:
            score -= 10

        logger.debug(
            f"Scored slot {slot.isoformat()}: {score} points "
            f"({num_available} available, weekday={day_of_week})"
        )

        return score

    @staticmethod
    def find_optimal_time(
        attendee_emails: List[str],
        duration_minutes: int,
        search_start: datetime,
        search_days: int,
        business_start: time,
        business_end: time,
        freebusy_data: Dict[str, List[TimeSlot]],
        user_timezones: Dict[str, str],
        min_attendees: int = 1
    ) -> Optional[Tuple[datetime, Dict[str, bool], int]]:
        """Find optimal meeting time using scored ranking.

        Algorithm:
        1. Generate candidate slots during business hours
        2. Filter by business hours in all attendee timezones
        3. Score each slot by availability and preferences
        4. Return highest scoring slot

        Args:
            attendee_emails: List of attendee email addresses
            duration_minutes: Meeting duration in minutes
            search_start: Start of search period (timezone-aware)
            search_days: Number of days to search
            business_start: Business hours start time
            business_end: Business hours end time
            freebusy_data: Dictionary mapping emails to busy periods
            user_timezones: Dictionary mapping emails to timezones
            min_attendees: Minimum attendees required

        Returns:
            Tuple of (optimal_slot_start, availability_dict, score) or None if no suitable slot
        """
        logger.info(
            f"Finding optimal time for {len(attendee_emails)} attendees, "
            f"duration={duration_minutes}m, min={min_attendees}"
        )

        # Step 1: Generate candidate slots
        candidates = AvailabilityChecker.generate_candidate_slots(
            start_date=search_start,
            num_days=search_days,
            duration_minutes=duration_minutes,
            business_start=business_start,
            business_end=business_end
        )

        if not candidates:
            logger.warning("No candidate slots generated")
            return None

        # Step 2: Filter by business hours across all timezones
        valid_candidates = AvailabilityChecker.filter_by_business_hours_multi_tz(
            slots=candidates,
            user_timezones=user_timezones,
            business_start=business_start,
            business_end=business_end
        )

        if not valid_candidates:
            logger.warning("No slots valid for all user timezones")
            return None

        # Step 3: Score each slot and find the best
        best_slot = None
        best_availability = None
        best_score = -1

        for slot in valid_candidates:
            # Check availability
            availability = AvailabilityChecker.check_availability(
                slot_start=slot,
                duration_minutes=duration_minutes,
                freebusy_data=freebusy_data
            )

            # Score the slot
            score = SchedulingEngine.score_slot(
                slot=slot,
                availability=availability,
                min_attendees=min_attendees
            )

            # Track best slot
            if score is not None and score > best_score:
                best_score = score
                best_slot = slot
                best_availability = availability

                logger.debug(f"New best slot: {slot.isoformat()} with score {score}")

        if best_slot is None:
            logger.warning(
                f"No suitable slot found with {min_attendees}+ attendees in {search_days} days"
            )
            return None

        num_available = sum(1 for avail in best_availability.values() if avail)
        logger.info(
            f"Found optimal slot: {best_slot.isoformat()} "
            f"({num_available}/{len(attendee_emails)} available, score={best_score})"
        )

        return (best_slot, best_availability, best_score)

    @staticmethod
    def format_availability_summary(
        availability: Dict[str, bool],
        user_names: Dict[str, str]
    ) -> str:
        """Format availability dictionary as a human-readable summary.

        Args:
            availability: Dictionary mapping user IDs to availability
            user_names: Dictionary mapping user IDs to display names

        Returns:
            Formatted string with available and unavailable users
        """
        available = []
        unavailable = []

        for user_id, is_available in availability.items():
            name = user_names.get(user_id, user_id)
            if is_available:
                available.append(name)
            else:
                unavailable.append(name)

        summary_parts = []

        if available:
            summary_parts.append(f"*Available ({len(available)}):* {', '.join(available)}")

        if unavailable:
            summary_parts.append(f"*Unavailable ({len(unavailable)}):* {', '.join(unavailable)}")

        return "\n".join(summary_parts)
