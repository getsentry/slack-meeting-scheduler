"""Scheduling mode enumeration."""

from enum import Enum


class SchedulingMode(Enum):
    """Enumeration of scheduling modes."""

    SPECIFIC_TIME = "specific_time"
    FIND_AVAILABILITY = "find_availability"

    def __str__(self) -> str:
        """String representation of the scheduling mode."""
        return self.value
