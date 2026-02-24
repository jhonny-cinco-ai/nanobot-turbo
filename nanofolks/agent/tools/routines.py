"""Routines tool for scheduling reminders and team routines."""

from typing import Any

from nanofolks.agent.tools.base import Tool
from nanofolks.routines.models import RoutineSchedule
from nanofolks.routines.service import RoutineService


class RoutinesTool(Tool):
    """
    Tool to schedule reminders, recurring tasks, and routing calibration.

    Actions:
    - add: user routines (reminders/tasks)
    - calibrate: system routine for routing optimization
    - list: list routines (user + system)
    - remove: remove a routine by id
    """

    def __init__(self, routine_service: RoutineService, default_timezone: str = "UTC"):
        self._routines = routine_service
        self._channel = ""
        self._chat_id = ""
        self._default_timezone = default_timezone

    def set_context(self, channel: str, chat_id: str) -> None:
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "routines"

    @property
    def description(self) -> str:
        return (
            "Schedule routines and reminders with timezone support. "
            "Actions: add, calibrate, list, remove. "
            "Use 'calibrate' to schedule routing optimization."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "calibrate", "list", "remove"],
                    "description": "Action to perform"
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message or task description (for add)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (e.g., 3600 for hourly)"
                },
                "schedule": {
                    "type": "string",
                    "description": "Schedule expression, e.g. '0 2 * * *'"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Deprecated alias for schedule"
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone for schedule (e.g., 'America/New_York')"
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')"
                },
                "job_id": {
                    "type": "string",
                    "description": "Routine ID to remove (for remove)"
                }
            },
            "required": ["action"]
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        schedule: str | None = None,
        cron_expr: str | None = None,
        timezone: str | None = None,
        at: str | None = None,
        job_id: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_routine(message, every_seconds, schedule, cron_expr, at, timezone)
        if action == "calibrate":
            return self._add_calibration_routine(every_seconds, schedule, cron_expr, timezone)
        if action == "list":
            return self._list_routines()
        if action == "remove":
            return self._remove_routine(job_id)
        return f"Unknown action: {action}"

    def _add_routine(
        self,
        message: str,
        every_seconds: int | None,
        schedule: str | None,
        cron_expr: str | None,
        at: str | None,
        timezone: str | None = None,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"

        schedule_expr = schedule or cron_expr

        if timezone and not schedule_expr:
            return "Error: timezone can only be used with schedule expressions"
        if timezone:
            from zoneinfo import ZoneInfo
            try:
                ZoneInfo(timezone)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{timezone}'"

        effective_tz = timezone or self._default_timezone

        delete_after = False
        if every_seconds:
            schedule_obj = RoutineSchedule(kind="every", every_ms=every_seconds * 1000)
        elif schedule_expr:
            schedule_obj = RoutineSchedule(kind="cron", expr=schedule_expr, tz=effective_tz)
        elif at:
            from datetime import datetime
            dt = datetime.fromisoformat(at)
            at_ms = int(dt.timestamp() * 1000)
            schedule_obj = RoutineSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, schedule, or at is required"

        job = self._routines.add_routine(
            name=message[:30],
            schedule=schedule_obj,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            payload_kind="agent_turn",
            scope="user",
            routine="reminder",
            delete_after_run=delete_after,
        )
        return f"Created routine '{job.name}' (id: {job.id}). You'll receive this message as scheduled."

    def _add_calibration_routine(
        self,
        every_seconds: int | None,
        schedule: str | None,
        cron_expr: str | None,
        timezone: str | None = None,
    ) -> str:
        effective_tz = timezone or self._default_timezone
        schedule_expr = schedule or cron_expr

        if not every_seconds and not schedule_expr:
            schedule_expr = "0 2 * * *"
            schedule_obj = RoutineSchedule(kind="cron", expr=schedule_expr, tz=effective_tz)
            schedule_desc = "daily at 2:00 AM"
        elif every_seconds:
            schedule_obj = RoutineSchedule(kind="every", every_ms=every_seconds * 1000)
            if every_seconds < 3600:
                schedule_desc = f"every {every_seconds} seconds"
            elif every_seconds < 86400:
                hours = every_seconds / 3600
                schedule_desc = f"every {hours:.1f} hours" if hours != int(hours) else f"every {int(hours)} hours"
            else:
                days = every_seconds / 86400
                schedule_desc = f"every {days:.1f} days" if days != int(days) else f"every {int(days)} days"
        elif schedule_expr:
            schedule_obj = RoutineSchedule(kind="cron", expr=schedule_expr, tz=effective_tz)
            schedule_desc = f"on schedule '{schedule_expr}'"
        else:
            return "Error: either every_seconds or schedule is required"

        job = self._routines.add_routine(
            name="Routing Calibration",
            schedule=schedule_obj,
            message="CALIBRATE_ROUTING",
            deliver=False,
            channel="internal",
            to="calibration",
            payload_kind="system_event",
            scope="system",
            routine="calibration",
        )

        return (
            f"Scheduled routing calibration {schedule_desc} (routine id: {job.id}).\n\n"
            "This runs in the background to improve routing accuracy over time."
        )

    def _list_routines(self) -> str:
        jobs = self._routines.list_routines()
        if not jobs:
            return "No scheduled routines."

        user_jobs = []
        system_jobs = []

        for job in jobs:
            if job.payload.scope == "system":
                system_jobs.append(job)
            else:
                user_jobs.append(job)

        lines = []

        if user_jobs:
            lines.append("Your routines:")
            for job in user_jobs:
                lines.append(f"  - {job.name} (id: {job.id}, {job.schedule.kind})")

        if system_jobs:
            if user_jobs:
                lines.append("")
            lines.append("Team routines:")
            for job in system_jobs:
                lines.append(f"  - {job.name} (id: {job.id}, {job.schedule.kind})")

        return "\n".join(lines)

    def _remove_routine(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._routines.remove_routine(job_id):
            return f"Removed routine {job_id}"
        return f"Routine {job_id} not found"
