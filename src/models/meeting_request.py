"""MeetingRequest data model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .scheduling_mode import SchedulingMode


@dataclass
class MeetingRequest:
    """Represents a meeting scheduling request."""

    request_id: str
    channel_id: str
    message_ts: str
    initiator_user_id: str
    reaction_duration_seconds: int
    scheduling_mode: SchedulingMode
    duration_minutes: int
    min_reactions: int
    created_at: datetime
    specific_datetime: Optional[datetime] = None
    participants: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of the meeting request."""
        mode = (
            "specific time"
            if self.scheduling_mode == SchedulingMode.SPECIFIC_TIME
            else "find availability"
        )
        return (
            f"MeetingRequest(id={self.request_id}, mode={mode}, "
            f"participants={len(self.participants)}, duration={self.duration_minutes}m)"
        )
