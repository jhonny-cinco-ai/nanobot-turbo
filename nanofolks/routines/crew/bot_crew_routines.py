"""Independent crew routines service for each bot (legacy heartbeat).

This module provides BotCrewRoutinesService which manages autonomous
periodic checks for individual bots with full resilience features.

Supports two modes:
1. CREW_ROUTINES.md mode (OpenClaw-style): Bot reads CREW_ROUTINES.md and executes tasks via LLM
2. Legacy check mode: Runs registered programmatic checks
"""

# Note: Class name is legacy, but it is the crew routines engine.

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger

from nanofolks.agent.work_log import LogLevel
from nanofolks.routines.crew.check_registry import check_registry
from nanofolks.routines.crew.crew_routines_models import (
    CheckDefinition,
    CheckResult,
    CheckStatus,
    CrewRoutinesConfig,
    CrewRoutinesHistory,
    CrewRoutinesTick,
)
from nanofolks.security.credential_detector import CredentialDetector
from nanofolks.metrics import get_metrics

# The prompt sent to agent during crew routines (from legacy service)
CREW_ROUTINES_PROMPT = """Read CREW_ROUTINES.md in your workspace (if it exists).
Follow any instructions or tasks listed there.
If nothing needs attention, reply with just: CREW_ROUTINES_OK"""

# Token that indicates "nothing to do"
CREW_ROUTINES_OK_TOKEN = "CREW_ROUTINES_OK"


def _is_crew_routines_empty(content: str | None) -> bool:
    """Check if CREW_ROUTINES.md has no actionable content."""
    if not content:
        return True

    skip_patterns = {"- [ ]", "* [ ]", "- [x]", "* [x]"}

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<!--") or line in skip_patterns:
            continue
        return False

    return True


class BotCrewRoutinesService:
    """Independent crew routines service for a single bot (legacy heartbeat).

    Each bot runs its own crew routines with role-specific:
    - Intervals (default: 60 minutes for specialists, 30 for coordinator)
    - Checks (domain-specific periodic tasks)
    - Execution strategy (parallel/sequential, retries)
    - Resilience (circuit breaker, error handling)

    Example:
        # Create service for a bot
        service = BotCrewRoutinesService(
            bot_instance=researcher_bot,
            config=CrewRoutinesConfig(
                bot_name="researcher",
                interval_s=3600,  # 60 minutes
                checks=[
                    CheckDefinition(name="monitor_data_sources", ...),
                    CheckDefinition(name="track_market_trends", ...),
                ]
            )
        )

        # Start the crew routines
        await service.start()

        # Later, stop it
        service.stop()
    """

    def __init__(
        self,
        bot_instance: Any,
        config: CrewRoutinesConfig,
        workspace: Path | None = None,
        provider=None,
        routing_config=None,
        reasoning_config=None,
        work_log_manager=None,
        on_crew_routines: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_tick_complete: Optional[Callable[[CrewRoutinesTick], None]] = None,
        on_check_complete: Optional[Callable[[CheckResult], None]] = None,
        tool_registry=None,
    ):
        """Initialize crew routines service for a bot.

        Args:
            bot_instance: The bot instance this service manages
            config: CrewRoutines configuration
            workspace: Path to bot's workspace (for CREW_ROUTINES.md)
            provider: LLM provider for crew routines execution
            routing_config: Smart routing config for model selection
            reasoning_config: Reasoning/CoT settings for this bot
            work_log_manager: Work log manager for logging crew routines events
            on_crew_routines: Callback to execute crew routines tasks via LLM
            on_tick_complete: Optional callback when a tick completes
            on_check_complete: Optional callback when a check completes
            tool_registry: Optional tool registry for tool execution during crew routines
        """
        self.bot = bot_instance
        self.config = config
        self.workspace = workspace
        self.provider = provider
        self.routing_config = routing_config
        self.reasoning_config = reasoning_config
        self.work_log_manager = work_log_manager
        self.on_crew_routines = on_crew_routines
        self.on_tick_complete = on_tick_complete
        self.on_check_complete = on_check_complete
        self.tool_registry = tool_registry

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._current_tick: Optional[CrewRoutinesTick] = None
        self._external_scheduler = False

        # History
        self.history = CrewRoutinesHistory(bot_name=config.bot_name)
        self._metrics = get_metrics()

        # Circuit breaker for resilience (optional)
        self.circuit_breaker = None
        if config.circuit_breaker_enabled:
            try:
                from nanofolks.coordinator.circuit_breaker import (
                    CircuitBreaker,
                    CircuitBreakerConfig,
                )
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
        """Check if crew routines are currently running."""
        return self._running

    @property
    def current_tick(self) -> Optional[CrewRoutinesTick]:
        """Get the currently executing tick (if any)."""
        return self._current_tick

    async def start(self) -> None:
        """Start the crew routines service."""
        if self._running:
            logger.warning(f"[{self.config.bot_name}] Crew routines already running")
            return

        if not self.config.enabled:
            logger.info(f"[{self.config.bot_name}] Crew routines disabled")
            return

        if self._external_scheduler:
            self._running = True
            logger.info(f"[{self.config.bot_name}] Crew routines marked running (external scheduler)")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())

        interval_min = self.config.interval_s / 60
        logger.info(
            f"[{self.config.bot_name}] Crew routines started "
            f"(every {interval_min:.0f}min, "
            f"{len(self.config.checks)} checks)"
        )

    def stop(self) -> None:
        """Stop the crew routines service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info(f"[{self.config.bot_name}] Crew routines stopped")

    def set_external_scheduler(self, enabled: bool) -> None:
        """Enable or disable external scheduling for crew routines."""
        self._external_scheduler = enabled
        self._running = enabled

    async def trigger_now(self, reason: str = "manual") -> CrewRoutinesTick:
        """Manually trigger a crew routines tick.

        Args:
            reason: Why crew routines are being triggered

        Returns:
            CrewRoutinesTick result
        """
        return await self._execute_tick(trigger_type="manual", triggered_by=reason)

    def _get_crew_routines_file_path(self) -> Path | None:
        """Get path to bot's CREW_ROUTINES.md file."""
        if self.workspace:
            # Option 1: workspace/bots/{bot_name}/CREW_ROUTINES.md
            bot_crew_routines = self.workspace / "bots" / self.config.bot_name / "CREW_ROUTINES.md"
            if bot_crew_routines.exists():
                return bot_crew_routines

            # Option 2: workspace/CREW_ROUTINES.md (for leader)
            workspace_crew_routines = self.workspace / "CREW_ROUTINES.md"
            if workspace_crew_routines.exists():
                return workspace_crew_routines

        return None

    _crew_routines_secret_warning_shown: set[str] = set()

    def _scan_crew_routines_for_secrets(self, content: str, file_path: Path) -> list[dict]:
        """Scan CREW_ROUTINES.md content for credentials.

        Returns list of detected credentials with type and value (masked).
        """
        detector = CredentialDetector()
        matches = detector.detect(content)

        if matches:
            detected = []
            for match in matches:
                value = match.value
                masked_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
                detected.append({
                    "type": match.credential_type,
                    "masked_value": masked_value,
                    "file": str(file_path),
                })
            return detected

        return []

    def _warn_crew_routines_secrets(self, content: str, file_path: Path) -> None:
        """Warn if CREW_ROUTINES.md contains potential secrets."""
        file_key = str(file_path)
        if file_key in self._crew_routines_secret_warning_shown:
            return

        detected = self._scan_crew_routines_for_secrets(content, file_path)

        if detected:
            self._crew_routines_secret_warning_shown.add(file_key)
            logger.warning(
                f"[{self.config.bot_name}] ⚠️ SECURITY WARNING: Potential secrets detected in {file_path.name}"
            )
            unique_types = set(item['type'] for item in detected)
            for item in detected:
                logger.warning(
                    f"  - {item['type']}: {item['masked_value']} "
                    f"(will be converted to {{symbolic_ref}} before sending to LLM)"
                )
            logger.warning(
                "\n  ➤ To fix this, you can:\n"
            )
            logger.warning(
                f"  Option 1 (Chat): Tell me 'Please secure the keys in {file_path.name}' and I'll help you fix it\n"
            )
            logger.warning(
                "  Option 2 (CLI): Run these commands:\n"
            )
            for key_type in unique_types:
                logger.warning(
                    f"    1. nanofolks security add {key_type}\n"
                    f"    2. Edit {file_path.name} and replace the actual key with {{{{{key_type}}}}}\n"
                )
            logger.warning(
                f"\n  Example: After adding the key, update {file_path.name} to use {{{{{key_type}}}}} instead of the actual key value."
            )

    def _read_crew_routines_content(self) -> str | None:
        """Read CREW_ROUTINES.md content if exists."""
        crew_routines_file = self._get_crew_routines_file_path()
        if crew_routines_file:
            try:
                content = crew_routines_file.read_text(encoding="utf-8")
                self._warn_crew_routines_secrets(content, crew_routines_file)
                return content
            except Exception as e:
                logger.warning(f"[{self.config.bot_name}] Failed to read CREW_ROUTINES.md: {e}")
        return None

    async def _execute_crew_routines_md(self) -> CheckResult | None:
        """Execute CREW_ROUTINES.md tasks (OpenClaw-style).

        Reads CREW_ROUTINES.md from the bot's workspace and executes
        tasks via:
        1. on_crew_routines callback (if provided)
        2. Direct LLM call with routing + reasoning config (if provider available)

        Returns:
            CheckResult if CREW_ROUTINES.md was processed, None if not present
        """
        content = self._read_crew_routines_content()

        # Check if CREW_ROUTINES.md exists and has content
        if _is_crew_routines_empty(content):
            logger.debug(f"[{self.config.bot_name}] CREW_ROUTINES.md empty or not found")
            return None

        # Convert any credentials to symbolic references before sending to LLM
        from nanofolks.security.symbolic_converter import get_symbolic_converter
        converter = get_symbolic_converter()
        conversion_result = converter.convert(content, f"crew_routines:{self.config.bot_name}")
        safe_content = conversion_result.text

        if conversion_result.credentials:
            logger.info(
                f"🔐 [{self.config.bot_name}] Converted {len(conversion_result.credentials)} "
                f"credential(s) to symbolic references in CREW_ROUTINES.md"
            )

        # Log crew routines start
        self._log_crew_routines_start(content)

        logger.info(f"[{self.config.bot_name}] Executing CREW_ROUTINES.md tasks...")

        try:
            # Option 1: Use callback if provided
            if self.on_crew_routines:
                response = await self._execute_via_callback()
            # Option 2: Use direct LLM with routing (use safe_content with refs resolved)
            elif self.provider:
                response = await self._execute_via_provider(safe_content)
            # No way to execute
            else:
                logger.warning(f"[{self.config.bot_name}] No way to execute CREW_ROUTINES.md")
                self._log_crew_routines_error("No execution path available")
                return None

            # Check if agent said "nothing to do"
            if CREW_ROUTINES_OK_TOKEN.replace("_", "") in response.upper().replace("_", ""):
                logger.info(f"[{self.config.bot_name}] CREW_ROUTINES_OK (no action needed)")
                self._log_crew_routines_ok()
                return CheckResult(
                    check_name="CREW_ROUTINES.md",
                    status=CheckStatus.SUCCESS,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=True,
                    message="No action needed"
                )
            else:
                logger.info(f"[{self.config.bot_name}] CREW_ROUTINES.md: action taken")
                self._log_crew_routines_action(response)
                return CheckResult(
                    check_name="CREW_ROUTINES.md",
                    status=CheckStatus.SUCCESS,
                    started_at=datetime.now(),
                    completed_at=datetime.now(),
                    success=True,
                    message=response[:500]  # Truncate for storage
                )

        except Exception as e:
            logger.error(f"[{self.config.bot_name}] CREW_ROUTINES.md execution failed: {e}")
            self._log_crew_routines_error(str(e))
            return CheckResult(
                check_name="CREW_ROUTINES.md",
                status=CheckStatus.FAILED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                success=False,
                error=str(e),
                message="Execution failed"
            )

    def _log_crew_routines_start(self, content: str) -> None:
        """Log crew routines tick start."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="crew_routines",
                message=f"Crew routines tick started for @{self.config.bot_name}",
                details={
                    "bot_name": self.config.bot_name,
                    "tasks": content[:1000] if content else "",
                    "interval_s": self.config.interval_s,
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log crew routines start: {e}")

    def _log_crew_routines_ok(self) -> None:
        """Log crew routines with no action needed."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="crew_routines",
                message=f"CREW_ROUTINES_OK - No action needed for @{self.config.bot_name}",
                details={"bot_name": self.config.bot_name, "action": "none"},
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log CREW_ROUTINES_OK: {e}")

    def _log_crew_routines_action(self, response: str) -> None:
        """Log crew routines action taken."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.ACTION,
                category="crew_routines",
                message=f"Crew routines action taken by @{self.config.bot_name}",
                details={
                    "bot_name": self.config.bot_name,
                    "response": response[:2000],
                    "action": "completed",
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log crew routines action: {e}")

    def _log_crew_routines_error(self, error: str) -> None:
        """Log crew routines error."""
        if not self.work_log_manager:
            return
        try:
            self.work_log_manager.log(
                level=LogLevel.ERROR,
                category="crew_routines",
                message=f"Crew routines error for @{self.config.bot_name}: {error}",
                details={
                    "bot_name": self.config.bot_name,
                    "error": error,
                },
                triggered_by=self.config.bot_name,
                bot_name=self.config.bot_name,
            )
        except Exception as e:
            logger.warning(f"[{self.config.bot_name}] Failed to log crew routines error: {e}")

    async def _execute_via_callback(self) -> str:
        """Execute crew routines via callback."""
        return await self.on_crew_routines(CREW_ROUTINES_PROMPT)

    async def _execute_via_provider(self, content: str) -> str:
        """Execute crew routines directly via provider with routing and optional tools.

        Uses smart model selection and bot's reasoning config.
        If tool_registry is provided, executes tools as needed.
        """
        # Select model using routing
        model = await self._select_model()

        # Build messages
        messages = self._build_crew_routines_messages(content)

        # Apply reasoning config (temperature, etc.)
        extra_kwargs = {}
        if self.reasoning_config:
            extra_kwargs["temperature"] = self.reasoning_config.temperature
            extra_kwargs["max_tokens"] = self.reasoning_config.max_tokens or 4096

        # Get tool definitions if registry exists
        tool_definitions = None
        if self.tool_registry:
            tool_definitions = self.tool_registry.get_definitions()

        logger.info(
            f"[{self.config.bot_name}] CrewRoutines using model: {model}"
            + (f" with {len(tool_definitions)} tools" if tool_definitions else "")
        )

        # Execute with tool support if available
        if tool_definitions:
            return await self._execute_with_tools(
                messages=messages,
                model=model,
                extra_kwargs=extra_kwargs,
            )

        # Simple LLM call without tools
        response = await self.provider.chat(
            model=model,
            messages=messages,
            **extra_kwargs
        )

        return response.content or ""

    async def _execute_with_tools(
        self,
        messages: list[dict],
        model: str,
        extra_kwargs: dict,
    ) -> str:
        """Execute crew routines with tool support.

        Args:
            messages: Message list for LLM
            model: Model to use
            extra_kwargs: Additional kwargs (temperature, max_tokens)

        Returns:
            Final response content
        """
        tool_definitions = self.tool_registry.get_definitions()
        max_iterations = 10

        for iteration in range(max_iterations):
            response = await self.provider.chat(
                model=model,
                messages=messages,
                tools=tool_definitions,
                **extra_kwargs
            )

            content = response.content or ""
            tool_calls = getattr(response, 'tool_calls', None) or []

            if not tool_calls:
                return content

            # Execute tool calls
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments

                # Parse arguments
                if isinstance(tool_args, str):
                    import json
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                logger.debug(f"[{self.config.bot_name}] CrewRoutines executing: {tool_name}")
                result = await self.tool_registry.execute(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": result,
                })

            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in tool_calls
                ],
            })

        logger.warning(f"[{self.config.bot_name}] CrewRoutines max iterations reached")
        return content

    async def _select_model(self) -> str:
        """Select model using smart routing.

        Uses the same routing logic as AgentLoop.
        """
        # Default to provider's default
        default_model = self.provider.get_default_model()

        if not self.routing_config or not self.routing_config.enabled:
            return default_model

        try:
            from nanofolks.agent.stages import RoutingContext, RoutingStage

            # Create routing stage
            routing_stage = RoutingStage(config=self.routing_config)

            # Create minimal context for crew routines (no session history)
            routing_ctx = RoutingContext(
                message=None,  # CrewRoutines has no user message
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

    def _build_crew_routines_messages(self, content: str) -> list[dict]:
        """Build messages for crew routines with reasoning config."""
        # Build system prompt with reasoning guidance
        system_prompt = CREW_ROUTINES_PROMPT

        if self.reasoning_config:
            # Add reasoning guidance based on CoT level
            cot_prompt = self.reasoning_config.get_crew_routines_prompt()
            if cot_prompt:
                system_prompt = f"{system_prompt}\n\n{cot_prompt}"

        # Add CREW_ROUTINES.md content
        user_message = f"""Checklist from CREW_ROUTINES.md:

{content}

Evaluate each item and take any necessary actions. If nothing needs attention, respond with just: CREW_ROUTINES_OK"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    async def _run_loop(self) -> None:
        """Main crew routines loop."""
        while self._running:
            try:
                # Wait for interval
                await asyncio.sleep(self.config.interval_s)

                if not self._running:
                    break

                # Execute tick
                await self._execute_tick(trigger_type="scheduled")

            except asyncio.CancelledError:
                logger.debug(f"[{self.config.bot_name}] CrewRoutines loop cancelled")
                break
            except Exception as e:
                logger.error(f"[{self.config.bot_name}] CrewRoutines error: {e}")
                # Continue loop even on error

    async def _execute_tick(
        self,
        trigger_type: str = "scheduled",
        triggered_by: Optional[str] = None
    ) -> CrewRoutinesTick:
        """Execute a single crew routines tick.

        Args:
            trigger_type: Type of trigger (scheduled, manual, event)
            triggered_by: What triggered this tick

        Returns:
            CrewRoutinesTick with results
        """
        tick_id = str(uuid.uuid4())[:8]
        tick = CrewRoutinesTick(
            tick_id=tick_id,
            bot_name=self.config.bot_name,
            started_at=datetime.now(),
            config=self.config,
            trigger_type=trigger_type,
            triggered_by=triggered_by
        )
        self._current_tick = tick
        self._metrics.incr(
            "crew_routines.tick.started",
            tags={"bot": self.config.bot_name, "trigger": trigger_type},
        )

        logger.info(
            f"[{self.config.bot_name}] Tick {tick_id} started "
            f"({len(self.config.checks)} checks)"
        )

        try:
            # Check circuit breaker
            if self.circuit_breaker:
                from nanofolks.coordinator.circuit_breaker import CircuitState
                state = self.circuit_breaker.get_state(self.config.bot_name)
                if state == CircuitState.OPEN:
                    logger.warning(
                        f"[{self.config.bot_name}] Circuit breaker OPEN, "
                        f"skipping tick"
                    )
                    tick.status = "skipped"
                    self._metrics.incr(
                        "crew_routines.tick.skipped",
                        tags={"bot": self.config.bot_name},
                    )
                    return tick

            # First: Check CREW_ROUTINES.md (OpenClaw-style)
            crew_routines_result = await self._execute_crew_routines_md()

            # Then: Execute registered checks (legacy mode)
            if self.config.parallel_checks:
                results = await self._execute_checks_parallel(tick)
            else:
                results = await self._execute_checks_sequential(tick)

            # Include CREW_ROUTINES.md result if it was executed
            if crew_routines_result:
                results = [crew_routines_result] + results

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
            if tick.status == "completed":
                self._metrics.incr(
                    "crew_routines.tick.completed",
                    tags={"bot": self.config.bot_name},
                )
            else:
                self._metrics.incr(
                    "crew_routines.tick.completed_with_failures",
                    tags={"bot": self.config.bot_name},
                )

        except Exception as e:
            tick.status = "failed"
            logger.error(f"[{self.config.bot_name}] Tick {tick_id} failed: {e}")
            self._metrics.incr(
                "crew_routines.tick.failed",
                tags={"bot": self.config.bot_name},
            )

            # Record circuit breaker failure
            if self.circuit_breaker:
                self.circuit_breaker._record_failure(self.config.bot_name, 0)

        finally:
            self._current_tick = None

        return tick

    async def _execute_checks_parallel(self, tick: CrewRoutinesTick) -> List[CheckResult]:
        """Execute checks in parallel with concurrency limit."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_checks)

        async def run_with_limit(check_def: CheckDefinition) -> CheckResult:
            async with semaphore:
                return await self._execute_single_check(check_def, tick)

        tasks = [run_with_limit(check) for check in self.config.checks if check.enabled]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_checks_sequential(self, tick: CrewRoutinesTick) -> List[CheckResult]:
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
        tick: CrewRoutinesTick
    ) -> CheckResult:
        """Execute a single check with retry logic."""
        self._metrics.incr(
            "crew_routines.check.started",
            tags={"bot": self.config.bot_name, "check": check_def.name},
        )

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
                self._metrics.incr(
                    "crew_routines.check.completed",
                    tags={"bot": self.config.bot_name, "check": check_def.name},
                )
                return result


            # Retry delay
            if attempt < self.config.retry_attempts - 1:
                delay = self.config.retry_delay_s * (self.config.retry_backoff ** attempt)
                logger.warning(
                    f"[{self.config.bot_name}] Check '{check_def.name}' "
                    f"failed (attempt {attempt + 1}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        self._metrics.incr(
            "crew_routines.check.failed",
            tags={"bot": self.config.bot_name, "check": check_def.name},
        )
        return result

    def get_status(self) -> Dict[str, Any]:
        """Get current crew routines status.

        Returns:
            Status dictionary with metrics
        """
        return {
            "bot_name": self.config.bot_name,
            "running": self._running,
            "enabled": self.config.enabled,
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


__all__ = ["BotCrewRoutinesService"]
