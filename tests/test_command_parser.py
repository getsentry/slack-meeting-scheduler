"""Tests for CommandParser."""

import pytest

from src.slack.command_parser import CommandParser, CommandParameters
from src.models import SchedulingMode


class TestCommandParser:
    """Tests for CommandParser."""

    def test_parse_simple_specific_time(self):
        """Test parsing simple specific time command."""
        result = CommandParser.parse("5m tomorrow 2pm")

        assert result.reaction_duration_seconds == 300
        assert result.scheduling_mode == SchedulingMode.SPECIFIC_TIME
        assert result.specific_datetime_text == "tomorrow 2pm"
        assert result.duration_minutes == 30  # default
        assert result.min_reactions == 1  # default

    def test_parse_find_time(self, monkeypatch):
        """Test parsing find-time command."""
        # Enable find-time feature for this test via environment variable
        monkeypatch.setenv('ENABLE_FIND_TIME', 'true')
        # Clear the config singleton to force reload
        import src.config
        src.config._config = None

        result = CommandParser.parse("1h find-time")

        assert result.reaction_duration_seconds == 3600
        assert result.scheduling_mode == SchedulingMode.FIND_AVAILABILITY
        assert result.specific_datetime_text is None
        assert result.duration_minutes == 30  # default
        assert result.min_reactions == 1  # default

    def test_parse_find_time_hyphenated(self, monkeypatch):
        """Test parsing find-time with hyphen."""
        # Enable find-time feature for this test via environment variable
        monkeypatch.setenv('ENABLE_FIND_TIME', 'true')
        # Clear the config singleton to force reload
        import src.config
        src.config._config = None

        result = CommandParser.parse("30m find-time")

        assert result.scheduling_mode == SchedulingMode.FIND_AVAILABILITY
        assert result.specific_datetime_text is None

    def test_parse_duration_seconds(self):
        """Test parsing duration in seconds."""
        result = CommandParser.parse("30s tomorrow 2pm")

        assert result.reaction_duration_seconds == 30

    def test_parse_duration_minutes(self):
        """Test parsing duration in minutes."""
        result = CommandParser.parse("15m tomorrow 2pm")

        assert result.reaction_duration_seconds == 900

    def test_parse_duration_hours(self):
        """Test parsing duration in hours."""
        result = CommandParser.parse("2h tomorrow 2pm")

        assert result.reaction_duration_seconds == 7200

    def test_parse_with_duration_param(self):
        """Test parsing with duration parameter."""
        result = CommandParser.parse("5m tomorrow 2pm duration:60m")

        assert result.duration_minutes == 60
        assert "duration:60m" not in result.specific_datetime_text

    def test_parse_with_duration_param_no_m_suffix(self):
        """Test parsing duration parameter without 'm' suffix."""
        result = CommandParser.parse("5m find-time duration:45")

        assert result.duration_minutes == 45

    def test_parse_with_min_param(self):
        """Test parsing with min reactions parameter."""
        result = CommandParser.parse("5m tomorrow 2pm min:3")

        assert result.min_reactions == 3
        assert "min:3" not in result.specific_datetime_text

    def test_parse_with_both_params(self):
        """Test parsing with both duration and min parameters."""
        result = CommandParser.parse("1h next Monday 10am duration:90m min:5")

        assert result.duration_minutes == 90
        assert result.min_reactions == 5
        assert "duration:90m" not in result.specific_datetime_text
        assert "min:5" not in result.specific_datetime_text
        assert "next Monday 10am" in result.specific_datetime_text

    def test_parse_complex_datetime(self):
        """Test parsing complex datetime string."""
        result = CommandParser.parse("30m Jan 20 at 3:30pm")

        assert result.specific_datetime_text == "Jan 20 at 3:30pm"
        assert result.scheduling_mode == SchedulingMode.SPECIFIC_TIME

    def test_parse_custom_defaults(self):
        """Test parsing with custom default values."""
        result = CommandParser.parse("5m tomorrow 2pm", default_duration=60, default_min=2)

        assert result.duration_minutes == 60
        assert result.min_reactions == 2

    def test_parse_params_override_defaults(self):
        """Test that explicit params override defaults."""
        result = CommandParser.parse(
            "5m tomorrow 2pm duration:45m min:3",
            default_duration=60,
            default_min=2
        )

        assert result.duration_minutes == 45
        assert result.min_reactions == 3

    def test_parse_empty_string_raises_error(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="Command text cannot be empty"):
            CommandParser.parse("")

    def test_parse_whitespace_only_raises_error(self):
        """Test parsing whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Command text cannot be empty"):
            CommandParser.parse("   ")

    def test_parse_missing_duration_raises_error(self):
        """Test parsing without duration prefix raises ValueError."""
        with pytest.raises(ValueError, match="Missing reaction duration"):
            CommandParser.parse("tomorrow 2pm")

    def test_parse_missing_datetime_raises_error(self):
        """Test parsing specific time mode without datetime raises ValueError."""
        with pytest.raises(ValueError, match="Missing date/time"):
            CommandParser.parse("5m")

    def test_parse_missing_datetime_with_only_params_raises_error(self):
        """Test parsing with only parameters but no datetime raises ValueError."""
        with pytest.raises(ValueError, match="Missing date/time"):
            CommandParser.parse("5m duration:60m")

    def test_parse_case_insensitive_duration(self):
        """Test that duration parsing is case insensitive."""
        result1 = CommandParser.parse("5M tomorrow 2pm")
        result2 = CommandParser.parse("5m tomorrow 2pm")

        assert result1.reaction_duration_seconds == result2.reaction_duration_seconds

    def test_parse_case_insensitive_find_time(self, monkeypatch):
        """Test that find-time parsing is case insensitive."""
        # Enable find-time feature for this test via environment variable
        monkeypatch.setenv('ENABLE_FIND_TIME', 'true')
        # Clear the config singleton to force reload
        import src.config
        src.config._config = None

        result1 = CommandParser.parse("5m FIND-TIME")
        result2 = CommandParser.parse("5m find-time")

        assert result1.scheduling_mode == result2.scheduling_mode

    def test_parse_case_insensitive_params(self):
        """Test that parameter parsing is case insensitive."""
        result = CommandParser.parse("5m tomorrow 2pm DURATION:60M MIN:3")

        assert result.duration_minutes == 60
        assert result.min_reactions == 3

    def test_parse_find_time_with_params(self, monkeypatch):
        """Test parsing find-time with parameters."""
        # Enable find-time feature for this test via environment variable
        monkeypatch.setenv('ENABLE_FIND_TIME', 'true')
        # Clear the config singleton to force reload
        import src.config
        src.config._config = None

        result = CommandParser.parse("2h find-time duration:45m min:4")

        assert result.reaction_duration_seconds == 7200
        assert result.scheduling_mode == SchedulingMode.FIND_AVAILABILITY
        assert result.duration_minutes == 45
        assert result.min_reactions == 4

    def test_parse_find_time_disabled(self):
        """Test that find-time is rejected when feature flag is disabled."""
        # Clear config singleton to ensure clean state
        import src.config
        src.config._config = None

        with pytest.raises(ValueError, match="Automatic time finding is currently disabled"):
            CommandParser.parse("5m find-time")

    def test_parse_extra_whitespace(self):
        """Test parsing with extra whitespace."""
        result = CommandParser.parse("  5m   tomorrow   2pm   duration:60m  ")

        assert result.reaction_duration_seconds == 300
        assert result.duration_minutes == 60

    def test_get_help_message(self):
        """Test help message generation."""
        # Clear config singleton to ensure clean state
        import src.config
        src.config._config = None

        help_msg = CommandParser.get_help_message()

        assert "Meeting Scheduler Help" in help_msg
        assert "/schedule-meet" in help_msg
        # Note: find-time is only shown if feature flag is enabled
        assert "duration:" in help_msg
        assert "min:" in help_msg

    def test_parse_preserves_datetime_text_content(self):
        """Test that datetime text is preserved correctly."""
        result = CommandParser.parse("5m next Wednesday at 2:30pm duration:45m")

        # Parameters should be removed from datetime text
        assert "duration:45m" not in result.specific_datetime_text
        # But the actual datetime should still be there
        assert "next Wednesday at 2:30pm" in result.specific_datetime_text

    def test_parse_multiple_digit_values(self):
        """Test parsing with large numeric values."""
        result = CommandParser.parse("120m tomorrow 2pm duration:180m min:10")

        assert result.reaction_duration_seconds == 7200  # 120 minutes
        assert result.duration_minutes == 180
        assert result.min_reactions == 10

    def test_parse_zero_values_rejected(self):
        """Test that zero values are parsed (validation happens elsewhere)."""
        result = CommandParser.parse("1m tomorrow 2pm duration:0m min:0")

        # Parser doesn't validate, just extracts
        assert result.duration_minutes == 0
        assert result.min_reactions == 0
