"""TimeSlot data model for representing time periods."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimeSlot:
    """Represents a time slot with start and end times."""

    start: datetime
    end: datetime

    def overlaps(self, other: 'TimeSlot') -> bool:
        """Check if this time slot overlaps with another.

        Args:
            other: Another TimeSlot to check against

        Returns:
            True if the time slots overlap, False otherwise
        """
        return self.start < other.end and other.start < self.end

    def contains(self, dt: datetime) -> bool:
        """Check if a datetime falls within this time slot.

        Args:
            dt: Datetime to check

        Returns:
            True if dt is within this time slot, False otherwise
        """
        return self.start <= dt < self.end

    def duration_minutes(self) -> int:
        """Calculate the duration of this time slot in minutes.

        Returns:
            Duration in minutes
        """
        return int((self.end - self.start).total_seconds() / 60)

    def __str__(self) -> str:
        """String representation of the time slot."""
        return f"{self.start.isoformat()} - {self.end.isoformat()}"
