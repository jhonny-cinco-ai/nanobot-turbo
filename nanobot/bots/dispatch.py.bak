"""Bot Dispatch system with Leader-First architecture.

Routes messages through the Leader bot first, unless user directly
tags/mentions a specific bot or sends a DM.

The Leader acts as the nexus between user and crew, with powers to:
- Create workspaces
- Invite bots to workspaces
- Coordinate responses from crew members
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from nanobot.models.workspace import Workspace, WorkspaceType


class DispatchTarget(Enum):
    """Who should receive the message."""
    LEADER_FIRST = "leader_first"      # Route through Leader
    DIRECT_BOT = "direct_bot"          # User tagged a specific bot
    DM = "dm"                          # Direct message to specific bot


@dataclass
class DispatchResult:
    """Result of dispatch decision."""
    target: DispatchTarget
    primary_bot: str                   # Who responds first
    secondary_bots: List[str]          # Who gets notified after
    workspace_id: Optional[str] = None
    reason: str = ""                   # Why this dispatch decision


class BotDispatch:
    """Routes messages to appropriate bots with Leader-First logic.
    
    Rules:
    1. Default: Message goes to Leader first
    2. Exception: User tags @bot → Direct to that bot
    3. Exception: DM to bot → Direct to that bot
    4. Exception: @all or @crew → All participants
    """
    
    # Bot mention patterns
    BOT_MENTIONS = {
        "@leader": "nanobot",
        "@nanobot": "nanobot",
        "@coordinator": "nanobot",
        "@researcher": "researcher",
        "@coder": "coder",
        "@social": "social",
        "@creative": "creative",
        "@auditor": "auditor",
        "@all": "all",
        "@crew": "all",
        "@team": "all",
    }
    
    def __init__(self, leader_bot=None, workspace_manager=None):
        """Initialize Bot Dispatch.
        
        Args:
            leader_bot: The Leader/Nanobot instance
            workspace_manager: Manager for workspace operations
        """
        self.leader_bot = leader_bot
        self.workspace_manager = workspace_manager
    
    def dispatch_message(
        self,
        message: str,
        workspace: Optional[Workspace] = None,
        is_dm: bool = False,
        dm_target: Optional[str] = None,
    ) -> DispatchResult:
        """Determine who should handle this message.
        
        Args:
            message: User message content
            workspace: Workspace context (None if DM)
            is_dm: Whether this is a direct message
            dm_target: If DM, which bot it was sent to
            
        Returns:
            DispatchResult with routing decision
        """
        # Case 1: Direct Message (DM) - bypass leader
        if is_dm and dm_target:
            return DispatchResult(
                target=DispatchTarget.DM,
                primary_bot=dm_target,
                secondary_bots=[],
                workspace_id=None,
                reason=f"Direct message to @{dm_target}"
            )
        
        # Case 2: User tagged specific bot - bypass leader
        mentioned_bot = self._extract_mention(message)
        if mentioned_bot:
            if mentioned_bot == "all":
                # @all or @crew - notify all workspace participants
                participants = workspace.participants if workspace else ["nanobot"]
                return DispatchResult(
                    target=DispatchTarget.DIRECT_BOT,
                    primary_bot="nanobot",  # Leader coordinates
                    secondary_bots=participants,
                    workspace_id=workspace.id if workspace else None,
                    reason="User tagged @all/@crew - leader coordinates all bots"
                )
            else:
                # Specific bot mentioned
                return DispatchResult(
                    target=DispatchTarget.DIRECT_BOT,
                    primary_bot=mentioned_bot,
                    secondary_bots=[],
                    workspace_id=workspace.id if workspace else None,
                    reason=f"User tagged @{mentioned_bot} directly"
                )
        
        # Case 3: Default - Route through Leader first
        participants = workspace.participants if workspace else ["nanobot"]
        secondary = [p for p in participants if p != "nanobot"]
        
        return DispatchResult(
            target=DispatchTarget.LEADER_FIRST,
            primary_bot="nanobot",
            secondary_bots=secondary,
            workspace_id=workspace.id if workspace else None,
            reason="Default: Leader coordinates response"
        )
    
    def _extract_mention(self, message: str) -> Optional[str]:
        """Extract bot mention from message.
        
        Args:
            message: User message
            
        Returns:
            Bot name if mentioned, None otherwise
        """
        message_lower = message.lower()
        
        # Check for @all variations first (highest priority)
        all_patterns = ["@all", "@crew", "@team", "@everyone"]
        for pattern in all_patterns:
            if pattern in message_lower:
                return "all"
        
        # Check for specific bot mentions
        for mention, bot_name in self.BOT_MENTIONS.items():
            if mention.lower() in message_lower:
                return bot_name
        
        return None
    
    def should_leader_create_workspace(
        self,
        message: str,
        current_workspace: Optional[Workspace] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if Leader should create a new workspace.
        
        Detects workspace creation requests like:
        - "Create a workspace for the website project"
        - "New project: mobile app"
        
        Args:
            message: User message
            current_workspace: Current workspace context
            
        Returns:
            Tuple of (should_create, workspace_name, project_type)
        """
        creation_patterns = [
            r"(?:create|make|start|set up)\s+(?:a\s+)?(?:new\s+)?workspace(?:\s+for\s+)?(?:the\s+)?(.+?)(?:\s+project)?$",
            r"(?:create|make|start|set up)\s+(?:a\s+)?(?:new\s+)?project(?:\s+called)?\s*:?\s*(.+)",
            r"new\s+workspace\s*:?\s*(.+)",
            r"new\s+project\s*:?\s*(.+)",
        ]
        
        message_lower = message.lower()
        
        for pattern in creation_patterns:
            match = re.search(pattern, message_lower)
            if match:
                workspace_name = match.group(1).strip()
                # Determine project type from keywords
                project_type = self._infer_project_type(workspace_name)
                return True, workspace_name, project_type
        
        return False, None, None
    
    def _infer_project_type(self, name: str) -> str:
        """Infer project type from workspace name.
        
        Args:
            name: Workspace/project name
            
        Returns:
            Project type category
        """
        name_lower = name.lower()
        
        type_keywords = {
            "website": "web",
            "web": "web",
            "app": "mobile",
            "mobile": "mobile",
            "research": "research",
            "analysis": "research",
            "audit": "audit",
            "security": "audit",
            "marketing": "marketing",
            "campaign": "marketing",
            "social": "social",
            "content": "content",
        }
        
        for keyword, project_type in type_keywords.items():
            if keyword in name_lower:
                return project_type
        
        return "general"
    
    def suggest_bots_for_project(self, project_type: str) -> List[str]:
        """Suggest which bots to invite based on project type.
        
        Args:
            project_type: Type of project
            
        Returns:
            List of recommended bot names
        """
        suggestions = {
            "web": ["nanobot", "coder", "creative"],
            "mobile": ["nanobot", "coder", "creative"],
            "research": ["nanobot", "researcher"],
            "audit": ["nanobot", "auditor"],
            "marketing": ["nanobot", "social", "creative"],
            "social": ["nanobot", "social"],
            "content": ["nanobot", "creative", "social"],
            "general": ["nanobot"],
        }
        
        return suggestions.get(project_type, ["nanobot"])
    
    def format_dispatch_summary(self, result: DispatchResult) -> str:
        """Format dispatch result for debugging/logging.
        
        Args:
            result: Dispatch decision
            
        Returns:
            Human-readable summary
        """
        lines = [
            f"🎯 Dispatch: {result.target.value}",
            f"   Primary: {result.primary_bot}",
        ]
        
        if result.secondary_bots:
            lines.append(f"   Secondary: {', '.join(result.secondary_bots)}")
        
        if result.workspace_id:
            lines.append(f"   Workspace: {result.workspace_id}")
        
        lines.append(f"   Reason: {result.reason}")
        
        return "\n".join(lines)


# Convenience function
def get_bot_dispatch(leader_bot=None, workspace_manager=None) -> BotDispatch:
    """Get BotDispatch instance.
    
    Args:
        leader_bot: Leader bot instance
        workspace_manager: Workspace manager
        
    Returns:
        BotDispatch instance
    """
    return BotDispatch(leader_bot, workspace_manager)
