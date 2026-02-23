"""Data models for multi-agent orchestration."""

from .bot_registry import BotRegistry, get_bot_registry, list_available_bots
from .role_card import (
    BotCapabilities,
    RoleCard,
    RoleCardDomain,
    get_role_card,
    is_valid_bot,
    list_bots,
    BUILTIN_ROLES,
)
from .message_envelope import MessageDirection, MessageEnvelope
from .room import Message, Room, RoomType, SharedContext

# Legacy aliases for backwards compatibility
Workspace = Room
WorkspaceType = RoomType

__all__ = [
    # Room (primary)
    "Room",
    "RoomType",
    "Message",
    "SharedContext",
    # Message Envelope
    "MessageEnvelope",
    "MessageDirection",
    # Workspace (legacy alias for backwards compatibility)
    "Workspace",
    "WorkspaceType",
    # Role Card
    "RoleCard",
    "RoleCardDomain",
    "BotCapabilities",
    "get_role_card",
    "list_bots",
    "is_valid_bot",
    "BUILTIN_ROLES",
    # Bot Registry
    "BotRegistry",
    "get_bot_registry",
    "list_available_bots",
]
