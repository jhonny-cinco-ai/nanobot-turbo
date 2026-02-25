"""Sidekick sessions: focused helper agents spawned by bots.

Sidekicks are short-lived task sessions with minimal context. They never
post directly to rooms; parent bots merge and report results.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class SidekickTaskEnvelope:
    """Task brief passed to a sidekick."""

    task_id: str
    parent_bot_id: str
    room_id: str
    goal: str
    inputs: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    output_format: str = "summary"
    parent_is_sidekick: bool = False


@dataclass
class SidekickResult:
    """Result returned by a sidekick."""

    task_id: str
    status: str = "success"  # success, partial, failed, timeout
    summary: str = ""
    artifacts: list[Any] = field(default_factory=list)
    notes: str = ""
    duration_ms: int | None = None


class SidekickLimitError(RuntimeError):
    """Raised when sidekick concurrency limits are exceeded."""


class SidekickOrchestrator:
    """Spawn and manage sidekick task execution."""

    def __init__(
        self,
        *,
        max_per_bot: int,
        max_per_room: int,
        max_tokens: int,
        timeout_seconds: int,
    ) -> None:
        self.max_per_bot = max_per_bot
        self.max_per_room = max_per_room
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self._active_by_bot: dict[str, int] = defaultdict(int)
        self._active_by_room: dict[str, int] = defaultdict(int)
        self._active_tasks_by_room: dict[str, set[asyncio.Task]] = defaultdict(set)

    def cancel_room(self, room_id: str) -> int:
        """Cancel all running sidekicks for a room."""
        tasks = list(self._active_tasks_by_room.get(room_id, set()))
        for task in tasks:
            task.cancel()
        return len(tasks)

    def can_spawn(self, parent_bot_id: str, room_id: str, count: int = 1) -> bool:
        """Check if spawning sidekicks would exceed limits."""
        if count <= 0:
            return True
        if self._active_by_bot[parent_bot_id] + count > self.max_per_bot:
            return False
        if self._active_by_room[room_id] + count > self.max_per_room:
            return False
        return True

    def _reserve(self, parent_bot_id: str, room_id: str, count: int) -> None:
        if not self.can_spawn(parent_bot_id, room_id, count):
            raise SidekickLimitError("Sidekick limit exceeded")
        self._active_by_bot[parent_bot_id] += count
        self._active_by_room[room_id] += count

    def _release(self, parent_bot_id: str, room_id: str, count: int) -> None:
        self._active_by_bot[parent_bot_id] = max(0, self._active_by_bot[parent_bot_id] - count)
        self._active_by_room[room_id] = max(0, self._active_by_room[room_id] - count)

    def _assert_parent_not_sidekick(self, tasks: list[SidekickTaskEnvelope]) -> None:
        if any(task.parent_is_sidekick for task in tasks):
            raise ValueError("Sidekicks cannot spawn sidekicks")

    async def run(
        self,
        tasks: list[SidekickTaskEnvelope],
        runner: Callable[[SidekickTaskEnvelope], Awaitable[SidekickResult]],
    ) -> list[SidekickResult]:
        """Run sidekick tasks with concurrency limits and timeout handling."""
        if not tasks:
            return []

        self._assert_parent_not_sidekick(tasks)

        # Enforce limits per task to keep accounting correct
        reserved: list[tuple[str, str]] = []
        try:
            for task in tasks:
                self._reserve(task.parent_bot_id, task.room_id, 1)
                reserved.append((task.parent_bot_id, task.room_id))
        except SidekickLimitError:
            for parent_bot_id, room_id in reserved:
                self._release(parent_bot_id, room_id, 1)
            raise

        async def _run_one(task: SidekickTaskEnvelope) -> SidekickResult:
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(runner(task), timeout=self.timeout_seconds)
                if result.duration_ms is None:
                    result.duration_ms = int((time.monotonic() - start) * 1000)
                return result
            except asyncio.TimeoutError:
                return SidekickResult(
                    task_id=task.task_id,
                    status="timeout",
                    summary="",
                    notes="Timed out",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            except asyncio.CancelledError:
                return SidekickResult(
                    task_id=task.task_id,
                    status="failed",
                    summary="",
                    notes="Cancelled",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            except Exception as exc:
                return SidekickResult(
                    task_id=task.task_id,
                    status="failed",
                    summary="",
                    notes=str(exc),
                    duration_ms=int((time.monotonic() - start) * 1000),
                )

        running: list[tuple[str, asyncio.Task]] = []
        try:
            for task in tasks:
                runner_task = asyncio.create_task(_run_one(task))
                running.append((task.room_id, runner_task))
                self._active_tasks_by_room[task.room_id].add(runner_task)

            gathered = await asyncio.gather(
                *[runner_task for _, runner_task in running],
                return_exceptions=True,
            )
            results: list[SidekickResult] = []
            for task, result in zip(tasks, gathered, strict=False):
                if isinstance(result, SidekickResult):
                    results.append(result)
                elif isinstance(result, asyncio.CancelledError):
                    results.append(
                        SidekickResult(
                            task_id=task.task_id,
                            status="failed",
                            summary="",
                            notes="Cancelled",
                        )
                    )
                elif isinstance(result, Exception):
                    results.append(
                        SidekickResult(
                            task_id=task.task_id,
                            status="failed",
                            summary="",
                            notes=str(result),
                        )
                    )
                else:
                    results.append(
                        SidekickResult(
                            task_id=task.task_id,
                            status="failed",
                            summary="",
                            notes="Unknown error",
                        )
                    )
            return results
        finally:
            for task in tasks:
                self._release(task.parent_bot_id, task.room_id, 1)
            for room_id, runner_task in running:
                active = self._active_tasks_by_room.get(room_id)
                if not active:
                    continue
                active.discard(runner_task)
                if not active:
                    self._active_tasks_by_room.pop(room_id, None)
