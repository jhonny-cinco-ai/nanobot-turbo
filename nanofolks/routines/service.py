"""Routines service: unified interface over the scheduler."""

from pathlib import Path
from typing import Any

from nanofolks.routines_engine.service import CronService
from nanofolks.routines.models import Routine, RoutinePayload, RoutineSchedule
from nanofolks.config.loader import get_data_dir


def get_default_routines_store() -> Path:
    return get_data_dir() / "routines" / "jobs.json"


class RoutineService:
    """Unified routines service (user + team/system)."""

    def __init__(self, store_path: Path | None = None):
        self._cron = CronService(store_path or get_default_routines_store())

    @property
    def scheduler(self) -> CronService:
        return self._cron

    async def start(self) -> None:
        await self._cron.start()

    def stop(self) -> None:
        self._cron.stop()

    def status(self) -> dict:
        return self._cron.status()

    # Compatibility for existing callers
    def list_jobs(self, *args: Any, **kwargs: Any) -> list[Routine]:
        return self._cron.list_jobs(*args, **kwargs)

    def list_routines(self, *args: Any, **kwargs: Any) -> list[Routine]:
        return self._cron.list_jobs(*args, **kwargs)

    def add_routine(
        self,
        name: str,
        schedule: RoutineSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        payload_kind: str = "agent_turn",
        scope: str = "user",
        routine: str | None = None,
        bot: str | None = None,
        metadata: dict | None = None,
        enabled: bool = True,
        delete_after_run: bool = False,
    ) -> Routine:
        return self._cron.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            channel=channel,
            to=to,
            payload_kind=payload_kind,
            scope=scope,
            routine=routine,
            bot=bot,
            metadata=metadata,
            enabled=enabled,
            delete_after_run=delete_after_run,
        )

    def update_routine(
        self,
        routine_id: str,
        schedule: RoutineSchedule | None = None,
        enabled: bool | None = None,
        payload: RoutinePayload | None = None,
        name: str | None = None,
        delete_after_run: bool | None = None,
    ) -> Routine | None:
        return self._cron.update_job(
            routine_id,
            schedule=schedule,
            enabled=enabled,
            payload=payload,
            name=name,
            delete_after_run=delete_after_run,
        )

    def remove_routine(self, routine_id: str) -> bool:
        return self._cron.remove_job(routine_id)

    def enable_routine(self, routine_id: str, enabled: bool = True) -> Routine | None:
        return self._cron.enable_job(routine_id, enabled=enabled)

    async def run_routine(self, routine_id: str, force: bool = False) -> bool:
        return await self._cron.run_job(routine_id, force=force)
