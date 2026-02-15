"""Independent heartbeat service for each bot.

This module provides BotHeartbeatService which manages autonomous
periodic checks for individual bots with full resilience features.

Supports two modes:
1. HEARTBEAT.md mode (OpenClaw-style): Bot reads HEARTBEAT.md and executes tasks via LLM
2. Legacy check mode: Runs registered programmatic checks
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Coroutine

from loguru import logger

from nanobot.agent.work_log import LogLevel
from nanobot.heartbeat.models import (
    HeartbeatConfig, HeartbeatTick, CheckResult, 
    CheckStatus, HeartbeatHistory, CheckDefinition
)
from nanobot.heartbeat.check_registry import check_registry


# The prompt sent to agent during heartbeat (from legacy service)
HEARTBEAT_PROMPT = """Read HEARTBEAT.md in your workspace (if it exists).
Follow any instructions or tasks listed there.
If nothing needs attention, reply with just: HEARTBEAT_OK"""

# Token that indicates "nothing to do"
HEARTBEAT_OK_TOKEN = "HEARTBEAT_OK"


def _is_heartbeat_empty(content: str | None) -> bool:
    """Check if HEARTBEAT.md has no actionable content."""
    if not content:
        return True
    
    skip_patterns = {"- [ ]", "* [ ]", "- [x]", "* [x]"}
    
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<!--") or line in skip_patterns:
            continue
        return False
    
    return True


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
        workspace: Path | None = None,
        provider=None,
        routing_config=None,
        reasoning_config=None,
        work_log_manager=None,
        on_heartbeat: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_tick_complete: Optional[Callable[[HeartbeatTick], None]] = None,
        on_check_complete: Optional[Callable[[CheckResult], None]] = None
    ):
        """Initialize heartbeat service for a bot.
        
        Args:
            bot_instance: The bot instance this service manages
            config: Heartbeat configuration
            workspace: Path to bot's workspace (for HEARTBEAT.md)
            provider: LLM provider for heartbeat execution
            routing_config: Smart routing config for model selection
            reasoning_config: Reasoning/CoT settings for this bot
            work_log_manager: Work log manager for logging heartbeat events
            on_heartbeat: Callback to execute heartbeat tasks via LLM
            on_tick_complete: Optional callback when a tick completes
            on_check_complete: Optional callback when a check completes
        """
        self.bot = bot_instance
        self.config = config
        self.workspace = workspace
        self.provider = provider
        self.routing_config = routing_config
        self.reasoning_config = reasoning_config
        self.work_log_manager = work_log_manager
        self.on_heartbeat = on_heartbeat
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
    
    def _get_heartbeat_file_path(self) -> Path | None:
        """Get path to bot's HEARTBEAT.md file."""
        if self.workspace:
            # Option 1: workspace/bots/{bot_name}/HEARTBEAT.md
            bot_heartbeat = self.workspace / "bots" / self.config.bot_name / "HEARTBEAT.md"
            if bot_heartbeat.exists():
                return bot_heartbeat
            
            # Option 2: workspace/HEARTBEAT.md (for leader)
            workspace_heartbeat = self.workspace / "HEARTBEAT.md"
            if workspace_heartbeat.exists():
                return workspace_heartbeat
        
        return None
    
    def _read_heartbeat_content(self) -> str | None:
        """Read HEARTBEAT.md content if exists."""
        heartbeat_file = self._get_heartbeat_file_path()
        if heartbeat_file:
            try:
                return heartbeat_file.read_text()
            except Exception as e:
                logger.warning(f"[{self.config.bot_name}] Failed to read HEARTBEAT.md: {e}")
        return None
    
    async def _execute_heartbeat_md(self) -> CheckResult | None:
        """Execute HEARTBEAT.md tasks (OpenClaw-style).
        
        Reads HEARTBEAT.md from the bot's workspace and executes
        tasks via:
        1. on_heartbeat callback (if provided)
        2. Direct LLM call with routing + reasoning config (if provider available)
        
        Returns:
            CheckResult if HEARTBEAT.md was processed, None if not present
        """
        content = self._read_heartbeat_content()
        
        # Check if HEARTBEAT.md exists and has content
        if _is_heartbeat_empty(content):
            logger.debug(f"[{self.config.bot_name}] HEARTBEAT.md empty or not found")
            return None
        
        # Log heartbeat start
        self._log_heartbeat_start(content)
        
        logger.info(f"[{self.config.bot_name}] Executing HEARTBEAT.md tasks...")
        
        try:
            # Option 1: Use callback if provided
            if self.on_heartbeat:
                response = await self._execute_via_callback()
            # Option 2: Use direct LLM with routing
            elif self.provider:
                response = await self._execute_via_provider(content)
            # No way to execute
            else:
                logger.warning(f"[{self.config.bot_name}] No way to execute HEARTBEAT.md")
                self._log_heartbeat_error("No execution path available")
                return None
            
            # Check if agent said "nothing to do"
            if HEARTBEAT_OK_TOKEN.replace("_", "") in response.upper().replace("_", ""):
                logger.info(f"[{self.config.bot_name}] HEARTBEAT_OK (no action needed)")
                self._log_heartbeat_ok()
                return CheckResult(
                    check_name="HEARTBEAT.md",
                    status=CheckStatus.SUCCESS,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=True,
                    message="No action needed"
                )
            else:
                logger.info(f"[{self.config.bot_name}] HEARTBEAT.md: action taken")
                self._log_heartbeat_action(response)
                return CheckResult(
                    check_name="HEARTBEAT.md",
                    status=CheckStatus.SUCCESS,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=True,
                    message=response[:500]  # Truncate for storage
                )
                
        except Exception as e:
            logger.error(f"[{self.config.bot_name}] HEARTBEAT.md execution failed: {e}")
            self._log_heartbeat_error(str(e))
            return CheckResult(
                check_name="HEARTBEAT.md",
                status=CheckStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=False,
                error=str(e),
                message="Execution failed"
            )
    
    def _log_heartbeat_start(self, content: str) -> None:
        """Log heartbeat tick start."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="heartbeat",
                message=f"Heartbeat tick started for @{self.config.bot_name}",
                details={
                    "bot_name": self.config.bot_name,
                    "tasks": content[:1000] if content else "",
                    "interval_s": self.config.interval_s,
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log heartbeat start: {e}")
    
    def _log_heartbeat_ok(self) -> None:
        """Log heartbeat with no action needed."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="heartbeat",
                message=f"HEARTBEAT_OK - No action needed for @{self.config.bot_name}",
                details={"bot_name": self.config.bot_name, "action": "none"},
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log HEARTBEAT_OK: {e}")
    
    def _log_heartbeat_action(self, response: str) -> None:
        """Log heartbeat action taken."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.ACTION,
                category="heartbeat",
                message=f"Heartbeat action taken by @{self.config.bot_name}",
                details={
                    "bot_name": self.config.bot_name,
                    "response": response[:2000],
                    "action": "completed",
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log heartbeat action: {e}")
    
    def _log_heartbeat_error(self, error: str) -> None:
        """Log heartbeat error."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.ERROR,
                category="heartbeat",
                message=f"Heartbeat error for @{self.config.bot_name}: {error}",
                details={
                    "bot_name": self.config.bot_name,
                    "error": error,
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log heartbeat error: {e}")
    
    async def _execute_via_callback(self) -> str:
        """Execute heartbeat via callback."""
        return await self.on_heartbeat(HEARTBEAT_PROMPT)
    
    async def _execute_via_provider(self, content: str) -> str:
        """Execute heartbeat directly via provider with routing.
        
        Uses smart model selection and bot's reasoning config.
        """
        # Select model using routing
        model = await self._select_model()
        
        # Build messages with reasoning config
        messages = self._build_heartbeat_messages(content)
        
        # Apply reasoning config (temperature, etc.)
        extra_kwargs = {}
        if self.reasoning_config:
            extra_kwargs["temperature"] = self.reasoning_config.temperature
            extra_kwargs["max_tokens"] = self.reasoning_config.max_tokens or 4096
        
        logger.info(
            f"[{self.config.bot_name}] Heartbeat using model: {model}"
        )
        
        response = await self.provider.chat(
            model=model,
            messages=messages,
            **extra_kwargs
        )
        
        return response.content or ""
    
    async def _select_model(self) -> str:
        """Select model using smart routing.
        
        Uses the same routing logic as AgentLoop.
        """
        # Default to provider's default
        default_model = self.provider.get_default_model()
        
        if not self.routing_config or not self.routing_config.enabled:
            return default_model
        
        try:
            from nanobot.agent.stages import RoutingStage, RoutingContext
            
            # Create routing stage
            routing_stage = RoutingStage(config=self.routing_config)
            
            # Create minimal context for heartbeat (no session history)
            routing_ctx = RoutingContext(
                message=None,  # Heartbeat has no user message
                session=None,
                config=self.routing_config
            )
            
            # Execute routing
            routing_ctx = await routing_stage.execute(routing_ctx)
            
            if routing_ctx.model:
                return routing_ctx.model
            
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Routing failed: {e}, using default")
        
        return default_model
    
    def _build_heartbeat_messages(self, content: str) -> list[dict]:
        """Build messages for heartbeat with reasoning config."""
        # Build system prompt with reasoning guidance
        system_prompt = HEARTBEAT_PROMPT
        
        if self.reasoning_config:
            # Add reasoning guidance based on CoT level
            cot_prompt = self.reasoning_config.get_heartbeat_prompt()
            if cot_prompt:
                system_prompt = f"{system_prompt}\n\n{cot_prompt}"
        
        # Add HEARTBEAT.md content
        user_message = f"""Checklist from HEARTBEAT.md:

{content}

Evaluate each item and take any necessary actions. If nothing needs attention, respond with just: HEARTBEAT_OK"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
    
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
            
            # First: Check HEARTBEAT.md (OpenClaw-style)
            heartbeat_result = await self._execute_heartbeat_md()
            
            # Then: Execute registered checks (legacy mode)
            if self.config.parallel_checks:
                results = await self._execute_checks_parallel(tick)
            else:
                results = await self._execute_checks_sequential(tick)
            
            # Include HEARTBEAT.md result if it was executed
            if heartbeat_result:
                results = [heartbeat_result] + results
            
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