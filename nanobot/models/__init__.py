"""Data models for multi-agent orchestration."""

from .room import Room, RoomType, Message, SharedContext
from .role_card import RoleCard, RoleCardDomain, BotCapabilities, get_role_card, list_bots, is_valid_bot
from .bot_registry import BotRegistry, get_bot_registry, list_available_bots

# Legacy aliases for backwards compatibility
Workspace = Room
WorkspaceType = RoomType

__all__ = [
    # Room (primary)
    "Room",
    "RoomType",
    "Message",
    "SharedContext",
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
    # Bot Registry
    "BotRegistry",
    "get_bot_registry",
    "list_available_bots",
]
