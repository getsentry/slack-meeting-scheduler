"""Configuration management for the meeting scheduler."""

from datetime import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
load_dotenv()


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Slack Configuration (optional for CLI mode)
    slack_bot_token: Optional[str] = Field(
        None, description="Slack bot token (xoxb-...)"
    )
    slack_app_token: Optional[str] = Field(
        None, description="Slack app token for Socket Mode (xapp-...)"
    )

    # Google Configuration
    # Optional: Only needed for local development. Cloud Run uses the service account identity automatically.
    google_service_account_path: Optional[str] = Field(
        None, description="Path to Google service account JSON file (local dev only)"
    )
    google_service_account_json: Optional[str] = Field(
        None,
        description="Google service account JSON content as string (local dev only)",
    )

    # Meeting Defaults
    default_meeting_duration: int = Field(
        30, description="Default meeting duration in minutes"
    )
    min_reactions: int = Field(1, description="Default minimum reactions required")
    default_reaction_emoji: str = Field(
        "white_check_mark", description="Default emoji for reactions"
    )

    # Business Hours
    business_hours_start: str = Field(
        "09:00", description="Business hours start time (HH:MM)"
    )
    business_hours_end: str = Field(
        "17:00", description="Business hours end time (HH:MM)"
    )

    # Availability Search Settings
    max_days_ahead: int = Field(
        14, description="Maximum days ahead to search for availability"
    )

    # Feature Flags
    enable_find_time: bool = Field(
        False, description="Enable automatic time finding (disabled for MVP)"
    )

    # Application Settings
    log_level: str = Field("INFO", description="Logging level")

    # Sentry Configuration
    sentry_dsn: Optional[str] = Field(None, description="Sentry DSN for error tracking")
    sentry_environment: str = Field("production", description="Sentry environment name")
    sentry_traces_sample_rate: float = Field(
        1.0, description="Sentry traces sample rate (0.0-1.0)"
    )
    sentry_profiles_sample_rate: float = Field(
        1.0, description="Sentry profiling sample rate (0.0-1.0)"
    )

    @field_validator("google_service_account_path", mode="before")
    @classmethod
    def validate_service_account_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the service account path exists if provided."""
        if v and not Path(v).exists():
            raise ValueError(f"Service account file not found at: {v}")
        return v

    @field_validator("business_hours_start", "business_hours_end")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time format (HH:MM)."""
        try:
            hours, minutes = v.split(":")
            time(int(hours), int(minutes))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid time format: {v}. Expected HH:MM")
        return v

    def get_business_hours_start(self) -> time:
        """Get business hours start as a time object."""
        hours, minutes = self.business_hours_start.split(":")
        return time(int(hours), int(minutes))

    def get_business_hours_end(self) -> time:
        """Get business hours end as a time object."""
        hours, minutes = self.business_hours_end.split(":")
        return time(int(hours), int(minutes))

    def get_service_account_credentials(self) -> Optional[str]:
        """Get service account credentials (either from file or JSON string).

        Returns:
            Service account JSON content as string, or None to use Application Default Credentials

        Note:
            Returns None when running on Cloud Run, which uses the service account identity automatically.
        """
        if self.google_service_account_json:
            return self.google_service_account_json
        elif self.google_service_account_path:
            with open(self.google_service_account_path, "r") as f:
                return f.read()
        else:
            # Use Application Default Credentials (Cloud Run service account identity)
            return None


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        Config instance

    Raises:
        ValueError: If configuration is invalid
    """
    global _config
    if _config is None:
        _config = Config()
    return _config
