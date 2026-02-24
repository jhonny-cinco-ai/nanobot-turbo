# Timezone UX Design for Non-Technical Users

## Problem Solved

**Traditional approach** (bad UX for non-technical users):
- User: "Remind me at 9 AM"
- System: "What timezone?"
- User: Confused 😕

**Our solution** (great UX):
- User: "Remind me at 9 AM"
- System: Uses their configured timezone automatically ✅

**Where it's stored**: User's workspace `USER.md` file (not in config.json)
- Single source of truth for user preferences
- Agent reads USER.md as context, understands timezone naturally
- Easy for user to edit: just update one file

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ User Sets Timezone in USER.md (Workspace/USER.md)           │
│ - Timezone: America/New_York                                │
│ - Language: English                                         │
│ - Communication style: casual                               │
└────────────────────────────┬─────────────────────────────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
                   ▼                   ▼
        ┌──────────────────┐ ┌──────────────────────┐
        │ Agent Reads      │ │ CronTool Gets        │
        │ USER.md Context  │ │ Timezone via         │
        │ (for AI prompts) │ │ get_user_timezone()  │
        └────────┬─────────┘ └──────────┬───────────┘
                 │                      │
                 └──────────┬───────────┘
                            │
                            ▼
        ┌─────────────────────────────────────────┐
        │ CronTool Initialized with System TZ     │
        │ _default_timezone = "America/New_York"  │
        └────────────────┬──────────────────────┘
                         │
           ┌─────────────┴────────────────┐
           │                              │
           ▼                              ▼
   ┌──────────────┐          ┌─────────────────────┐
   │ User asks AI │          │ AI Reads USER.md    │
   │ "9 AM daily" │          │ Sees timezone      │
   └──────┬───────┘          │ Understands context │
          │                  └────────┬────────────┘
          │                           │
          └───────────┬───────────────┘
                      ▼
    ┌─────────────────────────────────────┐
    │ CronTool Creates Job:               │
    │ expr: "0 9 * * *"                   │
    │ tz: "America/New_York"              │
    └─────────────────────────────────────┘
```

**Key Advantage**: USER.md is part of the agent's context, so the AI naturally understands timezone from what it reads!

## User Journey

### 1. First Setup (One-Time)
```
User installs nanofolks
  → Edit config or run setup
  → Set timezone: "America/New_York"
  → Done! ✅
```

### 2. Creating Reminders (Ongoing)
```
User: "Remind me at 9 AM every weekday"

System (internal):
  1. Parse request
  2. Create schedule expression: "0 9 * * 1-5"
  3. Get system_timezone from config: "America/New_York"
  4. Create CronSchedule(expr="...", tz="America/New_York")
  5. Save to routines
  6. Execute at 9 AM EST

Result: No timezone confusion, works automatically ✅
```

### 3. Optional: Override for Specific Job
```
User: "Remind me at 2 PM Tokyo time"

System (internal):
  1. Parse timezone mention: "Tokyo time"
  2. Extract timezone: "Asia/Tokyo"
  3. Create CronSchedule(expr="...", tz="Asia/Tokyo")
  4. Override default for this job only
  5. Store with custom timezone

Result: Job uses Asia/Tokyo, other jobs still use America/New_York ✅
```

## USER.md Format

### Default Template (Fresh Install)
```markdown
# User

Information about the user goes here.

## Preferences

- Communication style: casual
- Timezone: UTC
- Language: English

## About You

Add your preferences, constraints, and communication style here. This helps the AI understand how to interact with you.
```

### After User Setup
```markdown
# User

Information about the user goes here.

## Preferences

- Communication style: casual
- Timezone: America/New_York
- Language: English

## About You

I prefer clear, concise communication. I'm in the US Eastern timezone.
I work 9-5 Monday-Friday. Please remind me about meetings 30 minutes before.
```

## Implementation Details

Note: "cron" here refers to the internal routines scheduler. User-facing scheduling is exposed as **routines**.

### RoutinesTool Constructor
```python
def __init__(self, routine_service: RoutineService, default_timezone: str = "UTC"):
    self._routines = routine_service
    self._default_timezone = default_timezone  # From config
```

### Job Creation Logic
```python
def _add_routine(self, message, every_seconds, schedule, cron_expr, at, timezone=None):
    # User-provided timezone OR fallback to default
    effective_tz = timezone or self._default_timezone
    
    if schedule:
        # Create schedule with effective timezone
        schedule = RoutineSchedule(kind="cron", expr=schedule, tz=effective_tz)
```

## Future Enhancement: AI Timezone Detection

Could enhance AI agent to:
1. Detect user location (IP geolocation)
2. Detect system timezone
3. Ask user to confirm: "I detected you're in New York. Use America/New_York?"
4. Auto-set system_timezone on first run

This would make setup even more automatic for non-technical users.

## Testing Scenarios

| Scenario | User Action | Expected Behavior |
|----------|-------------|-------------------|
| New user | System timezone = "UTC" (default) | Jobs run in UTC |
| User sets timezone | Edit config to "America/New_York" | All jobs run in EST/EDT |
| User says "9 AM" | No timezone mentioned | Uses system_timezone |
| User says "9 AM EST" | Timezone mentioned | Override system_timezone for this job |
| Multiple timezones | Some jobs EST, some JST | Each job respects its own timezone |
| Sync across devices | User travels, local time changes | Jobs still run at configured time (UTC-based, then converted to local) |

## Benefits

✅ **Non-technical users don't have to think about timezones**
✅ **Default sensible behavior (UTC or detected local timezone)**
✅ **Can override when needed (multi-timezone scenarios)**
✅ **Jobs stored as UTC internally (portable)**
✅ **Natural language understanding by AI agent**
✅ **One-time setup, works forever**

## Implementation Files

- `nanofolks/utils/user_profile.py` - `get_user_timezone()` function
- `nanofolks/agent/tools/routines.py` - RoutinesTool with timezone support
- `nanofolks/agent/loop.py` - Passes timezone to RoutinesTool
- `nanofolks/cli/commands.py` - Reads from USER.md on startup
- `nanofolks/agent/context.py` - Already loads USER.md into context

## Related Documentation

- [CRON_TIMEZONE_IMPLEMENTATION.md](./CRON_TIMEZONE_IMPLEMENTATION.md) - Technical details
- USER.md template in workspace - User preferences (auto-created on setup)
