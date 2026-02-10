"""nanobot Memory System

A lightweight, local-first memory system for the nanobot AI assistant.
Provides semantic search, entity tracking, and knowledge graph capabilities.
"""

from nanobot.memory.models import (
    Event,
    Entity,
    Edge,
    Fact,
    Topic,
    SummaryNode,
    Learning,
)
from nanobot.memory.store import MemoryStore
from nanobot.memory.embeddings import (
    EmbeddingProvider,
    pack_embedding,
    unpack_embedding,
    cosine_similarity,
)

__all__ = [
    "Event",
    "Entity",
    "Edge",
    "Fact",
    "Topic",
    "SummaryNode",
    "Learning",
    "MemoryStore",
    "EmbeddingProvider",
    "pack_embedding",
    "unpack_embedding",
    "cosine_similarity",
]
