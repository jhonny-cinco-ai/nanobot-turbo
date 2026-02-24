"""Data models for crew routines engine (legacy heartbeat).

This module defines the core data structures for per-bot crew routines,
including configurations, check results, and execution tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional


class CheckPriority(Enum):
    """Priority levels for crew routines checks."""
    CRITICAL = "critical"    # Run immediately, alert on failure
    HIGH = "high"           # Run promptly, log failures
    NORMAL = "normal"       # Run during normal crew routines
    LOW = "low"             # Run when resources available


class CheckStatus(Enum):
    """Status of a crew routines check execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class CheckDefinition:
    """Definition of a single crew routines check.

    Attributes:
        name: Unique identifier for the check
        description: Human-readable description
        priority: Priority level (critical/high/normal/low)
        max_duration_s: Maximum allowed execution time
        retry_attempts: Number of retry attempts on failure
        dependencies: List of check names that must complete first
        enabled: Whether this check is enabled
        config: Dynamic configuration parameters
    """
    name: str
    description: str = ""
    priority: CheckPriority = CheckPriority.NORMAL
    max_duration_s: float = 60.0
    retry_attempts: int = 1
    dependencies: List[str] = field(default_factory=list)
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Result of executing a crew routines check.

    Attributes:
        check_name: Name of the check that was executed
        status: Execution status (pending/running/success/failed/etc.)
        started_at: When the check started
        completed_at: When the check completed (if finished)
        duration_ms: Execution duration in milliseconds
        success: Whether the check succeeded
        message: Human-readable result message
        data: Structured data returned by the check
        error: Error message if failed
        error_type: Type of error if failed
        stack_trace: Stack trace if failed
        action_taken: Description of any action taken
        notifications_sent: List of notifications sent
    """
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
class CrewRoutinesConfig:
    """Configuration for a bot's crew routines.

    Attributes:
        bot_name: Name of the bot this config belongs to
        interval_s: Seconds between crew routines ticks (default: 3600 = 60 min)
        max_execution_time_s: Maximum time for entire tick
        enabled: Whether crew routines are enabled
        checks: List of checks to execute
        parallel_checks: Whether to run checks in parallel
        max_concurrent_checks: Maximum parallel checks
        stop_on_first_failure: Whether to stop if a check fails
        retry_attempts: Number of retry attempts per check
        retry_delay_s: Delay between retries
        retry_backoff: Multiplier for retry delay
        circuit_breaker_enabled: Whether circuit breaker is active
        circuit_breaker_threshold: Failures before opening circuit
        circuit_breaker_timeout_s: Seconds before retrying after open
        notify_on_failure: Whether to notify on check failure
        notify_on_success: Whether to notify on check success
        notification_channels: Where to send notifications
        log_level: Logging level
        retain_history_count: Number of historical ticks to keep
    """
    bot_name: str
    interval_s: int = 3600              # 60 minutes default (1 hour)
    max_execution_time_s: int = 300     # 5 minutes max per tick
    enabled: bool = True

    # Check definitions
    checks: List[CheckDefinition] = field(default_factory=list)

    # Execution strategy
    parallel_checks: bool = True
    max_concurrent_checks: int = 3
    stop_on_first_failure: bool = False

    # Retry configuration
    retry_attempts: int = 2
    retry_delay_s: float = 5.0
    retry_backoff: float = 2.0

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout_s: int = 300

    # Notification settings
    notify_on_failure: bool = True
    notify_on_success: bool = False
    notification_channels: List[str] = field(default_factory=lambda: ["coordinator"])

    # Logging
    log_level: str = "INFO"
    retain_history_count: int = 100

    def get_interval_minutes(self) -> int:
        """Get interval in minutes for display."""
        return self.interval_s // 60

    def set_interval_minutes(self, minutes: int) -> None:
        """Set interval from minutes."""
        self.interval_s = minutes * 60


@dataclass
class CrewRoutinesTick:
    """A single crew routines execution.

    Attributes:
        tick_id: Unique identifier for this tick
        bot_name: Name of the bot that executed this tick
        started_at: When the tick started
        config: Configuration used for this tick
        results: Results of all checks executed
        status: Overall tick status
        trigger_type: What triggered this tick (scheduled/manual/event)
        triggered_by: Identifier of what triggered this tick
    """
    tick_id: str
    bot_name: str
    started_at: datetime
    config: CrewRoutinesConfig

    # Execution tracking
    results: List[CheckResult] = field(default_factory=list)
    status: str = "running"  # running, completed, failed, timeout, completed_with_failures

    # Metadata
    trigger_type: str = "scheduled"
    triggered_by: Optional[str] = None

    def get_success_rate(self) -> float:
        """Calculate success rate of checks.

        Returns:
            Float between 0.0 and 1.0 representing success rate
        """
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

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of this tick."""
        return {
            "tick_id": self.tick_id,
            "bot_name": self.bot_name,
            "status": self.status,
            "success_rate": self.get_success_rate(),
            "checks_total": len(self.results),
            "checks_failed": len(self.get_failed_checks()),
            "duration_ms": self.duration_ms(),
            "trigger_type": self.trigger_type,
        }


@dataclass
class CrewRoutinesHistory:
    """History of crew routines executions for a bot.

    Attributes:
        bot_name: Name of the bot
        ticks: List of historical ticks
        total_ticks: Total number of ticks executed
        successful_ticks: Number of successful ticks
        failed_ticks: Number of failed ticks
        last_tick_at: When the last tick ran
        last_success_at: When the last successful tick ran
        last_failure_at: When the last failed tick ran
    """
    bot_name: str
    ticks: List[CrewRoutinesTick] = field(default_factory=list)

    # Statistics
    total_ticks: int = 0
    successful_ticks: int = 0
    failed_ticks: int = 0

    last_tick_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None

    def add_tick(self, tick: CrewRoutinesTick) -> None:
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
        """Get average success rate over last N ticks.

        Args:
            last_n: Number of recent ticks to consider

        Returns:
            Average success rate as float
        """
        if not self.ticks:
            return 0.0
        recent = self.ticks[-last_n:]
        return sum(t.get_success_rate() for t in recent) / len(recent)

    def get_uptime_percentage(self, window_hours: int = 24) -> float:
        """Calculate uptime percentage over time window.

        Args:
            window_hours: Time window in hours

        Returns:
            Uptime percentage (0-100)
        """
        if not self.ticks:
            return 0.0

        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent_ticks = [t for t in self.ticks if t.started_at > cutoff]

        if not recent_ticks:
            return 0.0

        successful = sum(1 for t in recent_ticks if t.status == "completed")
        return (successful / len(recent_ticks)) * 100

    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        return {
            "bot_name": self.bot_name,
            "total_ticks": self.total_ticks,
            "successful_ticks": self.successful_ticks,
            "failed_ticks": self.failed_ticks,
            "success_rate": self.get_average_success_rate(),
            "uptime_24h": self.get_uptime_percentage(24),
            "last_tick": self.last_tick_at.isoformat() if self.last_tick_at else None,
            "last_success": self.last_success_at.isoformat() if self.last_success_at else None,
        }


# Type aliases for common function signatures
CheckHandler = Callable[[Any, Dict[str, Any]], Any]
AsyncCheckHandler = Callable[[Any, Dict[str, Any]], Coroutine[Any, Any, Any]]


__all__ = [
    "CheckPriority",
    "CheckStatus",
    "CheckDefinition",
    "CheckResult",
    "CrewRoutinesConfig",
    "CrewRoutinesTick",
    "CrewRoutinesHistory",
    "CheckHandler",
    "AsyncCheckHandler",
]
