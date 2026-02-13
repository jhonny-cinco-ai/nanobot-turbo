"""SQLite persistence layer for Learning Exchange insights.

This module provides the InsightStore class which manages database operations
for queued learning packages, enabling them to survive process restarts and
session boundaries.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

from loguru import logger

from nanobot.agent.learning_exchange import LearningPackage, InsightCategory, ApplicabilityScope
from nanobot.config.loader import get_data_dir


class InsightStore:
    """
    SQLite storage for Learning Exchange insight packages.
    
    Provides persistence for queued insights so they survive process restarts
    and enable long-term bot learning across sessions.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize insight store.
        
        Args:
            db_path: Path to SQLite database (defaults to data_dir/learning_exchange.db)
        """
        if db_path is None:
            db_path = get_data_dir() / "learning_exchange.db"
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connection pool (created lazily)
        self._conn: Optional[sqlite3.Connection] = None
        
        # Initialize database
        self._init_db()
        
        logger.info(f"InsightStore initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            
        return self._conn
    
    def _init_db(self):
        """Initialize SQLite database with queued_packages table."""
        conn = self._get_connection()
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queued_packages (
                id TEXT PRIMARY KEY,
                package_id TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence REAL NOT NULL,
                scope TEXT NOT NULL,
                applicable_workspaces_json TEXT,
                applicable_bots_json TEXT,
                source_bot TEXT NOT NULL,
                source_workspace TEXT NOT NULL,
                evidence_json TEXT,
                context_json TEXT,
                created_at REAL NOT NULL,
                queued_at REAL,
                distributed_to_json TEXT,
                status TEXT DEFAULT 'queued',
                distribution_count INTEGER DEFAULT 0,
                last_distributed_at REAL
            )
        """)
        
        # Create indexes for efficient queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_packages_status 
            ON queued_packages(status)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_packages_scope 
            ON queued_packages(scope)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_packages_confidence 
            ON queued_packages(confidence)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_packages_created_at 
            ON queued_packages(created_at DESC)
        """)
        
        conn.commit()
    
    def save_package(self, package: LearningPackage) -> str:
        """
        Save a learning package to the database.
        
        Args:
            package: LearningPackage to save
            
        Returns:
            Package ID
        """
        conn = self._get_connection()
        
        conn.execute("""
            INSERT OR REPLACE INTO queued_packages (
                id, package_id, category, title, description, confidence,
                scope, applicable_workspaces_json, applicable_bots_json,
                source_bot, source_workspace, evidence_json, context_json,
                created_at, queued_at, distributed_to_json, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()),
            package.package_id,
            package.category.value,
            package.title,
            package.description,
            package.confidence,
            package.scope.value,
            json.dumps(package.applicable_workspaces),
            json.dumps(package.applicable_bots),
            package.source_bot,
            package.source_workspace,
            json.dumps(package.evidence),
            json.dumps(package.context),
            package.created_at.timestamp(),
            package.queued_at.timestamp() if package.queued_at else None,
            json.dumps(package.distributed_to),
            'queued'
        ))
        
        conn.commit()
        logger.debug(f"Saved package: {package.package_id}")
        
        return package.package_id
    
    def get_package(self, package_id: str) -> Optional[LearningPackage]:
        """
        Retrieve a package by ID.
        
        Args:
            package_id: Package ID to retrieve
            
        Returns:
            LearningPackage if found, None otherwise
        """
        conn = self._get_connection()
        
        row = conn.execute(
            "SELECT * FROM queued_packages WHERE package_id = ?",
            (package_id,)
        ).fetchone()
        
        if row:
            return self._row_to_package(row)
        
        return None
    
    def get_pending_packages(self, limit: int = 100) -> List[LearningPackage]:
        """
        Get all pending (queued) packages.
        
        Args:
            limit: Maximum number to retrieve
            
        Returns:
            List of LearningPackages
        """
        conn = self._get_connection()
        
        rows = conn.execute(
            "SELECT * FROM queued_packages WHERE status = 'queued' ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        
        return [self._row_to_package(row) for row in rows]
    
    def get_packages_by_status(self, status: str, limit: int = 100) -> List[LearningPackage]:
        """
        Get packages by distribution status.
        
        Args:
            status: Status to filter by ('queued', 'distributed', 'archived')
            limit: Maximum number to retrieve
            
        Returns:
            List of LearningPackages
        """
        conn = self._get_connection()
        
        rows = conn.execute(
            "SELECT * FROM queued_packages WHERE status = ? ORDER BY created_at ASC LIMIT ?",
            (status, limit)
        ).fetchall()
        
        return [self._row_to_package(row) for row in rows]
    
    def get_packages_by_scope(self, scope: ApplicabilityScope, limit: int = 100) -> List[LearningPackage]:
        """
        Get packages by scope.
        
        Args:
            scope: ApplicabilityScope to filter by
            limit: Maximum number to retrieve
            
        Returns:
            List of LearningPackages
        """
        conn = self._get_connection()
        
        rows = conn.execute(
            "SELECT * FROM queued_packages WHERE status = 'queued' AND scope = ? ORDER BY created_at ASC LIMIT ?",
            (scope.value, limit)
        ).fetchall()
        
        return [self._row_to_package(row) for row in rows]
    
    def mark_distributed(self, package_id: str, distributed_to: List[str]) -> bool:
        """
        Mark a package as distributed to specific bots.
        
        Args:
            package_id: Package ID
            distributed_to: List of bot names it was distributed to
            
        Returns:
            True if updated, False if not found
        """
        conn = self._get_connection()
        
        # Get existing package
        row = conn.execute(
            "SELECT * FROM queued_packages WHERE package_id = ?",
            (package_id,)
        ).fetchone()
        
        if not row:
            return False
        
        # Update distributed_to and status
        existing_distributed = json.loads(row['distributed_to_json']) if row['distributed_to_json'] else []
        all_distributed = list(set(existing_distributed + distributed_to))
        
        conn.execute("""
            UPDATE queued_packages
            SET status = 'distributed',
                distributed_to_json = ?,
                last_distributed_at = ?,
                distribution_count = distribution_count + 1
            WHERE package_id = ?
        """, (
            json.dumps(all_distributed),
            datetime.now().timestamp(),
            package_id
        ))
        
        conn.commit()
        logger.debug(f"Marked package {package_id} as distributed to {distributed_to}")
        
        return True
    
    def archive_package(self, package_id: str) -> bool:
        """
        Archive a package (mark as complete).
        
        Args:
            package_id: Package ID to archive
            
        Returns:
            True if updated, False if not found
        """
        conn = self._get_connection()
        
        cursor = conn.execute(
            "UPDATE queued_packages SET status = 'archived' WHERE package_id = ?",
            (package_id,)
        )
        
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.debug(f"Archived package: {package_id}")
            return True
        
        return False
    
    def delete_package(self, package_id: str) -> bool:
        """
        Delete a package from the database.
        
        Args:
            package_id: Package ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        
        cursor = conn.execute(
            "DELETE FROM queued_packages WHERE package_id = ?",
            (package_id,)
        )
        
        conn.commit()
        
        if cursor.rowcount > 0:
            logger.debug(f"Deleted package: {package_id}")
            return True
        
        return False
    
    def get_stats(self) -> dict:
        """
        Get statistics about stored packages.
        
        Returns:
            Dictionary with counts by status and scope
        """
        conn = self._get_connection()
        
        # Count by status
        status_counts = {}
        for row in conn.execute("SELECT status, COUNT(*) as count FROM queued_packages GROUP BY status"):
            status_counts[row['status']] = row['count']
        
        # Count by scope
        scope_counts = {}
        for row in conn.execute("SELECT scope, COUNT(*) as count FROM queued_packages WHERE status = 'queued' GROUP BY scope"):
            scope_counts[row['scope']] = row['count']
        
        # Average confidence
        avg_conf = conn.execute(
            "SELECT AVG(confidence) as avg FROM queued_packages WHERE status = 'queued'"
        ).fetchone()
        
        return {
            "total_packages": sum(status_counts.values()),
            "by_status": status_counts,
            "by_scope": scope_counts,
            "average_confidence": avg_conf['avg'] if avg_conf['avg'] else 0.0,
            "pending_count": status_counts.get('queued', 0),
            "distributed_count": status_counts.get('distributed', 0),
            "archived_count": status_counts.get('archived', 0),
        }
    
    def cleanup_archived(self, days_old: int = 7) -> int:
        """
        Delete archived packages older than specified days.
        
        Args:
            days_old: Number of days threshold
            
        Returns:
            Number of packages deleted
        """
        conn = self._get_connection()
        
        cutoff_timestamp = (datetime.now().timestamp()) - (days_old * 86400)
        
        cursor = conn.execute(
            "DELETE FROM queued_packages WHERE status = 'archived' AND last_distributed_at < ?",
            (cutoff_timestamp,)
        )
        
        conn.commit()
        
        deleted_count = cursor.rowcount
        logger.info(f"Cleaned up {deleted_count} archived packages older than {days_old} days")
        
        return deleted_count
    
    def _row_to_package(self, row: sqlite3.Row) -> LearningPackage:
        """Convert database row to LearningPackage object."""
        return LearningPackage(
            package_id=row['package_id'],
            category=InsightCategory(row['category']),
            title=row['title'],
            description=row['description'],
            confidence=row['confidence'],
            source_bot=row['source_bot'],
            scope=ApplicabilityScope(row['scope']),
            applicable_workspaces=json.loads(row['applicable_workspaces_json']) if row['applicable_workspaces_json'] else [],
            applicable_bots=json.loads(row['applicable_bots_json']) if row['applicable_bots_json'] else [],
            source_workspace=row['source_workspace'],
            created_at=datetime.fromtimestamp(row['created_at']),
            evidence=json.loads(row['evidence_json']) if row['evidence_json'] else {},
            context=json.loads(row['context_json']) if row['context_json'] else {},
            queued_at=datetime.fromtimestamp(row['queued_at']) if row['queued_at'] else None,
            distributed_to=json.loads(row['distributed_to_json']) if row['distributed_to_json'] else [],
        )
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("InsightStore connection closed")
