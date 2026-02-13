"""Multi-agent memory system for per-bot learning and cross-pollination.

This module provides classes to manage bot-specific memories, shared workspace memories,
and the mechanisms for promoting private learnings to shared knowledge.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger

from nanobot.memory.models import Learning
from nanobot.memory.store import TurboMemoryStore


@dataclass
class BotMemory:
    """Per-bot private memory container.
    
    Each bot maintains a set of private learnings that are specific to their
    domain or role. These can be promoted to shared memory via cross-pollination.
    """
    bot_id: str
    bot_role: str  # "leader", "researcher", "coder", etc.
    store: TurboMemoryStore
    
    # Cache of private learnings (loaded on demand)
    _private_learnings: dict[str, Learning] = field(default_factory=dict)
    _loaded: bool = False
    
    def add_learning(
        self,
        content: str,
        source: str,
        sentiment: str = "neutral",
        confidence: float = 0.8,
        tool_name: Optional[str] = None,
        recommendation: str = "",
        is_private: bool = True,
    ) -> Learning:
        """Add a learning to this bot's memory.
        
        Args:
            content: The insight text
            source: "user_feedback" or "self_evaluation"
            sentiment: "positive", "negative", or "neutral"
            confidence: Confidence score (0.0-1.0)
            tool_name: Optional tool-specific learning
            recommendation: Actionable instruction
            is_private: If True, private to this bot; if False, shared workspace
            
        Returns:
            The created Learning object
        """
        learning = Learning(
            id=str(uuid.uuid4()),
            content=content,
            source=source,
            sentiment=sentiment,
            confidence=confidence,
            tool_name=tool_name,
            recommendation=recommendation,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "bot_id": self.bot_id,
                "bot_role": self.bot_role,
                "is_private": is_private,
            }
        )
        
        # Save to database with bot-scoping
        self.store.save_learning_with_bot_scope(learning, self.bot_id, is_private)
        
        # Cache locally
        self._private_learnings[learning.id] = learning
        
        logger.info(
            f"Bot {self.bot_id} learned: {content[:50]}... "
            f"(private={is_private})"
        )
        
        return learning
    
    def get_private_learnings(self) -> list[Learning]:
        """Get all private learnings for this bot.
        
        Returns:
            List of Learning objects that are private to this bot
        """
        if not self._loaded:
            self._load_private_learnings()
        
        return list(self._private_learnings.values())
    
    def _load_private_learnings(self) -> None:
        """Load private learnings from database."""
        learnings = self.store.get_learnings_by_bot(self.bot_id, private_only=True)
        self._private_learnings = {l.id: l for l in learnings}
        self._loaded = True
    
    def promote_learning(
        self,
        learning_id: str,
        reason: str = "Applicable across team"
    ) -> bool:
        """Promote a private learning to shared memory.
        
        This is called during cross-pollination to make a bot's insight
        available to the entire team.
        
        Args:
            learning_id: ID of the learning to promote
            reason: Reason for promotion
            
        Returns:
            True if successful, False otherwise
        """
        if learning_id not in self._private_learnings:
            logger.warning(f"Learning {learning_id} not found in bot memory")
            return False
        
        learning = self._private_learnings[learning_id]
        
        # Update in database
        self.store.promote_learning_to_shared(learning_id, self.bot_id, reason)
        
        logger.info(
            f"Promoted learning from {self.bot_id}: {learning.content[:50]}... "
            f"(reason: {reason})"
        )
        
        return True


@dataclass
class SharedMemoryPool:
    """Workspace-wide shared memory accessed by all bots.
    
    The shared pool contains learnings that have been promoted from individual
    bot memories or created as workspace-wide insights.
    """
    workspace_id: str
    store: TurboMemoryStore
    
    # Cache of shared learnings
    _shared_learnings: dict[str, Learning] = field(default_factory=dict)
    _loaded: bool = False
    
    def get_shared_learnings(self) -> list[Learning]:
        """Get all shared learnings in the workspace.
        
        Returns:
            List of shared Learning objects
        """
        if not self._loaded:
            self._load_shared_learnings()
        
        return list(self._shared_learnings.values())
    
    def _load_shared_learnings(self) -> None:
        """Load shared learnings from database."""
        learnings = self.store.get_learnings_by_scope(
            workspace_id=self.workspace_id,
            private=False
        )
        self._shared_learnings = {l.id: l for l in learnings}
        self._loaded = True
    
    def get_learnings_by_domain(self, domain: str) -> list[Learning]:
        """Get shared learnings for a specific domain.
        
        Args:
            domain: The domain ("research", "development", "community", etc.)
            
        Returns:
            List of shared learnings in that domain
        """
        if not self._loaded:
            self._load_shared_learnings()
        
        return [
            l for l in self._shared_learnings.values()
            if l.metadata.get("domain") == domain
        ]
    
    def invalidate_cache(self) -> None:
        """Invalidate the shared learnings cache (call after updates)."""
        self._shared_learnings.clear()
        self._loaded = False


@dataclass
class CrossPollination:
    """Mechanism for promoting valuable private learnings to shared memory.
    
    Cross-pollination analyzes each bot's private learnings and promotes
    those that are broadly applicable to the shared memory pool.
    """
    store: TurboMemoryStore
    
    # Confidence threshold for promotion (insights below this stay private)
    confidence_threshold: float = 0.75
    
    # Maximum insights to promote per bot per run (to avoid spam)
    max_promotions_per_bot: int = 3
    
    def run_cross_pollination(self, bot_ids: list[str]) -> dict[str, int]:
        """Run cross-pollination across multiple bots.
        
        Analyzes each bot's private learnings and promotes applicable ones
        to shared memory.
        
        Args:
            bot_ids: List of bot IDs to process
            
        Returns:
            Dictionary mapping bot_id -> count of promotions
        """
        results = {}
        
        for bot_id in bot_ids:
            promoted_count = self._pollinate_bot(bot_id)
            results[bot_id] = promoted_count
            logger.info(f"Cross-pollination for {bot_id}: {promoted_count} promoted")
        
        return results
    
    def _pollinate_bot(self, bot_id: str) -> int:
        """Pollinate a single bot's learnings.
        
        Args:
            bot_id: The bot to process
            
        Returns:
            Number of learnings promoted
        """
        # Get bot's private learnings
        learnings = self.store.get_learnings_by_bot(bot_id, private_only=True)
        
        # Filter by confidence and promotion count
        candidates = [
            l for l in learnings
            if l.confidence >= self.confidence_threshold
            and l.metadata.get("promotion_count", 0) < 3
        ]
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda l: l.confidence, reverse=True)
        
        # Promote top N candidates
        promoted_count = 0
        for learning in candidates[:self.max_promotions_per_bot]:
            self.store.promote_learning_to_shared(
                learning.id,
                bot_id,
                reason="Cross-pollination: High confidence insight"
            )
            promoted_count += 1
        
        return promoted_count
    
    def get_promotion_history(self, learning_id: str) -> Optional[dict]:
        """Get the promotion history for a learning.
        
        Args:
            learning_id: ID of the learning
            
        Returns:
            Dictionary with promotion details or None if not found
        """
        return self.store.get_promotion_history(learning_id)


@dataclass
class BotExpertise:
    """Tracks domain expertise confidence for each bot.
    
    As bots interact with different domains, their expertise in those
    domains increases, helping the team route tasks to the best bot.
    """
    store: TurboMemoryStore
    
    # Cache of expertise scores
    _expertise_cache: dict[tuple[str, str], float] = field(default_factory=dict)
    
    def record_interaction(
        self,
        bot_id: str,
        domain: str,
        successful: bool = True
    ) -> None:
        """Record a bot's interaction in a domain.
        
        Args:
            bot_id: The bot that performed the action
            domain: The domain ("research", "development", etc.)
            successful: Whether the interaction was successful
        """
        self.store.record_bot_expertise(bot_id, domain, successful)
        
        # Invalidate cache
        key = (bot_id, domain)
        if key in self._expertise_cache:
            del self._expertise_cache[key]
        
        logger.debug(f"Recorded expertise: {bot_id} in {domain} (success={successful})")
    
    def get_expertise_score(self, bot_id: str, domain: str) -> float:
        """Get the expertise confidence score for a bot in a domain.
        
        Args:
            bot_id: The bot
            domain: The domain
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        key = (bot_id, domain)
        
        if key not in self._expertise_cache:
            score = self.store.get_bot_expertise(bot_id, domain)
            self._expertise_cache[key] = score
        
        return self._expertise_cache[key]
    
    def get_best_bot_for_domain(self, domain: str, bot_ids: list[str]) -> str:
        """Find the bot with highest expertise in a domain.
        
        Args:
            domain: The domain
            bot_ids: List of candidate bots
            
        Returns:
            ID of the bot with highest expertise
        """
        best_bot = bot_ids[0]
        best_score = self.get_expertise_score(best_bot, domain)
        
        for bot_id in bot_ids[1:]:
            score = self.get_expertise_score(bot_id, domain)
            if score > best_score:
                best_bot = bot_id
                best_score = score
        
        return best_bot
    
    def get_expertise_report(self, bot_id: str) -> dict[str, float]:
        """Get all expertise scores for a bot across domains.
        
        Args:
            bot_id: The bot
            
        Returns:
            Dictionary mapping domain -> confidence score
        """
        return self.store.get_all_bot_expertise(bot_id)
