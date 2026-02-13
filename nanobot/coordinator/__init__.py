"""Coordinator module for multi-agent orchestration.

Provides inter-bot communication, task delegation, and team coordination.
"""

from nanobot.coordinator.models import (
    BotMessage,
    MessageType,
    Task,
    TaskStatus,
    TaskPriority,
    TaskDependency,
    ConversationContext,
    CoordinationEvent,
)
from nanobot.coordinator.bus import InterBotBus
from nanobot.coordinator.coordinator_bot import CoordinatorBot
from nanobot.coordinator.store import CoordinatorStore
from nanobot.coordinator.autonomous import AutonomousBotTeam, BotCollaborator

__all__ = [
    "BotMessage",
    "MessageType",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskDependency",
    "ConversationContext",
    "CoordinationEvent",
    "InterBotBus",
    "CoordinatorBot",
    "CoordinatorStore",
    "AutonomousBotTeam",
    "BotCollaborator",
]
