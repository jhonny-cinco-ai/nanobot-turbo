"""Room and team UI components for enhanced CLI experience.

Provides:
- TeamRoster - Display available bots
- RoomList - Display available rooms
- StatusBar - Current room/team status
- AI-assisted room creation
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

console = Console()
ACCENT_COLOR = "bright_magenta"


class TeamRoster:
    """Manages team member display."""

    BOT_ROLES = [
        ("leader", "Leader"),
        ("researcher", "Research"),
        ("coder", "Code"),
        ("creative", "Design"),
        ("social", "Community"),
        ("auditor", "Quality"),
    ]

    def __init__(self, workspace_path: Optional[Path] = None, team_name: Optional[str] = None):
        """Initialize team roster."""
        self.workspace_path = Path(workspace_path) if workspace_path else None
        self.team_name = team_name or self._load_team_name()

    def _load_team_name(self) -> str:
        try:
            from nanofolks.bots.appearance_config import get_appearance_config

            appearance = get_appearance_config()
            team_manager = appearance.team_manager
            if team_manager and team_manager.get_current_team_name():
                return team_manager.get_current_team_name() or "pirate_crew"
        except Exception:
            pass

        return "pirate_crew"

    def _get_profile(self, bot_role: str):
        try:
            from nanofolks.teams import get_bot_team_profile

            return get_bot_team_profile(
                bot_role,
                self.team_name,
                workspace_path=self.workspace_path,
            )
        except Exception:
            return None

    def render(self, current_room_participants: List[str], compact: bool = False) -> str:
        """
        Render team roster.

        Args:
            current_room_participants: List of bots in current room
            compact: If True, only show in-room bots

        Returns:
            Formatted team display string
        """
        output = f"[bold {ACCENT_COLOR}]TEAM[/bold {ACCENT_COLOR}]\n"

        for bot_role, role_label in self.BOT_ROLES:
            profile = self._get_profile(bot_role)
            bot_name = profile.bot_name if profile else bot_role
            bot_title = profile.bot_title if profile else role_label
            emoji = profile.emoji if profile else "•"
            in_room = bot_role in current_room_participants

            if compact and not in_room:
                continue

            marker = "→ " if in_room and not compact else "  "
            name_style = "[green]" if in_room else ""
            end_style = "[/green]" if in_room else ""

            output += (
                f"{marker}{emoji} {name_style}{bot_name:12}{end_style} "
                f"({bot_title}) [dim]@{bot_role}[/dim]\n"
            )

        return output

    def render_compact_inline(self, participants: List[str]) -> str:
        """
        Render team inline for status bar.

        Args:
            participants: List of bots

        Returns:
            Inline team display (emoji + count)
        """
        emojis = []
        for bot_role, _ in self.BOT_ROLES:
            if bot_role in participants:
                profile = self._get_profile(bot_role)
                emojis.append(profile.emoji if profile else "•")

        return " ".join(emojis)

    def get_bot_info(self, bot_name: str) -> Optional[Dict[str, str]]:
        """Get information about a bot.

        Args:
            bot_name: Name of bot

        Returns:
            Dict with emoji, role, title or None
        """
        profile = self._get_profile(bot_name)
        if not profile:
            return None

        role_label = dict(self.BOT_ROLES).get(bot_name, bot_name.title())

        return {
            "emoji": profile.emoji,
            "name": profile.bot_name,
            "role": role_label,
            "title": profile.bot_title,
        }


class RoomList:
    """Manages room list display."""

    def __init__(self):
        """Initialize room list."""
        pass

    def render(self, rooms: List[Dict[str, Any]], current_room_id: str) -> str:
        """
        Render list of rooms.

        Args:
            rooms: List of room dicts from RoomManager.list_rooms()
            current_room_id: Currently selected room

        Returns:
            Formatted room list string
        """
        output = f"[bold {ACCENT_COLOR}]ROOMS[/bold {ACCENT_COLOR}]\n"

        for room in rooms:
            room_id = room['id']
            room_type = room['type']
            participant_count = room['participant_count']
            is_current = room_id == current_room_id

            # Get icon for room type
            icon = self._get_room_icon(room_type)

            # Format line
            marker = "→ " if is_current else "  "

            if is_current:
                line = f"{marker}[bold green]{icon} {room_id:15}[/bold green] ({participant_count})\n"
            else:
                line = f"{marker}{icon} {room_id:15} ({participant_count})\n"

            output += line

        return output

    def render_table(self, rooms: List[Dict[str, Any]], current_room_id: str) -> Table:
        """
        Render rooms as a table.

        Args:
            rooms: List of room dicts
            current_room_id: Currently selected room

        Returns:
            Rich Table object
        """
        table = Table(title="Available Rooms", box=None)
        table.add_column("Room", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("Bots", style="green")

        for room in rooms:
            icon = self._get_room_icon(room['type'])
            room_id = f"#{room['id']}"

            if room['id'] == current_room_id:
                room_id = f"[bold green]{room_id}[/bold green] →"

            table.add_row(
                room_id,
                f"{icon} {room['type']}",
                str(room['participant_count'])
            )

        return table

    @staticmethod
    def _get_room_icon(room_type: str) -> str:
        """Get emoji icon for room type."""
        icons = {
            "open": "🌐",
            "project": "📁",
            "direct": "💬",
            "coordination": "🤖"
        }
        return icons.get(room_type, "📌")


class StatusBar:
    """Top status bar showing current room and team."""

    def render(
        self,
        room_id: str,
        participants_count: int,
        bot_emojis: str = "",
        context_usage: str | None = None,
    ) -> str:
        """
        Render status bar.

        Args:
            room_id: Current room ID
            participants_count: Number of bots in room
            bot_emojis: Optional emoji string of team members

        Returns:
            Formatted status bar
        """
        status = f"[dim]Room:[/dim] [bold {ACCENT_COLOR}]#{room_id}[/bold {ACCENT_COLOR}]"
        status += f" • [dim]Team:[/dim] [{ACCENT_COLOR}]{participants_count}[/{ACCENT_COLOR}]"
        if context_usage:
            status += f" • [dim]Context:[/dim] [{ACCENT_COLOR}]{context_usage}[/{ACCENT_COLOR}]"

        if bot_emojis:
            status += f" {bot_emojis}"

        return status


class RoomCreationIntent:
    """Represents the AI's intent to create a room."""

    def __init__(
        self,
        should_create: bool = False,
        room_name: str = "",
        room_type: str = "project",
        summary: str = "",
        recommended_bots: List[Dict[str, str]] = None
    ):
        """Initialize room creation intent.

        Args:
            should_create: Whether to create a room
            room_name: Name of room to create
            room_type: Type of room (project, general, direct, coordination)
            summary: Summary of the project/room
            recommended_bots: List of {"name": "bot", "reason": "why"} dicts
        """
        self.should_create = should_create
        self.room_name = room_name
        self.room_type = room_type
        self.summary = summary
        self.recommended_bots = recommended_bots or []

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoomCreationIntent":
        """Create intent from dictionary (from LLM response).

        Args:
            data: Dictionary from LLM response

        Returns:
            RoomCreationIntent instance
        """
        return cls(
            should_create=data.get("should_create_room", False),
            room_name=data.get("room_name", ""),
            room_type=data.get("room_type", "project"),
            summary=data.get("summary", ""),
            recommended_bots=data.get("recommended_bots", [])
        )

    def display_recommendation(self) -> str:
        """Display the recommendation to user.

        Returns:
            Formatted recommendation text
        """
        if not self.should_create:
            return ""

        output = "[dim]\n🔍 Analyzing task requirements...\n[/dim]\n"
        output += f"[dim]{self.summary}[/dim]\n\n"
        output += "[bold]Recommended team:[/bold]\n"

        roster = TeamRoster()
        for bot in self.recommended_bots:
            bot_name = bot["name"]
            reason = bot["reason"]
            info = roster.get_bot_info(bot_name)

            if info:
                output += f"  {info['emoji']} @{bot_name:12} ({reason})\n"

        return output

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "should_create_room": self.should_create,
            "room_name": self.room_name,
            "room_type": self.room_type,
            "summary": self.summary,
            "recommended_bots": self.recommended_bots
        }


def parse_llm_intent_response(response_text: str) -> RoomCreationIntent:
    """Parse LLM response for room creation intent.

    Args:
        response_text: LLM response containing JSON

    Returns:
        RoomCreationIntent instance

    Raises:
        ValueError: If JSON cannot be parsed
    """
    try:
        # Extract JSON from response
        start = response_text.find('{')
        end = response_text.rfind('}') + 1

        if start == -1 or end == 0:
            raise ValueError("No JSON found in response")

        json_str = response_text[start:end]
        data = json.loads(json_str)

        return RoomCreationIntent.from_dict(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse LLM response: {e}")


def render_dual_panel(left_content: str, right_content: str) -> None:
    """Render two panels side by side.

    Args:
        left_content: Content for left panel
        right_content: Content for right panel
    """
    # Simple implementation without Layout (compatible with more terminals)
    console.print(left_content)
    console.print(right_content)


def render_sidebar_layout(chat_area: str, sidebar: str) -> None:
    """Render chat area with sidebar.

    Uses simple printing since not all terminals support Layout.

    Args:
        chat_area: Main chat content
        sidebar: Sidebar content (team & rooms)
    """
    # This is a simplified version
    # For true side-by-side, would need to use Rich Layout
    # but that requires more complex terminal handling

    console.print(sidebar)  # Show sidebar above chat
    console.print(chat_area)  # Show chat


# Export public API
__all__ = [
    "TeamRoster",
    "RoomList",
    "StatusBar",
    "RoomCreationIntent",
    "parse_llm_intent_response",
    "render_dual_panel",
    "render_sidebar_layout",
]
