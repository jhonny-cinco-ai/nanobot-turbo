"""Routine model aliases over the existing scheduler types.

This keeps one domain name (`routines`) while reusing the current scheduler
implementation under the hood.
"""

from nanofolks.routines.engine.types import (
    CronJob as Routine,
    CronJobState as RoutineState,
    CronPayload as RoutinePayload,
    CronSchedule as RoutineSchedule,
    CronStore as RoutineStore,
)

__all__ = [
    "Routine",
    "RoutineState",
    "RoutinePayload",
    "RoutineSchedule",
    "RoutineStore",
]
