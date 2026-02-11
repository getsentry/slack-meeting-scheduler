#!/bin/bash

# Example CLI test script for slack-meeting-scheduler
# This demonstrates how to test the meeting scheduler without deploying to Slack

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Meeting Scheduler CLI Test Examples ===${NC}\n"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Copy .env.example to .env and configure your Google Calendar credentials"
    exit 1
fi

# Example 1: Schedule at specific time (dry run)
echo -e "${GREEN}Example 1: Schedule meeting tomorrow at 2pm (dry run)${NC}"
echo "Command: uv run python -m src.cli schedule \\"
echo "  --attendees 'alice@example.com:America/New_York,bob@example.com:Europe/London' \\"
echo "  --time 'tomorrow 2pm' \\"
echo "  --duration 30 \\"
echo "  --timezone 'America/New_York'"
echo ""
read -p "Press Enter to run (or Ctrl+C to skip)..."
uv run python -m src.cli schedule \
  --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \
  --time "tomorrow 2pm" \
  --duration 30 \
  --timezone "America/New_York"
echo -e "\n---\n"

# Example 2: Find optimal time (dry run)
echo -e "${GREEN}Example 2: Find optimal time for next 7 days (dry run)${NC}"
echo "Command: uv run python -m src.cli find \\"
echo "  --attendees 'alice@example.com:America/New_York,bob@example.com:Europe/London' \\"
echo "  --duration 60 \\"
echo "  --search-days 7 \\"
echo "  --min-attendees 2 \\"
echo "  --timezone 'America/New_York'"
echo ""
read -p "Press Enter to run (or Ctrl+C to skip)..."
uv run python -m src.cli find \
  --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \
  --duration 60 \
  --search-days 7 \
  --min-attendees 2 \
  --timezone "America/New_York"
echo -e "\n---\n"

# Example 3: Single attendee with verbose output (dry run)
echo -e "${GREEN}Example 3: Single attendee with verbose logging (dry run)${NC}"
echo "Command: uv run python -m src.cli schedule \\"
echo "  --attendees 'test@example.com:UTC' \\"
echo "  --time 'next Monday 10am' \\"
echo "  --duration 30 \\"
echo "  --timezone 'UTC' \\"
echo "  -v"
echo ""
read -p "Press Enter to run (or Ctrl+C to skip)..."
uv run python -m src.cli schedule \
  --attendees "test@example.com:UTC" \
  --time "next Monday 10am" \
  --duration 30 \
  --timezone "UTC" \
  -v
echo -e "\n---\n"

echo -e "${BLUE}=== All examples completed ===${NC}"
echo ""
echo "Note: All examples run in dry-run mode (no events created)"
echo "To actually create events, add --execute flag"
echo ""
echo "Example with --execute:"
echo "  uv run python -m src.cli schedule \\"
echo "    --attendees 'your@email.com:America/New_York' \\"
echo "    --time 'tomorrow 3pm' \\"
echo "    --timezone 'America/New_York' \\"
echo "    --execute"
