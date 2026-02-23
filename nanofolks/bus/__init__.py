"""Message bus module for decoupled channel-agent communication."""

from nanofolks.bus.events import MessageEnvelope
from nanofolks.bus.queue import MessageBus

__all__ = ["MessageBus", "MessageEnvelope"]
