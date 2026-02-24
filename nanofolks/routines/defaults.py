"""Default team routines seeding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from nanofolks.routines.models import RoutineSchedule
from nanofolks.routines.service import RoutineService


@dataclass(frozen=True)
class TeamEnergyProfile:
    name: str
    team_check_in_minutes: int
    room_pulse_minutes: int
    bot_focus_minutes: int


ENERGY_PROFILES = {
    "quiet": TeamEnergyProfile("quiet", team_check_in_minutes=240, room_pulse_minutes=360, bot_focus_minutes=1440),
    "balanced": TeamEnergyProfile("balanced", team_check_in_minutes=120, room_pulse_minutes=240, bot_focus_minutes=720),
    "active": TeamEnergyProfile("active", team_check_in_minutes=60, room_pulse_minutes=120, bot_focus_minutes=360),
}


def _routine_exists(
    routines: RoutineService,
    routine: str,
    target_type: str,
    target_id: str | None,
) -> bool:
    for job in routines.list_routines(include_disabled=True, scope="system"):
        if job.payload.routine != routine:
            continue
        if job.payload.metadata and job.payload.metadata.get("target_type") != target_type:
            continue
        if target_id and job.payload.metadata and job.payload.metadata.get("target_id") != target_id:
            continue
        return True
    return False


def seed_default_team_routines(
    routines: RoutineService,
    team_bots: Iterable[str],
    room_ids: Iterable[str],
    energy: str = "balanced",
) -> None:
    profile = ENERGY_PROFILES.get(energy, ENERGY_PROFILES["balanced"])

    # Team check-in
    if not _routine_exists(routines, "team_check_in", "team", None):
        schedule = RoutineSchedule(kind="every", every_ms=profile.team_check_in_minutes * 60 * 1000)
        routines.add_routine(
            name="Team Check-In",
            schedule=schedule,
            message="TEAM_ROUTINE: team_check_in",
            deliver=False,
            channel="internal",
            to="team",
            payload_kind="system_event",
            scope="system",
            routine="team_check_in",
            metadata={"target_type": "team"},
        )

    # Room pulse per room
    for room_id in room_ids:
        if _routine_exists(routines, "room_pulse", "room", room_id):
            continue
        schedule = RoutineSchedule(kind="every", every_ms=profile.room_pulse_minutes * 60 * 1000)
        routines.add_routine(
            name=f"Room Pulse: {room_id}",
            schedule=schedule,
            message=f"TEAM_ROUTINE: room_pulse room={room_id}",
            deliver=False,
            channel="internal",
            to=room_id,
            payload_kind="system_event",
            scope="system",
            routine="room_pulse",
            metadata={"target_type": "room", "target_id": room_id},
        )

    # Specialist focus per bot
    for bot_name in team_bots:
        if _routine_exists(routines, "bot_focus", "bot", bot_name):
            continue
        schedule = RoutineSchedule(kind="every", every_ms=profile.bot_focus_minutes * 60 * 1000)
        routines.add_routine(
            name=f"Bot Focus: {bot_name}",
            schedule=schedule,
            message=f"TEAM_ROUTINE: bot_focus bot={bot_name}",
            deliver=False,
            channel="internal",
            to=bot_name,
            payload_kind="system_event",
            scope="system",
            routine="bot_focus",
            metadata={"target_type": "bot", "target_id": bot_name},
        )
