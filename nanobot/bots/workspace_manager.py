"""Workspace management with default General workspace.

Automatically creates and manages workspaces, including a default
"General" workspace that exists on first run with Leader ready to go.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from loguru import logger

from nanobot.config.loader import get_data_dir
from nanobot.models.workspace import Workspace, WorkspaceType


class WorkspaceManager:
    """Manages all workspaces with automatic default creation."""
    
    # Default workspace that always exists
    DEFAULT_WORKSPACE_ID = "general"
    DEFAULT_WORKSPACE_NAME = "General"
    
    def __init__(self):
        """Initialize workspace manager."""
        self.config_dir = get_data_dir()
        self.workspaces_dir = self.config_dir / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        
        self._workspaces: Dict[str, Workspace] = {}
        self._load_or_create_default()
    
    def _load_or_create_default(self) -> None:
        """Load existing workspaces or create default General workspace."""
        # Try to load existing workspaces
        workspace_files = list(self.workspaces_dir.glob("*.json"))
        
        if workspace_files:
            # Load all existing workspaces
            for ws_file in workspace_files:
                try:
                    ws_data = json.loads(ws_file.read_text())
                    workspace = self._workspace_from_dict(ws_data)
                    self._workspaces[workspace.id] = workspace
                    logger.debug(f"Loaded workspace: {workspace.id}")
                except Exception as e:
                    logger.warning(f"Failed to load workspace {ws_file}: {e}")
        
        # Ensure General workspace exists
        if self.DEFAULT_WORKSPACE_ID not in self._workspaces:
            self._create_default_workspace()
    
    def _create_default_workspace(self) -> None:
        """Create the default General workspace with Leader."""
        general = Workspace(
            id=self.DEFAULT_WORKSPACE_ID,
            type=WorkspaceType.OPEN,
            participants=["nanobot"],  # Only Leader initially
            owner="user",
            created_at=datetime.now(),
        )
        
        self._workspaces[self.DEFAULT_WORKSPACE_ID] = general
        self._save_workspace(general)
        
        logger.info(f"Created default '{self.DEFAULT_WORKSPACE_NAME}' workspace with Leader")
    
    def _save_workspace(self, workspace: Workspace) -> None:
        """Save workspace to disk."""
        ws_file = self.workspaces_dir / f"{workspace.id}.json"
        ws_data = self._workspace_to_dict(workspace)
        ws_file.write_text(json.dumps(ws_data, indent=2, default=str))
    
    def _workspace_to_dict(self, workspace: Workspace) -> dict:
        """Convert workspace to dictionary."""
        return {
            "id": workspace.id,
            "type": workspace.type.value,
            "participants": workspace.participants,
            "owner": workspace.owner,
            "created_at": workspace.created_at.isoformat(),
            "summary": workspace.summary,
            "auto_archive": workspace.auto_archive,
            "coordinator_mode": workspace.coordinator_mode,
        }
    
    def _workspace_from_dict(self, data: dict) -> Workspace:
        """Create workspace from dictionary."""
        return Workspace(
            id=data["id"],
            type=WorkspaceType(data["type"]),
            participants=data.get("participants", []),
            owner=data.get("owner", "user"),
            created_at=datetime.fromisoformat(data["created_at"]),
            summary=data.get("summary", ""),
            auto_archive=data.get("auto_archive", False),
            coordinator_mode=data.get("coordinator_mode", False),
        )
    
    @property
    def default_workspace(self) -> Workspace:
        """Get the default General workspace.
        
        Returns:
            General workspace (always exists)
        """
        return self._workspaces[self.DEFAULT_WORKSPACE_ID]
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID.
        
        Args:
            workspace_id: Workspace identifier
            
        Returns:
            Workspace or None if not found
        """
        return self._workspaces.get(workspace_id)
    
    def create_workspace(
        self,
        name: str,
        workspace_type: WorkspaceType = WorkspaceType.PROJECT,
        participants: Optional[List[str]] = None,
    ) -> Workspace:
        """Create a new workspace.
        
        Args:
            name: Workspace name (becomes ID)
            workspace_type: Type of workspace
            participants: Initial bot participants (defaults to ["nanobot"])
            
        Returns:
            Created workspace
        """
        # Sanitize name for ID
        workspace_id = name.lower().replace(" ", "-").replace("_", "-")
        
        if workspace_id in self._workspaces:
            raise ValueError(f"Workspace '{name}' already exists")
        
        # Default to just Leader if no participants specified
        if participants is None:
            participants = ["nanobot"]
        
        workspace = Workspace(
            id=workspace_id,
            type=workspace_type,
            participants=participants,
            owner="user",
            created_at=datetime.now(),
        )
        
        self._workspaces[workspace_id] = workspace
        self._save_workspace(workspace)
        
        logger.info(f"Created workspace '{name}' with {len(participants)} bots")
        return workspace
    
    def invite_bot(self, workspace_id: str, bot_name: str) -> bool:
        """Invite a bot to a workspace.
        
        Args:
            workspace_id: Target workspace
            bot_name: Bot to invite
            
        Returns:
            True if invited, False if already present
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            logger.error(f"Workspace '{workspace_id}' not found")
            return False
        
        if bot_name in workspace.participants:
            logger.debug(f"Bot '{bot_name}' already in workspace '{workspace_id}'")
            return False
        
        workspace.add_participant(bot_name)
        self._save_workspace(workspace)
        
        logger.info(f"Invited '{bot_name}' to workspace '{workspace_id}'")
        return True
    
    def remove_bot(self, workspace_id: str, bot_name: str) -> bool:
        """Remove a bot from a workspace.
        
        Args:
            workspace_id: Target workspace
            bot_name: Bot to remove
            
        Returns:
            True if removed, False if not present or workspace not found
        """
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False
        
        if bot_name not in workspace.participants:
            return False
        
        # Don't remove the last bot (keep at least Leader)
        if len(workspace.participants) <= 1:
            logger.warning(f"Cannot remove last bot from workspace '{workspace_id}'")
            return False
        
        workspace.remove_participant(bot_name)
        self._save_workspace(workspace)
        
        logger.info(f"Removed '{bot_name}' from workspace '{workspace_id}'")
        return True
    
    def list_workspaces(self) -> List[dict]:
        """List all workspaces.
        
        Returns:
            List of workspace summaries
        """
        return [
            {
                "id": ws.id,
                "type": ws.type.value,
                "participants": ws.participants,
                "participant_count": len(ws.participants),
                "is_default": ws.id == self.DEFAULT_WORKSPACE_ID,
            }
            for ws in self._workspaces.values()
        ]
    
    def get_workspace_participants(self, workspace_id: str) -> List[str]:
        """Get list of bots in a workspace.
        
        Args:
            workspace_id: Workspace identifier
            
        Returns:
            List of bot names (empty if workspace not found)
        """
        workspace = self._workspaces.get(workspace_id)
        if workspace:
            return workspace.participants.copy()
        return []


# Global instance
_workspace_manager: Optional[WorkspaceManager] = None


def get_workspace_manager() -> WorkspaceManager:
    """Get the global workspace manager.
    
    Returns:
        WorkspaceManager instance (creates if needed)
    """
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager


def reset_workspace_manager() -> None:
    """Reset the global workspace manager (forces reload)."""
    global _workspace_manager
    _workspace_manager = None
