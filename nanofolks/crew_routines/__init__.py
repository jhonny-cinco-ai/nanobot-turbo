"""Crew routines engine for per-bot autonomous checks (legacy heartbeat).

This module provides infrastructure for each bot to run independent crew routines
with domain-specific checks, configurable intervals, and full resilience.

Example Usage:
    from nanofolks.crew_routines import BotCrewRoutinesService, CrewRoutinesConfig
    from nanofolks.crew_routines.check_registry import register_check

    # Define a check
    @register_check(
        name="monitor_data",
        description="Monitor data sources",
        bot_domains=["research"]
    )
    async def monitor_data(bot, config):
        # Check implementation
        return {"success": True, "data": {}}

    # Create and start crew routine engine
    service = BotCrewRoutinesService(
        bot_instance=bot,
        config=CrewRoutinesConfig(
            bot_name="researcher",
            interval_s=3600,  # 60 minutes
            checks=[CheckDefinition(name="monitor_data", ...)]
        )
    )
    await service.start()
"""

# Note: The legacy HeartbeatService has been removed.
# Use BotCrewRoutinesService and MultiCrewRoutinesManager instead.

# Crew routines engine (legacy heartbeat)
from nanofolks.crew_routines.bot_crew_routines import BotCrewRoutinesService
from nanofolks.crew_routines.check_registry import (
    CheckRegistry,
    check_registry,
    register_check,
)
from nanofolks.crew_routines.dashboard import DashboardService, MetricsBuffer
from nanofolks.crew_routines.dashboard_server import DashboardHTTPServer
from nanofolks.crew_routines.crew_routines_models import (
    CheckDefinition,
    CheckPriority,
    CheckResult,
    CheckStatus,
    CrewRoutinesConfig,
    CrewRoutinesHistory,
    CrewRoutinesTick,
)
from nanofolks.crew_routines.multi_manager import (
    CrossBotCheck,
    MultiCrewRoutinesManager,
    TeamHealthReport,
)

__version__ = "1.0.0"

__all__ = [
    # Enums
    "CheckPriority",
    "CheckStatus",
    # Models
    "CheckDefinition",
    "CheckResult",
    "CrewRoutinesConfig",
    "CrewRoutinesTick",
    "CrewRoutinesHistory",
    # Services
    "BotCrewRoutinesService",
    "MultiCrewRoutinesManager",
    # Registry
    "CheckRegistry",
    "check_registry",
    "register_check",
    # Coordination
    "CrossBotCheck",
    "TeamHealthReport",
    # Dashboard
    "DashboardService",
    "MetricsBuffer",
    "DashboardHTTPServer",
]
