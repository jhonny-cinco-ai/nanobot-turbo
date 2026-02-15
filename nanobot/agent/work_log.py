"""Work log data models for tracking AI agent decision-making.

This module provides data structures for logging agent work, including
decisions, tool executions, errors, and other key events.

Supports both single-bot and multi-agent workspace modes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, List
from enum import Enum
import json


class LogLevel(Enum):
    """Severity/importance levels for work log entries."""
    INFO = "info"           # Normal operation
    THINKING = "thinking"   # Reasoning steps
    DECISION = "decision"   # Choice made
    CORRECTION = "correction"  # Mistake fixed
    UNCERTAINTY = "uncertainty"  # Low confidence
    WARNING = "warning"     # Issue encountered
    ERROR = "error"         # Failure
    TOOL = "tool"           # Tool execution
    # Multi-agent specific levels
    HANDOFF = "handoff"     # Bot-to-bot work transfer
    COORDINATION = "coordination"  # Coordinator mode decisions


class RoomType(Enum):
    """Types of rooms for multi-agent collaboration."""
    OPEN = "open"           # #general - casual, all bots
    PROJECT = "project"     # #project-alpha - focused team
    DIRECT = "direct"       # DM @researcher - 1-on-1
    COORDINATION = "coordination"  # nanobot manages autonomously


# Legacy alias for backwards compatibility
WorkspaceType = RoomType


@dataclass
class WorkLogEntry:
    """A single entry in a work log.
    
    Represents one step in the agent's decision-making process,
    such as a thought, decision, tool execution, or error.
    
    Supports both single-bot and multi-agent modes. In single-bot mode,
    multi-agent fields use sensible defaults.
    """
    timestamp: datetime
    level: LogLevel
    step: int                    # Sequential step number
    category: str                # "memory", "tool", "routing", etc.
    message: str                 # Human-readable description
    
    # Core fields (always used)
    details: dict = field(default_factory=dict)  # Structured data
    confidence: Optional[float] = None  # 0.0-1.0 for uncertainty
    duration_ms: Optional[int] = None   # How long this step took
    
    # Tool execution fields
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[Any] = None
    tool_status: Optional[str] = None   # "success", "error", "timeout"
    tool_error: Optional[str] = None
    
    # ===============================
    # Multi-Agent Extension Fields
    # ===============================
    
    # Workspace context (single-bot: uses "default")
    room_id: str = "default"  # "#general", "#project-refactor", or "default"
    room_type: WorkspaceType = RoomType.OPEN
    participants: List[str] = field(default_factory=lambda: ["nanobot"])
    
    # Bot identity (single-bot: always "nanobot")
    bot_name: str = "nanobot"      # Which bot created this entry
    bot_role: str = "primary"      # "coordinator", "specialist", "user-proxy", "primary"
    triggered_by: str = "user"     # "user", "nanobot", "@researcher", etc.
    
    # Coordinator mode (single-bot: always False)
    coordinator_mode: bool = False      # Was nanobot coordinating?
    escalation: bool = False            # Did this trigger escalation?
    
    # Cross-bot communication (single-bot: empty)
    mentions: List[str] = field(default_factory=list)  # ["@researcher", "@coder"]
    response_to: Optional[int] = None   # Step number this responds to
    
    # Learning Exchange (single-bot: False)
    shareable_insight: bool = False     # Can this be shared with other bots?
    insight_category: Optional[str] = None  # "user_preference", "tool_pattern", etc.
    
    def is_tool_entry(self) -> bool:
        """Check if this entry represents a tool execution."""
        return self.tool_name is not None
    
    def is_bot_conversation(self) -> bool:
        """Check if this is bot-to-bot communication.
        
        Returns True if the entry was triggered by another bot
        or if coordinator mode was active.
        """
        return self.triggered_by.startswith("@") or self.coordinator_mode
    
    def is_multi_agent_entry(self) -> bool:
        """Check if this entry uses multi-agent features.
        
        Returns True if any multi-agent fields are set to non-default values.
        """
        return (
            self.room_id != "default" or
            self.room_type != RoomType.OPEN or
            len(self.participants) > 1 or
            self.bot_name != "nanobot" or
            self.bot_role != "primary" or
            self.triggered_by != "user" or
            self.coordinator_mode or
            self.escalation or
            len(self.mentions) > 0 or
            self.response_to is not None or
            self.shareable_insight
        )
    
    def to_dict(self) -> dict:
        """Convert entry to dictionary for serialization."""
        return {
            # Core fields
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "step": self.step,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "tool_status": self.tool_status,
            "tool_error": self.tool_error,
            # Multi-agent fields
            "room_id": self.room_id,
            "room_type": self.room_type.value,
            "participants": self.participants,
            "bot_name": self.bot_name,
            "bot_role": self.bot_role,
            "triggered_by": self.triggered_by,
            "coordinator_mode": self.coordinator_mode,
            "escalation": self.escalation,
            "mentions": self.mentions,
            "response_to": self.response_to,
            "shareable_insight": self.shareable_insight,
            "insight_category": self.insight_category
        }


@dataclass
class WorkLog:
    """A complete work log for a single session.
    
    Tracks all the steps an agent took to process a user query,
    from start to finish. Supports both single-bot and multi-agent modes.
    """
    session_id: str
    query: str                   # Original user query
    start_time: datetime
    end_time: Optional[datetime] = None
    entries: List[WorkLogEntry] = field(default_factory=list)
    final_output: Optional[str] = None
    
    # Multi-agent context (single-bot: uses defaults)
    room_id: str = "default"  # "#general", "#project-alpha", etc.
    room_type: WorkspaceType = RoomType.OPEN
    participants: List[str] = field(default_factory=lambda: ["nanobot"])
    coordinator: Optional[str] = None  # "nanobot" if in coordinator mode
    
    def add_entry(self, level: LogLevel, category: str, message: str,
                  details: Optional[dict] = None, confidence: Optional[float] = None,
                  duration_ms: Optional[int] = None, bot_name: str = "nanobot",
                  triggered_by: str = "user") -> WorkLogEntry:
        """Add a work log entry.
        
        Args:
            level: Severity/importance of the entry
            category: Type of activity (memory, tool, routing, etc.)
            message: Human-readable description
            details: Structured data about the entry
            confidence: Confidence level (0.0-1.0) if applicable
            duration_ms: How long this step took in milliseconds
            bot_name: Which bot created this entry (multi-agent)
            triggered_by: Who triggered this action (multi-agent)
            
        Returns:
            The created WorkLogEntry
        """
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=level,
            step=len(self.entries) + 1,
            category=category,
            message=message,
            details=details or {},
            confidence=confidence,
            duration_ms=duration_ms,
            # Multi-agent context from parent log
            room_id=self.room_id,
            room_type=self.room_type,
            participants=self.participants.copy(),
            bot_name=bot_name,
            triggered_by=triggered_by,
            coordinator_mode=(self.coordinator is not None)
        )
        self.entries.append(entry)
        return entry
    
    def add_tool_entry(self, tool_name: str, tool_input: dict,
                       tool_output: Any, tool_status: str,
                       duration_ms: int, message: Optional[str] = None,
                       bot_name: str = "nanobot") -> WorkLogEntry:
        """Add a tool execution entry.
        
        Args:
            tool_name: Name of the tool that was executed
            tool_input: Input parameters to the tool
            tool_output: Result from the tool
            tool_status: Execution status ("success", "error", etc.)
            duration_ms: How long the tool took to execute
            message: Optional custom message (defaults to tool name)
            bot_name: Which bot executed this tool (multi-agent)
            
        Returns:
            The created WorkLogEntry
        """
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.TOOL,
            step=len(self.entries) + 1,
            category="tool_execution",
            message=message or f"Executed {tool_name}",
            duration_ms=duration_ms,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            tool_status=tool_status,
            # Multi-agent context from parent log
            room_id=self.room_id,
            room_type=self.room_type,
            participants=self.participants.copy(),
            bot_name=bot_name,
            coordinator_mode=(self.coordinator is not None)
        )
        self.entries.append(entry)
        return entry
    
    def add_bot_message(self, bot_name: str, message: str,
                       response_to: Optional[int] = None,
                       mentions: Optional[List[str]] = None) -> WorkLogEntry:
        """Add a bot-to-bot conversation entry (multi-agent).
        
        Args:
            bot_name: Name of the bot sending the message
            message: The message content
            response_to: Step number this responds to (for threading)
            mentions: List of bot mentions ["@researcher", "@coder"]
            
        Returns:
            The created WorkLogEntry
        """
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            step=len(self.entries) + 1,
            category="bot_conversation",
            message=f"{bot_name}: {message}",
            bot_name=bot_name,
            triggered_by=bot_name,
            response_to=response_to,
            mentions=mentions or [],
            # Multi-agent context from parent log
            room_id=self.room_id,
            room_type=self.room_type,
            participants=self.participants.copy(),
            coordinator_mode=(self.coordinator is not None)
        )
        self.entries.append(entry)
        return entry
    
    def add_escalation(self, reason: str, bot_name: str = "nanobot") -> WorkLogEntry:
        """Log an escalation that needs user attention (multi-agent).
        
        Args:
            reason: Why this needs user attention
            bot_name: Which bot triggered the escalation
            
        Returns:
            The created WorkLogEntry
        """
        entry = WorkLogEntry(
            timestamp=datetime.now(),
            level=LogLevel.COORDINATION,
            step=len(self.entries) + 1,
            category="escalation",
            message=f"🚨 Escalation: {reason}",
            bot_name=bot_name,
            triggered_by=bot_name,
            coordinator_mode=True,
            escalation=True,
            # Multi-agent context from parent log
            room_id=self.room_id,
            room_type=self.room_type,
            participants=self.participants.copy()
        )
        self.entries.append(entry)
        return entry
    
    def get_entries_by_level(self, level: LogLevel) -> List[WorkLogEntry]:
        """Get all entries of a specific level.
        
        Args:
            level: The log level to filter by
            
        Returns:
            List of matching entries
        """
        return [e for e in self.entries if e.level == level]
    
    def get_entries_by_category(self, category: str) -> List[WorkLogEntry]:
        """Get all entries of a specific category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of matching entries
        """
        return [e for e in self.entries if e.category == category]
    
    def get_entries_by_bot(self, bot_name: str) -> List[WorkLogEntry]:
        """Get all entries from a specific bot (multi-agent).
        
        Args:
            bot_name: The bot name to filter by
            
        Returns:
            List of matching entries
        """
        return [e for e in self.entries if e.bot_name == bot_name]
    
    def get_errors(self) -> List[WorkLogEntry]:
        """Get all error entries.
        
        Returns:
            List of error entries
        """
        return self.get_entries_by_level(LogLevel.ERROR)
    
    def get_decisions(self) -> List[WorkLogEntry]:
        """Get all decision entries.
        
        Returns:
            List of decision entries
        """
        return self.get_entries_by_level(LogLevel.DECISION)
    
    def get_tool_calls(self) -> List[WorkLogEntry]:
        """Get all tool execution entries.
        
        Returns:
            List of tool execution entries
        """
        return [e for e in self.entries if e.is_tool_entry()]
    
    def get_bot_conversations(self) -> List[WorkLogEntry]:
        """Get all bot-to-bot conversation entries (multi-agent).
        
        Returns:
            List of bot conversation entries
        """
        return [e for e in self.entries if e.is_bot_conversation()]
    
    def get_duration_ms(self) -> Optional[int]:
        """Get total duration of the session in milliseconds.
        
        Returns:
            Duration in milliseconds, or None if session hasn't ended
        """
        if not self.end_time:
            return None
        return int((self.end_time - self.start_time).total_seconds() * 1000)
    
    def to_dict(self) -> dict:
        """Convert work log to dictionary for serialization.
        
        Returns:
            Dictionary representation of the work log
        """
        return {
            # Core fields
            "session_id": self.session_id,
            "query": self.query,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "final_output": self.final_output,
            "entry_count": len(self.entries),
            "duration_ms": self.get_duration_ms(),
            # Multi-agent fields
            "room_id": self.room_id,
            "room_type": self.room_type.value,
            "participants": self.participants,
            "coordinator": self.coordinator,
            "entries": [e.to_dict() for e in self.entries]
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert work log to JSON string.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)
