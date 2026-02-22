"""nanofolks Memory System

A lightweight, local-first memory system for the nanofolks AI assistant.
Provides semantic search, entity tracking, and knowledge graph capabilities.
"""

from nanofolks.memory.background import (
    ActivityTracker,
    BackgroundProcessor,
)
from nanofolks.memory.bot_memory import (
    BotExpertise,
    BotMemory,
    CrossPollination,
    SharedMemoryPool,
)
from nanofolks.memory.context import (
    ContextAssembler,
    ContextBudget,
    create_context_assembler,
)
from nanofolks.memory.embeddings import (
    EmbeddingProvider,
    cosine_similarity,
    pack_embedding,
    unpack_embedding,
)
from nanofolks.memory.extraction import (
    ExtractionResult,
    Gliner2Extractor,
    extract_entities,
)
from nanofolks.memory.graph import (
    KnowledgeGraphManager,
    create_entity_resolver,
)
from nanofolks.memory.learning import (
    FeedbackDetector,
    LearningManager,
    create_learning_manager,
)
from nanofolks.memory.models import (
    Edge,
    Entity,
    Event,
    Fact,
    Learning,
    SummaryNode,
    Topic,
)
from nanofolks.memory.preferences import (
    PreferencesAggregator,
    create_preferences_aggregator,
)
from nanofolks.memory.retrieval import (
    MemoryRetrieval,
    create_retrieval,
)
from nanofolks.memory.store import TurboMemoryStore
from nanofolks.memory.summaries import (
    SummaryTreeManager,
    create_summary_manager,
)
from nanofolks.memory.vector_index import VectorIndex

__all__ = [
    "Event",
    "Entity",
    "Edge",
    "Fact",
    "Topic",
    "SummaryNode",
    "Learning",
    "TurboMemoryStore",
    "EmbeddingProvider",
    "VectorIndex",
    "pack_embedding",
    "unpack_embedding",
    "cosine_similarity",
    "ActivityTracker",
    "BackgroundProcessor",
    "Gliner2Extractor",
    "ExtractionResult",
    "extract_entities",
    "KnowledgeGraphManager",
    "create_entity_resolver",
    "SummaryTreeManager",
    "create_summary_manager",
    "ContextAssembler",
    "ContextBudget",
    "create_context_assembler",
    "MemoryRetrieval",
    "create_retrieval",
    "LearningManager",
    "FeedbackDetector",
    "create_learning_manager",
    "PreferencesAggregator",
    "create_preferences_aggregator",
    "BotMemory",
    "SharedMemoryPool",
    "CrossPollination",
    "BotExpertise",
]
