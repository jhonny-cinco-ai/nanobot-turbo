"""Helpers for normalizing room and session identifiers."""

from __future__ import annotations

ROOM_PREFIX = "room:"


def normalize_room_id(value: str | None) -> str | None:
    """Normalize a room identifier to its canonical form.

    Accepts values like:
    - "room:general"
    - "#general"
    - "general"

    Returns:
        Canonical room id (e.g., "general") or None if empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if text.startswith(ROOM_PREFIX):
        text = text[len(ROOM_PREFIX):]

    if text.startswith("#"):
        text = text[1:]

    text = text.strip()
    return text or None


def room_to_session_id(room_id: str | None) -> str:
    """Convert a room id to a session id (room:...)."""
    normalized = normalize_room_id(room_id)
    return f"{ROOM_PREFIX}{normalized}" if normalized else ""


def session_to_room_id(session_id: str | None) -> str | None:
    """Convert a session id to a room id."""
    return normalize_room_id(session_id)


def session_key_for_message(room_id: str | None, channel: str, chat_id: str) -> str:
    """Compute a stable session key for a message.

    Prefers a room id if available; falls back to channel + chat id.
    """
    normalized = normalize_room_id(room_id)
    if normalized:
        return room_to_session_id(normalized)
    return f"{ROOM_PREFIX}{channel}_{chat_id}"

