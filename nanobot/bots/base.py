"""Base class for all specialist bots."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from nanobot.models.role_card import RoleCard
from nanobot.models.workspace import Workspace


class SpecialistBot(ABC):
    """Abstract base class for all bot implementations."""

    def __init__(self, role_card: RoleCard):
        """Initialize a bot with a role card.
        
        Args:
            role_card: Role card defining bot's personality and constraints
        """
        self.role_card = role_card
        self.private_memory: Dict[str, Any] = {
            "learnings": [],  # Lessons learned by this bot
            "expertise_domains": [],  # Domains where bot is competent
            "mistakes": [],  # Errors and how they were recovered
            "confidence": 0.7,  # Self-assessed competence (0.0-1.0)
            "created_at": datetime.now().isoformat(),
        }

    @property
    def name(self) -> str:
        """Get bot name."""
        return self.role_card.bot_name

    @property
    def domain(self) -> str:
        """Get bot domain."""
        return self.role_card.domain.value

    @property
    def title(self) -> str:
        """Get bot title."""
        return self.role_card.title

    def can_perform_action(self, action: str) -> tuple[bool, Optional[str]]:
        """Validate if bot can perform an action (check hard bans).
        
        Args:
            action: Action description
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        return self.role_card.validate_action(action)

    def get_greeting(self, workspace: Optional[Workspace] = None) -> str:
        """Get bot's greeting for a workspace.
        
        Args:
            workspace: Workspace context (optional)
            
        Returns:
            Greeting message
        """
        return self.role_card.greeting

    def record_learning(self, lesson: str, confidence: float = 0.7) -> None:
        """Record a private learning.
        
        Args:
            lesson: What was learned
            confidence: How confident in this learning (0.0-1.0)
        """
        self.private_memory["learnings"].append({
            "lesson": lesson,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })

    def record_mistake(self, error: str, recovery: str, lesson: Optional[str] = None) -> None:
        """Record a mistake and how it was recovered.
        
        Args:
            error: What went wrong
            recovery: How the error was fixed
            lesson: Optional lesson learned
        """
        record = {
            "error": error,
            "recovery": recovery,
            "timestamp": datetime.now().isoformat(),
        }
        if lesson:
            record["lesson"] = lesson
        
        self.private_memory["mistakes"].append(record)

    def add_expertise(self, domain: str) -> None:
        """Add a domain to bot's expertise.
        
        Args:
            domain: Domain name
        """
        if domain not in self.private_memory["expertise_domains"]:
            self.private_memory["expertise_domains"].append(domain)

    def update_confidence(self, delta: float) -> None:
        """Update bot's confidence level.
        
        Args:
            delta: Change in confidence (-1.0 to 1.0)
        """
        current = self.private_memory["confidence"]
        new_confidence = max(0.0, min(1.0, current + delta))
        self.private_memory["confidence"] = new_confidence

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of bot's status and learnings.
        
        Returns:
            Summary dictionary
        """
        return {
            "name": self.name,
            "domain": self.domain,
            "title": self.title,
            "learnings_count": len(self.private_memory["learnings"]),
            "mistakes_count": len(self.private_memory["mistakes"]),
            "expertise_domains": self.private_memory["expertise_domains"],
            "confidence": self.private_memory["confidence"],
            "created_at": self.private_memory["created_at"],
        }

    @abstractmethod
    async def process_message(self, message: str, workspace: Workspace) -> str:
        """Process a message and generate response.
        
        This is the main interaction method for the bot.
        
        Args:
            message: User or system message
            workspace: Workspace context
            
        Returns:
            Bot's response message
        """
        pass

    @abstractmethod
    async def execute_task(self, task: str, workspace: Workspace) -> Dict[str, Any]:
        """Execute a specific task.
        
        This is for structured task execution (not conversational).
        
        Args:
            task: Task description
            workspace: Workspace context
            
        Returns:
            Task result dictionary
        """
        pass
