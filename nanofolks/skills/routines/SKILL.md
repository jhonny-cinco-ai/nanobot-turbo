---
name: routines
description: Schedule routines, reminders, and recurring tasks.
---

# Routines

Use the `routines` tool to schedule reminders or recurring tasks.

## Three Modes

1. **Reminder** - message is sent directly to user
2. **Task** - message is a task description, agent executes and sends result
3. **One-time** - runs once at a specific time, then auto-deletes

## Examples

Fixed reminder:
```
routines(action="add", message="Time to take a break!", every_seconds=1200)
```

Dynamic task (agent executes each time):
```
routines(action="add", message="Check HKUDS/nanofolks GitHub stars and report", every_seconds=600)
```

One-time scheduled task (compute ISO datetime from current time):
```
routines(action="add", message="Remind me about the meeting", at="<ISO datetime>")
```

Timezone-aware cron:
```
routines(action="add", message="Morning standup", schedule="0 9 * * 1-5", timezone="America/Vancouver")
```

List/remove:
```
routines(action="list")
routines(action="remove", job_id="abc123")
```

## Time Expressions

| User says | Parameters |
|-----------|------------|
| every 20 minutes | every_seconds: 1200 |
| every hour | every_seconds: 3600 |
| every day at 8am | schedule: "0 8 * * *" |
| weekdays at 5pm | schedule: "0 17 * * 1-5" |
| 9am Vancouver time daily | schedule: "0 9 * * *", timezone: "America/Vancouver" |
| at a specific time | at: ISO datetime string (compute from current time) |

## Timezone

Use `timezone` with `schedule` to run in a specific IANA timezone. Without it, the server's local timezone is used.
