"""Base class for all specialist bots with team routines support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from loguru import logger

from nanofolks.models.role_card import RoleCard
from nanofolks.teams import TeamManager

if TYPE_CHECKING:
    from nanofolks.teams.workspace import Workspace


class SpecialistBot(ABC):
    """Abstract base class for all bot implementations with autonomous team routines.

    Each bot runs its own independent team routines with:
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
        team_manager: Optional[TeamManager] = None,
        custom_name: Optional[str] = None,
        workspace_path: Optional["Path"] = None
    ):
        """Initialize a bot with a role card.

        Args:
            role_card: Role card defining bot's personality and constraints
            bus: InterBotBus for communication with coordinator
            workspace_id: Workspace context ID
            team_manager: Optional team manager for applying team-styled display names
            custom_name: Optional custom display name (overrides team style)
            workspace_path: Path to workspace for DM room logging
        """
        self.role_card = role_card
        self.bus = bus
        self.workspace_id = workspace_id
        self._workspace_path = workspace_path
        self._team_manager = team_manager
        self.private_memory: Dict[str, Any] = {
            "learnings": [],  # Lessons learned by this bot
            "expertise_domains": [],  # Domains where bot is competent
            "mistakes": [],  # Errors and how they were recovered
            "confidence": 0.7,  # Self-assessed competence (0.0-1.0)
            "created_at": datetime.now().isoformat(),
            "team_routines_history": [],  # History of team routines executions
        }

        # Persistent learning manager — injected by gateway via set_learning_manager().
        # When set, record_learning() writes to TurboMemoryStore in addition to
        # private_memory, making observations visible to ContextAssembler.
        self._learning_manager: Optional[Any] = None

        # Apply team styling if available
        if team_manager and team_manager.current_team:
            self._apply_team_to_role_card()

        # Apply custom name if provided (highest priority)
        if custom_name:
            self.set_display_name(custom_name)

        # team routines service (initialized lazily)
        self._team_routines = None
        self._team_routines_config = None

    @property
    def workspace(self) -> Optional["Path"]:
        """Get workspace path."""
        return self._workspace_path

    @workspace.setter
    def workspace(self, path: "Path"):
        """Set workspace path."""
        self._workspace_path = path

    def _create_tool_registry(self, workspace: "Path | None" = None):
        """Create a tool registry for this bot based on permissions.

        Args:
            workspace: Path to workspace

        Returns:
            ToolRegistry configured for this bot, or None if no workspace
        """
        if not workspace:
            return None

        from nanofolks.agent.tools.factory import create_bot_registry

        return create_bot_registry(
            workspace=workspace,
            bot_name=self.role_card.bot_name,
        )

    def _apply_team_to_role_card(self) -> None:
        """Apply current team style to role card display name and personality."""
        if not self._team_manager or not self._team_manager.current_team:
            return

        try:
            profile = self._team_manager.get_bot_team_profile(
                self.role_card.bot_name, workspace_path=self._workspace_path
            )
            if profile:
                # Update display name from team profile (use title as default display name)
                title = profile.bot_title
                if title:
                    self.role_card.set_display_name(title)
                    logger.debug(
                        f"[{self.role_card.bot_name}] Applied team display name: {title}"
                    )

                # Update greeting if team profile provides one
                if profile.greeting:
                    self.role_card.greeting = profile.greeting

                # Update voice if team profile provides one
                if profile.voice:
                    self.role_card.voice = profile.voice

        except Exception as e:
            logger.warning(f"[{self.role_card.bot_name}] Failed to apply team styling: {e}")

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
        """Reset display name to default (uses title or team-styled name)."""
        self.role_card.set_display_name("")
        # Re-apply team styling if available
        if self._team_manager and self._team_manager.current_team:
            self._apply_team_to_role_card()

    def can_perform_action(self, action: str, context: Optional[Dict] = None) -> tuple[bool, Optional[str]]:
        """Validate if bot can perform an action (check hard bans).

        Args:
            action: Action description
            context: Additional context about the action (tool name, parameters, etc.)

        Returns:
            Tuple of (is_allowed, error_message)
        """
        return self.role_card.check_hard_bans(action, context)

    def get_greeting(self, workspace: Optional[Workspace] = None) -> str:
        """Get bot's greeting for a workspace.

        Args:
            workspace: Workspace context (optional)

        Returns:
            Greeting message
        """
        return self.role_card.greeting

    def set_learning_manager(self, manager: Any) -> None:
        """Inject a shared LearningManager for persistent storage.

        When set, every call to record_learning() will also write the
        observation to TurboMemoryStore via the manager, making it
        visible to ContextAssembler.assemble_context().

        Args:
            manager: LearningManager instance (from nanofolks.memory.learning)
        """
        self._learning_manager = manager
        logger.debug(
            f"[{self.role_card.bot_name}] LearningManager injected for persistent storage"
        )

    def record_learning(self, lesson: str, confidence: float = 0.7) -> None:
        """Record a private learning — in-memory and, if a manager is
        available, also persist to TurboMemoryStore.

        Args:
            lesson: What was learned
            confidence: How confident in this learning (0.0-1.0)
        """
        entry = {
            "lesson": lesson,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        }
        self.private_memory["learnings"].append(entry)

        # Persist to the shared store when a LearningManager has been injected.
        # We schedule this as a fire-and-forget task so we never block the
        # team routines tick that called us.
        if self._learning_manager is not None:
            try:
                import asyncio
                from datetime import datetime as _dt
                from uuid import uuid4 as _uuid4

                from nanofolks.memory.models import Learning

                now = _dt.now()
                learning_obj = Learning(
                    id=str(_uuid4()),
                    content=lesson,
                    source=f"team_routines:{self.role_card.bot_name}",
                    sentiment="neutral",
                    confidence=confidence,
                    recommendation=None,
                    superseded_by=None,
                    content_embedding=None,
                    created_at=now,
                    updated_at=now,
                    relevance_score=1.0,
                    times_accessed=0,
                    last_accessed=None,
                )

                async def _flush(manager, obj, bot_name):
                    try:
                        # store.create_learning() is synchronous (SQLite)
                        manager.store.create_learning(obj)
                    except Exception as exc:
                        logger.debug(
                            f"[{bot_name}] Learning persistence skipped: {exc}"
                        )

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        _flush(
                            self._learning_manager,
                            learning_obj,
                            self.role_card.bot_name,
                        )
                    )
            except Exception:
                pass  # Never block team routines

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
            "team_routines_running": self.is_team_routines_running,
        }

    async def get_recent_handoffs(self, limit: int = 20, room_id: Optional[str] = None):
        """Get recent handoffs from the shared work log."""
        try:
            from nanofolks.agent import get_work_log_manager

            manager = get_work_log_manager()
            return manager.get_recent_handoffs(limit=limit, workspace_id=room_id)
        except Exception as e:
            logger.debug(f"[{self.role_card.bot_name}] Handoff lookup failed: {e}")
            return []

    # ==================================================================
    # team routines Methods
    # ==================================================================

    def initialize_team_routines(
        self,
        config=None,
        workspace=None,
        provider=None,
        routing_config=None,
        reasoning_config=None,
        work_log_manager=None,
        on_team_routines=None,
        on_tick_complete: Optional[Callable] = None,
        on_check_complete: Optional[Callable] = None,
        tool_registry=None,
    ) -> None:
        """Initialize bot's autonomous team routines.

        Args:
            config: team routines configuration (uses default if None)
            workspace: Path to bot's workspace (for TEAM_ROUTINES.md)
            provider: LLM provider for team routines execution
            routing_config: Smart routing config for model selection
            reasoning_config: Reasoning/CoT settings for this bot
            work_log_manager: Work log manager for logging team routines events
            on_team_routines: Callback to execute TEAM_ROUTINES.md tasks via LLM
            on_tick_complete: Callback when tick completes
            on_check_complete: Callback when individual check completes
            tool_registry: Optional tool registry for tool execution during team routines
        """
        if config is None:
            # Load default config for this bot type
            from nanofolks.bots.team_routines_configs import get_bot_team_routines_config
            config = get_bot_team_routines_config(self.role_card.bot_name)

        self._team_routines_config = config

        # Import here to avoid circular imports
        from nanofolks.routines.team.bot_team_routines import BotTeamRoutinesService

        # Wrap callbacks to include bot context
        def tick_callback(tick):
            self._on_team_routines_tick_complete(tick)
            if on_tick_complete:
                on_tick_complete(tick)

        def check_callback(result):
            self._on_check_complete(result)
            if on_check_complete:
                on_check_complete(result)

        self._team_routines = BotTeamRoutinesService(
            bot_instance=self,
            config=config,
            workspace=workspace,
            provider=provider,
            routing_config=routing_config,
            reasoning_config=reasoning_config,
            work_log_manager=work_log_manager,
            on_team_routines=on_team_routines,
            on_tick_complete=tick_callback,
            on_check_complete=check_callback,
            tool_registry=tool_registry,
        )

        logger.info(
            f"[{self.role_card.bot_name}] team routines initialized: "
            f"{config.interval_s}s interval, {len(config.checks)} checks"
        )

    async def start_team_routines(self) -> None:
        """Start bot's independent team routines."""
        if self._team_routines is None:
            # Auto-initialize with defaults
            self.initialize_team_routines()

        if self._team_routines:
            await self._team_routines.start()

    def stop_team_routines(self) -> None:
        """Stop bot's team routines."""
        if self._team_routines:
            self._team_routines.stop()

    @property
    def is_team_routines_running(self) -> bool:
        """Check if team routines are currently running."""
        return self._team_routines is not None and self._team_routines.is_running

    def get_team_routines_status(self) -> Dict[str, Any]:
        """Get current team routines status."""
        if self._team_routines:
            return self._team_routines.get_status()
        return {"running": False, "bot_name": self.role_card.bot_name}

    async def trigger_team_routines_now(self, reason: str = "manual"):
        """Manually trigger a team routines tick.

        Args:
            reason: Why team routines are being triggered

        Returns:
            TeamRoutinesTick result
        """
        if self._team_routines is None:
            self.initialize_team_routines()

        if self._team_routines is not None:
            return await self._team_routines.trigger_now(reason)
        return None

    def _on_team_routines_tick_complete(self, tick) -> None:
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

        self.private_memory["team_routines_history"].append(tick_summary)

        # Trim history if too long
        max_history = tick.config.retain_history_count if tick.config else 100
        if len(self.private_memory["team_routines_history"]) > max_history:
            self.private_memory["team_routines_history"] = self.private_memory["team_routines_history"][-max_history:]

        # Record learning
        success_rate = tick.get_success_rate()
        if success_rate >= 0.9:
            self.record_learning(
                lesson=f"TeamRoutines tick {tick.tick_id} completed with {success_rate:.0%} success",
                confidence=0.9
            )
        elif success_rate < 0.5:
            self.record_mistake(
                error=f"TeamRoutines tick {tick.tick_id} had low success rate: {success_rate:.0%}",
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
        """Notify coordinator of team routines finding.

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
                "source": "team_routines",
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

    async def send_message_to_bot(
        self,
        recipient_bot: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        expect_reply: bool = False,
        timeout_seconds: int = 60
    ) -> tuple[bool, Optional[str]]:
        """Send a direct message to another specialist bot.

        This enables bot-to-bot communication for simple queries without
        going through the Leader. Use this for:
        - Quick questions ("What's the coding standard for X?")
        - Information requests ("Do you have data on Y?")
        - Clarifications ("Can you verify this fact?")

        For complex coordination or task delegation, use notify_coordinator()
        or ask Leader to invoke the bot.

        Messages are logged to direct rooms for transparency - users can peek
        into bot-to-bot conversations.

        Args:
            recipient_bot: Name of target bot (e.g., "coder", "researcher")
            message: Message content
            context: Additional context data
            expect_reply: Whether to wait for a response
            timeout_seconds: How long to wait for reply (if expect_reply=True)

        Returns:
            Tuple of (success, reply_message or None)
            If expect_reply=False: (True, None) on success, (False, None) on failure
            If expect_reply=True: (True, reply) on success, (False, error) on failure/timeout
        """
        # Log to DM room for transparency (before sending)
        try:
            from nanofolks.bots.room_manager import get_room_manager
            msg_type = "query" if expect_reply else "info"
            get_room_manager().log_dm_message(
                sender_bot=self.role_card.bot_name,
                recipient_bot=recipient_bot,
                content=message,
                message_type=msg_type,
                context=context,
            )
        except Exception as e:
            logger.debug(f"[{self.role_card.bot_name}] DM log failed: {e}")

        if self.bus is None:
            logger.warning(f"[{self.role_card.bot_name}] No bus available for messaging")
            return False, "No message bus available"

        try:
            import uuid

            from nanofolks.coordinator.models import BotMessage, MessageType

            # Create message
            bot_message = BotMessage(
                id=str(uuid.uuid4()),
                sender_id=self.role_card.bot_name,
                recipient_id=recipient_bot,
                type=MessageType.QUERY if expect_reply else MessageType.INFO,
                content=message,
                context=context or {},
                conversation_id=context.get("conversation_id") if context else None
            )

            # Send message
            message_id = self.bus.send_message(bot_message)

            logger.info(
                f"[{self.role_card.bot_name}] Sent message to @{recipient_bot}: "
                f"{message[:50]}..."
            )

            if not expect_reply:
                return True, None

            # Wait for reply
            import asyncio
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                # Check inbox for reply
                inbox = self.bus.get_inbox(self.role_card.bot_name)

                # Look for reply to our message
                for msg in reversed(inbox):
                    if (msg.sender_id == recipient_bot and
                        msg.context.get("reply_to") == message_id):
                        logger.info(
                            f"[{self.role_card.bot_name}] Received reply from @{recipient_bot}"
                        )

                        # Log reply to DM room for transparency
                        try:
                            from nanofolks.bots.room_manager import get_room_manager
                            get_room_manager().log_dm_message(
                                sender_bot=recipient_bot,
                                recipient_bot=self.role_card.bot_name,
                                content=msg.content,
                                message_type="response",
                                context={"reply_to": message_id},
                                reply_to=message_id,
                            )
                        except Exception as e:
                            logger.debug(f"[{self.role_card.bot_name}] DM reply log failed: {e}")

                        return True, msg.content

                await asyncio.sleep(0.5)  # Check every 500ms

            # Timeout
            logger.warning(
                f"[{self.role_card.bot_name}] Timeout waiting for reply from @{recipient_bot}"
            )
            return False, f"Timeout waiting for reply from @{recipient_bot}"

        except Exception as e:
            logger.error(f"[{self.role_card.bot_name}] Failed to send message to @{recipient_bot}: {e}")
            return False, str(e)

    async def ask_bot(
        self,
        recipient_bot: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 60
    ) -> tuple[bool, Optional[str]]:
        """Ask another bot a question and wait for answer.

        Convenience wrapper around send_message_to_bot() that always
        expects a reply.

        Args:
            recipient_bot: Name of bot to ask (e.g., "coder", "researcher")
            question: The question to ask
            context: Additional context
            timeout_seconds: How long to wait for answer

        Returns:
            Tuple of (success, answer or error_message)

        Example:
            success, answer = await social_bot.ask_bot(
                "coder",
                "What are our Python naming conventions?"
            )
            if success:
                print(f"Coder said: {answer}")
        """
        return await self.send_message_to_bot(
            recipient_bot=recipient_bot,
            message=question,
            context=context,
            expect_reply=True,
            timeout_seconds=timeout_seconds
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
