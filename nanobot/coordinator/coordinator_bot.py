"""Coordinator bot for multi-agent orchestration.

The Coordinator bot manages team collaboration, delegates tasks,
and ensures smooth inter-bot communication.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from nanobot.bots.base import SpecialistBot
from nanobot.coordinator.bus import InterBotBus
from nanobot.coordinator.models import BotMessage, MessageType, Task, TaskStatus
from nanobot.memory.bot_memory import BotExpertise
from nanobot.models.workspace import Workspace


class CoordinatorBot(SpecialistBot):
    """The Coordinator bot - orchestrates team collaboration.
    
    Responsibilities:
    - Route user requests to appropriate bots
    - Decompose complex tasks into sub-tasks
    - Delegate work to specialists
    - Monitor task progress
    - Assemble and present results
    - Facilitate team discussions
    """
    
    def __init__(self, role_card, bus: InterBotBus, expertise: BotExpertise):
        """Initialize the Coordinator bot.
        
        Args:
            role_card: Role card defining bot personality
            bus: InterBotBus for communication
            expertise: BotExpertise for bot selection
        """
        super().__init__(role_card)
        self.bus = bus
        self.expertise = expertise
        
        # Coordinator state
        self._active_tasks: Dict[str, Task] = {}
        self._waiting_for_responses: Dict[str, BotMessage] = {}
        self._team_summary: str = ""
    
    def analyze_request(self, content: str, user_id: str) -> Dict:
        """Analyze a user request to determine routing.
        
        Args:
            content: User's request
            user_id: User ID
            
        Returns:
            Analysis dict with routing decision
        """
        analysis = {
            "content": content,
            "user_id": user_id,
            "complexity": self._estimate_complexity(content),
            "domains": self._extract_domains(content),
            "requires_team": False,
            "recommended_approach": "route_to_specialist",
        }
        
        # Determine complexity and approach
        if len(analysis["domains"]) == 0:
            analysis["recommended_approach"] = "ask_for_clarification"
        elif len(analysis["domains"]) == 1:
            if analysis["complexity"] == "high":
                analysis["requires_team"] = True
                analysis["recommended_approach"] = "decompose_and_delegate"
            else:
                analysis["recommended_approach"] = "route_to_specialist"
        else:
            analysis["requires_team"] = True
            analysis["recommended_approach"] = "parallel_delegation"
        
        logger.info(
            f"Request analysis: {analysis['recommended_approach']} "
            f"({len(analysis['domains'])} domains, complexity={analysis['complexity']})"
        )
        
        return analysis
    
    def find_best_bot(
        self,
        domain: str,
        available_bots: List[str],
        task_complexity: str = "medium"
    ) -> str:
        """Find the best bot for a task.
        
        Args:
            domain: Task domain
            available_bots: List of bot IDs to choose from
            task_complexity: low, medium, or high
            
        Returns:
            Best bot ID
        """
        if not available_bots:
            return self.name  # Fallback to self
        
        if len(available_bots) == 1:
            return available_bots[0]
        
        # Get expertise scores
        best_bot = available_bots[0]
        best_score = self.expertise.get_expertise_score(best_bot, domain)
        
        for bot_id in available_bots[1:]:
            score = self.expertise.get_expertise_score(bot_id, domain)
            if score > best_score:
                best_bot = bot_id
                best_score = score
        
        logger.info(f"Selected {best_bot} for {domain} (score: {best_score:.2f})")
        
        return best_bot
    
    def create_task(
        self,
        title: str,
        description: str,
        domain: str,
        assigned_to: str,
        requirements: Optional[List[str]] = None,
        due_date: Optional[datetime] = None,
        parent_task_id: Optional[str] = None
    ) -> Task:
        """Create a task for a bot.
        
        Args:
            title: Task title
            description: Detailed description
            domain: Task domain
            assigned_to: Bot ID to assign to
            requirements: List of requirements
            due_date: Optional due date
            parent_task_id: For sub-tasks
            
        Returns:
            Created Task object
        """
        task = Task(
            title=title,
            description=description,
            domain=domain,
            assigned_to=assigned_to,
            created_by=self.name,
            requirements=requirements or [],
            due_date=due_date,
            parent_task_id=parent_task_id,
        )
        
        self._active_tasks[task.id] = task
        
        # Send task to bot
        message = BotMessage(
            sender_id=self.name,
            recipient_id=assigned_to,
            message_type=MessageType.REQUEST,
            content=f"Task: {title}\n{description}",
            context={
                "task_id": task.id,
                "subject": title,
            }
        )
        
        msg_id = self.bus.send_message(message)
        self._waiting_for_responses[task.id] = message
        
        logger.info(
            f"Created task '{title}' and assigned to {assigned_to} (task_id: {task.id})"
        )
        
        return task
    
    def handle_task_result(
        self,
        task_id: str,
        result: str,
        confidence: float = 0.9,
        learnings: Optional[List[str]] = None,
        follow_ups: Optional[List[str]] = None
    ) -> bool:
        """Handle a task result from a bot.
        
        Args:
            task_id: The task ID
            result: The result content
            confidence: Confidence in result (0.0-1.0)
            learnings: Learnings from the task
            follow_ups: New tasks discovered
            
        Returns:
            True if successful
        """
        if task_id not in self._active_tasks:
            logger.warning(f"Received result for unknown task: {task_id}")
            return False
        
        task = self._active_tasks[task_id]
        task.mark_completed(result, confidence)
        
        if learnings:
            task.learnings = learnings
        if follow_ups:
            task.follow_ups = follow_ups
        
        # Remove from waiting
        if task_id in self._waiting_for_responses:
            del self._waiting_for_responses[task_id]
        
        logger.info(
            f"Task completed: {task.title} "
            f"(assigned to {task.assigned_to}, confidence: {confidence:.2f})"
        )
        
        return True
    
    def handle_task_failure(
        self,
        task_id: str,
        error: str,
        recovery_suggestion: Optional[str] = None
    ) -> bool:
        """Handle task failure.
        
        Args:
            task_id: The task ID
            error: Error description
            recovery_suggestion: Optional suggestion for recovery
            
        Returns:
            True if handled successfully
        """
        if task_id not in self._active_tasks:
            logger.warning(f"Failure report for unknown task: {task_id}")
            return False
        
        task = self._active_tasks[task_id]
        task.mark_failed(error)
        
        logger.warning(
            f"Task failed: {task.title} ({task.assigned_to})\n"
            f"Error: {error}"
        )
        
        # Notify team about failure
        if recovery_suggestion:
            message = BotMessage(
                sender_id=self.name,
                recipient_id="team",
                message_type=MessageType.DISCUSSION,
                content=f"Task '{task.title}' failed. Suggested recovery: {recovery_suggestion}",
                context={"task_id": task_id, "subject": f"Task Recovery: {task.title}"}
            )
            self.bus.send_message(message)
        
        return True
    
    def get_team_status(self) -> str:
        """Get current status of team and tasks.
        
        Returns:
            Status summary
        """
        lines = ["=== Team Status ==="]
        
        # Active tasks
        pending = [t for t in self._active_tasks.values() if t.status == TaskStatus.IN_PROGRESS]
        completed = [t for t in self._active_tasks.values() if t.status == TaskStatus.COMPLETED]
        failed = [t for t in self._active_tasks.values() if t.status == TaskStatus.FAILED]
        
        lines.append(f"Active: {len(pending)} | Completed: {len(completed)} | Failed: {len(failed)}")
        
        # Registered bots
        bots = self.bus.list_bots()
        lines.append(f"Team members: {len(bots)}")
        for bot_id, info in bots.items():
            msg_count = info.get("message_count", 0)
            lines.append(f"  - {info['name']} ({bot_id}): {msg_count} messages")
        
        # Top tasks
        if pending:
            lines.append("\nPending tasks:")
            for task in pending[:3]:
                lines.append(f"  - {task.title} (assigned to {task.assigned_to})")
        
        return "\n".join(lines)
    
    def broadcast_to_team(
        self,
        content: str,
        message_type: MessageType = MessageType.BROADCAST
    ) -> str:
        """Send a message to all team members.
        
        Args:
            content: Message content
            message_type: Type of message
            
        Returns:
            Message ID
        """
        message = BotMessage(
            sender_id=self.name,
            recipient_id="team",
            message_type=message_type,
            content=content,
            context={"subject": "Team announcement"}
        )
        
        msg_id = self.bus.send_message(message)
        logger.info(f"Broadcast to team: {content[:50]}...")
        
        return msg_id
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _estimate_complexity(self, content: str) -> str:
        """Estimate task complexity.
        
        Args:
            content: Task description
            
        Returns:
            low, medium, or high
        """
        # Simple heuristic based on content length and keywords
        complexity_keywords = {
            "high": ["analyze", "design", "architect", "recommend", "comprehensive"],
            "medium": ["implement", "review", "check", "update", "modify"],
            "low": ["fetch", "list", "get", "find"]
        }
        
        content_lower = content.lower()
        
        for level in ["high", "medium", "low"]:
            for keyword in complexity_keywords[level]:
                if keyword in content_lower:
                    return level
        
        # Default based on length
        if len(content) > 200:
            return "high"
        elif len(content) > 100:
            return "medium"
        else:
            return "low"
    
    def _extract_domains(self, content: str) -> List[str]:
        """Extract domains mentioned in content.
        
        Args:
            content: Content to analyze
            
        Returns:
            List of domain names
        """
        # Simple keyword-based extraction
        domain_keywords = {
            "research": ["research", "investigate", "analyze", "study", "explore"],
            "development": ["build", "implement", "code", "develop", "create"],
            "community": ["community", "social", "engagement", "communication"],
            "design": ["design", "ui", "ux", "interface", "visual"],
            "quality": ["test", "review", "audit", "check", "verify"],
        }
        
        content_lower = content.lower()
        found_domains = []
        
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if keyword in content_lower:
                    if domain not in found_domains:
                        found_domains.append(domain)
                    break
        
        return found_domains
    
    # =========================================================================
    # Abstract Method Implementations
    # =========================================================================
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        """Process a message and generate response.
        
        Args:
            message: User or system message
            workspace: Workspace context
            
        Returns:
            Bot's response message
        """
        # Analyze the request
        analysis = self.analyze_request(message, "user")
        
        response_parts = [
            f"I'll help with that. I'm analyzing your request ({analysis['complexity']} complexity).",
            f"Domains involved: {', '.join(analysis['domains']) or 'general'}",
            f"Approach: {analysis['recommended_approach'].replace('_', ' ')}",
        ]
        
        if analysis["requires_team"]:
            response_parts.append("I'll coordinate with the team to handle this.")
        
        return "\n".join(response_parts)
    
    async def execute_task(self, task: str, workspace: Workspace) -> Dict[str, Any]:
        """Execute a specific task.
        
        Args:
            task: Task description
            workspace: Workspace context
            
        Returns:
            Task result dictionary
        """
        # Create a task object
        task_obj = self.create_task(
            title="Coordinator Task",
            description=task,
            domain="coordination",
            assigned_to=self.name,
            parent_task_id=None
        )
        
        return {
            "task_id": task_obj.id,
            "status": "created",
            "title": task_obj.title,
            "assigned_to": task_obj.assigned_to,
        }
