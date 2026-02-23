"""Unified message envelope for routing across the system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from nanofolks.utils.ids import normalize_room_id, session_key_for_message

MessageDirection = Literal["inbound", "outbound"]


@dataclass
class MessageEnvelope:
    """Single message shape for broker, bus, channels, and tools."""

    channel: str  # telegram, discord, slack, whatsapp, cli, gui
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    direction: MessageDirection = "inbound"
    sender_id: str | None = None  # User identifier (inbound)
    sender_role: str | None = None  # user, bot, system
    bot_name: str | None = None  # Bot name if sender is a bot
    reply_to: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    room_id: str | None = None  # Room ID if part of room-centric routing
    trace_id: str | None = None

    @property
    def session_key(self) -> str:
        """Unique key for session identification (room-centric format)."""
        return session_key_for_message(self.room_id, self.channel, self.chat_id)

    def set_room(self, room_id: str) -> None:
        """Set the room for this message (room-centric routing)."""
        self.room_id = normalize_room_id(room_id)
