"""Sidekick tool for spawning focused helper sessions."""

from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

from nanofolks.agent.tools.base import Tool
from nanofolks.agent.sidekicks import SidekickTaskEnvelope

if TYPE_CHECKING:
    from nanofolks.agent.bot_invoker import BotInvoker


class SidekickTool(Tool):
    """Tool to spawn sidekicks for focused sub-tasks.

    Sidekicks never post to the room directly. The parent bot merges results.
    """

    def __init__(self, invoker: "BotInvoker", parent_bot_role: str):
        self._invoker = invoker
        self._parent_bot_role = parent_bot_role
        self._room_id: str = "general"

    def set_context(self, room_id: str | None) -> None:
        if room_id:
            self._room_id = room_id

    @property
    def name(self) -> str:
        return "sidekick"

    @property
    def description(self) -> str:
        return (
            "Spawn sidekicks to handle focused sub-tasks in parallel. "
            "Use this when you want to split a task into smaller parts. "
            "Sidekicks return summaries only; you must merge and respond."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string"},
                            "inputs": {"type": "object"},
                            "constraints": {"type": "object"},
                            "output_format": {"type": "string"},
                        },
                        "required": ["goal"],
                    },
                }
            },
            "required": ["tasks"],
        }

    async def execute(self, tasks: list[dict[str, Any]], **kwargs: Any) -> str:
        envelopes: list[SidekickTaskEnvelope] = []
        for task in tasks:
            envelopes.append(
                SidekickTaskEnvelope(
                    task_id=str(uuid.uuid4())[:8],
                    parent_bot_id=self._parent_bot_role,
                    room_id=self._room_id,
                    goal=task.get("goal", "").strip(),
                    inputs=task.get("inputs") or {},
                    constraints=task.get("constraints") or {},
                    output_format=task.get("output_format") or "summary",
                )
            )

        results = await self._invoker.run_sidekicks(
            parent_bot_role=self._parent_bot_role,
            room_id=self._room_id,
            tasks=envelopes,
        )

        if not results:
            return "Sidekick results: none (limits hit or disabled)."

        return self._invoker.format_sidekick_results(results)
