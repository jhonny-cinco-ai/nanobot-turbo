"""Bot template files for multi-agent system."""

from pathlib import Path
from typing import Optional

TEMPLATES_DIR = Path(__file__).parent / "bots"
SOUL_TEMPLATES_DIR = Path(__file__).parent / "soul"
IDENTITY_TEMPLATES_DIR = Path(__file__).parent / "identity"
ROLE_TEMPLATES_DIR = Path(__file__).parent / "role"

BOT_NAMES = ["leader", "researcher", "coder", "social", "creative", "auditor"]
TEAM_NAMES = ["pirate_crew", "rock_band", "swat_team", "feral_clowder", "executive_suite", "space_crew"]


def get_agents_template(bot_name: str) -> str | None:
    """Get AGENTS.md template for a bot.

    Args:
        bot_name: Name of the bot

    Returns:
        Template content or None if not found
    """
    template_file = TEMPLATES_DIR / f"{bot_name}_AGENTS.md"
    if template_file.exists():
        return template_file.read_text(encoding="utf-8")
    return None


def get_all_agents_templates() -> dict[str, str]:
    """Get all AGENTS.md templates.

    Returns:
        Dict mapping bot_name to template content
    """
    templates = {}
    for bot_name in BOT_NAMES:
        content = get_agents_template(bot_name)
        if content:
            templates[bot_name] = content
    return templates


def get_soul_template_for_bot(bot_name: str, team: Optional[str] = None) -> Optional[str]:
    """Get SOUL.md template for a bot.

    Tries to find SOUL template from teams. If no team specified,
    tries all available teams and returns first match.

    Args:
        bot_name: Name of the bot
        team: Optional team name. If not specified, tries all teams.

    Returns:
        SOUL.md template content or None if not found
    """
    # If team specified, try that specific team
    if team:
        template_file = SOUL_TEMPLATES_DIR / team / f"{bot_name}_SOUL.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
        return None

    # Try all available teams, return first match
    for team_name in TEAM_NAMES:
        template_file = SOUL_TEMPLATES_DIR / team_name / f"{bot_name}_SOUL.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")

    return None


def get_identity_template_for_bot(bot_name: str, team: Optional[str] = None) -> Optional[str]:
    """Get IDENTITY.md template for a bot.

    Tries to find IDENTITY template from teams. If no team specified,
    tries all available teams and returns first match.

    Args:
        bot_name: Name of the bot
        team: Optional team name. If not specified, tries all teams.

    Returns:
        IDENTITY.md template content or None if not found
    """
    # If team specified, try that specific team
    if team:
        template_file = IDENTITY_TEMPLATES_DIR / team / f"{bot_name}_IDENTITY.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
        return None

    # Try all available teams, return first match
    for team_name in TEAM_NAMES:
        template_file = IDENTITY_TEMPLATES_DIR / team_name / f"{bot_name}_IDENTITY.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")

    return None


def get_role_template_for_bot(bot_name: str) -> Optional[str]:
    """Get ROLE.md template for a bot.

    Loads the default ROLE.md template for the specified bot.

    Args:
        bot_name: Name of the bot

    Returns:
        ROLE.md template content or None if not found
    """
    template_file = ROLE_TEMPLATES_DIR / f"{bot_name}_ROLE.md"
    if template_file.exists():
        return template_file.read_text(encoding="utf-8")
    return None


def get_all_role_templates() -> dict[str, str]:
    """Get all ROLE.md templates.

    Returns:
        Dict mapping bot_name to template content
    """
    templates = {}
    for bot_name in BOT_NAMES:
        content = get_role_template_for_bot(bot_name)
        if content:
            templates[bot_name] = content
    return templates


# Import discovery functions for template-based team management
from nanofolks.templates.discovery import (
    discover_teams,
    get_team,
    list_teams,
    get_bot_team_profile,
    get_all_bot_team_profiles,
)
from nanofolks.templates.parser import (
    get_bot_metadata,
    parse_soul_file,
    parse_identity_file,
    BotMetadata,
)

__all__ = [
    # Template getters
    "get_agents_template",
    "get_all_agents_templates",
    "get_soul_template_for_bot",
    "get_identity_template_for_bot",
    "get_role_template_for_bot",
    "get_all_role_templates",
    # Discovery functions
    "discover_teams",
    "get_team",
    "list_teams",
    "get_bot_team_profile",
    "get_all_bot_team_profiles",
    # Parser functions
    "get_bot_metadata",
    "parse_soul_file",
    "parse_identity_file",
    "BotMetadata",
    # Constants
    "BOT_NAMES",
    "TEAM_NAMES",
]
