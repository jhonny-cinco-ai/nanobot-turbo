"""Cron tool for scheduling reminders, tasks, and routing calibration."""

from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.cron.service import CronService
from nanobot.cron.types import CronPayload, CronSchedule


class CronTool(Tool):
    """
    Tool to schedule reminders, recurring tasks, and routing calibration.
    
    Supports two job types:
    1. User reminders (delivered back to user via chat/channel)
    2. System calibration (optimizes routing performance in background)
    """
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return (
            "Schedule reminders, recurring tasks, and routing calibration. "
            "Actions: add (reminders/tasks), calibrate (routing optimization), list, remove. "
            "Use 'calibrate' to schedule automatic routing performance optimization."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "calibrate", "list", "remove"],
                    "description": "Action to perform: 'add' for reminders/tasks, 'calibrate' for routing optimization"
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message or task description (for add action)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (e.g., 3600 for hourly, 86400 for daily)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression for precise scheduling (e.g., '0 2 * * *' for 2am daily)"
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution (e.g. '2026-02-12T10:30:00')"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID to remove (for remove action)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        at: str | None = None,
        job_id: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            return self._add_job(message, every_seconds, cron_expr, at)
        elif action == "calibrate":
            return self._add_calibration_job(every_seconds, cron_expr)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"
    
    def _add_job(self, message: str, every_seconds: int | None, cron_expr: str | None, at: str | None) -> str:
        """Add a user reminder or task job."""
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        
        # Build schedule
        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
        elif at:
            from datetime import datetime
            dt = datetime.fromisoformat(at)
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"
        
        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after,
        )
        return f"Created reminder '{job.name}' (id: {job.id}). You'll receive this message as scheduled."
    
    def _add_calibration_job(self, every_seconds: int | None, cron_expr: str | None) -> str:
        """
        Add a routing calibration job to optimize classification performance.
        
        Calibration analyzes classification history and improves routing accuracy
        over time by learning from successful LLM classifications.
        
        This is a system job that runs in background - no user delivery.
        """
        # Default to daily calibration if no schedule specified
        if not every_seconds and not cron_expr:
            # Default: daily at 2:00 AM
            cron_expr = "0 2 * * *"
            schedule = CronSchedule(kind="cron", expr=cron_expr)
            schedule_desc = "daily at 2:00 AM"
        elif every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
            # Format description
            if every_seconds < 3600:
                schedule_desc = f"every {every_seconds} seconds"
            elif every_seconds < 86400:
                hours = every_seconds / 3600
                schedule_desc = f"every {hours:.1f} hours" if hours != int(hours) else f"every {int(hours)} hours"
            else:
                days = every_seconds / 86400
                schedule_desc = f"every {days:.1f} days" if days != int(days) else f"every {int(days)} days"
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
            schedule_desc = f"on schedule '{cron_expr}'"
        else:
            return "Error: either every_seconds or cron_expr is required"
        
        # Create calibration job - system job, no delivery to user
        job = self._cron.add_job(
            name="Routing Calibration",
            schedule=schedule,
            message="CALIBRATE_ROUTING",  # Special marker for calibration
            deliver=False,  # System job, don't deliver to user
            channel="internal",
            to="calibration",
        )
        
        return (
            f"✓ Scheduled routing calibration {schedule_desc} (job id: {job.id}).\n\n"
            f"This will automatically optimize message routing based on classification history, "
            f"improving accuracy and reducing costs over time. "
            f"Calibration runs in the background - you'll see improvements gradually."
        )
    
    def _list_jobs(self) -> str:
        """List all jobs - separate user reminders from system calibration."""
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        
        # Separate user jobs from calibration jobs
        user_jobs = []
        calibration_jobs = []
        
        for job in jobs:
            if job.payload.message == "CALIBRATE_ROUTING":
                calibration_jobs.append(job)
            else:
                user_jobs.append(job)
        
        lines = []
        
        # Show user reminders first
        if user_jobs:
            lines.append("📅 Your Reminders:")
            for job in user_jobs:
                lines.append(f"  • {job.name} (id: {job.id}, {job.schedule.kind})")
        
        # Show calibration jobs
        if calibration_jobs:
            if user_jobs:
                lines.append("")
            lines.append("🔧 System Calibration:")
            for job in calibration_jobs:
                lines.append(f"  • {job.name} (id: {job.id}, {job.schedule.kind})")
        
        return "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
