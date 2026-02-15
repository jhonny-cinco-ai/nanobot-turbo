"""Base class for all specialist bots with heartbeat support."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from loguru import logger

from nanobot.models.role_card import RoleCard
from nanobot.models.room import Room
from nanobot.themes import ThemeManager, get_theme


class SpecialistBot(ABC):
    """Abstract base class for all bot implementations with autonomous heartbeat.
    
    Each bot runs its own independent heartbeat with:
    - Role-specific periodic checks
    - Domain-optimized intervals
    - Autonomous task execution
    - Self-managed state
    """

    def __init__(
        self,
        role_card: RoleCard,
        bus=None,
        workspace_id: Optional[str] = None,
        theme_manager: Optional[ThemeManager] = None,
        custom_name: Optional[str] = None
    ):
        """Initialize a bot with a role card.
        
        Args:
            role_card: Role card defining bot's personality and constraints
            bus: InterBotBus for communication with coordinator
            workspace_id: Workspace context ID
            theme_manager: Optional theme manager for applying themed display names
            custom_name: Optional custom display name (overrides theme)
        """
        self.role_card = role_card
        self.bus = bus
        self.workspace_id = workspace_id
        self._theme_manager = theme_manager
        self.private_memory: Dict[str, Any] = {
            "learnings": [],  # Lessons learned by this bot
            "expertise_domains": [],  # Domains where bot is competent
            "mistakes": [],  # Errors and how they were recovered
            "confidence": 0.7,  # Self-assessed competence (0.0-1.0)
            "created_at": datetime.now().isoformat(),
            "heartbeat_history": [],  # History of heartbeat executions
        }
        
        # Apply theme if available
        if theme_manager and theme_manager.current_theme:
            self._apply_theme_to_role_card()
        
        # Apply custom name if provided (highest priority)
        if custom_name:
            self.set_display_name(custom_name)
        
        # Heartbeat service (initialized lazily)
        self._heartbeat = None
        self._heartbeat_config = None
    
    def _create_tool_registry(self, workspace: "Path | None" = None):
        """Create a tool registry for this bot based on permissions.
        
        Args:
            workspace: Path to workspace
            
        Returns:
            ToolRegistry configured for this bot, or None if no workspace
        """
        if not workspace:
            return None
        
        from nanobot.agent.tools.factory import create_bot_registry
        
        return create_bot_registry(
            workspace=workspace,
            bot_name=self.role_card.bot_name,
        )

    def _apply_theme_to_role_card(self) -> None:
        """Apply current theme to role card display name and personality."""
        if not self._theme_manager or not self._theme_manager.current_theme:
            return
        
        try:
            theming = self._theme_manager.get_bot_theming(self.role_card.bot_name)
            if theming:
                # Update display name from theme (use title as default display name)
                title = theming.get("title")
                if title:
                    self.role_card.set_display_name(title)
                    logger.debug(
                        f"[{self.role_card.bot_name}] Applied theme display name: {title}"
                    )
                
                # Update greeting if theme provides one
                if theming.get("greeting"):
                    self.role_card.greeting = theming["greeting"]
                
                # Update voice if theme provides one
                if theming.get("voice"):
                    self.role_card.voice = theming["voice"]
                    
        except Exception as e:
            logger.warning(f"[{self.role_card.bot_name}] Failed to apply theme: {e}")

    @property
    def name(self) -> str:
        """Get bot name."""
        return self.role_card.bot_name

    @property
    def domain(self) -> str:
        """Get bot domain."""
        return self.role_card.domain.value

    @property
    def title(self) -> str:
        """Get bot title."""
        return self.role_card.title

    @property
    def display_name(self) -> str:
        """Get bot display name (user-customizable).
        
        Returns:
            Display name (falls back to title if not set)
        """
        return self.role_card.get_display_name()

    def set_display_name(self, name: str) -> None:
        """Set a custom display name for this bot.
        
        Args:
            name: Custom display name (e.g., "Blackbeard", "Slash", "Neo")
        """
        old_name = self.display_name
        self.role_card.set_display_name(name)
        logger.info(
            f"[{self.role_card.bot_name}] Display name changed: "
            f"'{old_name}' → '{self.display_name}'"
        )

    def reset_display_name(self) -> None:
        """Reset display name to default (uses title or themed name)."""
        self.role_card.set_display_name("")
        # Re-apply theme if available
        if self._theme_manager and self._theme_manager.current_theme:
            self._apply_theme_to_role_card()

    def can_perform_action(self, action: str) -> tuple[bool, Optional[str]]:
        """Validate if bot can perform an action (check hard bans).
        
        Args:
            action: Action description
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        return self.role_card.validate_action(action)

    def get_greeting(self, workspace: Optional[Workspace] = None) -> str:
        """Get bot's greeting for a workspace.
        
        Args:
            workspace: Workspace context (optional)
            
        Returns:
            Greeting message
        """
        return self.role_card.greeting

    def record_learning(self, lesson: str, confidence: float = 0.7) -> None:
        """Record a private learning.
        
        Args:
            lesson: What was learned
            confidence: How confident in this learning (0.0-1.0)
        """
        self.private_memory["learnings"].append({
            "lesson": lesson,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })

    def record_mistake(self, error: str, recovery: str, lesson: Optional[str] = None) -> None:
        """Record a mistake and how it was recovered.
        
        Args:
            error: What went wrong
            recovery: How the error was fixed
            lesson: Optional lesson learned
        """
        record = {
            "error": error,
            "recovery": recovery,
            "timestamp": datetime.now().isoformat(),
        }
        if lesson:
            record["lesson"] = lesson
        
        self.private_memory["mistakes"].append(record)

    def add_expertise(self, domain: str) -> None:
        """Add a domain to bot's expertise.
        
        Args:
            domain: Domain name
        """
        if domain not in self.private_memory["expertise_domains"]:
            self.private_memory["expertise_domains"].append(domain)

    def update_confidence(self, delta: float) -> None:
        """Update bot's confidence level.
        
        Args:
            delta: Change in confidence (-1.0 to 1.0)
        """
        current = self.private_memory["confidence"]
        new_confidence = max(0.0, min(1.0, current + delta))
        self.private_memory["confidence"] = new_confidence

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of bot's status and learnings.
        
        Returns:
            Summary dictionary
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "domain": self.domain,
            "title": self.title,
            "learnings_count": len(self.private_memory["learnings"]),
            "mistakes_count": len(self.private_memory["mistakes"]),
            "expertise_domains": self.private_memory["expertise_domains"],
            "confidence": self.private_memory["confidence"],
            "created_at": self.private_memory["created_at"],
            "heartbeat_running": self.is_heartbeat_running,
        }

    # ==================================================================
    # Heartbeat Methods
    # ==================================================================

    def initialize_heartbeat(
        self,
        config=None,
        workspace=None,
        provider=None,
        routing_config=None,
        reasoning_config=None,
        work_log_manager=None,
        on_heartbeat=None,
        on_tick_complete: Optional[Callable] = None,
        on_check_complete: Optional[Callable] = None,
        tool_registry=None,
    ) -> None:
        """Initialize bot's autonomous heartbeat.
        
        Args:
            config: Heartbeat configuration (uses default if None)
            workspace: Path to bot's workspace (for HEARTBEAT.md)
            provider: LLM provider for heartbeat execution
            routing_config: Smart routing config for model selection
            reasoning_config: Reasoning/CoT settings for this bot
            work_log_manager: Work log manager for logging heartbeat events
            on_heartbeat: Callback to execute HEARTBEAT.md tasks via LLM
            on_tick_complete: Callback when tick completes
            on_check_complete: Callback when individual check completes
            tool_registry: Optional tool registry for tool execution during heartbeat
        """
        if config is None:
            # Load default config for this bot type
            from nanobot.bots.heartbeat_configs import get_bot_heartbeat_config
            config = get_bot_heartbeat_config(self.role_card.bot_name)
        
        self._heartbeat_config = config
        
        # Import here to avoid circular imports
        from nanobot.heartbeat.bot_heartbeat import BotHeartbeatService
        
        # Wrap callbacks to include bot context
        def tick_callback(tick):
            self._on_heartbeat_tick_complete(tick)
            if on_tick_complete:
                on_tick_complete(tick)
        
        def check_callback(result):
            self._on_check_complete(result)
            if on_check_complete:
                on_check_complete(result)
        
        self._heartbeat = BotHeartbeatService(
            bot_instance=self,
            config=config,
            workspace=workspace,
            provider=provider,
            routing_config=routing_config,
            reasoning_config=reasoning_config,
            work_log_manager=work_log_manager,
            on_heartbeat=on_heartbeat,
            on_tick_complete=tick_callback,
            on_check_complete=check_callback,
            tool_registry=tool_registry,
        )
        
        logger.info(
            f"[{self.role_card.bot_name}] Heartbeat initialized: "
            f"{config.interval_s}s interval, {len(config.checks)} checks"
        )

    async def start_heartbeat(self) -> None:
        """Start bot's independent heartbeat."""
        if self._heartbeat is None:
            # Auto-initialize with defaults
            self.initialize_heartbeat()
        
        if self._heartbeat:
            await self._heartbeat.start()

    def stop_heartbeat(self) -> None:
        """Stop bot's heartbeat."""
        if self._heartbeat:
            self._heartbeat.stop()

    @property
    def is_heartbeat_running(self) -> bool:
        """Check if heartbeat is currently running."""
        return self._heartbeat is not None and self._heartbeat.is_running

    def get_heartbeat_status(self) -> Dict[str, Any]:
        """Get current heartbeat status."""
        if self._heartbeat:
            return self._heartbeat.get_status()
        return {"running": False, "bot_name": self.role_card.bot_name}

    async def trigger_heartbeat_now(self, reason: str = "manual"):
        """Manually trigger a heartbeat tick.
        
        Args:
            reason: Why heartbeat is being triggered
            
        Returns:
            HeartbeatTick result
        """
        if self._heartbeat is None:
            self.initialize_heartbeat()
        
        if self._heartbeat is not None:
            return await self._heartbeat.trigger_now(reason)
        return None

    def _on_heartbeat_tick_complete(self, tick) -> None:
        """Internal handler for tick completion.
        
        Records to bot's private memory and logs learning.
        """
        # Record to private memory
        tick_summary = {
            "tick_id": tick.tick_id,
            "timestamp": tick.started_at.isoformat(),
            "status": tick.status,
            "success_rate": tick.get_success_rate(),
            "failed_checks": [r.check_name for r in tick.get_failed_checks()],
        }
        
        self.private_memory["heartbeat_history"].append(tick_summary)
        
        # Trim history if too long
        max_history = tick.config.retain_history_count if tick.config else 100
        if len(self.private_memory["heartbeat_history"]) > max_history:
            self.private_memory["heartbeat_history"] = self.private_memory["heartbeat_history"][-max_history:]
        
        # Record learning
        success_rate = tick.get_success_rate()
        if success_rate >= 0.9:
            self.record_learning(
                lesson=f"Heartbeat tick {tick.tick_id} completed with {success_rate:.0%} success",
                confidence=0.9
            )
        elif success_rate < 0.5:
            self.record_mistake(
                error=f"Heartbeat tick {tick.tick_id} had low success rate: {success_rate:.0%}",
                recovery="Review failed checks and adjust configuration"
            )

    def _on_check_complete(self, result) -> None:
        """Internal handler for check completion."""
        # Log check completion
        if result.success:
            logger.debug(
                f"[{self.role_card.bot_name}] Check '{result.check_name}' completed successfully"
            )
        else:
            logger.warning(
                f"[{self.role_card.bot_name}] Check '{result.check_name}' failed: {result.error}"
            )

    # ==================================================================
    # Communication with Coordinator
    # ==================================================================

    async def notify_coordinator(
        self,
        message: str,
        priority: str = "normal",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Notify coordinator of heartbeat finding.
        
        Args:
            message: Notification message
            priority: Priority level (low/normal/high/critical)
            data: Additional data to include
            
        Returns:
            True if notification sent successfully
        """
        if self.bus is None:
            logger.warning(f"[{self.role_card.bot_name}] No bus available for notification")
            return False
        
        try:
            # Create notification payload
            notification = {
                "sender": self.role_card.bot_name,
                "recipient": "coordinator",
                "type": "notification",
                "message": message,
                "priority": priority,
                "data": data or {},
                "source": "heartbeat",
                "timestamp": datetime.now().isoformat()
            }
            
            # Send via bus if available
            if hasattr(self.bus, 'send_message'):
                self.bus.send_message(notification)
            
            logger.info(f"[{self.role_card.bot_name}] Notified coordinator: {message}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.role_card.bot_name}] Failed to notify coordinator: {e}")
            return False

    async def escalate_to_coordinator(
        self,
        message: str,
        priority: str = "high",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Escalate issue to coordinator for human attention.
        
        Args:
            message: Escalation message
            priority: Priority level
            data: Supporting data
            
        Returns:
            True if escalation sent successfully
        """
        return await self.notify_coordinator(
            message=f"[ESCALATION] {message}",
            priority=priority,
            data=data
        )

    @abstractmethod
    async def process_message(self, message: str, workspace: Workspace) -> str:
        """Process a message and generate response.
        
        This is the main interaction method for the bot.
        
        Args:
            message: User or system message
            workspace: Workspace context
            
        Returns:
            Bot's response message
        """
        pass

    @abstractmethod
    async def execute_task(self, task: str, workspace: Workspace) -> Dict[str, Any]:
        """Execute a specific task.
        
        This is for structured task execution (not conversational).
        
        Args:
            task: Task description
            workspace: Workspace context
            
        Returns:
            Task result dictionary
        """
        pass
