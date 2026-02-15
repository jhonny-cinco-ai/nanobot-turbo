"""Workspace management (legacy alias for Room management).

This module provides backwards compatibility. Use RoomManager instead.
"""

from .room_manager import (
    RoomManager,
    get_room_manager,
    reset_room_manager,
    Room,
    RoomType,
)

# Legacy aliases for backwards compatibility
WorkspaceManager = RoomManager
get_workspace_manager = get_room_manager
reset_workspace_manager = reset_room_manager
Workspace = Room
WorkspaceType = RoomType

__all__ = [
    # New naming (preferred)
    "RoomManager",
    "get_room_manager",
    "reset_room_manager",
    "Room",
    "RoomType",
    # Legacy aliases
    "WorkspaceManager",
    "get_workspace_manager",
    "reset_workspace_manager",
    "Workspace",
    "WorkspaceType",
]
