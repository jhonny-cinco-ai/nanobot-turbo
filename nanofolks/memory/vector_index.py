"""HNSW-based vector index for semantic search.

This module provides fast approximate nearest neighbor (ANN) search
using hnswlib, replacing the brute-force cosine similarity approach.
"""

import os
from pathlib import Path
from typing import Optional

import hnswlib
import numpy as np
from loguru import logger


class VectorIndex:
    """
    HNSW-based vector index for fast semantic search.
    
    Uses hierarchical navigable small world (HNSW) graphs for
    O(log n) query time instead of O(n) brute force.
    """

    def __init__(
        self,
        workspace: Path,
        dimension: int = 384,
        ef_construction: int = 200,
        M: int = 16,
        max_elements: int = 100000,
        name: str = "events",
    ):
        """
        Initialize the vector index.
        
        Args:
            workspace: Path to workspace directory
            dimension: Embedding dimension (384 for bge-small)
            ef_construction: Construction-time parameter (higher = better index, slower build)
            M: Number of connections per layer (higher = better recall, more memory)
            name: Name for this index (used in filename)
        """
        self.workspace = workspace
        self.dimension = dimension
        self.ef_construction = ef_construction
        self.M = M
        self.max_elements = max_elements
        self.name = name
        
        self.index_path = workspace / "memory" / f"{name}_index.bin"
        self.id_mapping_path = workspace / "memory" / f"{name}_ids.json"
        
        self._index: Optional[hnswlib.Index] = None
        self._id_map: dict[str, int] = {}  # event_id -> index position
        self._reverse_map: dict[int, str] = {}  # index position -> event_id
        
    def _ensure_index(self):
        """Ensure the HNSW index is initialized."""
        if self._index is None:
            self._index = hnswlib.Index(
                space='cosine',
                dim=self.dimension
            )
            self._index.set_ef(256)  # Query-time parameter - higher for better recall
            self._index.set_num_threads(4)
            
    def initialize(self):
        """Initialize or load the index."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._ensure_index()
        
        if self.index_path.exists():
            try:
                self._index.load_index(str(self.index_path))
                self._load_id_mapping()
                logger.info(f"Loaded vector index from {self.index_path}")
            except Exception as e:
                logger.warning(f"Failed to load index: {e}, creating new one")
                self._create_new_index()
        else:
            self._create_new_index()
            
    def _create_new_index(self):
        """Create a new index."""
        self._ensure_index()
        self._index.init_index(
            max_elements=self.max_elements,
            ef_construction=self.ef_construction,
            M=self.M
        )
        logger.info(f"Created new vector index (dim={self.dimension})")

    def reset(self):
        """Reset the index on disk and in memory."""
        self._index = None
        self._id_map = {}
        self._reverse_map = {}
        if self.index_path.exists():
            try:
                self.index_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove index file {self.index_path}: {e}")
        if self.id_mapping_path.exists():
            try:
                self.id_mapping_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove id map {self.id_mapping_path}: {e}")

    def rebuild(self, items: list[tuple[str, list[float]]]) -> int:
        """Rebuild the index from a full vector list."""
        self.reset()
        self._create_new_index()
        if not items:
            return 0
        self.add_vectors_batch(items)
        self.save()
        return len(items)
    
    def _load_id_mapping(self):
        """Load ID mapping from disk."""
        import json
        if self.id_mapping_path.exists():
            try:
                data = json.loads(self.id_mapping_path.read_text())
                self._id_map = data.get('id_map', {})
                self._reverse_map = {int(k): v for k, v in data.get('reverse_map', {}).items()}
            except Exception as e:
                logger.warning(f"Failed to load ID mapping: {e}")
                self._id_map = {}
                self._reverse_map = {}
                
    def _save_id_mapping(self):
        """Save ID mapping to disk."""
        import json
        self.id_mapping_path.parent.mkdir(parents=True, exist_ok=True)
        self.id_mapping_path.write_text(json.dumps({
            'id_map': self._id_map,
            'reverse_map': {str(k): v for k, v in self._reverse_map.items()}
        }))
        
    def add_vector(self, event_id: str, embedding: list[float]):
        """
        Add a vector to the index.
        
        Args:
            event_id: Unique identifier for the vector
            embedding: Embedding vector
        """
        self._ensure_index()

        max_elements = self._index.get_max_elements()
        current_count = self._index.get_current_count()
        if current_count + 1 > max_elements:
            new_max = max(current_count + 1, max_elements * 2)
            self._index.resize_index(new_max)
        
        if event_id in self._id_map:
            logger.debug(f"Vector {event_id} already in index, skipping")
            return
            
        # Convert to numpy array
        vec = np.array(embedding, dtype=np.float32)
        
        # Normalize for cosine similarity
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
            
        # Add to index
        idx = len(self._id_map)
        self._index.add_items([vec], [idx])
        
        # Update mappings
        self._id_map[event_id] = idx
        self._reverse_map[idx] = event_id
        
    def add_vectors_batch(self, items: list[tuple[str, list[float]]]):
        """
        Add multiple vectors in batch.
        
        Args:
            items: List of (event_id, embedding) tuples
        """
        if not items:
            return
            
        self._ensure_index()
        
        # Filter out duplicates
        new_items = [(eid, emb) for eid, emb in items if eid not in self._id_map]
        if not new_items:
            return

        max_elements = self._index.get_max_elements()
        current_count = self._index.get_current_count()
        needed = current_count + len(new_items)
        if needed > max_elements:
            new_max = max(needed, max_elements * 2)
            self._index.resize_index(new_max)
            
        # Convert to numpy array
        vectors = []
        ids = []
        start_idx = len(self._id_map)
        
        for i, (event_id, embedding) in enumerate(new_items):
            vec = np.array(embedding, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec)
            ids.append(start_idx + i)
            self._id_map[event_id] = start_idx + i
            self._reverse_map[start_idx + i] = event_id
            
        self._index.add_items(vectors, ids)
        logger.debug(f"Added {len(new_items)} vectors to index")
        
    def search(
        self,
        query_embedding: list[float],
        k: int = 10,
        filter_event_ids: list[str] = None,
    ) -> list[tuple[str, float]]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector
            k: Number of results to return
            filter_event_ids: Optional list of IDs to filter results to
            
        Returns:
            List of (event_id, similarity_score) tuples, sorted by similarity
        """
        if self._index is None or self._index.get_current_count() == 0:
            return []
            
        # Normalize query
        vec = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
            
        # Search
        labels, distances = self._index.knn_query([vec], k=k + (len(filter_event_ids) if filter_event_ids else 0))
        
        results = []
        for idx, distance in zip(labels[0], distances[0]):
            event_id = self._reverse_map.get(int(idx))
            if event_id is None:
                continue
                
            # Apply filter if provided
            if filter_event_ids and event_id not in filter_event_ids:
                continue
                
            # Convert distance to similarity (cosine distance -> similarity)
            similarity = 1.0 - distance
            results.append((event_id, similarity))
            
            if len(results) >= k:
                break
                
        return results
        
    def get_vector(self, event_id: str) -> Optional[list[float]]:
        """
        Get a vector by event ID.
        
        Args:
            event_id: Event ID
            
        Returns:
            Embedding vector, or None if not found
        """
        idx = self._id_map.get(event_id)
        if idx is None:
            return None
            
        try:
            vectors = self._index.get_items([idx])
            return vectors[0].tolist()
        except Exception:
            return None
            
    def delete_vector(self, event_id: str):
        """
        Delete a vector from the index.
        
        Note: HNSW doesn't support efficient deletion, so we mark it
        as deleted and skip it in searches. For full deletion, rebuild.
        
        Args:
            event_id: Event ID to delete
        """
        # HNSW deletion is expensive - just remove from mapping
        idx = self._id_map.pop(event_id, None)
        if idx is not None:
            self._reverse_map.pop(idx, None)
            logger.debug(f"Marked vector {event_id} for deletion")
            
    def save(self):
        """Save the index to disk."""
        if self._index is not None:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self._index.save_index(str(self.index_path))
            self._save_id_mapping()
            logger.info(f"Saved vector index to {self.index_path}")
            
    def get_stats(self) -> dict:
        """Get index statistics."""
        if self._index is None:
            return {"count": 0, "dimension": self.dimension}
        return {
            "count": self._index.get_current_count(),
            "dimension": self.dimension,
            "max_elements": self._index.get_max_elements(),
            "ef_construction": self.ef_construction,
        }
        
    def close(self):
        """Close and save the index."""
        self.save()
        
    def __enter__(self):
        self.initialize()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
