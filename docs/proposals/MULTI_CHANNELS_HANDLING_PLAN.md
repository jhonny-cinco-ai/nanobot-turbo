# Multi-Channel Handling Improvements Plan

**Status:** Draft  
**Date:** 2026-02-19  
**Priority:** High  
**Risk:** Medium  
**Est. Duration:** 2-3 weeks  

---

## Executive Summary

This document outlines critical improvements to nanofolks' multi-channel, multi-bot architecture to address race conditions, file corruption risks, and message ordering issues identified in the current implementation.

### Current Problems

1. **File Write Race Conditions**: Multiple channels writing to the same room/session file simultaneously can corrupt data
2. **No Global Message Ordering**: Messages from different channels lack causal ordering guarantees
3. **Message Loss on Crashes**: In-flight messages can be lost if agent crashes mid-processing
4. **No Deduplication**: Same message may be processed multiple times on channel retries

### Solution Approach

Adopt proven distributed systems patterns from object-storage-based queues (inspired by [Turbopuffer's queue architecture](https://turbopuffer.com/blog/object-storage-queue)):

- **CAS (Compare-And-Set) writes** for conflict-free file updates
- **Per-room message brokers** for parallel processing with FIFO guarantees
- **Group commit** to batch writes and reduce I/O contention
- **Heartbeat-based task tracking** for 6-bot coordination

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CURRENT STATE (Problematic)                      │
│                                                                          │
│  ┌──────────┐      ┌──────────────┐      ┌─────────────────────────┐    │
│  │Telegram  │      │              │      │   Session Files         │    │
│  └────┬─────┘      │   Global     │      │   ┌─────────────────┐   │    │
│       │            │   Queue      │      │   │ room:general    │   │    │
│  ┌────┴─────┐      │   (asyncio)  │      │   │ ┌──┬──┬──┬──┐   │   │    │
│  │WhatsApp  │─────▶│              │─────▶│   │ │m1│m2│m3│m4│   │   │    │
│  └────┬─────┘      │   Agent Loop │      │   │ └──┴──┴──┴──┘   │   │    │
│       │            │   (1 at a    │      │   └─────────────────┘   │    │
│  ┌────┴─────┐      │    time)     │      │   ┌─────────────────┐   │    │
│  │Discord   │      │              │      │   │ telegram:123    │   │    │
│  └──────────┘      └──────────────┘      │   │ (separate!)     │   │    │
│                                          │   └─────────────────┘   │    │
│  ⚠️ Race condition: Telegram + WhatsApp   │                         │    │
│     both write to room:general.jsonl     └─────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    TARGET STATE (Improved)                               │
│                                                                          │
│  ┌──────────┐     ┌─────────────────────────────────────────────────┐   │
│  │Telegram  │     │         Per-Room Message Brokers                │   │
│  └────┬─────┘     │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │   │
│       │           │  │ room:general│  │room:project1│  │room:dm   │ │   │
│  ┌────┴─────┐     │  │  Broker     │  │   Broker    │  │ Broker   │ │   │
│  │WhatsApp  │────▶│  │ ┌─────────┐ │  │ ┌─────────┐ │  │┌────────┐│ │   │
│  └────┬─────┘     │  │ │ msg_q   │ │  │ │ msg_q   │ │  ││ msg_q  ││ │   │
│       │           │  │ │┌─┬─┬─┐  │ │  │ │┌─┬─┬─┐  │ │  ││┌─┬─┬─┐ ││ │   │
│  ┌────┴─────┐     │  │ ││m│m│m│  │ │  │ ││m│m│m│  │ │  │││m│m│m│ ││ │   │
│  │Discord   │     │  │ │└─┴─┴─┘  │ │  │ │└─┴─┴─┘  │ │  ││└─┴─┴─┘ ││ │   │
│  └──────────┘     │  │ │ seq=42  │ │  │ │ seq=17  │ │  ││ seq=5  ││ │   │
│                   │  │ └─────────┘ │  │ └─────────┘ │  │└────────┘│   │
│  Channels route   │  └──────┬──────┘  └──────┬──────┘  └────┬─────┘   │
│  by room_id       │         │                │              │         │
│                   └─────────┼────────────────┼──────────────┘         │
│                             │                │                        │
│                             ▼                ▼                        │
│                        ┌──────────┐    ┌──────────┐                   │
│                        │ Agent A  │    │ Agent B  │  (parallel rooms) │
│                        │(Bots 1-3)│    │(Bots 4-6)│                   │
│                        └────┬─────┘    └────┬─────┘                   │
│                             │               │                         │
│                        CAS writes     CAS writes                      │
│                             ▼               ▼                         │
│                        ┌─────────────────────────┐                    │
│                        │   Storage Layer         │                    │
│                        │   ┌─────────────────┐   │                    │
│                        │   │ SQLite (WAL)    │   │                    │
│                        │   │ + CAS file ops  │   │                    │
│                        │   └─────────────────┘   │                    │
│                        └─────────────────────────┘                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: CAS-Based File Storage (Week 1)

### 1.1 Problem: Concurrent File Writes

**Current Code (nanofolks/session/dual_mode.py:131):**
```python
# NO LOCKING - Race condition!
with open(path, "w") as f:
    f.write(json.dumps(metadata_line) + "\n")
    for msg in session.messages:
        f.write(json.dumps(msg) + "\n")
```

If two channels write to `room:general.jsonl` simultaneously:
- Channel A reads file (version 1)
- Channel B reads file (version 1)
- Channel A writes (version 2)
- Channel B writes (version 2) ← **OVERWRITES A's changes!**

### 1.2 Solution: ETag-Based CAS

**New Implementation:**

```python
# nanofolks/storage/cas_storage.py
import hashlib
import json
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
from loguru import logger
import fcntl  # Unix file locking


@dataclass
class CASResult:
    """Result of a CAS operation."""
    success: bool
    current_version: str
    new_version: Optional[str] = None
    error: Optional[str] = None


class CASFileStorage:
    """
    Compare-And-Set file storage for conflict-free concurrent writes.
    
    Uses ETags (content hashes) for versioning:
    - Read returns (data, etag)
    - Write only succeeds if etag matches current
    - Automatic retry on conflict
    """
    
    def __init__(self, base_path: Path, max_retries: int = 10):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        
    def _compute_etag(self, content: str) -> str:
        """Compute ETag (hash) for content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _get_path(self, key: str) -> Path:
        """Get file path for a key."""
        safe_key = key.replace(":", "_").replace("/", "_")
        return self.base_path / f"{safe_key}.jsonl"
    
    def _get_etag_path(self, key: str) -> Path:
        """Get ETag file path."""
        return self.base_path / f"{key.replace(':', '_')}.etag"
    
    def read(self, key: str) -> tuple[Optional[list], Optional[str]]:
        """
        Read data and its ETag.
        
        Returns:
            (data, etag) or (None, None) if not exists
        """
        path = self._get_path(key)
        etag_path = self._get_etag_path(key)
        
        if not path.exists():
            return None, None
            
        try:
            with open(path, 'r') as f:
                # Use advisory locking for reads too
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                content = f.read()
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Compute current ETag
            current_etag = self._compute_etag(content)
            
            # Parse JSONL
            data = []
            for line in content.strip().split('\n'):
                if line:
                    data.append(json.loads(line))
            
            return data, current_etag
            
        except Exception as e:
            logger.error(f"Error reading {key}: {e}")
            return None, None
    
    def write_cas(
        self, 
        key: str, 
        data: list, 
        expected_etag: Optional[str],
        retry_fn: Optional[Callable] = None
    ) -> CASResult:
        """
        Write data only if current ETag matches expected.
        
        Args:
            key: Storage key
            data: Data to write (list of dicts, serialized as JSONL)
            expected_etag: Expected current ETag (None for new files)
            retry_fn: Optional function to call on conflict for merge
            
        Returns:
            CASResult with success status
        """
        path = self._get_path(key)
        
        for attempt in range(self.max_retries):
            try:
                # Read current state
                _, current_etag = self.read(key)
                
                # Check if ETag matches (or both None for new file)
                if current_etag != expected_etag:
                    if retry_fn:
                        # Call merge function to resolve conflict
                        current_data, _ = self.read(key)
                        data = retry_fn(current_data, data)
                        # Recompute expected_etag after merge
                        _, expected_etag = self.read(key)
                        continue  # Retry with merged data
                    else:
                        return CASResult(
                            success=False,
                            current_version=current_etag or "new",
                            error=f"ETag mismatch: expected {expected_etag}, got {current_etag}"
                        )
                
                # Serialize data
                lines = [json.dumps(item, default=str) for item in data]
                content = '\n'.join(lines) + '\n'
                new_etag = self._compute_etag(content)
                
                # Write atomically using temp file + rename
                temp_path = path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(content)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
                # Atomic rename
                temp_path.rename(path)
                
                logger.debug(f"CAS write succeeded for {key} (attempt {attempt + 1})")
                return CASResult(
                    success=True,
                    current_version=new_etag,
                    new_version=new_etag
                )
                
            except Exception as e:
                logger.warning(f"CAS write attempt {attempt + 1} failed for {key}: {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(0.01 * (2 ** attempt))  # Exponential backoff
                else:
                    return CASResult(
                        success=False,
                        current_version=current_etag or "unknown",
                        error=str(e)
                    )
        
        return CASResult(
            success=False,
            current_version="unknown",
            error="Max retries exceeded"
        )
    
    def write_with_retry(
        self, 
        key: str, 
        data: list,
        merge_fn: Optional[Callable[[list, list], list]] = None
    ) -> CASResult:
        """
        Write with automatic retry on conflict using merge function.
        
        Args:
            key: Storage key
            data: Data to write
            merge_fn: Function to merge current and new data on conflict
                     Signature: merge_fn(current_data, new_data) -> merged_data
        """
        _, current_etag = self.read(key)
        
        if merge_fn:
            return self.write_cas(key, data, current_etag, retry_fn=merge_fn)
        else:
            return self.write_cas(key, data, current_etag)


class SessionCASStorage(CASFileStorage):
    """CAS storage specialized for session management."""
    
    def merge_sessions(self, current: list, new: list) -> list:
        """
        Merge two session arrays, keeping unique messages by ID.
        
        This is called on CAS conflict to merge concurrent writes.
        """
        seen_ids = set()
        merged = []
        
        # Add all current messages
        for item in current:
            msg_id = item.get('id') or item.get('_id') or hash(json.dumps(item, sort_keys=True))
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                merged.append(item)
        
        # Add new messages that aren't duplicates
        for item in new:
            msg_id = item.get('id') or item.get('_id') or hash(json.dumps(item, sort_keys=True))
            if msg_id not in seen_ids:
                seen_ids.add(msg_id)
                merged.append(item)
        
        # Sort by timestamp if available
        merged.sort(key=lambda x: x.get('timestamp', 0))
        
        return merged
    
    def save_session(self, session_key: str, messages: list) -> CASResult:
        """Save session with automatic conflict resolution."""
        return self.write_with_retry(
            session_key, 
            messages, 
            merge_fn=self.merge_sessions
        )
```

### 1.3 Migration Strategy

**Week 1 Tasks:**
1. Create `nanofolks/storage/cas_storage.py` module
2. Update `RoomSessionManager` to use CAS storage
3. Add feature flag `USE_CAS_STORAGE` (default False)
4. Write tests for concurrent write scenarios
5. Gradual rollout: enable for new rooms first

---

## Phase 2: Per-Room Message Brokers (Week 2)

### 2.1 Problem: Sequential Processing Bottleneck

Currently, all messages go through a single `AgentLoop` processing sequentially:

```python
# Current: Single global queue
async def process_job(self, job: ProcessingJob) -> None:
    # All messages processed one at a time globally
    # Room A blocks Room B blocks Room C
```

**Issues:**
- Slow room (complex query) blocks fast rooms
- No parallelism between independent conversations
- Cross-channel sync is manual and error-prone

### 2.2 Solution: Room-Based Parallel Processing

**New Architecture:**

```python
# nanofolks/broker/room_broker.py
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from loguru import logger
from nanofolks.bus.events import MessageEnvelope, MessageEnvelope
from nanofolks.storage.cas_storage import SessionCASStorage


@dataclass
class QueuedMessage:
    """Message in the room queue with sequence number."""
    seq: int  # Monotonic sequence number for ordering
    message: MessageEnvelope
    received_at: datetime = field(default_factory=datetime.now)
    claimed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None  # Bot name


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
        storage: SessionCASStorage,
        agent_loop: 'AgentLoop',
        max_queue_size: int = 1000
    ):
        self.room_id = room_id
        self.storage = storage
        self.agent_loop = agent_loop
        self.max_queue_size = max_queue_size
        
        # In-memory queue (backed by CAS storage for durability)
        self._queue: asyncio.Queue[QueuedMessage] = asyncio.Queue(maxsize=max_queue_size)
        self._seq_counter = 0
        self._running = False
        self._process_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.messages_received = 0
        self.messages_processed = 0
        self.messages_failed = 0
    
    async def enqueue(self, message: MessageEnvelope) -> bool:
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
                # Wait for message (with timeout for periodic checks)
                queued = await asyncio.wait_for(
                    self._queue.get(), 
                    timeout=1.0
                )
                
                # Mark as claimed
                queued.claimed_at = datetime.now()
                queued.claimed_by = self.agent_loop.bot_name
                
                # Process message
                try:
                    await self._process_message(queued)
                    self.messages_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process message {queued.seq}: {e}")
                    self.messages_failed += 1
                    # Could retry here with backoff
                
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
        
        # Pass to agent loop for actual processing
        await self.agent_loop.process_inbound(queued.message)
    
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
        storage: SessionCASStorage,
        agent_loop_factory: Callable[[], 'AgentLoop']
    ):
        self.storage = storage
        self.agent_loop_factory = agent_loop_factory
        self._brokers: dict[str, RoomMessageBroker] = {}
        self._lock = asyncio.Lock()
    
    async def route_message(self, message: MessageEnvelope) -> bool:
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
            # Get or create broker for this room
            if room_id not in self._brokers:
                broker = RoomMessageBroker(
                    room_id=room_id,
                    storage=self.storage,
                    agent_loop=self.agent_loop_factory()
                )
                await broker.start()
                self._brokers[room_id] = broker
                logger.info(f"Created broker for room {room_id}")
            
            broker = self._brokers[room_id]
        
        # Enqueue (outside lock)
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
```

### 2.3 Benefits

1. **Parallel Processing**: Room A and Room B process simultaneously
2. **FIFO Guarantees**: Messages within a room processed in order
3. **Isolation**: Slow query in one room doesn't block others
4. **Scalability**: Add more agent loops for high-traffic rooms

---

## Phase 3: Group Commit for Message Batching (Week 2-3)

### 3.1 Problem: Excessive I/O

Current behavior: Every message triggers a file write
```
10 messages = 10 file writes = 10 * 5ms = 50ms I/O time
```

### 3.2 Solution: Buffered Group Commit

```python
# nanofolks/broker/group_commit.py
import asyncio
from dataclasses import dataclass
from typing import List, Callable
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class CommitBatch:
    """Batch of messages to commit together."""
    messages: List[dict]
    created_at: datetime
    futures: List[asyncio.Future]  # For acknowledging each message


class GroupCommitBuffer:
    """
    Buffers messages and commits in batches to reduce I/O.
    
    Inspired by database group commit: coalesce multiple writes
    into a single disk flush.
    """
    
    def __init__(
        self,
        commit_fn: Callable[[List[dict]], None],
        max_batch_size: int = 50,
        max_latency_ms: float = 100.0,
        min_batch_size: int = 5
    ):
        self.commit_fn = commit_fn
        self.max_batch_size = max_batch_size
        self.max_latency = timedelta(milliseconds=max_latency_ms)
        self.min_batch_size = min_batch_size
        
        self._buffer: List[dict] = []
        self._futures: List[asyncio.Future] = []
        self._lock = asyncio.Lock()
        self._commit_task: Optional[asyncio.Task] = None
        self._last_commit = datetime.now()
        self._running = False
    
    async def start(self) -> None:
        """Start the commit loop."""
        self._running = True
        self._commit_task = asyncio.create_task(self._commit_loop())
    
    async def stop(self) -> None:
        """Stop and flush remaining messages."""
        self._running = False
        if self._commit_task:
            # Final flush
            await self._flush()
            self._commit_task.cancel()
            try:
                await self._commit_task
            except asyncio.CancelledError:
                pass
    
    async def add(self, message: dict) -> asyncio.Future:
        """
        Add message to batch.
        
        Returns:
            Future that completes when message is committed
        """
        future = asyncio.Future()
        
        async with self._lock:
            self._buffer.append(message)
            self._futures.append(future)
            
            # Trigger immediate commit if batch is full
            if len(self._buffer) >= self.max_batch_size:
                asyncio.create_task(self._flush())
        
        return future
    
    async def _commit_loop(self) -> None:
        """Periodic commit based on latency."""
        while self._running:
            await asyncio.sleep(0.01)  # 10ms check interval
            
            async with self._lock:
                if not self._buffer:
                    continue
                
                elapsed = datetime.now() - self._last_commit
                
                # Commit if:
                # 1. Latency threshold reached, OR
                # 2. Min batch size reached and some time passed
                should_commit = (
                    elapsed >= self.max_latency or
                    (len(self._buffer) >= self.min_batch_size and elapsed >= timedelta(milliseconds=10))
                )
                
                if should_commit:
                    await self._do_commit()
    
    async def _flush(self) -> None:
        """Flush current buffer."""
        async with self._lock:
            if self._buffer:
                await self._do_commit()
    
    async def _do_commit(self) -> None:
        """Perform the actual commit."""
        if not self._buffer:
            return
        
        messages = self._buffer.copy()
        futures = self._futures.copy()
        
        self._buffer.clear()
        self._futures.clear()
        self._last_commit = datetime.now()
        
        try:
            # Execute commit
            await asyncio.get_event_loop().run_in_executor(
                None, self.commit_fn, messages
            )
            
            # Signal completion
            for future in futures:
                if not future.done():
                    future.set_result(True)
            
            logger.debug(f"Group commit: {len(messages)} messages")
            
        except Exception as e:
            logger.error(f"Group commit failed: {e}")
            # Signal failure
            for future in futures:
                if not future.done():
                    future.set_exception(e)


# Usage in RoomMessageBroker
class RoomMessageBroker:
    def __init__(self, ...):
        # ... existing init ...
        self._commit_buffer = GroupCommitBuffer(
            commit_fn=self._persist_messages,
            max_batch_size=50,
            max_latency_ms=100
        )
    
    def _persist_messages(self, messages: List[dict]) -> None:
        """Persist batch of messages to storage."""
        # CAS write all messages at once
        self.storage.save_session(self.room_id, messages)
    
    async def _process_message(self, queued: QueuedMessage) -> None:
        # Process through agent
        response = await self.agent_loop.process_inbound(queued.message)
        
        # Add to batch instead of immediate write
        await self._commit_buffer.add({
            'seq': queued.seq,
            'message': queued.message,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
```

### 3.3 Performance Impact

**Before:**
- 100 messages = 100 writes × 5ms = 500ms

**After (group commit):**
- 100 messages = 2 batches × 5ms = 10ms
- **50x reduction in I/O time**

---

## Phase 4: Bot Coordination with Heartbeats (Week 3)

### 4.1 Problem: Bot Task Assignment

In the 6-bot system, if a bot crashes mid-task:
- Task is stuck "in progress"
- No recovery mechanism
- Other bots don't know the task failed

### 4.2 Solution: Heartbeat-Based Task Tracking

```python
# nanofolks/bots/coordinator.py
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from enum import Enum
from loguru import logger


class TaskStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class BotTask:
    """A task assigned to a bot."""
    task_id: str
    room_id: str
    message_seq: int
    bot_name: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class BotCoordinator:
    """
    Coordinates the 6-bot fleet with heartbeats and task reassignment.
    
    Each bot must send heartbeats while processing. If a bot fails to
    heartbeat within the timeout, its tasks are reassigned.
    """
    
    HEARTBEAT_INTERVAL_SEC = 5
    HEARTBEAT_TIMEOUT_SEC = 15
    
    def __init__(self):
        self._tasks: Dict[str, BotTask] = {}
        self._bot_heartbeats: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._active_bots: set[str] = set()
    
    async def start(self) -> None:
        """Start the coordinator."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Bot coordinator started")
    
    async def stop(self) -> None:
        """Stop the coordinator."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def register_bot(self, bot_name: str) -> None:
        """Register a bot as active."""
        async with self._lock:
            self._active_bots.add(bot_name)
            self._bot_heartbeats[bot_name] = datetime.now()
        logger.info(f"Bot {bot_name} registered")
    
    async def unregister_bot(self, bot_name: str) -> None:
        """Unregister a bot."""
        async with self._lock:
            self._active_bots.discard(bot_name)
            self._bot_heartbeats.pop(bot_name, None)
        logger.info(f"Bot {bot_name} unregistered")
    
    async def heartbeat(self, bot_name: str) -> None:
        """Record a heartbeat from a bot."""
        async with self._lock:
            self._bot_heartbeats[bot_name] = datetime.now()
    
    async def claim_task(
        self, 
        task_id: str, 
        bot_name: str,
        room_id: str,
        message_seq: int
    ) -> bool:
        """
        Claim a task for a bot.
        
        Returns:
            True if claim successful, False if already claimed
        """
        async with self._lock:
            if task_id in self._tasks:
                existing = self._tasks[task_id]
                if existing.status == TaskStatus.CLAIMED:
                    # Check if claim expired
                    if existing.last_heartbeat:
                        elapsed = (datetime.now() - existing.last_heartbeat).total_seconds()
                        if elapsed > self.HEARTBEAT_TIMEOUT_SEC:
                            # Reclaim
                            existing.bot_name = bot_name
                            existing.claimed_at = datetime.now()
                            existing.last_heartbeat = datetime.now()
                            return True
                return False
            
            # New task
            task = BotTask(
                task_id=task_id,
                room_id=room_id,
                message_seq=message_seq,
                bot_name=bot_name,
                status=TaskStatus.CLAIMED,
                claimed_at=datetime.now(),
                last_heartbeat=datetime.now()
            )
            self._tasks[task_id] = task
            return True
    
    async def start_task(self, task_id: str, bot_name: str) -> bool:
        """Mark task as started."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.bot_name == bot_name:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
                return True
            return False
    
    async def complete_task(
        self, 
        task_id: str, 
        bot_name: str,
        result: dict
    ) -> bool:
        """Mark task as completed."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.bot_name == bot_name:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result
                return True
            return False
    
    async def fail_task(
        self, 
        task_id: str, 
        bot_name: str,
        error: str
    ) -> bool:
        """Mark task as failed."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.bot_name == bot_name:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error = error
                return True
            return False
    
    async def _monitor_loop(self) -> None:
        """Monitor heartbeats and reassign stuck tasks."""
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL_SEC)
            
            async with self._lock:
                now = datetime.now()
                
                # Check for timed-out bots
                timed_out_bots = []
                for bot_name, last_hb in self._bot_heartbeats.items():
                    elapsed = (now - last_hb).total_seconds()
                    if elapsed > self.HEARTBEAT_TIMEOUT_SEC:
                        timed_out_bots.append(bot_name)
                
                # Reassign tasks from timed-out bots
                for task in self._tasks.values():
                    if task.bot_name in timed_out_bots:
                        if task.status in (TaskStatus.CLAIMED, TaskStatus.RUNNING):
                            logger.warning(
                                f"Bot {task.bot_name} timed out, "
                                f"reassigning task {task.task_id}"
                            )
                            task.status = TaskStatus.PENDING
                            task.bot_name = ""
                            task.claimed_at = None
                            task.last_heartbeat = None
                
                # Clean up old completed tasks
                cutoff = now - timedelta(hours=1)
                to_remove = [
                    tid for tid, task in self._tasks.items()
                    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
                    and task.completed_at and task.completed_at < cutoff
                ]
                for tid in to_remove:
                    del self._tasks[tid]
    
    async def get_pending_tasks(self, room_id: Optional[str] = None) -> List[BotTask]:
        """Get pending tasks, optionally filtered by room."""
        async with self._lock:
            tasks = [
                task for task in self._tasks.values()
                if task.status == TaskStatus.PENDING
            ]
            if room_id:
                tasks = [t for t in tasks if t.room_id == room_id]
            return tasks
    
    def get_stats(self) -> dict:
        """Get coordinator statistics."""
        status_counts = {}
        for task in self._tasks.values():
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
        
        return {
            "active_bots": len(self._active_bots),
            "total_tasks": len(self._tasks),
            "by_status": status_counts
        }
```

### 4.3 Integration with Room Brokers

```python
class RoomMessageBroker:
    async def _process_message(self, queued: QueuedMessage) -> None:
        # Generate task ID
        task_id = f"{self.room_id}:{queued.seq}"
        
        # Claim task with coordinator
        if not await self.coordinator.claim_task(
            task_id=task_id,
            bot_name=self.agent_loop.bot_name,
            room_id=self.room_id,
            message_seq=queued.seq
        ):
            logger.warning(f"Task {task_id} already claimed")
            return
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._send_heartbeats(task_id)
            )
            
            # Mark as started
            await self.coordinator.start_task(task_id, self.agent_loop.bot_name)
            
            # Process message
            response = await self.agent_loop.process_inbound(queued.message)
            
            # Complete task
            await self.coordinator.complete_task(
                task_id, 
                self.agent_loop.bot_name,
                {"response": response}
            )
            
        except Exception as e:
            await self.coordinator.fail_task(
                task_id,
                self.agent_loop.bot_name,
                str(e)
            )
            raise
        finally:
            heartbeat_task.cancel()
    
    async def _send_heartbeats(self, task_id: str) -> None:
        """Send periodic heartbeats while processing."""
        while True:
            await asyncio.sleep(BotCoordinator.HEARTBEAT_INTERVAL_SEC)
            await self.coordinator.heartbeat(self.agent_loop.bot_name)
```

---

## Implementation Timeline

### Week 1: CAS Storage Foundation
- [ ] Day 1-2: Create `CASFileStorage` module
- [ ] Day 3: Update `RoomSessionManager` to use CAS
- [ ] Day 4: Write comprehensive tests for concurrent writes
- [ ] Day 5: Add feature flag and test in staging

### Week 2: Per-Room Brokers
- [ ] Day 1-2: Implement `RoomMessageBroker`
- [ ] Day 3: Implement `RoomBrokerManager`
- [ ] Day 4: Integrate with existing message bus
- [ ] Day 5: Add group commit buffer

### Week 3: Bot Coordination & Polish
- [ ] Day 1-2: Implement `BotCoordinator` with heartbeats
- [ ] Day 3: Integration testing across all components
- [ ] Day 4: Performance benchmarking
- [ ] Day 5: Documentation and rollout plan

---

## Risk Mitigation

### Risk 1: CAS Performance Degradation
**Mitigation:** Implement in-memory caching layer; CAS only used for persistence

### Risk 2: Increased Memory Usage (per-room brokers)
**Mitigation:** Broker per room, not per channel; idle rooms garbage collect after 1 hour

### Risk 3: Message Loss During Migration
**Mitigation:** Feature flags allow gradual rollout; can disable and fall back to old system

### Risk 4: Complexity in Debugging
**Mitigation:** Extensive logging and metrics; dashboard for queue depths and broker stats

---

## Success Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| Concurrent write safety | None (race conditions) | 100% CAS success | Conflict resolution rate |
| File I/O operations | 1 per message | 1 per 50 messages (group commit) | Write operations/sec |
| Message ordering | Best effort | FIFO guarantee within room | Message sequence validation |
| Bot crash recovery | None | <15s reassignment | Time to reassign stuck tasks |
| Cross-channel latency | Variable | <100ms P99 | Time from channel receive to queue |

---

## Conclusion

This plan addresses the critical concurrency and ordering issues in nanofolks' multi-channel architecture while maintaining the existing Python codebase. The CAS pattern eliminates file corruption, per-room brokers enable parallelism, group commit reduces I/O, and heartbeats ensure reliable bot coordination.

**Next Steps:**
1. Review and approve design
2. Create implementation tickets
3. Begin Week 1 development
4. Weekly progress reviews

---

**References:**
- [Turbopuffer Queue Architecture](https://turbopuffer.com/blog/object-storage-queue)
- Current implementation: `nanofolks/session/dual_mode.py`, `nanofolks/bus/queue.py`
- Related proposals: `ROOM_CENTRIC_IMPLEMENTATION_PLAN.md`
