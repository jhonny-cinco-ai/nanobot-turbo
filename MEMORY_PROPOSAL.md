# Proposal: nanobot-turbo Memory System v2

## Executive Summary

Replace the current flat-file memory system (MEMORY.md + JSONL sessions) with a 3-layer memory architecture inspired by babyagi3, adapted for lightweight single-user deployment on modest hardware (4 cores, 8GB RAM, 150GB disk).

**Design principles:**
- No LLM calls on the hot path (context assembly is pure lookup)
- Local-first (works offline, zero ongoing cost for embeddings + extraction)
- Graceful degradation (every layer can fail independently)
- Backward-compatible (existing JSONL sessions preserved)
- Modular extractors (swap spaCy for GLiNER2 or LLM later without changing the rest)

---

## Current State

### What exists

```
User message → Session (JSONL, last 50 msgs) → System prompt
                                                  ├── MEMORY.md (agent writes manually)
                                                  ├── YYYY-MM-DD.md (agent writes manually)
                                                  ├── SOUL.md, USER.md, etc. (static)
                                                  └── Skills (static)
```

### Key limitations
- Agent must manually decide to write to MEMORY.md (passive memory)
- Hard cutoff at 50 messages, no summarization of dropped messages
- No entity tracking, no relationship mapping, no semantic search
- No automatic learning from user feedback
- Tool calls and reasoning chains are discarded after each request
- No cross-session context (Telegram can't see CLI history)
- `get_recent_memories(days=7)` exists but is never called (dead code)
- No configurable context budget (everything concatenated blindly)

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: Event Log                        │
│  Immutable record of ALL interactions                        │
│  SQLite table: events                                        │
│  Fields: timestamp, channel, direction, event_type,          │
│          content, content_embedding, session_key,            │
│          parent_event_id, extraction_status                  │
│  Stores: user msgs, assistant msgs, tool calls, tool results │
└─────────────────────┬───────────────────────────────────────┘
                      │ Background extraction (every 60s)
                      │ spaCy NER + heuristic SVO + optional API fallback
                      v
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2: Knowledge Graph                  │
│  Structured knowledge extracted from events                  │
│  SQLite tables: entities, edges, facts, topics               │
│  Entities: people, orgs, tools, concepts (with embeddings)   │
│  Edges: relationships between entities (with strength)       │
│  Facts: subject-predicate-object triplets                    │
│  Topics: theme clusters linked to events                     │
└─────────────────────┬───────────────────────────────────────┘
                      │ Staleness-driven refresh
                      │ Batch summarization when threshold reached
                      v
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: Hierarchical Summaries            │
│  Pre-computed summaries organized as a tree                  │
│  SQLite table: summary_nodes                                 │
│  Tree: root → channel → entity_type → entity/topic           │
│  Special node: user_preferences (always in context)          │
│  Staleness counter per node, refresh when > 10 new events    │
└─────────────────────────────────────────────────────────────┘
          │
          │ Context assembly (no LLM calls, pure lookup)
          v
┌─────────────────────────────────────────────────────────────┐
│                    CONTEXT BUDGET                             │
│  Per-section token allocation (~4000 tokens total)           │
│  identity: 200  │ state: 150   │ knowledge: 500              │
│  channel: 300   │ entity: 400  │ topics: 400                 │
│  user_prefs: 300│ learnings: 200│ recent: 400                │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Storage: SQLite

```
~/.nanobot/workspace/memory/memory.db
```

Single file, zero config, perfect for single-user. Tables:
- `events` - Immutable event log
- `entities` - People, orgs, concepts
- `edges` - Relationships between entities
- `facts` - Subject-predicate-object triplets
- `topics` - Theme clusters
- `event_topics` - Junction table
- `summary_nodes` - Hierarchical summary tree
- `learnings` - Self-improvement records

### Embeddings: Local-first via FastEmbed

```
Model: BAAI/bge-small-en-v1.5
Size: 67MB on disk
RAM: ~200-400MB at runtime
Dimensions: 384
Quality: MTEB 62.2 (comparable to OpenAI text-embedding-3-small)
Runtime: ONNX (no PyTorch)
Fallback: qwen/qwen3-embedding-0.6b via OpenRouter ($0.01/M tokens)
```

New dependency: `fastembed` (~50MB install, pulls `onnxruntime` + `tokenizers` + `numpy`)

### Extraction: spaCy + Heuristics + Optional API

```
Layer 1: spaCy en_core_web_sm (12MB model, ~50MB RAM)
  → NER: PERSON, ORG, GPE, DATE, MONEY, etc. (18 types)
  → Dependency parsing for SVO relationship extraction
  → Speed: ~10,000 docs/sec

Layer 2: Heuristic relationship rules (~0MB)
  → Pattern matching: "X works at Y", "X likes Y", "X is Y's Z"
  → Covers ~60-70% of conversational relationships

Layer 3: Cheap API fallback (optional, configurable)
  → For complex extractions the heuristics can't handle
  → Uses existing LLM classifier model (gpt-5-nano or similar)
  → Can be disabled entirely for zero-cost operation
```

New dependency: `spacy` + `en_core_web_sm` model (~60MB total)

### RAM Budget

| Component | RAM | Notes |
|-----------|-----|-------|
| OS + Python + Bot | ~500MB-1GB | Existing |
| FastEmbed + bge-small | ~200-400MB | New |
| spaCy en_core_web_sm | ~50-80MB | New |
| SQLite memory.db | ~10-50MB | New |
| **Total system** | **~1.5-2GB** | |
| **Free RAM** | **~6-6.5GB** | |

---

## Data Models

### Event

```python
@dataclass
class Event:
    id: str                    # UUID
    timestamp: datetime
    channel: str               # cli, telegram, whatsapp, system
    direction: str             # inbound, outbound, internal
    event_type: str            # message, tool_call, tool_result, observation
    content: str               # Raw text
    content_embedding: bytes | None  # Packed float32 vector (384 dims)
    session_key: str           # channel:chat_id
    parent_event_id: str | None     # For threading (tool_result → tool_call)
    person_id: str | None      # Entity ID of the person involved
    tool_name: str | None      # For tool_call/tool_result events
    extraction_status: str     # pending, complete, skipped, failed
    metadata: dict             # Flexible extra data
```

### Entity

```python
@dataclass
class Entity:
    id: str                    # UUID
    name: str                  # Canonical name
    entity_type: str           # person, org, location, concept, tool, topic
    aliases: list[str]         # Alternative names
    description: str           # Brief description
    name_embedding: bytes | None
    source_event_ids: list[str]
    event_count: int           # How many events mention this entity
    first_seen: datetime
    last_seen: datetime
```

### Edge (Relationship)

```python
@dataclass
class Edge:
    id: str
    source_entity_id: str      # Entity A
    target_entity_id: str      # Entity B
    relation: str              # "works at", "likes", "knows"
    relation_type: str         # professional, social, technical, etc.
    strength: float            # 0.0-1.0 (incremented on re-mention)
    source_event_ids: list[str]
    first_seen: datetime
    last_seen: datetime
```

### Fact

```python
@dataclass
class Fact:
    id: str
    subject_entity_id: str
    predicate: str             # "prefers", "lives in", "is expert in"
    object_text: str           # Literal value or entity reference
    object_entity_id: str | None
    fact_type: str             # relation, attribute, preference, state
    confidence: float
    strength: float            # Incremented on re-mention
    source_event_ids: list[str]
    valid_from: datetime | None
    valid_to: datetime | None  # For temporal facts
```

### SummaryNode

```python
@dataclass
class SummaryNode:
    id: str
    node_type: str             # root, channel, entity, entity_type, topic, preferences
    key: str                   # "root", "channel:telegram", "entity:{id}", "user_preferences"
    parent_id: str | None
    summary: str               # LLM-generated text
    summary_embedding: bytes | None
    events_since_update: int   # Staleness counter
    last_updated: datetime
```

### Learning

```python
@dataclass
class Learning:
    id: str
    content: str               # The insight
    content_embedding: bytes | None
    source: str                # user_feedback, self_evaluation
    sentiment: str             # positive, negative, neutral
    confidence: float
    tool_name: str | None      # Tool-specific learning
    recommendation: str        # Actionable instruction
    superseded_by: str | None  # Contradiction resolution
    created_at: datetime
    updated_at: datetime       # For decay calculation (14-day half-life)
```

---

## Implementation Plan

### Phase 1: Foundation (SQLite + Event Log)
**Estimated effort: 3-5 days**

New files:
- `nanobot/memory/__init__.py` - Module exports
- `nanobot/memory/models.py` - All dataclasses above
- `nanobot/memory/store.py` - SQLite database manager (create tables, CRUD operations)
- `nanobot/memory/events.py` - Event logging (write events, query events)

Changes to existing files:
- `nanobot/agent/loop.py` - After each message exchange, log events to SQLite (user message, assistant response, all tool calls and results)
- `pyproject.toml` - No new dependencies for Phase 1 (SQLite is built-in)

What this gives you:
- Complete, immutable record of all interactions
- Tool calls and reasoning chains preserved (currently discarded)
- Cross-session queryable history (all channels in one DB)
- Foundation for all subsequent phases

Backward compatibility:
- Existing JSONL session manager continues to work unchanged
- Events are logged IN ADDITION to JSONL (dual-write)
- No existing behavior changes

### Phase 2: Embeddings + Semantic Search
**Estimated effort: 2-3 days**

New files:
- `nanobot/memory/embeddings.py` - Embedding provider (local FastEmbed + API fallback)

Changes to existing files:
- `nanobot/memory/store.py` - Add embedding columns, cosine similarity search
- `nanobot/memory/events.py` - Embed event content on write
- `pyproject.toml` - Add `fastembed` dependency
- `nanobot/config/schema.py` - Add `MemoryConfig` with embedding settings

What this gives you:
- Semantic search over all past conversations
- "Search your memory for anything about pricing" actually works
- Foundation for knowledge graph extraction (needs embeddings for entity resolution)

### Phase 3: Knowledge Graph Extraction
**Estimated effort: 5-7 days**

New files:
- `nanobot/memory/extraction.py` - Background extraction pipeline
- `nanobot/memory/graph.py` - Entity resolution, edge management, fact deduplication
- `nanobot/memory/extractors/spacy_extractor.py` - spaCy NER + SVO extraction
- `nanobot/memory/extractors/heuristic_extractor.py` - Pattern-based relationship rules
- `nanobot/memory/extractors/api_extractor.py` - Optional LLM fallback extractor

Changes to existing files:
- `nanobot/agent/loop.py` - Start background extraction task on agent startup
- `pyproject.toml` - Add `spacy` dependency
- `nanobot/config/schema.py` - Add extraction config (interval, batch size, API fallback toggle)

What this gives you:
- Automatic entity tracking (people, orgs, concepts mentioned in conversations)
- Relationship mapping ("John works at Acme Corp")
- Fact storage ("User prefers short emails")
- Background processing that doesn't slow down chat

Extraction pipeline:
```
Every 60 seconds:
  1. Check if user is actively chatting → back off if yes
  2. Fetch up to 20 pending events
  3. For each event:
     a. spaCy NER → extract entities (PERSON, ORG, etc.)
     b. spaCy dependency parse → extract SVO relationships
     c. Heuristic patterns → extract additional relationships
     d. If confidence is low and API fallback enabled → batch for LLM extraction
  4. Resolve entities (merge duplicates, update aliases)
  5. Create/update edges with strength tracking
  6. Store facts with deduplication
  7. Mark events as extraction_status = "complete"
```

### Phase 4: Hierarchical Summaries
**Estimated effort: 4-6 days**

New files:
- `nanobot/memory/summaries.py` - Summary tree management, staleness tracking, refresh logic

Changes to existing files:
- `nanobot/memory/extraction.py` - After extraction, increment staleness counters on relevant summary nodes
- `nanobot/memory/extraction.py` - After extraction batch, trigger stale summary refresh

What this gives you:
- Pre-computed summaries for fast context assembly
- "What do you know about John Smith?" returns a summary, not raw events
- Summaries automatically refresh when enough new information accumulates
- Tree structure allows drill-down (root → channel → entity)

Summary refresh strategy:
```
Staleness threshold: 10 events since last update
Refresh priority: leaf nodes first (entity, topic), then branches, then root
Leaf refresh: Fetch 30 source events + previous summary → LLM generates new summary
Branch refresh: Synthesize from child summaries (no direct event access)
Root refresh: High-level overview from top-level children

Note: This is the ONE place that requires LLM calls in the memory system.
Uses the existing LLM classifier model (cheap, batched, background-only).
```

### Phase 5: Learning + User Preferences
**Estimated effort: 3-5 days**

New files:
- `nanobot/memory/learning.py` - Feedback detection, learning storage, contradiction resolution
- `nanobot/memory/preferences.py` - Aggregate learnings into user_preferences summary

Changes to existing files:
- `nanobot/memory/extraction.py` - Add feedback detection to extraction pipeline
- `nanobot/memory/summaries.py` - Add special `user_preferences` node (always in context)

What this gives you:
- Bot learns from corrections: "Actually, I prefer shorter emails"
- Preferences persist across sessions and channels
- 14-day decay with re-boost (useful learnings survive, stale ones fade)
- Contradiction resolution (new preference supersedes old one, with audit trail)
- `user_preferences` summary always included in system prompt (~300 tokens)

### Phase 6: Context Assembly + Retrieval
**Estimated effort: 3-4 days**

New files:
- `nanobot/memory/context.py` - Token-budgeted context assembly from summaries
- `nanobot/memory/retrieval.py` - Query interface (entity lookup, semantic search, graph traversal)

Changes to existing files:
- `nanobot/agent/context.py` - Replace current `get_memory_context()` with summary-based assembly
- `nanobot/agent/loop.py` - Register memory tools (search_memory, get_entity, etc.)

New agent tools:
- `search_memory` - Semantic search over events, entities, facts
- `get_entity` - Look up everything known about a person/org/concept
- `get_relationships` - Find connections between entities
- `recall` - Retrieve relevant context for a topic

What this gives you:
- Smart context assembly that respects token budgets
- Agent can actively query its own memory
- User can ask "What do you know about X?" and get a real answer

Context budget allocation:
```
Section              Budget    Condition
─────────────────────────────────────────
Identity             200 tok   Always
State/time           150 tok   Always
Knowledge (root)     500 tok   Always
Recent activity      400 tok   Always
Channel context      300 tok   If channel known
Entity context       400 tok   If person identified
Topics               400 tok   If current topics
User preferences     300 tok   Always (if available)
Tool learnings       200 tok   If tool-specific context
─────────────────────────────────────────
Total               ~3850 tok
```

### Phase 7: CLI Commands + Testing
**Estimated effort: 2-3 days**

Changes to existing files:
- `nanobot/cli/commands.py` - Add memory subcommands

New CLI commands:
```bash
nanobot memory status          # Show memory stats (events, entities, summaries)
nanobot memory search "query"  # Semantic search
nanobot memory entities        # List known entities
nanobot memory entity "John"   # Show everything about John
nanobot memory summary         # Show root summary
nanobot memory forget "entity" # Remove an entity and related data
nanobot memory export          # Export memory to JSON
nanobot memory import file.json # Import memory from JSON
```

New test files:
- `tests/memory/test_store.py` - SQLite CRUD operations
- `tests/memory/test_events.py` - Event logging and querying
- `tests/memory/test_embeddings.py` - Embedding generation and search
- `tests/memory/test_extraction.py` - Entity/relationship extraction
- `tests/memory/test_summaries.py` - Summary tree and staleness
- `tests/memory/test_learning.py` - Feedback detection and contradiction resolution
- `tests/memory/test_context.py` - Token-budgeted context assembly

---

## Configuration Schema

```python
class MemoryConfig(BaseModel):
    """Configuration for the memory system."""
    enabled: bool = True
    db_path: str = "memory/memory.db"  # Relative to workspace

    class EmbeddingConfig(BaseModel):
        provider: str = "local"        # "local" or "api"
        local_model: str = "BAAI/bge-small-en-v1.5"
        api_model: str = "qwen/qwen3-embedding-0.6b"
        api_fallback: bool = True      # Fall back to API if local fails
        cache_embeddings: bool = True

    class ExtractionConfig(BaseModel):
        enabled: bool = True
        interval_seconds: int = 60
        batch_size: int = 20
        spacy_model: str = "en_core_web_sm"
        api_fallback: bool = False     # Use LLM for complex extractions
        api_model: str = ""            # Uses LLM classifier model if empty
        activity_backoff: bool = True  # Back off when user is chatting

    class SummaryConfig(BaseModel):
        staleness_threshold: int = 10  # Events before refresh
        max_refresh_batch: int = 20    # Max nodes to refresh per cycle
        model: str = ""                # Uses LLM classifier model if empty

    class LearningConfig(BaseModel):
        enabled: bool = True
        decay_days: int = 14           # Half-life for learning relevance
        max_learnings: int = 200       # Max active learnings

    class ContextConfig(BaseModel):
        total_budget: int = 4000       # Total token budget for memory context
        always_include_preferences: bool = True

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
```

Example config.json addition:
```json
{
  "memory": {
    "enabled": true,
    "embedding": {
      "provider": "local",
      "api_fallback": true
    },
    "extraction": {
      "enabled": true,
      "interval_seconds": 60,
      "api_fallback": false
    },
    "learning": {
      "enabled": true,
      "decay_days": 14
    }
  }
}
```

---

## New Dependencies

| Package | Size | Purpose | Phase |
|---------|------|---------|-------|
| `fastembed` | ~50MB install | Local embeddings (ONNX) | Phase 2 |
| `spacy` | ~30MB install | NER + dependency parsing | Phase 3 |
| `en_core_web_sm` | ~12MB model | spaCy English model | Phase 3 |

Total new disk: ~90MB
Total new RAM: ~250-480MB

No PyTorch, no TensorFlow, no GPU required.

---

## Migration Strategy

### Existing JSONL sessions
- Continue to work unchanged (dual-write approach)
- New events are logged to SQLite AND JSONL
- JSONL remains the source for `Session.get_history()` (sliding window)
- SQLite becomes the source for semantic search, entity queries, and summaries
- Optional future: one-time migration script to import historical JSONL into SQLite events

### Existing MEMORY.md + daily notes
- Continue to work as before
- Content from MEMORY.md is imported into the knowledge graph as facts/entities on first run
- Daily notes are imported as events on first run
- After migration, new memories go to SQLite; old files remain readable

### Existing bootstrap files (SOUL.md, USER.md, etc.)
- Unchanged. These are static identity files, not memory.
- Over time, `user_preferences` summary node may partially replace USER.md with learned preferences.

---

## File Map (New Files)

```
nanobot/memory/
├── __init__.py              # Module exports
├── models.py                # Event, Entity, Edge, Fact, Topic, SummaryNode, Learning
├── store.py                 # SQLite database manager (tables, CRUD, migrations)
├── events.py                # Event logging and querying
├── embeddings.py            # FastEmbed local + API fallback
├── graph.py                 # Entity resolution, edges, facts, dedup
├── extraction.py            # Background extraction pipeline + scheduling
├── extractors/
│   ├── __init__.py
│   ├── base.py              # Extractor interface
│   ├── spacy_extractor.py   # spaCy NER + SVO
│   ├── heuristic_extractor.py # Pattern-based relationships
│   └── api_extractor.py     # Optional LLM fallback
├── summaries.py             # Summary tree, staleness, refresh
├── learning.py              # Feedback detection, decay, contradictions
├── preferences.py           # User preferences aggregation
├── context.py               # Token-budgeted context assembly
└── retrieval.py             # Query interface (search, lookup, traverse)

tests/memory/
├── __init__.py
├── test_store.py
├── test_events.py
├── test_embeddings.py
├── test_extraction.py
├── test_summaries.py
├── test_learning.py
└── test_context.py
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SQLite write contention from background extraction during chat | Chat latency | Activity-aware throttling: back off extraction when user is chatting |
| spaCy extraction quality too low for relationships | Poor knowledge graph | Modular extractor interface: swap in GLiNER2 or LLM later without changing the rest |
| Embedding model too large for some environments | Won't start | Configurable: disable local embeddings, use API-only, or disable entirely |
| Summary refresh costs money (LLM calls) | Ongoing cost | Uses cheapest available model; configurable threshold; can disable entirely |
| Memory.db grows too large | Disk space | Configurable retention policy (default 365 days / 100K events) |
| Breaking changes to context builder | Regression | Dual-mode: old context builder path preserved behind feature flag |

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|-------------|
| Phase 1: Foundation (SQLite + Events) | 3-5 days | None |
| Phase 2: Embeddings + Search | 2-3 days | Phase 1 |
| Phase 3: Knowledge Graph | 5-7 days | Phase 2 |
| Phase 4: Hierarchical Summaries | 4-6 days | Phase 3 |
| Phase 5: Learning + Preferences | 3-5 days | Phase 4 |
| Phase 6: Context Assembly + Retrieval | 3-4 days | Phase 4, 5 |
| Phase 7: CLI + Testing | 2-3 days | All phases |
| **Total** | **22-33 days** | |

Phases 1-3 are the core. After Phase 3, you have a working memory system with event logging, semantic search, and automatic entity/relationship extraction. Phases 4-7 add polish and sophistication.

---

## Success Criteria

After full implementation:

1. **"What do you know about John?"** - Returns structured entity summary with relationships, not "I don't have memory of that"
2. **"Actually, I prefer shorter responses"** - Creates a learning record, reflected in future responses via `user_preferences`
3. **Greeting "hi" after a week** - Bot recalls recent topics, ongoing tasks, and user preferences from memory
4. **Cross-channel continuity** - Information shared on Telegram is available when chatting via CLI
5. **Zero-cost baseline** - With API fallback disabled, the entire memory system runs locally at $0/month
6. **RAM under 2.5GB total** - Memory infrastructure uses <500MB on top of existing bot

---

## References

- [babyagi3 memory system](https://github.com/yoheinakajima/babyagi3/tree/main/memory) - Inspiration for 3-layer architecture
- [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5) - Local embedding model
- [FastEmbed](https://github.com/qdrant/fastembed) - ONNX-based embedding runtime
- [spaCy en_core_web_sm](https://spacy.io/models/en#en_core_web_sm) - NER + dependency parsing
- [qwen/qwen3-embedding-0.6b](https://openrouter.ai/qwen/qwen3-embedding-0.6b) - API embedding fallback

---

**Last Updated**: 2026-02-10
**Status**: Proposal - Pending Approval
**Author**: nanobot-turbo development team
