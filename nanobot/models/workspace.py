"""Workspace data model (legacy alias for Room)."""

from .room import Room, RoomType, Message, SharedContext

# Legacy aliases for backwards compatibility
Workspace = Room
WorkspaceType = RoomType

__all__ = [
    "Workspace",
    "WorkspaceType",
    "Message", 
    "SharedContext",
]
