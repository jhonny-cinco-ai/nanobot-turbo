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
    last_crew_routines: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class BotCoordinator:
    """
    Coordinates the bot fleet with crew routines and task reassignment.
    
    Each bot must send crew routines while processing. If a bot fails to
    check in within the timeout, its tasks are reassigned.
    """
    
    CREW_ROUTINES_INTERVAL_SEC = 5
    CREW_ROUTINES_TIMEOUT_SEC = 15
    
    def __init__(self):
        self._tasks: Dict[str, BotTask] = {}
        self._bot_crew_routines: Dict[str, datetime] = {}
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
            self._bot_crew_routines[bot_name] = datetime.now()
        logger.info(f"Bot {bot_name} registered")
    
    async def unregister_bot(self, bot_name: str) -> None:
        """Unregister a bot."""
        async with self._lock:
            self._active_bots.discard(bot_name)
            self._bot_crew_routines.pop(bot_name, None)
        logger.info(f"Bot {bot_name} unregistered")
    
    async def crew_routines(self, bot_name: str) -> None:
        """Record a crew routines check-in from a bot."""
        async with self._lock:
            self._bot_crew_routines[bot_name] = datetime.now()
    
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
                    if existing.last_crew_routines:
                        elapsed = (datetime.now() - existing.last_crew_routines).total_seconds()
                        if elapsed > self.CREW_ROUTINES_TIMEOUT_SEC:
                            existing.bot_name = bot_name
                            existing.claimed_at = datetime.now()
                            existing.last_crew_routines = datetime.now()
                            return True
                return False
            
            task = BotTask(
                task_id=task_id,
                room_id=room_id,
                message_seq=message_seq,
                bot_name=bot_name,
                status=TaskStatus.CLAIMED,
                claimed_at=datetime.now(),
                last_crew_routines=datetime.now()
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
        """Monitor crew routines and reassign stuck tasks."""
        while self._running:
            await asyncio.sleep(self.CREW_ROUTINES_INTERVAL_SEC)
            
            async with self._lock:
                now = datetime.now()
                
                timed_out_bots = []
                for bot_name, last_hb in self._bot_crew_routines.items():
                    elapsed = (now - last_hb).total_seconds()
                    if elapsed > self.CREW_ROUTINES_TIMEOUT_SEC:
                        timed_out_bots.append(bot_name)
                
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
                            task.last_crew_routines = None
                
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
