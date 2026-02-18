"""Async message queue for decoupled channel-agent communication."""

import asyncio
from typing import Any, Awaitable, Callable, Optional

from loguru import logger

from nanofolks.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.
    
    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    
    Supports cross-channel broadcast via room-centric routing.
    """
    
    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._outbound_subscribers: dict[str, list[Callable[[OutboundMessage], Awaitable[None]]]] = {}
        self._running = False
        self._room_manager: Optional[Any] = None  # Set via set_room_manager()
    
    def set_room_manager(self, room_manager) -> None:
        """Set the room manager for cross-channel broadcast.
        
        Args:
            room_manager: RoomManager instance for looking up linked channels
        """
        self._room_manager = room_manager
        logger.info("MessageBus room manager configured for cross-channel broadcast")
    
    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)
    
    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()
    
    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)
    
    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()
    
    def subscribe_outbound(
        self, 
        channel: str, 
        callback: Callable[[OutboundMessage], Awaitable[None]]
    ) -> None:
        """Subscribe to outbound messages for a specific channel."""
        if channel not in self._outbound_subscribers:
            self._outbound_subscribers[channel] = []
        self._outbound_subscribers[channel].append(callback)
    
    async def dispatch_outbound(self) -> None:
        """
        Dispatch outbound messages to subscribed channels.
        
        If room_id is set on the message and room_manager is configured,
        also broadcasts to all linked channels in that room.
        
        Run this as a background task.
        """
        self._running = True
        while self._running:
            try:
                msg = await asyncio.wait_for(self.outbound.get(), timeout=1.0)
                
                # Send to the original channel
                subscribers = self._outbound_subscribers.get(msg.channel, [])
                for callback in subscribers:
                    try:
                        await callback(msg)
                    except Exception as e:
                        logger.error(f"Error dispatching to {msg.channel}: {e}")
                
                # Cross-channel broadcast: send to all linked channels in the room
                if msg.room_id and self._room_manager:
                    await self._broadcast_to_linked_channels(msg)
                    
            except asyncio.TimeoutError:
                continue
    
    async def _broadcast_to_linked_channels(self, original_msg: OutboundMessage) -> None:
        """Broadcast message to all channels linked to the same room.
        
        Args:
            original_msg: The original outbound message with room_id set
        """
        if not self._room_manager:
            return
        
        room_id = original_msg.room_id
        try:
            # Get all channels linked to this room
            linked_channels = self._room_manager.get_channel_mappings_for_room(room_id)
            
            if not linked_channels:
                return
            
            # Create a copy for each linked channel
            for linked in linked_channels:
                channel = linked.get("channel")
                chat_id = linked.get("chat_id")
                
                # Skip the original channel (already sent)
                if channel == original_msg.channel and str(chat_id) == str(original_msg.chat_id):
                    continue
                
                # Check if channel is active (has subscribers)
                if channel not in self._outbound_subscribers:
                    logger.debug(f"Skipping broadcast to inactive channel: {channel}")
                    continue
                
                # Create broadcast message
                broadcast_msg = OutboundMessage(
                    channel=channel,
                    chat_id=str(chat_id),
                    content=original_msg.content,
                    reply_to=original_msg.reply_to,
                    media=original_msg.media.copy(),
                    metadata={
                        **original_msg.metadata,
                        "broadcast_from": original_msg.channel,
                        "broadcast_room": room_id,
                    },
                    room_id=room_id,
                )
                
                # Send to linked channel
                subscribers = self._outbound_subscribers.get(channel, [])
                for callback in subscribers:
                    try:
                        await callback(broadcast_msg)
                        logger.debug(f"Broadcast message to {channel}:{chat_id} (room: {room_id})")
                    except Exception as e:
                        logger.error(f"Error broadcasting to {channel}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in cross-channel broadcast for room {room_id}: {e}")
    
    def stop(self) -> None:
        """Stop the dispatcher loop."""
        self._running = False
    
    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()
    
    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
