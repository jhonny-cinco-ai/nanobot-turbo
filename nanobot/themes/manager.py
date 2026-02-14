"""Theme manager for applying and switching themes."""

from typing import Optional

from nanobot.themes.presets import get_theme, list_themes, AVAILABLE_THEMES
from nanobot.themes.theme import Theme, ThemeName


class ThemeManager:
    """Manage theme selection and application."""

    def __init__(self, default_theme: str = "pirate_crew"):
        """Initialize theme manager.

        Args:
            default_theme: Default theme name (pirate_crew, rock_band, swat_team, feral_clowder, executive_suite, space_crew)
        """
        self.current_theme: Optional[Theme] = get_theme(default_theme)
        if self.current_theme is None:
            self.current_theme = AVAILABLE_THEMES[0]  # Fall back to first theme

    def list_themes(self) -> list[dict]:
        """Get list of available themes.

        Returns:
            List of theme dictionaries with name, display_name, description, emoji
        """
        return list_themes()

    def select_theme(self, theme_name: str) -> Optional[Theme]:
        """Select a theme.

        Args:
            theme_name: Theme name (pirate_crew, rock_band, etc.)

        Returns:
            Selected theme or None if not found
        """
        theme = get_theme(theme_name)
        if theme:
            self.current_theme = theme
            return theme
        return None

    def get_current_theme(self) -> Optional[Theme]:
        """Get currently active theme.

        Returns:
            Current theme or None
        """
        return self.current_theme

    def get_current_theme_name(self) -> Optional[str]:
        """Get name of currently active theme.

        Returns:
            Theme name or None
        """
        if self.current_theme:
            return self.current_theme.name.value
        return None

    def get_bot_theming(self, bot_name: str) -> dict:
        """Get theming for a specific bot in current theme.

        Args:
            bot_name: Name of bot (nanobot, researcher, coder, social, creative, auditor)

        Returns:
            Dictionary with bot theming info (title, personality, greeting, voice, emoji)
        """
        if not self.current_theme:
            return {}

        theming = self.current_theme.get_bot_theming(bot_name)
        if theming:
            return {
                "title": theming.title,
                "personality": theming.personality,
                "greeting": theming.greeting,
                "voice": theming.voice_directive,
                "emoji": theming.emoji,
            }
        return {}

    def get_all_bots_theming(self) -> dict:
        """Get theming for all bots in current theme.

        Returns:
            Dictionary mapping bot names to their theming
        """
        if not self.current_theme:
            return {}

        all_theming = {}
        for bot_name, theming in self.current_theme.get_all_bots_theming().items():
            all_theming[bot_name] = {
                "title": theming.title,
                "personality": theming.personality,
                "greeting": theming.greeting,
                "voice": theming.voice_directive,
                "emoji": theming.emoji,
            }
        return all_theming

    def to_dict(self) -> dict:
        """Convert current theme to dictionary.

        Returns:
            Theme dictionary representation
        """
        if self.current_theme:
            return self.current_theme.to_dict()
        return {}
