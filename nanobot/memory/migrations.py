"""Database migrations for multi-agent bot-scoping support.

This module handles schema migrations to add bot-scoping to the memory system.
Migrations are idempotent and only run once per database.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


class MigrationManager:
    """Manages database schema migrations."""
    
    def __init__(self, db_path: Path):
        """Initialize migration manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
    
    def apply_migrations(self) -> None:
        """Apply all pending migrations to the database."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        try:
            # Create migrations tracking table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at REAL NOT NULL
                )
            """)
            conn.commit()
            
            # Get list of applied migrations
            cursor = conn.execute("SELECT id FROM migrations")
            applied = {row["id"] for row in cursor.fetchall()}
            
            # Define all migrations
            migrations = [
                ("001_add_bot_scoping_to_events", self._migration_001_bot_scoping_events),
                ("002_add_bot_scoping_to_learnings", self._migration_002_bot_scoping_learnings),
                ("003_add_bot_scoping_to_summaries", self._migration_003_bot_scoping_summaries),
                ("004_create_bot_expertise_table", self._migration_004_bot_expertise),
                ("005_create_bot_memory_ledger", self._migration_005_bot_memory_ledger),
                ("006_add_metadata_to_learnings", self._migration_006_metadata_to_learnings),
                ("007_create_coordinator_messages", self._migration_007_coordinator_messages),
                ("008_create_coordinator_tasks", self._migration_008_coordinator_tasks),
                ("009_create_coordinator_decisions", self._migration_009_coordinator_decisions),
            ]
            
            # Apply pending migrations
            for migration_id, migration_func in migrations:
                if migration_id not in applied:
                    logger.info(f"Applying migration: {migration_id}")
                    try:
                        migration_func(conn)
                        conn.execute(
                            "INSERT INTO migrations (id, name, applied_at) VALUES (?, ?, ?)",
                            (migration_id, migration_id, datetime.now().timestamp())
                        )
                        conn.commit()
                        logger.info(f"Migration applied: {migration_id}")
                    except Exception as e:
                        conn.rollback()
                        logger.error(f"Migration failed: {migration_id}: {e}")
                        raise
        finally:
            conn.close()
    
    @staticmethod
    def _migration_001_bot_scoping_events(conn: sqlite3.Connection) -> None:
        """Add bot_name and bot_role columns to events table.
        
        This enables tracking which bot created or processed an event.
        """
        # Check if columns already exist
        cursor = conn.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "bot_name" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN bot_name TEXT DEFAULT 'leader'")
            logger.debug("Added bot_name column to events table")
        
        if "bot_role" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN bot_role TEXT DEFAULT 'leader'")
            logger.debug("Added bot_role column to events table")
        
        # Create index for bot_name lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_bot_name ON events(bot_name)")
        logger.debug("Created index on events.bot_name")
    
    @staticmethod
    def _migration_002_bot_scoping_learnings(conn: sqlite3.Connection) -> None:
        """Add bot_id, is_private, promotion_count to learnings table.
        
        This enables:
        - Tracking which bot learned something (bot_id)
        - Private (per-bot) vs shared (workspace-wide) learnings (is_private)
        - Cross-pollination tracking (promotion_count)
        """
        cursor = conn.execute("PRAGMA table_info(learnings)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "bot_id" not in columns:
            conn.execute("ALTER TABLE learnings ADD COLUMN bot_id TEXT DEFAULT 'leader'")
            logger.debug("Added bot_id column to learnings table")
        
        if "is_private" not in columns:
            conn.execute("ALTER TABLE learnings ADD COLUMN is_private INTEGER DEFAULT 0")
            logger.debug("Added is_private column to learnings table")
        
        if "promotion_count" not in columns:
            conn.execute("ALTER TABLE learnings ADD COLUMN promotion_count INTEGER DEFAULT 0")
            logger.debug("Added promotion_count column to learnings table")
        
        # Create indexes for filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_bot_id ON learnings(bot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_learnings_private ON learnings(is_private)")
        logger.debug("Created indexes on learnings.bot_id and learnings.is_private")
    
    @staticmethod
    def _migration_003_bot_scoping_summaries(conn: sqlite3.Connection) -> None:
        """Add bot_id, domain to summary_nodes table.
        
        This enables per-bot summary tracking and domain expertise summaries.
        """
        cursor = conn.execute("PRAGMA table_info(summary_nodes)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "bot_id" not in columns:
            conn.execute("ALTER TABLE summary_nodes ADD COLUMN bot_id TEXT DEFAULT 'leader'")
            logger.debug("Added bot_id column to summary_nodes table")
        
        if "domain" not in columns:
            conn.execute("ALTER TABLE summary_nodes ADD COLUMN domain TEXT")
            logger.debug("Added domain column to summary_nodes table")
        
        # Create index for bot-specific summaries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_bot_id ON summary_nodes(bot_id)")
        logger.debug("Created index on summary_nodes.bot_id")
    
    @staticmethod
    def _migration_004_bot_expertise(conn: sqlite3.Connection) -> None:
        """Create bot_expertise table for tracking per-bot domain expertise.
        
        Stores confidence scores for each bot's domain expertise.
        """
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_expertise (
                id TEXT PRIMARY KEY,
                bot_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                interaction_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                last_updated REAL,
                UNIQUE(bot_id, domain),
                FOREIGN KEY (bot_id) REFERENCES entities(id)
            )
        """)
        
        # Create indexes for efficient lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_expertise_bot ON bot_expertise(bot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_expertise_domain ON bot_expertise(domain)")
        
        logger.debug("Created bot_expertise table")
    
    @staticmethod
    def _migration_005_bot_memory_ledger(conn: sqlite3.Connection) -> None:
        """Create bot_memory_ledger table for tracking private→shared promotion.
        
        Records when bot memories are promoted to shared memories.
        """
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_memory_ledger (
                id TEXT PRIMARY KEY,
                bot_id TEXT NOT NULL,
                learning_id TEXT NOT NULL UNIQUE,
                original_scope TEXT NOT NULL,  -- "private" or "shared"
                promotion_date REAL,
                promotion_reason TEXT,
                exposure_count INTEGER DEFAULT 0,
                cross_pollinated_by TEXT,  -- Which bot promoted it
                FOREIGN KEY (bot_id) REFERENCES entities(id),
                FOREIGN KEY (learning_id) REFERENCES learnings(id)
            )
        """)
        
        # Create indexes for tracking promotion history
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_bot ON bot_memory_ledger(bot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_learning ON bot_memory_ledger(learning_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_promoted ON bot_memory_ledger(promotion_date)")
        
        logger.debug("Created bot_memory_ledger table")
    
    @staticmethod
    def _migration_006_metadata_to_learnings(conn: sqlite3.Connection) -> None:
        """Add metadata column to learnings table for bot-scoping and extensibility."""
        cursor = conn.execute("PRAGMA table_info(learnings)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if "metadata" not in columns:
            conn.execute("ALTER TABLE learnings ADD COLUMN metadata TEXT")
            logger.debug("Added metadata column to learnings table")
    
    @staticmethod
    def _migration_007_coordinator_messages(conn: sqlite3.Connection) -> None:
        """Create coordinator_messages table for persistent message storage."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coordinator_messages (
                id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                context TEXT,
                timestamp REAL NOT NULL,
                response_to_id TEXT,
                workspace_id TEXT
            )
        """)
        
        # Create indexes for efficient queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_messages_conversation ON coordinator_messages(conversation_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_messages_sender ON coordinator_messages(sender_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_messages_recipient ON coordinator_messages(recipient_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_messages_timestamp ON coordinator_messages(timestamp)")
        
        logger.debug("Created coordinator_messages table")
    
    @staticmethod
    def _migration_008_coordinator_tasks(conn: sqlite3.Connection) -> None:
        """Create coordinator_tasks table for persistent task storage."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coordinator_tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                domain TEXT NOT NULL,
                priority INTEGER DEFAULT 3,
                assigned_to TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_by TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                due_date REAL,
                requirements TEXT,
                result TEXT,
                confidence REAL,
                parent_task_id TEXT,
                workspace_id TEXT
            )
        """)
        
        # Create indexes for efficient queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_tasks_status ON coordinator_tasks(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_tasks_assigned_to ON coordinator_tasks(assigned_to)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_tasks_domain ON coordinator_tasks(domain)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_tasks_created_at ON coordinator_tasks(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_tasks_parent ON coordinator_tasks(parent_task_id)")
        
        logger.debug("Created coordinator_tasks table")
    
    @staticmethod
    def _migration_009_coordinator_decisions(conn: sqlite3.Connection) -> None:
        """Create coordinator_decisions table for decision audit trail."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coordinator_decisions (
                id TEXT PRIMARY KEY,
                decision_type TEXT NOT NULL,
                task_id TEXT,
                participants TEXT,
                positions TEXT,
                reasoning TEXT,
                final_decision TEXT,
                confidence REAL,
                timestamp REAL NOT NULL,
                workspace_id TEXT
            )
        """)
        
        # Create indexes for efficient queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_decisions_timestamp ON coordinator_decisions(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_decisions_task_id ON coordinator_decisions(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_coord_decisions_type ON coordinator_decisions(decision_type)")
        
        logger.debug("Created coordinator_decisions table")
