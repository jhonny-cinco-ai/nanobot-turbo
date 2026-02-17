"""Project State Manager - Manages state for full discovery flow."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

from loguru import logger


class ProjectPhase(Enum):
    """Project lifecycle phases."""
    IDLE = "idle"
    DISCOVERY = "discovery"
    SYNTHESIS = "synthesis"
    APPROVAL = "approval"
    EXECUTION = "execution"
    REVIEW = "review"


@dataclass
class ProjectState:
    """Current state of a project/task."""
    phase: ProjectPhase = ProjectPhase.IDLE
    user_goal: str = ""
    intent_type: str = ""
    discovery_log: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    approval: Optional[Dict[str, Any]] = None
    execution_plan: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    iteration: int = 0
    suggested_bots: List[str] = field(default_factory=list)


class ProjectStateManager:
    """Manages project state across sessions for full discovery flow.
    
    This implements the state machine for:
    DISCOVERY → SYNTHESIS → APPROVAL → EXECUTION → REVIEW → IDLE
    """
    
    TIMEOUT_MINUTES = 30
    MIN_QUESTIONS = 3
    MIN_BOTS_WITH_QUESTIONS = 2
    
    def __init__(self, workspace: Path, room_id: str):
        """Initialize project state manager.
        
        Args:
            workspace: Workspace directory
            room_id: Room identifier
        """
        self.workspace = workspace
        self.room_id = room_id
        self.state_dir = workspace / ".nanofolks" / "project_states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{room_id}.json"
        self._state: Optional[ProjectState] = None
    
    @property
    def state(self) -> ProjectState:
        """Get current state (lazy load)."""
        if self._state is None:
            self._state = self._load_state()
        return self._state
    
    def _load_state(self) -> ProjectState:
        """Load state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    data['created_at'] = datetime.fromisoformat(data['created_at'])
                    data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                    data['phase'] = ProjectPhase(data['phase'])
                    return ProjectState(**data)
            except Exception as e:
                logger.warning(f"Failed to load project state: {e}")
        return ProjectState()
    
    def _save_state(self):
        """Persist state to disk."""
        data = {
            'phase': self.state.phase.value,
            'user_goal': self.state.user_goal,
            'intent_type': self.state.intent_type,
            'discovery_log': self.state.discovery_log,
            'synthesis': self.state.synthesis,
            'approval': self.state.approval,
            'execution_plan': self.state.execution_plan,
            'created_at': self.state.created_at.isoformat(),
            'updated_at': datetime.now().isoformat(),
            'iteration': self.state.iteration,
            'suggested_bots': self.state.suggested_bots,
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def start_discovery(self, user_goal: str, intent_type: str, suggested_bots: Optional[List[str]] = None):
        """Begin discovery phase.
        
        Args:
            user_goal: The user's original goal/request
            intent_type: Type of intent (build, explore, task, etc.)
            suggested_bots: Bots relevant to this intent
        """
        self.state.phase = ProjectPhase.DISCOVERY
        self.state.user_goal = user_goal
        self.state.intent_type = intent_type
        self.state.discovery_log = []
        self.state.synthesis = None
        self.state.approval = None
        self.state.suggested_bots = suggested_bots if suggested_bots else ["leader", "researcher", "creative"]
        self.state.iteration += 1
        self._save_state()
        
        logger.info(f"Started discovery for: {user_goal[:50]}...")
    
    def log_discovery_entry(
        self, 
        bot_name: str, 
        content: str, 
        is_question: bool = True
    ):
        """Log discovery question or answer.
        
        Args:
            bot_name: Name of the bot (or "user")
            content: The question or answer content
            is_question: Whether this is a question
        """
        self.state.discovery_log.append({
            'bot': bot_name,
            'content': content,
            'is_question': is_question,
            'timestamp': datetime.now().isoformat()
        })
        self._save_state()
    
    def complete_discovery(self):
        """Transition from discovery to synthesis."""
        self.state.phase = ProjectPhase.SYNTHESIS
        self._save_state()
        
        logger.info("Discovery complete, moving to synthesis")
    
    def set_synthesis(self, synthesis: Dict[str, Any]):
        """Set synthesis and move to approval.
        
        Args:
            synthesis: The synthesized project brief
        """
        self.state.synthesis = synthesis
        self.state.phase = ProjectPhase.APPROVAL
        self._save_state()
        
        logger.info("Synthesis complete, awaiting approval")
    
    def handle_approval(self, approved: bool, feedback: Optional[str] = None):
        """Handle user approval decision.
        
        Args:
            approved: Whether the user approved
            feedback: User's feedback if rejected
        """
        self.state.approval = {
            'approved': approved,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }
        
        if approved:
            self.state.phase = ProjectPhase.EXECUTION
            logger.info("Approved! Moving to execution")
        else:
            self.state.phase = ProjectPhase.DISCOVERY
            logger.info("Rejected! Returning to discovery")
        
        self._save_state()
    
    def start_execution(self, plan: Dict[str, Any]):
        """Begin execution phase.
        
        Args:
            plan: Execution plan with tasks for each bot
        """
        self.state.execution_plan = plan
        self.state.phase = ProjectPhase.EXECUTION
        self._save_state()
        
        logger.info("Starting execution phase")
    
    def complete_review(self):
        """Reset to idle after successful review."""
        self.state.phase = ProjectPhase.IDLE
        self._save_state()
        
        logger.info("Project complete, reset to idle")
    
    def reset(self):
        """Force reset to idle state."""
        self.state.phase = ProjectPhase.IDLE
        self._save_state()
        
        logger.info("Project state reset to idle")
    
    def check_timeout(self) -> bool:
        """Check if project timed out due to inactivity.
        
        Returns:
            True if timed out and reset to idle
        """
        if self.state.phase == ProjectPhase.IDLE:
            return False
        
        elapsed = (datetime.now() - self.state.updated_at).total_seconds() / 60
        if elapsed > self.TIMEOUT_MINUTES:
            self.state.phase = ProjectPhase.IDLE
            self._save_state()
            logger.info(f"Project timed out after {elapsed:.0f} minutes")
            return True
        return False
    
    def _is_discovery_complete(self) -> bool:
        """Check if discovery phase is complete.
        
        Discovery is complete when:
        - At least MIN_QUESTIONS questions have been asked
        - At least MIN_BOTS_WITH_QUESTIONS different bots have asked questions
        """
        log = self.state.discovery_log
        
        questions = [e for e in log if e.get('is_question', True)]
        bots_with_questions = len(set(e['bot'] for e in questions))
        
        complete = len(questions) >= self.MIN_QUESTIONS and bots_with_questions >= self.MIN_BOTS_WITH_QUESTIONS
        
        if complete:
            logger.info(f"Discovery complete: {len(questions)} questions from {bots_with_questions} bots")
        
        return complete
    
    def _get_next_bot(self) -> str:
        """Get next bot to ask a question (round-robin).
        
        Returns:
            Name of the next bot to ask a question
        """
        log = self.state.discovery_log
        bots = self.state.suggested_bots or ["leader", "researcher", "creative"]
        
        asked = set(e['bot'] for e in log if e.get('is_question', True))
        
        for bot in bots:
            if bot not in asked:
                return bot
        
        return bots[0]
    
    def get_context(self, bot_name: str) -> str:
        """Get formatted context for a bot.
        
        Args:
            bot_name: Name of the bot to get context for
            
        Returns:
            Formatted context string
        """
        sections = [
            "# Project Context",
            "",
            f"## Phase: {self.state.phase.value.upper()}",
        ]
        
        if self.state.user_goal:
            sections.extend(["", f"## Goal", self.state.user_goal])
        
        if self.state.phase == ProjectPhase.DISCOVERY:
            sections.extend([
                "",
                "## Your Task",
                "Ask ONE clarifying question to understand the user's need.",
                "",
                "## Questions Already Asked"
            ])
            for entry in self.state.discovery_log:
                if entry.get('is_question', True):
                    sections.append(f"- @{entry['bot']}: {entry['content']}")
        
        elif self.state.phase == ProjectPhase.EXECUTION:
            next_steps = self.state.synthesis.get('next_steps', {}) if self.state.synthesis else {}
            if bot_name in next_steps:
                sections.extend(["", f"## Your Task", next_steps[bot_name]])
        
        return "\n".join(sections)
    
    def format_status(self) -> str:
        """Get human-readable status string."""
        lines = [
            f"Phase: {self.state.phase.value.upper()}",
            f"Iteration: {self.state.iteration}",
        ]
        
        if self.state.user_goal:
            lines.append(f"Goal: {self.state.user_goal[:50]}...")
        
        if self.state.discovery_log:
            questions = [e for e in self.state.discovery_log if e.get('is_question', True)]
            lines.append(f"Questions: {len(questions)}")
        
        if self.state.phase != ProjectPhase.IDLE:
            elapsed = (datetime.now() - self.state.updated_at).total_seconds() / 60
            lines.append(f"Last activity: {elapsed:.0f}m ago")
        
        return "\n".join(lines)


def get_project_state_manager(workspace: Path, room_id: str) -> ProjectStateManager:
    """Get ProjectStateManager instance.
    
    Args:
        workspace: Workspace directory
        room_id: Room identifier
        
    Returns:
        ProjectStateManager instance
    """
    return ProjectStateManager(workspace, room_id)
