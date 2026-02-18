"""Manage personality files for all team members in multi-agent system."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from loguru import logger
from nanofolks.teams import BotTeamProfile, Team

if TYPE_CHECKING:
    from nanofolks.teams.theme import Theme


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

    # Role descriptions for each bot type
    ROLE_DESCRIPTIONS = {
        "leader": (
            "I lead the team, make strategic decisions, and ensure "
            "coordination between team members. I prioritize alignment "
            "and overall mission success."
        ),
        "researcher": (
            "I gather and analyze information, verify claims, and provide "
            "evidence-based insights. I help the team understand problems "
            "deeply before solutions are attempted."
        ),
        "coder": (
            "I implement technical solutions and turn ideas into working "
            "code. I focus on reliability, maintainability, and pragmatic "
            "problem-solving."
        ),
        "social": (
            "I engage with users, understand their needs, and maintain "
            "positive relationships. I bridge gaps between technical work "
            "and human needs."
        ),
        "creative": (
            "I explore novel ideas, challenge assumptions, and propose "
            "innovative solutions. I think beyond conventional boundaries."
        ),
        "auditor": (
            "I ensure quality, validate solutions, and identify risks. "
            "I maintain standards and prevent problems from reaching users."
        ),
    }

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
        theme: Team,
        team: List[str],
        force: bool = False
    ) -> Dict[str, bool]:
        """Apply theme to all team members' personality files.

        Creates SOUL.md (voice/personality) and IDENTITY.md + ROLE.md
        (identity/relationships + capabilities/constraints).

        Args:
            theme: Theme object to apply
            team: List of bot names in team
            force: If True, overwrite existing files

        Returns:
            Dict mapping bot_name -> success (bool)
        """
        results = {}

        for bot_name in team:
            try:
                bot_theming = theme.get_bot_theming(bot_name)
                if bot_theming:
                    # Apply SOUL.md (voice and personality)
                    soul_success = self.apply_theme_to_bot(
                        bot_name,
                        bot_theming,
                        theme,
                        force=force
                    )

                    # Apply IDENTITY.md + ROLE.md
                    # (identity includes both relationships AND role/capabilities)
                    identity_success = self.apply_identity_to_bot(
                        bot_name,
                        theme=theme.name.value,
                        force=force
                    )

                    # Both should succeed for overall success
                    results[bot_name] = soul_success and identity_success
                else:
                    results[bot_name] = False
            except Exception as e:
                logger.error(f"Failed to apply theme to {bot_name}: {e}")
                results[bot_name] = False

        return results

    def apply_theme_to_bot(
        self,
        bot_name: str,
        theming: BotTeamProfile,
        theme: Team,
        force: bool = False
    ) -> bool:
        """Update a specific bot's SOUL.md with theme personality.

        Args:
            bot_name: Name of the bot
            theming: Bot theming from theme
            theme: Theme object (for context)
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

        content = self._generate_soul_content(bot_name, theming, theme)
        soul_file.write_text(content, encoding="utf-8")

        return True

    def _generate_soul_content(
        self,
        bot_name: str,
        theming: BotTeamProfile,
        theme: Theme
    ) -> str:
        """Generate SOUL.md content from theme.

        Args:
            bot_name: Name of the bot
            theming: Bot theming from theme
            theme: Theme object

        Returns:
            Formatted SOUL.md content
        """
        role_desc = self._get_role_description(bot_name)
        timestamp = datetime.now().isoformat()

        return f"""# Soul: {bot_name.title()}

{theming.emoji} **{theming.title}**

I am the {theming.title}, part of the collaborative team.

## Role & Purpose

{role_desc}

## Personality Traits

{theming.personality}

## Communication Style

{theming.voice_directive}

## Greeting

> {theming.greeting}

## Current Theme

- **Theme**: {theme.name.value}
- **Title**: {theming.title}
- **Emoji**: {theming.emoji}
- **Updated**: {timestamp}

## Team Context

This SOUL.md is generated by the theme system. Each bot has a distinct personality that changes with themes.

Custom edits to this file persist until the theme is reapplied with `force=True`.

---
*Generated by SoulManager - Part of multi-agent orchestration*
"""

    def _get_role_description(self, bot_name: str) -> str:
        """Get role-specific description for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            Role description
        """
        return self.ROLE_DESCRIPTIONS.get(
            bot_name,
            "I contribute to team objectives."
        )

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
        default_content: str = None
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

Default personality - no theme applied.

Apply a theme using the onboarding wizard to customize my personality.

## Role

I am the {bot_name} specialist on the team.

---
*No theme applied - run onboarding to customize.*
"""

    def list_bots_with_souls(self) -> List[str]:
        """List all bots that have SOUL.md files.

        Returns:
            List of bot names
        """
        bots = []

        if self.bots_dir.exists():
            for bot_dir in self.bots_dir.iterdir():
                if bot_dir.is_dir():
                    soul_file = bot_dir / "SOUL.md"
                    if soul_file.exists():
                        bots.append(bot_dir.name)

        return sorted(bots)

    def delete_bot_soul(self, bot_name: str) -> bool:
        """Delete a bot's SOUL.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if deleted, False if not found
        """
        soul_file = self.bots_dir / bot_name / "SOUL.md"

        if soul_file.exists():
            soul_file.unlink()

            # Remove directory if empty
            bot_dir = soul_file.parent
            try:
                bot_dir.rmdir()
            except OSError:
                pass  # Directory not empty

            return True

        return False

    def soul_exists(self, bot_name: str) -> bool:
        """Check if a bot has a SOUL.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if SOUL.md exists, False otherwise
        """
        soul_file = self.bots_dir / bot_name / "SOUL.md"
        return soul_file.exists()

    def get_team_summary(self, team: List[str]) -> Dict[str, dict]:
        """Get personality summary for a team.

        Args:
            team: List of bot names

        Returns:
            Dict mapping bot_name -> {title, emoji, theme, etc}
        """
        summary = {}

        for bot_name in team:
            soul_content = self.get_bot_soul(bot_name)

            if soul_content:
                # Parse soul content to extract key fields
                title = self._extract_title(soul_content)
                emoji = self._extract_emoji(soul_content)
                theme = self._extract_theme(soul_content)

                summary[bot_name] = {
                    "title": title,
                    "emoji": emoji,
                    "theme": theme,
                    "has_soul": True,
                }
            else:
                summary[bot_name] = {
                    "title": None,
                    "emoji": None,
                    "theme": None,
                    "has_soul": False,
                }

        return summary

    def _extract_title(self, soul_content: str) -> Optional[str]:
        """Extract title from SOUL.md content.

        Args:
            soul_content: SOUL.md content

        Returns:
            Title or None
        """
        import re
        match = re.search(r'\*\*(.+?)\*\*', soul_content)
        return match.group(1) if match else None

    def _extract_emoji(self, soul_content: str) -> Optional[str]:
        """Extract emoji from SOUL.md content.

        Args:
            soul_content: SOUL.md content

        Returns:
            Emoji or None
        """
        import re
        match = re.search(r'([\U0001F300-\U0001F9FF])', soul_content)
        return match.group(1) if match else None

    # ==================================================================
    # AGENTS.md Management
    # ==================================================================

    def get_bot_agents(self, bot_name: str) -> Optional[str]:
        """Load a bot's AGENTS.md content.

        Args:
            bot_name: Name of the bot

        Returns:
            AGENTS.md content or None if not found
        """
        agents_file = self.bots_dir / bot_name / "AGENTS.md"

        if agents_file.exists():
            return agents_file.read_text(encoding="utf-8")

        return None

    def apply_agents_to_team(self, team: List[str], force: bool = False) -> Dict[str, bool]:
        """Apply AGENTS.md templates to all team members.

        Args:
            team: List of bot names in team
            force: If True, overwrite existing files

        Returns:
            Dict mapping bot_name -> success (bool)
        """
        results = {}

        for bot_name in team:
            try:
                success = self.apply_agents_to_bot(bot_name, force=force)
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

        template = get_agents_templates().get(bot_name)
        if not template:
            return False

        agents_file.write_text(template, encoding="utf-8")
        return True

    def apply_identity_to_team(self, team: List[str], theme: Optional[str] = None, force: bool = False) -> Dict[str, bool]:
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

    def agents_exists(self, bot_name: str) -> bool:
        """Check if a bot has an AGENTS.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            True if AGENTS.md exists, False otherwise
        """
        agents_file = self.bots_dir / bot_name / "AGENTS.md"
        return agents_file.exists()

    def get_or_create_agents(self, bot_name: str) -> str:
        """Get bot agents, creating with default template if not found.

        Args:
            bot_name: Name of the bot

        Returns:
            AGENTS.md content
        """
        content = self.get_bot_agents(bot_name)

        if content is not None:
            return content

        return get_agents_templates().get(bot_name, "")

    def _extract_theme(self, soul_content: str) -> Optional[str]:
        """Extract theme name from SOUL.md content.

        Args:
            soul_content: SOUL.md content

        Returns:
            Theme name or None
        """
        import re
        match = re.search(r'\*\*Theme\*\*:\s*(.+?)(?:\n|$)', soul_content)
        return match.group(1) if match else None
