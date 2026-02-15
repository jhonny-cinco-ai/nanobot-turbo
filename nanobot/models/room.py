"""Room data model for multi-agent orchestration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class RoomType(Enum):
    """Types of rooms in the system."""

    OPEN = "open"  # #general - all bots, casual chat
    PROJECT = "project"  # #project-x - specific team, deadline-driven
    DIRECT = "direct"  # DM @bot - 1-on-1 focused discussion
    COORDINATION = "coordination"  # nanobot manages when user away


@dataclass
class Message:
    """A message in a room."""

    sender: str  # Bot name or "user"
    content: str  # Message content
    timestamp: datetime  # When sent
    room_id: str  # Which room
    attachments: List[str] = field(default_factory=list)  # File paths


@dataclass
class SharedContext:
    """Shared memory for a room (all bots see this)."""

    events: List[Dict[str, Any]] = field(default_factory=list)
    """What happened (timestamped)"""

    entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    """Knowledge graph: people, orgs, concepts"""

    facts: List[Dict[str, Any]] = field(default_factory=list)
    """Verified truths with confidence scores"""

    artifact_chain: List[Dict[str, Any]] = field(default_factory=list)
    """Structured handoffs between bots"""


@dataclass
class Room:
    """A room for crew collaboration."""

    id: str  # "general", "project-alpha", "dm-researcher"
    type: RoomType  # OPEN, PROJECT, DIRECT, COORDINATION
    participants: List[str] = field(default_factory=list)  # ["nanobot", "researcher"]
    owner: str = "user"  # "user" or bot name if coordination mode
    created_at: datetime = field(default_factory=datetime.now)

    # Memory
    shared_context: SharedContext = field(default_factory=SharedContext)
    history: List[Message] = field(default_factory=list)
    summary: str = ""

    # Behavior
    auto_archive: bool = False
    archive_after_days: int = 30
    coordinator_mode: bool = False
    escalation_threshold: str = "medium"  # "low", "medium", "high"

    # Metadata
    deadline: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, sender: str, content: str) -> Message:
        """Add a message to room history.
        
        Args:
            sender: Bot name or "user"
            content: Message content
            
        Returns:
            Created Message object
        """
        msg = Message(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            room_id=self.id,
        )
        self.history.append(msg)
        return msg

    def add_participant(self, bot_name: str) -> None:
        """Add bot to room.
        
        Args:
            bot_name: Name of bot to add
        """
        if bot_name not in self.participants:
            self.participants.append(bot_name)

    def remove_participant(self, bot_name: str) -> None:
        """Remove bot from room.
        
        Args:
            bot_name: Name of bot to remove
        """
        if bot_name in self.participants:
            self.participants.remove(bot_name)

    def has_participant(self, bot_name: str) -> bool:
        """Check if bot is in room.
        
        Args:
            bot_name: Name of bot to check
            
        Returns:
            True if bot is participant
        """
        return bot_name in self.participants

    def is_active(self) -> bool:
        """Check if room should be archived.
        
        Returns:
            True if room is still active
        """
        if not self.history:
            return False
        
        last_activity = self.history[-1].timestamp
        days_inactive = (datetime.now() - last_activity).days
        return days_inactive < self.archive_after_days

    def get_last_message(self) -> Optional[Message]:
        """Get the most recent message in room.
        
        Returns:
            Last message or None if no messages
        """
        return self.history[-1] if self.history else None

    def get_participant_messages(self, bot_name: str) -> List[Message]:
        """Get all messages from specific participant.
        
        Args:
            bot_name: Name of bot
            
        Returns:
            List of messages from that bot
        """
        return [msg for msg in self.history if msg.sender == bot_name]

    def add_fact(
        self, subject: str, predicate: str, obj: str, confidence: float = 1.0
    ) -> None:
        """Add fact to shared memory.
        
        Args:
            subject: Subject of fact
            predicate: Relationship
            obj: Object of fact
            confidence: Confidence score (0.0-1.0)
        """
        fact = {
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }
        self.shared_context.facts.append(fact)

    def add_entity(self, entity_id: str, entity_data: Dict[str, Any]) -> None:
        """Add entity to knowledge graph.
        
        Args:
            entity_id: Unique entity identifier
            entity_data: Entity information
        """
        self.shared_context.entities[entity_id] = entity_data

    def add_event(self, content: str, source: str, **kwargs: Any) -> None:
        """Add event to shared history.
        
        Args:
            content: What happened
            source: Where event came from
            **kwargs: Additional event data
        """
        event = {
            "content": content,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.shared_context.events.append(event)
