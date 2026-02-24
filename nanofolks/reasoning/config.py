"""Chain-of-Thought reasoning configuration for bots.

Provides adaptive reasoning that considers bot specialization,
routing tier, and tool context to optimize token usage while
maintaining reasoning quality.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class CoTLevel(Enum):
    """Chain-of-thought reasoning levels."""
    NONE = "none"           # No reflection, fastest
    MINIMAL = "minimal"     # Only after error-prone tools
    STANDARD = "standard"   # After complex tools
    FULL = "full"           # After every tool call


@dataclass
class ReasoningConfig:
    """Configuration for bot reasoning behavior.

    Provides adaptive Chain-of-Thought that considers:
    - Bot's base reasoning level
    - Routing tier (simple/medium/complex)
    - Tool-specific triggers

    Example:
        >>> config = ReasoningConfig(
        ...     cot_level=CoTLevel.STANDARD,
        ...     always_cot_tools={"spawn", "exec"},
        ...     never_cot_tools={"time", "date"},
        ... )
        >>> config.should_use_cot("complex", "spawn")
        True
        >>> config.should_use_cot("simple", "time")
        False
    """

    # Primary setting
    cot_level: CoTLevel = CoTLevel.STANDARD

    # Tier overrides (optional)
    simple_tier_level: Optional[CoTLevel] = None
    medium_tier_level: Optional[CoTLevel] = None
    complex_tier_level: Optional[CoTLevel] = None

    # Tool-specific triggers
    always_cot_tools: Set[str] = field(default_factory=set)
    never_cot_tools: Set[str] = field(default_factory=set)

    # Custom prompt (optional)
    reflection_prompt: Optional[str] = None

    # Token budget for reflection
    max_reflection_tokens: int = 150

    # LLM settings for crew_routines
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    def get_crew_routines_prompt(self) -> str:
        """Get reasoning guidance for crew_routines tasks.

        Returns:
            Prompt segment with reasoning instructions for crew_routines
        """
        if self.cot_level == CoTLevel.NONE:
            return ""

        level_name = get_cot_level_name(self.cot_level)

        base = f"[{level_name} reasoning mode]"

        # Add reflection guidance based on level
        if self.cot_level in (CoTLevel.STANDARD, CoTLevel.FULL):
            base += " Think step-by-step through each checklist item."

        if self.cot_level == CoTLevel.FULL:
            base += " Consider alternatives and edge cases."

        return base

    def should_use_cot(self, tier: str, tool_name: str) -> bool:
        """Determine if CoT should be used for this context.

        Args:
            tier: Routing tier ("simple", "medium", "complex")
            tool_name: Name of the tool being executed

        Returns:
            True if CoT reflection should be added
        """
        # Check exclusions first (highest priority)
        if tool_name in self.never_cot_tools:
            logger.debug(f"CoT disabled for tool '{tool_name}' (in never_cot_tools)")
            return False

        # Check mandatory triggers
        if tool_name in self.always_cot_tools:
            logger.debug(f"CoT enabled for tool '{tool_name}' (in always_cot_tools)")
            return True

        # Determine effective level based on tier
        effective_level = self._get_effective_level(tier)

        # Map level to behavior
        if effective_level == CoTLevel.NONE:
            return False
        elif effective_level == CoTLevel.FULL:
            return True
        elif effective_level == CoTLevel.MINIMAL:
            # Only for error-prone tools
            error_prone = {"spawn", "exec", "eval", "github"}
            return tool_name in error_prone
        else:  # STANDARD
            # After multi-step or complex tools, skip simple ones
            simple_tools = {"time", "date", "ping", "weather"}
            return tool_name not in simple_tools

    def _get_effective_level(self, tier: str) -> CoTLevel:
        """Get CoT level considering tier overrides.

        Args:
            tier: Routing tier

        Returns:
            Effective CoTLevel for this tier
        """
        # Check for explicit override
        tier_map = {
            "simple": self.simple_tier_level,
            "medium": self.medium_tier_level,
            "complex": self.complex_tier_level,
        }

        override = tier_map.get(tier.lower())
        if override is not None:
            return override

        # Apply default tier adjustments
        levels = [CoTLevel.NONE, CoTLevel.MINIMAL, CoTLevel.STANDARD, CoTLevel.FULL]

        try:
            idx = levels.index(self.cot_level)
        except ValueError:
            logger.warning(f"Unknown cot_level: {self.cot_level}, defaulting to STANDARD")
            return CoTLevel.STANDARD

        if tier.lower() == "simple" and self.cot_level != CoTLevel.NONE:
            # Downgrade simple tier by one level
            return levels[max(0, idx - 1)]
        elif tier.lower() == "complex" and self.cot_level != CoTLevel.FULL:
            # Upgrade complex tier by one level
            return levels[min(len(levels) - 1, idx + 1)]

        return self.cot_level

    def get_reflection_prompt(self) -> str:
        """Get the reflection prompt.

        Returns:
            Custom prompt if set, otherwise default
        """
        if self.reflection_prompt:
            return self.reflection_prompt
        return "Reflect on the results and decide next steps."


# Bot-specific reasoning configurations
RESEARCHER_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    always_cot_tools={"search", "analyze", "compare", "research"},
    never_cot_tools={"time", "date", "ping"},
    reflection_prompt="""Reflect on your research:
1. What sources did you find? Are they credible?
2. What gaps exist in the information?
3. What's the key insight for the user?
4. What follow-up might be valuable?""",
    max_reflection_tokens=200,
)

CODER_REASONING = ReasoningConfig(
    cot_level=CoTLevel.FULL,
    always_cot_tools={"spawn", "exec", "github", "eval", "test"},
    never_cot_tools={"time", "date"},
    reflection_prompt="""Analyze this code execution:
1. Did the code run successfully? If not, what error occurred?
2. What does the output/outputs tell you?
3. What's the next implementation step?
4. Are there edge cases or issues to address?""",
    max_reflection_tokens=250,
)

SOCIAL_REASONING = ReasoningConfig(
    cot_level=CoTLevel.NONE,
    simple_tier_level=CoTLevel.NONE,
    medium_tier_level=CoTLevel.NONE,
    complex_tier_level=CoTLevel.MINIMAL,  # Only for complex campaigns
    always_cot_tools=set(),
    never_cot_tools={"*"},  # Never use CoT for social (all tools)
    reflection_prompt=None,
    max_reflection_tokens=0,
)

AUDITOR_REASONING = ReasoningConfig(
    cot_level=CoTLevel.MINIMAL,
    always_cot_tools={"audit", "review", "analyze"},
    never_cot_tools={"time", "date", "list", "ping"},
    reflection_prompt="""Verify audit findings:
1. What issues were identified? How severe?
2. Are there compliance violations to address?
3. What's the recommended remediation?
4. Any gaps in the audit scope?""",
    max_reflection_tokens=100,
)

CREATIVE_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    always_cot_tools={"generate", "design", "edit", "create"},
    never_cot_tools={"time", "date", "ping"},
    reflection_prompt="""Evaluate your creative work:
1. Does this match the user's intent?
2. What alternatives could work?
3. Any improvements to suggest?
4. Is anything missing?""",
    max_reflection_tokens=180,
)

COORDINATOR_REASONING = ReasoningConfig(
    cot_level=CoTLevel.FULL,
    always_cot_tools={"delegate", "coordinate", "notify", "dispatch"},
    never_cot_tools={"time", "date", "ping"},
    reflection_prompt="""Assess coordination status:
1. What tasks are in progress? Any blockers?
2. Which bot is best suited for next action?
3. Any updates needed for the user?
4. What's the priority order?""",
    max_reflection_tokens=200,
)

# Default fallback
DEFAULT_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    reflection_prompt="""Reflect on the results:
1. Did the action complete successfully?
2. What does the output tell you?
3. What's the next step?
4. Any issues to address?""",
    max_reflection_tokens=150,
)

# Mapping of bot names to their reasoning configs
BOT_REASONING_CONFIGS: Dict[str, ReasoningConfig] = {
    "ResearcherBot": RESEARCHER_REASONING,
    "CoderBot": CODER_REASONING,
    "SocialBot": SOCIAL_REASONING,
    "AuditorBot": AUDITOR_REASONING,
    "CreativeBot": CREATIVE_REASONING,
    "BotLeader": COORDINATOR_REASONING,
    "coordinator": COORDINATOR_REASONING,
    "leader": COORDINATOR_REASONING,
    "researcher": RESEARCHER_REASONING,
    "coder": CODER_REASONING,
    "social": SOCIAL_REASONING,
    "auditor": AUDITOR_REASONING,
    "creative": CREATIVE_REASONING,
}


def get_reasoning_config(bot_name: str) -> ReasoningConfig:
    """Get reasoning configuration for a bot.

    Args:
        bot_name: Name of the bot (e.g., "CoderBot", "coder")

    Returns:
        ReasoningConfig for the bot, or default if not found
    """
    # Try exact match first
    if bot_name in BOT_REASONING_CONFIGS:
        return BOT_REASONING_CONFIGS[bot_name]

    # Try case-insensitive match
    bot_name_lower = bot_name.lower()
    for name, config in BOT_REASONING_CONFIGS.items():
        if name.lower() == bot_name_lower:
            return config

    # Return default
    logger.debug(f"No reasoning config found for '{bot_name}', using default")
    return DEFAULT_REASONING


def get_cot_level_name(level: CoTLevel) -> str:
    """Get human-readable name for CoT level.

    Args:
        level: CoTLevel enum value

    Returns:
        Human-readable string
    """
    names = {
        CoTLevel.NONE: "No CoT",
        CoTLevel.MINIMAL: "Minimal CoT",
        CoTLevel.STANDARD: "Standard CoT",
        CoTLevel.FULL: "Full CoT",
    }
    return names.get(level, "Unknown")
