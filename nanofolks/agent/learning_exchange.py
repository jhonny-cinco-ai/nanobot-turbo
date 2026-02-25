"""Learning Exchange system for sharing insights across bot instances.

This module provides classes for queuing high-confidence insights and sharing
them with other bots within the same workspace. Implements automatic insight
detection, filtering, and cross-bot distribution.

Key concepts:
- LearningPackage: Encapsulates a shareable insight with metadata
- InsightQueue: Manages queuing of insights for distribution
- ApplicabilityRule: Determines workspace-scoped applicability
- LearningExchange: Main integration point for insight sharing
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

if TYPE_CHECKING:
    pass


class InsightCategory(Enum):
    """Categories of insights that can be shared."""
    USER_PREFERENCE = "user_preference"  # User likes certain response styles
    TOOL_PATTERN = "tool_pattern"        # Tool works well in certain contexts
    REASONING_PATTERN = "reasoning_pattern"  # Successful reasoning approaches
    ERROR_PATTERN = "error_pattern"      # Common errors and solutions
    PERFORMANCE_TIP = "performance_tip"  # Speed/efficiency improvements
    CONTEXT_TIP = "context_tip"          # Knowledge about domain/project
    WORKFLOW_TIP = "workflow_tip"        # Process improvements
    INTEGRATION_TIP = "integration_tip"  # How tools work together


class ApplicabilityScope(Enum):
    """Scope of insight applicability."""
    GENERAL = "general"          # Applies to all workspaces (#general)
    PROJECT = "project"          # Applies to project workspace (#project-*)
    TEAM = "team"                # Applies to specific team workspace
    BOT_SPECIFIC = "bot_specific"  # Only for specific bot (DM @bot)


@dataclass
class LearningPackage:
    """A packaged insight ready for sharing with other bots.

    Represents a high-confidence observation that can be distributed
    to other bot instances for improved collaborative performance.
    """

    # Core insight data (required)
    category: InsightCategory  # What type of insight is this?
    title: str  # Short summary for display
    description: str  # Detailed explanation
    confidence: float  # 0.0-1.0 (must be >= 0.85 to queue)
    source_bot: str  # Which bot created this insight?

    # Scope and applicability (required)
    scope: ApplicabilityScope = ApplicabilityScope.GENERAL  # Who should receive this?

    # Identity
    package_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Applicability
    applicable_workspaces: List[str] = field(default_factory=list)
        # For TEAM/PROJECT scope: which workspaces?
    applicable_bots: List[str] = field(default_factory=list)
        # For BOT_SPECIFIC scope: which bots?

    # Source information
    source_workspace: str = "default"  # Where was this learned?
    created_at: datetime = field(default_factory=datetime.now)

    # Content metadata
    evidence: Dict = field(default_factory=dict)
        # Supporting data (successful examples, patterns observed, etc.)
    context: Dict = field(default_factory=dict)
        # Additional context (tool versions, environment, etc.)

    # Distribution state
    queued_at: Optional[datetime] = None  # When was this queued?
    distributed_to: List[str] = field(default_factory=list)
        # Which bots have received this?

    def is_queued(self) -> bool:
        """Check if this package has been queued for distribution."""
        return self.queued_at is not None

    def has_been_distributed_to(self, bot_name: str) -> bool:
        """Check if this insight has been shared with a specific bot."""
        return bot_name in self.distributed_to

    def mark_distributed(self, bot_names: List[str]):
        """Mark this insight as distributed to specific bots."""
        self.distributed_to.extend(bot_names)
        # Remove duplicates
        self.distributed_to = list(set(self.distributed_to))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "package_id": self.package_id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "scope": self.scope.value,
            "applicable_workspaces": self.applicable_workspaces,
            "applicable_bots": self.applicable_bots,
            "source_bot": self.source_bot,
            "source_workspace": self.source_workspace,
            "created_at": self.created_at.isoformat(),
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "evidence": self.evidence,
            "context": self.context,
            "distributed_to": self.distributed_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LearningPackage":
        """Create from dictionary (deserialization)."""
        package = cls(
            package_id=data.get("package_id", str(uuid.uuid4())),
            category=InsightCategory(data["category"]),
            title=data["title"],
            description=data["description"],
            confidence=data["confidence"],
            scope=ApplicabilityScope(data["scope"]),
            applicable_workspaces=data.get("applicable_workspaces", []),
            applicable_bots=data.get("applicable_bots", []),
            source_bot=data["source_bot"],
            source_workspace=data.get("source_workspace", "default"),
            evidence=data.get("evidence", {}),
            context=data.get("context", {}),
            distributed_to=data.get("distributed_to", []),
        )
        if data.get("queued_at"):
            package.queued_at = datetime.fromisoformat(data["queued_at"])
        if data.get("created_at"):
            package.created_at = datetime.fromisoformat(data["created_at"])
        return package


@dataclass
class InsightQueue:
    """Manages a queue of insights waiting for distribution.

    Handles queuing, filtering, and tracking of insights that are ready
    to be shared with other bot instances.
    """

    workspace_id: str = "default"
    bot_name: str = "leader"
    _queue: List[LearningPackage] = field(default_factory=list)
    _processed: List[str] = field(default_factory=list)
        # Package IDs that have been processed

    def enqueue(self, package: LearningPackage) -> bool:
        """Add an insight to the queue.

        Args:
            package: The LearningPackage to queue

        Returns:
            True if queued, False if already exists
        """
        # Check if already queued (by ID)
        if any(p.package_id == package.package_id for p in self._queue):
            return False

        # Mark as queued
        package.queued_at = datetime.now()
        self._queue.append(package)
        return True

    def dequeue(self) -> Optional[LearningPackage]:
        """Get and remove the next insight from the queue.

        Returns:
            The next LearningPackage, or None if queue empty
        """
        if not self._queue:
            return None

        package = self._queue.pop(0)
        self._processed.append(package.package_id)
        return package

    def peek(self) -> Optional[LearningPackage]:
        """Look at next insight without removing it.

        Returns:
            The next LearningPackage, or None if queue empty
        """
        return self._queue[0] if self._queue else None

    def get_all_pending(self) -> List[LearningPackage]:
        """Get all pending insights without removing them.

        Returns:
            List of queued LearningPackages
        """
        return list(self._queue)

    def get_by_scope(self, scope: ApplicabilityScope) -> List[LearningPackage]:
        """Get all pending insights with a specific scope.

        Args:
            scope: The ApplicabilityScope to filter by

        Returns:
            List of matching LearningPackages
        """
        return [p for p in self._queue if p.scope == scope]

    def get_by_category(self, category: InsightCategory) -> List[LearningPackage]:
        """Get all pending insights with a specific category.

        Args:
            category: The InsightCategory to filter by

        Returns:
            List of matching LearningPackages
        """
        return [p for p in self._queue if p.category == category]

    def has_pending(self) -> bool:
        """Check if there are any pending insights.

        Returns:
            True if queue is not empty
        """
        return len(self._queue) > 0

    def clear(self):
        """Clear all pending insights from the queue."""
        self._queue.clear()

    def size(self) -> int:
        """Get the number of pending insights.

        Returns:
            Number of items in queue
        """
        return len(self._queue)

    def processed_count(self) -> int:
        """Get the number of insights that have been processed.

        Returns:
            Count of processed package IDs
        """
        return len(self._processed)

    def to_dict(self) -> dict:
        """Convert queue state to dictionary."""
        return {
            "workspace_id": self.workspace_id,
            "bot_name": self.bot_name,
            "pending_count": len(self._queue),
            "processed_count": len(self._processed),
            "pending_packages": [p.to_dict() for p in self._queue],
            "processed_ids": self._processed,
        }


class ApplicabilityRule:
    """Determines if an insight should be shared with specific workspaces/bots.

    Implements workspace-scoped learning rules:
    - GENERAL insights (#general workspace) → share with all bots
    - PROJECT insights (#project-*) → share with project team
    - TEAM insights → share with specific team
    - BOT_SPECIFIC insights (DM @bot) → bot-specific learning
    """

    @staticmethod
    def applies_to_workspace(package: LearningPackage,
                            target_workspace: str) -> bool:
        """Check if an insight applies to a specific workspace.

        Args:
            package: The LearningPackage to evaluate
            target_workspace: The target workspace ID

        Returns:
            True if insight should be shared with this workspace
        """
        if package.scope == ApplicabilityScope.GENERAL:
            return True

        if package.scope == ApplicabilityScope.PROJECT:
            # Project insights apply to #project-* workspaces
            if target_workspace.startswith("#project-"):
                # If specified, only apply to listed workspaces
                if package.applicable_workspaces:
                    return target_workspace in package.applicable_workspaces
                return True
            return False

        if package.scope == ApplicabilityScope.TEAM:
            # Team insights apply to specific teams
            if package.applicable_workspaces:
                return target_workspace in package.applicable_workspaces
            return False

        if package.scope == ApplicabilityScope.BOT_SPECIFIC:
            # These should only be applied by the WorkLogManager
            return False

        return False

    @staticmethod
    def applies_to_bot(package: LearningPackage,
                      target_bot: str) -> bool:
        """Check if an insight applies to a specific bot.

        Args:
            package: The LearningPackage to evaluate
            target_bot: The target bot name

        Returns:
            True if insight should be available to this bot
        """
        if package.scope in [ApplicabilityScope.GENERAL,
                           ApplicabilityScope.PROJECT]:
            return True

        if package.scope == ApplicabilityScope.TEAM:
            if package.applicable_bots:
                return target_bot in package.applicable_bots
            # If no specific bots listed, apply to all
            return True

        if package.scope == ApplicabilityScope.BOT_SPECIFIC:
            if package.applicable_bots:
                return target_bot in package.applicable_bots
            return False

        return False


class LearningExchange:
    """Main interface for the Learning Exchange system.

    Coordinates queuing, distribution, and application of insights
    across bot instances. Handles high-level orchestration of the
    learning exchange workflow with SQLite persistence.
    """

    def __init__(self, bot_name: str = "leader",
                 workspace_id: str = "default",
                 store=None):
        """Initialize the Learning Exchange system.

        Args:
            bot_name: Name of this bot instance
            workspace_id: Current workspace ID
            store: Optional InsightStore for persistence (lazy-loaded if None)
        """
        self.bot_name = bot_name
        self.workspace_id = workspace_id
        self.queue = InsightQueue(workspace_id=workspace_id, bot_name=bot_name)
        self._store = store  # Will be lazy-loaded from insight_store module if needed
        self._distribution_callbacks: Dict[str, List[Callable]] = {}

    def _get_store(self):
        """Lazy-load InsightStore (avoids circular imports)."""
        if self._store is None:
            from nanofolks.agent.insight_store import InsightStore
            self._store = InsightStore()
        return self._store

    def load_pending_packages(self) -> int:
        """Load pending packages from persistence on startup.

        Returns:
            Number of packages loaded
        """
        store = self._get_store()
        pending = store.get_pending_packages(limit=1000)

        for package in pending:
            self.queue.enqueue(package)

        if pending:
            from loguru import logger
            logger.info(f"Loaded {len(pending)} pending packages from persistence")

        return len(pending)

    def queue_insight(self, category: InsightCategory, title: str,
                     description: str, confidence: float,
                     scope: ApplicabilityScope = ApplicabilityScope.GENERAL,
                     applicable_workspaces: Optional[List[str]] = None,
                     applicable_bots: Optional[List[str]] = None,
                     evidence: Optional[Dict] = None,
                     context: Optional[Dict] = None) -> Optional[LearningPackage]:
        """Create and queue an insight for distribution.

        Only insights with confidence >= 0.85 will be queued.
        Queued insights are persisted to SQLite.

        Args:
            category: What type of insight?
            title: Short summary
            description: Detailed explanation
            confidence: Confidence level (0.0-1.0)
            scope: Who should receive this?
            applicable_workspaces: Specific workspaces (for TEAM/PROJECT)
            applicable_bots: Specific bots (for TEAM/BOT_SPECIFIC)
            evidence: Supporting data
            context: Additional context

        Returns:
            The LearningPackage if queued, None if confidence too low
        """
        # Only queue high-confidence insights
        if confidence < 0.85:
            return None

        package = LearningPackage(
            category=category,
            title=title,
            description=description,
            confidence=confidence,
            scope=scope,
            applicable_workspaces=applicable_workspaces or [],
            applicable_bots=applicable_bots or [],
            source_bot=self.bot_name,
            source_workspace=self.workspace_id,
            evidence=evidence or {},
            context=context or {},
        )

        # Queue in memory
        self.queue.enqueue(package)

        # Persist to database
        try:
            store = self._get_store()
            store.save_package(package)
        except Exception as e:
            from loguru import logger
            logger.warning(f"Failed to persist queued insight: {e}")

        return package

    def register_distribution_callback(self, bot_name: str,
                                      callback: Callable[[LearningPackage], bool]):
        """Register a callback for distributing insights to a specific bot.

        Args:
            bot_name: Target bot name
            callback: Function to call with the package. Should return True
                     if successfully distributed, False otherwise.
        """
        if bot_name not in self._distribution_callbacks:
            self._distribution_callbacks[bot_name] = []
        self._distribution_callbacks[bot_name].append(callback)

    def distribute_insights(self) -> Dict[str, int]:
        """Distribute all queued insights to appropriate targets.

        Processes all pending insights and distributes them based on
        applicability rules. Updates persistence to mark packages as distributed.

        Returns:
            Dict with distribution statistics:
            {
                "total_queued": int,
                "total_distributed": int,
                "by_scope": {"general": int, "project": int, ...},
                "by_bot": {"researcher": int, "coder": int, ...}
            }
        """
        stats = {
            "total_queued": self.queue.size(),
            "total_distributed": 0,
            "by_scope": {},
            "by_bot": {},
            "skipped": []
        }

        store = self._get_store()

        while self.queue.has_pending():
            package = self.queue.dequeue()
            if not package:
                break

            distributed_to = []

            # Distribute to registered callbacks (bots)
            for bot_name, callbacks in self._distribution_callbacks.items():
                if ApplicabilityRule.applies_to_bot(package, bot_name):
                    for callback in callbacks:
                        try:
                            if callback(package):
                                distributed_to.append(bot_name)
                                break
                        except Exception:
                            # Log but continue with other bots
                            pass

            if distributed_to:
                package.mark_distributed(distributed_to)
                stats["total_distributed"] += 1

                # Track by scope
                scope_name = package.scope.value
                stats["by_scope"][scope_name] = stats["by_scope"].get(scope_name, 0) + 1

                # Track by bot
                for bot_name in distributed_to:
                    stats["by_bot"][bot_name] = stats["by_bot"].get(bot_name, 0) + 1

                # Persist distribution status
                try:
                    store.mark_distributed(package.package_id, distributed_to)
                except Exception as e:
                    from loguru import logger
                    logger.warning(f"Failed to update distribution status: {e}")

                # Save to Turbo Memory for cross-bot learning
                self._save_to_turbo_memory(package)
            else:
                stats["skipped"].append(package.package_id)

        return stats

    def _save_to_turbo_memory(self, package: LearningPackage) -> None:
        """Save distributed insight to Turbo Memory for persistent learning.

        Converts the LearningPackage to a Learning object and saves it
        to Turbo Memory's learnings table.

        Args:
            package: The distributed LearningPackage
        """
        try:
            # Convert to Learning object for Turbo Memory
            learning = LearningExchange.create_learning_from_package(package)

            if not learning:
                return

            # Get Turbo Memory store
            from nanofolks.config.loader import get_data_dir
            from nanofolks.memory.store import TurboMemoryStore

            memory_store = TurboMemoryStore(get_data_dir())

            # Save as shared learning with bot-scoping metadata
            learning_id = memory_store.save_learning_with_bot_scope(
                learning,
                bot_id=package.source_bot,
                is_private=False
            )

            from loguru import logger
            logger.info(
                f"Saved distributed insight to Turbo Memory: {learning.content[:50]}... "
                f"(id: {learning_id})"
            )

        except ImportError:
            # Turbo Memory not available, skip
            pass
        except Exception as e:
            from loguru import logger
            logger.warning(f"Failed to save to Turbo Memory: {e}")

    def get_applicable_insights(self, workspace_id: Optional[str] = None,
                               bot_name: Optional[str] = None) -> List[LearningPackage]:
        """Get all insights applicable to a specific context.

        Args:
            workspace_id: Target workspace (defaults to current)
            bot_name: Target bot (defaults to self.bot_name)

        Returns:
            List of applicable LearningPackages
        """
        workspace_id = workspace_id or self.workspace_id
        bot_name = bot_name or self.bot_name

        applicable = []
        for package in self.queue.get_all_pending():
            if (ApplicabilityRule.applies_to_workspace(package, workspace_id) and
                ApplicabilityRule.applies_to_bot(package, bot_name)):
                applicable.append(package)

        return applicable

    def clear_queue(self):
        """Clear all pending insights from the queue."""
        self.queue.clear()

    def get_queue_state(self) -> dict:
        """Get current queue state for debugging/monitoring.

        Returns:
            Dictionary with queue statistics and pending packages
        """
        return self.queue.to_dict()

    @staticmethod
    def create_learning_from_package(package: LearningPackage):
        """
        Convert a received LearningPackage into a Learning object.

        This is used when a bot receives a distributed insight and wants to
        store it in its own Turbo Memory for reference and decay tracking.

        The created Learning object:
        - Has source="learning_exchange" to indicate it came from distribution
        - Starts with fresh relevance_score of 1.0 (independent decay)
        - Preserves the original insight category and confidence
        - Includes evidence of where it came from

        Args:
            package: The LearningPackage received from another bot

        Returns:
            Learning object ready to store in Turbo Memory
        """
        from datetime import datetime
        from uuid import uuid4

        from nanofolks.memory.models import Learning

        # Map category to sentiment for Learning object
        category_to_sentiment = {
            InsightCategory.USER_PREFERENCE: "positive",
            InsightCategory.ERROR_PATTERN: "negative",
            InsightCategory.REASONING_PATTERN: "positive",
            InsightCategory.TOOL_PATTERN: "positive",
            InsightCategory.PERFORMANCE_TIP: "positive",
            InsightCategory.CONTEXT_TIP: "neutral",
            InsightCategory.WORKFLOW_TIP: "positive",
            InsightCategory.INTEGRATION_TIP: "positive",
        }

        sentiment = category_to_sentiment.get(package.category, "neutral")

        # Create recommendation from package description
        recommendation = f"Apply this learning: {package.description}"

        now = datetime.now()

        return Learning(
            id=str(uuid4()),
            content=package.title,  # Use title as concise content summary
            source="learning_exchange",  # Mark as from Learning Exchange
            sentiment=sentiment,
            confidence=package.confidence,
            recommendation=recommendation,
            superseded_by=None,
            content_embedding=None,
            created_at=now,
            updated_at=now,
            relevance_score=1.0,  # Fresh score - independent decay
            times_accessed=0,
            last_accessed=None,
            metadata={
                "source_bot": package.source_bot,
                "source_workspace": package.source_workspace,
                "category": package.category.value,
                "scope": package.scope.value,
            },
        )

    def receive_learning_package(self, package: LearningPackage, store):
        """
        Receive a distributed learning package and store it in local Turbo Memory.

        This is the receiving-side handler that converts a LearningPackage into
        a Learning object and stores it in the bot's local memory system.

        Args:
            package: The LearningPackage received from another bot
            store: TurboMemoryStore instance to persist the learning

        Returns:
            The stored Learning object or None if storage failed
        """
        try:
            # Convert package to learning object
            learning = self.create_learning_from_package(package)

            # Store in local Turbo Memory as shared learning with source bot attribution
            store.save_learning_with_bot_scope(
                learning,
                bot_id=package.source_bot,
                is_private=False
            )

            from loguru import logger
            logger.info(
                f"Received learning package from {package.source_bot}: "
                f"{learning.id} ({package.category.value})"
            )

            return learning
        except Exception as e:
            from loguru import logger
            logger.warning(f"Failed to receive learning package: {e}")
            return None
