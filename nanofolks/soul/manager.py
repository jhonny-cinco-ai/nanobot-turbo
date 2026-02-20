"""Manage personality files for all team members in multi-agent system."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


def get_agents_templates() -> Dict[str, str]:
    """Get AGENTS.md templates from template files.

    Returns:
        Dict mapping bot_name to template content
    """
    from nanofolks.templates import get_all_agents_templates
    return get_all_agents_templates()


class SoulManager:
    """Manage SOUL.md files for all team members.

    Handles per-bot personality files in workspace/bots/{name}/SOUL.md structure.
    Supports theme application to all team members atomically.

    Also manages AGENTS.md files for per-bot instructions.
    """

    def __init__(self, workspace_path: Path):
        """Initialize SoulManager.

        Args:
            workspace_path: Path to workspace directory
        """
        self.workspace = Path(workspace_path)
        self.bots_dir = self.workspace / "bots"
        self.bots_dir.mkdir(parents=True, exist_ok=True)

    def apply_theme_to_team(
        self,
        theme_name: str,
        team: List[str],
        force: bool = False
    ) -> Dict[str, bool]:
        """Apply theme to all team members' personality files.

        Creates SOUL.md (voice/personality) and IDENTITY.md + ROLE.md
        (identity/relationships + capabilities/constraints).

        Args:
            theme_name: Name of theme to apply (e.g., 'executive_suite')
            team: List of bot names in team
            force: If True, overwrite existing files

        Returns:
            Dict mapping bot_name -> success (bool)
        """
        results = {}

        for bot_name in team:
            try:
                # Apply SOUL.md (voice and personality)
                soul_success = self.apply_theme_to_bot(
                    bot_name,
                    theme_name,
                    force=force
                )

                # Apply IDENTITY.md + ROLE.md
                # (identity includes both relationships AND role/capabilities)
                identity_success = self.apply_identity_to_bot(
                    bot_name,
                    theme=theme_name,
                    force=force
                )

                # Both should succeed for overall success
                results[bot_name] = soul_success and identity_success
            except Exception as e:
                logger.error(f"Failed to apply theme to {bot_name}: {e}")
                results[bot_name] = False

        return results

    def apply_theme_to_bot(
        self,
        bot_name: str,
        theme_name: str,
        force: bool = False
    ) -> bool:
        """Update a specific bot's SOUL.md with theme personality.

        Args:
            bot_name: Name of the bot
            theme_name: Name of theme to apply (e.g., 'executive_suite')
            force: If True, overwrite existing file

        Returns:
            True if successful, False otherwise
        """
        soul_dir = self.bots_dir / bot_name
        soul_dir.mkdir(parents=True, exist_ok=True)

        soul_file = soul_dir / "SOUL.md"

        # Don't overwrite existing files unless forced
        if soul_file.exists() and not force:
            return False

        # Load SOUL.md from template (consistent with IDENTITY.md and ROLE.md)
        from nanofolks.templates import get_soul_template_for_bot
        content = get_soul_template_for_bot(bot_name, theme=theme_name)
        
        if content:
            soul_file.write_text(content, encoding="utf-8")
            return True
        else:
            return False

    def get_bot_soul(self, bot_name: str) -> Optional[str]:
        """Load a bot's SOUL.md content.

        Loading hierarchy:
        1. Workspace bot-specific: /bots/{bot_name}/SOUL.md
        2. Template from detected theme: /templates/soul/{theme}/{bot_name}_SOUL.md
        3. Returns None if none found

        Args:
            bot_name: Name of the bot

        Returns:
            SOUL.md content or None if not found
        """
        # 1. Check workspace bot-specific first
        soul_file = self.bots_dir / bot_name / "SOUL.md"
        if soul_file.exists():
            return soul_file.read_text(encoding="utf-8")

        # 2. Check template directories for themes
        template_soul = self._load_soul_from_templates(bot_name)
        if template_soul:
            return template_soul

        return None

    def get_or_create_soul(
        self,
        bot_name: str,
        default_content: Optional[str] = None
    ) -> str:
        """Get bot soul, creating with default if not found.

        Args:
            bot_name: Name of the bot
            default_content: Default content if file doesn't exist

        Returns:
            SOUL.md content
        """
        content = self.get_bot_soul(bot_name)

        if content is not None:
            return content

        if default_content:
            return default_content

        return self._get_default_soul(bot_name)

    def _load_soul_from_templates(self, bot_name: str) -> Optional[str]:
        """Load SOUL.md from template directories.

        Tries to find SOUL templates from installed themes.

        Args:
            bot_name: Name of the bot

        Returns:
            SOUL.md content from template or None if not found
        """
        try:
            from nanofolks.templates import get_soul_template_for_bot
            return get_soul_template_for_bot(bot_name)
        except (ImportError, Exception):
            return None

    def _get_default_soul(self, bot_name: str) -> str:
        """Get default soul for bot without theme applied.

        Args:
            bot_name: Name of the bot

        Returns:
            Default SOUL.md content
        """
        return f"""# Soul: {bot_name.title()}

👤 **{bot_name.title()}**

I am the {bot_name.title()}, part of the collaborative team.

## Role & Purpose

I contribute to team objectives.

## Communication Style

Professional and collaborative.

---
*Default soul - apply a theme for personality*
"""

    def agents_exists(self, bot_name: str) -> bool:
        """Check if a bot has an AGENTS.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if AGENTS.md exists
        """
        agents_file = self.bots_dir / bot_name / "AGENTS.md"
        return agents_file.exists()

    def apply_agents_to_team(self, team: List[str]) -> Dict[str, bool]:
        """Apply AGENTS.md templates to all team members.

        Args:
            team: List of bot names in team

        Returns:
            Dict mapping bot_name -> success (bool)
        """
        results = {}

        for bot_name in team:
            try:
                success = self.apply_agents_to_bot(bot_name)
                results[bot_name] = success
            except Exception:
                results[bot_name] = False

        return results

    def apply_agents_to_bot(self, bot_name: str, force: bool = False) -> bool:
        """Create a bot's AGENTS.md from template.

        Args:
            bot_name: Name of the bot
            force: If True, overwrite existing file

        Returns:
            True if successful, False otherwise
        """
        agents_dir = self.bots_dir / bot_name
        agents_dir.mkdir(parents=True, exist_ok=True)

        agents_file = agents_dir / "AGENTS.md"

        if agents_file.exists() and not force:
            return False

        from nanofolks.templates import get_agents_template
        template = get_agents_template(bot_name)
        if not template:
            return False

        agents_file.write_text(template, encoding="utf-8")
        return True

    def apply_identity_to_team(
        self,
        team: List[str],
        theme: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, bool]:
        """Apply IDENTITY.md and ROLE.md templates to all team members.

        Creates both identity (relationships, personality) and role (capabilities,
        constraints) files for each bot.

        Args:
            team: List of bot names in team
            theme: Optional theme name. If provided, applies identity from that theme
            force: If True, overwrite existing files

        Returns:
            Dict mapping bot_name -> success (bool)
        """
        results = {}

        for bot_name in team:
            try:
                success = self.apply_identity_to_bot(bot_name, theme=theme, force=force)
                results[bot_name] = success
            except Exception:
                results[bot_name] = False

        return results

    def apply_identity_to_bot(self, bot_name: str, theme: Optional[str] = None, force: bool = False) -> bool:
        """Create a bot's IDENTITY.md and ROLE.md from templates.

        Creates both identity (relationships, personality) and role (capabilities, constraints)
        files together since they define who the bot is and what they can do.

        Args:
            bot_name: Name of the bot
            theme: Optional theme name. If provided, loads identity from that specific theme
            force: If True, overwrite existing files

        Returns:
            True if both files created successfully, False otherwise
        """
        bot_dir = self.bots_dir / bot_name
        bot_dir.mkdir(parents=True, exist_ok=True)

        # Create IDENTITY.md
        identity_file = bot_dir / "IDENTITY.md"
        identity_success = True

        if not identity_file.exists() or force:
            from nanofolks.templates import get_identity_template_for_bot
            identity_template = get_identity_template_for_bot(bot_name, theme=theme)

            if identity_template:
                identity_file.write_text(identity_template, encoding="utf-8")
                identity_success = True
            else:
                identity_success = False

        # Create ROLE.md (always from default templates, not theme-specific)
        role_file = bot_dir / "ROLE.md"
        role_success = True

        if not role_file.exists() or force:
            from nanofolks.templates import get_role_template_for_bot
            role_template = get_role_template_for_bot(bot_name)

            if role_template:
                role_file.write_text(role_template, encoding="utf-8")
                role_success = True
            else:
                role_success = False

        return identity_success and role_success

    def identity_exists(self, bot_name: str) -> bool:
        """Check if a bot has an IDENTITY.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if IDENTITY.md exists
        """
        identity_file = self.bots_dir / bot_name / "IDENTITY.md"
        return identity_file.exists()

    def role_exists(self, bot_name: str) -> bool:
        """Check if a bot has a ROLE.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if ROLE.md exists
        """
        role_file = self.bots_dir / bot_name / "ROLE.md"
        return role_file.exists()
