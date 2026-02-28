"""Session management for conversation history."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanofolks.utils.helpers import ensure_dir, safe_filename, strip_base64_images


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.
    """

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        if role == "user":
            content = strip_base64_images(content)
        msg = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), **kwargs}
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(
        self, max_messages: int = 50, preserve_tool_chains: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.

        CRITICAL: Never separate tool_use → tool_result pairs.
        Anthropic API requires every tool_result to have matching tool_use
        in the immediately preceding assistant message.

        Args:
            max_messages: Maximum messages to return.
            preserve_tool_chains: If True, ensures tool pairs are never separated.

        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = (
            self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        )

        # If preserving tool chains, ensure we don't break pairs
        if preserve_tool_chains and recent:
            recent = self._preserve_tool_chains(recent)

        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def _preserve_tool_chains(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Ensure tool_use → tool_result pairs are never separated.

        Critical for API compatibility. If a tool_use is included, its matching
        tool_result must also be included (and vice versa).

        Args:
            messages: List of messages to check.

        Returns:
            Messages with tool pairs preserved.
        """
        if not messages:
            return messages

        # Find tool_use IDs in assistant messages
        tool_use_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                # Check for tool_use blocks
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_use_ids.add(block.get("id"))

        # Check first message - if it's a tool_result, find its tool_use
        if messages[0].get("role") == "user":
            content = messages[0].get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_use_id = block.get("tool_use_id")
                        # Check if the tool_use is NOT in our messages
                        if tool_use_id and tool_use_id not in tool_use_ids:
                            # We need to find and include the tool_use message
                            # Search backwards from the start of messages
                            missing_tool_use = self._find_tool_use_message(tool_use_id)
                            if missing_tool_use:
                                logger.debug(
                                    f"Adding missing tool_use {tool_use_id} to preserve chain"
                                )
                                messages.insert(0, missing_tool_use)

        return messages

    def _find_tool_use_message(self, tool_use_id: str) -> dict[str, Any] | None:
        """
        Find the assistant message containing a specific tool_use.

        Args:
            tool_use_id: The ID of the tool_use to find.

        Returns:
            The message containing the tool_use, or None if not found.
        """
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            if block.get("id") == tool_use_id:
                                return msg
        return None

    def get_safe_compaction_point(self, target_messages: int = 30) -> int:
        """
        Find a safe index to compact at, ensuring no tool chains are broken.

        This finds the most recent assistant message before target_messages
        that is not followed by an incomplete tool chain.

        Args:
            target_messages: Target number of recent messages to keep.

        Returns:
            Safe index to truncate at (messages before this are compacted).
        """
        if len(self.messages) <= target_messages:
            return 0

        # Look for a safe boundary before target_messages
        check_index = len(self.messages) - target_messages

        # Find the previous assistant message
        while check_index > 0:
            msg = self.messages[check_index]

            # Assistant messages are safe boundaries
            if msg.get("role") == "assistant":
                # Check if this assistant has tool_use blocks
                content = msg.get("content", [])
                has_tool_use = False
                tool_use_ids = []

                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            has_tool_use = True
                            tool_use_ids.append(block.get("id"))

                # If no tool_use, this is definitely a safe boundary
                if not has_tool_use:
                    return check_index

                # If it has tool_use, check that all results are in the keep zone
                all_results_present = True
                for tool_id in tool_use_ids:
                    # Check if tool_result is in messages after check_index
                    result_found = False
                    for i in range(check_index + 1, len(self.messages)):
                        later_msg = self.messages[i]
                        if later_msg.get("role") == "user":
                            later_content = later_msg.get("content", [])
                            if isinstance(later_content, list):
                                for block in later_content:
                                    if (
                                        isinstance(block, dict)
                                        and block.get("type") == "tool_result"
                                    ):
                                        if block.get("tool_use_id") == tool_id:
                                            result_found = True
                                            break
                        if result_found:
                            break

                    if not result_found:
                        all_results_present = False
                        break

                if all_results_present:
                    return check_index

            check_index -= 1

        # Fallback: return 0 (compact everything)
        return 0

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(Path.home() / ".nanofolks" / "sessions")
        self._cache: dict[str, Session] = {}

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        # Try to load from disk
        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)

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
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)

        with open(path, "w") as f:
            # Write metadata first
            metadata_line = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
            }
            f.write(json.dumps(metadata_line) + "\n")

            # Write messages
            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")

        self._cache[session.key] = session

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)

        # Remove file
        path = self._get_session_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            sessions.append(
                                {
                                    "key": path.stem.replace("_", ":"),
                                    "created_at": data.get("created_at"),
                                    "updated_at": data.get("updated_at"),
                                    "path": str(path),
                                }
                            )
            except Exception:
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
