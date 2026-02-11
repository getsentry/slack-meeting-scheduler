# Meeting Scheduler

A Slack app that schedules Google Meet meetings with reaction-based attendance tracking. The app collects reactions from interested participants and either schedules at a specific time or finds the optimal time when most people are available.

## Features

- **Reaction-Based Attendance**: Collect interested participants via Slack reactions
- **Two Scheduling Modes**:
  - **Specific Time**: Schedule meeting at a user-specified date/time
  - **Find Availability**: Automatically find optimal time when most people are available
- **Natural Language Parsing**: Use intuitive time formats like "tomorrow 2pm" or "next Monday 10am"
- **Timezone-Aware**: Respects each user's timezone from their Slack profile
- **Business Hours**: Only schedules during configured business hours (default: 9am-5pm)
- **Google Meet Integration**: Automatically creates Google Meet links
- **Calendar Invitations**: Sends calendar invites to all participants

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Slack workspace with admin access
- Google Workspace account with:
  - Service account credentials
  - Calendar API enabled
  - Domain-wide delegation (optional, for accessing user calendars)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd slack-meeting-scheduler
```

### 2. Install Dependencies

```bash
# Install uv if you haven't already
# See: https://github.com/astral-sh/uv

# Install project dependencies
uv sync
```

### 3. Create Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From an app manifest"
3. Select your workspace
4. Copy the contents of `slack-app-manifest.yaml` and paste it
5. Click "Create"
6. Navigate to "Basic Information" and note your **App Token** (starts with `xapp-`)
7. Navigate to "OAuth & Permissions" and click "Install to Workspace"
8. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

**Important**: Make sure Socket Mode is enabled (Settings → Socket Mode → Enable)

### 4. Set Up Google Service Account

#### For Cloud Run Deployment (Recommended)

When deploying to Cloud Run, the application automatically uses the Cloud Run service account identity. No JSON file or credentials are needed.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Grant Calendar permissions to the Cloud Run service account:
   - Navigate to "IAM & Admin" → "IAM"
   - Find the Cloud Run service account (e.g., `PROJECT_ID-compute@developer.gserviceaccount.com`)
   - Add the "Calendar API Editor" role or create a custom role with Calendar permissions

**Note**: The application will automatically use Application Default Credentials when no service account JSON is provided.

#### For Local Development

For local development, you need to create a service account JSON file:

1. In the Google Cloud Console, navigate to "IAM & Admin" → "Service Accounts"
2. Click "Create Service Account"
3. Fill in the details and click "Create"
4. Grant the "Editor" role (or custom role with Calendar permissions)
5. Click "Done"
6. Create a key:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" → "Create New Key"
   - Select "JSON" format
   - Save the JSON file securely
7. Set the path in your `.env` file: `GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json`

**Optional - Domain-Wide Delegation** (for accessing user calendars):
1. In the service account details, click "Show Domain-Wide Delegation"
2. Enable "Domain-Wide Delegation"
3. Go to your Google Workspace Admin Console
4. Navigate to Security → API Controls → Domain-wide Delegation
5. Add the service account Client ID
6. Grant the following scopes:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`

**Note**: Domain-wide delegation requires a service account JSON file and is not supported with Application Default Credentials.

### 5. Set Up Sentry (Optional but Recommended)

Sentry provides error tracking and performance monitoring for your application.

1. Go to [sentry.io](https://sentry.io) and create an account (free tier available)
2. Create a new project and select "Python" as the platform
3. Copy your DSN (Data Source Name) from the project settings
4. Add it to your `.env` file (see next step)

**What Sentry provides:**
- Real-time error tracking with full stack traces
- Performance monitoring and tracing
- Breadcrumbs showing user actions leading to errors
- Email/Slack notifications for new errors
- Error grouping and deduplication

### 6. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Google Configuration (optional for Cloud Run)
# For local development only - Cloud Run uses service account identity automatically
# GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/your-service-account.json

# Meeting Defaults (optional, these are the defaults)
DEFAULT_MEETING_DURATION=60
MIN_REACTIONS=2
DEFAULT_REACTION_EMOJI=white_check_mark

# Business Hours (24-hour format HH:MM)
BUSINESS_HOURS_START=09:00
BUSINESS_HOURS_END=17:00

# Availability Search Settings
MAX_DAYS_AHEAD=14

# Application Settings
LOG_LEVEL=INFO

# Sentry Configuration (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=1.0
SENTRY_PROFILES_SAMPLE_RATE=1.0
```

**Note**: If you don't set `SENTRY_DSN`, the application will run normally without Sentry integration.

### 7. Run the Application

```bash
# Using uv
uv run python -m src.main

# Or activate the virtual environment and run
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m src.main
```

You should see output indicating the app is running:

```
Starting Meeting Scheduler application
Configuration: duration=30m, min_reactions=1, business_hours=09:00-17:00
Handlers registered, starting Socket Mode connection...
```

## Usage

### CLI Testing (Without Slack)

For local testing without deploying to Slack or Cloud Run, use the built-in CLI:

```bash
# Test scheduling at a specific time (dry run - doesn't create event)
uv run python -m src.cli schedule \
  --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \
  --time "tomorrow 2pm" \
  --duration 30 \
  --timezone "America/New_York"

# Test finding optimal availability (dry run)
uv run python -m src.cli find \
  --attendees "alice@example.com:America/New_York,bob@example.com:Europe/London" \
  --duration 60 \
  --search-days 7 \
  --min-attendees 2 \
  --timezone "America/New_York"

# Actually create a calendar event (remove --dry-run or use --no-dry-run)
uv run python -m src.cli schedule \
  --attendees "alice@example.com:America/New_York" \
  --time "tomorrow 3pm" \
  --timezone "America/New_York" \
  --no-dry-run
```

**CLI Options:**

**`schedule` command** - Schedule at a specific time:
- `--attendees`: Comma-separated list of `email:timezone` pairs (required)
- `--time`: Meeting time in natural language (required) e.g., "tomorrow 2pm", "Jan 20 at 3:30pm"
- `--timezone`: Timezone for interpreting the time (default: UTC)
- `--duration`: Meeting duration in minutes (default: 30)
- `--dry-run` / `--no-dry-run`: Dry run mode (default: true)
- `-v` / `--verbose`: Enable verbose logging

**`find` command** - Find optimal time:
- `--attendees`: Comma-separated list of `email:timezone` pairs (required)
- `--duration`: Meeting duration in minutes (default: 30)
- `--search-days`: Number of days ahead to search (default: 14)
- `--min-attendees`: Minimum attendees required (default: 1)
- `--timezone`: Reference timezone for business hours (default: UTC)
- `--dry-run` / `--no-dry-run`: Dry run mode (default: true)
- `-v` / `--verbose`: Enable verbose logging

**Notes:**
- CLI mode doesn't require Slack tokens (SLACK_BOT_TOKEN and SLACK_APP_TOKEN are optional)
- You still need Google Calendar credentials (GOOGLE_SERVICE_ACCOUNT_PATH)
- By default, CLI runs in dry-run mode (won't create events). Use `--no-dry-run` to actually create events.
- Attendee emails should be valid Google accounts for calendar integration to work

### Slash Command

Use the `/schedule-meet` command in any Slack channel:

**Format:**
```
/schedule-meet [reaction-time] [mode] [options]
```

**Examples:**

Schedule for a specific time:
```
/schedule-meet 5m tomorrow 2pm
/schedule-meet 1h Jan 20 at 3:30pm
/schedule-meet 30m next Monday 10am duration:60m
/schedule-meet 2h tomorrow 3pm min:3
```

Find optimal availability:
```
/schedule-meet 5m find-time
/schedule-meet 1h find-time duration:45m
/schedule-meet 30m find-time min:2
```

**Parameters:**
- **reaction-time** (required): How long to collect reactions
  - Format: `5m` (minutes), `1h` (hours), `30s` (seconds)
- **mode**: Either a specific date/time OR `find-time`
  - Specific time: Natural language like "tomorrow 2pm", "Jan 20 at 3:30pm"
  - Find time: Use `find-time` keyword
- **duration:Xm** (optional): Meeting duration in minutes (default: 30)
- **min:N** (optional): Minimum reactions required (default: 1)

### App Mention

You can also mention the bot:

```
@MeetingBot 5m tomorrow 2pm
@MeetingBot 1h find-time min:3
```

### Workflow

1. **Post Command**: User runs `/schedule-meet` with parameters
2. **Collect Reactions**: App posts a message and collects 👍 reactions for the specified duration
3. **Check Minimum**: Verifies enough people reacted
4. **Schedule Meeting**:
   - **Specific Time**: Creates meeting at the specified time
   - **Find Availability**: Queries calendars and finds optimal time
5. **Create Event**: Creates Google Calendar event with Meet link
6. **Send Invites**: Sends calendar invitations to all participants
7. **Post Results**: Posts meeting details back to Slack

## Architecture

```
src/
├── main.py                    # Application entry point
├── config.py                  # Configuration management
├── slack/                     # Slack integration
│   ├── app.py                 # Slack Bolt app setup
│   ├── handlers.py            # Command/mention handlers
│   ├── command_parser.py      # Command text parsing
│   ├── reactions.py           # Reaction tracking
│   └── utils.py               # Slack utilities
├── google/                    # Google Calendar integration
│   ├── auth.py                # Service account auth
│   └── calendar_client.py     # Calendar API client
├── scheduling/                # Scheduling logic
│   ├── engine.py              # Scheduling algorithm
│   ├── availability.py        # Availability checking
│   ├── parser.py              # Date/time parsing
│   └── timezone_handler.py    # Timezone utilities
├── models/                    # Data models
│   ├── meeting_request.py
│   ├── time_slot.py
│   └── scheduling_mode.py
└── coordinator/               # Workflow coordination
    └── meeting_coordinator.py
```

## Scheduling Algorithm

When using "find-time" mode, the app uses a scored ranking algorithm:

1. **Generate Candidates**: Create 30-minute increment slots during business hours
2. **Filter by Timezone**: Ensure slots work for all attendees' timezones
3. **Query Availability**: Check Google Calendar for busy periods
4. **Score Slots**: Assign points based on:
   - Base: 100 points per available attendee
   - Bonus: +10 per day earlier in the week
   - Bonus: +20 for mid-day slots (11am-2pm)
   - Penalty: -10 for edge hours (9-10am, 4-5pm)
5. **Select Optimal**: Choose highest-scoring slot meeting minimum attendees

## Limitations (MVP)

- **State Persistence**: In-memory only - pending requests are lost on app restart
- **Weekend Handling**: Currently skips all weekends, no custom workweek configuration
- **Recurring Meetings**: Not supported
- **Multiple Options**: Can't present multiple time options for voting
- **Pre-flight Checks**: Doesn't check availability before scheduling specific times

## Error Tracking and Monitoring

The application includes Sentry integration for comprehensive error tracking and performance monitoring.

### What Gets Tracked

**Automatically Captured:**
- All unhandled exceptions with full stack traces
- Logging messages at ERROR level
- Performance metrics and traces
- API call durations

**Custom Context:**
- User ID who initiated the meeting request
- Scheduling mode (specific time vs find availability)
- Channel ID where the request was made
- Meeting parameters (duration, min reactions, etc.)

### Viewing Errors in Sentry

When an error occurs:
1. Log into your Sentry dashboard
2. Navigate to "Issues" to see grouped errors
3. Click on an issue to see:
   - Full stack trace
   - User who triggered the error
   - Environment and release information
   - Breadcrumbs (recent logs and actions)
   - Tags for filtering (scheduling_mode, channel_id, etc.)

### Configuration

Adjust Sentry behavior via environment variables:
- `SENTRY_ENVIRONMENT`: Set to `development`, `staging`, or `production`
- `SENTRY_TRACES_SAMPLE_RATE`: Percentage of transactions to trace (0.0-1.0)
- `SENTRY_PROFILES_SAMPLE_RATE`: Percentage of transactions to profile (0.0-1.0)

**Tip**: In production, you may want to reduce sample rates (e.g., 0.1 = 10%) to reduce data usage while still catching issues.

## Troubleshooting

### "Could not retrieve email addresses for participants"

**Cause**: The Slack app doesn't have the `users:read.email` scope.

**Solution**:
1. Go to your Slack app settings
2. Navigate to "OAuth & Permissions"
3. Add the `users:read.email` scope
4. Reinstall the app to your workspace

### "Failed to query calendar availability"

**Possible causes**:
- Service account doesn't have Calendar API enabled
- Service account JSON file is invalid or not accessible
- Domain-wide delegation not set up correctly

**Solution**:
- Verify Calendar API is enabled in Google Cloud Console
- Check `GOOGLE_SERVICE_ACCOUNT_PATH` points to valid JSON file
- Review service account permissions

### "No slot found with minimum attendees"

**Cause**: No time found when enough people are available within the search window.

**Solutions**:
- Reduce minimum attendees requirement: `/schedule-meet 5m find-time min:2`
- Ask participants to update their calendars
- Try scheduling for a specific time instead

### Timezone issues

**Symptoms**: Meetings scheduled at wrong times, business hours not respected

**Checks**:
- Verify users have timezone set in their Slack profile
- Check `BUSINESS_HOURS_START` and `BUSINESS_HOURS_END` are in 24-hour format
- Ensure `MAX_DAYS_AHEAD` is reasonable (default: 14 days)

## Development

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run black src/
uv run ruff check src/
```

### Type Checking

```bash
uv run mypy src/
```

## Deployment

### Deploy to Cloud Run

The application is designed to run on Google Cloud Run with minimal configuration.

**Prerequisites:**
- Google Cloud project with billing enabled
- `gcloud` CLI installed and configured
- Calendar API enabled (see setup instructions above)

**Steps:**

1. Create a Dockerfile (if not already present):

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN uv sync --frozen

# Run the application
CMD ["uv", "run", "python", "-m", "src.main"]
```

2. Set environment variables as Cloud Run secrets or environment variables:

```bash
# Create secrets for sensitive values
gcloud secrets create slack-bot-token --data-file=- <<< "xoxb-your-bot-token"
gcloud secrets create slack-app-token --data-file=- <<< "xapp-your-app-token"
gcloud secrets create sentry-dsn --data-file=- <<< "https://your-sentry-dsn"

# Deploy to Cloud Run
gcloud run deploy slack-meeting-scheduler \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets=SLACK_BOT_TOKEN=slack-bot-token:latest,SLACK_APP_TOKEN=slack-app-token:latest,SENTRY_DSN=sentry-dsn:latest \
  --set-env-vars="LOG_LEVEL=INFO,SENTRY_ENVIRONMENT=production,DEFAULT_MEETING_DURATION=30,MIN_REACTIONS=1,BUSINESS_HOURS_START=09:00,BUSINESS_HOURS_END=17:00,MAX_DAYS_AHEAD=14"
```

3. Grant Calendar API permissions to the Cloud Run service account:

```bash
# Get the Cloud Run service account email
gcloud run services describe slack-meeting-scheduler --region us-central1 --format="value(spec.template.spec.serviceAccountName)"

# Or use the default compute service account
# PROJECT_NUMBER-compute@developer.gserviceaccount.com

# Grant Calendar permissions (do this in the Google Cloud Console under IAM)
```

**Important Notes:**
- No service account JSON file is needed - Cloud Run automatically provides credentials via Application Default Credentials
- The Cloud Run service account needs Calendar API permissions
- Socket Mode requires a persistent connection, so ensure your Cloud Run service doesn't timeout
- Consider using Cloud Run with minimum instances (1+) to maintain the Socket Mode connection
- Monitor logs and errors through Sentry and Google Cloud Logging

### Environment Variables for Cloud Run

When deploying to Cloud Run, set these environment variables:

**Required:**
- `SLACK_BOT_TOKEN` - Slack bot OAuth token (xoxb-...)
- `SLACK_APP_TOKEN` - Slack app token for Socket Mode (xapp-...)

**Optional:**
- `LOG_LEVEL` - Logging level (default: INFO)
- `SENTRY_DSN` - Sentry DSN for error tracking
- `SENTRY_ENVIRONMENT` - Environment name (e.g., production, staging)
- `SENTRY_TRACES_SAMPLE_RATE` - Traces sample rate (0.0-1.0, default: 1.0)
- `SENTRY_PROFILES_SAMPLE_RATE` - Profiles sample rate (0.0-1.0, default: 1.0)
- `DEFAULT_MEETING_DURATION` - Default meeting duration in minutes (default: 30)
- `MIN_REACTIONS` - Default minimum reactions (default: 1)
- `DEFAULT_REACTION_EMOJI` - Default reaction emoji (default: white_check_mark)
- `BUSINESS_HOURS_START` - Business hours start time HH:MM (default: 09:00)
- `BUSINESS_HOURS_END` - Business hours end time HH:MM (default: 17:00)
- `MAX_DAYS_AHEAD` - Max days to search for availability (default: 14)

**Not Needed:**
- `GOOGLE_SERVICE_ACCOUNT_PATH` - Not needed on Cloud Run
- `GOOGLE_SERVICE_ACCOUNT_JSON` - Not needed on Cloud Run

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review logs for error messages

## Future Enhancements

- Persistent state storage (Redis/database)
- Custom business hours per user
- Recurring meeting support
- Interactive buttons for confirming/canceling
- Multiple time option voting
- Meeting templates
- Admin commands
- Analytics and usage tracking
