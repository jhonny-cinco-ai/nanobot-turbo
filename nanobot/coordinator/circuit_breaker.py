"""Circuit breaker pattern for resilient bot operations.

Implements circuit breaker pattern to detect failures, prevent cascading failures,
and provide automatic recovery mechanisms with retry logic and fallback strategies.
"""

import time
import random
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps

from loguru import logger


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5           # Failures before opening
    success_threshold: int = 2           # Successes to close from half-open
    timeout: float = 60.0                # Seconds before half-open attempt
    retry_attempts: int = 3              # Max retry attempts
    retry_delay: float = 1.0             # Initial retry delay (seconds)
    retry_backoff: float = 2.0           # Backoff multiplier
    retry_jitter: float = 0.1            # Jitter factor (0.0-1.0)


@dataclass
class CallMetrics:
    """Metrics for a bot call."""
    bot_id: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    average_response_time: float = 0.0
    total_response_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.call_count == 0:
            return 1.0
        return self.success_count / self.call_count
    
    @property
    def is_healthy(self) -> bool:
        """Check if bot is healthy."""
        if self.call_count < 5:
            return True  # Not enough data
        return self.success_rate >= 0.7


class CircuitBreaker:
    """Circuit breaker for bot failure protection.
    
    Monitors bot health, detects failures, and prevents cascading failures
    by temporarily rejecting calls to failing bots.
    """
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize circuit breaker.
        
        Args:
            config: Configuration options
        """
        self.config = config or CircuitBreakerConfig()
        self._states: Dict[str, CircuitState] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._metrics: Dict[str, CallMetrics] = {}
        self._fallbacks: Dict[str, Callable] = {}
    
    def register_bot(self, bot_id: str, fallback: Optional[Callable] = None) -> None:
        """Register a bot for circuit breaker monitoring.
        
        Args:
            bot_id: Bot identifier
            fallback: Optional fallback function
        """
        self._states[bot_id] = CircuitState.CLOSED
        self._metrics[bot_id] = CallMetrics(bot_id=bot_id)
        if fallback:
            self._fallbacks[bot_id] = fallback
    
    def call(
        self,
        bot_id: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with circuit breaker protection.
        
        Args:
            bot_id: Bot being called
            operation: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: If operation fails after retries
        """
        # Check circuit state
        state = self._get_state(bot_id)
        
        if state == CircuitState.OPEN:
            # Check if we should try half-open
            if self._should_attempt_reset(bot_id):
                logger.info(f"Circuit for {bot_id} attempting reset (half-open)")
                self._set_state(bot_id, CircuitState.HALF_OPEN)
            else:
                logger.warning(f"Circuit open for {bot_id}, rejecting call")
                if bot_id in self._fallbacks:
                    return self._fallbacks[bot_id](*args, **kwargs)
                raise CircuitBreakerOpen(f"Circuit open for bot {bot_id}")
        
        # Execute with retry logic
        return self._execute_with_retry(bot_id, operation, *args, **kwargs)
    
    def _execute_with_retry(
        self,
        bot_id: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with retry logic.
        
        Args:
            bot_id: Bot being called
            operation: Function to execute
            
        Returns:
            Operation result
            
        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        delay = self.config.retry_delay
        
        for attempt in range(self.config.retry_attempts + 1):
            start_time = time.time()
            
            try:
                result = operation(*args, **kwargs)
                
                # Record success
                response_time = time.time() - start_time
                self._record_success(bot_id, response_time)
                
                return result
                
            except Exception as e:
                last_exception = e
                response_time = time.time() - start_time
                
                # Record failure
                self._record_failure(bot_id, response_time)
                
                if attempt < self.config.retry_attempts:
                    # Calculate delay with jitter
                    jitter = delay * self.config.retry_jitter * (2 * random.random() - 1)
                    actual_delay = max(0, delay + jitter)
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {bot_id}, "
                        f"retrying in {actual_delay:.2f}s"
                    )
                    time.sleep(actual_delay)
                    
                    # Exponential backoff
                    delay *= self.config.retry_backoff
                else:
                    logger.error(f"All {self.config.retry_attempts + 1} attempts failed for {bot_id}")
        
        # All retries exhausted
        raise last_exception
    
    def _record_success(self, bot_id: str, response_time: float) -> None:
        """Record successful call.
        
        Args:
            bot_id: Bot ID
            response_time: Response time in seconds
        """
        metrics = self._get_metrics(bot_id)
        
        metrics.call_count += 1
        metrics.success_count += 1
        metrics.consecutive_successes += 1
        metrics.consecutive_failures = 0
        metrics.last_success_time = datetime.now()
        
        # Update average response time
        metrics.total_response_time += response_time
        metrics.average_response_time = (
            metrics.total_response_time / metrics.call_count
        )
        
        # Check if we should close circuit from half-open
        if self._get_state(bot_id) == CircuitState.HALF_OPEN:
            if metrics.consecutive_successes >= self.config.success_threshold:
                logger.info(f"Circuit for {bot_id} closed (recovered)")
                self._set_state(bot_id, CircuitState.CLOSED)
                metrics.consecutive_successes = 0
    
    def _record_failure(self, bot_id: str, response_time: float) -> None:
        """Record failed call.
        
        Args:
            bot_id: Bot ID
            response_time: Response time in seconds
        """
        metrics = self._get_metrics(bot_id)
        
        metrics.call_count += 1
        metrics.failure_count += 1
        metrics.consecutive_failures += 1
        metrics.consecutive_successes = 0
        metrics.last_failure_time = datetime.now()
        
        # Update average response time
        metrics.total_response_time += response_time
        metrics.average_response_time = (
            metrics.total_response_time / metrics.call_count
        )
        
        # Update last failure time for circuit
        self._last_failure_time[bot_id] = time.time()
        
        # Check if we should open circuit
        if metrics.consecutive_failures >= self.config.failure_threshold:
            if self._get_state(bot_id) != CircuitState.OPEN:
                logger.error(
                    f"Circuit for {bot_id} opened after "
                    f"{metrics.consecutive_failures} consecutive failures"
                )
                self._set_state(bot_id, CircuitState.OPEN)
    
    def _get_state(self, bot_id: str) -> CircuitState:
        """Get circuit state for bot.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            Circuit state
        """
        return self._states.get(bot_id, CircuitState.CLOSED)
    
    def _set_state(self, bot_id: str, state: CircuitState) -> None:
        """Set circuit state for bot.
        
        Args:
            bot_id: Bot ID
            state: New state
        """
        old_state = self._states.get(bot_id)
        self._states[bot_id] = state
        
        if old_state != state:
            logger.info(f"Circuit state for {bot_id}: {old_state.value} -> {state.value}")
    
    def _get_metrics(self, bot_id: str) -> CallMetrics:
        """Get or create metrics for bot.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            Call metrics
        """
        if bot_id not in self._metrics:
            self._metrics[bot_id] = CallMetrics(bot_id=bot_id)
        return self._metrics[bot_id]
    
    def _should_attempt_reset(self, bot_id: str) -> bool:
        """Check if enough time has passed to try reset.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            True if should attempt reset
        """
        last_failure = self._last_failure_time.get(bot_id)
        if last_failure is None:
            return True
        
        return (time.time() - last_failure) >= self.config.timeout
    
    def get_metrics(self, bot_id: str) -> Optional[CallMetrics]:
        """Get metrics for a bot.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            Metrics or None
        """
        return self._metrics.get(bot_id)
    
    def get_all_metrics(self) -> Dict[str, CallMetrics]:
        """Get metrics for all bots.
        
        Returns:
            Dict of bot_id -> metrics
        """
        return dict(self._metrics)
    
    def get_state(self, bot_id: str) -> CircuitState:
        """Get current circuit state.
        
        Args:
            bot_id: Bot ID
            
        Returns:
            Current state
        """
        return self._get_state(bot_id)
    
    def reset(self, bot_id: str) -> None:
        """Manually reset circuit breaker for a bot.
        
        Args:
            bot_id: Bot ID
        """
        self._set_state(bot_id, CircuitState.CLOSED)
        if bot_id in self._metrics:
            self._metrics[bot_id] = CallMetrics(bot_id=bot_id)
        if bot_id in self._last_failure_time:
            del self._last_failure_time[bot_id]
        
        logger.info(f"Circuit for {bot_id} manually reset")
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health report for all monitored bots.
        
        Returns:
            Health report dictionary
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_bots": len(self._states),
            "states": {},
            "metrics": {},
            "healthy_bots": [],
            "unhealthy_bots": [],
        }
        
        for bot_id, state in self._states.items():
            report["states"][bot_id] = state.value
            
            metrics = self._metrics.get(bot_id)
            if metrics:
                report["metrics"][bot_id] = {
                    "success_rate": f"{metrics.success_rate:.1%}",
                    "avg_response_time": f"{metrics.average_response_time:.3f}s",
                    "total_calls": metrics.call_count,
                    "is_healthy": metrics.is_healthy,
                }
                
                if metrics.is_healthy and state == CircuitState.CLOSED:
                    report["healthy_bots"].append(bot_id)
                else:
                    report["unhealthy_bots"].append(bot_id)
        
        return report


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryStrategy:
    """Configurable retry strategy with exponential backoff.
    
    Provides flexible retry mechanisms with various backoff strategies.
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[type]] = None
    ):
        """Initialize retry strategy.
        
        Args:
            max_attempts: Maximum retry attempts
            base_delay: Initial delay between retries
            max_delay: Maximum delay cap
            backoff_factor: Exponential backoff multiplier
            jitter: Whether to add random jitter
            retryable_exceptions: Exception types to retry
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]
    
    def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with retry logic.
        
        Args:
            operation: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None
        delay = self.base_delay
        
        for attempt in range(self.max_attempts):
            try:
                return operation(*args, **kwargs)
            except tuple(self.retryable_exceptions) as e:
                last_exception = e
                
                if attempt < self.max_attempts - 1:
                    # Calculate delay with optional jitter
                    actual_delay = delay
                    if self.jitter:
                        jitter_amount = delay * 0.1 * (2 * random.random() - 1)
                        actual_delay = max(0, delay + jitter_amount)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.max_attempts} failed: {e}. "
                        f"Retrying in {actual_delay:.2f}s..."
                    )
                    
                    time.sleep(actual_delay)
                    
                    # Exponential backoff
                    delay = min(delay * self.backoff_factor, self.max_delay)
                else:
                    logger.error(f"All {self.max_attempts} attempts failed")
        
        raise last_exception
    
    def with_retry(self, operation: Callable) -> Callable:
        """Decorator to add retry logic to a function.
        
        Args:
            operation: Function to wrap
            
        Returns:
            Wrapped function
        """
        @wraps(operation)
        def wrapper(*args, **kwargs):
            return self.execute(operation, *args, **kwargs)
        return wrapper


class LoadBalancer:
    """Simple load balancer for distributing work across bots.
    
    Monitors bot load and distributes tasks to prevent overload.
    """
    
    def __init__(self):
        """Initialize load balancer."""
        self._bot_loads: Dict[str, int] = {}
        self._bot_capacity: Dict[str, int] = {}
        self._task_history: List[Dict[str, Any]] = []
    
    def register_bot(self, bot_id: str, capacity: int = 10) -> None:
        """Register a bot with load balancer.
        
        Args:
            bot_id: Bot identifier
            capacity: Maximum concurrent tasks
        """
        self._bot_loads[bot_id] = 0
        self._bot_capacity[bot_id] = capacity
    
    def assign_task(self, task_id: str, candidate_bots: List[str]) -> Optional[str]:
        """Assign task to least loaded bot.
        
        Args:
            task_id: Task identifier
            candidate_bots: List of available bot IDs
            
        Returns:
            Selected bot ID or None if all overloaded
        """
        if not candidate_bots:
            return None
        
        # Filter to bots with capacity
        available = []
        for bot_id in candidate_bots:
            load = self._bot_loads.get(bot_id, 0)
            capacity = self._bot_capacity.get(bot_id, 10)
            
            if load < capacity:
                available.append((bot_id, load))
        
        if not available:
            logger.warning(f"All bots overloaded for task {task_id}")
            return None
        
        # Select least loaded
        selected = min(available, key=lambda x: x[1])[0]
        
        # Update load
        self._bot_loads[selected] = self._bot_loads.get(selected, 0) + 1
        
        # Record assignment
        self._task_history.append({
            "task_id": task_id,
            "bot_id": selected,
            "timestamp": datetime.now(),
        })
        
        logger.info(f"Task {task_id} assigned to {selected} "
                   f"(load: {self._bot_loads[selected]}/{self._bot_capacity.get(selected, 10)})")
        
        return selected
    
    def complete_task(self, bot_id: str) -> None:
        """Mark task as completed for a bot.
        
        Args:
            bot_id: Bot that completed task
        """
        if bot_id in self._bot_loads and self._bot_loads[bot_id] > 0:
            self._bot_loads[bot_id] -= 1
    
    def get_load_report(self) -> Dict[str, Any]:
        """Get current load report.
        
        Returns:
            Load report dictionary
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "bots": {},
            "total_active_tasks": sum(self._bot_loads.values()),
            "total_capacity": sum(self._bot_capacity.values()),
        }
        
        for bot_id, load in self._bot_loads.items():
            capacity = self._bot_capacity.get(bot_id, 10)
            utilization = load / capacity if capacity > 0 else 0
            
            report["bots"][bot_id] = {
                "load": load,
                "capacity": capacity,
                "utilization": f"{utilization:.1%}",
                "available": capacity - load,
            }
        
        return report
    
    def is_overloaded(self, bot_id: str, threshold: float = 0.9) -> bool:
        """Check if bot is overloaded.
        
        Args:
            bot_id: Bot to check
            threshold: Utilization threshold (0.0-1.0)
            
        Returns:
            True if overloaded
        """
        load = self._bot_loads.get(bot_id, 0)
        capacity = self._bot_capacity.get(bot_id, 10)
        
        if capacity == 0:
            return True
        
        return (load / capacity) >= threshold
