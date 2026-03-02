"""Template parser for extracting bot and team metadata from markdown files."""

import re
from pathlib import Path
from typing import Optional

from nanofolks.templates import SOUL_TEMPLATES_DIR, IDENTITY_TEMPLATES_DIR


class BotMetadata:
    """Metadata extracted from bot template files."""

    def __init__(
        self,
        bot_name: str,
        bot_title: str,
        name: str,
        emoji: str,
        personality: str = "",
        greeting: str = "",
        voice_directive: str = "",
    ):
        self.bot_name = bot_name
        self.bot_title = bot_title
        self.name = name
        self.emoji = emoji
        self.personality = personality
        self.greeting = greeting
        self.voice_directive = voice_directive

    def to_dict(self) -> dict:
        """Convert to dictionary for compatibility."""
        return {
            "bot_title": self.bot_title,
            "bot_name": self.name,
            "personality": self.personality,
            "greeting": self.greeting,
            "voice": self.voice_directive,
            "emoji": self.emoji,
        }


def parse_soul_file(content: str) -> dict:
    """Parse SOUL.md file and extract metadata.

    Args:
        content: Content of SOUL.md file

    Returns:
        Dictionary with extracted fields (emoji, title, name, personality, etc.)
    """
    metadata = {}

    # Extract emoji and title from first header line
    # Pattern: 📈 **Chief Marketing Officer (CMO)**
    header_match = re.search(r"^(.)\s*\*\*(.+?)\s*\((.+?)\)\*\*", content, re.MULTILINE)
    if header_match:
        metadata["emoji"] = header_match.group(1)
        metadata["title"] = header_match.group(2)
        metadata["short_title"] = header_match.group(3)

    # Extract name from "I am [Name], the [Title]" pattern
    # Pattern: I am Catherine, the CMO
    name_match = re.search(r"I am ([^,]+), the ([^.]+)", content)
    if name_match:
        metadata["name"] = name_match.group(1).strip()

    # Extract personality from "## Vibe" or "## Personality Traits" section
    vibe_match = re.search(r"##\s*Vibe\s*\n+(.+?)(?=\n##|\Z)", content, re.DOTALL)
    if vibe_match:
        metadata["personality"] = vibe_match.group(1).strip().split("\n")[0]

    personality_match = re.search(
        r"##\s*Personality Traits\s*\n+(.+?)(?=\n##|\Z)", content, re.DOTALL
    )
    if personality_match and "personality" not in metadata:
        metadata["personality"] = personality_match.group(1).strip()

    # Extract greeting from blockquote after "## Greeting"
    greeting_match = re.search(r"##\s*Greeting\s*\n+>\s*(.+?)(?=\n##|\Z)", content, re.DOTALL)
    if greeting_match:
        metadata["greeting"] = greeting_match.group(1).strip().replace("\n", " ")

    # Extract voice directive from "## Communication Style" or "## Vibe"
    voice_match = re.search(r"##\s*Communication Style\s*\n+(.+?)(?=\n##|\Z)", content, re.DOTALL)
    if voice_match:
        metadata["voice_directive"] = voice_match.group(1).strip()

    return metadata


def parse_identity_file(content: str) -> dict:
    """Parse IDENTITY.md file and extract metadata.

    Args:
        content: Content of IDENTITY.md file

    Returns:
        Dictionary with extracted fields (name, title, emoji, vibe, etc.)
    """
    metadata = {}

    # Extract Name field
    name_match = re.search(r"\*\*Name:\*\*\s*(.+)", content)
    if name_match:
        metadata["name"] = name_match.group(1).strip()

    # Extract Creature/Title field
    creature_match = re.search(r"\*\*Creature:\*\*\s*(.+)", content)
    if creature_match:
        metadata["title"] = creature_match.group(1).strip()
        # Also extract short title from parentheses
        short_match = re.search(r"\((.+?)\)", metadata["title"])
        if short_match:
            metadata["short_title"] = short_match.group(1)

    # Extract Emoji field
    emoji_match = re.search(r"\*\*Emoji:\*\*\s*(.)", content)
    if emoji_match:
        metadata["emoji"] = emoji_match.group(1)

    # Extract Vibe field
    vibe_match = re.search(r"\*\*Vibe:\*\*\s*(.+)", content)
    if vibe_match:
        metadata["personality"] = vibe_match.group(1).strip()

    return metadata


def get_bot_metadata(bot_name: str, team_name: str) -> Optional[BotMetadata]:
    """Get metadata for a bot in a team by parsing template files.

    Tries to extract from both SOUL.md and IDENTITY.md, combining the data.

    Args:
        bot_name: Bot role name (leader, researcher, coder, social, creative, auditor)
        team_name: Team name (pirate_team, executive_suite, etc.)

    Returns:
        BotMetadata object or None if templates not found
    """
    # Try to load SOUL.md
    soul_file = SOUL_TEMPLATES_DIR / team_name / f"{bot_name}_SOUL.md"
    soul_metadata = {}
    if soul_file.exists():
        soul_content = soul_file.read_text(encoding="utf-8")
        soul_metadata = parse_soul_file(soul_content)

    # Try to load IDENTITY.md
    identity_file = IDENTITY_TEMPLATES_DIR / team_name / f"{bot_name}_IDENTITY.md"
    identity_metadata = {}
    if identity_file.exists():
        identity_content = identity_file.read_text(encoding="utf-8")
        identity_metadata = parse_identity_file(identity_content)

    # Merge metadata, preferring SOUL.md for most fields
    metadata = {**identity_metadata, **soul_metadata}
    # But IDENTITY.md Name field should always take precedence for bot personality name
    if identity_metadata.get("name"):
        metadata["name"] = identity_metadata["name"]

    if not metadata:
        return None

    return BotMetadata(
        bot_name=bot_name,
        bot_title=metadata.get("title", metadata.get("short_title", bot_name)),
        name=metadata.get("name", bot_name),
        emoji=metadata.get("emoji", "👤"),
        personality=metadata.get("personality", ""),
        greeting=metadata.get("greeting", ""),
        voice_directive=metadata.get("voice_directive", ""),
    )


def parse_team_description(team_name: str) -> str:
    """Parse team description from TEAM.md or any bot's SOUL.md file.

    Args:
        team_name: Team name

    Returns:
        Team description or empty string
    """
    # Priority 1: Check for dedicated TEAM.md file (team-oriented description)
    team_file = SOUL_TEMPLATES_DIR / team_name / "TEAM.md"
    if team_file.exists():
        return team_file.read_text(encoding="utf-8").strip()

    # Priority 2: Fallback to leader's SOUL.md (legacy/default)
    soul_file = SOUL_TEMPLATES_DIR / team_name / "leader_SOUL.md"
    if soul_file.exists():
        content = soul_file.read_text(encoding="utf-8")
        # Look for team description in "Role & Purpose" section
        role_match = re.search(r"##\s*Role & Purpose\s*\n+(.+?)(?=\n##|\Z)", content, re.DOTALL)
        if role_match:
            return role_match.group(1).strip().split("\n")[0]

    return ""
