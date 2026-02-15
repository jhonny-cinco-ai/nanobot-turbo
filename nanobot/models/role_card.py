"""Minimal role card - only functional constraints in code."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class RoleCardDomain(Enum):
    """Domain/specialty of a bot."""
    COORDINATION = "coordination"
    RESEARCH = "research"
    DEVELOPMENT = "development"
    COMMUNITY = "community"
    DESIGN = "design"
    QUALITY = "quality"


@dataclass
class BotCapabilities:
    """What features/tools are enabled for a bot."""
    can_invoke_bots: bool = False
    can_do_heartbeat: bool = False
    can_access_web: bool = True
    can_exec_commands: bool = True
    can_send_messages: bool = True
    max_concurrent_tasks: int = 1


@dataclass
class RoleCard:
    """Minimal bot configuration - only functional constraints.
    
    Everything else (personality, voice, identity) comes from template files:
    - SOUL.md: Voice, core truths, how the bot speaks
    - IDENTITY.md: Who am I, relationships, quirks
    - AGENTS.md: Role instructions, guidelines
    """
    
    bot_name: str  # System identifier (e.g., "researcher", "coder")
    domain: RoleCardDomain  # What the bot specializes in
    capabilities: BotCapabilities = field(default_factory=BotCapabilities)
    
    # Metadata
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_capability(self, cap: str) -> bool:
        """Check if bot has a capability."""
        return getattr(self.capabilities, cap, False)


# Built-in bot definitions (minimal - just domain + capabilities)
# These define what each bot CAN do functionally
BUILTIN_BOTS: Dict[str, RoleCard] = {
    "leader": RoleCard(
        bot_name="leader",
        domain=RoleCardDomain.COORDINATION,
        capabilities=BotCapabilities(
            can_invoke_bots=True,
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=True,
            can_send_messages=True,
            max_concurrent_tasks=3,
        ),
    ),
    "researcher": RoleCard(
        bot_name="researcher",
        domain=RoleCardDomain.RESEARCH,
        capabilities=BotCapabilities(
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=False,
            can_send_messages=False,
        ),
    ),
    "coder": RoleCard(
        bot_name="coder",
        domain=RoleCardDomain.DEVELOPMENT,
        capabilities=BotCapabilities(
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=True,
            can_send_messages=False,
        ),
    ),
    "social": RoleCard(
        bot_name="social",
        domain=RoleCardDomain.COMMUNITY,
        capabilities=BotCapabilities(
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=False,
            can_send_messages=True,
        ),
    ),
    "creative": RoleCard(
        bot_name="creative",
        domain=RoleCardDomain.DESIGN,
        capabilities=BotCapabilities(
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=False,
            can_send_messages=False,
        ),
    ),
    "auditor": RoleCard(
        bot_name="auditor",
        domain=RoleCardDomain.QUALITY,
        capabilities=BotCapabilities(
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=True,
            can_send_messages=False,
        ),
    ),
}


def get_role_card(bot_name: str) -> Optional[RoleCard]:
    """Get role card for a bot.
    
    Args:
        bot_name: Name of the bot
        
    Returns:
        RoleCard or None if not found
    """
    return BUILTIN_BOTS.get(bot_name)


def list_bots() -> list[str]:
    """List all available bot names."""
    return list(BUILTIN_BOTS.keys())


def is_valid_bot(bot_name: str) -> bool:
    """Check if a bot name is valid."""
    return bot_name in BUILTIN_BOTS
