"""Data models for inter-bot coordination.

Defines messages, tasks, and other structures for bot collaboration.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MessageType(str, Enum):
    """Types of messages between bots."""
    REQUEST = "request"           # Bot requesting help from another
    RESPONSE = "response"         # Direct response to a request
    REPORT = "report"             # Status update or completion report
    DISCUSSION = "discussion"     # Contribution to team discussion
    BROADCAST = "broadcast"       # Message to all bots
    CLARIFICATION = "clarification"  # Request for clarification
    AGREEMENT = "agreement"       # Agreement with a proposal
    DISAGREEMENT = "disagreement" # Disagreement with a proposal


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"           # Waiting to be assigned
    ASSIGNED = "assigned"         # Assigned to a bot
    IN_PROGRESS = "in_progress"   # Bot is working on it
    BLOCKED = "blocked"           # Waiting for dependencies
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Failed to complete
    CANCELLED = "cancelled"       # User or system cancelled


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 3
    HIGH = 5


@dataclass
class BotMessage:
    """Message between bots.
    
    Messages enable bots to:
    - Request help from each other
    - Share findings and opinions
    - Coordinate on tasks
    - Discuss decisions
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""           # Bot ID of sender
    recipient_id: str = "team"    # Bot ID or "team" for broadcast
    message_type: MessageType = MessageType.REQUEST
    content: str = ""             # The message text
    conversation_id: str = ""     # Thread ID for grouping
    context: Dict[str, Any] = field(default_factory=dict)  # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    
    # For responses, reference original request
    response_to_id: Optional[str] = None
    
    def __post_init__(self):
        """Ensure conversation_id is set."""
        if not self.conversation_id:
            self.conversation_id = str(uuid.uuid4())


@dataclass
class Task:
    """A unit of work to be completed.
    
    Tasks can be assigned to individual bots or decomposed into sub-tasks.
    Track status, dependencies, and results.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    domain: str = ""              # research, development, community, etc.
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Assignment
    assigned_to: Optional[str] = None  # Bot ID
    created_by: Optional[str] = None   # Who created the task
    
    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    
    # Requirements and constraints
    requirements: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    result: str = ""
    confidence: float = 0.5       # How confident in the result (0.0-1.0)
    
    # Relationships
    parent_task_id: Optional[str] = None  # For sub-tasks
    learnings: List[str] = field(default_factory=list)  # What was learned
    follow_ups: List[str] = field(default_factory=list)  # New tasks discovered
    
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date or self.status == TaskStatus.COMPLETED:
            return False
        return datetime.now() > self.due_date
    
    def time_elapsed(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
    
    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def mark_completed(self, result: str, confidence: float = 0.9) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result = result
        self.confidence = confidence
    
    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.result = error
        self.confidence = 0.0


@dataclass
class TaskDependency:
    """Dependency between tasks.
    
    Task A depends on Task B means B must complete before A can start.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""              # The dependent task
    depends_on_task_id: str = ""   # The prerequisite task


@dataclass
class ConversationContext:
    """Context for a conversation thread.
    
    Tracks the thread of messages between bots to maintain context.
    """
    conversation_id: str = ""
    initiated_by: str = ""         # Bot that started the conversation
    subject: str = ""              # What is being discussed
    messages: List[BotMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_message_at: datetime = field(default_factory=datetime.now)
    participants: List[str] = field(default_factory=list)  # Bot IDs
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: BotMessage) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)
        self.last_message_at = message.timestamp
        
        # Track participants
        if message.sender_id not in self.participants:
            self.participants.append(message.sender_id)
        if message.recipient_id != "team" and message.recipient_id not in self.participants:
            self.participants.append(message.recipient_id)
    
    def get_summary(self) -> str:
        """Get a summary of the conversation."""
        if not self.messages:
            return f"Conversation: {self.subject} (no messages)"
        
        summary_parts = [
            f"Conversation: {self.subject}",
            f"Initiated by: {self.initiated_by}",
            f"Participants: {', '.join(self.participants)}",
            f"Messages: {len(self.messages)}",
        ]
        return "\n".join(summary_parts)


@dataclass
class CoordinationEvent:
    """Record of a coordination action.
    
    Logs when coordination happens for transparency and learning.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""           # "task_assigned", "message_sent", "decision_made", etc.
    initiator: str = ""            # Bot that initiated
    involved_bots: List[str] = field(default_factory=list)  # All bots involved
    task_id: Optional[str] = None
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
