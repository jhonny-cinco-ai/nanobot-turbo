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

## Detailed Design: Entity Resolution Algorithm

Entity resolution is the core deduplication mechanism in Phase 3 (Knowledge Graph Extraction). It prevents the knowledge graph from fragmenting into redundant entities ("John", "john", "John Smith", "J. Smith" should all resolve to one canonical entity).

### Design Goals

1. **High precision** (false positive merges are worse than false negatives)
2. **Fast execution** (<50ms p99 for typical workloads)
3. **No LLM calls on hot path** (everything is heuristic or embedding-based)
4. **Progressive resolution** (cheap fast checks first, expensive checks only when necessary)
5. **Auditable** (track why entities were merged, support manual correction)

### Resolution Pipeline (5 Layers)

```
New mention → Layer 1: Rule-based exact/case-insensitive match
           → Layer 2: Fuzzy string matching (Levenshtein)
           → Layer 3: Semantic embedding similarity
           → Layer 4: Contextual scoring (shared relationships)
           → Layer 5: LLM fallback (optional, batched, async)
           → Decision: merge, create new, or tentative
```

### Layer 1: Rule-Based Matching

**Speed**: <1ms per candidate set  
**Precision**: 100% (no false positives)  
**Coverage**: ~40-50% of mentions

```python
def rule_based_match(
    mention: str,
    mention_type: str,
    candidates: list[Entity]
) -> Entity | None:
    """
    Fast exact matching with case/whitespace normalization.
    """
    normalized = normalize_mention(mention)
    
    for entity in candidates:
        # Exact match on canonical name
        if normalize_mention(entity.name) == normalized:
            return entity
        
        # Exact match on any alias
        for alias in entity.aliases:
            if normalize_mention(alias) == normalized:
                return entity
    
    return None

def normalize_mention(text: str) -> str:
    """Normalization preserving semantic identity."""
    text = text.strip().lower()
    text = re.sub(r'\s+', ' ', text)  # Collapse whitespace
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    return text
```

### Layer 2: Fuzzy String Matching

**Speed**: ~1-5ms for 100 candidates  
**Precision**: ~85% (with tuned threshold)  
**Coverage**: +20-25% of mentions

```python
from rapidfuzz import fuzz

def fuzzy_match(
    mention: str,
    candidates: list[Entity],
    threshold: float = 0.85
) -> Entity | None:
    """
    Fuzzy string matching using Levenshtein distance.
    """
    best_entity = None
    best_score = 0.0
    
    for entity in candidates:
        # Check canonical name
        score = fuzz.ratio(mention.lower(), entity.name.lower()) / 100.0
        if score > best_score:
            best_score = score
            best_entity = entity
        
        # Check aliases
        for alias in entity.aliases:
            score = fuzz.ratio(mention.lower(), alias.lower()) / 100.0
            if score > best_score:
                best_score = score
                best_entity = entity
    
    if best_score >= threshold:
        return best_entity
    
    return None
```

**Threshold tuning**:
- PERSON: 0.85 (stricter - "John Smith" vs "Jane Smith" are different)
- ORG: 0.80 (looser - "Acme Corp" vs "Acme Corporation")
- LOCATION: 0.90 (stricter - "Paris, France" vs "Paris, Texas")
- CONCEPT: 0.75 (looser - "machine learning" vs "ML")

### Layer 3: Semantic Embedding Similarity

**Speed**: ~10-30ms for 100 candidates (with FAISS index)  
**Precision**: ~75% (embedding models can conflate similar concepts)  
**Coverage**: +15-20% of mentions

```python
import numpy as np

def semantic_match(
    mention: str,
    mention_embedding: np.ndarray,
    candidates: list[Entity],
    threshold: float = 0.80
) -> Entity | None:
    """
    Semantic similarity using cosine distance on embeddings.
    """
    best_entity = None
    best_similarity = 0.0
    
    for entity in candidates:
        if entity.name_embedding is None:
            continue
        
        # Cosine similarity
        entity_emb = unpack_embedding(entity.name_embedding)
        similarity = np.dot(mention_embedding, entity_emb) / (
            np.linalg.norm(mention_embedding) * np.linalg.norm(entity_emb)
        )
        
        if similarity > best_similarity:
            best_similarity = similarity
            best_entity = entity
    
    if best_similarity >= threshold:
        return best_entity
    
    return None
```

**Optimization**: For large entity sets (>1000), use FAISS approximate nearest neighbor search instead of brute-force.

```python
# Optional FAISS index for scaling to 10K+ entities
import faiss

class EntityIndex:
    def __init__(self, embedding_dim: int = 384):
        self.index = faiss.IndexFlatIP(embedding_dim)  # Inner product (cosine)
        self.entity_ids: list[str] = []
    
    def add(self, entity_id: str, embedding: np.ndarray):
        # Normalize for cosine similarity
        embedding = embedding / np.linalg.norm(embedding)
        self.index.add(embedding.reshape(1, -1))
        self.entity_ids.append(entity_id)
    
    def search(self, query_embedding: np.ndarray, k: int = 10) -> list[tuple[str, float]]:
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        scores, indices = self.index.search(query_embedding.reshape(1, -1), k)
        return [(self.entity_ids[i], scores[0][idx]) for idx, i in enumerate(indices[0])]
```

### Layer 4: Contextual Scoring

**Speed**: ~5-10ms (requires DB queries)  
**Precision**: ~90% (high signal)  
**Coverage**: +5-10% of mentions

```python
def contextual_match(
    mention: str,
    mention_context: dict,  # {event_id, nearby_entities, session_key}
    candidates: list[Entity],
    threshold: float = 0.70
) -> Entity | None:
    """
    Score candidates by shared context (co-occurring entities, session).
    """
    scores = {}
    
    for entity in candidates:
        score = 0.0
        
        # Boost if mentioned in same session
        if mention_context.get("session_key") in entity.metadata.get("sessions", []):
            score += 0.3
        
        # Boost if shares relationships with nearby entities
        nearby_entity_ids = mention_context.get("nearby_entities", [])
        for nearby_id in nearby_entity_ids:
            if has_edge(entity.id, nearby_id):
                score += 0.2
        
        # Boost if mentioned in recent events
        days_since_last_seen = (datetime.now() - entity.last_seen).days
        if days_since_last_seen < 7:
            score += 0.2
        
        scores[entity.id] = score
    
    best_entity = max(candidates, key=lambda e: scores.get(e.id, 0.0))
    if scores.get(best_entity.id, 0.0) >= threshold:
        return best_entity
    
    return None
```

### Layer 5: LLM Fallback (Optional)

**Speed**: ~200-2000ms (batched, async)  
**Precision**: ~95% (best, but expensive)  
**Coverage**: Remaining ~5-10% of hard cases

```python
async def llm_fallback_match(
    mention: str,
    mention_context: str,
    candidates: list[Entity],
    llm_client: LLM
) -> Entity | None:
    """
    LLM-based disambiguation for hard cases.
    Batched and async to avoid blocking.
    """
    if not candidates:
        return None
    
    prompt = f"""Given the mention "{mention}" in context:
    {mention_context}
    
    Which entity does this refer to?
    
    Candidates:
    {format_candidates(candidates)}
    
    Respond with ONLY the candidate number (1-{len(candidates)}) or "NEW" if none match.
    """
    
    response = await llm_client.complete(prompt, model="gpt-5-nano")
    
    if response.strip().upper() == "NEW":
        return None
    
    try:
        idx = int(response.strip()) - 1
        if 0 <= idx < len(candidates):
            return candidates[idx]
    except ValueError:
        pass
    
    return None
```

**Usage policy**:
- Only enabled if `extraction.api_fallback = true`
- Only used for mentions with 2+ viable candidates after Layer 4
- Batched every 60 seconds (not per-mention)
- Falls back to "create new entity" if LLM fails

### Full Resolution Flow

```python
@dataclass
class ResolutionResult:
    entity: Entity | None
    confidence: float
    method: str  # "rule", "fuzzy", "semantic", "contextual", "llm", "new"

async def resolve_entity(
    mention: str,
    mention_type: str,
    mention_embedding: np.ndarray,
    context: dict,
    config: ExtractionConfig,
    store: MemoryStore
) -> ResolutionResult:
    """
    Progressive entity resolution through 5 layers.
    """
    # Step 1: Candidate filtering (cheap, fast)
    candidates = get_candidate_entities(
        entity_type=mention_type,
        max_candidates=100,
        filters={
            "last_seen_after": datetime.now() - timedelta(days=90),
            "event_count_min": 2  # Skip one-off entities
        }
    )
    
    if not candidates:
        return ResolutionResult(None, 1.0, "new")
    
    # Step 2: Layer 1 - Rule-based
    entity = rule_based_match(mention, mention_type, candidates)
    if entity:
        return ResolutionResult(entity, 1.0, "rule")
    
    # Step 3: Layer 2 - Fuzzy
    entity = fuzzy_match(mention, candidates, threshold=get_threshold(mention_type))
    if entity:
        return ResolutionResult(entity, 0.85, "fuzzy")
    
    # Step 4: Layer 3 - Semantic
    entity = semantic_match(mention, mention_embedding, candidates, threshold=0.80)
    if entity:
        return ResolutionResult(entity, 0.75, "semantic")
    
    # Step 5: Layer 4 - Contextual
    entity = contextual_match(mention, context, candidates, threshold=0.70)
    if entity:
        return ResolutionResult(entity, 0.80, "contextual")
    
    # Step 6: Layer 5 - LLM fallback (optional, async)
    if config.api_fallback and len(candidates) <= 5:
        entity = await llm_fallback_match(mention, context, candidates, store.llm_client)
        if entity:
            return ResolutionResult(entity, 0.95, "llm")
    
    # Step 7: Create new entity
    return ResolutionResult(None, 1.0, "new")
```

### Performance Optimizations

#### 1. Candidate Filtering

Don't check all entities; pre-filter by:
- Entity type (PERSON mentions only check PERSON entities)
- Recency (entities mentioned in last 90 days)
- Frequency (entities mentioned 2+ times)
- First letter (for large sets, use prefix index)

```python
def get_candidate_entities(
    entity_type: str,
    max_candidates: int = 100,
    filters: dict = None
) -> list[Entity]:
    """
    Fetch candidate entities with smart filtering.
    """
    query = """
        SELECT * FROM entities
        WHERE entity_type = ?
        AND last_seen > ?
        AND event_count >= ?
        ORDER BY event_count DESC
        LIMIT ?
    """
    # Returns top N most-mentioned entities of the right type
```

#### 2. Caching

Cache resolution results for the duration of an extraction batch:
```python
@dataclass
class ResolutionCache:
    cache: dict[str, Entity | None] = field(default_factory=dict)
    
    def get(self, mention: str, mention_type: str) -> Entity | None:
        key = f"{mention_type}:{normalize_mention(mention)}"
        return self.cache.get(key)
    
    def set(self, mention: str, mention_type: str, entity: Entity | None):
        key = f"{mention_type}:{normalize_mention(mention)}"
        self.cache[key] = entity
```

#### 3. Tentative Merges

For low-confidence matches (0.70-0.85), create "tentative" merge records instead of immediate merges. After 3+ confirmations (same mention resolves to same entity), promote to permanent.

```python
@dataclass
class TentativeMerge:
    mention: str
    entity_id: str
    confidence: float
    confirmation_count: int
    created_at: datetime
```

### Configuration Schema

```python
class EntityResolutionConfig(BaseModel):
    """Entity resolution algorithm configuration."""
    
    # Candidate filtering
    max_candidates: int = 100
    candidate_recency_days: int = 90
    candidate_min_mentions: int = 2
    
    # Layer thresholds
    fuzzy_threshold_person: float = 0.85
    fuzzy_threshold_org: float = 0.80
    fuzzy_threshold_location: float = 0.90
    fuzzy_threshold_concept: float = 0.75
    semantic_threshold: float = 0.80
    contextual_threshold: float = 0.70
    
    # Tentative merges
    tentative_threshold: float = 0.70
    tentative_confirmation_count: int = 3
    
    # LLM fallback
    llm_fallback_enabled: bool = False
    llm_fallback_max_candidates: int = 5
    
    # Performance
    use_faiss_index: bool = False  # Enable for 10K+ entities
    faiss_neighbors: int = 10
```

Example config:
```json
{
  "memory": {
    "extraction": {
      "entity_resolution": {
        "fuzzy_threshold_person": 0.85,
        "semantic_threshold": 0.80,
        "llm_fallback_enabled": false
      }
    }
  }
}
```

### Monitoring and Observability

Track resolution metrics:
```python
@dataclass
class ResolutionMetrics:
    total_resolutions: int
    method_counts: dict[str, int]  # {"rule": 450, "fuzzy": 230, ...}
    avg_latency_ms: dict[str, float]  # {"rule": 0.8, "fuzzy": 3.2, ...}
    confidence_distribution: dict[str, int]  # {"high": 600, "medium": 100, ...}
    tentative_merges: int
    false_positive_reports: int  # User-reported incorrect merges
```

CLI command to inspect:
```bash
$ nanobot memory resolution-stats
Entity Resolution Statistics (last 7 days)
─────────────────────────────────────────
Total resolutions:    1,234
  - Rule-based:       45% (avg 0.8ms)
  - Fuzzy:            28% (avg 3.2ms)
  - Semantic:         18% (avg 12ms)
  - Contextual:       7%  (avg 8ms)
  - LLM fallback:     0%  (disabled)
  - New entities:     2%

Tentative merges:     23 (awaiting confirmation)
False positives:      2 (0.16%)
```

### Testing Strategy

```python
# tests/memory/test_entity_resolution.py

def test_rule_based_exact_match():
    """Layer 1: Exact match on canonical name."""
    entity = Entity(id="1", name="John Smith", entity_type="person", aliases=[])
    result = rule_based_match("john smith", "person", [entity])
    assert result == entity

def test_fuzzy_match_nickname():
    """Layer 2: Fuzzy match for nickname."""
    entity = Entity(id="1", name="Elizabeth", entity_type="person", aliases=["Liz"])
    result = fuzzy_match("Lizzy", [entity], threshold=0.80)
    assert result == entity

def test_semantic_match_synonym():
    """Layer 3: Semantic match for synonym."""
    entity = Entity(
        id="1", 
        name="machine learning", 
        entity_type="concept",
        name_embedding=embed("machine learning")
    )
    result = semantic_match("ML", embed("ML"), [entity], threshold=0.75)
    assert result == entity

def test_no_false_positive_merge():
    """Precision: Don't merge different people with similar names."""
    john_smith = Entity(id="1", name="John Smith", entity_type="person", aliases=[])
    jane_smith = Entity(id="2", name="Jane Smith", entity_type="person", aliases=[])
    result = fuzzy_match("John Smith", [jane_smith], threshold=0.85)
    assert result is None  # Should NOT match Jane
```

### Performance Targets

| Percentile | Latency Target | Notes |
|------------|---------------|-------|
| p50 | <1ms | Rule-based fast path |
| p90 | <5ms | Fuzzy + semantic |
| p95 | <10ms | Contextual scoring |
| p99 | <50ms | Rare LLM fallback |

For 100 entity candidates:
- Layer 1 (rule): ~0.5ms
- Layer 2 (fuzzy): ~2-3ms
- Layer 3 (semantic): ~10ms (brute force) or ~2ms (FAISS)
- Layer 4 (contextual): ~5ms (requires DB queries)
- Layer 5 (LLM): ~200-2000ms (batched, async)

### Resource Requirements

**Memory**:
- Entity cache: ~10KB per 100 entities
- Embedding cache: ~1.5KB per entity (384 dims × 4 bytes)
- FAISS index (optional): ~2MB per 10K entities

**Disk**:
- SQLite indexes on entities.name, entities.entity_type, entities.last_seen

**CPU**:
- Minimal (string operations + vector dot products)
- FAISS index build: ~1-2 seconds for 10K entities (one-time)

---

## Detailed Design: Background Task Infrastructure

The memory system requires several background tasks that must NOT interfere with interactive chat:
- Entity extraction from pending events (every 60s)
- Summary node refresh when staleness threshold reached
- Tentative merge confirmation
- Learning decay and garbage collection

This design provides a lightweight task queue + worker pool that integrates with the existing asyncio event loop in `AgentLoop`.

### Design Goals

1. **Non-blocking** (chat never waits for background tasks)
2. **Activity-aware** (back off during active conversations)
3. **Priority-based** (urgent tasks like extraction > housekeeping)
4. **Graceful degradation** (task failures don't crash the agent)
5. **Observable** (metrics + logging for monitoring)
6. **Configurable** (task intervals, worker count, timeouts)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     AgentLoop                            │
│  - Main message processing loop                          │
│  - Tracks user activity (last_message_time)              │
│  - Spawns BackgroundTaskManager on startup               │
└─────────────────┬───────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────┐
│              BackgroundTaskManager                       │
│  - Registers task definitions                            │
│  - Spawns worker pool (configurable size)                │
│  - Schedules periodic tasks                              │
│  - Exposes submit_task(task) API                         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────┐
│                   TaskQueue                              │
│  - Priority queue (high → medium → low)                  │
│  - Backpressure: max 1000 pending tasks                  │
│  - Deduplication: same task type + args                  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────┐
│                  WorkerPool                              │
│  - N async workers (default: 2)                          │
│  - Each worker: get_task() → execute() → mark_done()     │
│  - Exponential backoff on task failure                   │
│  - Timeout protection (max 300s per task)                │
└─────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. ActivityTracker

Tracks user chat activity to determine when it's safe to run background tasks.

```python
from datetime import datetime, timedelta

class ActivityTracker:
    """
    Tracks user activity to implement activity-aware task scheduling.
    """
    def __init__(self, quiet_threshold_seconds: int = 30):
        self.last_message_time: datetime | None = None
        self.quiet_threshold = timedelta(seconds=quiet_threshold_seconds)
    
    def mark_activity(self):
        """Called by AgentLoop when user sends a message."""
        self.last_message_time = datetime.now()
    
    def is_user_active(self) -> bool:
        """Returns True if user has been active in the last N seconds."""
        if self.last_message_time is None:
            return False
        return datetime.now() - self.last_message_time < self.quiet_threshold
    
    def seconds_since_last_activity(self) -> float:
        """Returns seconds since last user message."""
        if self.last_message_time is None:
            return float('inf')
        return (datetime.now() - self.last_message_time).total_seconds()
```

Integration with `AgentLoop`:
```python
# nanobot/agent/loop.py

class AgentLoop:
    def __init__(self, ...):
        # Existing fields...
        self.activity_tracker = ActivityTracker(quiet_threshold_seconds=30)
        self.task_manager = BackgroundTaskManager(
            activity_tracker=self.activity_tracker,
            config=self.config.memory.tasks
        )
    
    async def process_message(self, message: Message):
        # Mark user activity
        self.activity_tracker.mark_activity()
        
        # Existing message processing...
        # ...
```

#### 2. Task Definition

```python
from enum import Enum
from typing import Callable, Any
from dataclasses import dataclass, field

class TaskPriority(Enum):
    HIGH = 1      # Extraction (user-facing, affects next query)
    MEDIUM = 2    # Summary refresh (improves context quality)
    LOW = 3       # Garbage collection, metrics, etc.

@dataclass
class Task:
    """A unit of background work."""
    task_type: str                     # "extraction", "summary_refresh", etc.
    priority: TaskPriority
    func: Callable[..., Any]           # Async function to execute
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    
    # Scheduling
    interval_seconds: int | None = None  # For periodic tasks
    next_run: datetime | None = None
    
    # Execution tracking
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Activity awareness
    requires_quiet: bool = True        # If True, skip when user is active
    
    # Timeout
    timeout_seconds: int = 300

    def should_run(self, activity_tracker: ActivityTracker) -> bool:
        """Check if task should run now."""
        if self.requires_quiet and activity_tracker.is_user_active():
            return False
        
        if self.next_run and datetime.now() < self.next_run:
            return False
        
        return True
    
    def __hash__(self):
        # For deduplication
        return hash((self.task_type, str(self.args), str(self.kwargs)))
```

#### 3. TaskQueue

```python
import asyncio
from queue import PriorityQueue
from typing import Optional

class TaskQueue:
    """
    Priority queue for background tasks with deduplication.
    """
    def __init__(self, max_size: int = 1000):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self.pending_tasks: set[int] = set()  # For deduplication
        self._lock = asyncio.Lock()
    
    async def put(self, task: Task):
        """Add a task to the queue (deduplicated)."""
        async with self._lock:
            task_hash = hash(task)
            if task_hash in self.pending_tasks:
                return  # Already queued
            
            priority = task.priority.value
            await self.queue.put((priority, task))
            self.pending_tasks.add(task_hash)
    
    async def get(self) -> Task:
        """Get the highest-priority task."""
        priority, task = await self.queue.get()
        async with self._lock:
            self.pending_tasks.discard(hash(task))
        return task
    
    def qsize(self) -> int:
        return self.queue.qsize()
    
    def is_full(self) -> bool:
        return self.queue.full()
```

#### 4. WorkerPool

```python
import asyncio
from loguru import logger

class WorkerPool:
    """
    Pool of async workers that execute tasks from the queue.
    """
    def __init__(
        self,
        queue: TaskQueue,
        activity_tracker: ActivityTracker,
        num_workers: int = 2,
        metrics: 'TaskMetrics' | None = None
    ):
        self.queue = queue
        self.activity_tracker = activity_tracker
        self.num_workers = num_workers
        self.metrics = metrics or TaskMetrics()
        self.workers: list[asyncio.Task] = []
        self.running = False
    
    async def start(self):
        """Start all workers."""
        self.running = True
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker_loop(worker_id=i))
            self.workers.append(worker)
        logger.info(f"Started {self.num_workers} background workers")
    
    async def stop(self):
        """Stop all workers gracefully."""
        self.running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("Stopped background workers")
    
    async def _worker_loop(self, worker_id: int):
        """Main worker loop: get task → execute → repeat."""
        logger.debug(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get next task
                task = await self.queue.get()
                
                # Check if task should run now
                if not task.should_run(self.activity_tracker):
                    # Re-queue for later
                    task.next_run = datetime.now() + timedelta(seconds=30)
                    await self.queue.put(task)
                    continue
                
                # Execute task
                await self._execute_task(task, worker_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.debug(f"Worker {worker_id} stopped")
    
    async def _execute_task(self, task: Task, worker_id: int):
        """Execute a single task with timeout and retry logic."""
        task.started_at = datetime.now()
        self.metrics.task_started(task)
        
        logger.debug(f"Worker {worker_id} executing {task.task_type} (priority={task.priority.name})")
        
        try:
            # Execute with timeout
            await asyncio.wait_for(
                task.func(*task.args, **task.kwargs),
                timeout=task.timeout_seconds
            )
            
            task.completed_at = datetime.now()
            duration = (task.completed_at - task.started_at).total_seconds()
            self.metrics.task_completed(task, duration)
            
            logger.debug(f"Task {task.task_type} completed in {duration:.2f}s")
            
        except asyncio.TimeoutError:
            logger.warning(f"Task {task.task_type} timed out after {task.timeout_seconds}s")
            await self._handle_task_failure(task, "timeout")
            
        except Exception as e:
            logger.error(f"Task {task.task_type} failed: {e}")
            await self._handle_task_failure(task, str(e))
    
    async def _handle_task_failure(self, task: Task, error: str):
        """Handle task failure with exponential backoff retry."""
        task.failed_at = datetime.now()
        task.retry_count += 1
        self.metrics.task_failed(task, error)
        
        if task.retry_count < task.max_retries:
            # Exponential backoff: 2^retry seconds
            backoff_seconds = 2 ** task.retry_count
            task.next_run = datetime.now() + timedelta(seconds=backoff_seconds)
            await self.queue.put(task)
            logger.info(f"Task {task.task_type} will retry in {backoff_seconds}s (attempt {task.retry_count + 1}/{task.max_retries})")
        else:
            logger.error(f"Task {task.task_type} failed permanently after {task.max_retries} retries")
```

#### 5. BackgroundTaskManager

```python
class BackgroundTaskManager:
    """
    Manages background tasks for the memory system.
    """
    def __init__(
        self,
        activity_tracker: ActivityTracker,
        config: 'TaskConfig',
        memory_store: 'MemoryStore'
    ):
        self.activity_tracker = activity_tracker
        self.config = config
        self.memory_store = memory_store
        
        self.queue = TaskQueue(max_size=1000)
        self.worker_pool = WorkerPool(
            queue=self.queue,
            activity_tracker=activity_tracker,
            num_workers=config.num_workers
        )
        
        self.periodic_tasks: list[Task] = []
        self.scheduler_task: asyncio.Task | None = None
    
    async def start(self):
        """Start the task manager and worker pool."""
        await self.worker_pool.start()
        
        # Register periodic tasks
        self._register_periodic_tasks()
        
        # Start scheduler
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info("Background task manager started")
    
    async def stop(self):
        """Stop the task manager gracefully."""
        if self.scheduler_task:
            self.scheduler_task.cancel()
        await self.worker_pool.stop()
        logger.info("Background task manager stopped")
    
    def _register_periodic_tasks(self):
        """Register all periodic background tasks."""
        from nanobot.memory.extraction import run_extraction_batch
        from nanobot.memory.summaries import refresh_stale_summaries
        from nanobot.memory.learning import decay_learnings
        
        # Task 1: Extract entities from pending events (every 60s)
        self.periodic_tasks.append(Task(
            task_type="extraction",
            priority=TaskPriority.HIGH,
            func=run_extraction_batch,
            args=(self.memory_store,),
            interval_seconds=self.config.extraction_interval,
            requires_quiet=True,
            timeout_seconds=120
        ))
        
        # Task 2: Refresh stale summary nodes (every 5 minutes)
        self.periodic_tasks.append(Task(
            task_type="summary_refresh",
            priority=TaskPriority.MEDIUM,
            func=refresh_stale_summaries,
            args=(self.memory_store,),
            interval_seconds=self.config.summary_refresh_interval,
            requires_quiet=True,
            timeout_seconds=300
        ))
        
        # Task 3: Apply learning decay (every 1 hour)
        self.periodic_tasks.append(Task(
            task_type="learning_decay",
            priority=TaskPriority.LOW,
            func=decay_learnings,
            args=(self.memory_store,),
            interval_seconds=self.config.learning_decay_interval,
            requires_quiet=False,  # Doesn't need quiet
            timeout_seconds=60
        ))
    
    async def _scheduler_loop(self):
        """Periodic task scheduler."""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                for task in self.periodic_tasks:
                    if task.next_run is None or datetime.now() >= task.next_run:
                        # Schedule next run
                        task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
                        
                        # Submit to queue
                        await self.queue.put(task)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    async def submit_task(self, task: Task):
        """Submit a one-off task (non-periodic)."""
        await self.queue.put(task)
```

#### 6. Metrics and Observability

```python
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class TaskMetrics:
    """Metrics for background task execution."""
    total_started: int = 0
    total_completed: int = 0
    total_failed: int = 0
    
    by_type: dict[str, dict] = field(default_factory=lambda: defaultdict(lambda: {
        "started": 0,
        "completed": 0,
        "failed": 0,
        "total_duration": 0.0,
        "avg_duration": 0.0,
        "last_run": None,
        "last_error": None
    }))
    
    def task_started(self, task: Task):
        self.total_started += 1
        self.by_type[task.task_type]["started"] += 1
    
    def task_completed(self, task: Task, duration: float):
        self.total_completed += 1
        stats = self.by_type[task.task_type]
        stats["completed"] += 1
        stats["total_duration"] += duration
        stats["avg_duration"] = stats["total_duration"] / stats["completed"]
        stats["last_run"] = datetime.now()
    
    def task_failed(self, task: Task, error: str):
        self.total_failed += 1
        stats = self.by_type[task.task_type]
        stats["failed"] += 1
        stats["last_error"] = error
    
    def summary(self) -> dict:
        """Return metrics summary."""
        return {
            "total": {
                "started": self.total_started,
                "completed": self.total_completed,
                "failed": self.total_failed,
                "success_rate": self.total_completed / max(self.total_started, 1)
            },
            "by_type": dict(self.by_type)
        }
```

### Configuration Schema

```python
class TaskConfig(BaseModel):
    """Background task configuration."""
    
    # Worker pool
    num_workers: int = 2
    max_queue_size: int = 1000
    
    # Activity awareness
    quiet_threshold_seconds: int = 30  # User inactive for 30s = safe to run tasks
    
    # Task intervals (seconds)
    extraction_interval: int = 60
    summary_refresh_interval: int = 300  # 5 minutes
    learning_decay_interval: int = 3600  # 1 hour
    
    # Timeouts
    extraction_timeout: int = 120
    summary_refresh_timeout: int = 300
    learning_decay_timeout: int = 60
    
    # Retries
    max_retries: int = 3
```

Example config:
```json
{
  "memory": {
    "tasks": {
      "num_workers": 2,
      "extraction_interval": 60,
      "summary_refresh_interval": 300,
      "quiet_threshold_seconds": 30
    }
  }
}
```

### Integration with AgentLoop

```python
# nanobot/agent/loop.py

class AgentLoop:
    def __init__(self, config: Config, message_bus: MessageBus):
        # Existing init...
        
        # Memory system
        if config.memory.enabled:
            self.memory_store = MemoryStore(config.memory)
            self.activity_tracker = ActivityTracker(
                quiet_threshold_seconds=config.memory.tasks.quiet_threshold_seconds
            )
            self.task_manager = BackgroundTaskManager(
                activity_tracker=self.activity_tracker,
                config=config.memory.tasks,
                memory_store=self.memory_store
            )
    
    async def start(self):
        """Start the agent loop and background tasks."""
        # Existing startup...
        
        if self.config.memory.enabled:
            await self.task_manager.start()
        
        logger.info("Agent loop started")
    
    async def stop(self):
        """Stop the agent loop gracefully."""
        if self.config.memory.enabled:
            await self.task_manager.stop()
        
        # Existing shutdown...
        
        logger.info("Agent loop stopped")
    
    async def process_message(self, message: Message):
        """Process a user message."""
        # Mark user activity
        if self.config.memory.enabled:
            self.activity_tracker.mark_activity()
        
        # Existing message processing...
        # ...
```

### CLI Commands

```bash
# Show background task status
$ nanobot memory tasks
Background Tasks Status
───────────────────────────────────────
Workers:              2 active
Queue size:           5 pending
User activity:        Active (12s ago)

Periodic Tasks:
  extraction          Next run: 45s  Last: 2m ago  Avg: 8.2s
  summary_refresh     Next run: 3m   Last: 7m ago  Avg: 23.1s
  learning_decay      Next run: 42m  Last: 1h ago  Avg: 2.3s

Metrics (last 24h):
  Total started:      1,234
  Total completed:    1,220 (98.9%)
  Total failed:       14 (1.1%)

# Manually trigger a task
$ nanobot memory extract-now
Submitted extraction task (will run when user is quiet)

# Show detailed metrics
$ nanobot memory task-metrics
Task Metrics
───────────────────────────────────────
extraction:
  Runs:              342
  Avg duration:      8.2s
  Success rate:      99.7%
  Last run:          2m ago
  Last error:        None

summary_refresh:
  Runs:              48
  Avg duration:      23.1s
  Success rate:      95.8%
  Last run:          7m ago
  Last error:        "LLM timeout" (1h ago)
```

### Error Handling

```python
class TaskError(Exception):
    """Base exception for task errors."""
    pass

class TaskTimeoutError(TaskError):
    """Task exceeded timeout."""
    pass

class TaskRetryableError(TaskError):
    """Task failed but can be retried."""
    pass

class TaskPermanentError(TaskError):
    """Task failed permanently, don't retry."""
    pass
```

Usage in tasks:
```python
async def run_extraction_batch(memory_store: MemoryStore):
    """Extract entities from pending events."""
    try:
        events = memory_store.get_pending_events(limit=20)
        
        for event in events:
            try:
                await extract_entities_from_event(event)
            except ExtractionError as e:
                # Individual event failure, continue batch
                logger.warning(f"Failed to extract from event {event.id}: {e}")
                continue
        
        logger.info(f"Extracted entities from {len(events)} events")
        
    except DatabaseError as e:
        # Transient DB error, retry
        raise TaskRetryableError(f"Database error: {e}")
    
    except Exception as e:
        # Unknown error, log and fail permanently
        logger.exception(f"Extraction batch failed: {e}")
        raise TaskPermanentError(f"Unexpected error: {e}")
```

### Testing Strategy

```python
# tests/memory/test_background_tasks.py

@pytest.mark.asyncio
async def test_activity_aware_scheduling():
    """Tasks should not run when user is active."""
    tracker = ActivityTracker(quiet_threshold_seconds=30)
    queue = TaskQueue()
    
    # User is active
    tracker.mark_activity()
    
    task = Task(
        task_type="test",
        priority=TaskPriority.HIGH,
        func=async_noop,
        requires_quiet=True
    )
    
    # Should not run
    assert not task.should_run(tracker)
    
    # Wait for quiet period
    await asyncio.sleep(31)
    
    # Should run now
    assert task.should_run(tracker)

@pytest.mark.asyncio
async def test_task_retry_with_backoff():
    """Failed tasks should retry with exponential backoff."""
    tracker = ActivityTracker()
    queue = TaskQueue()
    worker_pool = WorkerPool(queue, tracker, num_workers=1)
    
    attempts = []
    
    async def failing_task():
        attempts.append(datetime.now())
        if len(attempts) < 3:
            raise TaskRetryableError("Temporary failure")
    
    task = Task(
        task_type="test",
        priority=TaskPriority.HIGH,
        func=failing_task,
        max_retries=3
    )
    
    await queue.put(task)
    await worker_pool.start()
    
    # Wait for retries
    await asyncio.sleep(10)
    
    # Should have 3 attempts with increasing backoff
    assert len(attempts) == 3
    assert (attempts[1] - attempts[0]).total_seconds() >= 2  # 2^1 backoff
    assert (attempts[2] - attempts[1]).total_seconds() >= 4  # 2^2 backoff
    
    await worker_pool.stop()

@pytest.mark.asyncio
async def test_task_timeout():
    """Tasks should be killed if they exceed timeout."""
    tracker = ActivityTracker()
    queue = TaskQueue()
    worker_pool = WorkerPool(queue, tracker, num_workers=1)
    
    async def slow_task():
        await asyncio.sleep(100)  # Never completes
    
    task = Task(
        task_type="test",
        priority=TaskPriority.HIGH,
        func=slow_task,
        timeout_seconds=1
    )
    
    await queue.put(task)
    await worker_pool.start()
    
    # Wait for timeout
    await asyncio.sleep(2)
    
    # Task should have failed due to timeout
    assert worker_pool.metrics.by_type["test"]["failed"] == 1
    
    await worker_pool.stop()
```

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Worker startup | <100ms | Should not delay agent startup |
| Task submission | <1ms | Non-blocking queue put |
| Activity check | <0.1ms | Simple timestamp comparison |
| Queue overhead | <1% CPU | Minimal background CPU usage |
| Memory overhead | <10MB | Worker pool + queue state |

### Resource Requirements

**Memory**:
- WorkerPool: ~2MB (worker tasks + metrics)
- TaskQueue: ~5MB (1000 tasks × ~5KB each)
- Total: ~7-10MB

**CPU**:
- Idle: <1% (scheduler checking every 10s)
- Active: 5-20% (during task execution)

**Threads**:
- All async (no additional threads)
- Runs within existing asyncio event loop

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
