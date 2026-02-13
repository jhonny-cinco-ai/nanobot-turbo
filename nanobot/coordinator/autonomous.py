"""Autonomous bot collaboration system.

Enables bots to work together without explicit orchestration,
suggesting tasks, sharing expertise, and self-organizing.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger

from nanobot.coordinator.bus import InterBotBus
from nanobot.coordinator.models import BotMessage, MessageType, Task, TaskStatus
from nanobot.coordinator.store import CoordinatorStore
from nanobot.memory.bot_memory import BotExpertise


class AutonomousBotTeam:
    """Manages autonomous bot collaboration and self-organization.
    
    Enables bots to:
    - Monitor team progress
    - Suggest follow-up tasks
    - Volunteer for work
    - Self-organize on projects
    - Share expertise proactively
    """
    
    def __init__(
        self,
        bus: InterBotBus,
        store: CoordinatorStore,
        expertise: BotExpertise,
        workspace_id: str
    ):
        """Initialize autonomous team.
        
        Args:
            bus: InterBotBus for communication
            store: CoordinatorStore for persistence
            expertise: BotExpertise for routing
            workspace_id: Workspace identifier
        """
        self.bus = bus
        self.store = store
        self.expertise = expertise
        self.workspace_id = workspace_id
        
        # Team state
        self._active_bots: Set[str] = set()
        self._task_queue: List[Task] = []
        self._suggestions_made: Dict[str, int] = defaultdict(int)
        self._collaboration_history: List[str] = []
        
        # Configuration
        self.suggestion_threshold = 0.75  # Confidence threshold for suggestions
        self.collaboration_timeout = 3600  # seconds (1 hour)
        self.max_suggestions_per_bot = 5
    
    def register_bot(self, bot_id: str) -> None:
        """Register a bot as part of the team.
        
        Args:
            bot_id: The bot ID to register
        """
        self._active_bots.add(bot_id)
        logger.info(f"Bot registered with autonomous team: {bot_id}")
    
    def get_active_bots(self) -> List[str]:
        """Get list of active bots.
        
        Returns:
            List of active bot IDs
        """
        return list(self._active_bots)
    
    def monitor_team_progress(self) -> Dict[str, any]:
        """Monitor overall team progress.
        
        Returns:
            Dictionary with team statistics
        """
        # Get all tasks for this workspace
        completed = self.store.get_tasks_by_status(TaskStatus.COMPLETED, self.workspace_id, limit=100)
        in_progress = self.store.get_tasks_by_status(TaskStatus.IN_PROGRESS, self.workspace_id, limit=100)
        failed = self.store.get_tasks_by_status(TaskStatus.FAILED, self.workspace_id, limit=100)
        pending = self.store.get_tasks_by_status(TaskStatus.PENDING, self.workspace_id, limit=100)
        
        total_tasks = len(completed) + len(in_progress) + len(failed) + len(pending)
        
        # Calculate team statistics
        stats = {
            "active_bots": len(self._active_bots),
            "total_tasks": total_tasks,
            "completed_tasks": len(completed),
            "in_progress_tasks": len(in_progress),
            "failed_tasks": len(failed),
            "pending_tasks": len(pending),
            "success_rate": len(completed) / total_tasks if total_tasks > 0 else 0.0,
            "avg_confidence": (
                sum(t.confidence for t in completed) / len(completed)
                if completed else 0.0
            ),
            "suggestions_made": dict(self._suggestions_made),
            "team_velocity": self._calculate_velocity(completed),
        }
        
        return stats
    
    def suggest_tasks(self) -> List[Tuple[str, Task]]:
        """Suggest follow-up tasks based on completed work.
        
        Returns:
            List of (bot_id, suggested_task) tuples
        """
        suggestions = []
        
        # Get recently completed tasks
        completed = self.store.get_tasks_by_status(TaskStatus.COMPLETED, self.workspace_id, limit=20)
        
        for task in completed:
            if not task.follow_ups:
                continue
            
            # Convert follow-up descriptions to tasks
            for follow_up_desc in task.follow_ups:
                # Parse follow-up to create task
                suggested_task = self._create_suggested_task(
                    description=follow_up_desc,
                    domain=task.domain,
                    parent_task_id=task.id
                )
                
                # Find best bot for this task
                best_bot = self._find_best_bot_for_task(suggested_task)
                
                if best_bot:
                    suggestions.append((best_bot, suggested_task))
                    self._suggestions_made[best_bot] += 1
                    
                    # Log suggestion
                    msg = BotMessage(
                        sender_id="team",
                        recipient_id=best_bot,
                        message_type=MessageType.REQUEST,
                        content=f"Suggested task: {suggested_task.title}",
                        context={"task_id": suggested_task.id, "source": "auto_suggestion"}
                    )
                    self.bus.send_message(msg)
                    
                    logger.info(f"Suggested task to {best_bot}: {suggested_task.title}")
        
        return suggestions
    
    def detect_bottlenecks(self) -> List[Dict[str, any]]:
        """Detect workflow bottlenecks and suggest workarounds.
        
        Returns:
            List of bottleneck descriptions
        """
        bottlenecks = []
        
        # Get in-progress tasks
        in_progress = self.store.get_tasks_by_status(TaskStatus.IN_PROGRESS, self.workspace_id, limit=50)
        
        # Check for tasks exceeding time estimates
        now = datetime.now()
        for task in in_progress:
            if not task.started_at:
                continue
            
            elapsed = (now - task.started_at).total_seconds()
            
            # If task is taking longer than expected (heuristic: > 2 hours), flag as bottleneck
            if elapsed > 7200:  # 2 hours
                bottlenecks.append({
                    "task_id": task.id,
                    "task_title": task.title,
                    "assigned_to": task.assigned_to,
                    "elapsed_seconds": elapsed,
                    "issue": "Task taking longer than expected",
                    "suggestion": f"Consider offering assistance to {task.assigned_to}"
                })
        
        # Check for failed tasks with no retry
        failed = self.store.get_tasks_by_status(TaskStatus.FAILED, self.workspace_id, limit=20)
        for task in failed:
            if task.completed_at and (now - task.completed_at).total_seconds() < 300:  # < 5 mins ago
                bottlenecks.append({
                    "task_id": task.id,
                    "task_title": task.title,
                    "assigned_to": task.assigned_to,
                    "issue": "Recent task failure",
                    "suggestion": f"Offer alternative approach to {task.assigned_to}"
                })
        
        return bottlenecks
    
    def volunteer_assistance(self, helper_bot: str) -> Optional[Task]:
        """Bot volunteers to help with a task.
        
        Args:
            helper_bot: Bot offering assistance
            
        Returns:
            Task to help with, or None if none available
        """
        # Find a task that could use help
        in_progress = self.store.get_tasks_by_status(TaskStatus.IN_PROGRESS, self.workspace_id, limit=10)
        
        for task in in_progress:
            # Check if helper has relevant expertise
            helper_score = self.expertise.get_expertise_score(helper_bot, task.domain)
            
            if helper_score > 0.5:  # Has some expertise
                logger.info(f"{helper_bot} volunteering to help with task: {task.title}")
                
                # Send offer message
                msg = BotMessage(
                    sender_id=helper_bot,
                    recipient_id=task.assigned_to,
                    message_type=MessageType.REQUEST,
                    content=f"I can help you with '{task.title}'. I have {helper_score:.0%} expertise in {task.domain}.",
                    context={"task_id": task.id, "offer_type": "collaboration"}
                )
                self.bus.send_message(msg)
                
                return task
        
        return None
    
    def handle_bot_suggestion_response(
        self,
        bot_id: str,
        task_id: str,
        accepted: bool,
        reason: Optional[str] = None
    ) -> None:
        """Handle bot's response to a suggested task.
        
        Args:
            bot_id: The bot responding
            task_id: The suggested task ID
            accepted: Whether the task was accepted
            reason: Optional reason for response
        """
        if accepted:
            logger.info(f"{bot_id} accepted suggested task {task_id}")
            self._collaboration_history.append(f"{bot_id}:accepted:{task_id}")
        else:
            logger.info(f"{bot_id} declined suggested task {task_id}: {reason or 'no reason given'}")
            self._collaboration_history.append(f"{bot_id}:declined:{task_id}")
    
    def report_team_status(self) -> str:
        """Generate team status report.
        
        Returns:
            Formatted status report
        """
        stats = self.monitor_team_progress()
        
        lines = [
            "=== AUTONOMOUS TEAM STATUS REPORT ===",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Active Bots: {stats['active_bots']}",
            "",
            "Task Statistics:",
            f"  Total: {stats['total_tasks']}",
            f"  Completed: {stats['completed_tasks']}",
            f"  In Progress: {stats['in_progress_tasks']}",
            f"  Failed: {stats['failed_tasks']}",
            f"  Pending: {stats['pending_tasks']}",
            "",
            "Performance Metrics:",
            f"  Success Rate: {stats['success_rate']:.1%}",
            f"  Avg Confidence: {stats['avg_confidence']:.2f}",
            f"  Team Velocity: {stats['team_velocity']:.1f} tasks/hour",
            "",
            "Collaboration Activity:",
            f"  Suggestions Made: {sum(stats['suggestions_made'].values())}",
        ]
        
        # Add per-bot stats
        if stats['suggestions_made']:
            lines.append("  Per-Bot Suggestions:")
            for bot_id, count in sorted(stats['suggestions_made'].items()):
                lines.append(f"    - {bot_id}: {count}")
        
        # Add recent activity
        bottlenecks = self.detect_bottlenecks()
        if bottlenecks:
            lines.append("")
            lines.append("Detected Bottlenecks:")
            for bn in bottlenecks[:3]:
                lines.append(f"  - {bn['task_title']}: {bn['issue']}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _create_suggested_task(
        self,
        description: str,
        domain: str,
        parent_task_id: Optional[str] = None
    ) -> Task:
        """Create a task from a suggestion.
        
        Args:
            description: Task description
            domain: Task domain
            parent_task_id: Optional parent task ID
            
        Returns:
            New Task object
        """
        return Task(
            id=str(uuid.uuid4()),
            title=f"Follow-up: {description[:50]}",
            description=description,
            domain=domain,
            assigned_to="",  # Will be assigned by suggest_tasks
            parent_task_id=parent_task_id,
            created_by="autonomous_system"
        )
    
    def _find_best_bot_for_task(self, task: Task) -> Optional[str]:
        """Find the best bot for a task.
        
        Args:
            task: The task
            
        Returns:
            Bot ID or None
        """
        if not self._active_bots:
            return None
        
        best_bot = None
        best_score = -1
        
        for bot_id in self._active_bots:
            score = self.expertise.get_expertise_score(bot_id, task.domain)
            
            # Factor in current workload (fewer suggestions = better)
            workload_factor = 1 - (self._suggestions_made[bot_id] / self.max_suggestions_per_bot)
            adjusted_score = score * workload_factor
            
            if adjusted_score > best_score:
                best_bot = bot_id
                best_score = adjusted_score
        
        return best_bot if best_score > self.suggestion_threshold else None
    
    def _calculate_velocity(self, completed_tasks: List[Task]) -> float:
        """Calculate team velocity (tasks per hour).
        
        Args:
            completed_tasks: List of completed tasks
            
        Returns:
            Tasks per hour
        """
        if not completed_tasks:
            return 0.0
        
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        tasks_in_last_hour = sum(
            1 for t in completed_tasks
            if t.completed_at and t.completed_at > one_hour_ago
        )
        
        return tasks_in_last_hour


class BotCollaborator:
    """Mixin for bots to enable autonomous collaboration.
    
    Add to SpecialistBot to enable:
    - Suggesting follow-up tasks
    - Volunteering for work
    - Sharing expertise
    """
    
    def __init__(self, team: AutonomousBotTeam):
        """Initialize collaborator.
        
        Args:
            team: AutonomousBotTeam instance
        """
        self.team = team
        self.collaboration_stats = {
            "tasks_suggested": 0,
            "tasks_accepted": 0,
            "assistance_offered": 0,
            "expertise_shared": 0,
        }
    
    def add_followup_task(self, task: Task, description: str) -> None:
        """Add a follow-up task suggestion.
        
        Args:
            task: Current task
            description: Description of follow-up work
        """
        if not hasattr(task, 'follow_ups'):
            task.follow_ups = []
        
        task.follow_ups.append(description)
        self.collaboration_stats["tasks_suggested"] += 1
        
        logger.info(f"Added follow-up suggestion: {description}")
    
    def volunteer_for_work(self) -> Optional[Task]:
        """Volunteer to help with team tasks.
        
        Returns:
            Task to help with or None
        """
        task = self.team.volunteer_assistance(self.name)
        
        if task:
            self.collaboration_stats["assistance_offered"] += 1
        
        return task
    
    def share_expertise(self, domain: str, expertise_description: str) -> None:
        """Share expertise with the team.
        
        Args:
            domain: Domain of expertise
            expertise_description: Description of expertise
        """
        msg = BotMessage(
            sender_id=self.name,
            recipient_id="team",
            message_type=MessageType.DISCUSSION,
            content=f"Expertise in {domain}: {expertise_description}",
            context={"expertise_domain": domain}
        )
        
        self.team.bus.send_message(msg)
        self.collaboration_stats["expertise_shared"] += 1
        
        logger.info(f"{self.name} shared expertise in {domain}")
    
    def get_collaboration_stats(self) -> Dict[str, int]:
        """Get collaboration statistics.
        
        Returns:
            Dictionary of stats
        """
        return self.collaboration_stats.copy()
