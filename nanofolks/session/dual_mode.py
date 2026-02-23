"""Room-centric session manager.

Simple room-based session storage using room:{id} keys.
No legacy support needed since project hasn't launched yet.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanofolks.session.manager import Session, SessionManager
from nanofolks.utils.helpers import safe_filename
from nanofolks.utils.ids import room_to_session_id, session_to_room_id

if TYPE_CHECKING:
    from nanofolks.config.schema import Config


class RoomSessionManager(SessionManager):
    """
    Room-centric session manager.

    All sessions use room:{id} keys stored in ~/.nanofolks/room_sessions/

    Session Key Format:
    - room:general, room:project-abc123, etc.

    Storage:
    - ~/.nanofolks/room_sessions/{room_id}.jsonl
    
    Supports CAS (Compare-And-Set) storage for conflict-free concurrent writes.
    Enable via config.storage.use_cas_storage or NANOFOLKS_USE_CAS_STORAGE env var.
    """

    def __init__(self, workspace: Path, config: "Config | None" = None):
        """
        Initialize room-centric session manager.

        Args:
            workspace: Workspace directory
            config: Optional config object for feature flags
        """
        super().__init__(workspace)

        self.room_sessions_dir = Path.home() / ".nanofolks" / "room_sessions"
        self.room_sessions_dir.mkdir(parents=True, exist_ok=True)
        
        self._config = config
        self._cas_storage = None
        
        use_cas = self._get_cas_enabled()
        if use_cas:
            try:
                from nanofolks.storage import SessionCASStorage
                self._cas_storage = SessionCASStorage(self.room_sessions_dir)
                logger.info("CAS storage enabled for RoomSessionManager")
            except Exception as e:
                logger.warning(f"Failed to initialize CAS storage: {e}")
    
    def _get_cas_enabled(self) -> bool:
        """Check if CAS storage is enabled via config or environment variable."""
        if self._config and hasattr(self._config, 'storage'):
            return self._config.storage.use_cas_storage
        
        import os
        return os.environ.get("NANOFOLKS_USE_CAS_STORAGE", "true").lower() == "true"

    def _get_room_session_path(self, room_key: str) -> Path:
        """Get file path for a room session.

        Args:
            room_key: Room key (e.g., "room:general")

        Returns:
            Path to session file
        """
        # Extract room_id from key (e.g., "room:general" -> "general")
        room_id = session_to_room_id(room_key) or room_key
        safe_id = safe_filename(room_id)
        return self.room_sessions_dir / f"{safe_id}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        Get existing session or create new one.

        Args:
            key: Session key (room format, e.g., "room:general")

        Returns:
            Session object
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Try to load from disk
        session = self._load_room(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load_room(self, room_key: str) -> Session | None:
        """Load a room session from disk.

        Args:
            room_key: Room key (e.g., "room:general")

        Returns:
            Session or None if not found
        """
        path = self._get_room_session_path(room_key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None

            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)

            return Session(
                key=room_key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to load room session {room_key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """Save session to disk.

        Args:
            session: Session to save
        """
        if self._cas_storage and self._get_cas_enabled():
            self._save_cas(session)
        else:
            self._save_legacy(session)
        
        self._cache[session.key] = session
    
    def _save_cas(self, session: Session) -> None:
        """Save session using CAS storage for conflict-free writes."""
        messages = []
        
        metadata_line = {
            "_type": "metadata",
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "metadata": session.metadata
        }
        messages.append(metadata_line)
        
        for msg in session.messages:
            messages.append(msg)
        
        result = self._cas_storage.save_session(session.key, messages)
        if not result.success:
            logger.warning(f"CAS write failed for {session.key}: {result.error}")
    
    def _save_legacy(self, session: Session) -> None:
        """Save session using legacy file write (not thread-safe)."""
        path = self._get_room_session_path(session.key)

        with open(path, "w") as f:
            metadata_line = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata
            }
            f.write(json.dumps(metadata_line) + "\n")

            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")

    def delete(self, key: str) -> bool:
        """Delete a session.

        Args:
            key: Session key

        Returns:
            True if deleted, False if not found
        """
        # Remove from cache
        self._cache.pop(key, None)

        # Delete file
        path = self._get_room_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all room sessions.

        Returns:
            List of session info dicts
        """
        sessions = []

        for path in self.room_sessions_dir.glob("*.jsonl"):
            try:
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            room_id = path.stem
                            key = room_to_session_id(room_id)
                            sessions.append({
                                "key": key,
                                "type": "room",
                                "created_at": data.get("created_at"),
                                "updated_at": data.get("updated_at"),
                                "path": str(path)
                            })
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def get_session_stats(self) -> dict[str, Any]:
        """Get statistics about sessions.

        Returns:
            Dictionary with session statistics
        """
        room_count = len(list(self.room_sessions_dir.glob("*.jsonl")))

        return {
            "room_sessions": room_count,
            "total_sessions": room_count,
        }


def create_session_manager(workspace: Path, config: Any = None) -> RoomSessionManager:
    """
    Factory function to create room-centric session manager.

    Args:
        workspace: Workspace directory
        config: Configuration object (optional, for feature flags like storage.use_cas_storage)

    Returns:
        RoomSessionManager instance
    """
    return RoomSessionManager(workspace, config)
