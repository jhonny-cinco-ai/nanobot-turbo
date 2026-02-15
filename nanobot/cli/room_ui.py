"""Room and team UI components for enhanced CLI experience.

Provides:
- TeamRoster - Display available bots
- RoomList - Display available rooms
- StatusBar - Current room/team status
- AI-assisted room creation
"""

from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
import json

console = Console()


class TeamRoster:
    """Manages team member display."""
    
    # All available bots with emoji and role
    ALL_BOTS = [
        ("🧠", "researcher", "Research", "Navigator"),
        ("💻", "coder", "Code", "Gunner"),
        ("🎨", "creative", "Design", "Artist"),
        ("🤝", "social", "Community", "Lookout"),
        ("✅", "auditor", "Quality", "Quartermaster"),
        ("👑", "leader", "Leader", "Coordinator"),
    ]
    
    def __init__(self):
        """Initialize team roster."""
        self.bots_dict = {name: (emoji, role, title) for emoji, name, role, title in self.ALL_BOTS}
    
    def render(self, current_room_participants: List[str], compact: bool = False) -> str:
        """
        Render team roster.
        
        Args:
            current_room_participants: List of bots in current room
            compact: If True, only show in-room bots
            
        Returns:
            Formatted team display string
        """
        output = "[bold cyan]TEAM[/bold cyan]\n"
        
        if compact:
            # Show only bots in current room
            for emoji, name, role, title in self.ALL_BOTS:
                if name in current_room_participants:
                    output += f"  {emoji} [green]{name:12}[/green] {role}\n"
        else:
            # Show all bots with indicator if in room
            for emoji, name, role, title in self.ALL_BOTS:
                if name in current_room_participants:
                    output += f"→ {emoji} [green]{name:12}[/green] {role}\n"
                else:
                    output += f"  {emoji} {name:12} {role}\n"
        
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
        for emoji, name, _, _ in self.ALL_BOTS:
            if name in participants:
                emojis.append(emoji)
        
        return " ".join(emojis)
    
    def get_bot_info(self, bot_name: str) -> Optional[Dict[str, str]]:
        """Get information about a bot.
        
        Args:
            bot_name: Name of bot
            
        Returns:
            Dict with emoji, role, title or None
        """
        if bot_name in self.bots_dict:
            emoji, role, title = self.bots_dict[bot_name]
            return {
                "emoji": emoji,
                "name": bot_name,
                "role": role,
                "title": title
            }
        return None


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
        output = "[bold cyan]ROOMS[/bold cyan]\n"
        
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
    
    def render(self, room_id: str, participants_count: int, bot_emojis: str = "") -> str:
        """
        Render status bar.
        
        Args:
            room_id: Current room ID
            participants_count: Number of bots in room
            bot_emojis: Optional emoji string of team members
            
        Returns:
            Formatted status bar
        """
        status = f"[dim]Room:[/dim] [bold cyan]#{room_id}[/bold cyan]"
        status += f" • [dim]Team:[/dim] [green]{participants_count}[/green]"
        
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
