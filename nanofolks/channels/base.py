"""Base channel interface for chat platforms."""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from nanofolks.bots.room_manager import get_room_manager
from nanofolks.bus.events import MessageEnvelope
from nanofolks.bus.queue import MessageBus


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.

    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the nanofolks message bus.

    Supports room-centric architecture where channels join rooms
    for cross-platform conversation continuity.
    """

    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.

        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False

    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.

        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass

    @abstractmethod
    async def send(self, msg: MessageEnvelope) -> None:
        """
        Send a message through this channel.

        Args:
            msg: The message to send.
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this bot.

        Args:
            sender_id: The sender's identifier.

        Returns:
            True if allowed, False otherwise.
        """
        allow_list = getattr(self.config, "allow_from", [])

        # If no allow list, allow everyone
        if not allow_list:
            return True

        sender_str = str(sender_id)
        if sender_str in allow_list:
            return True
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in allow_list:
                    return True
        return False

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Handle an incoming message from the chat platform.

        Routing logic:
        - First contact: auto-register (channel, chat_id) → general room.
        - Subsequent messages: route to the registered room.
        - Meta-command "!room <room_id>": switch the active room without
          invoking the agent. Sends a lightweight confirmation reply.
        - "!rooms": list available rooms.

        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier.
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
        """
        if not self.is_allowed(sender_id):
            logger.warning(
                f"Access denied for sender {sender_id} on channel {self.name}. "
                f"Add them to allowFrom list in config to grant access."
            )
            return

        try:
            room_manager = get_room_manager()

            # ── Auto-registration on first contact ────────────────────────────
            room_id = room_manager.get_room_for_channel(self.name, chat_id)
            if not room_id:
                room_manager.join_channel_to_room(
                    self.name, chat_id, room_manager.DEFAULT_ROOM_ID
                )
                room_id = room_manager.DEFAULT_ROOM_ID
                logger.info(
                    f"[{self.name}] First contact from {chat_id} — "
                    f"auto-registered to room:{room_id}"
                )

            # ── Room meta-commands (intercepted before agent) ─────────────────
            stripped = content.strip()

            if stripped.lower() == "!rooms":
                await self._reply_rooms(room_manager, chat_id, room_id)
                return

            if stripped.lower().startswith("!room"):
                parts = stripped.split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else ""
                if target:
                    await self._switch_room(
                        room_manager, chat_id, target, sender_id, room_id
                    )
                else:
                    await self._reply_rooms(room_manager, chat_id, room_id)
                return

            # ── Normal message → forward to agent ────────────────────────────
            msg = MessageEnvelope(
                channel=self.name,
                sender_id=str(sender_id),
                chat_id=str(chat_id),
                content=content,
                direction="inbound",
                media=media or [],
                metadata=metadata or {},
            )
            msg.set_room(room_id)
            logger.debug(f"Routed {self.name}:{chat_id} → room:{room_id}")
            await self.bus.publish_inbound(msg)

        except Exception as e:
            logger.error(f"[{self.name}:{chat_id}] Message handling error: {e}")

    async def _switch_room(
        self,
        room_manager,
        chat_id: str,
        target_room_id: str,
        sender_id: str,
        current_room_id: str,
    ) -> None:
        """Switch the active room for this channel/chat endpoint.

        Updates the persisted mapping so all future messages from this chat
        are routed to the new room.

        Args:
            room_manager: RoomManager instance.
            chat_id: Platform chat identifier.
            target_room_id: Room ID to switch to.
            sender_id: Sender requesting the switch (for logging).
            current_room_id: Current room ID (for context on failure).
        """
        room = room_manager.get_room(target_room_id)
        if not room:
            logger.warning(
                f"[{self.name}:{chat_id}] Room '{target_room_id}' not found — "
                f"switch ignored"
            )
            reply = MessageEnvelope(
                channel=self.name,
                chat_id=chat_id,
                content=(
                    f"❌ Room '{target_room_id}' not found. "
                    f"You are still in '{current_room_id}'."
                ),
                direction="outbound",
            )
            await self.send(reply)
            return

        room_manager.join_channel_to_room(self.name, chat_id, target_room_id)
        logger.info(
            f"[{self.name}:{chat_id}] {sender_id} switched "
            f"{current_room_id} → {target_room_id}"
        )
        bots = ", ".join(f"@{b}" for b in room.participants) or "none"
        reply = MessageEnvelope(
            channel=self.name,
            chat_id=chat_id,
            content=(
                f"✅ Switched to room *{target_room_id}*\n"
                f"Participants: {bots}\n"
                f"Send *!rooms* to list all rooms."
            ),
            direction="outbound",
        )
        await self.send(reply)

    async def _reply_rooms(
        self,
        room_manager,
        chat_id: str,
        current_room_id: str,
    ) -> None:
        """Send a plain-text list of available rooms to the channel.

        Args:
            room_manager: RoomManager instance.
            chat_id: Platform chat identifier.
            current_room_id: Active room (highlighted in the list).
        """
        rooms = room_manager.list_rooms()
        lines = ["📁 *Available rooms:*"]
        for r in rooms:
            marker = "→" if r["id"] == current_room_id else "  "
            bots = r["participant_count"]
            lines.append(f"{marker} *{r['id']}* ({r['type']}, {bots} bots)")
        lines.append("\nSwitch with: *!room <room_id>*")
        reply = MessageEnvelope(
            channel=self.name,
            chat_id=chat_id,
            content="\n".join(lines),
            direction="outbound",
        )
        await self.send(reply)

    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
