"""Bot-to-bot DM room manager for persistent conversations.

This module provides the BotDMRoomManager class which handles:
- Creating and managing bot-to-bot DM rooms
- Persisting conversations to disk
- Loading conversation history
- Listing and querying DM rooms
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from loguru import logger

from nanofolks.models.bot_dm_room import (
    BotDMMessage,
    BotDMRoom,
    BotMessageType,
    generate_dm_room_id,
    generate_group_dm_room_id,
)


class BotDMRoomManager:
    """Manages bot-to-bot DM rooms with persistence.
    
    DM rooms are stored in: .nanofolks/dm_rooms/
    Each room is a JSONL file with one message per line.
    
    The manager ensures:
    - Consistent room IDs (alphabetically sorted bot names)
    - Persistence across restarts
    - Efficient loading of conversation history
    - Thread-safe operations
    """
    
    def __init__(self, workspace: Path):
        """Initialize the DM room manager.
        
        Args:
            workspace: The workspace root path
        """
        self.workspace = workspace
        self.dm_rooms_dir = workspace / ".nanofolks" / "dm_rooms"
        self.dm_rooms_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"BotDMRoomManager initialized at {self.dm_rooms_dir}")
    
    def _get_room_path(self, room_id: str) -> Path:
        """Get the file path for a room."""
        return self.dm_rooms_dir / f"{room_id}.jsonl"
    
    def get_or_create_room(
        self,
        bot_a: str,
        bot_b: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BotDMRoom:
        """Get existing DM room or create new one.
        
        Args:
            bot_a: First bot name
            bot_b: Second bot name
            metadata: Optional metadata for new room
            
        Returns:
            BotDMRoom instance
        """
        room_id = generate_dm_room_id(bot_a, bot_b)
        room_path = self._get_room_path(room_id)
        
        if room_path.exists():
            return self._load_room(room_id)
        
        # Create new room
        room = BotDMRoom(
            room_id=room_id,
            bots=sorted([bot_a.lower(), bot_b.lower()]),
            created_at=datetime.now(),
            messages=[],
            metadata=metadata or {}
        )
        self._save_room(room)
        logger.info(f"Created DM room: {room_id}")
        return room
    
    def get_or_create_group_room(
        self,
        bots: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> BotDMRoom:
        """Get existing group DM room or create new one.
        
        Args:
            bots: List of bot names (3+)
            metadata: Optional metadata for new room
            
        Returns:
            BotDMRoom instance
        """
        room_id = generate_group_dm_room_id(bots)
        room_path = self._get_room_path(room_id)
        
        if room_path.exists():
            return self._load_room(room_id)
        
        # Create new group room
        room = BotDMRoom(
            room_id=room_id,
            bots=sorted([b.lower() for b in bots]),
            created_at=datetime.now(),
            messages=[],
            metadata=metadata or {}
        )
        self._save_room(room)
        logger.info(f"Created group DM room: {room_id}")
        return room
    
    def get_room(self, room_id: str) -> Optional[BotDMRoom]:
        """Get a room by ID.
        
        Args:
            room_id: The room ID (e.g., "dm-leader-researcher")
            
        Returns:
            BotDMRoom or None if not found
        """
        room_path = self._get_room_path(room_id)
        if not room_path.exists():
            return None
        return self._load_room(room_id)
    
    def get_room_between(self, bot_a: str, bot_b: str) -> Optional[BotDMRoom]:
        """Get the DM room between two bots.
        
        Args:
            bot_a: First bot name
            bot_b: Second bot name
            
        Returns:
            BotDMRoom or None if not exists
        """
        room_id = generate_dm_room_id(bot_a, bot_b)
        return self.get_room(room_id)
    
    def log_message(
        self,
        sender_bot: str,
        recipient_bot: str,
        content: str,
        message_type: BotMessageType = BotMessageType.INFO,
        context: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None
    ) -> str:
        """Log a message to the appropriate DM room.
        
        This is the main method for bots to communicate.
        
        Args:
            sender_bot: Bot sending the message
            recipient_bot: Bot receiving the message
            content: Message content
            message_type: Type of message
            context: Additional context
            reply_to: ID of message being replied to
            
        Returns:
            Message ID
        """
        room = self.get_or_create_room(sender_bot, recipient_bot)
        
        message = BotDMMessage.create(
            sender_bot=sender_bot.lower(),
            recipient_bot=recipient_bot.lower(),
            content=content,
            message_type=message_type,
            context=context,
            reply_to=reply_to
        )
        
        room.add_message(message)
        self._append_message(room, message)
        
        logger.debug(
            f"Logged message in {room.room_id}: "
            f"@{sender_bot} -> @{recipient_bot}"
        )
        
        return message.id
    
    def log_query_and_response(
        self,
        sender_bot: str,
        recipient_bot: str,
        query: str,
        response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str]:
        """Log a query-response pair in one call.
        
        Convenience method for ask_bot() pattern.
        
        Args:
            sender_bot: Bot asking the question
            recipient_bot: Bot answering
            query: The question
            response: The answer
            context: Additional context
            
        Returns:
            Tuple of (query_message_id, response_message_id)
        """
        # Log query
        query_id = self.log_message(
            sender_bot=sender_bot,
            recipient_bot=recipient_bot,
            content=query,
            message_type=BotMessageType.QUERY,
            context=context
        )
        
        # Log response
        response_id = self.log_message(
            sender_bot=recipient_bot,
            recipient_bot=sender_bot,
            content=response,
            message_type=BotMessageType.RESPONSE,
            context=context,
            reply_to=query_id
        )
        
        return query_id, response_id
    
    def get_conversation_history(
        self,
        bot_a: str,
        bot_b: str,
        limit: int = 50
    ) -> List[BotDMMessage]:
        """Get conversation history between two bots.
        
        Args:
            bot_a: First bot name
            bot_b: Second bot name
            limit: Maximum number of messages to return
            
        Returns:
            List of messages, most recent last
        """
        room_id = generate_dm_room_id(bot_a, bot_b)
        room_path = self._get_room_path(room_id)
        
        if not room_path.exists():
            return []
        
        messages = []
        try:
            with open(room_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        messages.append(BotDMMessage.from_dict(data))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse DM room message: {line[:50]}")
                        continue
        except Exception as e:
            logger.error(f"Failed to load conversation history: {e}")
            return []
        
        return messages[-limit:] if messages else []
    
    def get_full_history(
        self,
        room_id: str,
        limit: int = 100
    ) -> List[BotDMMessage]:
        """Get full history for a specific room.
        
        Args:
            room_id: The room ID
            limit: Maximum number of messages
            
        Returns:
            List of messages
        """
        room_path = self._get_room_path(room_id)
        
        if not room_path.exists():
            return []
        
        messages = []
        try:
            with open(room_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        messages.append(BotDMMessage.from_dict(data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load room history: {e}")
            return []
        
        return messages[-limit:]
    
    def list_all_rooms(self) -> List[Dict[str, Any]]:
        """List all DM rooms with metadata.
        
        Returns:
            List of room summaries
        """
        rooms = []
        
        for room_file in self.dm_rooms_dir.glob("dm-*.jsonl"):
            room_id = room_file.stem
            
            try:
                # Load last message for preview
                last_message = None
                message_count = 0
                with open(room_file, 'r') as f:
                    lines = f.readlines()
                    message_count = len(lines)
                    if lines:
                        try:
                            last_data = json.loads(lines[-1].strip())
                            last_message = BotDMMessage.from_dict(last_data)
                        except:
                            pass
                
                # Parse bots from room_id
                parts = room_id.split('-')
                if len(parts) >= 3:
                    bots = parts[1:]  # Remove 'dm' prefix
                    
                    rooms.append({
                        "room_id": room_id,
                        "bots": bots,
                        "is_group": len(bots) > 2,
                        "message_count": message_count,
                        "last_activity": last_message.timestamp.isoformat() if last_message else None,
                        "last_message_preview": (
                            last_message.content[:50] + "..."
                            if last_message and len(last_message.content) > 50
                            else (last_message.content if last_message else None)
                        )
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to list room {room_id}: {e}")
        
        # Sort by last activity
        rooms.sort(
            key=lambda r: r.get("last_activity", ""),
            reverse=True
        )
        
        return rooms
    
    def delete_room(self, room_id: str) -> bool:
        """Delete a DM room and its history.
        
        Args:
            room_id: The room ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        room_path = self._get_room_path(room_id)
        
        if not room_path.exists():
            return False
        
        try:
            # Create backup before deletion
            backup_dir = self.dm_rooms_dir / "deleted"
            backup_dir.mkdir(exist_ok=True)
            shutil.move(
                str(room_path),
                str(backup_dir / f"{room_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
            )
            logger.info(f"Deleted DM room: {room_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete room {room_id}: {e}")
            return False
    
    def cleanup_old_rooms(self, days: int = 30) -> int:
        """Clean up rooms with no activity for specified days.
        
        Args:
            days: Number of days of inactivity before cleanup
            
        Returns:
            Number of rooms cleaned up
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        cleaned = 0
        
        for room_file in self.dm_rooms_dir.glob("dm-*.jsonl"):
            try:
                # Check last message timestamp
                with open(room_file, 'r') as f:
                    lines = f.readlines()
                    if not lines:
                        # Empty file, delete it
                        room_file.unlink()
                        cleaned += 1
                        continue
                    
                    last_data = json.loads(lines[-1].strip())
                    last_time = datetime.fromisoformat(last_data["timestamp"])
                    
                    if last_time < cutoff:
                        room_id = room_file.stem
                        if self.delete_room(room_id):
                            cleaned += 1
                            
            except Exception as e:
                logger.warning(f"Failed to check room {room_file}: {e}")
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old DM rooms")
        
        return cleaned
    
    def _load_room(self, room_id: str) -> BotDMRoom:
        """Load a room from disk."""
        room_path = self._get_room_path(room_id)
        
        if not room_path.exists():
            raise FileNotFoundError(f"Room not found: {room_id}")
        
        messages = []
        bots = None
        
        with open(room_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    messages.append(BotDMMessage.from_dict(data))
                    
                    # Extract bots from first message
                    if bots is None and messages:
                        bots = list(set([
                            messages[0].sender_bot,
                            messages[0].recipient_bot
                        ]))
                        
                except json.JSONDecodeError:
                    continue
        
        if not bots:
            # Fallback: parse from room_id
            parts = room_id.split('-')
            bots = parts[1:] if len(parts) >= 3 else ["unknown", "unknown"]
        
        return BotDMRoom(
            room_id=room_id,
            bots=bots,
            created_at=messages[0].timestamp if messages else datetime.now(),
            messages=messages
        )
    
    def _save_room(self, room: BotDMRoom):
        """Save a room to disk."""
        room_path = self._get_room_path(room.room_id)
        
        # Write all messages (overwrite)
        with open(room_path, 'w') as f:
            for msg in room.messages:
                f.write(json.dumps(msg.to_dict()) + '\n')
    
    def _append_message(self, room: BotDMRoom, message: BotDMMessage):
        """Append a single message to room file."""
        room_path = self._get_room_path(room.room_id)
        
        with open(room_path, 'a') as f:
            f.write(json.dumps(message.to_dict()) + '\n')


# Convenience functions for easy access
def get_dm_manager(workspace: Path) -> BotDMRoomManager:
    """Get or create a BotDMRoomManager instance."""
    return BotDMRoomManager(workspace)


def ensure_dm_rooms(workspace: Path) -> None:
    """Ensure DM rooms exist for all bot pairs.
    
    This should be called on startup to pre-create DM rooms
    for all bot pairs.
    
    Args:
        workspace: The workspace root path
    """
    manager = BotDMRoomManager(workspace)
    
    # All known bots
    bots = ["leader", "researcher", "coder", "social", "creative", "auditor"]
    
    # Create DM rooms for all pairs
    for i, bot_a in enumerate(bots):
        for bot_b in bots[i+1:]:
            try:
                room = manager.get_or_create_room(bot_a, bot_b)
                logger.debug(f"Ensured DM room: {room.room_id}")
            except Exception as e:
                logger.warning(f"Failed to create DM room for {bot_a}-{bot_b}: {e}")
    
    logger.info(f"Initialized DM rooms for {len(bots)} bots ({len(bots) * (len(bots) - 1) // 2} pairs)")


__all__ = [
    "BotDMRoomManager",
    "get_dm_manager",
    "ensure_dm_rooms",
]
