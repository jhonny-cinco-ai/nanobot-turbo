"""SQLite storage layer for the memory system.

This module provides the MemoryStore class which manages all database operations
for the memory system using SQLite with WAL mode for better concurrency.
"""

import json
import sqlite3
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from nanobot.config.schema import MemoryConfig
from nanobot.memory.models import Event, Entity, Edge, Fact, Topic, SummaryNode, Learning


class MemoryStore:
    """
    SQLite-based storage for the memory system.
    
    Uses WAL mode (Write-Ahead Logging) for better concurrency:
    - Readers don't block writers
    - Writers don't block readers
    - Better performance for concurrent access
    """
    
    def __init__(self, config: MemoryConfig, workspace: Path):
        """
        Initialize the memory store.
        
        Args:
            config: Memory system configuration
            workspace: Path to workspace directory
        """
        self.config = config
        self.workspace = workspace
        
        # Database file path
        self.db_path = workspace / config.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connection (created on first use)
        self._conn: Optional[sqlite3.Connection] = None
        
        logger.info(f"MemoryStore initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection with WAL mode."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA cache_size=10000;")
            
            # Initialize tables
            self._init_tables()
            
            logger.debug("Database connection established with WAL mode")
        
        return self._conn
    
    def _init_tables(self):
        """Create all required tables if they don't exist."""
        conn = self._conn
        
        # Events table - immutable record of all interactions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                channel TEXT NOT NULL,
                direction TEXT NOT NULL,
                event_type TEXT NOT NULL,
                content TEXT NOT NULL,
                session_key TEXT NOT NULL,
                parent_event_id TEXT,
                person_id TEXT,
                tool_name TEXT,
                extraction_status TEXT DEFAULT 'pending',
                content_embedding BLOB,
                relevance_score REAL DEFAULT 1.0,
                last_accessed REAL,
                metadata TEXT
            )
        """)
        
        # Index on frequently queried columns
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_key);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_extraction ON events(extraction_status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_channel ON events(channel);")
        
        # Entities table - people, orgs, concepts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                aliases TEXT,  -- JSON array
                description TEXT,
                name_embedding BLOB,
                description_embedding BLOB,
                source_event_ids TEXT,  -- JSON array
                event_count INTEGER DEFAULT 0,
                first_seen REAL,
                last_seen REAL
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);")
        
        # Edges table - relationships between entities
        conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_entity_id TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                relation_type TEXT,
                strength REAL DEFAULT 0.5,
                source_event_ids TEXT,  -- JSON array
                first_seen REAL,
                last_seen REAL,
                FOREIGN KEY (source_entity_id) REFERENCES entities(id),
                FOREIGN KEY (target_entity_id) REFERENCES entities(id)
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_entity_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_entity_id);")
        
        # Facts table - subject-predicate-object triplets
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_text TEXT NOT NULL,
                object_entity_id TEXT,
                fact_type TEXT DEFAULT 'attribute',
                confidence REAL DEFAULT 0.8,
                strength REAL DEFAULT 1.0,
                source_event_ids TEXT,  -- JSON array
                valid_from REAL,
                valid_to REAL,
                FOREIGN KEY (subject_entity_id) REFERENCES entities(id),
                FOREIGN KEY (object_entity_id) REFERENCES entities(id)
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject_entity_id);")
        
        # Topics table - theme clusters
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                embedding BLOB,
                event_ids TEXT,  -- JSON array
                first_seen REAL,
                last_seen REAL
            )
        """)
        
        # Summary nodes table - hierarchical summaries
        conn.execute("""
            CREATE TABLE IF NOT EXISTS summary_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                parent_id TEXT,
                summary TEXT,
                summary_embedding BLOB,
                events_since_update INTEGER DEFAULT 0,
                last_updated REAL,
                FOREIGN KEY (parent_id) REFERENCES summary_nodes(id)
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_type ON summary_nodes(node_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_key ON summary_nodes(key);")
        
        # Learnings table - user preferences and insights
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learnings (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                sentiment TEXT DEFAULT 'neutral',
                confidence REAL DEFAULT 0.8,
                tool_name TEXT,
                recommendation TEXT,
                superseded_by TEXT,
                content_embedding BLOB,
                created_at REAL,
                updated_at REAL,
                relevance_score REAL DEFAULT 1.0,
                times_accessed INTEGER DEFAULT 0,
                last_accessed REAL,
                FOREIGN KEY (superseded_by) REFERENCES learnings(id)
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_source ON learnings(source);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_relevance ON learnings(relevance_score);")
        
        conn.commit()
        logger.debug("Database tables initialized")
    
    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # =========================================================================
    # Event Operations
    # =========================================================================
    
    def save_event(self, event: Event) -> str:
        """
        Save an event to the database.
        
        Args:
            event: The event to save
            
        Returns:
            The event ID
        """
        conn = self._get_connection()
        
        # Serialize embedding if present
        embedding_bytes = None
        if event.content_embedding:
            # Pack float array into bytes (384 floats for bge-small)
            embedding_bytes = struct.pack(f'{len(event.content_embedding)}f', *event.content_embedding)
        
        conn.execute(
            """
            INSERT INTO events (
                id, timestamp, channel, direction, event_type, content,
                session_key, parent_event_id, person_id, tool_name,
                extraction_status, content_embedding, relevance_score,
                last_accessed, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.timestamp.timestamp() if event.timestamp else None,
                event.channel,
                event.direction,
                event.event_type,
                event.content,
                event.session_key,
                event.parent_event_id,
                event.person_id,
                event.tool_name,
                event.extraction_status,
                embedding_bytes,
                event.relevance_score,
                event.last_accessed.timestamp() if event.last_accessed else None,
                json.dumps(event.metadata) if event.metadata else None
            )
        )
        conn.commit()
        
        logger.debug(f"Event saved: {event.id}")
        return event.id
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Retrieve an event by ID."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return self._row_to_event(row)
    
    def get_events_by_session(
        self,
        session_key: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Event]:
        """
        Get events for a specific session.
        
        Args:
            session_key: The session identifier (e.g., "cli:default")
            limit: Maximum number of events to return
            offset: Number of events to skip
            
        Returns:
            List of events, most recent first
        """
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM events 
            WHERE session_key = ? 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
            """,
            (session_key, limit, offset)
        ).fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    def get_pending_events(self, limit: int = 20) -> list[Event]:
        """
        Get events awaiting extraction processing.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of events with extraction_status = 'pending'
        """
        conn = self._get_connection()
        rows = conn.execute(
            """
            SELECT * FROM events 
            WHERE extraction_status = 'pending'
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        
        return [self._row_to_event(row) for row in rows]
    
    def mark_event_extracted(self, event_id: str, status: str = "complete"):
        """
        Update extraction status for an event.
        
        Args:
            event_id: The event ID
            status: New status ('complete', 'failed', 'skipped')
        """
        conn = self._get_connection()
        conn.execute(
            "UPDATE events SET extraction_status = ? WHERE id = ?",
            (status, event_id)
        )
        conn.commit()
        
        logger.debug(f"Event {event_id} marked as {status}")
    
    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """Convert a database row to an Event object."""
        # Deserialize embedding
        embedding = None
        if row['content_embedding']:
            floats = struct.unpack('384f', row['content_embedding'])  # bge-small = 384 dims
            embedding = list(floats)
        
        # Deserialize metadata
        metadata = {}
        if row['metadata']:
            metadata = json.loads(row['metadata'])
        
        return Event(
            id=row['id'],
            timestamp=datetime.fromtimestamp(row['timestamp']) if row['timestamp'] else None,
            channel=row['channel'],
            direction=row['direction'],
            event_type=row['event_type'],
            content=row['content'],
            session_key=row['session_key'],
            parent_event_id=row['parent_event_id'],
            person_id=row['person_id'],
            tool_name=row['tool_name'],
            extraction_status=row['extraction_status'],
            content_embedding=embedding,
            relevance_score=row['relevance_score'],
            last_accessed=datetime.fromtimestamp(row['last_accessed']) if row['last_accessed'] else None,
            metadata=metadata
        )
    
    # =========================================================================
    # Semantic Search
    # =========================================================================
    
    def search_events(
        self,
        query_embedding: list[float],
        session_key: str | None = None,
        limit: int = 10,
        threshold: float = 0.5
    ) -> list[tuple[Event, float]]:
        """
        Search events by semantic similarity.
        
        Args:
            query_embedding: The query embedding vector
            session_key: Optional session to restrict search to
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (event, similarity_score) tuples, sorted by similarity
        """
        from nanobot.memory.embeddings import cosine_similarity
        
        conn = self._get_connection()
        
        # Get events with embeddings
        if session_key:
            rows = conn.execute(
                """
                SELECT * FROM events 
                WHERE session_key = ? AND content_embedding IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1000
                """,
                (session_key,)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM events 
                WHERE content_embedding IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1000
                """
            ).fetchall()
        
        # Calculate similarities
        results = []
        for row in rows:
            if row['content_embedding']:
                embedding = struct.unpack(f'{len(query_embedding)}f', row['content_embedding'])
                similarity = cosine_similarity(query_embedding, list(embedding))
                
                if similarity >= threshold:
                    event = self._row_to_event(row)
                    results.append((event, similarity))
        
        # Sort by similarity (highest first) and return top N
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def search_events_by_text(
        self,
        query: str,
        provider: "EmbeddingProvider",
        session_key: str | None = None,
        limit: int = 10,
        threshold: float = 0.5
    ) -> list[tuple[Event, float]]:
        """
        Search events by text query (automatically embeds query).
        
        Args:
            query: Text query
            provider: Embedding provider to use
            session_key: Optional session to restrict search to
            limit: Maximum number of results
            threshold: Minimum similarity score
            
        Returns:
            List of (event, similarity_score) tuples
        """
        query_embedding = provider.embed(query)
        return self.search_events(query_embedding, session_key, limit, threshold)
    
    def get_similar_entities(
        self,
        name_embedding: list[float],
        entity_type: str | None = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[tuple[Entity, float]]:
        """
        Find entities with similar names.
        
        Args:
            name_embedding: Embedding to compare against
            entity_type: Optional entity type filter
            limit: Maximum number of results
            threshold: Minimum similarity score
            
        Returns:
            List of (entity, similarity_score) tuples
        """
        from nanobot.memory.embeddings import cosine_similarity
        
        conn = self._get_connection()
        
        # Get entities with embeddings
        if entity_type:
            rows = conn.execute(
                "SELECT * FROM entities WHERE entity_type = ? AND name_embedding IS NOT NULL",
                (entity_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM entities WHERE name_embedding IS NOT NULL"
            ).fetchall()
        
        # Calculate similarities
        results = []
        for row in rows:
            if row['name_embedding']:
                embedding = struct.unpack(f'{len(name_embedding)}f', row['name_embedding'])
                similarity = cosine_similarity(name_embedding, list(embedding))
                
                if similarity >= threshold:
                    entity = self._row_to_entity(row)
                    results.append((entity, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        """Convert a database row to an Entity object."""
        # Deserialize name embedding
        name_embedding = None
        if row['name_embedding']:
            floats = struct.unpack('384f', row['name_embedding'])
            name_embedding = list(floats)
        
        # Deserialize description embedding
        desc_embedding = None
        if row['description_embedding']:
            floats = struct.unpack('384f', row['description_embedding'])
            desc_embedding = list(floats)
        
        # Deserialize aliases and source event IDs
        aliases = []
        if row['aliases']:
            aliases = json.loads(row['aliases'])
        
        source_ids = []
        if row['source_event_ids']:
            source_ids = json.loads(row['source_event_ids'])
        
        return Entity(
            id=row['id'],
            name=row['name'],
            entity_type=row['entity_type'],
            aliases=aliases,
            description=row['description'] or "",
            name_embedding=name_embedding,
            description_embedding=desc_embedding,
            source_event_ids=source_ids,
            event_count=row['event_count'] or 0,
            first_seen=datetime.fromtimestamp(row['first_seen']) if row['first_seen'] else None,
            last_seen=datetime.fromtimestamp(row['last_seen']) if row['last_seen'] else None
        )
    
    # =========================================================================
    # Statistics and Maintenance
    # =========================================================================
    
    def get_stats(self) -> dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with table row counts and other stats
        """
        conn = self._get_connection()
        
        tables = ['events', 'entities', 'edges', 'facts', 'topics', 'summary_nodes', 'learnings']
        stats = {}
        
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
        
        # Pending extractions
        pending = conn.execute(
            "SELECT COUNT(*) FROM events WHERE extraction_status = 'pending'"
        ).fetchone()[0]
        stats['pending_extractions'] = pending
        
        return stats
    
    def vacuum(self):
        """Optimize database (reclaim space, defragment)."""
        conn = self._get_connection()
        conn.execute("VACUUM;")
        conn.commit()
        logger.info("Database vacuumed")
