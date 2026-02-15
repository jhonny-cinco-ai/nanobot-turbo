"""Bot template files for multi-agent system."""

from pathlib import Path
from typing import Optional

TEMPLATES_DIR = Path(__file__).parent / "bots"
SOUL_TEMPLATES_DIR = Path(__file__).parent / "soul"
IDENTITY_TEMPLATES_DIR = Path(__file__).parent / "identity"

BOT_NAMES = ["nanobot", "researcher", "coder", "social", "creative", "auditor"]
THEME_NAMES = ["pirate_crew", "rock_band", "swat_team", "feral_clowder", "executive_suite", "space_crew"]


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


def get_soul_template_for_bot(bot_name: str, theme: Optional[str] = None) -> Optional[str]:
    """Get SOUL.md template for a bot.
    
    Tries to find SOUL template from themes. If no theme specified,
    tries all available themes and returns first match.
    
    Args:
        bot_name: Name of the bot
        theme: Optional theme name. If not specified, tries all themes.
        
    Returns:
        SOUL.md template content or None if not found
    """
    # If theme specified, try that specific theme
    if theme:
        template_file = SOUL_TEMPLATES_DIR / theme / f"{bot_name}_SOUL.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
        return None
    
    # Try all available themes, return first match
    for theme_name in THEME_NAMES:
        template_file = SOUL_TEMPLATES_DIR / theme_name / f"{bot_name}_SOUL.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
    
    return None


def get_identity_template_for_bot(bot_name: str, theme: Optional[str] = None) -> Optional[str]:
    """Get IDENTITY.md template for a bot.
    
    Tries to find IDENTITY template from themes. If no theme specified,
    tries all available themes and returns first match.
    
    Args:
        bot_name: Name of the bot
        theme: Optional theme name. If not specified, tries all themes.
        
    Returns:
        IDENTITY.md template content or None if not found
    """
    # If theme specified, try that specific theme
    if theme:
        template_file = IDENTITY_TEMPLATES_DIR / theme / f"{bot_name}_IDENTITY.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
        return None
    
    # Try all available themes, return first match
    for theme_name in THEME_NAMES:
        template_file = IDENTITY_TEMPLATES_DIR / theme_name / f"{bot_name}_IDENTITY.md"
        if template_file.exists():
            return template_file.read_text(encoding="utf-8")
    
    return None
