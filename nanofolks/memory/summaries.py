"""Hierarchical summaries for efficient context assembly.

This module implements Phase 4 of the memory proposal:
- Summary tree management (root → channel → entity_type → entity/topic)
- Staleness tracking (refresh when >10 new events)
- Batch summarization
- Pre-computed summaries for fast context assembly
"""

from datetime import datetime
from typing import Optional

from loguru import logger

from nanofolks.memory.models import SummaryNode
from nanofolks.memory.store import TurboMemoryStore
from nanofolks.utils.ids import room_to_session_id


class SummaryTreeManager:
    """
    Manages the hierarchical summary tree.

    Tree structure (room-centric):
    root/
    ├── room:general/
    │   ├── entity:John Smith (summary)
    │   ├── entity:Jane Doe (summary)
    │   └── topic:programming (summary)
    ├── room:project-website/
    │   └── ...
    └── user_preferences (always in context)
    """

    def __init__(
        self,
        store: TurboMemoryStore,
        staleness_threshold: int = 10,
        max_refresh_batch: int = 20,
        min_confidence: float = 0.3,
        max_age_days: int = 90,
        max_staleness: int = 200,
    ):
        """
        Initialize the summary tree manager.

        Args:
            store: TurboMemoryStore for database operations
            staleness_threshold: Events before refresh (default: 10)
            max_refresh_batch: Max nodes to refresh per cycle (default: 20)
        """
        self.store = store
        self.staleness_threshold = staleness_threshold
        self.max_refresh_batch = max_refresh_batch
        self.min_confidence = min_confidence
        self.max_age_days = max_age_days
        self.max_staleness = max_staleness

        # Ensure root node exists
        self._ensure_root_node()

        logger.info(f"SummaryTreeManager initialized (threshold: {staleness_threshold})")

    def _ensure_root_node(self):
        """Create root node if it doesn't exist."""
        root = self.store.get_summary_node("root")
        if not root:
            root = SummaryNode(
                id="root",
                node_type="root",
                key="root",
                summary="Root of conversation summary tree",
                confidence=0.7,
            )
            self.store.create_summary_node(root)
            logger.info("Created root summary node")

    def increment_staleness(self, room_id: str, entity_ids: list[str] = None):
        """
        Increment staleness counter for relevant nodes after new events.

        Args:
            room_id: Room where events occurred
            entity_ids: List of entity IDs mentioned in events
        """
        if not room_id:
            return

        # Get or create room node
        room_node = self._get_or_create_room_node(room_id)

        # Increment staleness
        room_node.events_since_update += 1
        self.store.update_summary_node(room_node)

        # Increment for specific entities
        if entity_ids:
            for entity_id in entity_ids:
                entity_node = self.store.get_summary_node(f"entity:{entity_id}")
                if entity_node:
                    entity_node.events_since_update += 1
                    self.store.update_summary_node(entity_node)

        logger.debug(f"Incremented staleness for room {room_id}")

    def get_stale_nodes(self, min_staleness: int = None) -> list[SummaryNode]:
        """
        Get all nodes that need refreshing.

        Args:
            min_staleness: Minimum staleness to consider (default: threshold)

        Returns:
            List of stale summary nodes
        """
        if min_staleness is None:
            min_staleness = self.staleness_threshold

        all_nodes = self.store.get_all_summary_nodes()
        stale_nodes = [n for n in all_nodes if n.events_since_update >= min_staleness]

        # Sort by staleness (highest first) and limit
        stale_nodes.sort(key=lambda n: n.events_since_update, reverse=True)

        return stale_nodes[:self.max_refresh_batch]

    def refresh_node(self, node_id: str) -> Optional[SummaryNode]:
        """
        Refresh a summary node by regenerating its content.

        Args:
            node_id: Node to refresh

        Returns:
            Updated node or None if not found
        """
        node = self.store.get_summary_node(node_id)
        if not node:
            return None

        try:
            # Generate new summary based on node type
            if node.node_type in {"room", "channel"}:
                from nanofolks.utils.ids import session_to_room_id

                if node.node_type == "channel":
                    room_id = node.key.replace("channel:", "")
                else:
                    room_id = session_to_room_id(node.key)
                new_summary, stats = self._generate_room_summary(room_id)
                confidence = self._score_room_summary(stats)
            elif node.node_type == "entity":
                entity_id = node.key.replace("entity:", "")
                new_summary, stats = self._generate_entity_summary(entity_id)
                confidence = self._score_entity_summary(stats)
            else:
                # Root or other types
                new_summary, stats = self._generate_root_summary()
                confidence = self._score_root_summary(stats)

            # Update node
            node.summary = new_summary
            node.confidence = confidence
            node.events_since_update = 0
            node.last_updated = datetime.now()

            self.store.update_summary_node(node)

            logger.info(f"Refreshed summary node: {node.key}")

            return node

        except Exception as e:
            logger.error(f"Failed to refresh node {node_id}: {e}")
            return None

    def refresh_all_stale(self) -> dict:
        """
        Refresh all stale nodes up to max_refresh_batch.

        Returns:
            Dict with refresh statistics
        """
        stale_nodes = self.get_stale_nodes()

        results = {
            "total_stale": len(stale_nodes),
            "refreshed": 0,
            "failed": 0,
            "nodes": [],
        }

        for node in stale_nodes:
            refreshed = self.refresh_node(node.id)
            if refreshed:
                results["refreshed"] += 1
                results["nodes"].append({
                    "id": node.id,
                    "key": node.key,
                    "type": node.node_type,
                })
            else:
                results["failed"] += 1

        logger.info(f"Summary refresh complete: {results['refreshed']} refreshed, {results['failed']} failed")

        return results

    def _get_or_create_room_node(self, room_id: str) -> SummaryNode:
        """Get or create a room summary node."""
        node_key = room_to_session_id(room_id)
        node = self.store.get_summary_node(node_key)

        if not node:
            node = SummaryNode(
                id=node_key,
                node_type="room",
                key=node_key,
                parent_id="root",
                summary=f"Summary for room {room_id}",
                confidence=0.5,
            )
            self.store.create_summary_node(node)
            logger.info(f"Created room summary node: {room_id}")

        return node

    def _generate_room_summary(self, room_id: str) -> tuple[str, dict]:
        """Generate summary for a room."""
        session_key = room_to_session_id(room_id)

        # Get recent events for this room
        events = self.store.get_events_for_session(session_key, limit=50)

        if not events:
            return f"No recent activity in {room_id}.", {"events": 0, "entities": 0}

        # Get entity counts
        entities = self.store.get_entities_for_session(session_key, limit=20)

        summary_parts = [
            f"Room: {room_id}",
            f"Recent events: {len(events)}",
            f"Active entities: {len(entities)}",
        ]

        # Add entity list
        if entities:
            entity_names = [e.name for e in entities[:5]]
            summary_parts.append(f"Key topics: {', '.join(entity_names)}")

        return "\n".join(summary_parts), {"events": len(events), "entities": len(entities)}

    def _generate_entity_summary(self, entity_id: str) -> tuple[str, dict]:
        """Generate summary for an entity."""
        entity = self.store.get_entity(entity_id)
        if not entity:
            return "Entity not found.", {"mentions": 0, "facts": 0}

        # Get facts about this entity
        facts = self.store.get_facts_for_entity(entity_id)

        summary_parts = [
            f"Entity: {entity.name}",
            f"Type: {entity.entity_type}",
            f"Mentions: {entity.event_count}",
        ]

        # Add facts
        if facts:
            fact_texts = [f"{f.predicate}: {f.object_text}" for f in facts[:3]]
            summary_parts.append(f"Known facts: {'; '.join(fact_texts)}")

        # Add aliases
        if entity.aliases:
            summary_parts.append(f"Also known as: {', '.join(entity.aliases[:3])}")

        return "\n".join(summary_parts), {"mentions": entity.event_count, "facts": len(facts)}

    def _generate_root_summary(self) -> tuple[str, dict]:
        """Generate root summary of all conversations."""
        stats = self.store.get_stats()

        summary = (
            f"Total events: {stats.get('events', 0)}\n"
            f"Total entities: {stats.get('entities', 0)}\n"
            f"Total facts: {stats.get('facts', 0)}\n"
            f"Summary nodes: {stats.get('summary_nodes', 0)}"
        )
        return summary, stats

    def _score_room_summary(self, stats: dict) -> float:
        events = int(stats.get("events", 0) or 0)
        entities = int(stats.get("entities", 0) or 0)
        if events == 0:
            return 0.2
        score = 0.4
        score += min(0.4, (events / 50) * 0.4)
        score += min(0.2, (entities / 10) * 0.2)
        return min(0.95, max(0.2, score))

    def _score_entity_summary(self, stats: dict) -> float:
        mentions = int(stats.get("mentions", 0) or 0)
        facts = int(stats.get("facts", 0) or 0)
        if mentions == 0:
            return 0.2
        score = 0.4
        score += min(0.4, (mentions / 20) * 0.4)
        score += min(0.2, (facts / 5) * 0.2)
        return min(0.95, max(0.2, score))

    def _score_root_summary(self, stats: dict) -> float:
        total_events = int(stats.get("events", 0) or 0)
        if total_events == 0:
            return 0.2
        score = 0.3 + min(0.6, (total_events / 200) * 0.6)
        return min(0.9, max(0.2, score))

    def cleanup_nodes(self) -> dict:
        """Prune stale/low-confidence summary nodes."""
        nodes = self.store.get_all_summary_nodes()
        parent_ids = {n.parent_id for n in nodes if n.parent_id}
        now = datetime.now()

        stats = {"evaluated": len(nodes), "removed": 0}
        for node in nodes:
            if node.id in {"root", "user_preferences"}:
                continue
            if node.id in parent_ids:
                continue
            confidence = node.confidence if node.confidence is not None else 0.5
            last_updated = node.last_updated or now
            age_days = (now - last_updated).days
            too_old = age_days >= self.max_age_days
            too_stale = node.events_since_update >= self.max_staleness

            if confidence < self.min_confidence and (too_old or too_stale):
                if self.store.delete_summary_node(node.id):
                    stats["removed"] += 1

        if stats["removed"]:
            logger.info(f"Summary cleanup removed {stats['removed']} nodes")
        return stats

    def get_summary_for_context(
        self,
        room_id: str,
        entity_ids: list[str] = None,
        max_tokens: int = 1000,
    ) -> str:
        """
        Get pre-computed summaries for context assembly.

        Args:
            room_id: Current room (room-centric)
            entity_ids: Entity IDs to include (optional)
            max_tokens: Maximum tokens to return

        Returns:
            Combined summary text
        """
        summaries = []

        # Get room summary (room-centric)
        room_node = self.store.get_summary_node(room_to_session_id(room_id))
        if room_node and room_node.summary and (room_node.confidence or 0.0) >= self.min_confidence:
            summaries.append(f"## Room: {room_id}\n{room_node.summary}")

        # Get entity summaries
        if entity_ids:
            for entity_id in entity_ids[:5]:  # Limit to top 5
                entity_node = self.store.get_summary_node(f"entity:{entity_id}")
                if entity_node and entity_node.summary and (entity_node.confidence or 0.0) >= self.min_confidence:
                    summaries.append(f"## {entity_node.key.replace('entity:', '')}\n{entity_node.summary}")

        # Get user preferences (always include)
        prefs_node = self.store.get_summary_node("user_preferences")
        if prefs_node and prefs_node.summary:
            summaries.append(f"## Preferences\n{prefs_node.summary}")

        # Combine and truncate
        combined = "\n\n".join(summaries)

        # Simple token estimation (4 chars ≈ 1 token)
        if len(combined) > max_tokens * 4:
            combined = combined[:max_tokens * 4] + "\n...[truncated]"

        return combined


def create_summary_manager(store: TurboMemoryStore, **kwargs) -> SummaryTreeManager:
    """Factory function to create a SummaryTreeManager."""
    return SummaryTreeManager(store, **kwargs)
