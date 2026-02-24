"""Crew routines checks for all bot types.

This module exports all domain-specific crew routines checks.
Importing these modules automatically registers the checks
with the global check registry.

Example:
    from nanofolks.bots.checks import researcher_checks, coder_checks
    # Checks are now registered and can be used by BotCrewRoutinesService
"""

# Import all check modules to ensure registration
# The act of importing registers the checks via @register_check decorator
from . import (
    auditor_checks,
    coder_checks,
    coordinator_checks,
    creative_checks,
    researcher_checks,
    social_checks,
)

__all__ = [
    "researcher_checks",
    "coder_checks",
    "social_checks",
    "auditor_checks",
    "creative_checks",
    "coordinator_checks",
]
