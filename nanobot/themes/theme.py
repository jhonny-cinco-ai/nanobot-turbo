"""Theme data structures for personality customization."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ThemeName(Enum):
    """Available personality themes."""

    PIRATE_CREW = "pirate_crew"
    ROCK_BAND = "rock_band"
    SWAT_TEAM = "swat_team"
    FERAL_CLOWDER = "feral_clowder"
    EXECUTIVE_SUITE = "executive_suite"
    SPACE_CREW = "space_crew"


@dataclass
class BotTheming:
    """How a bot appears within a theme."""

    title: str  # Role title ("Captain", "Lead Singer", "Commander", etc.)
    personality: str  # Brief personality description
    greeting: str  # How bot introduces itself
    voice_directive: str  # How bot should communicate
    emoji: str = ""  # Visual identifier
    default_name: str = ""  # Default display name (e.g., "Blackbeard", "Slash")

    def get_default_display_name(self) -> str:
        """Get the default display name for this bot.
        
        Returns:
            default_name if set, otherwise falls back to title
        """
        return self.default_name if self.default_name else self.title


@dataclass
class Theme:
    """Complete personality theme for the team."""

    name: ThemeName  # Theme identifier
    description: str  # Theme description
    nanobot: BotTheming  # nanobot theming
    researcher: BotTheming  # @researcher theming
    coder: BotTheming  # @coder theming
    social: BotTheming  # @social theming
    creative: BotTheming  # @creative theming
    auditor: BotTheming  # @auditor theming
    affinity_modifiers: Dict[str, float] = field(default_factory=dict)
    """Modifiers to affinity relationships in this theme"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional theme metadata"""

    def get_bot_theming(self, bot_name: str) -> Optional[BotTheming]:
        """Get theming for a specific bot.

        Args:
            bot_name: Name of bot (nanobot, researcher, coder, social, creative, auditor)

        Returns:
            BotTheming or None if bot not found
        """
        bot_map = {
            "nanobot": self.nanobot,
            "researcher": self.researcher,
            "coder": self.coder,
            "social": self.social,
            "creative": self.creative,
            "auditor": self.auditor,
        }
        return bot_map.get(bot_name)

    def get_all_bots_theming(self) -> Dict[str, BotTheming]:
        """Get theming for all 6 bots.

        Returns:
            Dictionary mapping bot names to their theming
        """
        return {
            "nanobot": self.nanobot,
            "researcher": self.researcher,
            "coder": self.coder,
            "social": self.social,
            "creative": self.creative,
            "auditor": self.auditor,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert theme to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "name": self.name.value,
            "description": self.description,
            "bots": {
                "nanobot": {
                    "title": self.nanobot.title,
                    "personality": self.nanobot.personality,
                    "greeting": self.nanobot.greeting,
                    "voice": self.nanobot.voice_directive,
                    "emoji": self.nanobot.emoji,
                },
                "researcher": {
                    "title": self.researcher.title,
                    "personality": self.researcher.personality,
                    "greeting": self.researcher.greeting,
                    "voice": self.researcher.voice_directive,
                    "emoji": self.researcher.emoji,
                },
                "coder": {
                    "title": self.coder.title,
                    "personality": self.coder.personality,
                    "greeting": self.coder.greeting,
                    "voice": self.coder.voice_directive,
                    "emoji": self.coder.emoji,
                },
                "social": {
                    "title": self.social.title,
                    "personality": self.social.personality,
                    "greeting": self.social.greeting,
                    "voice": self.social.voice_directive,
                    "emoji": self.social.emoji,
                },
                "creative": {
                    "title": self.creative.title,
                    "personality": self.creative.personality,
                    "greeting": self.creative.greeting,
                    "voice": self.creative.voice_directive,
                    "emoji": self.creative.emoji,
                },
                "auditor": {
                    "title": self.auditor.title,
                    "personality": self.auditor.personality,
                    "greeting": self.auditor.greeting,
                    "voice": self.auditor.voice_directive,
                    "emoji": self.auditor.emoji,
                },
            },
            "affinity_modifiers": self.affinity_modifiers,
        }
