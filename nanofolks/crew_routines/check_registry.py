"""Pluggable check registry for crew routines system.

This module provides a registry for crew routines checks that can be
dynamically registered and discovered by bot type.
"""

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from nanofolks.crew_routines.crew_routines_models import CheckDefinition, CheckResult, CheckStatus


@dataclass
class RegisteredCheck:
    """A registered check with its handler and metadata."""
    definition: CheckDefinition
    handler: Callable[..., Any]
    is_async: bool
    bot_domains: List[str]  # Which bot types can use this check


class CheckRegistry:
    """Registry of available crew routines checks.

    Checks can be registered dynamically and are discovered automatically
    for appropriate bot types. Supports both sync and async handlers.

    Example:
        registry = CheckRegistry()

        # Register a check
        @registry.check(
            name="github_issues",
            description="Check for new GitHub issues",
            bot_domains=["development"]
        )
        async def check_github_issues(bot, config):
            issues = await bot.check_repository_issues()
            return {"success": True, "issues_found": len(issues)}
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
        retry_attempts: int = 1,
        bot_domains: Optional[List[str]] = None,
        **config
    ) -> CheckDefinition:
        """Register a new check.

        Args:
            name: Unique check identifier
            handler: Function to execute (can be sync or async)
            description: Human-readable description
            priority: Check priority (critical/high/normal/low)
            max_duration_s: Maximum execution time in seconds
            retry_attempts: Number of retry attempts
            bot_domains: List of bot domains that can use this check
            **config: Additional check configuration

        Returns:
            CheckDefinition for the registered check

        Raises:
            ValueError: If check name already exists (unless overwritten)
        """
        from nanofolks.crew_routines.crew_routines_models import CheckDefinition, CheckPriority

        if name in self._checks:
            logger.warning(f"Check '{name}' already registered, overwriting")

        # Determine if handler is async
        is_async = inspect.iscoroutinefunction(handler)

        # Create definition
        definition = CheckDefinition(
            name=name,
            description=description or handler.__doc__ or "",
            priority=CheckPriority(priority),
            max_duration_s=max_duration_s,
            retry_attempts=retry_attempts,
            config=config
        )

        # Store registration
        self._checks[name] = RegisteredCheck(
            definition=definition,
            handler=handler,
            is_async=is_async,
            bot_domains=bot_domains or ["all"]
        )

        logger.debug(f"Registered crew routines check: {name}")
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
            logger.debug(f"Unregistered crew routines check: {name}")
            return True
        return False

    def get_check(self, name: str) -> Optional[RegisteredCheck]:
        """Get a registered check by name.

        Args:
            name: Check name

        Returns:
            RegisteredCheck or None if not found
        """
        return self._checks.get(name)

    def list_checks(
        self,
        bot_domain: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[CheckDefinition]:
        """List available checks with optional filtering.

        Args:
            bot_domain: Filter by bot domain (e.g., 'research', 'development')
            priority: Filter by priority level (e.g., 'critical', 'high')

        Returns:
            List of check definitions matching filters
        """
        checks = []

        for name, registered in self._checks.items():
            # Filter by bot domain
            if bot_domain:
                if bot_domain not in registered.bot_domains and "all" not in registered.bot_domains:
                    continue

            # Filter by priority
            if priority and registered.definition.priority.value != priority:
                continue

            checks.append(registered.definition)

        return checks

    def list_check_names(self) -> List[str]:
        """Get list of all registered check names.

        Returns:
            List of check names
        """
        return list(self._checks.keys())

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
            logger.warning(f"Check '{name}' timed out after {timeout}s")

        except Exception as e:
            result.status = CheckStatus.FAILED
            result.completed_at = datetime.now()
            result.error = str(e)
            result.error_type = type(e).__name__
            result.success = False
            logger.error(f"Check '{name}' failed: {e}")

        return result

    def check(
        self,
        name: Optional[str] = None,
        description: str = "",
        priority: str = "normal",
        max_duration_s: float = 60.0,
        retry_attempts: int = 1,
        bot_domains: Optional[List[str]] = None,
        **config
    ) -> Callable:
        """Decorator to register a function as a crew routines check.

        This is a convenience method that can be used as a decorator.

        Usage:
            registry = CheckRegistry()

            @registry.check(
                name="github_issues",
                description="Check for new GitHub issues",
                priority="high",
                bot_domains=["development"]
            )
            async def check_github_issues(bot, config):
                issues = await bot.check_repository_issues()
                return {"success": True, "issues_found": len(issues)}

        Args:
            name: Check name (uses function name if not provided)
            description: Human-readable description
            priority: Priority level
            max_duration_s: Maximum execution time
            retry_attempts: Number of retries
            bot_domains: Applicable bot domains
            **config: Additional configuration

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            check_name = name or func.__name__
            self.register(
                name=check_name,
                handler=func,
                description=description or func.__doc__ or "",
                priority=priority,
                max_duration_s=max_duration_s,
                retry_attempts=retry_attempts,
                bot_domains=bot_domains,
                **config
            )
            return func
        return decorator

    def clear(self) -> None:
        """Clear all registered checks. Useful for testing."""
        self._checks.clear()
        logger.debug("Cleared all registered checks")

    def __len__(self) -> int:
        """Return number of registered checks."""
        return len(self._checks)

    def __contains__(self, name: str) -> bool:
        """Check if a check is registered."""
        return name in self._checks


# Global registry instance for convenience
check_registry = CheckRegistry()


def register_check(
    name: Optional[str] = None,
    description: str = "",
    priority: str = "normal",
    max_duration_s: float = 60.0,
    retry_attempts: int = 1,
    bot_domains: Optional[List[str]] = None,
    **config
) -> Callable:
    """Global decorator to register a function as a crew routines check.

    This uses the global check_registry instance.

    Usage:
        from nanofolks.crew_routines.check_registry import register_check

        @register_check(
            name="github_issues",
            description="Check for new GitHub issues",
            bot_domains=["development"]
        )
        async def check_github_issues(bot, config):
            # Implementation
            return {"success": True, "issues_found": 5}

    Args:
        name: Check name
        description: Description
        priority: Priority level
        max_duration_s: Max duration
        retry_attempts: Retry attempts
        bot_domains: Bot domains
        **config: Additional config

    Returns:
        Decorator function
    """
    return check_registry.check(
        name=name,
        description=description,
        priority=priority,
        max_duration_s=max_duration_s,
        retry_attempts=retry_attempts,
        bot_domains=bot_domains,
        **config
    )


__all__ = [
    "CheckRegistry",
    "RegisteredCheck",
    "check_registry",
    "register_check",
]
