"""Manager for coordinating multiple bot crew routines (legacy heartbeat).

This module provides centralized management of crew routines across
all bots in the team. It handles:
- Starting/stopping all bot crew routines
- Monitoring team health
- Coordinating cross-bot tasks
- Aggregating metrics

Usage:
    from nanofolks.crew_routines.multi_manager import MultiCrewRoutinesManager

    manager = MultiCrewRoutinesManager(bus=interbot_bus)

    # Register bots
    for bot in [researcher, coder, social, creative, auditor, leader]:
        manager.register_bot(bot)

    # Start all crew routines
    await manager.start_all()

    # Get team health
    health = manager.get_team_health()

    # Stop all
    manager.stop_all()
"""

# Note: Class name is legacy, but methods now use crew routines terminology.

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from nanofolks.bots.base import SpecialistBot


@dataclass
class CrossBotCheck:
    """A check that requires coordination across multiple bots."""
    name: str
    description: str
    participating_bots: List[str]
    coordinator_check: str  # Check that runs on coordinator
    dependencies: List[str] = field(default_factory=list)  # Checks that must complete first


@dataclass
class TeamHealthReport:
    """Comprehensive health report for the bot team."""
    timestamp: str
    total_bots: int
    running_bots: int
    overall_success_rate: float
    total_ticks_all_bots: int
    failed_ticks_all_bots: int
    bots: Dict[str, Any]
    alerts: List[str] = field(default_factory=list)


class MultiCrewRoutinesManager:
    """Manages crew routines across all bots in the team (legacy heartbeat).

    Responsibilities:
    - Start/stop all bot crew routines
    - Coordinate cross-bot checks
    - Monitor overall team health
    - Aggregate crew routine metrics
    - Handle bot failures and recovery

    Example:
        manager = MultiCrewRoutinesManager(bus=bus)

        # Register bots
        for bot in team:
            manager.register_bot(bot)

        # Start all
        await manager.start_all()

        # Check health
        health = manager.get_team_health()
        print(f"Team success rate: {health['overall_success_rate']:.1f}%")

        # Stop all
        manager.stop_all()
    """

    def __init__(self, bus=None, routine_service=None):
        """Initialize the crew routines manager.

        Args:
            bus: InterBotBus for cross-bot communication (optional)
            routine_service: CronService instance for unified routine scheduling (optional)
        """
        self.bus = bus
        self._routine_service = routine_service

        # Bot registry
        self._bots: Dict[str, SpecialistBot] = {}
        self._crew_routines_tasks: Dict[str, asyncio.Task] = {}
        self._crew_routines_jobs: Dict[str, str] = {}

        # Cross-bot coordination
        self._cross_bot_checks: Dict[str, CrossBotCheck] = {}

        # State
        self._running = False
        self._coordinator_check_task: Optional[asyncio.Task] = None
        self._team_health_task: Optional[asyncio.Task] = None

        # Health monitoring
        self._health_check_interval_s = 300  # 5 minutes
        self._alerts: List[str] = []

    def register_bot(self, bot: SpecialistBot) -> None:
        """Register a bot for crew routines management.

        Args:
            bot: Bot instance to register

        Example:
            researcher = ResearcherBot()
            manager.register_bot(researcher)
        """
        bot_name = bot.role_card.bot_name

        if bot_name in self._bots:
            logger.warning(f"[MultiCrewRoutinesManager] Bot {bot_name} already registered, replacing")

        self._bots[bot_name] = bot
        logger.info(f"[MultiCrewRoutinesManager] Registered bot: {bot_name}")

    @property
    def bots(self) -> Dict[str, SpecialistBot]:
        """Expose registered bots for CLI tooling."""
        return self._bots

    def unregister_bot(self, bot_name: str) -> bool:
        """Unregister a bot and stop its crew routines.

        Args:
            bot_name: Name of bot to unregister

        Returns:
            True if unregistered successfully

        Example:
            manager.unregister_bot("researcher")
        """
        if bot_name not in self._bots:
            logger.warning(f"[MultiCrewRoutinesManager] Bot {bot_name} not registered")
            return False

        # Stop crew routines if running
        bot = self._bots[bot_name]
        try:
            bot.stop_crew_routines()
        except Exception as e:
            logger.error(f"[MultiCrewRoutinesManager] Error stopping {bot_name} crew routines: {e}")

        # Cancel task if exists
        if bot_name in self._crew_routines_tasks:
            self._crew_routines_tasks[bot_name].cancel()
            del self._crew_routines_tasks[bot_name]

        # Disable routine job if present
        if self._routine_service and bot_name in self._crew_routines_jobs:
            try:
                self._routine_service.update_job(self._crew_routines_jobs[bot_name], enabled=False)
            except Exception as e:
                logger.warning(f"[MultiCrewRoutinesManager] Failed to disable routine for {bot_name}: {e}")
            self._crew_routines_jobs.pop(bot_name, None)

        del self._bots[bot_name]
        logger.info(f"[MultiCrewRoutinesManager] Unregistered bot: {bot_name}")
        return True

    def _ensure_crew_routines_job(self, bot: SpecialistBot) -> None:
        """Ensure a crew routines job exists for the bot when using routine scheduler."""
        if not self._routine_service:
            return

        if bot._crew_routines is None or bot._crew_routines_config is None:
            bot.initialize_crew_routines()

        config = bot._crew_routines_config
        if not config:
            return

        from nanofolks.routines_engine.types import CronSchedule

        schedule = CronSchedule(kind="every", every_ms=config.interval_s * 1000)

        existing = self._routine_service.list_jobs(
            include_disabled=True,
            scope="system",
            routine="crew_routines",
            bot=bot.role_card.bot_name,
        )

        if existing:
            job = existing[0]
            self._routine_service.update_job(
                job.id,
                schedule=schedule,
                enabled=config.enabled,
            )
            self._crew_routines_jobs[bot.role_card.bot_name] = job.id
        else:
            job = self._routine_service.add_job(
                name=f"Crew routines {bot.role_card.bot_name}",
                schedule=schedule,
                message="CREW_ROUTINES_TICK",
                enabled=config.enabled,
                deliver=False,
                channel="internal",
                to=bot.role_card.bot_name,
                payload_kind="system_event",
                scope="system",
                routine="crew_routines",
                bot=bot.role_card.bot_name,
            )
            self._crew_routines_jobs[bot.role_card.bot_name] = job.id

        if bot._crew_routines:
            bot._crew_routines.set_external_scheduler(config.enabled)

    async def start_all(self) -> None:
        """Start crew routines for all registered bots.

        This starts each bot's independent crew routines service.
        Coordinator bot runs with 30min interval, specialists with 60min.

        Example:
            await manager.start_all()
        """
        self._running = True

        logger.info(f"[MultiCrewRoutinesManager] Starting crew routines for {len(self._bots)} bots")

        # Start each bot's crew routines
        for bot_name, bot in self._bots.items():
            try:
                if self._routine_service:
                    self._ensure_crew_routines_job(bot)
                else:
                    await bot.start_crew_routines()

                interval = bot._crew_routines_config.interval_s if bot._crew_routines_config else 3600
                checks_count = len(bot._crew_routines_config.checks) if bot._crew_routines_config else 0

                logger.info(
                    f"[MultiCrewRoutinesManager] Started {bot_name} crew routines: "
                    f"{interval}s interval, {checks_count} checks"
                )

            except Exception as e:
                logger.error(f"[MultiCrewRoutinesManager] Failed to start {bot_name} crew routines: {e}")

        # Start team health monitoring
        self._team_health_task = asyncio.create_task(
            self._monitor_team_health(),
            name="team_health_monitor"
        )

        logger.info("[MultiCrewRoutinesManager] All crew routines started")

    def stop_all(self) -> None:
        """Stop all bot crew routines.

        This gracefully stops all running crew routines and cancels
        any pending coordination tasks.

        Example:
            manager.stop_all()
        """
        self._running = False

        logger.info(f"[MultiCrewRoutinesManager] Stopping crew routines for {len(self._bots)} bots")

        # Stop each bot
        for bot_name, bot in self._bots.items():
            try:
                if self._routine_service:
                    if bot_name in self._crew_routines_jobs:
                        self._routine_service.update_job(self._crew_routines_jobs[bot_name], enabled=False)
                    if bot._crew_routines:
                        bot._crew_routines.set_external_scheduler(False)
                else:
                    bot.stop_crew_routines()
                logger.debug(f"[MultiCrewRoutinesManager] Stopped {bot_name} crew routines")
            except Exception as e:
                logger.error(f"[MultiCrewRoutinesManager] Error stopping {bot_name}: {e}")

        # Cancel health monitoring task
        if self._team_health_task:
            self._team_health_task.cancel()
            self._team_health_task = None

        # Cancel coordinator task
        if self._coordinator_check_task:
            self._coordinator_check_task.cancel()
            self._coordinator_check_task = None

        # Cancel any pending crew routines tasks
        for task in self._crew_routines_tasks.values():
            task.cancel()
        self._crew_routines_tasks.clear()

        logger.info("[MultiCrewRoutinesManager] All crew routines stopped")

    async def _monitor_team_health(self) -> None:
        """Monitor team health periodically.

        Runs every 5 minutes to check overall team health and
        generate alerts if issues are detected.
        """
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval_s)

                if not self._running:
                    break

                health = self.get_team_health()

                # Check for issues
                alerts = []

                if health.overall_success_rate < 80:
                    alerts.append(f"Low team success rate: {health.overall_success_rate:.1f}%")

                non_running = health.total_bots - health.running_bots
                if non_running > 0:
                    alerts.append(f"{non_running} bots not running")

                # Log alerts
                for alert in alerts:
                    logger.warning(f"[MultiCrewRoutinesManager] ALERT: {alert}")

                self._alerts = alerts

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MultiCrewRoutinesManager] Health monitoring error: {e}")

    def get_team_health(self) -> TeamHealthReport:
        """Get overall health status of all bot crew routines.

        Returns comprehensive health report with per-bot and aggregate metrics.

        Returns:
            TeamHealthReport with health metrics

        Example:
            health = manager.get_team_health()
            print(f"Success rate: {health.overall_success_rate:.1f}%")
            print(f"Running bots: {health.running_bots}/{health.total_bots}")
        """
        bot_statuses = {}

        for bot_name, bot in self._bots.items():
            try:
                status = bot.get_crew_routines_status()

                # Add bot-specific info
                status["bot_name"] = bot_name
                status["domain"] = bot.domain
                status["title"] = bot.title

                bot_statuses[bot_name] = status
            except Exception as e:
                logger.error(f"[MultiCrewRoutinesManager] Error getting status for {bot_name}: {e}")
                bot_statuses[bot_name] = {
                    "bot_name": bot_name,
                    "error": str(e),
                    "running": False
                }

        # Calculate aggregate metrics from crew routines history
        total_ticks = 0
        failed_ticks = 0

        for bot in self._bots.values():
            history = bot.private_memory.get("crew_routines_history", [])
            total_ticks += len(history)
            failed_ticks += sum(
                1 for tick in history
                if tick.get("status") in ["failed", "timeout"]
            )

        overall_success_rate = (
            ((total_ticks - failed_ticks) / total_ticks * 100)
            if total_ticks > 0 else 100.0
        )

        running_count = sum(
            1 for s in bot_statuses.values()
            if s.get("running", False)
        )

        return TeamHealthReport(
            timestamp=datetime.now().isoformat(),
            total_bots=len(self._bots),
            running_bots=running_count,
            overall_success_rate=overall_success_rate,
            total_ticks_all_bots=total_ticks,
            failed_ticks_all_bots=failed_ticks,
            bots=bot_statuses,
            alerts=self._alerts.copy()
        )

    def get_team_health_dict(self) -> Dict[str, Any]:
        """Get team health as a dictionary (for JSON serialization).

        Returns:
            Dict with health information
        """
        report = self.get_team_health()
        return {
            "timestamp": report.timestamp,
            "total_bots": report.total_bots,
            "running_bots": report.running_bots,
            "overall_success_rate": report.overall_success_rate,
            "total_ticks_all_bots": report.total_ticks_all_bots,
            "failed_ticks_all_bots": report.failed_ticks_all_bots,
            "bots": report.bots,
            "alerts": report.alerts
        }

    async def trigger_team_crew_routines(self, reason: str = "manual") -> Dict[str, Any]:
        """Manually trigger crew routines on all bots.

        This forces an immediate crew routines tick on all registered bots,
        regardless of their scheduled intervals.

        Args:
            reason: Why crew routines are being triggered

        Returns:
            Results from all bots

        Example:
            results = await manager.trigger_team_crew_routines("system_check")
            for bot_name, tick in results.items():
                print(f"{bot_name}: {tick.status}")
        """
        results = {}

        logger.info(f"[MultiCrewRoutinesManager] Triggering team crew routines: {reason}")

        for bot_name, bot in self._bots.items():
            try:
                tick = await bot.trigger_crew_routines_now(reason)
                results[bot_name] = {
                    "success": True,
                    "tick_id": tick.tick_id if tick else None,
                    "status": tick.status if tick else "unknown"
                }
                logger.debug(f"[MultiCrewRoutinesManager] Triggered {bot_name} crew routines")
            except Exception as e:
                results[bot_name] = {
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"[MultiCrewRoutinesManager] Failed to trigger {bot_name}: {e}")

        return results

    def get_registered_bots(self) -> List[str]:
        """Get list of registered bot names.

        Returns:
            List of bot names
        """
        return list(self._bots.keys())

    def is_running(self) -> bool:
        """Check if manager is running.

        Returns:
            True if manager is active
        """
        return self._running

    def register_cross_bot_check(self, check: CrossBotCheck) -> None:
        """Register a check that requires cross-bot coordination.

        Args:
            check: CrossBotCheck definition
        """
        self._cross_bot_checks[check.name] = check
        logger.info(f"[MultiCrewRoutinesManager] Registered cross-bot check: {check.name}")

    def get_bot(self, bot_name: str) -> Optional[SpecialistBot]:
        """Get a registered bot by name.

        Args:
            bot_name: Name of bot to retrieve

        Returns:
            Bot instance or None if not found
        """
        return self._bots.get(bot_name)

    async def enable_bot_crew_routines(self, bot_name: str) -> bool:
        """Enable and start crew routines scheduling for a bot."""
        bot = self.get_bot(bot_name)
        if not bot:
            return False
        if bot._crew_routines_config is None or bot._crew_routines is None:
            bot.initialize_crew_routines()
        if bot._crew_routines_config:
            bot._crew_routines_config.enabled = True

        if self._routine_service:
            self._ensure_crew_routines_job(bot)
            return True

        await bot.start_crew_routines()
        return True

    async def disable_bot_crew_routines(self, bot_name: str) -> bool:
        """Disable crew routines scheduling for a bot."""
        bot = self.get_bot(bot_name)
        if not bot:
            return False
        if bot._crew_routines_config:
            bot._crew_routines_config.enabled = False

        if self._routine_service:
            job_id = self._crew_routines_jobs.get(bot_name)
            if job_id:
                self._routine_service.update_job(job_id, enabled=False)
            if bot._crew_routines:
                bot._crew_routines.set_external_scheduler(False)
            return True

        bot.stop_crew_routines()
        return True

    async def start_bot_crew_routines(self, bot_name: str) -> bool:
        """Start crew routines for a bot (does not change config if already enabled)."""
        bot = self.get_bot(bot_name)
        if not bot:
            return False
        if bot._crew_routines_config is None or bot._crew_routines is None:
            bot.initialize_crew_routines()
        if bot._crew_routines_config and not bot._crew_routines_config.enabled:
            bot._crew_routines_config.enabled = True

        if self._routine_service:
            self._ensure_crew_routines_job(bot)
            return True

        await bot.start_crew_routines()
        return True

    async def stop_bot_crew_routines(self, bot_name: str) -> bool:
        """Stop crew routines for a bot (keeps config enabled)."""
        bot = self.get_bot(bot_name)
        if not bot:
            return False
        if self._routine_service:
            job_id = self._crew_routines_jobs.get(bot_name)
            if job_id:
                self._routine_service.update_job(job_id, enabled=False)
            if bot._crew_routines:
                bot._crew_routines.set_external_scheduler(False)
            return True

        bot.stop_crew_routines()
        return True

    def __len__(self) -> int:
        """Return number of registered bots."""
        return len(self._bots)

    def __contains__(self, bot_name: str) -> bool:
        """Check if a bot is registered."""
        return bot_name in self._bots


__all__ = [
    "MultiCrewRoutinesManager",
    "CrossBotCheck",
    "TeamHealthReport",
]
