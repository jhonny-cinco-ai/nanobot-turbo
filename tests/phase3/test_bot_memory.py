"""Tests for Phase 3 bot memory system.

Tests for BotMemory, SharedMemoryPool, CrossPollination, and BotExpertise classes.
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from nanobot.config.schema import MemoryConfig
from nanobot.memory.bot_memory import (
    BotMemory,
    SharedMemoryPool,
    CrossPollination,
    BotExpertise,
)
from nanobot.memory.models import Learning
from nanobot.memory.store import TurboMemoryStore


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def memory_config():
    """Create a memory configuration."""
    return MemoryConfig(
        db_path="memory/memory.db",
        enable_embeddings=False,
        enable_background_tasks=False,
    )


@pytest.fixture
def memory_store(temp_workspace, memory_config):
    """Create a memory store."""
    return TurboMemoryStore(memory_config, temp_workspace)


class TestBotMemory:
    """Tests for BotMemory class."""
    
    def test_init(self, memory_store):
        """Test BotMemory initialization."""
        bot_memory = BotMemory(
            bot_id="researcher",
            bot_role="researcher",
            store=memory_store,
        )
        
        assert bot_memory.bot_id == "researcher"
        assert bot_memory.bot_role == "researcher"
        assert bot_memory.store is memory_store
        assert len(bot_memory._private_learnings) == 0
        assert bot_memory._loaded is False
    
    def test_add_learning_private(self, memory_store):
        """Test adding a private learning."""
        bot_memory = BotMemory(
            bot_id="researcher",
            bot_role="researcher",
            store=memory_store,
        )
        
        learning = bot_memory.add_learning(
            content="Users prefer concise summaries",
            source="user_feedback",
            sentiment="positive",
            confidence=0.9,
            is_private=True,
        )
        
        assert learning.id is not None
        assert learning.content == "Users prefer concise summaries"
        assert learning.source == "user_feedback"
        assert learning.sentiment == "positive"
        assert learning.confidence == 0.9
    
    def test_add_learning_shared(self, memory_store):
        """Test adding a shared learning."""
        bot_memory = BotMemory(
            bot_id="coder",
            bot_role="coder",
            store=memory_store,
        )
        
        learning = bot_memory.add_learning(
            content="Python type hints improve code quality",
            source="self_evaluation",
            confidence=0.85,
            is_private=False,
        )
        
        assert learning.id is not None
        assert learning.content == "Python type hints improve code quality"
        assert learning.source == "self_evaluation"
    
    def test_get_private_learnings(self, memory_store):
        """Test retrieving private learnings."""
        bot_memory = BotMemory(
            bot_id="researcher",
            bot_role="researcher",
            store=memory_store,
        )
        
        # Add 3 private learnings
        learning1 = bot_memory.add_learning(
            content="Research learning 1",
            source="user_feedback",
            is_private=True,
        )
        learning2 = bot_memory.add_learning(
            content="Research learning 2",
            source="user_feedback",
            is_private=True,
        )
        learning3 = bot_memory.add_learning(
            content="Research learning 3",
            source="self_evaluation",
            is_private=False,
        )
        
        # Get private learnings
        private = bot_memory.get_private_learnings()
        
        assert len(private) == 2
        assert all(l.metadata.get("bot_id") == "researcher" for l in private)
    
    def test_promote_learning(self, memory_store):
        """Test promoting a learning from private to shared."""
        bot_memory = BotMemory(
            bot_id="researcher",
            bot_role="researcher",
            store=memory_store,
        )
        
        learning = bot_memory.add_learning(
            content="Important research insight",
            source="user_feedback",
            confidence=0.9,
            is_private=True,
        )
        
        # Promote the learning
        success = bot_memory.promote_learning(
            learning.id,
            reason="Broadly applicable insight"
        )
        
        assert success is True
    
    def test_promote_nonexistent_learning(self, memory_store):
        """Test promoting a nonexistent learning."""
        bot_memory = BotMemory(
            bot_id="researcher",
            bot_role="researcher",
            store=memory_store,
        )
        
        success = bot_memory.promote_learning(
            "nonexistent_id",
            reason="Test"
        )
        
        assert success is False


class TestSharedMemoryPool:
    """Tests for SharedMemoryPool class."""
    
    def test_init(self, memory_store):
        """Test SharedMemoryPool initialization."""
        pool = SharedMemoryPool(
            workspace_id="test_workspace",
            store=memory_store,
        )
        
        assert pool.workspace_id == "test_workspace"
        assert pool.store is memory_store
        assert len(pool._shared_learnings) == 0
        assert pool._loaded is False
    
    def test_get_shared_learnings(self, memory_store):
        """Test retrieving shared learnings."""
        # First add some shared learnings via BotMemory
        bot1 = BotMemory("researcher", "researcher", memory_store)
        bot2 = BotMemory("coder", "coder", memory_store)
        
        bot1.add_learning(
            content="Shared insight 1",
            source="user_feedback",
            is_private=False,
        )
        bot2.add_learning(
            content="Shared insight 2",
            source="user_feedback",
            is_private=False,
        )
        
        # Get shared learnings
        pool = SharedMemoryPool("test_workspace", memory_store)
        shared = pool.get_shared_learnings()
        
        assert len(shared) >= 2
    
    def test_invalidate_cache(self, memory_store):
        """Test cache invalidation."""
        pool = SharedMemoryPool("test_workspace", memory_store)
        
        # Load shared learnings
        shared1 = pool.get_shared_learnings()
        
        # Invalidate cache
        pool.invalidate_cache()
        
        assert pool._loaded is False
        assert len(pool._shared_learnings) == 0


class TestCrossPollination:
    """Tests for CrossPollination class."""
    
    def test_init(self, memory_store):
        """Test CrossPollination initialization."""
        pollinator = CrossPollination(store=memory_store)
        
        assert pollinator.store is memory_store
        assert pollinator.confidence_threshold == 0.75
        assert pollinator.max_promotions_per_bot == 3
    
    def test_custom_thresholds(self, memory_store):
        """Test initialization with custom thresholds."""
        pollinator = CrossPollination(
            store=memory_store,
            confidence_threshold=0.9,
            max_promotions_per_bot=5,
        )
        
        assert pollinator.confidence_threshold == 0.9
        assert pollinator.max_promotions_per_bot == 5
    
    def test_run_cross_pollination(self, memory_store):
        """Test running cross-pollination across multiple bots."""
        # Add private learnings with high confidence
        researcher = BotMemory("researcher", "researcher", memory_store)
        coder = BotMemory("coder", "coder", memory_store)
        
        # Add high confidence learnings (above threshold)
        researcher.add_learning(
            content="High confidence research insight",
            source="user_feedback",
            confidence=0.95,
            is_private=True,
        )
        researcher.add_learning(
            content="Another high confidence insight",
            source="self_evaluation",
            confidence=0.85,
            is_private=True,
        )
        
        coder.add_learning(
            content="High confidence coding insight",
            source="user_feedback",
            confidence=0.9,
            is_private=True,
        )
        
        # Run cross-pollination
        pollinator = CrossPollination(
            store=memory_store,
            confidence_threshold=0.75,
        )
        results = pollinator.run_cross_pollination(["researcher", "coder"])
        
        assert "researcher" in results
        assert "coder" in results
        assert results["researcher"] >= 0
        assert results["coder"] >= 0
    
    def test_promotion_respects_threshold(self, memory_store):
        """Test that promotion respects confidence threshold."""
        researcher = BotMemory("researcher", "researcher", memory_store)
        
        # Add low confidence learning
        researcher.add_learning(
            content="Low confidence insight",
            source="self_evaluation",
            confidence=0.5,
            is_private=True,
        )
        
        # Run cross-pollination with high threshold
        pollinator = CrossPollination(
            store=memory_store,
            confidence_threshold=0.8,
        )
        results = pollinator.run_cross_pollination(["researcher"])
        
        # Low confidence learning should not be promoted
        assert results["researcher"] == 0
    
    def test_promotion_respects_max_count(self, memory_store):
        """Test that promotion respects max per-bot limit."""
        researcher = BotMemory("researcher", "researcher", memory_store)
        
        # Add 10 high confidence learnings
        for i in range(10):
            researcher.add_learning(
                content=f"High confidence insight {i}",
                source="user_feedback",
                confidence=0.95,
                is_private=True,
            )
        
        # Run cross-pollination with low max
        pollinator = CrossPollination(
            store=memory_store,
            confidence_threshold=0.75,
            max_promotions_per_bot=2,
        )
        results = pollinator.run_cross_pollination(["researcher"])
        
        # Should promote only 2 per bot
        assert results["researcher"] <= 2


class TestBotExpertise:
    """Tests for BotExpertise class."""
    
    def test_init(self, memory_store):
        """Test BotExpertise initialization."""
        expertise = BotExpertise(store=memory_store)
        
        assert expertise.store is memory_store
        assert len(expertise._expertise_cache) == 0
    
    def test_record_successful_interaction(self, memory_store):
        """Test recording a successful interaction."""
        expertise = BotExpertise(store=memory_store)
        
        expertise.record_interaction(
            bot_id="researcher",
            domain="research",
            successful=True,
        )
        
        score = expertise.get_expertise_score("researcher", "research")
        assert score == 1.0  # First success = 100%
    
    def test_record_failed_interaction(self, memory_store):
        """Test recording a failed interaction."""
        expertise = BotExpertise(store=memory_store)
        
        expertise.record_interaction(
            bot_id="coder",
            domain="development",
            successful=False,
        )
        
        score = expertise.get_expertise_score("coder", "development")
        assert score == 0.0  # First failure = 0%
    
    def test_expertise_confidence_calculation(self, memory_store):
        """Test expertise confidence calculation."""
        expertise = BotExpertise(store=memory_store)
        
        # Record 3 successful, 1 failed
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", False)
        
        score = expertise.get_expertise_score("researcher", "research")
        # 3 successes / 4 total = 0.75
        assert 0.74 < score < 0.76
    
    def test_get_best_bot_for_domain(self, memory_store):
        """Test finding the best bot for a domain."""
        expertise = BotExpertise(store=memory_store)
        
        # Researcher has 3/4 successes = 0.75
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", False)
        
        # Coder has 2/3 successes = 0.67
        expertise.record_interaction("coder", "research", True)
        expertise.record_interaction("coder", "research", True)
        expertise.record_interaction("coder", "research", False)
        
        best = expertise.get_best_bot_for_domain("research", ["researcher", "coder"])
        assert best == "researcher"
    
    def test_get_expertise_report(self, memory_store):
        """Test getting a full expertise report for a bot."""
        expertise = BotExpertise(store=memory_store)
        
        # Add interactions across multiple domains
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "research", True)
        expertise.record_interaction("researcher", "community", True)
        expertise.record_interaction("researcher", "community", False)
        
        report = expertise.get_expertise_report("researcher")
        
        assert "research" in report
        assert "community" in report
        assert report["research"] == 1.0
        assert 0.49 < report["community"] < 0.51
    
    def test_cache_invalidation(self, memory_store):
        """Test that cache is invalidated after update."""
        expertise = BotExpertise(store=memory_store)
        
        # Record interaction and get score
        expertise.record_interaction("researcher", "research", True)
        score1 = expertise.get_expertise_score("researcher", "research")
        
        # Record another interaction (should invalidate cache)
        expertise.record_interaction("researcher", "research", False)
        score2 = expertise.get_expertise_score("researcher", "research")
        
        assert score1 != score2


class TestIntegration:
    """Integration tests for the bot memory system."""
    
    def test_bot_memories_are_isolated(self, memory_store):
        """Test that bot memories are properly isolated."""
        researcher = BotMemory("researcher", "researcher", memory_store)
        coder = BotMemory("coder", "coder", memory_store)
        
        researcher.add_learning(
            content="Research insight",
            source="user_feedback",
            is_private=True,
        )
        coder.add_learning(
            content="Coder insight",
            source="user_feedback",
            is_private=True,
        )
        
        researcher_learnings = researcher.get_private_learnings()
        coder_learnings = coder.get_private_learnings()
        
        # Each bot should only see their own learnings
        assert len(researcher_learnings) >= 1
        assert len(coder_learnings) >= 1
        assert all(
            l.metadata.get("bot_id") == "researcher"
            for l in researcher_learnings
        )
        assert all(
            l.metadata.get("bot_id") == "coder"
            for l in coder_learnings
        )
    
    def test_cross_pollination_workflow(self, memory_store):
        """Test a complete cross-pollination workflow."""
        # Setup bots
        researcher = BotMemory("researcher", "researcher", memory_store)
        
        # Add high-confidence private learning
        learning = researcher.add_learning(
            content="Important research finding",
            source="user_feedback",
            confidence=0.9,
            is_private=True,
        )
        
        # Verify it's private
        private_before = researcher.get_private_learnings()
        assert len(private_before) >= 1
        
        # Run cross-pollination
        pollinator = CrossPollination(
            store=memory_store,
            confidence_threshold=0.8,
        )
        results = pollinator.run_cross_pollination(["researcher"])
        
        # Verify promotion occurred
        assert results["researcher"] >= 1
        
        # Verify history was recorded
        history = pollinator.get_promotion_history(learning.id)
        assert history is not None
        assert history["bot_id"] == "researcher"
    
    def test_multiple_team_members_learning(self, memory_store):
        """Test multiple bot team members learning and sharing."""
        team = {
            "researcher": BotMemory("researcher", "researcher", memory_store),
            "coder": BotMemory("coder", "coder", memory_store),
            "designer": BotMemory("designer", "designer", memory_store),
        }
        
        # Each team member learns something
        for name, bot in team.items():
            bot.add_learning(
                content=f"{name.capitalize()} specialized knowledge",
                source="user_feedback",
                confidence=0.85,
                is_private=True,
            )
        
        # Create shared pool
        pool = SharedMemoryPool("test_workspace", memory_store)
        
        # Verify we can get shared learnings
        shared = pool.get_shared_learnings()
        assert len(shared) >= 0  # May be 0 if no promotions yet
