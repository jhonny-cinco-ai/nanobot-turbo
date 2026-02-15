"""Room management with default General room.

Automatically creates and manages rooms, including a default
"General" room that exists on first run with Leader ready to go.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from loguru import logger

from nanobot.config.loader import get_data_dir
from nanobot.models.room import Room, RoomType


class RoomManager:
    """Manages all rooms with automatic default creation."""
    
    # Default room that always exists
    DEFAULT_ROOM_ID = "general"
    DEFAULT_ROOM_NAME = "General"
    
    def __init__(self):
        """Initialize room manager."""
        self.config_dir = get_data_dir()
        self.rooms_dir = self.config_dir / "rooms"
        self.rooms_dir.mkdir(parents=True, exist_ok=True)
        
        self._rooms: Dict[str, Room] = {}
        self._load_or_create_default()
    
    def _load_or_create_default(self) -> None:
        """Load existing rooms or create default General room."""
        # Try to load existing rooms
        room_files = list(self.rooms_dir.glob("*.json"))
        
        if room_files:
            # Load all existing rooms
            for room_file in room_files:
                try:
                    room_data = json.loads(room_file.read_text())
                    room = self._room_from_dict(room_data)
                    self._rooms[room.id] = room
                    logger.debug(f"Loaded room: {room.id}")
                except Exception as e:
                    logger.warning(f"Failed to load room {room_file}: {e}")
        
        # Ensure General room exists
        if self.DEFAULT_ROOM_ID not in self._rooms:
            self._create_default_room()
    
    def _create_default_room(self) -> None:
        """Create the default General room with Leader."""
        general = Room(
            id=self.DEFAULT_ROOM_ID,
            type=RoomType.OPEN,
            participants=["nanobot"],  # Only Leader initially
            owner="user",
            created_at=datetime.now(),
        )
        
        self._rooms[self.DEFAULT_ROOM_ID] = general
        self._save_room(general)
        
        logger.info(f"Created default '{self.DEFAULT_ROOM_NAME}' room with Leader")
    
    def _save_room(self, room: Room) -> None:
        """Save room to disk."""
        room_file = self.rooms_dir / f"{room.id}.json"
        room_data = self._room_to_dict(room)
        room_file.write_text(json.dumps(room_data, indent=2, default=str))
    
    def _room_to_dict(self, room: Room) -> dict:
        """Convert room to dictionary."""
        return {
            "id": room.id,
            "type": room.type.value,
            "participants": room.participants,
            "owner": room.owner,
            "created_at": room.created_at.isoformat(),
            "summary": room.summary,
            "auto_archive": room.auto_archive,
            "coordinator_mode": room.coordinator_mode,
        }
    
    def _room_from_dict(self, data: dict) -> Room:
        """Create room from dictionary."""
        return Room(
            id=data["id"],
            type=RoomType(data["type"]),
            participants=data.get("participants", []),
            owner=data.get("owner", "user"),
            created_at=datetime.fromisoformat(data["created_at"]),
            summary=data.get("summary", ""),
            auto_archive=data.get("auto_archive", False),
            coordinator_mode=data.get("coordinator_mode", False),
        )
    
    @property
    def default_room(self) -> Room:
        """Get the default General room.
        
        Returns:
            General room (always exists)
        """
        return self._rooms[self.DEFAULT_ROOM_ID]
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """Get room by ID.
        
        Args:
            room_id: Room identifier
            
        Returns:
            Room or None if not found
        """
        return self._rooms.get(room_id)
    
    def create_room(
        self,
        name: str,
        room_type: RoomType = RoomType.PROJECT,
        participants: Optional[List[str]] = None,
    ) -> Room:
        """Create a new room.
        
        Args:
            name: Room name (becomes ID)
            room_type: Type of room
            participants: Initial bot participants (defaults to ["nanobot"])
            
        Returns:
            Created room
        """
        # Sanitize name for ID
        room_id = name.lower().replace(" ", "-").replace("_", "-")
        
        if room_id in self._rooms:
            raise ValueError(f"Room '{name}' already exists")
        
        # Default to just Leader if no participants specified
        if participants is None:
            participants = ["nanobot"]
        
        room = Room(
            id=room_id,
            type=room_type,
            participants=participants,
            owner="user",
            created_at=datetime.now(),
        )
        
        self._rooms[room_id] = room
        self._save_room(room)
        
        logger.info(f"Created room '{name}' with {len(participants)} bots")
        return room
    
    def invite_bot(self, room_id: str, bot_name: str) -> bool:
        """Invite a bot to a room.
        
        Args:
            room_id: Target room
            bot_name: Bot to invite
            
        Returns:
            True if invited, False if already present
        """
        room = self._rooms.get(room_id)
        if not room:
            logger.error(f"Room '{room_id}' not found")
            return False
        
        if bot_name in room.participants:
            logger.debug(f"Bot '{bot_name}' already in room '{room_id}'")
            return False
        
        room.add_participant(bot_name)
        self._save_room(room)
        
        logger.info(f"Invited '{bot_name}' to room '{room_id}'")
        return True
    
    def remove_bot(self, room_id: str, bot_name: str) -> bool:
        """Remove a bot from a room.
        
        Args:
            room_id: Target room
            bot_name: Bot to remove
            
        Returns:
            True if removed, False if not present or room not found
        """
        room = self._rooms.get(room_id)
        if not room:
            return False
        
        if bot_name not in room.participants:
            return False
        
        # Don't remove the last bot (keep at least Leader)
        if len(room.participants) <= 1:
            logger.warning(f"Cannot remove last bot from room '{room_id}'")
            return False
        
        room.remove_participant(bot_name)
        self._save_room(room)
        
        logger.info(f"Removed '{bot_name}' from room '{room_id}'")
        return True
    
    def list_rooms(self) -> List[dict]:
        """List all rooms.
        
        Returns:
            List of room summaries
        """
        return [
            {
                "id": room.id,
                "type": room.type.value,
                "participants": room.participants,
                "participant_count": len(room.participants),
                "is_default": room.id == self.DEFAULT_ROOM_ID,
            }
            for room in self._rooms.values()
        ]
    
    def get_room_participants(self, room_id: str) -> List[str]:
        """Get list of bots in a room.
        
        Args:
            room_id: Room identifier
            
        Returns:
            List of bot names (empty if room not found)
        """
        room = self._rooms.get(room_id)
        if room:
            return room.participants.copy()
        return []


# Global instance
_room_manager: Optional[RoomManager] = None


def get_room_manager() -> RoomManager:
    """Get the global room manager.
    
    Returns:
        RoomManager instance (creates if needed)
    """
    global _room_manager
    if _room_manager is None:
        _room_manager = RoomManager()
    return _room_manager


def reset_room_manager() -> None:
    """Reset the global room manager (forces reload)."""
    global _room_manager
    _room_manager = None
