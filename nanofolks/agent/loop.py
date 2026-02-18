"""Agent loop: the core processing engine."""

import asyncio
from contextlib import AsyncExitStack
import json
import json_repair
from pathlib import Path
from typing import Any

from loguru import logger

from nanofolks.bus.events import InboundMessage, OutboundMessage
from nanofolks.security.sanitizer import SecretSanitizer, mask_logs
from nanofolks.bus.queue import MessageBus
from nanofolks.providers.base import LLMProvider
from nanofolks.agent.context import ContextBuilder
from nanofolks.agent.tools.registry import ToolRegistry
from nanofolks.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanofolks.agent.tools.shell import ExecTool
from nanofolks.agent.tools.web import WebSearchTool, WebFetchTool
from nanofolks.agent.tools.message import MessageTool
from nanofolks.agent.tools.cron import CronTool
from nanofolks.agent.tools.update_config import UpdateConfigTool
from nanofolks.agent.stages import RoutingStage, RoutingContext
from nanofolks.config.schema import RoutingConfig
from nanofolks.session.manager import Session
from nanofolks.session.dual_mode import create_session_manager
from nanofolks.agent.work_log_manager import get_work_log_manager, LogLevel
from nanofolks.agent.work_log import RoomType
from nanofolks.reasoning.config import get_reasoning_config, ReasoningConfig
from nanofolks.teams import TeamManager


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        system_timezone: str = "UTC",
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        routing_config: RoutingConfig | None = None,
        evolutionary: bool = False,
        allowed_paths: list[str] | None = None,
        protected_paths: list[str] | None = None,
        memory_config: "MemoryConfig | None" = None,
        bot_name: str = "leader",
        mcp_servers: dict | None = None,
    ):
        from nanofolks.config.schema import ExecToolConfig
        from nanofolks.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.workspace_id = str(workspace)  # For Learning Exchange
        self.bot_name = bot_name  # Identity of this bot (leader is the leader)
        
        # Initialize reasoning configuration for this bot
        self.reasoning_config = get_reasoning_config(self.bot_name)
        logger.debug(f"Loaded reasoning config for {self.bot_name}: {self.reasoning_config.cot_level.value}")
        
        # Initialize current tier for CoT decisions (set by _select_model)
        self._current_tier = "medium"
        
        # Room context for multi-agent collaboration
        self._current_room_id: str = "general"
        self._current_room_type: str = "open"
        self._current_room_participants: list[str] = ["leader"]
        
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.system_timezone = system_timezone
        self.restrict_to_workspace = restrict_to_workspace
        self.evolutionary = evolutionary
        self.allowed_paths = allowed_paths or []
        self.protected_paths = protected_paths or []
        
        # Initialize secret sanitizer for security
        self.sanitizer = SecretSanitizer()
        
        self.context = ContextBuilder(workspace)
        
        # Initialize session manager (dual-mode with room-centric support)
        if session_manager:
            self.sessions = session_manager
        else:
            # Load config for session manager settings
            try:
                from nanofolks.config.loader import load_config
                config = load_config()
            except Exception:
                config = None
            self.sessions = create_session_manager(workspace, config)
        
        self.tools = ToolRegistry()
        
        # Initialize smart router if enabled
        self.routing_config = routing_config
        self.routing_stage = None
        if routing_config and routing_config.enabled:
            self.routing_stage = RoutingStage(
                config=routing_config,
                provider=provider,
                workspace=workspace,
                cron_service=cron_service,  # Pass cron to check for scheduled calibration
            )
            logger.info("Smart routing enabled")
        
        # Initialize memory system if enabled
        self.memory_config = memory_config  # Store for later access
        self.memory_store = None
        self.activity_tracker = None
        self.background_processor = None
        self.memory_retrieval = None
        self.context_assembler = None
        self.summary_manager = None
        self.preferences_aggregator = None
        self.session_compactor = None
        
        if memory_config and memory_config.enabled:
            from nanofolks.memory.store import TurboMemoryStore
            from nanofolks.memory.background import ActivityTracker, BackgroundProcessor
            from nanofolks.memory.summaries import SummaryTreeManager, create_summary_manager
            from nanofolks.memory.context import ContextAssembler, create_context_assembler
            from nanofolks.memory.retrieval import MemoryRetrieval, create_retrieval
            from nanofolks.memory.embeddings import EmbeddingProvider
            
            self.memory_store = TurboMemoryStore(memory_config, workspace)
            
            # Initialize activity tracker for background processing
            self.activity_tracker = ActivityTracker(
                quiet_threshold_seconds=memory_config.background.quiet_threshold_seconds
            )
            
            # Initialize background processor
            self.background_processor = BackgroundProcessor(
                memory_store=self.memory_store,
                activity_tracker=self.activity_tracker,
                interval_seconds=memory_config.background.interval_seconds,
            )
            
            # Initialize summary manager
            self.summary_manager = create_summary_manager(
                self.memory_store,
                staleness_threshold=memory_config.summary.staleness_threshold,
                max_refresh_batch=memory_config.summary.max_refresh_batch,
            )
            
            # Initialize context assembler
            self.context_assembler = create_context_assembler(
                self.memory_store,
                self.summary_manager,
            )
            
            # Initialize memory retrieval with embeddings
            embedding_provider = None
            if memory_config.embedding.provider == "local":
                embedding_provider = EmbeddingProvider(memory_config.embedding)
            
            self.memory_retrieval = create_retrieval(
                self.memory_store,
                embedding_provider=embedding_provider,
            )
            
            # Initialize Learning Exchange (Phase 6 persistence and distribution)
            from nanofolks.agent.learning_exchange import LearningExchange
            
            self.learning_exchange = LearningExchange(
                bot_name=self.bot_name,
                workspace_id=self.workspace_id,
            )
            
            # Load any pending packages from previous sessions
            pending_count = self.learning_exchange.load_pending_packages()
            if pending_count > 0:
                logger.info(f"Loaded {pending_count} pending learning packages from previous sessions")
            
            # Initialize learning manager (Phase 6) with Learning Exchange
            from nanofolks.memory.learning import create_learning_manager
            from nanofolks.memory.preferences import create_preferences_aggregator
            
            self.learning_manager = create_learning_manager(
                self.memory_store,
                embedding_provider=embedding_provider,
                decay_days=memory_config.learning.decay_days,
                decay_rate=memory_config.learning.relevance_decay_rate,
                exchange=self.learning_exchange,
                bot_name=self.bot_name,
            )
            
            # Register this bot to receive learning packages from the exchange
            async def receive_distributed_learning(package):
                """Callback to receive distributed learning packages."""
                if self.learning_manager:
                    learning = self.learning_exchange.receive_learning_package(
                        package, self.memory_store
                    )
                    if learning:
                        logger.debug(
                            f"Received learning from exchange: {learning.id} "
                            f"({package.category.value})" 
                        )
                    return learning is not None
                return False
            
            self.learning_exchange.register_distribution_callback(
                self.bot_name,
                receive_distributed_learning
            )
            
            # Initialize preferences aggregator
            self.preferences_aggregator = create_preferences_aggregator(
                self.memory_store,
                self.summary_manager,
            )
            
            # Initialize session compactor (Phase 8) - Long conversation support
            from nanofolks.memory.session_compactor import SessionCompactionConfig, SessionCompactor, SUMMARY_PROMPT
            
            async def summarize_messages(messages: list[dict[str, Any]]) -> str:
                """LLM-based summarization for session compaction."""
                # Format messages for the prompt
                formatted = []
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content_str = "".join(
                            b.get("text", "") for b in content if isinstance(b, dict)
                        )
                    else:
                        content_str = str(content)[:200]  # Truncate long content
                    formatted.append(f"{role}: {content_str}")
                
                prompt = SUMMARY_PROMPT.format(messages="\n".join(formatted[-10:]))  # Last 10 msgs
                
                try:
                    response = await self.provider.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model=self.model,
                        temperature=0.3,
                        max_tokens=150,
                    )
                    return response.content or ""
                except Exception as e:
                    logger.warning(f"Summarization failed: {e}")
                    return ""
            
            self.session_compactor = SessionCompactor(
                memory_config.session_compaction,
                summarizer=summarize_messages
            )
            
            logger.info(
                f"Memory system enabled with learning, context assembly, and retrieval. "
                f"Session compaction: {memory_config.session_compaction.mode} mode"
            )
        
        # Initialize work log manager for transparency
        self.work_log_manager = get_work_log_manager()
        
        # Initialize bot invoker for delegating to specialist bots
        from nanofolks.agent.bot_invoker import BotInvoker
        self.bot_invoker = BotInvoker(
            provider=provider,
            workspace=workspace,
            bus=bus,
            work_log_manager=self.work_log_manager,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            evolutionary=evolutionary,
            allowed_paths=allowed_paths,
            protected_paths=protected_paths,
        )
        
        # Initialize hybrid flow router for Phase 2 intent detection
        self.hybrid_router = None
        self._hybrid_router_enabled = True  # Can be disabled via config if needed
        
        # Ensure theme is applied to nanobot SOUL on first agent start
        self._apply_theme_if_needed()
        
    def _init_chat_onboarding(self) -> None:
        """Initialize chat onboarding system."""
        self._chat_onboarding: "ChatOnboarding | None" = None
        
        # We'll initialize the actual ChatOnboarding when needed (lazy init)
        # to avoid circular imports and ensure workspace is ready
        logger.debug("Chat onboarding system initialized (lazy)")
    
    def _get_chat_onboarding(self, session: Session) -> "ChatOnboarding | None":
        """Get or create ChatOnboarding instance for this session."""
        from nanofolks.agent.chat_onboarding import ChatOnboarding  # Lazy import
        
        # Check if onboarding exists in session metadata
        onboarding_data = session.metadata.get("_chat_onboarding")
        
        if onboarding_data:
            # Restore from session
            self._chat_onboarding = ChatOnboarding.from_dict(
                onboarding_data,
                self.workspace,
                self._theme_manager
            )
        elif self._chat_onboarding is None:
            # Create new instance
            self._theme_manager = TeamManager()
            self._chat_onboarding = ChatOnboarding(
                workspace_path=self.workspace,
                theme_manager=self._theme_manager
            )
        
        return self._chat_onboarding
    
    def _save_chat_onboarding(self, session: Session) -> None:
        """Save onboarding state to session."""
        if self._chat_onboarding:
            session.metadata["_chat_onboarding"] = self._chat_onboarding.to_dict()
    
    def _check_onboarding_needed(self, session: Session) -> bool:
        """Check if first-time user needs onboarding."""
        # Check if onboarding already completed in this session
        onboarding_data = session.metadata.get("_chat_onboarding")
        if onboarding_data:
            from nanofolks.agent.chat_onboarding import OnboardingState
            state = onboarding_data.get("state")
            if state in [OnboardingState.COMPLETED.value, OnboardingState.TEAM_INTRO.value]:
                return False
        
        # If session already has messages, user is returning
        if session.messages and len(session.messages) > 2:
            return False
        
        # Check USER.md for placeholders
        user_file = self.workspace / "USER.md"
        if user_file.exists():
            content = user_file.read_text()
            placeholders = ["(your name)", "(your timezone)", "(your role)"]
            if not any(p in content for p in placeholders):
                return False
        
        return True
    
    async def _handle_chat_onboarding(
        self, msg: InboundMessage, session: Session
    ) -> OutboundMessage | None:
        """Handle conversational onboarding for first-time users."""
        from nanofolks.agent.chat_onboarding import ChatOnboarding, OnboardingState
        from nanofolks.teams import TeamManager
        
        # Initialize onboarding
        if not hasattr(self, "_chat_onboarding") or self._chat_onboarding is None:
            self._theme_manager = TeamManager()
            self._chat_onboarding = ChatOnboarding(
                workspace_path=self.workspace,
                theme_manager=self._theme_manager
            )
        
        onboarding = self._chat_onboarding
        user_message = msg.content.strip()
        
        # Check if this is a special command during onboarding
        cmd = user_message.lower()
        
        # Handle /help during onboarding
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐚 I'm getting to know you first! Answer a few questions "
                       "and I'll introduce you to the team. 😊"
            )
        
        # Handle "tell me about X" during onboarding
        if user_message.lower().startswith("tell me about "):
            bot_name = user_message.lower().replace("tell me about ", "").strip()
            # Map common names to bot roles
            bot_map = {
                "leader": "leader", "captain": "leader", "blackbeard": "leader",
                "researcher": "researcher", "navigator": "researcher",
                "coder": "coder", "builder": "coder", "quartermaster": "coder",
                "creative": "creative", "artist": "creative", "carpenter": "creative",
                "social": "social", "crewman": "social", "boatswain": "social",
                "auditor": "auditor", "logkeeper": "auditor", "scop": "auditor",
            }
            actual_bot = bot_map.get(bot_name, bot_name)
            if actual_bot in ["leader", "researcher", "coder", "creative", "social", "auditor"]:
                intro = onboarding.introduce_bot(actual_bot)
                return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=intro)
        
        # Check onboarding state
        if onboarding.state == OnboardingState.NOT_STARTED:
            # First message - start onboarding with greeting
            onboarding.state = OnboardingState.IN_PROGRESS
            first_question = onboarding.get_next_question()
            
            # Get leader greeting from theme
            team = self._theme_manager.get_current_team()
            greeting = team.leader.greeting if team else "Ahoy there!"
            
            response = f"{greeting} 🎉\n\nI'm excited to get to know you! "
            if first_question:
                response += first_question["question"]
            
            # Save state
            self._save_chat_onboarding(session)
            session.add_message("user", user_message)
            session.add_message("assistant", response)
            self.sessions.save(session)
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
                room_id=msg.room_id or self._current_room_id,
            )
        
        elif onboarding.state == OnboardingState.IN_PROGRESS:
            # Process answer and get next question
            response = onboarding.process_answer(user_message)
            
            # Check if we moved to team intro
            if onboarding.state == OnboardingState.TEAM_INTRO:
                # Save state and complete
                self._save_chat_onboarding(session)
                onboarding.complete()
                self._save_chat_onboarding(session)
            
            # Save to session
            session.add_message("user", user_message)
            session.add_message("assistant", response)
            self.sessions.save(session)
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
                room_id=msg.room_id or self._current_room_id,
            )
        
        elif onboarding.state == OnboardingState.TEAM_INTRO:
            # Handle questions about bots
            if user_message.lower().startswith("tell me about "):
                bot_name = user_message.lower().replace("tell me about ", "").strip()
                bot_map = {
                    "leader": "leader", "captain": "leader",
                    "researcher": "researcher", "navigator": "researcher",
                    "coder": "coder", "builder": "coder", "quartermaster": "coder",
                    "creative": "creative", "artist": "creative", "carpenter": "creative",
                    "social": "social", "crewman": "social", "boatswain": "social",
                    "auditor": "auditor", "logkeeper": "auditor", "scop": "auditor",
                }
                actual_bot = bot_map.get(bot_name, bot_name)
                if actual_bot in ["leader", "researcher", "coder", "creative", "social", "auditor"]:
                    intro = onboarding.introduce_bot(actual_bot)
                    return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=intro)
            
            # Otherwise, normal conversation after onboarding
            onboarding.complete()
            self._save_chat_onboarding(session)
            # Return None to signal "continue with normal processing"
            return None
        
        # If onboarding completed, return None to continue with normal processing
        return None
    
    def _check_multi_bot_dispatch(self, message: str, session: Session) -> dict | None:
        """Check if message should trigger multi-bot response mode.
        
        Args:
            message: User message content
            session: Current session
            
        Returns:
            Dispatch info dict if multi-bot mode, None otherwise
        """
        from nanofolks.bots.dispatch import BotDispatch, DispatchTarget
        
        message_lower = message.lower()
        
        # Check for @all / @crew / multiple mentions
        dispatch = BotDispatch()
        result = dispatch.dispatch_message(message, room=None, is_dm=False)
        
        # Only handle MULTI_BOT and CREW_CONTEXT modes
        if result.target in [DispatchTarget.MULTI_BOT, DispatchTarget.CREW_CONTEXT]:
            # Get all bots to respond (primary + secondary)
            all_bots = [result.primary_bot] + result.secondary_bots
            # Remove duplicates while preserving order
            seen = set()
            unique_bots = []
            for bot in all_bots:
                if bot not in seen:
                    seen.add(bot)
                    unique_bots.append(bot)
            
            return {
                'is_multi_bot': True,
                'mode': result.target,
                'bots': unique_bots,
                'primary_bot': result.primary_bot,
                'reason': result.reason,
            }
        
        return None
    
    async def _handle_multi_bot_response(
        self,
        msg: InboundMessage,
        dispatch_result: dict,
        session: Session,
    ) -> OutboundMessage:
        """Handle multi-bot response generation.
        
        Args:
            msg: Inbound message
            dispatch_result: Dispatch information
            session: Current session
            
        Returns:
            Combined response from all bots
        """
        from nanofolks.agent.multi_bot_generator import MultiBotResponseGenerator
        from nanofolks.bots.dispatch import DispatchTarget
        
        bots = dispatch_result['bots']
        mode = dispatch_result['mode']
        
        logger.info(f"Multi-bot mode triggered: {mode.value} with bots: {', '.join(bots)}")
        
        # Log to work log
        self.work_log_manager.log(
            level=LogLevel.INFO,
            category="multi_bot",
            message=f"Multi-bot response: {mode.value} with {len(bots)} bots",
            details={
                'bots': bots,
                'mode': mode.value,
                'reason': dispatch_result['reason'],
            }
        )
        
        # Get room theme for affinity customization
        room_theme = "default"
        try:
            from nanofolks.teams import TeamManager
            team_manager = TeamManager()
            current_team = team_manager.get_current_team()
            if current_team:
                room_theme = current_team.name.value
        except Exception:
            pass
        
        # Generate responses in parallel
        generator = MultiBotResponseGenerator(
            provider=self.provider,
            workspace=self.workspace,
            model=self.model,
            temperature=self.temperature,
            max_tokens=1024,
            room_theme=room_theme,
        )
        
        try:
            responses = await generator.generate_responses(
                user_message=msg.content,
                bot_names=bots,
                mode=mode,
                room_context={'name': 'general'},
            )
            
            # Format combined response
            combined_content = generator.format_multi_bot_response(responses)
            
            # Log individual responses
            for response in responses:
                self.work_log_manager.log(
                    level=LogLevel.INFO,
                    category="bot_response",
                    message=f"@{response.bot_name} responded",
                    details={
                        'bot': response.bot_name,
                        'confidence': response.confidence,
                        'response_time_ms': response.response_time_ms,
                    }
                )
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=combined_content,
                room_id=msg.room_id or self._current_room_id,
                metadata={
                    'multi_bot': True,
                    'responding_bots': [r.bot_name for r in responses],
                    'mode': mode.value,
                }
            )
            
        except Exception as e:
            logger.error(f"Multi-bot response generation failed: {e}")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"❌ Error generating multi-bot response: {str(e)}",
            )
    
    def _apply_theme_if_needed(self) -> None:
        """Apply the selected theme to all team members' SOUL files on first start.
        
        This ensures all bots are ready to use immediately, whether in rooms or via DM.
        Team includes: leader (Leader), researcher, coder, social, creative, auditor
        """
        try:
            from nanofolks.teams import TeamManager
            from nanofolks.soul import SoulManager
            
            # Check if theme has been applied already (use leader as indicator)
            soul_file = self.workspace / "bots" / "leader" / "SOUL.md"
            if soul_file.exists():
                # Theme already applied to team
                logger.debug("Team SOUL files already initialized")
                return
            
            # Get the current theme from theme manager
            theme_manager = TeamManager()
            team = theme_manager.get_current_team()
            
            if not team:
                # No theme selected, skip
                logger.debug("No theme configured, skipping SOUL generation for team")
                return
            
            # Define the complete team (all available bots)
            crew = ["leader", "researcher", "coder", "social", "creative", "auditor"]
            
            # Apply the theme to all team members
            soul_manager = SoulManager(self.workspace)
            results = soul_manager.apply_theme_to_team(
                team,
                crew,
                force=False
            )
            
            # Log results
            successful = sum(1 for v in results.values() if v)
            logger.info(f"Initialized SOUL files for {successful}/{len(crew)} team members")
            
            # Show which bots are ready
            for bot_name, success in results.items():
                if success:
                    logger.debug(f"  ✓ {bot_name} ready for use (DM or room)")
                else:
                    logger.warning(f"  ✗ {bot_name} SOUL initialization failed")
            
        except Exception as e:
            logger.warning(f"Could not initialize team SOUL files: {e}")
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Always protect config file (defense in depth)
        # If protected_paths is empty, at least protect the config file
        default_protected = [str(Path.home() / ".nanofolks" / "config.json")]
        all_protected = list(set(self.protected_paths + default_protected))
        protected_dirs = [Path(p).expanduser().resolve() for p in all_protected]
        
        # Determine tool restrictions based on evolutionary mode
        if self.evolutionary and self.allowed_paths:
            # Evolutionary mode: use allowed_paths whitelist
            logger.info(f"Evolutionary mode enabled with allowed paths: {self.allowed_paths}")
            allowed_dirs = [Path(p).expanduser().resolve() for p in self.allowed_paths]
            self.tools.register(ReadFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
            self.tools.register(WriteFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
            self.tools.register(EditFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
            self.tools.register(ListDirTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
            
            # Shell tool with allowed_paths
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                allowed_paths=self.allowed_paths,
            ))
        else:
            # Standard mode: use restrict_to_workspace behavior
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            self.tools.register(ReadFileTool(allowed_dir=allowed_dir, protected_paths=protected_dirs))
            self.tools.register(WriteFileTool(allowed_dir=allowed_dir, protected_paths=protected_dirs))
            self.tools.register(EditFileTool(allowed_dir=allowed_dir, protected_paths=protected_dirs))
            self.tools.register(ListDirTool(allowed_dir=allowed_dir, protected_paths=protected_dirs))
            
            # Shell tool
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Invoke tool (for delegating to specialist bots)
        from nanofolks.agent.tools.invoke import InvokeTool
        invoke_tool = InvokeTool(invoker=self.bot_invoker)
        self.tools.register(invoke_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service, default_timezone=self.system_timezone))
        
        # Config update tool
        self.tools.register(UpdateConfigTool())
        
        # Memory tools (if memory system is enabled)
        if self.memory_store and self.memory_retrieval:
            from nanofolks.agent.tools.memory import create_memory_tools
            memory_tools = create_memory_tools(self.memory_store, self.memory_retrieval)
            for tool in memory_tools:
                self.tools.register(tool)
            logger.info(f"Registered {len(memory_tools)} memory tools")
        
        # Security tools (always available)
        from nanofolks.agent.tools.security import create_security_tools
        security_tools = create_security_tools()
        for tool in security_tools:
            self.tools.register(tool)
        logger.info(f"Registered {len(security_tools)} security tools")
        
        # Apply tool permissions based on bot's SOUL.md/AGENTS.md
        self._apply_tool_permissions()
    
    def _apply_tool_permissions(self) -> None:
        """Apply tool permissions from bot's SOUL.md/AGENTS.md files."""
        from nanofolks.agent.tools.permissions import (
            get_permissions_from_soul,
            get_permissions_from_agents,
            merge_permissions,
            filter_registry,
        )
        
        soul_perms = get_permissions_from_soul(self.bot_name, self.workspace)
        agents_perms = get_permissions_from_agents(self.bot_name, self.workspace)
        permissions = merge_permissions(soul_perms, agents_perms)
        
        if not permissions.allowed_tools and not permissions.denied_tools:
            logger.debug(f"[{self.bot_name}] No tool permissions defined")
            return
        
        filtered = filter_registry(self.tools, permissions)
        if len(filtered) != len(self.tools):
            logger.info(
                f"[{self.bot_name}] Tool permissions applied: "
                f"{len(self.tools)} -> {len(filtered)} tools"
            )
            self.tools = filtered
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")
        
        # Start background processor if memory is enabled
        if self.background_processor:
            await self.background_processor.start()
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    async def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        
        # Stop background processor if running
        if self.background_processor:
            await self.background_processor.stop()
        
        await self.close_mcp()
        logger.info("Agent loop stopping")
    
    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or not self._mcp_servers:
            return
        self._mcp_connected = True
        from nanofolks.agent.tools.mcp import connect_mcp_servers
        self._mcp_stack = AsyncExitStack()
        await self._mcp_stack.__aenter__()
        await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None
    
    async def _select_model(self, msg: InboundMessage, session: Session) -> str:
        """
        Select the appropriate model using smart routing.
        
        Args:
            msg: The inbound message
            session: The session for context
            
        Returns:
            Model identifier to use
        """
        # If routing is disabled, use default model
        if not self.routing_stage:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="routing",
                message="Smart routing disabled, using default model"
            )
            # Store tier for CoT decisions
            self._current_tier = "medium"
            return self.model
        
        try:
            # Create routing context
            routing_ctx = RoutingContext(
                message=msg,
                session=session,
                default_model=self.model,
                config=self.routing_config or RoutingConfig(),
            )
            
            # Execute routing stage
            import time
            start_time = time.time()
            routing_ctx = await self.routing_stage.execute(routing_ctx)
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Store tier for CoT decisions
            if routing_ctx.decision:
                self._current_tier = routing_ctx.decision.tier.value
            else:
                self._current_tier = "medium"
            
            # Log routing decision
            if routing_ctx.decision:
                logger.info(
                    f"Smart routing: {routing_ctx.decision.tier.value} "
                    f"(confidence: {routing_ctx.decision.confidence:.2f}, "
                    f"layer: {routing_ctx.decision.layer})"
                )
                
                # Log to work log
                self.work_log_manager.log(
                    level=LogLevel.DECISION,
                    category="routing",
                    message=f"Classified as {routing_ctx.decision.tier.value} tier",
                    details={
                        "tier": routing_ctx.decision.tier.value,
                        "model": routing_ctx.model,
                        "confidence": routing_ctx.decision.confidence,
                        "layer": routing_ctx.decision.layer
                    },
                    confidence=routing_ctx.decision.confidence,
                    duration_ms=duration_ms
                )
                
                # Log if low confidence
                if routing_ctx.decision.confidence < 0.7:
                    self.work_log_manager.log(
                        level=LogLevel.UNCERTAINTY,
                        category="routing",
                        message=f"Low confidence routing ({routing_ctx.decision.confidence:.0%})",
                        confidence=routing_ctx.decision.confidence
                    )
            
            return routing_ctx.model
            
        except Exception as e:
            logger.warning(f"Smart routing failed, using default model: {e}")
            self.work_log_manager.log(
                level=LogLevel.WARNING,
                category="routing",
                message=f"Smart routing failed: {str(e)}, using default model"
            )
            return self.model
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        # Check if required configuration is present
        if not self._has_required_config():
            return await self._send_onboarding_message(msg)
        
        # Log message processing start
        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        sanitized_preview = self.sanitizer.sanitize(preview)
        self.work_log_manager.log(
            level=LogLevel.INFO,
            category="general",
            message=f"Processing user message: {sanitized_preview}"
        )
        
        # Sanitize message content for logging to prevent secret exposure
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {sanitized_preview}")
        
        # Warn if secrets were detected
        if self.sanitizer.has_secrets(msg.content):
            secret_types = self.sanitizer.get_secret_types(msg.content)
            logger.warning(f"Detected potential secrets in message: {', '.join(secret_types)}")
            logger.warning("Secrets have been masked before sending to LLM")
        
        # Mark user activity for background processing
        if self.activity_tracker:
            self.activity_tracker.mark_activity()
        
        # Get or create session
        key = msg.session_key
        session = self.sessions.get_or_create(key)
        
        # Check if onboarding is needed for first-time users
        onboarding_response = None
        if self._check_onboarding_needed(session):
            onboarding_response = await self._handle_chat_onboarding(msg, session)
            # If onboarding returns a response, send it
            if onboarding_response is not None:
                return onboarding_response
            # If onboarding returns None, it completed - continue with normal processing
            # Message will be sanitized and added in normal flow below
        
        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            session.clear()
            self.sessions.save(session)
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐈 New session started.",
                room_id=msg.room_id or self._current_room_id,
            )
        if cmd == "/help":
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="🐈 nanofolks commands:\n/new — Start a new conversation\n/help — Show available commands",
                room_id=msg.room_id or self._current_room_id,
            )
        
        # Check for multi-bot triggers (@all, @crew, multiple @mentions)
        dispatch_result = self._check_multi_bot_dispatch(msg.content, session)
        if dispatch_result and dispatch_result.get('is_multi_bot'):
            return await self._handle_multi_bot_response(msg, dispatch_result, session)
        
        # NEW: Phase 2 - Intent Detection + Hybrid Router
        # Check for ongoing project state first
        if self._hybrid_router_enabled:
            from nanofolks.agent.project_state import ProjectStateManager, ProjectPhase
            room_id = msg.session_key  # Use session_key as room_id
            
            state_manager = ProjectStateManager(self.workspace, room_id)
            
            # Check for timeout
            state_manager.check_timeout()
            
            # If in the middle of a flow (not IDLE), continue it
            if state_manager.state.phase != ProjectPhase.IDLE:
                from nanofolks.agent.intent_flow_router import IntentFlowRouter
                if self.hybrid_router is None:
                    self.hybrid_router = IntentFlowRouter(self)
                return await self.hybrid_router._continue_full_flow(msg, state_manager, session)
            
            # NEW: Intent detection for new messages
            # Only use if NOT an explicit @mention (let existing dispatch handle those)
            if not dispatch_result:  # No @all/@crew/@bot explicit mentions
                from nanofolks.agent.intent_detector import IntentDetector, FlowType
                intent_detector = IntentDetector()
                intent = intent_detector.detect(msg.content)
                
                # Initialize router lazily
                if self.hybrid_router is None:
                    from nanofolks.agent.intent_flow_router import IntentFlowRouter
                    self.hybrid_router = IntentFlowRouter(self)
                
                # Route based on intent:
                # - QUICK: Route to quick flow (clarifying questions → answer)
                # - FULL: Let Leader handle it - Leader will decide to create room if needed
                #   This gives Leader autonomy to orchestrate complex tasks
                if intent.flow_type == FlowType.QUICK:
                    logger.info(f"Intent detected: {intent.intent_type.value}, routing to quick flow")
                    return await self.hybrid_router.route(msg, session)
                elif intent.flow_type == FlowType.FULL:
                    # Store intent info in session metadata for Leader to access
                    session.metadata['_detected_intent'] = {
                        'type': intent.intent_type.value,
                        'confidence': intent.confidence,
                        'suggested_bots': intent.suggested_bots,
                    }
                    
                    # Add intent context to session so Leader sees it
                    intent_context = f"\n[System: This request appears to be a {intent.intent_type.value} task. " \
                                    f"Suggested team: {', '.join(intent.suggested_bots)}]\n"
                    session.messages.append({
                        'role': 'system', 
                        'content': intent_context
                    })
                    self.sessions.save(session)
                    logger.info(f"Intent detected: {intent.intent_type.value}, passing to Leader (Leader will decide if room needed)")
                    # Don't auto-route - let Leader handle it normally
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        invoke_tool = self.tools.get("invoke")
        if invoke_tool:
            # Check for set_context method (invoke tool has it)
            set_context = getattr(invoke_tool, "set_context", None)
            if set_context and callable(set_context):
                set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        
        # NEW: Convert credentials to symbolic references before sending to LLM
        # This is the core security feature - credentials never reach the LLM
        from nanofolks.security.symbolic_converter import get_symbolic_converter
        converter = get_symbolic_converter()
        conversion_result = converter.convert(msg.content, session.session_key if session else None)
        
        # Use converted content (credentials replaced with {{ref}}) for LLM
        # But keep original for logging
        sanitized_content = conversion_result.text
        
        # Log warning if credentials were detected and converted
        if conversion_result.credentials:
            logger.info(f"🔐 Converted {len(conversion_result.credentials)} credential(s) to symbolic references: {[c['key_ref'] for c in conversion_result.credentials]}")
        
        # Also sanitize as backup defense-in-depth
        sanitized_content = self.sanitizer.sanitize(sanitized_content)
        
        # Log event to memory system if enabled
        if self.memory_store:
            from datetime import datetime
            from nanofolks.memory.models import Event
            import uuid
            
            event = Event(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                channel=msg.channel,
                direction="inbound",
                event_type="message",
                content=sanitized_content,
                session_key=msg.session_key,
            )
            self.memory_store.save_event(event)
            
            # Phase 6: Detect feedback from previous conversation
            if self.learning_manager and session.messages:
                try:
                    # Get last assistant message for context
                    last_assistant_msgs = [m for m in session.messages if m.get("role") == "assistant"]
                    if last_assistant_msgs:
                        context = last_assistant_msgs[-1].get("content", "")
                        
                        # Detect feedback in user message
                        learning = await self.learning_manager.process_message(
                            message=sanitized_content,
                            context=context,
                        )
                        
                        if learning:
                            logger.info(f"Detected feedback: {learning.content[:50]}...")
                            
                            # Increment preferences staleness
                            if self.preferences_aggregator:
                                self.preferences_aggregator.increment_staleness()
                                
                                # Refresh preferences if needed
                                await self.preferences_aggregator.refresh_if_needed()
                except Exception as e:
                    logger.error(f"Failed to process feedback: {e}")
        
        # Build memory context if memory system is enabled
        memory_context = ""
        if self.context_assembler and self.memory_retrieval:
            try:
                # Log memory retrieval start
                self.work_log_manager.log(
                    level=LogLevel.THINKING,
                    category="memory",
                    message="Retrieving relevant context from memory"
                )
                
                import time
                mem_start_time = time.time()
                
                # Find relevant entities from recent conversation
                relevant_entities = self.context_assembler.get_relevant_entities(
                    query=sanitized_content,
                    channel=msg.channel,
                    limit=5,
                )
                entity_ids = [e.id for e in relevant_entities]
                
                # Assemble memory context (room-centric)
                room_id_for_context = msg.room_id if msg.room_id else self._current_room_id
                memory_context = self.context_assembler.assemble_context(
                    room_id=room_id_for_context,
                    entity_ids=entity_ids,
                    include_preferences=True,
                )
                
                mem_duration_ms = int((time.time() - mem_start_time) * 1000)
                
                if memory_context:
                    self.work_log_manager.log(
                        level=LogLevel.INFO,
                        category="memory",
                        message=f"Retrieved {len(memory_context)} characters of memory context",
                        details={"entity_count": len(entity_ids)},
                        duration_ms=mem_duration_ms
                    )
                else:
                    self.work_log_manager.log(
                        level=LogLevel.WARNING,
                        category="memory",
                        message="No relevant memory context found",
                        duration_ms=mem_duration_ms
                    )
                
                logger.debug(f"Assembled memory context ({len(memory_context)} chars)")
            except Exception as e:
                logger.error(f"Failed to assemble memory context: {e}")
                self.work_log_manager.log(
                    level=LogLevel.ERROR,
                    category="memory",
                    message=f"Failed to retrieve memory context: {str(e)}"
                )
        
        # Phase 8: Check and trigger session compaction if needed
        # Prevents context overflow in long conversations
        if self.session_compactor:
            try:
                from nanofolks.memory.token_counter import count_messages
                
                # Get current context usage
                max_tokens = self.memory_config.enhanced_context.max_context_tokens if self.memory_config else 8000
                current_tokens = count_messages(session.messages)
                
                # Check if compaction needed
                if self.session_compactor.should_compact(session.messages, max_tokens):
                    # Get strategy recommendation
                    strategy = self.session_compactor.get_compaction_strategy(
                        session.messages, max_tokens
                    )
                    
                    logger.info(
                        f"🧹 Compaction triggered: {current_tokens} tokens approaching "
                        f"{max_tokens} limit - {strategy['reason']}"
                    )
                    
                    # Pre-compaction memory flush hook
                    if self.session_compactor.config.enable_memory_flush:
                        await self._memory_flush_hook(session, msg)
                    
                    # Compact the session
                    result = await self.session_compactor.compact_session(session, max_tokens)
                    
                    # Validate compaction
                    validation = self.session_compactor.validate_compaction(
                        session.messages, result.messages
                    )
                    
                    if not validation["is_valid"]:
                        for issue in validation["issues"]:
                            logger.error(f"Compaction validation failed: {issue}")
                    elif validation["warnings"]:
                        for warning in validation["warnings"]:
                            logger.warning(f"Compaction warning: {warning}")
                    
                    # Update session with compacted messages
                    session.messages = result.messages
                    
                    # Log compaction stats
                    logger.info(
                        f"🧹 Compaction complete: {result.original_count} → {result.compacted_count} messages, "
                        f"{result.tokens_before} → {result.tokens_after} tokens "
                        f"({result.compaction_ratio:.1%}), "
                        f"validation: {'passed' if validation['is_valid'] else 'failed'}"
                    )
                    
                    # Show compaction notice in response metadata
                    session.metadata["last_compaction"] = {
                        "original_count": result.original_count,
                        "compacted_count": result.compacted_count,
                        "tokens_before": result.tokens_before,
                        "tokens_after": result.tokens_after,
                        "mode": result.mode,
                        "strategy": strategy["strategy"],
                        "validation_passed": validation["is_valid"]
                    }
            except Exception as e:
                logger.error(f"Session compaction failed: {e}")
                # Continue without compaction - don't block message processing
        
        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=sanitized_content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            memory_context=memory_context if memory_context else None,
            bot_name=self.bot_name,
            room_id=self._current_room_id,
            room_type=self._current_room_type,
            participants=self._current_room_participants,
        )
        
        # Select model using smart routing
        selected_model = await self._select_model(msg, session)
        
        # Agent loop
        iteration = 0
        final_content = None
        secondary_model = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Check if streaming is enabled and we have a callback
            use_streaming = (
                hasattr(self, '_stream_callback') and 
                self._stream_callback and
                self.routing_config and 
                self.routing_config.streaming_enabled
            )
            
            # Call LLM with selected model (streaming or regular)
            try:
                if use_streaming and iteration == 1:  # Only stream on first iteration
                    # Use streaming for real-time updates
                    response = await self.stream_response(
                        messages=messages,
                        tools=self.tools.get_definitions(),
                        model=selected_model,
                        chunk_callback=self._stream_callback,
                        session=session,
                    )
                else:
                    response = await self.provider.chat(
                        messages=messages,
                        tools=self.tools.get_definitions(),
                        model=selected_model,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                    )
            except Exception as e:
                # Try secondary model if available
                if secondary_model is None and self.routing_config:
                    # Get routing context to find secondary model
                    routing_ctx = RoutingContext(
                        message=msg,
                        session=session,
                        default_model=self.model,
                        config=self.routing_config,
                    )
                    if self.routing_stage:
                        await self.routing_stage.execute(routing_ctx)
                        tier_config = getattr(self.routing_config.tiers, routing_ctx.metadata.get("routing_tier", "medium"), None)
                        secondary_model = tier_config.secondary_model if tier_config else None
                
                if secondary_model and selected_model != secondary_model:
                    logger.warning(f"Primary model {selected_model} failed: {e}. Trying secondary model {secondary_model}")
                    selected_model = secondary_model
                    iteration -= 1  # Retry with secondary model
                    continue
                else:
                    raise e
            
            # Log reasoning content from CoT models (DeepSeek-R1, Kimi, etc.)
            if response.reasoning_content:
                tier = self._get_tier_for_logging()
                self.work_log_manager.log(
                    level=LogLevel.THINKING,
                    category="reasoning",
                    message=f"CoT reasoning content (tier: {tier})",
                    details={
                        "thinking": response.reasoning_content[:500],
                        "tier": tier,
                    }
                )

            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    # Sanitize tool arguments to prevent secrets in logs
                    sanitized_args = self.sanitizer.sanitize(args_str[:200])
                    logger.info(f"Tool call: {tool_call.name}({sanitized_args})")
                    
                    # Log tool execution start
                    import time
                    tool_start_time = time.time()
                    
                    try:
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)
                        tool_duration_ms = int((time.time() - tool_start_time) * 1000)
                        
                        # Log successful tool execution
                        self.work_log_manager.log_tool(
                            tool_name=tool_call.name,
                            tool_input=tool_call.arguments,
                            tool_output=result,
                            tool_status="success",
                            duration_ms=tool_duration_ms
                        )
                    except Exception as tool_error:
                        tool_duration_ms = int((time.time() - tool_start_time) * 1000)
                        
                        # Log failed tool execution
                        self.work_log_manager.log(
                            level=LogLevel.ERROR,
                            category="tool_execution",
                            message=f"Tool {tool_call.name} failed: {str(tool_error)}",
                            details={"tool": tool_call.name, "error": str(tool_error)},
                            duration_ms=tool_duration_ms
                        )
                        raise
                    
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
                    
                    # Check if we should add CoT reflection (bot-level reasoning config)
                    if self._should_use_cot(tool_call.name):
                        reflection_prompt = self.reasoning_config.get_reflection_prompt()
                        messages.append({
                            "role": "user",
                            "content": reflection_prompt
                        })
                        logger.debug(f"Added CoT reflection after {tool_call.name}")
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            if iteration >= self.max_iterations:
                final_content = f"Reached {self.max_iterations} iterations without completion."
            else:
                final_content = "I've completed processing but have no response to give."
        
        # Log response completion
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        sanitized_response_preview = self.sanitizer.sanitize(preview)
        self.work_log_manager.log(
            level=LogLevel.INFO,
            category="general",
            message="Response generated successfully",
            details={
                "response_preview": sanitized_response_preview,
                "response_length": len(final_content),
                "iterations": iteration
            }
        )
        
        # Log response preview (sanitize to prevent echoing secrets)
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {sanitized_response_preview}")
        
        # Save to session (sanitize to prevent secrets in session history)
        sanitized_user_content = self.sanitizer.sanitize(msg.content)
        sanitized_assistant_content = self.sanitizer.sanitize(final_content)
        session.add_message("user", sanitized_user_content)
        session.add_message("assistant", sanitized_assistant_content)
        self.sessions.save(session)
        
        # Log outbound response to memory system if enabled
        if self.memory_store:
            from datetime import datetime
            from nanofolks.memory.models import Event
            import uuid
            
            event = Event(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                channel=msg.channel,
                direction="outbound",
                event_type="message",
                content=sanitized_assistant_content,
                session_key=msg.session_key,
            )
            self.memory_store.save_event(event)
        
        # Phase 9: Add context usage to response metadata
        response_metadata = msg.metadata or {}
        if self.memory_config and self.memory_config.enhanced_context.show_context_percentage:
            try:
                from nanofolks.memory.token_counter import count_messages
                max_tokens = self.memory_config.enhanced_context.max_context_tokens
                current_tokens = count_messages(session.messages)
                percentage = current_tokens / max_tokens if max_tokens > 0 else 0
                
                # Add context status to metadata
                response_metadata["context_usage"] = f"{percentage:.0%}"
                response_metadata["tokens_used"] = current_tokens
                response_metadata["tokens_remaining"] = max(0, max_tokens - current_tokens)
                
                # Log warning if approaching limit
                if percentage > self.memory_config.enhanced_context.warning_threshold:
                    logger.warning(
                        f"Context at {percentage:.0%} - consider using /compact command"
                    )
            except Exception as e:
                logger.debug(f"Failed to calculate context usage: {e}")
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            room_id=msg.room_id or self._current_room_id,
            metadata=response_metadata,  # Includes context usage if enabled
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context (room-centric format)
        # Prefer room_id from message, fallback to constructing from origin info
        if msg.room_id:
            session_key = f"room:{msg.room_id}"
        else:
            session_key = f"room:{origin_channel}_{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        invoke_tool = self.tools.get("invoke")
        if invoke_tool:
            set_context = getattr(invoke_tool, "set_context", None)
            if set_context and callable(set_context):
                set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
            bot_name=self.bot_name,
        )
        
        # Select model using smart routing
        selected_model = await self._select_model(msg, session)
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=selected_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content,
            room_id=msg.room_id or self._current_room_id,
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str | None = None,
        channel: str = "cli",
        chat_id: str = "direct",
        room_id: str = "general",
        room_type: str = "open",
        participants: list | None = None,
        stream_callback: callable = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier (room-centric format: "room:{room_id}"). 
                        If None, constructed from room_id.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).
            room_id: Room identifier for multi-agent context (default: "general").
            room_type: Type of room (open, project, direct, coordination).
            participants: List of bot participants in the room.
            stream_callback: Optional callback for streaming chunks (content: str) -> None.

        Returns:
            The agent's response.
        """
        # Set room context for this session
        self._current_room_id = room_id
        self._current_room_type = room_type
        self._current_room_participants = participants or ["leader"]
        
        # Construct session_key from room_id if not provided (room-centric)
        if session_key is None:
            session_key = f"room:{room_id}"
        
        # Start work log session for transparency with room context
        self.work_log_manager.start_session(
            session_key, 
            content,
            workspace_id=room_id,
            workspace_type=RoomType(room_type) if room_type else RoomType.OPEN,
            participants=participants or ["leader"]
        )
        
        try:
            await self._connect_mcp()
            
            msg = InboundMessage(
                channel=channel,
                sender_id="user",
                chat_id=chat_id,
                content=content,
                room_id=room_id
            )
            
            # Store stream callback for use in _process_message
            self._stream_callback = stream_callback

            response = await self._process_message(msg)
            result = response.content if response else ""
            
            # Clear callback after use
            self._stream_callback = None
            
            # End work log session
            self.work_log_manager.end_session(result)
            return result
            
        except Exception as e:
            # Log error and end session
            self.work_log_manager.log(
                level=LogLevel.ERROR,
                category="general",
                message=f"Error processing message: {str(e)}"
            )
            self.work_log_manager.end_session(f"Error: {str(e)}")
            raise

    def _has_required_config(self) -> bool:
        """Check if required configuration is present."""
        # Check if at least one provider has an API key
        from nanofolks.config.loader import load_config
        config = load_config()

        providers = ['openrouter', 'anthropic', 'openai', 'groq', 'deepseek', 'moonshot']
        for provider_name in providers:
            provider = getattr(config.providers, provider_name, None)
            if provider and provider.api_key:
                return True

        return False
    
    async def _memory_flush_hook(self, session: Session, msg: InboundMessage) -> None:
        """
        Pre-compaction memory flush hook.
        
        Allows the agent to persist important state to memory before
        compaction removes it from the session context.
        
        Inspired by OpenClaw's pre-compaction flush mechanism.
        
        Args:
            session: The session being compacted.
            msg: The current inbound message.
        """
        if not self.memory_store or not self.learning_manager:
            return
        
        try:
            logger.debug("Running pre-compaction memory flush hook")
            
            # Detect any learnings from recent conversation
            if session.messages:
                # Get last few messages to check for feedback
                recent_msgs = session.messages[-10:]
                for message in recent_msgs:
                    if message.get("role") == "user":
                        content = message.get("content", "")
                        # Check for feedback patterns
                        if self.learning_manager.feedback_detector.detect_feedback(content):
                            # Process and store learning
                            learnings = self.learning_manager.feedback_detector.extract_learning(content)
                            for learning_data in learnings:
                                await self.learning_manager.create_learning(
                                    content=learning_data["content"],
                                    category=learning_data.get("category", "general"),
                                    confidence=learning_data.get("confidence", 0.7),
                                    source_event_id=message.get("event_id", ""),
                                    tool_name=learning_data.get("tool_name")
                                )
            
            # Refresh preferences summary if needed
            if self.preferences_aggregator:
                await self.preferences_aggregator.refresh_if_needed()
            
            logger.debug("Memory flush hook complete")
            
        except Exception as e:
            logger.warning(f"Memory flush hook failed (non-critical): {e}")
            # Don't fail compaction if flush fails

    def _should_use_cot(self, tool_name: str) -> bool:
        """Determine if Chain-of-Thought reflection should be used.
        
        Checks bot's reasoning configuration and current routing tier.
        
        Args:
            tool_name: Name of the tool that was just executed
            
        Returns:
            True if CoT reflection should be added
        """
        tier = self._get_tier_for_logging()
        
        # Check if reasoning config is available
        if not hasattr(self, 'reasoning_config') or not self.reasoning_config:
            return False
        
        # Use reasoning config to decide
        return self.reasoning_config.should_use_cot(tier, tool_name)

    def _get_tier_for_logging(self) -> str:
        """Get the current tier for logging purposes.
        
        Provides safe access to _current_tier with proper warning
        if it's unexpectedly None.
        
        Returns:
            The current tier string (always returns a valid tier)
        """
        tier = getattr(self, '_current_tier', None)
        
        if tier is None:
            logger.warning(
                f"Tier not set for {self.bot_name}, "
                f"this is a bug - should be set in _select_model()"
            )
            return "medium"
        
        return tier

    async def stream_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        chunk_callback: callable,
        session: Session,
    ) -> LLMResponse:
        """Stream LLM response with real-time updates.
        
        Args:
            messages: Messages to send to LLM
            tools: Available tools
            model: Model to use
            chunk_callback: Called with each chunk content
            session: Current session (for logging)
            
        Returns:
            Complete LLMResponse
        """
        accumulated_content = []
        accumulated_reasoning = []
        final_tool_calls = []
        finish_reason = None
        
        # Log streaming start
        self.work_log_manager.log(
            level=LogLevel.INFO,
            category="streaming",
            message="Started streaming LLM response"
        )
        
        async for chunk in self.provider.stream_chat(
            messages=messages,
            tools=tools,
            model=model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ):
            if chunk.content:
                accumulated_content.append(chunk.content)
            
            if chunk.reasoning_content:
                accumulated_reasoning.append(chunk.reasoning_content)
            
            if chunk.tool_calls:
                final_tool_calls.extend(chunk.tool_calls)
            
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
            
            # Send chunk to callback for CLI display
            if chunk.content:
                chunk_callback(chunk.content)
            
            # Log this chunk to work logs (for debugging)
            if chunk.is_final and chunk.content:
                self.work_log_manager.log(
                    level=LogLevel.INFO,
                    category="streaming",
                    message="Streamed LLM response complete",
                    details={
                        "total_chunks": len(accumulated_content),
                        "reasoning_tokens": len("".join(accumulated_reasoning)) if accumulated_reasoning else 0
                    }
                )
        
        # Build final response
        full_content = "".join(accumulated_content)
        full_reasoning = "".join(accumulated_reasoning) if accumulated_reasoning else None
        
        return LLMResponse(
            content=full_content,
            tool_calls=final_tool_calls,
            finish_reason=finish_reason or "stop",
            usage={"completion_tokens": len(full_content.split())},  # Rough estimate
            reasoning_content=full_reasoning,
        )

    async def _send_onboarding_message(self, msg: InboundMessage) -> OutboundMessage:
        """Send onboarding message when config is missing."""
        logger.info(f"Sending onboarding message to {msg.channel}:{msg.sender_id}")

        content = """👋 Welcome to nanofolks!

I'm ready to help, but I need some configuration first.

**Required Setup:**
I need at least one LLM provider configured. Popular options:
• OpenRouter (recommended) - multi-model access
• Anthropic - Claude models
• OpenAI - GPT models

**To configure me:**
1. Run: `nanofolks configure`
2. Select your preferred provider
3. Enter your API key

**Get an API key:**
• OpenRouter: https://openrouter.ai/keys
• Anthropic: https://console.anthropic.com/
• OpenAI: https://platform.openai.com/api-keys

Once configured, we can start chatting! 🤖"""

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=content,
            room_id=msg.room_id or self._current_room_id,
            metadata=msg.metadata or {}
        )
