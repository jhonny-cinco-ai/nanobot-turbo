"""Relationship parser for extracting bot relationships from IDENTITY.md.

This module parses relationship definitions from bot identity files and
enables affinity-aware multi-bot interactions.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class BotRelationship:
    """Relationship between two bots."""
    target_bot: str
    affinity: float  # 0.0 to 1.0
    description: str
    interaction_style: str  # "agreeable", "challenging", "neutral"


class RelationshipParser:
    """Parse relationship sections from IDENTITY.md files or infer from teams."""

    def __init__(self, workspace: Path):
        """Initialize RelationshipParser.

        Args:
            workspace: Workspace path for loading IDENTITY.md files
        """
        self.workspace = Path(workspace)
        self._relationship_cache: Dict[str, List[BotRelationship]] = {}

    def get_bot_relationships(self, bot_name: str) -> List[BotRelationship]:
        """Get relationships for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            List of BotRelationship objects
        """
        if bot_name in self._relationship_cache:
            return self._relationship_cache[bot_name]

        relationships = self._load_from_identity_file(bot_name)

        if not relationships:
            relationships = self._infer_from_team(bot_name)

        self._relationship_cache[bot_name] = relationships
        return relationships

    def _load_from_identity_file(self, bot_name: str) -> List[BotRelationship]:
        """Load relationships from IDENTITY.md file.

        Args:
            bot_name: Name of the bot

        Returns:
            List of BotRelationship objects
        """
        identity_path = self.workspace / "bots" / bot_name / "IDENTITY.md"

        if not identity_path.exists():
            return []

        try:
            with open(identity_path, 'r') as f:
                content = f.read()

            return self.parse_relationships(content, bot_name)
        except Exception as e:
            logger.warning(f"Failed to parse IDENTITY.md for {bot_name}: {e}")
            return []

    def parse_relationships(self, identity_content: str, bot_name: str) -> List[BotRelationship]:
        """Extract relationships from IDENTITY.md content.

        Args:
            identity_content: Content of IDENTITY.md
            bot_name: Name of the bot whose relationships these are

        Returns:
            List of BotRelationship objects
        """
        relationships = []

        # Try different section headers that might contain relationships
        relationship_section = self._extract_section(
            identity_content,
            [
                "## Relationship with the Crew",
                "## Relationships",
                "### Relationships",
                "## Relationships with Others",
                "## Team Relationships",
            ]
        )

        if not relationship_section:
            return relationships

        lines = relationship_section.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                relationship = self._parse_relationship_line(line)
                if relationship:
                    relationships.append(relationship)

        return relationships

    def _extract_section(self, content: str, section_headers: List[str]) -> Optional[str]:
        """Extract a section from markdown content.

        Args:
            content: Full markdown content
            section_headers: Possible section headers to find

        Returns:
            Section content or None
        """
        lines = content.split('\n')

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped in section_headers:
                section_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    if next_line.startswith('#'):
                        break
                    section_lines.append(next_line)
                return '\n'.join(section_lines)

        return None

    def _parse_relationship_line(self, line: str) -> Optional[BotRelationship]:
        """Parse a single relationship line.

        Expected formats:
        - **Navigator (Sparrow):** My trusted first mate...
        - **Captain (Blackbeard):** My captain. Gives good orders.
        - Researcher: High affinity, we agree on most things
        - Creative (low affinity): Sometimes too dreamy
        - Auditor [0.3]: Keeps us honest but can be rigid
        """
        # Remove bullet marker
        line = line.lstrip('-*').strip()

        # Try format: **Role (Name):** Description
        bold_match = re.match(r'\*\*(\w+)\s*\([^)]+\):\*\*\s*(.+)', line)
        if bold_match:
            role_name = bold_match.group(1).lower()
            description = bold_match.group(2).strip()

            # Map role name to bot name
            bot_name_map = {
                'captain': 'leader',
                'navigator': 'researcher',
                'gunner': 'coder',
                'lookout': 'social',
                'artist': 'creative',
                'quartermaster': 'auditor',
                'lead': 'leader',
                'singer': 'leader',
                'guitar': 'researcher',
                'drummer': 'coder',
                'manager': 'social',
                'bassist': 'creative',
                'producer': 'auditor',
            }

            target_bot = bot_name_map.get(role_name, role_name)
            affinity = self._extract_affinity(description)
            interaction_style = self._determine_interaction_style(affinity, description)

            return BotRelationship(
                target_bot=target_bot,
                affinity=affinity,
                description=description,
                interaction_style=interaction_style
            )

        # Try format: BotName: description
        bot_match = re.match(r'^(\w+)\s*[:\[(]', line)
        if not bot_match:
            return None

        target_bot = bot_match.group(1).lower()
        rest = line[len(bot_match.group(0))-1:].strip(':[]')

        # Try to extract affinity score
        affinity = self._extract_affinity(rest)

        # Determine interaction style
        interaction_style = self._determine_interaction_style(affinity, rest)

        # Clean up description
        description = self._clean_description(rest)

        return BotRelationship(
            target_bot=target_bot,
            affinity=affinity,
            description=description,
            interaction_style=interaction_style
        )

    def _extract_affinity(self, text: str) -> float:
        """Extract affinity score from text."""
        score_match = re.search(r'[\[(](0?\.\d+)[\])]', text)
        if score_match:
            return float(score_match.group(1))

        text_lower = text.lower()
        if any(word in text_lower for word in ['high', 'trusted', 'close', 'friend']):
            return 0.8
        elif any(word in text_lower for word in ['medium', 'respect', 'colleague']):
            return 0.5
        elif any(word in text_lower for word in ['low', 'distant', 'challenging', 'disagree']):
            return 0.2

        return 0.5

    def _determine_interaction_style(self, affinity: float, text: str) -> str:
        """Determine interaction style based on affinity and text."""
        text_lower = text.lower()

        if 'challenge' in text_lower or 'disagree' in text_lower:
            return "challenging"
        elif affinity > 0.7:
            return "agreeable"
        elif affinity < 0.4:
            return "distant"
        else:
            return "neutral"

    def _clean_description(self, text: str) -> str:
        """Clean up description text."""
        text = re.sub(r'\s*[\[(]\d*\.?\d+[\])]\s*', ' ', text)
        text = ' '.join(text.split())
        return text.strip()

    def _infer_from_team(self, bot_name: str) -> List[BotRelationship]:
        """Infer relationships from the current team's personality data.

        This provides a fallback when IDENTITY.md doesn't exist.

        Args:
            bot_name: Name of the bot

        Returns:
            List of inferred BotRelationship objects
        """
        from nanofolks.teams import TeamManager
        from nanofolks.templates import get_bot_team_profile

        relationships = []

        try:
            team_manager = TeamManager()
            current_team_name = team_manager.get_current_team_name()

            if not current_team_name:
                return relationships

            bots = ["leader", "researcher", "coder", "social", "creative", "auditor"]
            bots.remove(bot_name)  # Remove self

            for other_bot in bots:
                profile = get_bot_team_profile(other_bot, current_team_name)
                if profile:
                    inferred_affinity = self._infer_affinity_from_profile(
                        bot_name, other_bot, profile
                    )
                    relationships.append(BotRelationship(
                        target_bot=other_bot,
                        affinity=inferred_affinity,
                        description=f"Team member ({profile.get('bot_title', other_bot)})",
                        interaction_style="neutral"
                    ))

        except Exception as e:
            logger.debug(f"Could not infer relationships from team: {e}")

        return relationships

    def _infer_affinity_from_profile(
        self,
        bot_name: str,
        other_bot: str,
        profile
    ) -> float:
        """Infer affinity from bot profile characteristics.

        Args:
            bot_name: Current bot
            other_bot: Other bot
            profile: Bot profile with personality attribute

        Returns:
            Inferred affinity score
        """
        personality = profile.personality.lower()

        positive_indicators = ['agree', 'trust', 'close', 'friend', 'collaborate']
        negative_indicators = ['challenge', 'disagree', 'rival', 'compete']

        if any(indicator in personality for indicator in positive_indicators):
            return 0.7
        elif any(indicator in personality for indicator in negative_indicators):
            return 0.3

        return 0.5

    def clear_cache(self) -> None:
        """Clear the relationship cache."""
        self._relationship_cache.clear()
