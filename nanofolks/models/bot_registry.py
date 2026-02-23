"""Bot registry - loads bot configurations from template files."""

from pathlib import Path
from typing import Optional

from nanofolks.models.role_card import RoleCard, get_role_card


class BotRegistry:
    """Registry for bots - combines RoleCard with template files.

    Bots are defined by:
    1. RoleCard (domain + capabilities) - functional constraints
    2. SOUL.md - voice and personality
    3. IDENTITY.md - who am I
    4. AGENTS.md - role instructions

    Users can add new bots by creating template files.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize registry.

        Args:
            templates_dir: Path to templates directory. Defaults to package templates.
        """
        if templates_dir is None:
             import nanofolks
             templates_dir = Path(nanofolks.__file__).parent / "templates"

        self.templates_dir = templates_dir
        self.bots_dir = templates_dir / "bots"
        self.soul_dir = templates_dir / "soul"
        self.identity_dir = templates_dir / "identity"

    def get_bot_names(self) -> list[str]:
        """Get all available bot names from templates."""
        bots = set()

        # Get from bots/AGENTS templates
        if self.bots_dir.exists():
            for f in self.bots_dir.glob("*_AGENTS.md"):
                bots.add(f.stem.replace("_AGENTS", ""))

        # Get from soul/ templates
        if self.soul_dir.exists():
            for team_dir in self.soul_dir.iterdir():
                if team_dir.is_dir():
                    for f in team_dir.glob("*_SOUL.md"):
                        bots.add(f.stem.replace("_SOUL", ""))

        # Get from identity/ templates
        if self.identity_dir.exists():
            for team_dir in self.identity_dir.iterdir():
                if team_dir.is_dir():
                    for f in team_dir.glob("*_IDENTITY.md"):
                        bots.add(f.stem.replace("_IDENTITY", ""))

        return sorted(bots)

    def get_role_card(self, bot_name: str) -> Optional[RoleCard]:
        """Get RoleCard for a bot (from code, not files)."""
        return get_role_card(bot_name)

    def has_soul(self, bot_name: str) -> bool:
        """Check if bot has SOUL.md template."""
        if not self.soul_dir.exists():
            return False
        for team_dir in self.soul_dir.iterdir():
            if team_dir.is_dir():
                soul_file = team_dir / f"{bot_name}_SOUL.md"
                if soul_file.exists():
                    return True
        return False

    def has_identity(self, bot_name: str) -> bool:
        """Check if bot has IDENTITY.md template."""
        if not self.identity_dir.exists():
            return False
        for team_dir in self.identity_dir.iterdir():
            if team_dir.is_dir():
                identity_file = team_dir / f"{bot_name}_IDENTITY.md"
                if identity_file.exists():
                    return True
        return False

    def has_agents(self, bot_name: str) -> bool:
        """Check if bot has AGENTS.md template."""
        agents_file = self.bots_dir / f"{bot_name}_AGENTS.md"
        return agents_file.exists()

    def get_soul_content(self, bot_name: str, team_name: str = "pirate_crew") -> Optional[str]:
        """Get SOUL.md content for a bot and team."""
        soul_file = self.soul_dir / team_name / f"{bot_name}_SOUL.md"
        if soul_file.exists():
            return soul_file.read_text(encoding="utf-8")
        return None

    def get_identity_content(self, bot_name: str, team_name: str = "pirate_crew") -> Optional[str]:
        """Get IDENTITY.md content for a bot and team."""
        identity_file = self.identity_dir / team_name / f"{bot_name}_IDENTITY.md"
        if identity_file.exists():
            return identity_file.read_text(encoding="utf-8")
        return None

    def get_agents_content(self, bot_name: str) -> Optional[str]:
        """Get AGENTS.md content for a bot."""
        agents_file = self.bots_dir / f"{bot_name}_AGENTS.md"
        if agents_file.exists():
            return agents_file.read_text(encoding="utf-8")
        return None

    def get_available_teams(self) -> list[str]:
        """Get list of available teams."""
        if not self.soul_dir.exists():
            return []
        return [d.name for d in self.soul_dir.iterdir() if d.is_dir()]


# Global registry instance
_registry: Optional[BotRegistry] = None


def get_bot_registry() -> BotRegistry:
    """Get global bot registry instance."""
    global _registry
    if _registry is None:
        _registry = BotRegistry()
    return _registry


def list_available_bots() -> list[str]:
    """List all available bot names."""
    return get_bot_registry().get_bot_names()


def is_valid_bot(bot_name: str) -> bool:
    """Check if a bot name is valid (has RoleCard + templates)."""
    registry = get_bot_registry()
    return (
        registry.get_role_card(bot_name) is not None and
        (registry.has_soul(bot_name) or registry.has_agents(bot_name))
    )
