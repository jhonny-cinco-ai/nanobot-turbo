"""Configuration utilities for bot teams and custom names.

Provides functions to load and apply user preferences for:
- Crew teams (pirate, rock band, etc.)
- Custom bot display names
"""

import json
from typing import Dict, Optional

from loguru import logger

from nanofolks.config.loader import get_data_dir
from nanofolks.teams import TeamManager


class BotAppearanceConfig:
    """Manages bot appearance configuration (teams and custom names)."""

    def __init__(self):
        """Initialize appearance config."""
        self.config_dir = get_data_dir()
        self.team_file = self.config_dir / "team_config.json"
        self.names_file = self.config_dir / "bot_custom_names.json"

        # Load configurations
        self._team_manager: Optional[TeamManager] = None
        self._custom_names: Dict[str, str] = {}
        self._load_configs()

    def _load_configs(self) -> None:
        """Load team and name configurations from disk."""
        # Load team
        if self.team_file.exists():
            try:
                team_config = json.loads(self.team_file.read_text())
                current_team = team_config.get("current_team", "pirate_crew")
                self._team_manager = TeamManager(current_team)
                logger.debug(f"Loaded team: {current_team}")
            except Exception as e:
                logger.warning(f"Failed to load team config: {e}")
                self._team_manager = TeamManager("pirate_crew")
        else:
            # Default to pirate crew
            self._team_manager = TeamManager("pirate_crew")

        # Load custom names
        if self.names_file.exists():
            try:
                self._custom_names = json.loads(self.names_file.read_text())
                logger.debug(f"Loaded custom names for {len(self._custom_names)} bots")
            except Exception as e:
                logger.warning(f"Failed to load bot names config: {e}")
                self._custom_names = {}

    @property
    def team_manager(self) -> Optional[TeamManager]:
        """Get the current team manager.

        Returns:
            TeamManager instance or None
        """
        return self._team_manager

    def get_custom_name(self, bot_name: str) -> Optional[str]:
        """Get custom display name for a bot.

        Args:
            bot_name: Bot identifier (leader, researcher, coder, etc.)

        Returns:
            Custom name if set, None otherwise
        """
        return self._custom_names.get(bot_name.lower())

    def get_bot_appearance(self, bot_name: str) -> Dict[str, Optional[str]]:
        """Get complete appearance config for a bot.

        This combines team defaults with user customizations.

        Args:
            bot_name: Bot identifier

        Returns:
            Dictionary with display_name, title, greeting, etc.
        """
        result = {
            "display_name": None,
            "title": None,
            "greeting": None,
            "voice": None,
            "emoji": None,
        }

        # Get team defaults
        if self._team_manager and self._team_manager.current_team:
            profile = self._team_manager.get_bot_team_profile(bot_name)
            if profile:
                result["title"] = profile.get("title")
                result["greeting"] = profile.get("greeting")
                result["voice"] = profile.get("voice")
                result["emoji"] = profile.get("emoji")
                # Default display name is the title
                result["display_name"] = profile.get("title")

        # Override with custom name if set
        custom_name = self.get_custom_name(bot_name)
        if custom_name:
            result["display_name"] = custom_name

        return result

    def reload(self) -> None:
        """Reload configurations from disk."""
        self._load_configs()
        logger.info("Reloaded bot appearance configuration")


# Global instance
_appearance_config: Optional[BotAppearanceConfig] = None


def get_appearance_config() -> BotAppearanceConfig:
    """Get the global appearance configuration.

    Returns:
        BotAppearanceConfig instance (creates if needed)
    """
    global _appearance_config
    if _appearance_config is None:
        _appearance_config = BotAppearanceConfig()
    return _appearance_config


def reset_appearance_config() -> None:
    """Reset the global appearance configuration (forces reload)."""
    global _appearance_config
    _appearance_config = None
