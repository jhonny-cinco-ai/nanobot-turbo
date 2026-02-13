"""Independent heartbeat service for each bot.

This module provides BotHeartbeatService which manages autonomous
periodic checks for individual bots with full resilience features.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from nanobot.heartbeat.models import (
    HeartbeatConfig, HeartbeatTick, CheckResult, 
    CheckStatus, HeartbeatHistory, CheckDefinition
)
from nanobot.heartbeat.check_registry import check_registry


class BotHeartbeatService:
    """Independent heartbeat service for a single bot.
    
    Each bot runs its own heartbeat with role-specific:
    - Intervals (default: 60 minutes for specialists, 30 for coordinator)
    - Checks (domain-specific periodic tasks)
    - Execution strategy (parallel/sequential, retries)
    - Resilience (circuit breaker, error handling)
    
    Example:
        # Create service for a bot
        service = BotHeartbeatService(
            bot_instance=researcher_bot,
            config=HeartbeatConfig(
                bot_name="researcher",
                interval_s=3600,  # 60 minutes
                checks=[
                    CheckDefinition(name="monitor_data_sources", ...),
                    CheckDefinition(name="track_market_trends", ...),
                ]
            )
        )
        
        # Start the heartbeat
        await service.start()
        
        # Later, stop it
        service.stop()
    """
    
    def __init__(
        self,
        bot_instance: Any,
        config: HeartbeatConfig,
        on_tick_complete: Optional[Callable[[HeartbeatTick], None]] = None,
        on_check_complete: Optional[Callable[[CheckResult], None]] = None
    ):
        """Initialize heartbeat service for a bot.
        
        Args:
            bot_instance: The bot instance this service manages
            config: Heartbeat configuration
            on_tick_complete: Optional callback when a tick completes
            on_check_complete: Optional callback when a check completes
        """
        self.bot = bot_instance
        self.config = config
        self.on_tick_complete = on_tick_complete
        self.on_check_complete = on_check_complete
        
        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_tick: Optional[HeartbeatTick] = None
        
        # History
        self.history = HeartbeatHistory(bot_name=config.bot_name)
        
        # Circuit breaker for resilience (optional)
        self.circuit_breaker = None
        if config.circuit_breaker_enabled:
            try:
                from nanobot.coordinator.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
                cb_config = CircuitBreakerConfig(
                    failure_threshold=config.circuit_breaker_threshold,
                    timeout=config.circuit_breaker_timeout_s
                )
                self.circuit_breaker = CircuitBreaker(cb_config)
                self.circuit_breaker.register_bot(config.bot_name)
            except ImportError:
                logger.warning(f"[{config.bot_name}] Circuit breaker not available")
    
    @property
    def is_running(self) -> bool:
        """Check if heartbeat is currently running."""
        return self._running
    
    @property
    def current_tick(self) -> Optional[HeartbeatTick]:
        """Get the currently executing tick (if any)."""
        return self._current_tick
    
    async def start(self) -> None:
        """Start the heartbeat service."""
        if self._running:
            logger.warning(f"[{self.config.bot_name}] Heartbeat already running")
            return
        
        if not self.config.enabled:
            logger.info(f"[{self.config.bot_name}] Heartbeat disabled")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        
        interval_min = self.config.interval_s / 60
        logger.info(
            f"[{self.config.bot_name}] Heartbeat started "
            f"(every {interval_min:.0f}min, "
            f"{len(self.config.checks)} checks)"
        )
    
    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info(f"[{self.config.bot_name}] Heartbeat stopped")
    
    async def trigger_now(self, reason: str = "manual") -> HeartbeatTick:
        """Manually trigger a heartbeat tick.
        
        Args:
            reason: Why heartbeat is being triggered
            
        Returns:
            HeartbeatTick result
        """
        return await self._execute_tick(trigger_type="manual", triggered_by=reason)
    
    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                # Wait for interval
                await asyncio.sleep(self.config.interval_s)
                
                if not self._running:
                    break
                
                # Execute tick
                await self._execute_tick(trigger_type="scheduled")
                
            except asyncio.CancelledError:
                logger.debug(f"[{self.config.bot_name}] Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"[{self.config.bot_name}] Heartbeat error: {e}")
                # Continue loop even on error
    
    async def _execute_tick(
        self,
        trigger_type: str = "scheduled",
        triggered_by: Optional[str] = None
    ) -> HeartbeatTick:
        """Execute a single heartbeat tick.
        
        Args:
            trigger_type: Type of trigger (scheduled, manual, event)
            triggered_by: What triggered this tick
            
        Returns:
            HeartbeatTick with results
        """
        tick_id = str(uuid.uuid4())[:8]
        tick = HeartbeatTick(
            tick_id=tick_id,
            bot_name=self.config.bot_name,
            started_at=datetime.now(),
            config=self.config,
            trigger_type=trigger_type,
            triggered_by=triggered_by
        )
        self._current_tick = tick
        
        logger.info(
            f"[{self.config.bot_name}] Tick {tick_id} started "
            f"({len(self.config.checks)} checks)"
        )
        
        try:
            # Check circuit breaker
            if self.circuit_breaker:
                from nanobot.coordinator.circuit_breaker import CircuitState
                state = self.circuit_breaker.get_state(self.config.bot_name)
                if state == CircuitState.OPEN:
                    logger.warning(
                        f"[{self.config.bot_name}] Circuit breaker OPEN, "
                        f"skipping tick"
                    )
                    tick.status = "skipped"
                    return tick
            
            # Execute checks
            if self.config.parallel_checks:
                results = await self._execute_checks_parallel(tick)
            else:
                results = await self._execute_checks_sequential(tick)
            
            tick.results = results
            
            # Determine overall status
            failed = [r for r in results if not r.success]
            if failed and self.config.stop_on_first_failure:
                tick.status = "failed"
            elif failed:
                tick.status = "completed_with_failures"
            else:
                tick.status = "completed"
            
            # Record in history
            self.history.add_tick(tick)
            
            # Callback
            if self.on_tick_complete:
                try:
                    self.on_tick_complete(tick)
                except Exception as e:
                    logger.error(f"Tick complete callback error: {e}")
            
            # Log summary
            success_rate = tick.get_success_rate()
            logger.info(
                f"[{self.config.bot_name}] Tick {tick_id} completed: "
                f"{len(results)} checks, {success_rate:.0%} success"
            )
            
        except Exception as e:
            tick.status = "failed"
            logger.error(f"[{self.config.bot_name}] Tick {tick_id} failed: {e}")
            
            # Record circuit breaker failure
            if self.circuit_breaker:
                self.circuit_breaker._record_failure(self.config.bot_name, 0)
        
        finally:
            self._current_tick = None
        
        return tick
    
    async def _execute_checks_parallel(self, tick: HeartbeatTick) -> List[CheckResult]:
        """Execute checks in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_checks)
        
        async def run_with_limit(check_def: CheckDefinition) -> CheckResult:
            async with semaphore:
                return await self._execute_single_check(check_def, tick)
        
        tasks = [run_with_limit(check) for check in self.config.checks if check.enabled]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_checks_sequential(self, tick: HeartbeatTick) -> List[CheckResult]:
        """Execute checks one at a time."""
        results = []
        
        for check_def in self.config.checks:
            if not check_def.enabled:
                continue
                
            result = await self._execute_single_check(check_def, tick)
            results.append(result)
            
            # Respect stop_on_first_failure
            if not result.success and self.config.stop_on_first_failure:
                break
        
        return results
    
    async def _execute_single_check(
        self,
        check_def: CheckDefinition,
        tick: HeartbeatTick
    ) -> CheckResult:
        """Execute a single check with retry logic."""
        last_error = None
        
        for attempt in range(self.config.retry_attempts):
            # Use circuit breaker if enabled
            if self.circuit_breaker:
                try:
                    result = await self.circuit_breaker.call(
                        self.config.bot_name,
                        check_registry.execute_check,
                        check_def.name,
                        self.bot,
                        check_def.max_duration_s
                    )
                except Exception as e:
                    result = CheckResult(
                        check_name=check_def.name,
                        status=CheckStatus.FAILED,
                        started_at=datetime.now(),
                        error=str(e),
                        error_type=type(e).__name__,
                        success=False
                    )
            else:
                result = await check_registry.execute_check(
                    check_def.name,
                    self.bot,
                    check_def.max_duration_s
                )
            
            # Callback
            if self.on_check_complete:
                try:
                    self.on_check_complete(result)
                except Exception as e:
                    logger.error(f"Check complete callback error: {e}")
            
            # Check result
            if result.success:
                return result
            
            last_error = result.error
            
            # Retry delay
            if attempt < self.config.retry_attempts - 1:
                delay = self.config.retry_delay_s * (self.config.retry_backoff ** attempt)
                logger.warning(
                    f"[{self.config.bot_name}] Check '{check_def.name}' "
                    f"failed (attempt {attempt + 1}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)
        
        # All retries exhausted
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current heartbeat status.
        
        Returns:
            Status dictionary with metrics
        """
        return {
            "bot_name": self.config.bot_name,
            "running": self._running,
            "interval_s": self.config.interval_s,
            "interval_min": self.config.get_interval_minutes(),
            "checks_count": len(self.config.checks),
            "current_tick": self._current_tick.tick_id if self._current_tick else None,
            "circuit_breaker": "enabled" if self.circuit_breaker else "disabled",
            "history": {
                "total_ticks": self.history.total_ticks,
                "successful_ticks": self.history.successful_ticks,
                "failed_ticks": self.history.failed_ticks,
                "success_rate": self.history.get_average_success_rate(),
                "uptime_24h": self.history.get_uptime_percentage(24)
            }
        }
    
    async def wait_for_current_tick(self, timeout_s: float = 60.0) -> bool:
        """Wait for current tick to complete.
        
        Args:
            timeout_s: Maximum time to wait
            
        Returns:
            True if tick completed, False if timeout
        """
        if not self._current_tick:
            return True
        
        start = datetime.now()
        while self._current_tick:
            if (datetime.now() - start).total_seconds() > timeout_s:
                return False
            await asyncio.sleep(0.1)
        
        return True


__all__ = ["BotHeartbeatService"]