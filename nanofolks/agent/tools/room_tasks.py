"""Room task management tool."""

from __future__ import annotations

from typing import Any, Optional

from nanofolks.agent.tools.base import Tool
from nanofolks.bots.room_manager import get_room_manager


class RoomTaskTool(Tool):
    """Manage room tasks (add, list, assign, update status)."""

    def __init__(self):
        self._room_id: str | None = None

    def set_context(self, room_id: str | None) -> None:
        self._room_id = room_id

    @property
    def name(self) -> str:
        return "room_task"

    @property
    def description(self) -> str:
        return "Manage room tasks: add, list, assign, or update status."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "add", "status", "assign"],
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
            tasks = room.list_tasks(status=status)
            if not tasks:
                if status:
                    return f"No tasks with status '{status}' in room '{room_id}'."
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
            return f"Updated task {task.id[:8]} status → {status}."

        if action == "assign":
            task_id = kwargs.get("task_id")
            owner = kwargs.get("owner")
            if not task_id or not owner:
                return "Error: task_id and owner are required for action 'assign'."
            task = _find_task_by_prefix(room, task_id)
            if not task:
                return f"Error: No task matching '{task_id}' in {room_id}."
            if not room.assign_task(task.id, owner):
                return f"Error: Failed to assign task {task.id[:8]}."
            manager._save_room(room)
            return f"Assigned task {task.id[:8]} → {owner}."

        return f"Error: Unknown action '{action}'."


def _find_task_by_prefix(room, prefix: str) -> Optional[Any]:
    matches = [task for task in room.tasks if task.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None
