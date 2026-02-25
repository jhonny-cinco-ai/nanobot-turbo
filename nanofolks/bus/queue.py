"""Async message queue for decoupled channel-agent communication."""

import asyncio
from typing import Any, Optional

from nanofolks.bus.events import MessageEnvelope


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.

    When a RoomBrokerManager is attached via set_broker(), inbound messages
    are routed through the broker for per-room FIFO ordering instead of
    the flat asyncio.Queue fallback.
    """

    def __init__(self):
        self.inbound: asyncio.Queue[MessageEnvelope] = asyncio.Queue()
        self.outbound: asyncio.Queue[MessageEnvelope] = asyncio.Queue()
        self._room_manager: Optional[Any] = None  # Set via set_room_manager()
        self._broker: Optional[Any] = None        # Set via set_broker()

    def set_room_manager(self, room_manager) -> None:
        """Set the room manager for cross-channel broadcast.

        Args:
            room_manager: RoomManager instance for looking up linked channels
        """
        self._room_manager = room_manager

    def set_broker(self, broker) -> None:
        """Attach a RoomBrokerManager for per-room FIFO inbound routing.

        When set, publish_inbound() routes through the broker instead of
        the flat asyncio.Queue. The broker creates per-room queues on-demand
        and guarantees FIFO ordering within each room.

        Args:
            broker: RoomBrokerManager instance
        """
        self._broker = broker

    async def publish_inbound(self, msg: MessageEnvelope) -> bool:
        """Publish a message from a channel to the agent.

        Routes through the per-room broker if one is attached, otherwise
        falls back to the flat inbound queue consumed by AgentLoop.run().

        Returns:
            True if queued, False if dropped (e.g., broker full).
        """
        msg.direction = "inbound"
        msg.apply_defaults("user")
        if self._broker is not None:
            return await self._broker.route_message(msg)
        else:
            await self.inbound.put(msg)
            return True

    async def consume_inbound(self) -> MessageEnvelope:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: MessageEnvelope) -> None:
        """Publish a response from the agent to channels."""
        msg.direction = "outbound"
        if msg.room_id is None and self._room_manager is not None:
            try:
                room_id = self._room_manager.get_room_for_channel(msg.channel, msg.chat_id)
                if room_id:
                    msg.set_room(room_id)
            except Exception:
                pass
        msg.apply_defaults("bot")
        await self.outbound.put(msg)

    async def consume_outbound(self) -> MessageEnvelope:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
