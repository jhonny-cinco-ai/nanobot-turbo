"""Reasoning configurations for bot implementations.

This module exports bot-specific Chain-of-Thought configurations.
"""

from nanobot.reasoning.config import (
    ReasoningConfig,
    CoTLevel,
    RESEARCHER_REASONING,
    CODER_REASONING,
    SOCIAL_REASONING,
    AUDITOR_REASONING,
    CREATIVE_REASONING,
    COORDINATOR_REASONING,
    DEFAULT_REASONING,
    get_reasoning_config,
    BOT_REASONING_CONFIGS,
)

__all__ = [
    "ReasoningConfig",
    "CoTLevel",
    "RESEARCHER_REASONING",
    "CODER_REASONING",
    "SOCIAL_REASONING",
    "AUDITOR_REASONING",
    "CREATIVE_REASONING",
    "COORDINATOR_REASONING",
    "DEFAULT_REASONING",
    "get_reasoning_config",
    "BOT_REASONING_CONFIGS",
]
