"""Bot invocation system for delegating tasks to specialist bots.

This module provides both synchronous and asynchronous bot invocation where
the main agent (nanofolks) can delegate tasks to specialist bots. Supports:
- Synchronous: waits for response before continuing (legacy mode)
- Asynchronous: fires off task and notifies when complete (recommended)
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from nanofolks.agent.tools.registry import ToolRegistry
from nanofolks.agent.sidekicks import (
    SidekickLimitError,
    SidekickOrchestrator,
    SidekickResult,
    SidekickTaskEnvelope,
)
from nanofolks.agent.work_log import LogLevel
from nanofolks.bus.events import MessageEnvelope
from nanofolks.bus.queue import MessageBus
from nanofolks.config.schema import ExecToolConfig, SidekickConfig
from nanofolks.providers.base import LLMProvider
from nanofolks.security.sanitizer import SecretSanitizer
from nanofolks.utils.ids import room_to_session_id

# Available specialist bots that can be invoked
AVAILABLE_BOTS = {
    "researcher": {
        "domain": "research",
        "description": "Deep research, analysis, and information gathering",
        "bot_role": "Navigator",
    },
    "coder": {
        "domain": "development",
        "description": "Code implementation, debugging, and technical solutions",
        "bot_role": "Gunner",
    },
    "social": {
        "domain": "community",
        "description": "Community engagement, communication, and user relations",
        "bot_role": "Lookout",
    },
    "creative": {
        "domain": "design",
        "description": "Creative brainstorming, design, and content creation",
        "bot_role": "Artist",
    },
    "auditor": {
        "domain": "quality",
        "description": "Quality review, validation, and compliance checking",
        "bot_role": "Quartermaster",
    },
}


class BotInvoker:
    """
    Manages synchronous bot invocations.

    Allows the main agent (nanofolks) to delegate tasks to specialist bots
    and wait for their responses. Each bot has its own processing context
    with its SOUL.md personality.
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        work_log_manager: Any = None,
        memory_store: Any = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        evolutionary: bool = False,
        allowed_paths: list[str] | None = None,
        protected_paths: list[str] | None = None,
        sidekick_config: "SidekickConfig | None" = None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.evolutionary = evolutionary
        self.protected_paths = protected_paths or []
        self.allowed_paths = allowed_paths or []
        self.sidekick_config = sidekick_config or SidekickConfig()

        # Initialize secret sanitizer
        self.sanitizer = SecretSanitizer()

        # Work log manager for multi-bot tracking
        self.work_log_manager = work_log_manager
        self._memory_store = memory_store

        # Active invocations (all async now)
        self._active_invocations: dict[str, asyncio.Task[None]] = {}
        self._invocation_task_map: dict[str, dict[str, str]] = {}
        self._cached_team_name: str | None = None
        self._sidekick_orchestrator: SidekickOrchestrator | None = None

    def _get_sidekick_orchestrator(self) -> SidekickOrchestrator:
        if self._sidekick_orchestrator is None:
            self._sidekick_orchestrator = SidekickOrchestrator(
                max_per_bot=self.sidekick_config.max_sidekicks_per_bot,
                max_per_room=self.sidekick_config.max_sidekicks_per_room,
                max_tokens=self.sidekick_config.max_tokens,
                timeout_seconds=self.sidekick_config.timeout_seconds,
            )
        return self._sidekick_orchestrator

    async def invoke(
        self,
        bot_role: str,
        task: str,
        context: Optional[str] = None,
        session_id: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        origin_room_id: str | None = None,
        room_task_id: str | None = None,
    ) -> str:
        """
        Invoke a specialist bot to handle a task.

        The bot works in the background and reports results back when complete.
        This is always async - the main agent continues immediately.

        Args:
            bot_role: Role identifier (researcher, coder, social, creative, auditor)
            task: Task description for the bot
            context: Additional context from the main conversation
            session_id: Session ID for this invocation
            origin_channel: Channel to send notification when complete
            origin_chat_id: Chat ID to send notification when complete
            origin_room_id: Room ID to associate with the result

        Returns:
            Confirmation message that the bot was invoked
        """
        if bot_role not in AVAILABLE_BOTS:
            return f"Error: Unknown bot '{bot_role}'. Available bots: {', '.join(AVAILABLE_BOTS.keys())}"

        if bot_role == "leader":
            return "Error: Cannot invoke leader (Leader) - use @leader directly"

        invocation_id = str(uuid.uuid4())[:8]
        session_id = room_to_session_id(session_id or "invoke_general")

        # Always async - fire and forget
        return await self._invoke_async(
            invocation_id=invocation_id,
            bot_role=bot_role,
            task=task,
            context=context,
            session_id=session_id,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            origin_room_id=origin_room_id,
            room_task_id=room_task_id,
        )

    async def _invoke_async(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        context: Optional[str],
        session_id: str,
        origin_channel: str,
        origin_chat_id: str,
        origin_room_id: str | None,
        room_task_id: str | None,
    ) -> str:
        """Asynchronous invocation - fires off task and notifies when complete."""
        logger.info(f"Invoking {bot_role} (id: {invocation_id}, async): {task[:50]}...")

        # Log the bot invocation request
        self._log_invocation_request(invocation_id, bot_role, task, context)

        if room_task_id and origin_room_id:
            self._invocation_task_map[invocation_id] = {
                "room_id": origin_room_id,
                "task_id": room_task_id,
            }

        # Launch in background, don't wait
        task_handle = asyncio.create_task(
            self._process_invocation(
                invocation_id=invocation_id,
                bot_role=bot_role,
                task=task,
                context=context,
                session_id=session_id,
                origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                origin_room_id=origin_room_id,
            )
        )
        self._active_invocations[invocation_id] = task_handle

        # Get bot info for nice message
        bot_info = self.get_bot_info(bot_role)
        bot_title = bot_info.get("bot_name", bot_role) if bot_info else bot_role

        # Return immediately with confirmation
        return f"@{bot_role} ({bot_title}) is on the task. I'll share the results when ready."

    async def _process_invocation(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        context: Optional[str],
        session_id: str,
        origin_channel: str,
        origin_chat_id: str,
        origin_room_id: str | None,
    ) -> None:
        """Process a bot invocation and announce result when complete."""
        result: str = ""
        status = "ok"

        try:
            # Build system prompt for this bot
            system_prompt = await self._build_bot_system_prompt(bot_role, task)

            # Build user message
            user_message = task
            if context:
                user_message = f"Context from Leader:\n{context}\n\n---\n\nTask:\n{task}"

            # Process through LLM
            response = await self._call_bot_llm(
                bot_role,
                system_prompt,
                user_message,
                session_id,
                room_id=origin_room_id,
            )
            result = response or "Task completed but no response generated."

            logger.info(f"Async invocation {invocation_id} completed")

            # Log the bot's response
            self._log_invocation_response(invocation_id, bot_role, task, result)

        except Exception as e:
            logger.error(f"Async invocation {invocation_id} failed: {e}")
            result = f"Error: {str(e)}"
            status = "error"
            self._log_invocation_error(invocation_id, bot_role, task, str(e))
        finally:
            # Cleanup
            self._active_invocations.pop(invocation_id, None)

            # Announce result back to main agent via system message
            await self._announce_result(
                invocation_id=invocation_id,
                bot_role=bot_role,
                task=task,
                result=result,
                origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                origin_room_id=origin_room_id,
                status=status,
            )

    async def _announce_result(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        result: str,
        origin_channel: str,
        origin_chat_id: str,
        origin_room_id: str | None,
        status: str,
    ) -> None:
        """Announce the bot result back to the main agent via system message."""
        bot_info = self.get_bot_info(bot_role)
        bot_title = bot_info.get("bot_name", bot_role) if bot_info else bot_role
        status_text = "completed" if status == "ok" else "failed"

        announce_content = f"""[Bot @{bot_role} ({bot_title}) {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like 'invocation' or task IDs."""

        # Inject as system message to trigger main agent
        msg = MessageEnvelope(
            channel="system",
            sender_id=f"invoke:{bot_role}",
            chat_id=f"{origin_channel}:{origin_chat_id}",
            content=announce_content,
            direction="inbound",
            sender_role="system",
            room_id=origin_room_id,
        )

        await self.bus.publish_inbound(msg)
        logger.debug(f"Invocation {invocation_id} announced result to {origin_channel}:{origin_chat_id}")

        self._update_room_task(invocation_id, status, result)

    def _update_room_task(self, invocation_id: str, status: str, result: str) -> None:
        mapping = self._invocation_task_map.pop(invocation_id, None)
        if not mapping:
            return
        try:
            from nanofolks.bots.room_manager import get_room_manager

            manager = get_room_manager()
            room = manager.get_room(mapping["room_id"])
            if not room:
                return
            task = room.get_task(mapping["task_id"])
            if not task:
                return
            new_status = "done" if status == "ok" else "blocked"
            room.update_task_status(task.id, new_status)
            task.metadata["last_result"] = (result or "")[:2000]
            manager._save_room(room)
            self._log_task_event(mapping["room_id"], "status", task, extra={"status": new_status})
        except Exception as e:
            logger.warning(f"Failed to update room task for invocation {invocation_id}: {e}")

    def _log_task_event(self, room_id: str, action: str, task: Any, reason: str | None = None,
                        extra: dict[str, Any] | None = None) -> None:
        if not self._memory_store:
            return
        try:
            import uuid
            from datetime import datetime

            from nanofolks.memory.models import Event
            from nanofolks.utils.ids import room_to_session_id

            metadata = {
                "task_id": task.id,
                "action": action,
                "owner": task.owner,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date,
            }
            if reason:
                metadata["reason"] = reason
            if extra:
                metadata.update(extra)

            content = (
                f"Task {action}: {task.title} "
                f"(owner: {task.owner}, status: {task.status})"
            )

            event = Event(
                id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                channel="internal",
                direction="internal",
                event_type="task",
                content=content,
                session_key=room_to_session_id(room_id),
                metadata=metadata,
            )
            self._memory_store.save_event(event)
        except Exception:
            return

    def _get_team_name(self) -> str:
        """Get current team name from config (cached)."""
        if self._cached_team_name:
            return self._cached_team_name

        try:
            from nanofolks.bots.appearance_config import get_appearance_config

            appearance = get_appearance_config()
            team_manager = appearance.team_manager
            if team_manager and team_manager.get_current_team_name():
                self._cached_team_name = team_manager.get_current_team_name() or "pirate_crew"
            else:
                self._cached_team_name = "pirate_crew"
        except Exception:
            self._cached_team_name = "pirate_crew"

        return self._cached_team_name

    def _get_team_profile(self, bot_role: str):
        """Get aggregated team profile for display purposes."""
        try:
            from nanofolks.teams import get_bot_team_profile

            team_name = self._get_team_name()
            return get_bot_team_profile(bot_role, team_name, workspace_path=self.workspace)
        except Exception:
            return None

    async def _build_bot_system_prompt(self, bot_role: str, task: str) -> str:
        """Build system prompt for the invoked bot."""
        from nanofolks.soul import SoulManager

        # Get bot's SOUL.md if exists
        soul_manager = SoulManager(self.workspace)
        soul_content = soul_manager.get_bot_soul(bot_role)

        # Build system prompt
        bot_info = self.get_bot_info(bot_role) or AVAILABLE_BOTS[bot_role]

        if soul_content:
            system_prompt = soul_content
        else:
            # Fallback to basic role
            system_prompt = f"""You are @{bot_role} ({bot_info['bot_name']}), a specialist bot.

Domain: {bot_info['domain']}
Role: {bot_info['description']}

You are a specialist focused on {bot_info['domain']} tasks.
Provide helpful, expert responses in your domain."""

        # Add task context
        system_prompt += """

You were invoked by the Leader (leader) to help with a task.
Focus only on your domain expertise and provide a helpful response.
"""

        return system_prompt

    def _create_bot_tool_registry(self, bot_role: str, allow_sidekicks: bool = True) -> "ToolRegistry":
        """Create a tool registry for a bot based on permissions.

        Args:
            bot_role: Name of the bot

        Returns:
            ToolRegistry configured for this bot
        """
        from nanofolks.agent.tools.factory import create_bot_registry
        from nanofolks.agent.tools.permissions import (
            get_permissions_from_agents,
            get_permissions_from_soul,
            merge_permissions,
        )
        from nanofolks.agent.tools.sidekicks import SidekickTool

        registry = create_bot_registry(
            workspace=self.workspace,
            bot_role=bot_role,
            brave_api_key=self.brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=self.restrict_to_workspace,
        )
        if allow_sidekicks and self.sidekick_config.enabled:
            try:
                perms = merge_permissions(
                    get_permissions_from_soul(bot_role, self.workspace),
                    get_permissions_from_agents(bot_role, self.workspace),
                )
                if perms.is_allowed("sidekick"):
                    registry.register(SidekickTool(invoker=self, parent_bot_role=bot_role))
            except Exception:
                registry.register(SidekickTool(invoker=self, parent_bot_role=bot_role))

        return registry

    async def _call_bot_llm(
        self,
        bot_role: str,
        system_prompt: str,
        user_message: str,
        session_id: str,
        room_id: str | None = None,
        max_tokens: int | None = None,
        allow_sidekicks: bool = True,
    ) -> str:
        """Call LLM with bot's context and execute tools if needed.

        If the bot has tool permissions, this will:
        1. Create a filtered tool registry
        2. Call LLM with tool definitions
        3. Execute any tool calls
        4. Feed results back to LLM
        5. Continue until no more tool calls
        """

        # Create tool registry for this bot
        tool_registry = self._create_bot_tool_registry(bot_role, allow_sidekicks=allow_sidekicks)
        tool_definitions = tool_registry.get_definitions()
        if room_id:
            room_task_tool = tool_registry.get("room_task")
            if room_task_tool and hasattr(room_task_tool, "set_context"):
                room_task_tool.set_context(room_id)
            sidekick_tool = tool_registry.get("sidekick")
            if sidekick_tool and hasattr(sidekick_tool, "set_context"):
                sidekick_tool.set_context(room_id)

        # Build initial messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Maximum tool call iterations to prevent infinite loops
        max_iterations = 10

        for iteration in range(max_iterations):
            # Call LLM
            response = await self.provider.chat(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                tools=tool_definitions if tool_definitions else None,
            )

            # Get content and tool calls
            content = response.content or ""
            tool_calls = getattr(response, 'tool_calls', None) or []

            # If no tool calls, return the response
            if not tool_calls:
                return content

            # Execute tool calls and add results to messages
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments

                # Parse arguments (could be string or dict)
                if isinstance(tool_args, str):
                    import json
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                # Execute tool
                logger.debug(f"[{bot_role}] Executing tool: {tool_name}")
                result = await tool_registry.execute(tool_name, tool_args)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": result,
                })

            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in tool_calls
                ],
            })

        # Max iterations reached, return last content
        logger.warning(f"[{bot_role}] Max tool iterations ({max_iterations}) reached")
        return content

    def _build_sidekick_context_packet(self, task: SidekickTaskEnvelope) -> str:
        def _format_dict(label: str, data: dict[str, Any]) -> str:
            if not data:
                return f"{label}:\n- (none)"
            lines = [f"{label}:"]
            for key, value in data.items():
                lines.append(f"- {key}: {value}")
            return "\n".join(lines)

        parts = [
            f"Goal:\n{task.goal}",
            _format_dict("Inputs", task.inputs),
            _format_dict("Constraints", task.constraints),
            f"Output format:\n{task.output_format}",
        ]
        packet = "\n\n".join(parts).strip()
        limit = max(0, int(self.sidekick_config.max_context_chars))
        if limit and len(packet) > limit:
            packet = packet[: max(0, limit - 15)].rstrip() + "...(truncated)"
        return packet

    async def _build_sidekick_system_prompt(self, bot_role: str) -> str:
        from nanofolks.soul import SoulManager

        soul_manager = SoulManager(self.workspace)
        soul_content = soul_manager.get_bot_soul(bot_role)

        bot_info = self.get_bot_info(bot_role) or AVAILABLE_BOTS[bot_role]

        if soul_content:
            system_prompt = soul_content
        else:
            system_prompt = f"""You are @{bot_role} ({bot_info['bot_name']}), a specialist bot.

Domain: {bot_info['domain']}
Role: {bot_info['description']}

You are a specialist focused on {bot_info['domain']} tasks.
Provide helpful, expert responses in your domain."""

        system_prompt += """

You are acting as a sidekick. Focus only on the task goal and produce the requested output format.
Be concise and practical. Do not mention sidekicks or internal IDs.
"""

        return system_prompt

    async def run_sidekicks(
        self,
        parent_bot_role: str,
        room_id: str,
        tasks: list[SidekickTaskEnvelope],
    ) -> list[SidekickResult]:
        """Run sidekick tasks for a bot with shared limits and context packets."""
        if not self.sidekick_config.enabled or not tasks:
            return []

        orchestrator = self._get_sidekick_orchestrator()

        # Log spawn requests
        self._log_sidekick_spawn(parent_bot_role, room_id, tasks)

        async def _runner(task: SidekickTaskEnvelope) -> SidekickResult:
            # Build sidekick system prompt + context packet
            system_prompt = await self._build_sidekick_system_prompt(parent_bot_role)
            user_message = self._build_sidekick_context_packet(task)

            # Use a clean, per-sidekick session id
            session_id = room_to_session_id(f"sidekick_{task.task_id}")

            response = await self._call_bot_llm(
                parent_bot_role,
                system_prompt,
                user_message,
                session_id,
                room_id=room_id,
                max_tokens=self.sidekick_config.max_tokens,
                allow_sidekicks=False,
            )

            return SidekickResult(
                task_id=task.task_id,
                status="success",
                summary=response or "",
                artifacts=[],
                notes="",
            )

        try:
            results = await orchestrator.run(tasks, _runner)
            task_map = {task.task_id: task for task in tasks}
            self._log_sidekick_results(parent_bot_role, room_id, results, task_map=task_map)
            return results
        except SidekickLimitError:
            self._log_sidekick_limit(parent_bot_role, room_id, tasks)
            return [
                SidekickResult(
                    task_id="limit",
                    status="failed",
                    summary="",
                    notes="Sidekick limit exceeded",
                    artifacts=[],
                )
            ]

    def format_sidekick_results(self, results: list[SidekickResult]) -> str:
        """Format sidekick results for a parent bot merge step."""
        if not results:
            return "Sidekick results: none."

        success = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status in {"failed", "timeout"})

        lines = [
            "Sidekick results (merge into your response; do not mention sidekicks):",
            f"Summary: {success} success, {failed} failed",
        ]

        for result in results:
            summary = result.summary.strip().replace("\n", " ")
            if summary:
                summary = summary[:300] + ("..." if len(summary) > 300 else "")
            else:
                summary = "(no summary)"
            note = f" [{result.notes}]" if result.notes else ""
            lines.append(f"- {result.task_id} ({result.status}): {summary}{note}")

        if failed:
            lines.append("Missing coverage: one or more sidekicks did not return results.")

        return "\n".join(lines)

    def _log_sidekick_spawn(
        self,
        parent_bot_role: str,
        room_id: str,
        tasks: list[SidekickTaskEnvelope],
    ) -> None:
        if not self.work_log_manager:
            return
        for task in tasks:
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="sidekick",
                message=f"Spawned sidekick task {task.task_id}",
                details={
                    "task_id": task.task_id,
                    "room_id": room_id,
                    "parent_bot_id": task.parent_bot_id,
                    "parent_bot_role": parent_bot_role,
                    "goal": task.goal[:500],
                    "output_format": task.output_format,
                },
                bot_name=parent_bot_role,
                triggered_by=parent_bot_role,
            )

    def _log_sidekick_results(
        self,
        parent_bot_role: str,
        room_id: str,
        results: list[SidekickResult],
        *,
        task_map: dict[str, SidekickTaskEnvelope] | None = None,
    ) -> None:
        if not self.work_log_manager:
            return
        for result in results:
            task = task_map.get(result.task_id) if task_map else None
            self.work_log_manager.log(
                level=LogLevel.INFO if result.status == "success" else LogLevel.WARNING,
                category="sidekick",
                message=f"Sidekick task {result.task_id} {result.status}",
                details={
                    "task_id": result.task_id,
                    "room_id": room_id,
                    "parent_bot_id": task.parent_bot_id if task else None,
                    "status": result.status,
                    "summary": result.summary[:500],
                    "artifacts_count": len(result.artifacts or []),
                    "notes": result.notes,
                },
                duration_ms=result.duration_ms,
                bot_name=parent_bot_role,
                triggered_by=parent_bot_role,
            )

    def _log_sidekick_limit(
        self,
        parent_bot_role: str,
        room_id: str,
        tasks: list[SidekickTaskEnvelope],
    ) -> None:
        if not self.work_log_manager:
            return
        parent_bot_id = tasks[0].parent_bot_id if tasks else None
        task_ids = [task.task_id for task in tasks] if tasks else []
        self.work_log_manager.log(
            level=LogLevel.WARNING,
            category="sidekick",
            message="Sidekick limit exceeded",
            details={
                "room_id": room_id,
                "parent_bot_role": parent_bot_role,
                "parent_bot_id": parent_bot_id,
                "task_ids": task_ids,
                "requested": len(tasks),
                "max_per_bot": self.sidekick_config.max_sidekicks_per_bot,
                "max_per_room": self.sidekick_config.max_sidekicks_per_room,
            },
            bot_name=parent_bot_role,
            triggered_by=parent_bot_role,
        )

    def list_available_bots(self) -> dict:
        """List all bots that can be invoked."""
        return AVAILABLE_BOTS.copy()

    def get_bot_info(self, bot_role: str) -> Optional[dict]:
        """Get information about a specific bot."""
        base_info = AVAILABLE_BOTS.get(bot_role, {}).copy()

        profile = self._get_team_profile(bot_role)
        if profile:
            display_name = profile.bot_name or profile.bot_title or bot_role
            base_info.update({
                "bot_name": profile.bot_name or display_name,
                "bot_title": profile.bot_title,
                "emoji": profile.emoji,
                "team_name": profile.team_name,
            })

        return base_info or None

    def _log_invocation_request(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        context: Optional[str] = None,
    ) -> None:
        """Log a bot invocation request using work_log_manager."""
        if not self.work_log_manager:
            return

        try:
            # Log as a bot message with mention
            self.work_log_manager.log_bot_message(
                bot_role="leader",
                message=f"Invoking @{bot_role} with task: {task[:200]}...",
                mentions=[f"@{bot_role}"]
            )

            # Log as a handoff (bot-to-bot transfer)
            self.work_log_manager.log(
                level=LogLevel.HANDOFF,
                category="bot_invocation",
                message=f"Delegating task to @{bot_role}",
                details={
                    "invocation_id": invocation_id,
                    "target_bot": bot_role,
                    "task": task[:500],
                    "context": context[:500] if context else None,
                    "expected_deliverables": ["response"],
                    "context_transferred": bool(context),
                    "requires_approval": False,
                },
                triggered_by="leader"
            )
        except Exception as e:
            logger.warning(f"Failed to log invocation request: {e}")

    def _log_invocation_response(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        response: str,
    ) -> None:
        """Log a bot's response to an invocation."""
        if not self.work_log_manager:
            return

        try:
            # Log the bot's response
            self.work_log_manager.log_bot_message(
                bot_role=bot_role,
                message=f"Response to task: {task[:100]}...\n\n{response[:1000]}...",
                mentions=[f"@{bot_role}"]
            )

            # Log completion
            self.work_log_manager.log(
                level=LogLevel.INFO,
                category="bot_invocation",
                message=f"@{bot_role} completed the task",
                details={
                    "target_bot": bot_role,
                    "task": task[:500],
                    "response_length": len(response),
                },
                triggered_by=f"@{bot_role}"
            )

            self.work_log_manager.log(
                level=LogLevel.HANDOFF,
                category="bot_invocation_complete",
                message=f"@{bot_role} handoff completed",
                details={
                    "invocation_id": invocation_id,
                    "target_bot": bot_role,
                    "task": task[:500],
                    "actual_deliverables": ["response"],
                    "completed": True,
                    "status": "ok",
                    "response_length": len(response),
                },
                triggered_by=f"@{bot_role}"
            )
        except Exception as e:
            logger.warning(f"Failed to log invocation response: {e}")

    def _log_invocation_error(
        self,
        invocation_id: str,
        bot_role: str,
        task: str,
        error: str,
    ) -> None:
        """Log an error during bot invocation."""
        if not self.work_log_manager:
            return

        try:
            self.work_log_manager.log(
                level=LogLevel.ERROR,
                category="bot_invocation",
                message=f"@{bot_role} invocation failed: {error}",
                details={
                    "target_bot": bot_role,
                    "task": task[:500],
                    "error": error,
                },
                triggered_by="leader"
            )

            self.work_log_manager.log(
                level=LogLevel.HANDOFF,
                category="bot_invocation_complete",
                message=f"@{bot_role} handoff failed",
                details={
                    "invocation_id": invocation_id,
                    "target_bot": bot_role,
                    "task": task[:500],
                    "actual_deliverables": [],
                    "completed": True,
                    "status": "error",
                    "error": error,
                },
                triggered_by=f"@{bot_role}"
            )
        except Exception as e:
            logger.warning(f"Failed to log invocation error: {e}")
