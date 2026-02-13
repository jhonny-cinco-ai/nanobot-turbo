"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.security.sanitizer import SecretSanitizer, mask_logs
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.update_config import UpdateConfigTool
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.stages import RoutingStage, RoutingContext
from nanobot.config.schema import RoutingConfig
from nanobot.session.manager import SessionManager, Session
from nanobot.agent.work_log_manager import get_work_log_manager, LogLevel
from nanobot.reasoning.config import get_reasoning_config, ReasoningConfig


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
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        routing_config: RoutingConfig | None = None,
        evolutionary: bool = False,
        allowed_paths: list[str] | None = None,
        protected_paths: list[str] | None = None,
        memory_config: "MemoryConfig | None" = None,
    ):
        from nanobot.config.schema import ExecToolConfig
        from nanobot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.workspace_id = str(workspace)  # For Learning Exchange
        self.bot_name = "nanobot"  # Identity of this bot instance
        
        # Initialize reasoning configuration for this bot
        self.reasoning_config = get_reasoning_config(self.bot_name)
        logger.debug(f"Loaded reasoning config for {self.bot_name}: {self.reasoning_config.cot_level.value}")
        
        # Initialize current tier for CoT decisions (set by _select_model)
        self._current_tier = "medium"
        
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.evolutionary = evolutionary
        self.allowed_paths = allowed_paths or []
        self.protected_paths = protected_paths or []
        
        # Initialize secret sanitizer for security
        self.sanitizer = SecretSanitizer()
        
        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
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
            from nanobot.memory.store import TurboMemoryStore
            from nanobot.memory.background import ActivityTracker, BackgroundProcessor
            from nanobot.memory.summaries import SummaryTreeManager, create_summary_manager
            from nanobot.memory.context import ContextAssembler, create_context_assembler
            from nanobot.memory.retrieval import MemoryRetrieval, create_retrieval
            from nanobot.memory.embeddings import EmbeddingProvider
            
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
            from nanobot.agent.learning_exchange import LearningExchange
            
            self.learning_exchange = LearningExchange(
                bot_name=self.bot_name,
                workspace_id=self.workspace_id,
            )
            
            # Load any pending packages from previous sessions
            pending_count = self.learning_exchange.load_pending_packages()
            if pending_count > 0:
                logger.info(f"Loaded {pending_count} pending learning packages from previous sessions")
            
            # Initialize learning manager (Phase 6) with Learning Exchange
            from nanobot.memory.learning import create_learning_manager
            from nanobot.memory.preferences import create_preferences_aggregator
            
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
            from nanobot.memory.session_compactor import SessionCompactor, SessionCompactionConfig
            
            self.session_compactor = SessionCompactor(
                memory_config.session_compaction
            )
            
            logger.info(
                f"Memory system enabled with learning, context assembly, and retrieval. "
                f"Session compaction: {memory_config.session_compaction.mode} mode"
            )
        
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            evolutionary=evolutionary,
            allowed_paths=allowed_paths,
            protected_paths=protected_paths,
        )
        
        # Initialize work log manager for transparency
        self.work_log_manager = get_work_log_manager()
        
        self._running = False
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # Determine tool restrictions based on evolutionary mode
        if self.evolutionary and self.allowed_paths:
            # Evolutionary mode: use allowed_paths whitelist
            logger.info(f"Evolutionary mode enabled with allowed paths: {self.allowed_paths}")
            allowed_dirs = [Path(p).expanduser().resolve() for p in self.allowed_paths]
            protected_dirs = [Path(p).expanduser().resolve() for p in self.protected_paths]
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
            self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
            self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
            self.tools.register(EditFileTool(allowed_dir=allowed_dir))
            self.tools.register(ListDirTool(allowed_dir=allowed_dir))
            
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
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))
        
        # Config update tool
        self.tools.register(UpdateConfigTool())
        
        # Memory tools (if memory system is enabled)
        if self.memory_store and self.memory_retrieval:
            from nanobot.agent.tools.memory import create_memory_tools
            memory_tools = create_memory_tools(self.memory_store, self.memory_retrieval)
            for tool in memory_tools:
                self.tools.register(tool)
            logger.info(f"Registered {len(memory_tools)} memory tools")
        
        # Security tools (always available)
        from nanobot.agent.tools.security import create_security_tools
        security_tools = create_security_tools()
        for tool in security_tools:
            self.tools.register(tool)
        logger.info(f"Registered {len(security_tools)} security tools")
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
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
        
        logger.info("Agent loop stopping")
    
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
        
        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            session.clear()
            self.sessions.save(session)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 New session started.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 nanobot commands:\n/new — Start a new conversation\n/help — Show available commands")
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        
        # Sanitize message content before sending to LLM to prevent secret exposure
        sanitized_content = self.sanitizer.sanitize(msg.content)
        
        # Log event to memory system if enabled
        if self.memory_store:
            from datetime import datetime
            from nanobot.memory.models import Event
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
                
                # Assemble memory context
                memory_context = self.context_assembler.assemble_context(
                    channel=msg.channel,
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
                from nanobot.memory.token_counter import count_messages
                
                # Get current context usage
                max_tokens = self.memory_config.enhanced_context.max_context_tokens if self.memory_config else 8000
                current_tokens = count_messages(session.messages)
                
                # Check if compaction needed
                if self.session_compactor.should_compact(session.messages, max_tokens):
                    logger.info(
                        f"🧹 Compaction triggered: {current_tokens} tokens approaching "
                        f"{max_tokens} limit"
                    )
                    
                    # Pre-compaction memory flush hook
                    if self.session_compactor.config.enable_memory_flush:
                        await self._memory_flush_hook(session, msg)
                    
                    # Compact the session
                    result = await self.session_compactor.compact_session(session, max_tokens)
                    
                    # Update session with compacted messages
                    session.messages = result.messages
                    
                    # Log compaction stats
                    logger.info(
                        f"🧹 Compaction complete: {result.original_count} → {result.compacted_count} messages, "
                        f"{result.tokens_before} → {result.tokens_after} tokens "
                        f"({result.compaction_ratio:.1%})"
                    )
                    
                    # Show compaction notice in response metadata
                    session.metadata["last_compaction"] = {
                        "original_count": result.original_count,
                        "compacted_count": result.compacted_count,
                        "tokens_before": result.tokens_before,
                        "tokens_after": result.tokens_after,
                        "mode": result.mode
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
        )
        
        # Select model using smart routing
        selected_model = await self._select_model(msg, session)
        
        # Agent loop
        iteration = 0
        final_content = None
        secondary_model = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM with selected model
            try:
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=selected_model
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
            from nanobot.memory.models import Event
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
                from nanobot.memory.token_counter import count_messages
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
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
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
                model=selected_model
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
            content=final_content
        )
    
    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).

        Returns:
            The agent's response.
        """
        # Start work log session for transparency
        self.work_log_manager.start_session(session_key, content)
        
        try:
            msg = InboundMessage(
                channel=channel,
                sender_id="user",
                chat_id=chat_id,
                content=content
            )

            response = await self._process_message(msg)
            result = response.content if response else ""
            
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
        from nanobot.config.loader import load_config
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
        # Get current tier (default to medium if not set)
        tier = getattr(self, '_current_tier', 'medium')
        
        # Check if reasoning config is available
        if not hasattr(self, 'reasoning_config') or not self.reasoning_config:
            return False
        
        # Use reasoning config to decide
        return self.reasoning_config.should_use_cot(tier, tool_name)

    async def _send_onboarding_message(self, msg: InboundMessage) -> OutboundMessage:
        """Send onboarding message when config is missing."""
        logger.info(f"Sending onboarding message to {msg.channel}:{msg.sender_id}")

        content = """👋 Welcome to nanobot!

I'm ready to help, but I need some configuration first.

**Required Setup:**
I need at least one LLM provider configured. Popular options:
• OpenRouter (recommended) - multi-model access
• Anthropic - Claude models
• OpenAI - GPT models

**To configure me:**
1. Run: `nanobot configure`
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
            metadata=msg.metadata or {}
        )
