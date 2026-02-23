from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Callable
from datetime import datetime
from loguru import logger

if TYPE_CHECKING:
    from nanofolks.bus.events import MessageEnvelope
    from nanofolks.storage.cas_storage import CASFileStorage


@dataclass
class QueuedMessage:
    """Message in the room queue with sequence number."""
    seq: int
    message: "MessageEnvelope"
    received_at: datetime = field(default_factory=datetime.now)
    claimed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None


class RoomMessageBroker:
    """
    Per-room message broker with FIFO guarantees.
    
    Each room has its own queue and can process independently
    of other rooms, enabling parallelism across rooms while
    maintaining strict ordering within a room.
    """
    
    def __init__(
        self, 
        room_id: str,
        storage: Optional["CASFileStorage"] = None,
        agent_loop_factory: Optional[Callable[[], object]] = None,
        max_queue_size: int = 1000
    ):
        self.room_id = room_id
        self.storage = storage
        self.agent_loop_factory = agent_loop_factory
        self.agent_loop = None
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue(maxsize=max_queue_size)
        self._seq_counter = 0
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        
        self.messages_received = 0
        self.messages_processed = 0
        self.messages_failed = 0
    
    def set_agent_loop(self, agent_loop: object) -> None:
        """Set the agent loop for this broker."""
        self.agent_loop = agent_loop
    
    async def enqueue(self, message: "MessageEnvelope") -> bool:
        """
        Add message to room queue.
        
        Args:
            message: Inbound message to queue
            
        Returns:
            True if queued successfully, False if queue full
        """
        try:
            self._seq_counter += 1
            queued = QueuedMessage(
                seq=self._seq_counter,
                message=message
            )
            
            self._queue.put_nowait(queued)
            self.messages_received += 1
            
            logger.debug(f"Enqueued message {queued.seq} in room {self.room_id}")
            return True
            
        except asyncio.QueueFull:
            logger.error(f"Room {self.room_id} queue full, dropping message")
            return False
    
    async def start(self) -> None:
        """Start the broker processing loop."""
        if self.agent_loop_factory and not self.agent_loop:
            self.agent_loop = self.agent_loop_factory()
        
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info(f"Room broker started for {self.room_id}")
    
    async def stop(self) -> None:
        """Stop the broker gracefully."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Room broker stopped for {self.room_id}")
    
    async def _process_loop(self) -> None:
        """
        Main processing loop - FIFO order guaranteed.
        
        Processes messages one at a time to maintain ordering.
        Different rooms process in parallel.
        """
        while self._running:
            try:
                queued = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                
                queued.claimed_at = datetime.now()
                queued.claimed_by = getattr(self.agent_loop, 'bot_name', 'unknown') if self.agent_loop else 'unknown'
                
                try:
                    await self._process_message(queued)
                    self.messages_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process message {queued.seq}: {e}")
                    self.messages_failed += 1
                
                queued.processed_at = datetime.now()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    async def _process_message(self, queued: QueuedMessage) -> None:
        """Process a single message through the agent loop."""
        logger.info(
            f"Processing message {queued.seq} in room {self.room_id} "
            f"(queue depth: {self._queue.qsize()})"
        )
        
        if self.agent_loop and hasattr(self.agent_loop, 'process_inbound'):
            await self.agent_loop.process_inbound(queued.message)
        else:
            logger.warning(f"No agent loop configured for room {self.room_id}")
    
    @property
    def queue_depth(self) -> int:
        """Current number of messages waiting."""
        return self._queue.qsize()
    
    @property
    def is_running(self) -> bool:
        """Whether broker is active."""
        return self._running and (self._process_task is not None and not self._process_task.done())


class RoomBrokerManager:
    """
    Manages per-room message brokers.
    
    Routes messages to the correct room broker based on room_id.
    Creates brokers on-demand.
    """
    
    def __init__(
        self, 
        storage: Optional["CASFileStorage"] = None,
        agent_loop_factory: Optional[Callable[[], object]] = None
    ):
        self.storage = storage
        self.agent_loop_factory = agent_loop_factory
        self._brokers: dict[str, RoomMessageBroker] = {}
        self._lock = asyncio.Lock()
    
    async def route_message(self, message: "MessageEnvelope") -> bool:
        """
        Route message to appropriate room broker.
        
        Args:
            message: Inbound message (must have room_id set)
            
        Returns:
            True if routed successfully
        """
        room_id = message.room_id
        if not room_id:
            logger.error("Cannot route message without room_id")
            return False
        
        async with self._lock:
            if room_id not in self._brokers:
                broker = RoomMessageBroker(
                    room_id=room_id,
                    storage=self.storage,
                    agent_loop_factory=self.agent_loop_factory
                )
                await broker.start()
                self._brokers[room_id] = broker
                logger.info(f"Created broker for room {room_id}")
            
            broker = self._brokers[room_id]
        
        return await broker.enqueue(message)
    
    async def stop_all(self) -> None:
        """Stop all room brokers."""
        async with self._lock:
            for room_id, broker in self._brokers.items():
                await broker.stop()
            self._brokers.clear()
    
    def get_stats(self) -> dict:
        """Get stats for all brokers."""
        return {
            room_id: {
                "queue_depth": broker.queue_depth,
                "running": broker.is_running,
                "received": broker.messages_received,
                "processed": broker.messages_processed,
                "failed": broker.messages_failed
            }
            for room_id, broker in self._brokers.items()
        }
    
    def get_broker(self, room_id: str) -> Optional[RoomMessageBroker]:
        """Get a broker for a specific room."""
        return self._brokers.get(room_id)
