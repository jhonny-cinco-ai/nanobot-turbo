"""Room task management tool."""

from __future__ import annotations

from typing import Any, Optional

from nanofolks.agent.tools.base import Tool
from nanofolks.bots.room_manager import get_room_manager


class RoomTaskTool(Tool):
    """Manage room tasks (add, list, assign, update status)."""

    def __init__(self):
        self._room_id: str | None = None
        self._memory_store = None
        self._canceller = None

    def set_context(self, room_id: str | None) -> None:
        self._room_id = room_id

    def set_memory_store(self, memory_store) -> None:
        """Attach a memory store for logging task events."""
        self._memory_store = memory_store

    def set_canceller(self, canceller) -> None:
        """Attach a canceller callable for stopping room tasks."""
        self._canceller = canceller

    @property
    def name(self) -> str:
        return "room_task"

    @property
    def description(self) -> str:
        return "Manage room tasks: add, list, assign, handoff, update status, or stop running tasks."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "status", "assign", "handoff", "history", "stop"],
                    "description": "Task action to perform.",
                },
                "room_id": {
                    "type": "string",
                    "description": "Room ID (defaults to current room).",
                },
                "status": {
                    "type": "string",
                    "description": "Status filter or update value.",
                },
                "title": {
                    "type": "string",
                    "description": "Task title (for add).",
                },
                "owner": {
                    "type": "string",
                    "description": "Owner name (user or bot).",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for reassignment or handoff.",
                },
                "priority": {
                    "type": "string",
                    "description": "Priority: low, medium, high.",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date (YYYY-MM-DD).",
                },
                "task_id": {
                    "type": "string",
                    "description": "Task ID (prefix ok) for update/assign.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = (kwargs.get("action") or "").lower()
        room_id = (kwargs.get("room_id") or self._room_id or "general").strip()

        manager = get_room_manager()
        room = manager.get_room(room_id)
        if not room:
            return f"Error: Room '{room_id}' not found."

        if action == "list":
            status = kwargs.get("status")
            owner = kwargs.get("owner")
            tasks = room.list_tasks(status=status, owner=owner)
            if not tasks:
                if status:
                    return f"No tasks with status '{status}' in room '{room_id}'."
                if owner:
                    return f"No tasks owned by '{owner}' in room '{room_id}'."
                return f"No tasks in room '{room_id}'."
            lines = [f"Tasks for {room_id}:"]
            for task in tasks:
                lines.append(
                    f"- {task.id[:8]} | {task.title} | {task.owner} | {task.status}"
                )
            return "\n".join(lines)

        if action == "add":
            title = kwargs.get("title")
            if not title:
                return "Error: title is required for action 'add'."
            owner = kwargs.get("owner") or "user"
            status = kwargs.get("status") or "todo"
            priority = kwargs.get("priority") or "medium"
            due_date = kwargs.get("due_date")

            task = room.add_task(
                title=title,
                owner=owner,
                status=status,
                priority=priority,
                due_date=due_date,
            )
            manager._save_room(room)
            self._log_task_event(room_id, "add", task)
            return f"Added task {task.id[:8]} to {room_id}."

        if action == "status":
            task_id = kwargs.get("task_id")
            status = kwargs.get("status")
            if not task_id or not status:
                return "Error: task_id and status are required for action 'status'."
            task = _find_task_by_prefix(room, task_id)
            if not task:
                return f"Error: No task matching '{task_id}' in {room_id}."
            if not room.update_task_status(task.id, status):
                return f"Error: Failed to update task {task.id[:8]}."
            manager._save_room(room)
            self._log_task_event(room_id, "status", task, extra={"status": status})
            return f"Updated task {task.id[:8]} status → {status}."

        if action == "assign":
            task_id = kwargs.get("task_id")
            owner = kwargs.get("owner")
            reason = kwargs.get("reason")
            if not task_id or not owner:
                return "Error: task_id and owner are required for action 'assign'."
            task = _find_task_by_prefix(room, task_id)
            if not task:
                return f"Error: No task matching '{task_id}' in {room_id}."
            if not room.assign_task(task.id, owner, reason=reason):
                return f"Error: Failed to assign task {task.id[:8]}."
            manager._save_room(room)
            self._log_task_event(room_id, "assign", task, reason=reason)
            return f"Assigned task {task.id[:8]} → {owner}."

        if action == "handoff":
            task_id = kwargs.get("task_id")
            owner = kwargs.get("owner")
            reason = kwargs.get("reason")
            if not task_id or not owner:
                return "Error: task_id and owner are required for action 'handoff'."
            task = _find_task_by_prefix(room, task_id)
            if not task:
                return f"Error: No task matching '{task_id}' in {room_id}."
            if not room.handoff_task(task.id, owner, reason=reason):
                return f"Error: Failed to handoff task {task.id[:8]}."
            manager._save_room(room)
            self._log_task_event(room_id, "handoff", task, reason=reason)
            return f"Handoff recorded for {task.id[:8]} → {owner}."

        if action == "history":
            task_id = kwargs.get("task_id")
            if not task_id:
                return "Error: task_id is required for action 'history'."
            task = _find_task_by_prefix(room, task_id)
            if not task:
                return f"Error: No task matching '{task_id}' in {room_id}."
            handoffs = task.metadata.get("handoffs", [])
            if not handoffs:
                return f"No handoffs recorded for {task.id[:8]}."
            lines = [f"Handoffs for {task.id[:8]}:"]
            for handoff in handoffs:
                lines.append(
                    f"- {handoff.get('from')} -> {handoff.get('to')} | {handoff.get('reason', '')}"
                )
            return "\n".join(lines)

        if action == "stop":
            if not self._canceller:
                return "Error: stop is not available in this context."
            summary = self._canceller(room_id)
            return (
                "Stopped running tasks in room "
                f"'{room_id}'. "
                f"Cancelled invocations: {summary.get('invocations', 0)}, "
                f"sidekicks: {summary.get('sidekicks', 0)}."
            )

        return f"Error: Unknown action '{action}'."

    def _log_task_event(self, room_id: str, action: str, task: Any, reason: str | None = None,
                        extra: dict[str, Any] | None = None) -> None:
        if not self._memory_store:
            return
        try:
            import uuid
            from datetime import datetime

            from nanofolks.memory.models import Event
            from nanofolks.utils.ids import room_to_session_id

            metadata = {
                "task_id": task.id,
                "action": action,
                "owner": task.owner,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date,
            }
            if reason:
                metadata["reason"] = reason
            if extra:
                metadata.update(extra)

            content = (
                f"Task {action}: {task.title} "
                f"(owner: {task.owner}, status: {task.status})"
            )

            event = Event(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                channel="internal",
                direction="internal",
                event_type="task",
                content=content,
                session_key=room_to_session_id(room_id),
                metadata=metadata,
            )
            self._memory_store.save_event(event)
        except Exception:
            # Avoid hard failure in tool execution
            return


def _find_task_by_prefix(room, prefix: str) -> Optional[Any]:
    matches = [task for task in room.tasks if task.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None
