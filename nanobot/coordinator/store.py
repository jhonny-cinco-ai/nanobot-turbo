"""Persistent storage layer for coordinator system.

Manages persistence of messages, tasks, and decisions to SQLite database.
"""

import json
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from loguru import logger

from nanobot.coordinator.models import BotMessage, Task, MessageType, TaskStatus
from nanobot.memory.store import TurboMemoryStore


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    value: Any
    timestamp: float = field(default_factory=time.time)
    hits: int = 0


class QueryCache:
    """Simple TTL-based query cache for performance optimization."""
    
    def __init__(self, ttl_seconds: float = 30.0, max_size: int = 100):
        """Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live in seconds
            max_size: Maximum cache entries
        """
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/not found
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._stats["misses"] += 1
            return None
        
        # Check TTL
        if time.time() - entry.timestamp > self.ttl:
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        entry.hits += 1
        self._stats["hits"] += 1
        return entry.value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].timestamp
            )
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
        
        self._cache[key] = CacheEntry(value=value)
    
    def invalidate(self, pattern: str = "") -> None:
        """Invalidate cache entries matching pattern.
        
        Args:
            pattern: Key pattern to match (empty = all)
        """
        if not pattern:
            self._cache.clear()
        else:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "evictions": self._stats["evictions"],
            "hit_rate": hit_rate,
            "ttl_seconds": self.ttl,
        }


class CoordinatorStore:
    """Persistent storage for coordinator messages and tasks.
    
    Extends TurboMemoryStore with coordinator-specific tables.
    """
    
    def __init__(self, memory_store: TurboMemoryStore, cache_ttl: float = 30.0):
        """Initialize coordinator store.
        
        Args:
            memory_store: TurboMemoryStore instance for database access
            cache_ttl: Cache TTL in seconds (0 to disable caching)
        """
        self.memory_store = memory_store
        self._cache = QueryCache(ttl_seconds=cache_ttl) if cache_ttl > 0 else None
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self) -> None:
        """Ensure all coordinator tables exist (migrations will create them)."""
        # Migrations are run automatically when TurboMemoryStore connects
        # This is just a safety check
        conn = self.memory_store._get_connection()
        
        # Check if coordinator_messages table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='coordinator_messages'"
        )
        if not cursor.fetchone():
            logger.warning("Coordinator tables not found. Migrations may have been skipped.")
    
    # =========================================================================
    # Message Operations
    # =========================================================================
    
    def save_message(self, message: BotMessage, workspace_id: Optional[str] = None) -> str:
        """Save a message to persistent storage.
        
        Args:
            message: The BotMessage to save
            workspace_id: Optional workspace ID
            
        Returns:
            Message ID
        """
        conn = self.memory_store._get_connection()
        
        conn.execute(
            """
            INSERT INTO coordinator_messages (
                id, sender_id, recipient_id, message_type, content,
                conversation_id, context, timestamp, response_to_id, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.sender_id,
                message.recipient_id,
                message.message_type.value,
                message.content,
                message.conversation_id,
                json.dumps(message.context) if message.context else None,
                message.timestamp.timestamp(),
                message.response_to_id,
                workspace_id,
            )
        )
        conn.commit()
        
        logger.debug(f"Message saved: {message.id}")
        
        # Invalidate cache for this message
        if self._cache:
            self._cache.invalidate(f"msg:{message.id}")
        
        return message.id
    
    def get_message(self, message_id: str) -> Optional[BotMessage]:
        """Get a message by ID.
        
        Args:
            message_id: The message ID
            
        Returns:
            BotMessage or None if not found
        """
        cache_key = f"msg:{message_id}"
        
        # Try cache first
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        conn = self.memory_store._get_connection()
        
        cursor = conn.execute(
            "SELECT * FROM coordinator_messages WHERE id = ?",
            (message_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        message = self._row_to_message(row)
        
        # Cache the result
        if self._cache:
            self._cache.set(cache_key, message)
        
        return message
    
    def get_conversation(
        self,
        conversation_id: str,
        limit: int = 100
    ) -> List[BotMessage]:
        """Get all messages in a conversation.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum messages to return
            
        Returns:
            List of BotMessage objects
        """
        conn = self.memory_store._get_connection()
        
        cursor = conn.execute(
            """
            SELECT * FROM coordinator_messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (conversation_id, limit)
        )
        
        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))
        
        return messages
    
    def search_messages(
        self,
        query: str,
        sender_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 50
    ) -> List[BotMessage]:
        """Search messages by content and filters.
        
        Args:
            query: Text to search for
            sender_id: Filter by sender (optional)
            message_type: Filter by message type (optional)
            limit: Maximum results
            
        Returns:
            List of matching BotMessage objects
        """
        conn = self.memory_store._get_connection()
        
        where_clauses = ["content LIKE ?"]
        params = [f"%{query}%"]
        
        if sender_id:
            where_clauses.append("sender_id = ?")
            params.append(sender_id)
        
        if message_type:
            where_clauses.append("message_type = ?")
            params.append(message_type.value)
        
        where_sql = " AND ".join(where_clauses)
        
        cursor = conn.execute(
            f"""
            SELECT * FROM coordinator_messages
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params + [limit]
        )
        
        messages = []
        for row in cursor.fetchall():
            messages.append(self._row_to_message(row))
        
        return messages
    
    # =========================================================================
    # Task Operations
    # =========================================================================
    
    def save_task(self, task: Task, workspace_id: Optional[str] = None) -> str:
        """Save a task to persistent storage.
        
        Args:
            task: The Task to save
            workspace_id: Optional workspace ID
            
        Returns:
            Task ID
        """
        conn = self.memory_store._get_connection()
        
        conn.execute(
            """
            INSERT OR REPLACE INTO coordinator_tasks (
                id, title, description, domain, priority, assigned_to,
                status, created_by, created_at, started_at, completed_at,
                due_date, requirements, result, confidence, parent_task_id, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.title,
                task.description,
                task.domain,
                task.priority.value,
                task.assigned_to,
                task.status.value,
                task.created_by,
                task.created_at.timestamp(),
                task.started_at.timestamp() if task.started_at else None,
                task.completed_at.timestamp() if task.completed_at else None,
                task.due_date.timestamp() if task.due_date else None,
                json.dumps(task.requirements) if task.requirements else None,
                task.result,
                task.confidence,
                task.parent_task_id,
                workspace_id,
            )
        )
        conn.commit()
        
        logger.debug(f"Task saved: {task.id}")
        
        # Invalidate cache for this task
        if self._cache:
            self._cache.invalidate(f"task:{task.id}")
            # Also invalidate bot task lists
            if task.assigned_to:
                self._cache.invalidate(f"bot_tasks:{task.assigned_to}")
        
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.
        
        Args:
            task_id: The task ID
            
        Returns:
            Task or None if not found
        """
        cache_key = f"task:{task_id}"
        
        # Try cache first
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        conn = self.memory_store._get_connection()
        
        cursor = conn.execute(
            "SELECT * FROM coordinator_tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        task = self._row_to_task(row)
        
        # Cache the result
        if self._cache:
            self._cache.set(cache_key, task)
        
        return task
    
    def get_tasks_by_status(
        self,
        status: TaskStatus,
        workspace_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """Get tasks by status.
        
        Args:
            status: The task status to filter by
            workspace_id: Optional workspace ID filter
            limit: Maximum tasks to return
            
        Returns:
            List of Task objects
        """
        conn = self.memory_store._get_connection()
        
        if workspace_id:
            cursor = conn.execute(
                """
                SELECT * FROM coordinator_tasks
                WHERE status = ? AND workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status.value, workspace_id, limit)
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM coordinator_tasks
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status.value, limit)
            )
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append(self._row_to_task(row))
        
        return tasks
    
    def get_tasks_by_bot(
        self,
        bot_id: str,
        workspace_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Task]:
        """Get all tasks assigned to a bot.
        
        Args:
            bot_id: The bot ID
            workspace_id: Optional workspace ID filter
            limit: Maximum tasks to return
            
        Returns:
            List of Task objects
        """
        conn = self.memory_store._get_connection()
        
        if workspace_id:
            cursor = conn.execute(
                """
                SELECT * FROM coordinator_tasks
                WHERE assigned_to = ? AND workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bot_id, workspace_id, limit)
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM coordinator_tasks
                WHERE assigned_to = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (bot_id, limit)
            )
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append(self._row_to_task(row))
        
        return tasks
    
    def get_task_history(
        self,
        bot_id: str,
        workspace_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, any]:
        """Get task history for a bot.
        
        Args:
            bot_id: The bot ID
            workspace_id: Optional workspace ID filter
            limit: Maximum tasks to include
            
        Returns:
            Dictionary with task statistics and history
        """
        tasks = self.get_tasks_by_bot(bot_id, workspace_id, limit)
        
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]
        in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
        
        avg_confidence = (
            sum(t.confidence for t in completed) / len(completed)
            if completed else 0.0
        )
        
        return {
            "bot_id": bot_id,
            "total_tasks": len(tasks),
            "completed": len(completed),
            "failed": len(failed),
            "in_progress": len(in_progress),
            "success_rate": len(completed) / len(tasks) if tasks else 0.0,
            "avg_confidence": avg_confidence,
            "recent_tasks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "confidence": t.confidence,
                }
                for t in tasks[:10]
            ],
        }
    
    # =========================================================================
    # Decision Operations
    # =========================================================================
    
    def save_decision(
        self,
        decision_id: str,
        decision_type: str,
        participants: List[str],
        positions: Dict[str, str],
        reasoning: str,
        final_decision: str,
        confidence: float,
        task_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> str:
        """Save a decision to the audit trail.
        
        Args:
            decision_id: Unique decision ID
            decision_type: Type of decision (consensus, vote, escalation)
            participants: List of bot IDs that participated
            positions: Map of bot_id -> their position
            reasoning: Explanation of the decision
            final_decision: The final decision made
            confidence: Confidence in the decision (0.0-1.0)
            task_id: Optional related task ID
            workspace_id: Optional workspace ID
            
        Returns:
            Decision ID
        """
        conn = self.memory_store._get_connection()
        
        conn.execute(
            """
            INSERT INTO coordinator_decisions (
                id, decision_type, task_id, participants, positions,
                reasoning, final_decision, confidence, timestamp, workspace_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                decision_type,
                task_id,
                json.dumps(participants),
                json.dumps(positions),
                reasoning,
                final_decision,
                confidence,
                datetime.now().timestamp(),
                workspace_id,
            )
        )
        conn.commit()
        
        logger.debug(f"Decision saved: {decision_id}")
        return decision_id
    
    def get_decision(self, decision_id: str) -> Optional[Dict]:
        """Get a decision by ID.
        
        Args:
            decision_id: The decision ID
            
        Returns:
            Decision dictionary or None
        """
        conn = self.memory_store._get_connection()
        
        cursor = conn.execute(
            "SELECT * FROM coordinator_decisions WHERE id = ?",
            (decision_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._row_to_decision(row)
    
    def get_decisions_for_task(self, task_id: str) -> List[Dict]:
        """Get all decisions related to a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of decision dictionaries
        """
        conn = self.memory_store._get_connection()
        
        cursor = conn.execute(
            """
            SELECT * FROM coordinator_decisions
            WHERE task_id = ?
            ORDER BY timestamp DESC
            """,
            (task_id,)
        )
        
        decisions = []
        for row in cursor.fetchall():
            decisions.append(self._row_to_decision(row))
        
        return decisions
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> BotMessage:
        """Convert database row to BotMessage."""
        context = {}
        if row['context']:
            try:
                context = json.loads(row['context'])
            except (json.JSONDecodeError, TypeError):
                context = {}
        
        return BotMessage(
            id=row['id'],
            sender_id=row['sender_id'],
            recipient_id=row['recipient_id'],
            message_type=MessageType(row['message_type']),
            content=row['content'],
            conversation_id=row['conversation_id'],
            context=context,
            timestamp=datetime.fromtimestamp(row['timestamp']),
            response_to_id=row['response_to_id'],
        )
    
    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        """Convert database row to Task."""
        requirements = []
        if row['requirements']:
            try:
                requirements = json.loads(row['requirements'])
            except (json.JSONDecodeError, TypeError):
                requirements = []
        
        task = Task(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            domain=row['domain'],
            assigned_to=row['assigned_to'],
            created_by=row['created_by'],
            status=TaskStatus(row['status']),
            created_at=datetime.fromtimestamp(row['created_at']),
            started_at=datetime.fromtimestamp(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromtimestamp(row['completed_at']) if row['completed_at'] else None,
            due_date=datetime.fromtimestamp(row['due_date']) if row['due_date'] else None,
            requirements=requirements,
            result=row['result'] or "",
            confidence=row['confidence'] or 0.5,
            parent_task_id=row['parent_task_id'],
        )
        
        return task
    
    @staticmethod
    def _row_to_decision(row: sqlite3.Row) -> Dict:
        """Convert database row to decision dictionary."""
        participants = []
        positions = {}
        
        if row['participants']:
            try:
                participants = json.loads(row['participants'])
            except (json.JSONDecodeError, TypeError):
                participants = []
        
        if row['positions']:
            try:
                positions = json.loads(row['positions'])
            except (json.JSONDecodeError, TypeError):
                positions = {}
        
        return {
            "id": row['id'],
            "decision_type": row['decision_type'],
            "task_id": row['task_id'],
            "participants": participants,
            "positions": positions,
            "reasoning": row['reasoning'],
            "final_decision": row['final_decision'],
            "confidence": row['confidence'],
            "timestamp": datetime.fromtimestamp(row['timestamp']),
        }
