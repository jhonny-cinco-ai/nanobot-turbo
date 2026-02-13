"""Multi-heartbeat system for per-bot autonomous periodic checks.

This module provides infrastructure for each bot to run independent heartbeats
with domain-specific checks, configurable intervals, and full resilience.

Example Usage:
    from nanobot.heartbeat import BotHeartbeatService, HeartbeatConfig
    from nanobot.heartbeat.check_registry import register_check
    
    # Define a check
    @register_check(
        name="monitor_data",
        description="Monitor data sources",
        bot_domains=["research"]
    )
    async def monitor_data(bot, config):
        # Check implementation
        return {"success": True, "data": {}}
    
    # Create and start heartbeat
    service = BotHeartbeatService(
        bot_instance=bot,
        config=HeartbeatConfig(
            bot_name="researcher",
            interval_s=3600,  # 60 minutes
            checks=[CheckDefinition(name="monitor_data", ...)]
        )
    )
    await service.start()
"""

# Legacy single-heartbeat service (maintained for backward compatibility)
from nanobot.heartbeat.service import HeartbeatService

# New multi-heartbeat system
from nanobot.heartbeat.models import (
    CheckPriority,
    CheckStatus,
    CheckDefinition,
    CheckResult,
    HeartbeatConfig,
    HeartbeatTick,
    HeartbeatHistory,
)
from nanobot.heartbeat.bot_heartbeat import BotHeartbeatService
from nanobot.heartbeat.check_registry import (
    CheckRegistry,
    check_registry,
    register_check,
)

__version__ = "1.0.0"

__all__ = [
    # Legacy (backward compatibility)
    "HeartbeatService",
    # Enums
    "CheckPriority",
    "CheckStatus",
    # Models
    "CheckDefinition",
    "CheckResult",
    "HeartbeatConfig",
    "HeartbeatTick",
    "HeartbeatHistory",
    # Services
    "BotHeartbeatService",
    # Registry
    "CheckRegistry",
    "check_registry",
    "register_check",
]
