# Multi-Heartbeat Implementation Plan

**Status:** 📋 Planning Phase  
**Created:** February 13, 2026  
**Estimated Duration:** 3-4 days  
**Priority:** High - Core Infrastructure Enhancement

> ⭐ **Enables each bot to run autonomous periodic checks aligned with their role**

---

## Executive Summary

Currently, nanobot uses a single centralized heartbeat that processes all periodic tasks through one agent instance. This creates a bottleneck and doesn't leverage our multi-agent architecture.

**The Solution:** Implement **per-bot independent heartbeats** where each of the 6 bots (nanobot + 5 specialists) runs their own heartbeat with:
- **Standardized intervals** (60min default for all specialists, 30min for coordinator)
- **User customization** (adjust intervals per bot via configuration)
- **Domain-specific checklists** (coder checks repos, social checks posts)
- **Autonomous execution** (bots self-manage their periodic tasks)
- **Cross-bot coordination** (when tasks require multiple bots)

**Interval Strategy:**
- **Default:** 60 minutes for all specialist bots (researcher, coder, social, creative, auditor)
- **Coordinator:** 30 minutes for nanobot (needs faster coordination)
- **User Control:** All intervals customizable via configuration (minimum: 5 minutes)
- **Rationale:** Simple defaults that work for most use cases, with flexibility to optimize per domain

---

## Current State Analysis

### Problems with Centralized Heartbeat

```
┌─────────────────────────────────────────────────────────────┐
│                  CURRENT: Single Heartbeat                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  HeartbeatService (30min)                                    │
│       │                                                      │
│       ▼                                                      │
│  HEARTBEAT.md                                                │
│  ├─ Check GitHub issues (coding task)                        │
│  ├─ Research market trends (research task)                   │
│  ├─ Post to Twitter (social task)                            │
│  └─ Review code quality (audit task)                         │
│       │                                                      │
│       ▼                                                      │
│  Single Agent (nanobot only)                                 │
│  • Handles ALL tasks regardless of domain                    │
│  • No expertise-based routing                                │
│  • No load distribution                                      │
│  • No autonomous behavior                                    │
│  • One failure = all tasks fail                              │
│                                                              │
│  ❌ Wastes multi-agent infrastructure                        │
│  ❌ No role specialization                                   │
│  ❌ Single point of failure                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Issues Identified

1. **Inefficient Task Distribution**
   - All periodic tasks go to one agent
   - Specialist bots sit idle during heartbeats
   - No parallelism in task execution

2. **Inflexible Intervals**
   - Single 30-minute interval for all task types
   - Cannot adjust per bot based on domain needs
   - User cannot customize intervals per bot
   - One-size-fits-all approach wastes resources

3. **No Autonomy**
   - Bots can't self-initiate their domain-specific checks
   - HEARTBEAT.md must manually list all tasks
   - Bots can't learn what to check based on their role

4. **Lack of Resilience**
   - If heartbeat handler fails, all periodic tasks stop
   - No circuit breaker protection per bot
   - No fallback when one bot is overloaded

5. **Poor Transparency**
   - Can't tell which bot handled which periodic task
   - No audit trail for autonomous actions
   - No explanation of why certain checks were performed

---

## Target Architecture

### Multi-Heartbeat System Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TARGET: Multi-Heartbeat Architecture              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Each bot runs INDEPENDENT heartbeat:                               │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ @researcher │  │   @coder    │  │   @social   │                 │
│  │  Heartbeat  │  │  Heartbeat  │  │  Heartbeat  │                 │
│  │  (60 min)   │  │  (30 min)   │  │  (15 min)   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                          │
│  Check: │         Check: │         Check: │                          │
│  • Data │         • GitHub│         • Scheduled│                     │
│    sources│         issues│           posts│                        │
│  • Market│         • Build │         • Mentions│                     │
│    trends│           status│         • Engagement│                   │
│  • Comp-│         • Security│         • Trending│                     │
│    etitors│          scans│           topics│                       │
│         │                │                │                          │
│         └────────────────┴────────────────┘                          │
│                          │                                           │
│                          ▼                                           │
│              ┌─────────────────────┐                                │
│              │   CoordinatorBot    │                                │
│              │   ( coordination    │                                │
│              │     heartbeat )     │                                │
│              └─────────────────────┘                                │
│                          │                                           │
│              Check: Cross-bot dependencies                          │
│              Check: Task handoffs                                   │
│              Check: Escalation needs                                │
│                                                                      │
│  ✅ Each bot autonomous in their domain                             │
│  ✅ Role-optimized intervals                                        │
│  ✅ Parallel execution                                              │
│  ✅ Circuit breaker per bot                                         │
│  ✅ Full audit trail                                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **BotHeartbeatService** - Independent heartbeat per bot
2. **HeartbeatConfig** - Role-specific configuration
3. **CheckRunner** - Executes domain-specific checks
4. **HeartbeatCoordinator** - Manages cross-bot coordination
5. **CheckRegistry** - Pluggable check system

---

## Implementation Phases

### Phase 1: Core Infrastructure (Day 1)
**Goal:** Build base heartbeat service and config system

#### 1.1: Data Models
**File:** `nanobot/heartbeat/models.py`

```python
"""Data models for multi-heartbeat system."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar


class CheckPriority(Enum):
    """Priority levels for heartbeat checks."""
    CRITICAL = "critical"    # Run immediately, alert on failure
    HIGH = "high"           # Run promptly, log failures  
    NORMAL = "normal"       # Run during normal heartbeat
    LOW = "low"             # Run when resources available


class CheckStatus(Enum):
    """Status of a heartbeat check execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class CheckDefinition:
    """Definition of a single heartbeat check."""
    name: str                           # Unique identifier
    description: str                    # Human-readable description
    priority: CheckPriority
    max_duration_s: float = 60.0       # Timeout
    retry_attempts: int = 1
    dependencies: List[str] = field(default_factory=list)  # Other checks that must pass first
    enabled: bool = True
    
    # Dynamic configuration
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class CheckResult:
    """Result of executing a heartbeat check."""
    check_name: str
    status: CheckStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    
    # Outcome
    success: bool = False
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Error info
    error: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Action taken
    action_taken: Optional[str] = None
    notifications_sent: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "action_taken": self.action_taken,
        }


@dataclass
class HeartbeatConfig:
    """Configuration for a bot's heartbeat."""
    bot_name: str
    interval_s: int = 3600              # 60 minutes default (1 hour)
    max_execution_time_s: int = 300     # 5 minutes max per tick
    enabled: bool = True
    
    # Check definitions
    checks: List[CheckDefinition] = field(default_factory=list)
    
    # Execution strategy
    parallel_checks: bool = True        # Run independent checks in parallel
    max_concurrent_checks: int = 3      # Limit parallelism
    stop_on_first_failure: bool = False # Continue other checks if one fails
    
    # Retry configuration
    retry_attempts: int = 2
    retry_delay_s: float = 5.0
    retry_backoff: float = 2.0
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 3  # Failures before opening
    circuit_breaker_timeout_s: int = 300  # 5 minutes
    
    # Notification settings
    notify_on_failure: bool = True
    notify_on_success: bool = False     # Only notify on failure by default
    notification_channels: List[str] = field(default_factory=lambda: ["coordinator"])
    
    # Logging
    log_level: str = "INFO"
    retain_history_count: int = 100     # Keep last N heartbeat results


@dataclass
class HeartbeatTick:
    """A single heartbeat execution."""
    tick_id: str
    bot_name: str
    started_at: datetime
    config: HeartbeatConfig
    
    # Execution tracking
    results: List[CheckResult] = field(default_factory=list)
    status: str = "running"  # running, completed, failed, timeout
    
    # Metadata
    trigger_type: str = "scheduled"  # scheduled, manual, event_driven
    triggered_by: Optional[str] = None  # Event that triggered this tick
    
    def get_success_rate(self) -> float:
        """Calculate success rate of checks."""
        if not self.results:
            return 0.0
        successful = sum(1 for r in self.results if r.success)
        return successful / len(self.results)
    
    def get_failed_checks(self) -> List[CheckResult]:
        """Get list of failed checks."""
        return [r for r in self.results if not r.success]
    
    def duration_ms(self) -> float:
        """Get total duration in milliseconds."""
        if not self.results:
            return 0.0
        start = min(r.started_at for r in self.results)
        end_times = [r.completed_at for r in self.results if r.completed_at]
        if end_times:
            end = max(end_times)
            return (end - start).total_seconds() * 1000
        return 0.0


@dataclass
class HeartbeatHistory:
    """History of heartbeat executions for a bot."""
    bot_name: str
    ticks: List[HeartbeatTick] = field(default_factory=list)
    
    # Statistics
    total_ticks: int = 0
    successful_ticks: int = 0
    failed_ticks: int = 0
    
    last_tick_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    
    def add_tick(self, tick: HeartbeatTick):
        """Add a tick to history."""
        self.ticks.append(tick)
        self.total_ticks += 1
        self.last_tick_at = tick.started_at
        
        if tick.status == "completed":
            self.successful_ticks += 1
            self.last_success_at = tick.started_at
        else:
            self.failed_ticks += 1
            self.last_failure_at = tick.started_at
        
        # Trim history to retain limit
        retain_limit = tick.config.retain_history_count if tick.config else 100
        if len(self.ticks) > retain_limit:
            self.ticks = self.ticks[-retain_limit:]
    
    def get_average_success_rate(self, last_n: int = 10) -> float:
        """Get average success rate over last N ticks."""
        if not self.ticks:
            return 0.0
        recent = self.ticks[-last_n:]
        return sum(t.get_success_rate() for t in recent) / len(recent)
    
    def get_uptime_percentage(self, window_hours: int = 24) -> float:
        """Calculate uptime percentage over time window."""
        if not self.ticks:
            return 0.0
        
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent_ticks = [t for t in self.ticks if t.started_at > cutoff]
        
        if not recent_ticks:
            return 0.0
        
        successful = sum(1 for t in recent_ticks if t.status == "completed")
        return (successful / len(recent_ticks)) * 100
```

#### 1.2: Check Registry System
**File:** `nanobot/heartbeat/check_registry.py`

```python
"""Pluggable check registry for heartbeat system."""

import inspect
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass
from datetime import datetime
import asyncio

from loguru import logger

from nanobot.heartbeat.models import CheckDefinition, CheckResult, CheckStatus


@dataclass
class RegisteredCheck:
    """A registered check with its handler and metadata."""
    definition: CheckDefinition
    handler: Callable[..., Any]
    is_async: bool
    bot_domains: List[str]  # Which bot types can use this check


class CheckRegistry:
    """Registry of available heartbeat checks.
    
    Checks can be registered dynamically and are discovered automatically
    for appropriate bot types.
    """
    
    def __init__(self):
        self._checks: Dict[str, RegisteredCheck] = {}
    
    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        priority: str = "normal",
        max_duration_s: float = 60.0,
        bot_domains: Optional[List[str]] = None,
        **config
    ) -> CheckDefinition:
        """Register a new check.
        
        Args:
            name: Unique check identifier
            handler: Function to execute (can be sync or async)
            description: Human-readable description
            priority: Check priority (critical/high/normal/low)
            max_duration_s: Maximum execution time
            bot_domains: List of bot domains that can use this check
            **config: Additional check configuration
            
        Returns:
            CheckDefinition for the registered check
        """
        from nanobot.heartbeat.models import CheckDefinition, CheckPriority
        
        if name in self._checks:
            logger.warning(f"Check '{name}' already registered, overwriting")
        
        # Determine if handler is async
        is_async = asyncio.iscoroutinefunction(handler)
        
        # Create definition
        definition = CheckDefinition(
            name=name,
            description=description,
            priority=CheckPriority(priority),
            max_duration_s=max_duration_s,
            config=config
        )
        
        # Store registration
        self._checks[name] = RegisteredCheck(
            definition=definition,
            handler=handler,
            is_async=is_async,
            bot_domains=bot_domains or ["all"]
        )
        
        logger.info(f"Registered heartbeat check: {name}")
        return definition
    
    def unregister(self, name: str) -> bool:
        """Unregister a check.
        
        Args:
            name: Check name to unregister
            
        Returns:
            True if unregistered, False if not found
        """
        if name in self._checks:
            del self._checks[name]
            logger.info(f"Unregistered heartbeat check: {name}")
            return True
        return False
    
    def get_check(self, name: str) -> Optional[RegisteredCheck]:
        """Get a registered check by name."""
        return self._checks.get(name)
    
    def list_checks(
        self,
        bot_domain: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[CheckDefinition]:
        """List available checks with optional filtering.
        
        Args:
            bot_domain: Filter by bot domain
            priority: Filter by priority level
            
        Returns:
            List of check definitions
        """
        checks = []
        
        for name, registered in self._checks.items():
            # Filter by bot domain
            if bot_domain and bot_domain not in registered.bot_domains:
                if "all" not in registered.bot_domains:
                    continue
            
            # Filter by priority
            if priority and registered.definition.priority.value != priority:
                continue
            
            checks.append(registered.definition)
        
        return checks
    
    async def execute_check(
        self,
        name: str,
        bot_instance: Any,
        timeout_s: Optional[float] = None
    ) -> CheckResult:
        """Execute a registered check.
        
        Args:
            name: Check name to execute
            bot_instance: Bot instance to pass to handler
            timeout_s: Override timeout (uses check default if None)
            
        Returns:
            CheckResult with execution outcome
        """
        registered = self._checks.get(name)
        if not registered:
            return CheckResult(
                check_name=name,
                status=CheckStatus.FAILED,
                started_at=datetime.now(),
                success=False,
                error=f"Check '{name}' not found in registry",
                error_type="NotFoundError"
            )
        
        definition = registered.definition
        timeout = timeout_s or definition.max_duration_s
        
        result = CheckResult(
            check_name=name,
            status=CheckStatus.RUNNING,
            started_at=datetime.now()
        )
        
        try:
            # Execute with timeout
            if registered.is_async:
                outcome = await asyncio.wait_for(
                    registered.handler(bot_instance, definition.config),
                    timeout=timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                outcome = await asyncio.wait_for(
                    loop.run_in_executor(None, registered.handler, bot_instance, definition.config),
                    timeout=timeout
                )
            
            # Process outcome
            result.completed_at = datetime.now()
            result.duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000
            
            if isinstance(outcome, dict):
                result.success = outcome.get("success", True)
                result.message = outcome.get("message", "")
                result.data = outcome.get("data", {})
                result.action_taken = outcome.get("action_taken")
            else:
                # Treat return value as success indicator
                result.success = bool(outcome)
                result.message = str(outcome) if outcome else "Check completed"
            
            result.status = CheckStatus.SUCCESS if result.success else CheckStatus.FAILED
            
        except asyncio.TimeoutError:
            result.status = CheckStatus.TIMEOUT
            result.completed_at = datetime.now()
            result.error = f"Check timed out after {timeout}s"
            result.error_type = "TimeoutError"
            result.success = False
            
        except Exception as e:
            result.status = CheckStatus.FAILED
            result.completed_at = datetime.now()
            result.error = str(e)
            result.error_type = type(e).__name__
            result.success = False
            logger.error(f"Check '{name}' failed: {e}")
        
        return result


# Global registry instance
check_registry = CheckRegistry()


def check(
    name: Optional[str] = None,
    description: str = "",
    priority: str = "normal",
    max_duration_s: float = 60.0,
    bot_domains: Optional[List[str]] = None,
    **config
):
    """Decorator to register a function as a heartbeat check.
    
    Usage:
        @check(
            name="github_issues",
            description="Check for new GitHub issues",
            priority="high",
            bot_domains=["development"]
        )
        async def check_github_issues(bot, config):
            # Implementation
            return {"success": True, "issues_found": 5}
    """
    def decorator(func: Callable) -> Callable:
        check_name = name or func.__name__
        check_registry.register(
            name=check_name,
            handler=func,
            description=description or func.__doc__ or "",
            priority=priority,
            max_duration_s=max_duration_s,
            bot_domains=bot_domains,
            **config
        )
        return func
    return decorator
```

#### 1.3: Bot Heartbeat Service
**File:** `nanobot/heartbeat/bot_heartbeat.py`

```python
"""Independent heartbeat service for each bot."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from nanobot.heartbeat.models import (
    HeartbeatConfig, HeartbeatTick, CheckResult, 
    CheckStatus, HeartbeatHistory
)
from nanobot.heartbeat.check_registry import check_registry
from nanobot.coordinator.circuit_breaker import CircuitBreaker, CircuitState


class BotHeartbeatService:
    """Independent heartbeat service for a single bot.
    
    Each bot runs its own heartbeat with role-specific:
    - Intervals (social: 15min, research: 60min)
    - Checks (domain-specific tasks)
    - Configuration (parallelism, retries, etc.)
    """
    
    def __init__(
        self,
        bot_instance: Any,
        config: HeartbeatConfig,
        on_tick_complete: Optional[Callable[[HeartbeatTick], None]] = None,
        on_check_complete: Optional[Callable[[CheckResult], None]] = None
    ):
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
        
        # Circuit breaker for resilience
        self.circuit_breaker = None
        if config.circuit_breaker_enabled:
            from nanobot.coordinator.circuit_breaker import CircuitBreakerConfig
            cb_config = CircuitBreakerConfig(
                failure_threshold=config.circuit_breaker_threshold,
                timeout=config.circuit_breaker_timeout_s
            )
            self.circuit_breaker = CircuitBreaker(cb_config)
            self.circuit_breaker.register_bot(config.bot_name)
    
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
            f"(every {interval_min:.1f}min, "
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
            reason: Why this tick was triggered (manual, event, etc.)
            
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
        
        async def run_with_limit(check_def) -> CheckResult:
            async with semaphore:
                return await self._execute_single_check(check_def, tick)
        
        tasks = [run_with_limit(check) for check in self.config.checks]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _execute_checks_sequential(self, tick: HeartbeatTick) -> List[CheckResult]:
        """Execute checks one at a time."""
        results = []
        
        for check_def in self.config.checks:
            result = await self._execute_single_check(check_def, tick)
            results.append(result)
            
            # Respect stop_on_first_failure
            if not result.success and self.config.stop_on_first_failure:
                break
        
        return results
    
    async def _execute_single_check(
        self,
        check_def: Any,
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
            
            # Check result
            if result.success:
                break
            
            last_error = result.error
            
            # Retry delay
            if attempt < self.config.retry_attempts - 1:
                delay = self.config.retry_delay_s * (self.config.retry_backoff ** attempt)
                logger.warning(
                    f"[{self.config.bot_name}] Check '{check_def.name}' "
                    f"failed (attempt {attempt + 1}), retrying in {delay}s"
                )
                await asyncio.sleep(delay)
        
        # Callback
        if self.on_check_complete:
            try:
                self.on_check_complete(result)
            except Exception as e:
                logger.error(f"Check complete callback error: {e}")
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current heartbeat status."""
        return {
            "bot_name": self.config.bot_name,
            "running": self._running,
            "interval_s": self.config.interval_s,
            "checks_count": len(self.config.checks),
            "current_tick": self._current_tick.tick_id if self._current_tick else None,
            "history": {
                "total_ticks": self.history.total_ticks,
                "successful_ticks": self.history.successful_ticks,
                "failed_ticks": self.history.failed_ticks,
                "success_rate": self.history.get_average_success_rate(),
                "uptime_24h": self.history.get_uptime_percentage(24)
            }
        }
```

**Acceptance Criteria:**
- ✅ Data models support per-bot configuration
- ✅ Check registry allows dynamic registration
- ✅ BotHeartbeatService runs independently per bot
- ✅ Parallel/sequential execution modes
- ✅ Retry logic with backoff
- ✅ Circuit breaker integration
- ✅ Comprehensive history tracking

---

### Phase 2: Role-Specific Configurations (Day 1-2)
**Goal:** Create heartbeat configs for each bot type

#### 2.1: Researcher Bot Checks
**File:** `nanobot/bots/checks/researcher_checks.py`

```python
"""Heartbeat checks for ResearcherBot (Navigator)."""

from datetime import datetime
from typing import Dict, Any, List
from loguru import logger

from nanobot.heartbeat.check_registry import check
from nanobot.heartbeat.models import CheckDefinition


@check(
    name="monitor_data_sources",
    description="Check monitored data sources for updates",
    priority="high",
    max_duration_s=120.0,
    bot_domains=["research"],
    sources=[]  # Configurable list of sources
)
async def monitor_data_sources(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check configured data sources for new updates."""
    sources = config.get("sources", [])
    
    if not sources:
        return {"success": True, "message": "No data sources configured"}
    
    updates_found = []
    
    for source in sources:
        try:
            # Check source (implementation depends on source type)
            last_check = bot.private_memory.get("last_source_check", {}).get(source, 0)
            new_items = await bot.check_source_updates(source, since=last_check)
            
            if new_items:
                updates_found.append({
                    "source": source,
                    "new_items": len(new_items)
                })
                
                # Update memory
                if "last_source_check" not in bot.private_memory:
                    bot.private_memory["last_source_check"] = {}
                bot.private_memory["last_source_check"][source] = datetime.now().timestamp()
                
        except Exception as e:
            logger.error(f"Error checking source {source}: {e}")
    
    if updates_found:
        # Notify coordinator
        await bot.notify_coordinator(
            f"Found updates in {len(updates_found)} data sources",
            data={"updates": updates_found}
        )
    
    return {
        "success": True,
        "sources_checked": len(sources),
        "updates_found": len(updates_found),
        "action_taken": "notified_team" if updates_found else None
    }


@check(
    name="track_market_trends",
    description="Analyze market trends and detect significant changes",
    priority="normal",
    max_duration_s=180.0,
    bot_domains=["research"],
    markets=[]  # Configurable markets to track
)
async def track_market_trends(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Track market trends and alert on significant changes."""
    markets = config.get("markets", [])
    
    if not markets:
        return {"success": True, "message": "No markets configured for tracking"}
    
    significant_changes = []
    
    for market in markets:
        try:
            # Analyze trend
            trend = await bot.analyze_market_trend(market)
            
            if trend.significant_change:
                significant_changes.append({
                    "market": market,
                    "change_percent": trend.change_percent,
                    "direction": trend.direction,
                    "confidence": trend.confidence
                })
                
        except Exception as e:
            logger.error(f"Error analyzing market {market}: {e}")
    
    if significant_changes:
        # High confidence changes get escalated
        high_confidence = [c for c in significant_changes if c["confidence"] > 0.8]
        
        if high_confidence:
            await bot.escalate_to_coordinator(
                f"Significant market changes detected",
                priority="high",
                data={"changes": high_confidence}
            )
    
    return {
        "success": True,
        "markets_analyzed": len(markets),
        "significant_changes": len(significant_changes),
        "action_taken": "escalated" if significant_changes else None
    }


@check(
    name="monitor_research_deadlines",
    description="Check for approaching research deadlines",
    priority="critical",
    max_duration_s=30.0,
    bot_domains=["research"],
    warning_days=3
)
async def monitor_research_deadlines(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor research project deadlines and alert on approaching dates."""
    warning_days = config.get("warning_days", 3)
    
    # Get active research projects
    projects = await bot.get_active_research_projects()
    
    approaching_deadlines = []
    
    for project in projects:
        if project.deadline:
            days_until = (project.deadline - datetime.now()).days
            
            if days_until <= warning_days:
                approaching_deadlines.append({
                    "project": project.name,
                    "deadline": project.deadline.isoformat(),
                    "days_remaining": days_until,
                    "urgency": "critical" if days_until < 1 else "high"
                })
    
    if approaching_deadlines:
        # Sort by urgency
        approaching_deadlines.sort(key=lambda x: x["days_remaining"])
        
        await bot.notify_coordinator(
            f"{len(approaching_deadlines)} research deadlines approaching",
            priority="high",
            data={"deadlines": approaching_deadlines}
        )
    
    return {
        "success": True,
        "projects_checked": len(projects),
        "approaching_deadlines": len(approaching_deadlines),
        "action_taken": "notified_team" if approaching_deadlines else None
    }


@check(
    name="update_competitor_tracking",
    description="Update competitor tracking data",
    priority="normal",
    max_duration_s=300.0,
    bot_domains=["research"],
    competitors=[]  # Configurable competitor list
)
async def update_competitor_tracking(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update competitor tracking and report significant changes."""
    competitors = config.get("competitors", [])
    
    if not competitors:
        return {"success": True, "message": "No competitors configured for tracking"}
    
    updates = []
    
    for competitor in competitors:
        try:
            # Check for updates
            changes = await bot.check_competitor_updates(competitor)
            
            if changes:
                updates.append({
                    "competitor": competitor,
                    "changes": changes
                })
                
        except Exception as e:
            logger.error(f"Error checking competitor {competitor}: {e}")
    
    if updates:
        await bot.notify_coordinator(
            f"Competitor updates detected for {len(updates)} competitors",
            data={"updates": updates}
        )
    
    return {
        "success": True,
        "competitors_checked": len(competitors),
        "updates_found": len(updates),
        "action_taken": "notified_team" if updates else None
    }
```

#### 2.2: Coder Bot Checks
**File:** `nanobot/bots/checks/coder_checks.py`

```python
"""Heartbeat checks for CoderBot (Gunner)."""

from typing import Dict, Any, List
from loguru import logger

from nanobot.heartbeat.check_registry import check


@check(
    name="check_github_issues",
    description="Check GitHub repositories for new issues",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["development"],
    repositories=[]  # Configurable repos
)
async def check_github_issues(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check configured GitHub repositories for new issues."""
    repositories = config.get("repositories", [])
    
    if not repositories:
        return {"success": True, "message": "No repositories configured"}
    
    total_issues = 0
    critical_issues = []
    
    for repo in repositories:
        try:
            # Check for new issues
            since = bot.private_memory.get("last_issue_check", {}).get(repo)
            issues = await bot.check_repository_issues(repo, since=since)
            
            total_issues += len(issues)
            
            # Identify critical issues
            critical = [i for i in issues if i.priority in ["critical", "high"]]
            if critical:
                critical_issues.append({
                    "repository": repo,
                    "critical_count": len(critical),
                    "issues": critical
                })
            
            # Update memory
            if "last_issue_check" not in bot.private_memory:
                bot.private_memory["last_issue_check"] = {}
            bot.private_memory["last_issue_check"][repo] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error checking repo {repo}: {e}")
    
    if critical_issues:
        await bot.escalate_to_coordinator(
            f"Critical GitHub issues detected in {len(critical_issues)} repositories",
            priority="critical",
            data={"critical_issues": critical_issues}
        )
    
    return {
        "success": True,
        "repositories_checked": len(repositories),
        "total_issues": total_issues,
        "critical_issues": sum(i["critical_count"] for i in critical_issues),
        "action_taken": "escalated" if critical_issues else None
    }


@check(
    name="monitor_build_status",
    description="Monitor CI/CD build and test status",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["development"]
)
async def monitor_build_status(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor build pipelines and report failures."""
    # Get build status
    build_status = await bot.check_build_status()
    
    if build_status.failed:
        # Get details
        failed_builds = [b for b in build_status.builds if b.status == "failed"]
        
        await bot.escalate_to_coordinator(
            f"Build failures detected: {len(failed_builds)} builds failed",
            priority="high",
            data={
                "failed_builds": [
                    {
                        "pipeline": b.pipeline,
                        "failed_tests": b.failed_tests,
                        "error_summary": b.error_summary
                    }
                    for b in failed_builds
                ]
            }
        )
        
        return {
            "success": False,
            "builds_checked": len(build_status.builds),
            "failed_builds": len(failed_builds),
            "action_taken": "escalated",
            "message": f"{len(failed_builds)} builds failed"
        }
    
    return {
        "success": True,
        "builds_checked": len(build_status.builds),
        "all_passing": True,
        "message": "All builds passing"
    }


@check(
    name="security_vulnerability_scan",
    description="Scan for security vulnerabilities in dependencies",
    priority="critical",
    max_duration_s=120.0,
    bot_domains=["development"]
)
async def security_vulnerability_scan(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Scan project dependencies for known security vulnerabilities."""
    # Run security scan
    scan_results = await bot.run_security_scan()
    
    high_severity = [v for v in scan_results.vulnerabilities if v.severity == "high"]
    critical_severity = [v for v in scan_results.vulnerabilities if v.severity == "critical"]
    
    if critical_severity:
        # Immediate escalation for critical vulnerabilities
        await bot.escalate_to_coordinator(
            f"CRITICAL: {len(critical_severity)} security vulnerabilities found",
            priority="critical",
            data={
                "critical_vulnerabilities": [
                    {
                        "package": v.package,
                        "cve": v.cve_id,
                        "severity": v.severity,
                        "fixed_version": v.fixed_version
                    }
                    for v in critical_severity
                ]
            }
        )
        
        return {
            "success": False,
            "vulnerabilities_found": len(scan_results.vulnerabilities),
            "critical": len(critical_severity),
            "high": len(high_severity),
            "action_taken": "escalated_critical"
        }
    
    if high_severity:
        # Notify but don't escalate
        await bot.notify_coordinator(
            f"{len(high_severity)} high-severity vulnerabilities found",
            priority="high",
            data={"vulnerabilities": high_severity}
        )
    
    return {
        "success": True,
        "vulnerabilities_found": len(scan_results.vulnerabilities),
        "critical": len(critical_severity),
        "high": len(high_severity),
        "action_taken": None if not high_severity else "notified"
    }


@check(
    name="check_dependency_updates",
    description="Check for available dependency updates",
    priority="normal",
    max_duration_s=60.0,
    bot_domains=["development"]
)
async def check_dependency_updates(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check for outdated dependencies and suggest updates."""
    updates = await bot.check_dependency_updates()
    
    # Filter to significant updates (not just patch versions)
    significant = [
        u for u in updates
        if u.update_type in ["major", "minor"] or u.security_fix
    ]
    
    if significant:
        await bot.notify_coordinator(
            f"{len(significant)} significant dependency updates available",
            data={"updates": significant}
        )
    
    return {
        "success": True,
        "dependencies_checked": len(updates),
        "updates_available": len(updates),
        "significant_updates": len(significant),
        "action_taken": "notified" if significant else None
    }
```

#### 2.3: Social Bot Checks
**File:** `nanobot/bots/checks/social_checks.py`

```python
"""Heartbeat checks for SocialBot (Lookout)."""

from datetime import datetime
from typing import Dict, Any, List

from nanobot.heartbeat.check_registry import check


@check(
    name="publish_scheduled_posts",
    description="Publish posts scheduled for current time",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["community"]
)
async def publish_scheduled_posts(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check for and publish scheduled social media posts."""
    # Get posts scheduled for now or past
    now = datetime.now()
    scheduled_posts = await bot.get_scheduled_posts(before=now)
    
    published = []
    failed = []
    
    for post in scheduled_posts:
        try:
            success = await bot.publish_post(post)
            
            if success:
                published.append({
                    "post_id": post.id,
                    "platform": post.platform,
                    "content_preview": post.content[:50] + "..."
                })
            else:
                failed.append({
                    "post_id": post.id,
                    "platform": post.platform,
                    "error": "Publishing failed"
                })
                
        except Exception as e:
            failed.append({
                "post_id": post.id,
                "platform": post.platform,
                "error": str(e)
            })
    
    if failed:
        await bot.escalate_to_coordinator(
            f"Failed to publish {len(failed)} scheduled posts",
            priority="high",
            data={"failed_posts": failed}
        )
    
    return {
        "success": len(failed) == 0,
        "posts_scheduled": len(scheduled_posts),
        "published": len(published),
        "failed": len(failed),
        "action_taken": "escalated" if failed else None
    }


@check(
    name="monitor_community_mentions",
    description="Monitor social platforms for mentions and engagement",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["community"],
    platforms=["twitter", "linkedin", "reddit"]  # Configurable
)
async def monitor_community_mentions(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor social platforms for mentions requiring response."""
    platforms = config.get("platforms", ["twitter", "linkedin"])
    
    total_mentions = 0
    urgent_mentions = []
    
    for platform in platforms:
        try:
            # Get mentions since last check
            since = bot.private_memory.get("last_mention_check", {}).get(platform)
            mentions = await bot.check_mentions(platform, since=since)
            
            total_mentions += len(mentions)
            
            # Identify urgent mentions
            urgent = [m for m in mentions if m.requires_response and m.sentiment in ["negative", "urgent"]]
            if urgent:
                urgent_mentions.extend(urgent)
            
            # Update memory
            if "last_mention_check" not in bot.private_memory:
                bot.private_memory["last_mention_check"] = {}
            bot.private_memory["last_mention_check"][platform] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error checking mentions on {platform}: {e}")
    
    if urgent_mentions:
        # Draft responses for urgent mentions
        for mention in urgent_mentions:
            mention.suggested_response = await bot.draft_response(mention)
        
        await bot.notify_coordinator(
            f"{len(urgent_mentions)} urgent community mentions require response",
            priority="high",
            data={"mentions": urgent_mentions}
        )
    
    return {
        "success": True,
        "platforms_checked": len(platforms),
        "total_mentions": total_mentions,
        "urgent_mentions": len(urgent_mentions),
        "action_taken": "notified" if urgent_mentions else None
    }


@check(
    name="check_engagement_metrics",
    description="Analyze engagement metrics and report anomalies",
    priority="normal",
    max_duration_s=60.0,
    bot_domains=["community"]
)
async def check_engagement_metrics(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze engagement metrics and detect significant changes."""
    metrics = await bot.analyze_engagement_metrics()
    
    # Detect anomalies (sudden drops or spikes)
    anomalies = []
    
    for metric_name, values in metrics.items():
        current = values[-1] if values else 0
        avg = sum(values[:-1]) / len(values[:-1]) if len(values) > 1 else current
        
        # 30% drop or 50% spike is significant
        if current < avg * 0.7:
            anomalies.append({
                "metric": metric_name,
                "change": "drop",
                "percent": ((avg - current) / avg) * 100,
                "current": current,
                "average": avg
            })
        elif current > avg * 1.5:
            anomalies.append({
                "metric": metric_name,
                "change": "spike",
                "percent": ((current - avg) / avg) * 100,
                "current": current,
                "average": avg
            })
    
    if anomalies:
        await bot.notify_coordinator(
            f"Engagement anomalies detected: {len(anomalies)} metrics",
            data={"anomalies": anomalies}
        )
    
    return {
        "success": True,
        "metrics_analyzed": len(metrics),
        "anomalies_detected": len(anomalies),
        "action_taken": "notified" if anomalies else None
    }


@check(
    name="track_trending_topics",
    description="Track trending topics relevant to the brand",
    priority="low",
    max_duration_s=120.0,
    bot_domains=["community"],
    topics=[]  # Configurable topics to track
)
async def track_trending_topics(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Track trending topics and suggest content opportunities."""
    tracked_topics = config.get("topics", [])
    
    if not tracked_topics:
        return {"success": True, "message": "No topics configured for tracking"}
    
    trending = []
    
    for topic in tracked_topics:
        try:
            trend_data = await bot.check_trending(topic)
            
            if trend_data.is_trending and trend_data.volume > 1000:
                trending.append({
                    "topic": topic,
                    "volume": trend_data.volume,
                    "sentiment": trend_data.sentiment,
                    "opportunity_score": trend_data.opportunity_score
                })
                
        except Exception as e:
            logger.error(f"Error checking trends for {topic}: {e}")
    
    # Sort by opportunity score
    trending.sort(key=lambda x: x["opportunity_score"], reverse=True)
    
    if trending:
        await bot.notify_coordinator(
            f"{len(trending)} tracked topics are trending",
            data={
                "trending_topics": trending[:5],  # Top 5
                "suggested_action": "Consider creating content around these topics"
            }
        )
    
    return {
        "success": True,
        "topics_checked": len(tracked_topics),
        "trending": len(trending),
        "action_taken": "notified" if trending else None
    }
```

#### 2.4: Create Bot Configurations
**File:** `nanobot/bots/heartbeat_configs.py`

```python
"""Heartbeat configurations for each bot type."""

from nanobot.heartbeat.models import HeartbeatConfig, CheckDefinition
from nanobot.heartbeat.check_registry import check_registry


def get_researcher_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for ResearcherBot."""
    return HeartbeatConfig(
        bot_name="researcher",
        interval_s=60 * 60,  # 60 minutes - default for all specialist bots
        max_execution_time_s=600,  # 10 minutes max
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="monitor_data_sources",
                description="Check monitored data sources for updates",
                priority="high",
                max_duration_s=120.0
            ),
            CheckDefinition(
                name="track_market_trends",
                description="Analyze market trends and detect significant changes",
                priority="normal",
                max_duration_s=180.0
            ),
            CheckDefinition(
                name="monitor_research_deadlines",
                description="Check for approaching research deadlines",
                priority="critical",
                max_duration_s=30.0
            ),
            CheckDefinition(
                name="update_competitor_tracking",
                description="Update competitor tracking data",
                priority="normal",
                max_duration_s=300.0
            )
        ],
        
        # Execution strategy
        parallel_checks=True,
        max_concurrent_checks=2,  # Don't overwhelm data sources
        stop_on_first_failure=False,
        
        # Retry configuration
        retry_attempts=2,
        retry_delay_s=10.0,
        retry_backoff=2.0,
        
        # Circuit breaker
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_s=600,
        
        # Notifications
        notify_on_failure=True,
        notify_on_success=False,
        notification_channels=["coordinator"],
        
        # Logging
        log_level="INFO",
        retain_history_count=50
    )


def get_coder_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for CoderBot."""
    return HeartbeatConfig(
        bot_name="coder",
        interval_s=60 * 60,  # 60 minutes - default (user customizable)
        max_execution_time_s=300,  # 5 minutes max
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="check_github_issues",
                description="Check GitHub repositories for new issues",
                priority="critical",
                max_duration_s=60.0
            ),
            CheckDefinition(
                name="monitor_build_status",
                description="Monitor CI/CD build and test status",
                priority="high",
                max_duration_s=90.0
            ),
            CheckDefinition(
                name="security_vulnerability_scan",
                description="Scan for security vulnerabilities",
                priority="critical",
                max_duration_s=120.0
            ),
            CheckDefinition(
                name="check_dependency_updates",
                description="Check for available dependency updates",
                priority="normal",
                max_duration_s=60.0
            )
        ],
        
        # Execution strategy
        parallel_checks=True,
        max_concurrent_checks=3,
        stop_on_first_failure=False,
        
        # Retry configuration - more aggressive for development
        retry_attempts=3,
        retry_delay_s=5.0,
        retry_backoff=2.0,
        
        # Circuit breaker
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=5,  # More tolerant
        circuit_breaker_timeout_s=300,
        
        # Notifications - critical for dev issues
        notify_on_failure=True,
        notify_on_success=False,
        notification_channels=["coordinator"],
        
        # Logging
        log_level="INFO",
        retain_history_count=100  # More history for debugging
    )


def get_social_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for SocialBot."""
    return HeartbeatConfig(
        bot_name="social",
        interval_s=60 * 60,  # 60 minutes - default (user can lower if needed)
        max_execution_time_s=180,  # 3 minutes max
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="publish_scheduled_posts",
                description="Publish posts scheduled for current time",
                priority="critical",
                max_duration_s=60.0
            ),
            CheckDefinition(
                name="monitor_community_mentions",
                description="Monitor social platforms for mentions",
                priority="high",
                max_duration_s=90.0
            ),
            CheckDefinition(
                name="check_engagement_metrics",
                description="Analyze engagement metrics",
                priority="normal",
                max_duration_s=60.0
            ),
            CheckDefinition(
                name="track_trending_topics",
                description="Track trending topics",
                priority="low",
                max_duration_s=120.0
            )
        ],
        
        # Execution strategy
        parallel_checks=True,
        max_concurrent_checks=4,  # Social checks are lighter
        stop_on_first_failure=False,  # Keep publishing even if metrics fail
        
        # Retry configuration
        retry_attempts=2,
        retry_delay_s=3.0,  # Quick retry for social
        retry_backoff=1.5,
        
        # Circuit breaker
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=3,
        circuit_breaker_timeout_s=180,
        
        # Notifications
        notify_on_failure=True,
        notify_on_success=False,
        notification_channels=["coordinator"],
        
        # Logging
        log_level="INFO",
        retain_history_count=200  # Lots of social activity
    )


def get_auditor_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for AuditorBot."""
    return HeartbeatConfig(
        bot_name="auditor",
        interval_s=60 * 60,  # 60 minutes - default for all specialist bots
        max_execution_time_s=480,  # 8 minutes max for deep analysis
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="code_quality_analysis",
                description="Analyze code quality metrics",
                priority="high",
                max_duration_s=180.0
            ),
            CheckDefinition(
                name="compliance_check",
                description="Check compliance requirements",
                priority="critical",
                max_duration_s=120.0
            ),
            CheckDefinition(
                name="review_queue_monitor",
                description="Monitor pending reviews",
                priority="normal",
                max_duration_s=60.0
            ),
            CheckDefinition(
                name="process_audit",
                description="Audit team processes",
                priority="low",
                max_duration_s=300.0
            )
        ],
        
        # Execution strategy - sequential for thoroughness
        parallel_checks=False,
        stop_on_first_failure=False,
        
        # Retry configuration
        retry_attempts=2,
        retry_delay_s=15.0,
        retry_backoff=2.0,
        
        # Circuit breaker
        circuit_breaker_enabled=True,
        circuit_breaker_threshold=2,  # Strict for quality
        circuit_breaker_timeout_s=600,
        
        # Notifications
        notify_on_failure=True,
        notify_on_success=True,  # Auditor reports all findings
        notification_channels=["coordinator"],
        
        # Logging
        log_level="INFO",
        retain_history_count=100
    )


def get_creative_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for CreativeBot."""
    return HeartbeatConfig(
        bot_name="creative",
        interval_s=60 * 60,  # 60 minutes - default for all specialist bots
        max_execution_time_s=300,
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="design_deadline_check",
                description="Check approaching design deadlines",
                priority="high",
                max_duration_s=30.0
            ),
            CheckDefinition(
                name="brand_consistency_audit",
                description="Audit brand consistency",
                priority="normal",
                max_duration_s=120.0
            ),
            CheckDefinition(
                name="inspiration_monitor",
                description="Monitor for inspiration opportunities",
                priority="low",
                max_duration_s=180.0
            )
        ],
        
        parallel_checks=True,
        max_concurrent_checks=2,
        circuit_breaker_enabled=True,
        notification_channels=["coordinator"]
    )


def get_coordinator_heartbeat_config() -> HeartbeatConfig:
    """Get heartbeat configuration for CoordinatorBot (nanobot)."""
    return HeartbeatConfig(
        bot_name="nanobot",
        interval_s=30 * 60,  # 30 minutes - coordination needs regular check-ins
        max_execution_time_s=300,
        enabled=True,
        
        checks=[
            CheckDefinition(
                name="cross_bot_coordination",
                description="Check for cross-bot coordination needs",
                priority="high",
                max_duration_s=60.0
            ),
            CheckDefinition(
                name="workspace_management",
                description="Manage workspace lifecycle",
                priority="normal",
                max_duration_s=90.0
            ),
            CheckDefinition(
                name="escalation_review",
                description="Review pending escalations",
                priority="critical",
                max_duration_s=30.0
            ),
            CheckDefinition(
                name="team_health_check",
                description="Check overall team health",
                priority="normal",
                max_duration_s=120.0
            )
        ],
        
        parallel_checks=True,
        max_concurrent_checks=4,
        circuit_breaker_enabled=True,
        notification_channels=["user"],  # Coordinator notifies user directly
        log_level="INFO"
    )


# Registry of all bot heartbeat configurations
BOT_HEARTBEAT_CONFIGS = {
    "researcher": get_researcher_heartbeat_config,
    "coder": get_coder_heartbeat_config,
    "social": get_social_heartbeat_config,
    "auditor": get_auditor_heartbeat_config,
    "creative": get_creative_heartbeat_config,
    "nanobot": get_coordinator_heartbeat_config,
}


def get_heartbeat_config(bot_name: str) -> HeartbeatConfig:
    """Get heartbeat configuration for a specific bot.
    
    Args:
        bot_name: Name of the bot
        
    Returns:
        HeartbeatConfig for the bot
        
    Raises:
        ValueError: If bot_name is not recognized
    """
    config_fn = BOT_HEARTBEAT_CONFIGS.get(bot_name)
    if not config_fn:
        raise ValueError(f"No heartbeat config for bot: {bot_name}")
    
    return config_fn()
```

**Acceptance Criteria:**
- ✅ Each bot has domain-specific checks registered
- ✅ Check implementations are async and return structured results
- ✅ Configurations define intervals appropriate to domain needs
- ✅ Error handling and logging throughout
- ✅ Coordinator notifications on important findings
- ✅ Check registry allows dynamic discovery

---

#### 2.5: User Configuration of Intervals
**File:** `nanobot/config/heartbeat_config.py`

Users can customize heartbeat intervals per bot via configuration:

```python
"""User-customizable heartbeat configuration."""

from typing import Dict, Optional
from dataclasses import dataclass

from nanobot.heartbeat.models import HeartbeatConfig
from nanobot.bots.heartbeat_configs import get_heartbeat_config, BOT_HEARTBEAT_CONFIGS


@dataclass
class UserHeartbeatSettings:
    """User-customizable settings for bot heartbeats."""
    # Bot name -> interval in seconds
    intervals: Dict[str, int]
    
    # Bot name -> enabled/disabled
    enabled: Dict[str, bool]
    
    # Minimum allowed interval (5 minutes to prevent abuse)
    MIN_INTERVAL_S: int = 5 * 60
    
    # Maximum allowed interval (24 hours)
    MAX_INTERVAL_S: int = 24 * 60 * 60
    
    # Default interval for specialist bots
    DEFAULT_SPECIALIST_INTERVAL_S: int = 60 * 60  # 60 minutes
    
    # Default interval for coordinator
    DEFAULT_COORDINATOR_INTERVAL_S: int = 30 * 60  # 30 minutes


class HeartbeatConfigLoader:
    """Loads and applies user heartbeat configuration."""
    
    def __init__(self, config_path: str = "config/heartbeat.json"):
        self.config_path = config_path
        self.user_settings = self._load_user_settings()
    
    def _load_user_settings(self) -> UserHeartbeatSettings:
        """Load user settings from config file."""
        import json
        from pathlib import Path
        
        path = Path(self.config_path)
        if not path.exists():
            # Return defaults
            return UserHeartbeatSettings(
                intervals={},
                enabled={}
            )
        
        with open(path) as f:
            data = json.load(f)
        
        return UserHeartbeatSettings(
            intervals=data.get("intervals", {}),
            enabled=data.get("enabled", {})
        )
    
    def get_bot_config(self, bot_name: str) -> HeartbeatConfig:
        """Get heartbeat config for a bot with user overrides applied.
        
        Args:
            bot_name: Name of the bot
            
        Returns:
            HeartbeatConfig with user customizations applied
        """
        # Get base config
        base_config = get_heartbeat_config(bot_name)
        
        # Apply user interval override
        if bot_name in self.user_settings.intervals:
            user_interval = self.user_settings.intervals[bot_name]
            
            # Validate interval
            user_interval = max(
                self.user_settings.MIN_INTERVAL_S,
                min(user_interval, self.user_settings.MAX_INTERVAL_S)
            )
            
            base_config.interval_s = user_interval
        
        # Apply user enabled/disabled override
        if bot_name in self.user_settings.enabled:
            base_config.enabled = self.user_settings.enabled[bot_name]
        
        return base_config
    
    def set_bot_interval(self, bot_name: str, interval_minutes: int) -> bool:
        """Set custom interval for a bot.
        
        Args:
            bot_name: Name of the bot
            interval_minutes: Interval in minutes (min: 5, max: 1440)
            
        Returns:
            True if successfully set
        """
        interval_s = interval_minutes * 60
        
        # Validate
        if interval_s < self.user_settings.MIN_INTERVAL_S:
            raise ValueError(f"Interval must be at least 5 minutes")
        
        if interval_s > self.user_settings.MAX_INTERVAL_S:
            raise ValueError(f"Interval must be at most 24 hours")
        
        # Apply
        self.user_settings.intervals[bot_name] = interval_s
        self._save_user_settings()
        
        return True
    
    def reset_to_defaults(self, bot_name: Optional[str] = None):
        """Reset intervals to defaults.
        
        Args:
            bot_name: Specific bot to reset, or None for all
        """
        if bot_name:
            if bot_name in self.user_settings.intervals:
                del self.user_settings.intervals[bot_name]
        else:
            self.user_settings.intervals.clear()
        
        self._save_user_settings()
    
    def _save_user_settings(self):
        """Save user settings to config file."""
        import json
        from pathlib import Path
        
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "intervals": self.user_settings.intervals,
            "enabled": self.user_settings.enabled
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


# Example user config file (config/heartbeat.json):
EXAMPLE_CONFIG = """
{
  "intervals": {
    "social": 900,
    "coder": 1800
  },
  "enabled": {
    "researcher": true,
    "social": true,
    "creative": false
  }
}
"""
```

**CLI Commands for User Configuration:**

```python
# nanobot/cli/commands.py

@app.command()
def heartbeat_config(
    bot: str = typer.Argument(..., help="Bot name"),
    interval: int = typer.Option(None, "--interval", "-i", help="Interval in minutes"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default"),
    disable: bool = typer.Option(False, "--disable", help="Disable heartbeat"),
    enable: bool = typer.Option(False, "--enable", help="Enable heartbeat"),
):
    """Configure heartbeat interval for a bot."""
    from nanobot.config.heartbeat_config import HeartbeatConfigLoader
    
    loader = HeartbeatConfigLoader()
    
    if reset:
        loader.reset_to_defaults(bot)
        console.print(f"[green]✓[/green] Reset {bot} heartbeat to default")
        return
    
    if disable:
        loader.user_settings.enabled[bot] = False
        loader._save_user_settings()
        console.print(f"[yellow]✓[/yellow] Disabled heartbeat for {bot}")
        return
    
    if enable:
        loader.user_settings.enabled[bot] = True
        loader._save_user_settings()
        console.print(f"[green]✓[/green] Enabled heartbeat for {bot}")
        return
    
    if interval:
        try:
            loader.set_bot_interval(bot, interval)
            console.print(f"[green]✓[/green] Set {bot} heartbeat to {interval} minutes")
        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
        return
    
    # Show current config
    config = loader.get_bot_config(bot)
    console.print(f"\n[bold]{bot} heartbeat configuration:[/bold]")
    console.print(f"  Interval: {config.interval_s // 60} minutes")
    console.print(f"  Enabled: {config.enabled}")
    console.print(f"  Checks: {len(config.checks)}")


@app.command()
def heartbeat_status():
    """Show status of all bot heartbeats."""
    from nanobot.config.heartbeat_config import HeartbeatConfigLoader
    
    loader = HeartbeatConfigLoader()
    
    console.print("\n[bold]Bot Heartbeat Status[/bold]\n")
    
    for bot_name in ["researcher", "coder", "social", "creative", "auditor", "nanobot"]:
        config = loader.get_bot_config(bot_name)
        interval_min = config.interval_s // 60
        
        status = "[green]●[/green] enabled" if config.enabled else "[red]●[/red] disabled"
        is_custom = bot_name in loader.user_settings.intervals
        interval_str = f"{interval_min}m"
        if is_custom:
            interval_str += " [yellow](custom)[/yellow]"
        
        console.print(f"  {bot_name:12} {status:15} interval: {interval_str:10} checks: {len(config.checks)}")
```

**Acceptance Criteria:**
- ✅ Users can view current heartbeat configuration
- ✅ Users can set custom intervals per bot (5min - 24hr range)
- ✅ Users can enable/disable heartbeats per bot
- ✅ Changes persist across restarts
- ✅ CLI commands for easy configuration
- ✅ Validation prevents invalid intervals
- ✅ Visual indicators for custom vs default settings

---

### Phase 3: Integration with Bot Classes (Day 2)
**Goal:** Integrate heartbeat into SpecialistBot base class

#### 3.1: Update SpecialistBot Base Class
**File:** `nanobot/bots/base.py`

```python
"""Base class for all specialist bots with heartbeat support."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import asyncio

from loguru import logger

from nanobot.models.role_card import RoleCard
from nanobot.heartbeat.bot_heartbeat import BotHeartbeatService
from nanobot.heartbeat.models import HeartbeatConfig, CheckResult, HeartbeatTick
from nanobot.coordinator.bus import InterBotBus


class SpecialistBot(ABC):
    """Base class for all specialist bots with autonomous heartbeat.
    
    Each bot runs its own independent heartbeat with:
    - Role-specific periodic checks
    - Domain-optimized intervals
    - Autonomous task execution
    - Self-managed state
    """
    
    def __init__(
        self,
        role_card: RoleCard,
        bus: Optional[InterBotBus] = None,
        workspace_id: Optional[str] = None
    ):
        self.role_card = role_card
        self.bus = bus
        self.workspace_id = workspace_id
        
        # Private memory for bot learnings
        self.private_memory: Dict[str, Any] = {
            "learnings": [],
            "expertise_domains": [],
            "mistakes": [],
            "confidence": 0.7,
            "heartbeat_history": [],
        }
        
        # Heartbeat service
        self._heartbeat: Optional[BotHeartbeatService] = None
        self._heartbeat_config: Optional[HeartbeatConfig] = None
    
    def initialize_heartbeat(
        self,
        config: Optional[HeartbeatConfig] = None,
        on_tick_complete: Optional[Callable[[HeartbeatTick], None]] = None,
        on_check_complete: Optional[Callable[[CheckResult], None]] = None
    ) -> None:
        """Initialize bot's autonomous heartbeat.
        
        Args:
            config: Heartbeat configuration (uses default if None)
            on_tick_complete: Callback when tick completes
            on_check_complete: Callback when individual check completes
        """
        if config is None:
            # Load default config for this bot type
            from nanobot.bots.heartbeat_configs import get_heartbeat_config
            config = get_heartbeat_config(self.role_card.bot_name)
        
        self._heartbeat_config = config
        
        # Wrap callbacks to include bot context
        def tick_callback(tick: HeartbeatTick):
            self._on_heartbeat_tick_complete(tick)
            if on_tick_complete:
                on_tick_complete(tick)
        
        def check_callback(result: CheckResult):
            self._on_check_complete(result)
            if on_check_complete:
                on_check_complete(result)
        
        self._heartbeat = BotHeartbeatService(
            bot_instance=self,
            config=config,
            on_tick_complete=tick_callback,
            on_check_complete=check_callback
        )
        
        logger.info(
            f"[{self.role_card.bot_name}] Heartbeat initialized: "
            f"{config.interval_s}s interval, {len(config.checks)} checks"
        )
    
    async def start_heartbeat(self) -> None:
        """Start bot's independent heartbeat."""
        if self._heartbeat is None:
            # Auto-initialize with defaults
            self.initialize_heartbeat()
        
        if self._heartbeat:
            await self._heartbeat.start()
    
    def stop_heartbeat(self) -> None:
        """Stop bot's heartbeat."""
        if self._heartbeat:
            self._heartbeat.stop()
    
    @property
    def is_heartbeat_running(self) -> bool:
        """Check if heartbeat is currently running."""
        return self._heartbeat is not None and self._heartbeat.is_running
    
    def get_heartbeat_status(self) -> Dict[str, Any]:
        """Get current heartbeat status."""
        if self._heartbeat:
            return self._heartbeat.get_status()
        return {"running": False, "bot_name": self.role_card.bot_name}
    
    async def trigger_heartbeat_now(self, reason: str = "manual") -> Any:
        """Manually trigger a heartbeat tick.
        
        Args:
            reason: Why heartbeat is being triggered
            
        Returns:
            HeartbeatTick result
        """
        if self._heartbeat is None:
            self.initialize_heartbeat()
        
        return await self._heartbeat.trigger_now(reason)
    
    def _on_heartbeat_tick_complete(self, tick: HeartbeatTick) -> None:
        """Internal handler for tick completion.
        
        Records to bot's private memory and logs learning.
        """
        # Record to private memory
        tick_summary = {
            "tick_id": tick.tick_id,
            "timestamp": tick.started_at.isoformat(),
            "status": tick.status,
            "success_rate": tick.get_success_rate(),
            "failed_checks": [r.check_name for r in tick.get_failed_checks()],
        }
        
        self.private_memory["heartbeat_history"].append(tick_summary)
        
        # Trim history if too long
        max_history = tick.config.retain_history_count if tick.config else 100
        if len(self.private_memory["heartbeat_history"]) > max_history:
            self.private_memory["heartbeat_history"] = self.private_memory["heartbeat_history"][-max_history:]
        
        # Record learning
        success_rate = tick.get_success_rate()
        if success_rate >= 0.9:
            self.record_learning(
                lesson=f"Heartbeat tick {tick.tick_id} completed with {success_rate:.0%} success",
                confidence=0.9
            )
        elif success_rate < 0.5:
            self.record_mistake(
                error=f"Heartbeat tick {tick.tick_id} had low success rate: {success_rate:.0%}",
                recovery="Review failed checks and adjust configuration"
            )
    
    def _on_check_complete(self, result: CheckResult) -> None:
        """Internal handler for check completion."""
        # Log to work log if available
        if hasattr(self, 'work_log_manager') and self.work_log_manager:
            from nanobot.agent.work_log_manager import LogLevel
            
            if result.success:
                self.work_log_manager.log(
                    level=LogLevel.INFO,
                    category="heartbeat",
                    message=f"Check '{result.check_name}' completed successfully",
                    metadata={"duration_ms": result.duration_ms}
                )
            else:
                self.work_log_manager.log(
                    level=LogLevel.WARNING,
                    category="heartbeat",
                    message=f"Check '{result.check_name}' failed: {result.error}",
                    metadata={"error": result.error, "error_type": result.error_type}
                )
    
    # ==================================================================
    # Communication with Coordinator
    # ==================================================================
    
    async def notify_coordinator(
        self,
        message: str,
        priority: str = "normal",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Notify coordinator of heartbeat finding.
        
        Args:
            message: Notification message
            priority: Priority level (low/normal/high/critical)
            data: Additional data to include
            
        Returns:
            True if notification sent successfully
        """
        if self.bus is None:
            logger.warning(f"[{self.role_card.bot_name}] No bus available for notification")
            return False
        
        try:
            from nanobot.coordinator.models import BotMessage, MessageType
            
            msg = BotMessage(
                sender_id=self.role_card.bot_name,
                recipient_id="coordinator",
                message_type=MessageType.NOTIFICATION,
                content=message,
                context={
                    "priority": priority,
                    "data": data or {},
                    "source": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            self.bus.send_message(msg)
            return True
            
        except Exception as e:
            logger.error(f"[{self.role_card.bot_name}] Failed to notify coordinator: {e}")
            return False
    
    async def escalate_to_coordinator(
        self,
        message: str,
        priority: str = "high",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Escalate issue to coordinator for human attention.
        
        Args:
            message: Escalation message
            priority: Priority level
            data: Supporting data
            
        Returns:
            True if escalation sent successfully
        """
        return await self.notify_coordinator(
            message=f"[ESCALATION] {message}",
            priority=priority,
            data=data
        )
    
    # ==================================================================
    # Abstract Methods - Bot Implementations
    # ==================================================================
    
    @abstractmethod
    async def process_message(self, message: str, workspace: Any) -> str:
        """Process a message sent to this bot.
        
        Args:
            message: Message content
            workspace: Workspace context
            
        Returns:
            Bot's response
        """
        pass
    
    @abstractmethod
    async def execute_task(self, task: str, workspace: Any) -> Dict[str, Any]:
        """Execute a specific task assigned to this bot.
        
        Args:
            task: Task description
            workspace: Workspace context
            
        Returns:
            Task execution result
        """
        pass
    
    # ==================================================================
    # Utility Methods
    # ==================================================================
    
    def can_perform_action(self, action: str) -> tuple[bool, Optional[str]]:
        """Validate action against hard bans."""
        return self.role_card.validate_action(action)
    
    def get_greeting(self) -> str:
        """Get bot's greeting."""
        return self.role_card.greeting
    
    def record_learning(self, lesson: str, confidence: float) -> None:
        """Record a private learning."""
        self.private_memory["learnings"].append({
            "lesson": lesson,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_mistake(self, error: str, recovery: str) -> None:
        """Record mistake and recovery."""
        self.private_memory["mistakes"].append({
            "error": error,
            "recovery": recovery,
            "timestamp": datetime.now().isoformat()
        })
```

#### 3.2: Update Concrete Bot Classes
**Example: ResearcherBot with Heartbeat**

```python
"""ResearcherBot with autonomous heartbeat."""

from typing import Dict, Any, List
from datetime import datetime

from nanobot.bots.base import SpecialistBot
from nanobot.models.role_card import RoleCard, BotDomain


# Researcher role card definition
RESEARCHER_ROLE = RoleCard(
    bot_name="researcher",
    domain=BotDomain.RESEARCH,
    title="Navigator",
    description="Deep research and analysis",
    # ... rest of role card
)


class ResearcherBot(SpecialistBot):
    """Navigator - autonomous research specialist."""
    
    def __init__(self, bus=None, workspace_id=None):
        super().__init__(RESEARCHER_ROLE, bus, workspace_id)
        
        # Initialize with researcher-specific heartbeat
        from nanobot.bots.heartbeat_configs import get_researcher_heartbeat_config
        self.initialize_heartbeat(
            config=get_researcher_heartbeat_config()
        )
    
    async def process_message(self, message: str, workspace: Any) -> str:
        """Process research-related messages."""
        # Implementation
        pass
    
    async def execute_task(self, task: str, workspace: Any) -> Dict[str, Any]:
        """Execute research tasks."""
        # Implementation
        pass
    
    # ==================================================================
    # Heartbeat Check Methods - Called by check registry
    # ==================================================================
    
    async def check_source_updates(self, source: str, since: float = None) -> List[Dict]:
        """Check a data source for updates."""
        # Implementation for data source monitoring
        pass
    
    async def analyze_market_trend(self, market: str) -> Any:
        """Analyze trends for a specific market."""
        # Implementation for market analysis
        pass
    
    async def get_active_research_projects(self) -> List[Any]:
        """Get list of active research projects."""
        # Implementation
        pass
    
    async def check_competitor_updates(self, competitor: str) -> List[Dict]:
        """Check for competitor updates."""
        # Implementation
        pass
```

**Acceptance Criteria:**
- ✅ SpecialistBot base class supports heartbeat initialization
- ✅ Automatic memory management for heartbeat history
- ✅ Coordinator notification methods
- ✅ Concrete bots auto-initialize with domain-specific configs
- ✅ Heartbeat starts/stops with bot lifecycle

---

### Phase 4: Multi-Heartbeat Manager (Day 3)
**Goal:** Coordinate all bot heartbeats and handle cross-bot scenarios

#### 4.1: MultiHeartbeatManager
**File:** `nanobot/heartbeat/multi_manager.py`

```python
"""Manager for coordinating multiple bot heartbeats."""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from nanobot.bots.base import SpecialistBot
from nanobot.heartbeat.models import HeartbeatTick
from nanobot.coordinator.bus import InterBotBus
from nanobot.coordinator.audit import AuditTrail, AuditEventType


@dataclass
class CrossBotCheck:
    """A check that requires coordination across multiple bots."""
    name: str
    description: str
    participating_bots: List[str]
    coordinator_check: str  # Check that runs on coordinator
    dependencies: List[str]  # Checks that must complete first


class MultiHeartbeatManager:
    """Manages heartbeats across all bots in the team.
    
    Responsibilities:
    - Start/stop all bot heartbeats
    - Coordinate cross-bot checks
    - Monitor overall team health
    - Aggregate heartbeat metrics
    - Handle bot failures and recovery
    """
    
    def __init__(
        self,
        bus: InterBotBus,
        audit_trail: Optional[AuditTrail] = None
    ):
        self.bus = bus
        self.audit = audit_trail or AuditTrail()
        
        # Bot registry
        self._bots: Dict[str, SpecialistBot] = {}
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        
        # Cross-bot coordination
        self._cross_bot_checks: Dict[str, CrossBotCheck] = {}
        
        # State
        self._running = False
        self._coordinator_check_task: Optional[asyncio.Task] = None
    
    def register_bot(self, bot: SpecialistBot) -> None:
        """Register a bot for heartbeat management.
        
        Args:
            bot: Bot instance to register
        """
        bot_name = bot.role_card.bot_name
        self._bots[bot_name] = bot
        
        logger.info(f"[MultiHeartbeatManager] Registered bot: {bot_name}")
    
    def unregister_bot(self, bot_name: str) -> bool:
        """Unregister a bot and stop its heartbeat.
        
        Args:
            bot_name: Name of bot to unregister
            
        Returns:
            True if unregistered successfully
        """
        if bot_name not in self._bots:
            return False
        
        # Stop heartbeat if running
        bot = self._bots[bot_name]
        bot.stop_heartbeat()
        
        # Cancel task if exists
        if bot_name in self._heartbeat_tasks:
            self._heartbeat_tasks[bot_name].cancel()
            del self._heartbeat_tasks[bot_name]
        
        del self._bots[bot_name]
        logger.info(f"[MultiHeartbeatManager] Unregistered bot: {bot_name}")
        return True
    
    async def start_all(self) -> None:
        """Start heartbeats for all registered bots."""
        self._running = True
        
        logger.info(f"[MultiHeartbeatManager] Starting heartbeats for {len(self._bots)} bots")
        
        # Start each bot's heartbeat
        for bot_name, bot in self._bots.items():
            try:
                await bot.start_heartbeat()
                
                # Audit log
                self.audit.log_event(
                    event_type=AuditEventType.BOT_SELECTION,
                    description=f"Started heartbeat for {bot_name}",
                    bot_ids=[bot_name],
                    details={
                        "interval_s": bot._heartbeat_config.interval_s if bot._heartbeat_config else None,
                        "checks_count": len(bot._heartbeat_config.checks) if bot._heartbeat_config else 0
                    }
                )
                
            except Exception as e:
                logger.error(f"[MultiHeartbeatManager] Failed to start {bot_name} heartbeat: {e}")
        
        # Start coordinator checks
        if "nanobot" in self._bots:
            self._coordinator_check_task = asyncio.create_task(
                self._run_coordinator_checks()
            )
        
        logger.info("[MultiHeartbeatManager] All heartbeats started")
    
    def stop_all(self) -> None:
        """Stop all bot heartbeats."""
        self._running = False
        
        logger.info(f"[MultiHeartbeatManager] Stopping heartbeats for {len(self._bots)} bots")
        
        # Stop each bot
        for bot_name, bot in self._bots.items():
            try:
                bot.stop_heartbeat()
            except Exception as e:
                logger.error(f"[MultiHeartbeatManager] Error stopping {bot_name}: {e}")
        
        # Cancel coordinator task
        if self._coordinator_check_task:
            self._coordinator_check_task.cancel()
            self._coordinator_check_task = None
        
        logger.info("[MultiHeartbeatManager] All heartbeats stopped")
    
    async def _run_coordinator_checks(self) -> None:
        """Run coordinator-specific cross-bot checks."""
        coordinator = self._bots.get("nanobot")
        if not coordinator or not coordinator._heartbeat:
            return
        
        while self._running:
            try:
                # Wait for coordinator's interval
                interval = coordinator._heartbeat_config.interval_s
                await asyncio.sleep(interval)
                
                if not self._running:
                    break
                
                # Run cross-bot coordination check
                await self._execute_cross_bot_coordination()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MultiHeartbeatManager] Coordinator check error: {e}")
    
    async def _execute_cross_bot_coordination(self) -> None:
        """Execute cross-bot coordination check."""
        # Check for tasks requiring multiple bots
        cross_bot_tasks = self._identify_cross_bot_tasks()
        
        for task in cross_bot_tasks:
            # Coordinate execution across bots
            await self._coordinate_cross_bot_task(task)
    
    def _identify_cross_bot_tasks(self) -> List[Dict[str, Any]]:
        """Identify tasks requiring multiple bots."""
        # Implementation: Analyze active tasks across bots
        # to find dependencies requiring coordination
        return []
    
    async def _coordinate_cross_bot_task(self, task: Dict[str, Any]) -> None:
        """Coordinate execution of a cross-bot task."""
        # Implementation: Manage handoffs between bots
        pass
    
    def get_team_health(self) -> Dict[str, Any]:
        """Get overall health status of all bot heartbeats.
        
        Returns:
            Health summary with per-bot and aggregate metrics
        """
        bot_statuses = {}
        
        for bot_name, bot in self._bots.items():
            if bot._heartbeat:
                status = bot.get_heartbeat_status()
                bot_statuses[bot_name] = status
        
        # Calculate aggregate metrics
        total_ticks = sum(
            s.get("history", {}).get("total_ticks", 0)
            for s in bot_statuses.values()
        )
        
        failed_ticks = sum(
            s.get("history", {}).get("failed_ticks", 0)
            for s in bot_statuses.values()
        )
        
        overall_success_rate = (
            (total_ticks - failed_ticks) / total_ticks * 100
            if total_ticks > 0 else 0
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_bots": len(self._bots),
            "running_bots": sum(1 for s in bot_statuses.values() if s.get("running")),
            "overall_success_rate": overall_success_rate,
            "total_ticks_all_bots": total_ticks,
            "failed_ticks_all_bots": failed_ticks,
            "bots": bot_statuses
        }
    
    async def trigger_team_heartbeat(self, reason: str = "manual") -> Dict[str, Any]:
        """Manually trigger heartbeat on all bots.
        
        Args:
            reason: Why heartbeat is being triggered
            
        Returns:
            Results from all bots
        """
        results = {}
        
        for bot_name, bot in self._bots.items():
            try:
                tick = await bot.trigger_heartbeat_now(reason)
                results[bot_name] = tick
            except Exception as e:
                results[bot_name] = {"error": str(e)}
        
        return results
```

**Acceptance Criteria:**
- ✅ Manages multiple bot heartbeats simultaneously
- ✅ Coordinates cross-bot tasks
- ✅ Aggregates team health metrics
- ✅ Handles bot registration/unregistration
- ✅ Audit logging for all operations

---

### Phase 5: Integration & Testing (Day 3-4)
**Goal:** Wire everything together and test

#### 5.1: Integration in commands.py
**File:** `nanobot/cli/commands.py` (modification)

```python
# In the run command, replace single heartbeat with multi-heartbeat

from nanobot.heartbeat.multi_manager import MultiHeartbeatManager

# Create multi-heartbeat manager
multi_heartbeat = MultiHeartbeatManager(
    bus=bus,
    audit_trail=coordinator.audit_trail if 'coordinator' in locals() else None
)

# Register all bots
for bot in [researcher, coder, social, creative, auditor, nanobot]:
    multi_heartbeat.register_bot(bot)

# Start all heartbeats
await multi_heartbeat.start_all()

# In shutdown:
multi_heartbeat.stop_all()
```

#### 5.2: Test Suite
**File:** `tests/heartbeat/test_multi_heartbeat.py`

```python
"""Tests for multi-heartbeat system."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from nanobot.heartbeat.models import HeartbeatConfig, CheckDefinition
from nanobot.heartbeat.bot_heartbeat import BotHeartbeatService
from nanobot.heartbeat.multi_manager import MultiHeartbeatManager
from nanobot.bots.base import SpecialistBot


class TestBotHeartbeatService:
    """Tests for individual bot heartbeat."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create mock bot."""
        bot = Mock(spec=SpecialistBot)
        bot.role_card.bot_name = "test_bot"
        return bot
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return HeartbeatConfig(
            bot_name="test_bot",
            interval_s=1,  # 1 second for fast tests
            checks=[
                CheckDefinition(name="check1", description="Test check 1"),
                CheckDefinition(name="check2", description="Test check 2"),
            ]
        )
    
    @pytest.mark.asyncio
    async def test_heartbeat_starts_and_stops(self, mock_bot, config):
        """Test heartbeat starts and stops correctly."""
        service = BotHeartbeatService(mock_bot, config)
        
        assert not service.is_running
        
        await service.start()
        assert service.is_running
        
        service.stop()
        assert not service.is_running
    
    @pytest.mark.asyncio
    async def test_heartbeat_executes_checks(self, mock_bot, config):
        """Test that heartbeat executes registered checks."""
        # Register a mock check
        from nanobot.heartbeat.check_registry import check_registry
        
        async def mock_check(bot, cfg):
            return {"success": True, "message": "Mock check passed"}
        
        check_registry.register("check1", mock_check)
        
        service = BotHeartbeatService(mock_bot, config)
        
        # Trigger tick
        tick = await service.trigger_now("test")
        
        assert tick.status in ["completed", "completed_with_failures"]
        assert len(tick.results) == 2
    
    @pytest.mark.asyncio
    async def test_heartbeat_respects_interval(self, mock_bot):
        """Test that heartbeat respects configured interval."""
        config = HeartbeatConfig(
            bot_name="test_bot",
            interval_s=0.1,  # 100ms for test
            checks=[]
        )
        
        service = BotHeartbeatService(mock_bot, config)
        await service.start()
        
        # Wait for at least one tick
        await asyncio.sleep(0.15)
        
        service.stop()
        
        # Should have at least one tick in history
        assert service.history.total_ticks >= 1


class TestMultiHeartbeatManager:
    """Tests for multi-heartbeat manager."""
    
    @pytest.fixture
    def mock_bus(self):
        """Create mock message bus."""
        return Mock()
    
    @pytest.fixture
    def manager(self, mock_bus):
        """Create manager with mock bus."""
        return MultiHeartbeatManager(bus=mock_bus)
    
    @pytest.fixture
    def mock_bots(self):
        """Create mock bots."""
        bots = []
        for name in ["researcher", "coder", "social"]:
            bot = Mock(spec=SpecialistBot)
            bot.role_card.bot_name = name
            bot._heartbeat = None
            bot._heartbeat_config = None
            bots.append(bot)
        return bots
    
    def test_register_bot(self, manager, mock_bots):
        """Test bot registration."""
        bot = mock_bots[0]
        manager.register_bot(bot)
        
        assert "researcher" in manager._bots
        assert manager._bots["researcher"] == bot
    
    def test_unregister_bot(self, manager, mock_bots):
        """Test bot unregistration."""
        bot = mock_bots[0]
        manager.register_bot(bot)
        
        result = manager.unregister_bot("researcher")
        
        assert result is True
        assert "researcher" not in manager._bots
    
    @pytest.mark.asyncio
    async def test_start_all_starts_all_bots(self, manager, mock_bots):
        """Test that start_all starts all registered bots."""
        for bot in mock_bots:
            manager.register_bot(bot)
        
        await manager.start_all()
        
        # Each bot should have start_heartbeat called
        for bot in mock_bots:
            bot.start_heartbeat.assert_called_once()
        
        manager.stop_all()
    
    def test_get_team_health(self, manager, mock_bots):
        """Test team health aggregation."""
        for bot in mock_bots:
            manager.register_bot(bot)
        
        health = manager.get_team_health()
        
        assert health["total_bots"] == 3
        assert "bots" in health
        assert "overall_success_rate" in health


class TestCheckRegistry:
    """Tests for check registry."""
    
    @pytest.fixture
    def registry(self):
        """Create fresh registry."""
        from nanobot.heartbeat.check_registry import CheckRegistry
        return CheckRegistry()
    
    def test_register_check(self, registry):
        """Test check registration."""
        def test_handler(bot, config):
            return {"success": True}
        
        definition = registry.register(
            name="test_check",
            handler=test_handler,
            description="Test check"
        )
        
        assert definition.name == "test_check"
        assert "test_check" in registry._checks
    
    def test_list_checks_filters_by_domain(self, registry):
        """Test listing checks with domain filter."""
        # Register checks for different domains
        def handler(bot, config):
            return {"success": True}
        
        registry.register("check1", handler, bot_domains=["research"])
        registry.register("check2", handler, bot_domains=["development"])
        registry.register("check3", handler, bot_domains=["all"])
        
        research_checks = registry.list_checks(bot_domain="research")
        
        assert len(research_checks) == 2  # check1 and check3
    
    @pytest.mark.asyncio
    async def test_execute_check(self, registry):
        """Test check execution."""
        async def test_handler(bot, config):
            return {"success": True, "data": {"key": "value"}}
        
        registry.register("test_check", test_handler)
        
        mock_bot = Mock()
        result = await registry.execute_check("test_check", mock_bot)
        
        assert result.success is True
        assert result.check_name == "test_check"
```

**Acceptance Criteria:**
- ✅ Unit tests for all core components
- ✅ Integration tests for multi-bot scenarios
- ✅ Mock-based tests for fast execution
- ✅ Async test support
- ✅ >90% code coverage for heartbeat module

---

## Migration Path

### From Current System

**Current (Centralized):**
```python
# Single heartbeat
heartbeat = HeartbeatService(
    workspace=config.workspace_path,
    on_heartbeat=on_heartbeat,
    interval_s=30 * 60,
)
```

**New (Multi-Heartbeat):**
```python
# Multi-heartbeat
from nanobot.heartbeat.multi_manager import MultiHeartbeatManager

manager = MultiHeartbeatManager(bus=bus)

# Register bots with their own heartbeats
for bot in [researcher, coder, social, auditor, creative, nanobot]:
    manager.register_bot(bot)

# Start all
await manager.start_all()
```

**Migration Steps:**
1. Deploy new heartbeat system alongside existing
2. Gradually migrate bots to new system
3. Monitor for issues
4. Remove old HeartbeatService once all bots migrated

---

## Success Criteria

### Functional Requirements ✅
- [ ] Each bot has independent heartbeat
- [ ] Role-specific intervals (15-60 min)
- [ ] Domain-specific checks per bot
- [ ] Parallel check execution
- [ ] Circuit breaker protection
- [ ] Comprehensive audit trail
- [ ] Cross-bot coordination support
- [ ] Graceful error handling

### Performance Requirements ✅
- [ ] Heartbeat tick completes within 5 minutes
- [ ] No interference between bot heartbeats
- [ ] <10MB memory overhead per bot
- [ ] Check execution parallelized efficiently

### Quality Requirements ✅
- [ ] >90% test coverage
- [ ] All async code properly awaited
- [ ] Comprehensive error logging
- [ ] Documentation for all public APIs

---

## Timeline Summary

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| 1: Infrastructure | 1 day | Data models, registry, BotHeartbeatService |
| 2: Bot Configs | 1-2 days | Domain-specific checks + user config system |
| 3: Integration | 1 day | SpecialistBot updates, bot classes |
| 4: Coordination | 1 day | MultiHeartbeatManager, cross-bot features |
| 5: Testing | 1 day | Test suite, integration tests |
| **Total** | **4-5 days** | Complete multi-heartbeat system |

---

## Benefits

1. **Autonomy:** Each bot manages its own periodic tasks independently
2. **Simplicity:** Standardized 60-minute default (30min for coordinator) - easy to understand
3. **Flexibility:** Users can customize intervals per bot (5min - 24hr range)
4. **Efficiency:** Parallel execution across bot team
5. **Resilience:** Per-bot circuit breakers, isolated failures
6. **Scalability:** Add new bots without changing infrastructure
7. **Transparency:** Full audit trail for all periodic actions
8. **Role Alignment:** Domain-specific checks match bot responsibilities

---

**Created:** February 13, 2026  
**Status:** Ready for Implementation  
**Estimated Effort:** 4-5 days  
**Priority:** High
