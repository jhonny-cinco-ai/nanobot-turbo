# Cron Timezone Implementation (Internal Routines Engine)

## Overview

Implemented timezone-aware scheduling for the internal routines engine (legacy cron), based on commit d3f6c95 from the upstream repository.

Note: "cron" here refers to the internal scheduler. User-facing scheduling is exposed as **routines**.

**Key Design**: Uses a global **system_timezone** setting that applies to all routines, optimized for non-technical users who interact through the AI agent.

## Changes Made

### 1. **Cron Service (`nanofolks/routines_engine/service.py`)**

#### Imports Added
- `datetime` module
- `ZoneInfo` from `zoneinfo` module (Python 3.9+)

#### `_compute_next_run()` Function Enhanced
- **Old behavior**: Used Unix timestamps without timezone awareness
- **New behavior**: 
  - Respects `schedule.tz` if specified
  - Falls back to local timezone using `datetime.now().astimezone().tzinfo`
  - Uses datetime-aware croniter calculations instead of raw timestamps
  - Improved error logging for debugging timezone issues

```python
# Simplified cron logic now uses:
tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
base_dt = datetime.fromtimestamp(base_time, tz=tz)
cron = croniter(schedule.expr, base_dt)
next_dt = cron.get_next(datetime)
return int(next_dt.timestamp() * 1000)
```

### 2. **CLI Interface (`nanofolks/cli/commands.py`)**

Added `--tz` parameter to `routines add` command:

```bash
# Usage examples:
nanofolks routines add --name "Morning Briefing" --schedule "0 9 * * *" --tz "America/New_York" --message "What's on my calendar?"

nanofolks routines add --name "Tokyo Check" --schedule "0 17 * * *" --tz "Asia/Tokyo" --message "Status update"

# Defaults to local timezone if --tz not specified
nanofolks routines add --name "Local Job" --schedule "0 14 * * *" --message "Reminder"
```

### 3. **Agent Tool (`nanofolks/agent/tools/routines.py`)**

#### Constructor Enhanced
- Added `default_timezone` parameter (defaults to "UTC")
- Stores user's configured timezone from config

#### Description Updated
- Added timezone support to tool description
- Mentions supported timezone formats

#### Parameters Enhanced
- Added `timezone` parameter to tool's JSON schema (optional)
- If omitted, uses user's configured `system_timezone`
- Allows override for multi-timezone scenarios

#### Methods Updated
- `execute()`: Accepts optional `timezone` parameter
- `_add_routine()`: Uses user's default timezone if not specified
- `_add_calibration_routine()`: Uses user's default timezone for background jobs

### 4. **User Profile Utility (`nanofolks/utils/user_profile.py`)**

New utility functions:
- `get_user_timezone(workspace)` - Extracts timezone from USER.md
- `set_user_timezone(workspace, tz)` - Updates timezone in USER.md

**How it works**:
1. Reads workspace/USER.md
2. Looks for "Timezone: <value>" line (case-insensitive)
3. Returns timezone or "UTC" if not found
4. Handles errors gracefully

**Why USER.md instead of config.json**:
- USER.md is already loaded into agent's context
- Agent can read and understand user preferences naturally
- Single source of truth for user data
- Easy for non-technical users to edit

### 5. **Agent Loop (`nanofolks/agent/loop.py`)**

- Receives `system_timezone` parameter
- Passes it to `CronTool` during initialization
- Ensures all cron operations use user's timezone

## Backward Compatibility

✅ **Fully backward compatible**
- Jobs without `tz` parameter automatically use local timezone
- Existing jobs continue to work without modification
- `CronSchedule.tz` defaults to `None`, triggering local timezone fallback

## Supported Timezones

Standard IANA timezone identifiers:
- **Americas**: `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`
- **Europe**: `Europe/London`, `Europe/Paris`, `Europe/Berlin`, `Europe/Moscow`
- **Asia**: `Asia/Tokyo`, `Asia/Shanghai`, `Asia/Hong_Kong`, `Asia/Singapore`, `Asia/Dubai`, `Asia/Kolkata`
- **Australia**: `Australia/Sydney`, `Australia/Melbourne`
- **Pacific**: `Pacific/Auckland`, `Pacific/Fiji`
- **UTC**: `UTC`, `Etc/UTC`

## Usage Examples

### Setup: Set User Timezone (One-Time)

Edit `workspace/USER.md`:
```markdown
## Preferences

- Communication style: casual
- Timezone: America/New_York
- Language: English
```

That's it! The system will automatically read this on startup.

### Via CLI
```bash
# Uses the configured system_timezone automatically
nanofolks routines add --name "Morning Check" \
  --schedule "0 9 * * *" \
  --message "What needs attention today?"

# Override for specific timezone if needed
nanofolks routines add --name "Tokyo Check" \
  --schedule "0 9 * * *" \
  --tz "Asia/Tokyo" \
  --message "Tokyo office status"
```

### Via Agent/Tool (Recommended for Non-Technical Users)

User naturally asks: "Remind me at 9 AM every weekday"

The AI agent automatically:
1. Gets user's `system_timezone` from config (e.g., "America/New_York")
2. Creates job with that timezone
3. No timezone questions needed

```python
# Agent uses system_timezone by default - no override needed
await cron_tool.execute(
    action="add",
    message="Team standup",
    cron_expr="0 10 * * 1-5"  # Weekdays at 10 AM (uses system_timezone)
)

# Can override if user mentions specific timezone
await cron_tool.execute(
    action="add",
    message="Tokyo office check",
    cron_expr="0 9 * * 1-5",
    timezone="Asia/Tokyo"  # Override for this specific job
)

# Calibration also uses system_timezone
await cron_tool.execute(
    action="calibrate",
    cron_expr="0 2 * * *"  # Daily 2 AM in user's timezone
)
```

## Implementation Notes

1. **Datetime Calculation**: Cron expressions are now evaluated in the specified timezone, matching user expectations
2. **Timestamp Conversion**: Times are still stored as milliseconds since epoch (UTC), ensuring portable persistence
3. **Error Handling**: Invalid timezone names log warnings but don't crash (uses local timezone as fallback)
4. **Validation**: Timezone validation happens at cron execution time via `ZoneInfo`

## Testing Recommendations

```python
# Test timezone-aware scheduling
schedule = CronSchedule(kind="cron", expr="0 9 * * *", tz="America/New_York")
next_run = _compute_next_run(schedule, time.time() * 1000)

# Test local timezone fallback
schedule = CronSchedule(kind="cron", expr="0 9 * * *", tz=None)
next_run = _compute_next_run(schedule, time.time() * 1000)

# Test invalid timezone handling
schedule = CronSchedule(kind="cron", expr="0 9 * * *", tz="Invalid/Zone")
next_run = _compute_next_run(schedule, time.time() * 1000)  # Should use local TZ
```

## Files Modified

1. `nanofolks/routines_engine/service.py` - Core timezone-aware scheduling
2. `nanofolks/routines_engine/types.py` - Already had `tz` field (no changes)
3. `nanofolks/utils/user_profile.py` - **NEW** - Extract timezone from USER.md
4. `nanofolks/agent/tools/routines.py` - Routines tool with timezone support
5. `nanofolks/agent/loop.py` - Pass timezone to CronTool
6. `nanofolks/cli/commands.py` - Reads timezone from USER.md via `get_user_timezone()`

## Related Commit

Based on upstream commit: `d3f6c95cebaf17d04f0d04655a98c0e795777bb1`

Adapted to match nanofolks-turbo's architecture with both agent-based and CLI-based scheduling interfaces.
