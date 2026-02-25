"""Bot Dispatch system with Leader-First architecture.

Routes messages through the Leader bot first, unless user directly
tags/mentions a specific bot or sends a DM.

The Leader acts as the nexus between user and crew, with powers to:
- Create rooms
- Invite bots to rooms
- Coordinate responses from crew members
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

from nanofolks.models.room import Room


class DispatchTarget(Enum):
    """Who should receive the message."""
    LEADER_FIRST = "leader_first"      # Route through Leader
    DIRECT_BOT = "direct_bot"          # User tagged a specific bot
    DM = "dm"                          # Direct message to specific bot
    MULTI_BOT = "multi_bot"            # All specified bots respond (@all)
    CREW_CONTEXT = "crew_context"      # Relevant bots respond (@crew)


@dataclass
class DispatchResult:
    """Result of dispatch decision."""
    target: DispatchTarget
    primary_bot: str                   # Who responds first
    secondary_bots: List[str]          # Who gets notified after
    room_id: Optional[str] = None
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
        "@leader": "leader",
        "@coordinator": "leader",
        "@researcher": "researcher",
        "@coder": "coder",
        "@social": "social",
        "@creative": "creative",
        "@auditor": "auditor",
        "@all": "all",
        "@crew": "crew",
        "@team": "all",
    }

    # Keywords that trigger specific bots for @crew mode
    BOT_KEYWORDS = {
        "coder": ["code", "programming", "bug", "fix", "python", "javascript", "api", "database", "sql", "develop", "function", "class", "module"],
        "researcher": ["research", "data", "analyze", "market", "competitor", "trend", "survey", "study", "investigate", "report"],
        "creative": ["design", "visual", "logo", "brand", "color", "ui", "ux", "mockup", "creative", "image", "art", "style"],
        "social": ["post", "tweet", "engagement", "audience", "viral", "hashtag", "content", "social", "media", "marketing", "community"],
        "auditor": ["audit", "quality", "compliance", "security", "review", "check", "test", "validate", "verify", "standard"],
        "leader": ["plan", "coordinate", "delegate", "prioritize", "team", "schedule", "manage", "organize", "strategy"],
    }

    def __init__(self, leader_bot=None, room_manager=None):
        """Initialize Bot Dispatch.

        Args:
            leader_bot: The Leader/nanofolks instance
            room_manager: Manager for room operations
        """
        self.leader_bot = leader_bot
        self.room_manager = room_manager

    def dispatch_message(
        self,
        message: str,
        room: Optional[Room] = None,
        is_dm: bool = False,
        dm_target: Optional[str] = None,
    ) -> DispatchResult:
        """Determine who should handle this message.

        Args:
            message: User message content
            room: Room context (None if DM)
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
                room_id=None,
                reason=f"Direct message to @{dm_target}"
            )

        # Case 2: User tagged specific bot - bypass leader
        mentioned = self._extract_mentions(message)
        if mentioned:
            if "all" in mentioned:
                # @all - all bots respond simultaneously
                participants = room.participants if room else ["leader", "coder", "researcher", "creative", "social", "auditor"]
                return DispatchResult(
                    target=DispatchTarget.MULTI_BOT,
                    primary_bot="leader",
                    secondary_bots=[p for p in participants if p != "leader"],
                    room_id=room.id if room else None,
                    reason="User tagged @all - all bots respond"
                )
            elif "crew" in mentioned:
                # @crew - relevant bots based on keywords
                participants = room.participants if room else ["leader", "coder", "researcher", "creative", "social", "auditor"]
                relevant_bots = self._select_relevant_bots(message, participants)
                return DispatchResult(
                    target=DispatchTarget.CREW_CONTEXT,
                    primary_bot="leader",
                    secondary_bots=relevant_bots,
                    room_id=room.id if room else None,
                    reason="User tagged @crew - relevant bots respond"
                )
            elif len(mentioned) == 1:
                # Single bot mentioned
                return DispatchResult(
                    target=DispatchTarget.DIRECT_BOT,
                    primary_bot=mentioned[0],
                    secondary_bots=[],
                    room_id=room.id if room else None,
                    reason=f"User tagged @{mentioned[0]} directly"
                )
            else:
                # Multiple specific bots mentioned
                return DispatchResult(
                    target=DispatchTarget.MULTI_BOT,
                    primary_bot="leader",
                    secondary_bots=mentioned,
                    room_id=room.id if room else None,
                    reason=f"Multiple mentions: {', '.join(mentioned)}"
                )

        # Case 3: Default - Route through Leader first
        participants = room.participants if room else ["leader"]
        secondary = [p for p in participants if p != "leader"]

        return DispatchResult(
            target=DispatchTarget.LEADER_FIRST,
            primary_bot="leader",
            secondary_bots=secondary,
            room_id=room.id if room else None,
            reason="Default: Leader coordinates response"
        )

    def _extract_mentions(self, message: str) -> List[str]:
        """Extract all bot mentions from message.

        Args:
            message: User message

        Returns:
            List of mentioned bot names
        """
        message_lower = message.lower()
        mentions = []

        # Check for @all variations first (highest priority)
        all_patterns = ["@all", "@team", "@everyone"]
        for pattern in all_patterns:
            if pattern in message_lower:
                mentions.append("all")
                break

        # Check for @crew
        if "@crew" in message_lower:
            mentions.append("crew")

        # Check for specific bot mentions (excluding @all/@crew)
        for mention, bot_name in self.BOT_MENTIONS.items():
            if bot_name not in ["all", "crew"] and mention.lower() in message_lower:
                if bot_name not in mentions:
                    mentions.append(bot_name)

        return mentions

    def _select_relevant_bots(self, message: str, all_bots: List[str]) -> List[str]:
        """Select bots relevant to the message content based on keywords.

        Args:
            message: User message
            all_bots: List of available bots

        Returns:
            List of relevant bot names
        """
        message_lower = message.lower()

        # Score each bot based on keyword matches
        relevance_scores = {}
        for bot in all_bots:
            if bot == "leader":
                continue  # Leader is always primary, not secondary

            score = 0
            keywords = self.BOT_KEYWORDS.get(bot, [])
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            relevance_scores[bot] = score

        # Return bots with score > 0, or top 3 if none match
        relevant = [bot for bot, score in relevance_scores.items() if score > 0]

        if not relevant:
            # No clear matches, return first 3 non-leader bots
            non_leader = [b for b in all_bots if b != "leader"]
            return non_leader[:3]

        return relevant

    def should_leader_create_room(
        self,
        message: str,
        current_room: Optional[Room] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if Leader should create a new room.

        Detects room creation requests like:
        - "Create a room for the website project"
        - "New project: mobile app"

        Args:
            message: User message
            current_room: Current room context

        Returns:
            Tuple of (should_create, room_name, project_type)
        """
        creation_patterns = [
            r"(?:create|make|start|set up)\s+(?:a\s+)?(?:new\s+)?room(?:\s+for\s+)?(?:the\s+)?(.+?)(?:\s+project)?$",
            r"(?:create|make|start|set up)\s+(?:a\s+)?(?:new\s+)?workspace(?:\s+for\s+)?(?:the\s+)?(.+?)(?:\s+project)?$",
            r"(?:create|make|start|set up)\s+(?:a\s+)?(?:new\s+)?project(?:\s+called)?\s*:?\s*(.+)",
            r"new\s+room\s*:?\s*(.+)",
            r"new\s+workspace\s*:?\s*(.+)",
            r"new\s+project\s*:?\s*(.+)",
        ]

        message_lower = message.lower()

        for pattern in creation_patterns:
            match = re.search(pattern, message_lower)
            if match:
                room_name = match.group(1).strip()
                # Determine project type from keywords
                project_type = self._infer_project_type(room_name)
                return True, room_name, project_type

        return False, None, None

    def _infer_project_type(self, name: str) -> str:
        """Infer project type from room name.

        Args:
            name: Room/project name

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
            "web": ["leader", "coder", "creative"],
            "mobile": ["leader", "coder", "creative"],
            "research": ["leader", "researcher"],
            "audit": ["leader", "auditor"],
            "marketing": ["leader", "social", "creative"],
            "social": ["leader", "social"],
            "content": ["leader", "creative", "social"],
            "general": ["leader"],
        }

        return suggestions.get(project_type, ["leader"])

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

        if result.room_id:
            lines.append(f"   Room: {result.room_id}")

        lines.append(f"   Reason: {result.reason}")

        return "\n".join(lines)


# Convenience function
def get_bot_dispatch(leader_bot=None, room_manager=None) -> BotDispatch:
    """Get BotDispatch instance.

    Args:
        leader_bot: Leader bot instance
        room_manager: Room manager

    Returns:
        BotDispatch instance
    """
    return BotDispatch(leader_bot, room_manager)
