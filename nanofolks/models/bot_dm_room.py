"""Bot-to-bot DM room data model for transparent communication.

This module provides data structures for persistent bot-to-bot conversations
that users can peek into. These are separate from the main room conversations
and are used for bot coordination and delegation tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class BotMessageType(Enum):
    """Types of messages in bot-to-bot DM rooms."""
    QUERY = "query"           # Question expecting reply
    RESPONSE = "response"     # Reply to query
    INFO = "info"             # Information sharing (no reply expected)
    ESCALATION = "escalation" # Problem report requiring attention
    COORDINATION = "coordination"  # Task coordination


@dataclass
class BotDMMessage:
    """A message in a bot-to-bot DM room.
    
    These messages are logged for transparency and audit purposes,
    allowing users to peek into how bots collaborate.
    """
    id: str
    timestamp: datetime
    sender_bot: str           # e.g., "leader"
    recipient_bot: str        # e.g., "researcher"
    message_type: BotMessageType
    content: str              # Message content
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context
    reply_to: Optional[str] = None  # ID of message being replied to
    
    @classmethod
    def create(
        cls,
        sender_bot: str,
        recipient_bot: str,
        content: str,
        message_type: BotMessageType = BotMessageType.INFO,
        context: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None
    ) -> "BotDMMessage":
        """Factory method to create a new message."""
        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            sender_bot=sender_bot,
            recipient_bot=recipient_bot,
            message_type=message_type,
            content=content,
            context=context or {},
            reply_to=reply_to
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "sender_bot": self.sender_bot,
            "recipient_bot": self.recipient_bot,
            "message_type": self.message_type.value,
            "content": self.content,
            "context": self.context,
            "reply_to": self.reply_to
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotDMMessage":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sender_bot=data["sender_bot"],
            recipient_bot=data["recipient_bot"],
            message_type=BotMessageType(data["message_type"]),
            content=data["content"],
            context=data.get("context", {}),
            reply_to=data.get("reply_to")
        )
    
    def format_display(self) -> str:
        """Format message for display in CLI."""
        timestamp_str = self.timestamp.strftime("%H:%M")
        
        # Format based on type
        if self.message_type == BotMessageType.QUERY:
            prefix = "❓"
        elif self.message_type == BotMessageType.RESPONSE:
            prefix = "💬"
        elif self.message_type == BotMessageType.ESCALATION:
            prefix = "🚨"
        elif self.message_type == BotMessageType.COORDINATION:
            prefix = "📋"
        else:
            prefix = "📝"
        
        return f"{prefix} [{timestamp_str}] @{self.sender_bot}: {self.content}"


@dataclass
class BotDMRoom:
    """A DM room between two or more bots.
    
    These rooms are used for:
    - Bot-to-bot queries and responses
    - Task delegation tracking
    - Coordination conversations
    - User visibility into bot collaboration
    
    The room_id format is: dm-{bot_a}-{bot_b} (sorted alphabetically)
    For group DMs: dm-{bot_a}-{bot_b}-{bot_c} (sorted alphabetically)
    """
    room_id: str              # e.g., "dm-leader-researcher"
    bots: List[str]           # List of bot names, sorted alphabetically
    created_at: datetime
    messages: List[BotDMMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_group(self) -> bool:
        """Whether this is a group DM (more than 2 bots)."""
        return len(self.bots) > 2
    
    @property
    def display_name(self) -> str:
        """Human-readable name for the room."""
        if self.is_group:
            return f"Group DM: {', '.join(['@' + b for b in self.bots])}"
        elif len(self.bots) == 2:
            return f"DM: @{self.bots[0]} ↔ @{self.bots[1]}"
        else:
            return f"DM: {', '.join(['@' + b for b in self.bots])}"
    
    def get_other_bot(self, bot_name: str) -> Optional[str]:
        """Get the other bot in a 1-on-1 DM."""
        if len(self.bots) != 2:
            return None
        return self.bots[1] if self.bots[0] == bot_name else self.bots[0]
    
    def add_message(self, message: BotDMMessage):
        """Add a message to the room."""
        self.messages.append(message)
    
    def get_conversation(self, limit: int = 50) -> List[BotDMMessage]:
        """Get recent conversation, most recent last."""
        return self.messages[-limit:] if self.messages else []
    
    def get_conversation_between(
        self,
        bot_a: str,
        bot_b: str,
        limit: int = 50
    ) -> List[BotDMMessage]:
        """Get messages between two specific bots."""
        relevant = [
            m for m in self.messages
            if (m.sender_bot == bot_a and m.recipient_bot == bot_b) or
               (m.sender_bot == bot_b and m.recipient_bot == bot_a)
        ]
        return relevant[-limit:]
    
    def to_summary(self) -> Dict[str, Any]:
        """Get summary for listing."""
        last_message = self.messages[-1] if self.messages else None
        
        return {
            "room_id": self.room_id,
            "bots": self.bots,
            "display_name": self.display_name,
            "is_group": self.is_group,
            "message_count": len(self.messages),
            "last_activity": last_message.timestamp.isoformat() if last_message else None,
            "last_message_preview": last_message.content[:50] + "..." if last_message and len(last_message.content) > 50 else (last_message.content if last_message else None)
        }


def generate_dm_room_id(bot_a: str, bot_b: str) -> str:
    """Generate a consistent room ID for two bots.
    
    Bots are sorted alphabetically to ensure consistent ID
    regardless of message direction.
    
    Args:
        bot_a: First bot name
        bot_b: Second bot name
        
    Returns:
        Room ID string (e.g., "dm-leader-researcher")
    """
    bots = sorted([bot_a.lower(), bot_b.lower()])
    return f"dm-{bots[0]}-{bots[1]}"


def generate_group_dm_room_id(bots: List[str]) -> str:
    """Generate a room ID for a group DM.
    
    Args:
        bots: List of bot names (will be sorted alphabetically)
        
    Returns:
        Room ID string (e.g., "dm-auditor-coder-leader")
    """
    sorted_bots = sorted([b.lower() for b in bots])
    return "dm-" + "-".join(sorted_bots)


__all__ = [
    "BotMessageType",
    "BotDMMessage",
    "BotDMRoom",
    "generate_dm_room_id",
    "generate_group_dm_room_id",
]
