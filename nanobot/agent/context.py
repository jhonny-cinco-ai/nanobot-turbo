"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from pathlib import Path
from typing import Any, Optional

from nanobot.memory.store import TurboMemoryStore
from nanobot.agent.skills import SkillsLoader
from nanobot.config.loader import load_config
from nanobot.soul import SoulManager


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM. Supports bot-specific SOUL.md loading.
    """
    
    # Bootstrap files - AGENTS.md and SOUL.md are loaded per-bot, not workspace-level
    BOOTSTRAP_FILES = ["USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        
        # Initialize TurboMemoryStore with config
        config = load_config()
        if config.memory.enabled:
            self.memory = TurboMemoryStore(config.memory, workspace)
        else:
            self.memory = None
            
        self.skills = SkillsLoader(workspace)
        self.soul_manager = SoulManager(workspace)
    
    def build_system_prompt(
        self,
        skill_names: list[str] | None = None,
        bot_name: Optional[str] = None
    ) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.
        
        Args:
            skill_names: Optional list of skills to include.
            bot_name: Optional bot name for personality injection.
        
        Returns:
            Complete system prompt.
        """
        parts = []
        
        # Core identity (pass bot_name for customization)
        parts.append(self._get_identity(bot_name))
        
        # Bootstrap files (with optional bot-specific SOUL)
        bootstrap = self._load_bootstrap_files(bot_name=bot_name)
        if bootstrap:
            parts.append(bootstrap)
        
        # Tool permissions (per-bot restrictions)
        if bot_name:
            tool_perms = self._get_tool_permissions(bot_name)
            if tool_perms:
                parts.append(tool_perms)
        
        # Memory context
        if self.memory:
            memory = self.memory.get_memory_context()
            if memory:
                parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_tool_permissions(self, bot_name: str) -> Optional[str]:
        """Get tool permissions section for a bot.
        
        Args:
            bot_name: Bot name to get permissions for
            
        Returns:
            Formatted tool permissions section or None
        """
        from nanobot.agent.tools.permissions import (
            get_permissions_from_soul,
            get_permissions_from_agents,
            merge_permissions,
        )
        
        soul_perms = get_permissions_from_soul(bot_name, self.workspace)
        agents_perms = get_permissions_from_agents(bot_name, self.workspace)
        
        perms = merge_permissions(soul_perms, agents_perms)
        
        # If no permissions defined, return None
        if not perms.allowed_tools and not perms.denied_tools:
            return None
        
        sections = []
        
        if perms.allowed_tools:
            tools_list = ", ".join(sorted(perms.allowed_tools))
            sections.append(f"## Available Tools\n\nYou have access to: {tools_list}")
        
        if perms.denied_tools:
            tools_list = ", ".join(sorted(perms.denied_tools))
            sections.append(f"## Restricted Tools\n\nYou do NOT have access to: {tools_list}")
        
        if perms.custom_tools:
            custom_list = "\n".join(f"- **{name}**: {desc}" for name, desc in perms.custom_tools.items())
            sections.append(f"## Custom Tools\n\n{custom_list}")
        
        return "---\n\n" + "\n\n".join(sections)
    
    def _get_identity(self, bot_name: Optional[str] = None) -> str:
        """Get the core identity section customized for the bot."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        
        return self._build_identity(bot_name, now, tz, workspace_path, runtime)
    
    def _build_identity(
        self,
        bot_name: Optional[str],
        now: str,
        tz: str,
        workspace_path: str,
        runtime: str,
    ) -> str:
        """Build identity section customized for the bot."""
        is_leader = bot_name == "nanobot" or bot_name is None
        
        if is_leader:
            # Leader (nanobot) - full capabilities
            return f"""# nanobot 🐈

You are nanobot, the team leader and coordinator. You help users by orchestrating specialist bots when needed.

## Your Role
You are the main interface for the user. You can:
- Handle user requests directly for simple tasks
- Delegate complex tasks to specialist bots (@researcher, @coder, @social, @creative, @auditor)
- Synthesize results from multiple bots into coherent responses

## Tools
You have access to:
- File operations (read, write, edit, list)
- Shell commands (exec)
- Web access (search, fetch)
- Messaging (message)
- Invoke specialist bots (invoke)

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Team configurations: {workspace_path}/bots/
- SQLite memory: {workspace_path}/memory/memory.db
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## Guidelines
- For simple tasks, respond directly
- For complex tasks, use `invoke` to delegate to specialist bots
- Always synthesize results when multiple bots are involved
- Be helpful, accurate, and concise"""
        
        else:
            # Specialist bot
            bot_titles = {
                "researcher": "Navigator",
                "coder": "Gunner",
                "social": "Lookout",
                "creative": "Artist",
                "auditor": "Quartermaster",
            }
            safe_bot_name = bot_name or "specialist"
            title = bot_titles.get(safe_bot_name, safe_bot_name.title())
            
            return f"""# @{safe_bot_name} ({title})

You are @{safe_bot_name}, a specialist bot on the nanobot team.

## Your Role
You are a domain specialist. Focus on your area of expertise and provide expert responses.

## Tools
You have access to tools relevant to your role. Use them to accomplish your tasks.

## Current Time
{now} ({tz})

## Workspace
Your workspace is at: {workspace_path}/bots/{safe_bot_name}/
- HEARTBEAT.md: Your periodic tasks

## Guidelines
- Stay focused on your domain expertise
- Provide detailed, expert responses in your area
- Use available tools to gather information and take actions
- If a task is outside your expertise, suggest invoking another bot"""
    
    def _load_bootstrap_files(self, bot_name: Optional[str] = None) -> str:
        """Load bootstrap files with bot-specific SOUL, AGENTS, and IDENTITY if available.
        
        Args:
            bot_name: Optional bot name for personality injection.
        
        Returns:
            Formatted bootstrap content.
        """
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            # Special handling for SOUL.md with bot-specific support
            if filename == "SOUL.md":
                soul_content = self._load_soul_for_bot(bot_name)
                if soul_content:
                    parts.append(soul_content)
                continue
            
            # Special handling for AGENTS.md with bot-specific support
            if filename == "AGENTS.md":
                agents_content = self._load_agents_for_bot(bot_name)
                if agents_content:
                    parts.append(agents_content)
                continue
            
            # Special handling for IDENTITY.md with bot-specific support
            if filename == "IDENTITY.md":
                identity_content = self._load_identity_for_bot(bot_name)
                if identity_content:
                    parts.append(identity_content)
                continue
            
            # Other bootstrap files
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _load_agents_for_bot(self, bot_name: Optional[str] = None) -> Optional[str]:
        """Load AGENTS.md for a bot.
        
        Args:
            bot_name: Bot name to load specific AGENTS
        
        Returns:
            Formatted AGENTS content or None
        """
        from nanobot.soul import SoulManager
        
        # If no bot specified, no AGENTS content (workspace-level is deprecated)
        if not bot_name:
            return None
        
        # Load bot-specific AGENTS.md
        soul_manager = SoulManager(self.workspace)
        agents_content = soul_manager.get_bot_agents(bot_name)
        
        if agents_content:
            return f"## AGENTS.md (Bot: {bot_name})\n\n{agents_content}"
        
        return None
    
    def _load_soul_for_bot(self, bot_name: Optional[str] = None) -> Optional[str]:
        """Load SOUL.md for a bot.
        
        Args:
            bot_name: Bot name to load specific SOUL
        
        Returns:
            Formatted SOUL content or None
        """
        # If no bot specified, no SOUL content (workspace-level is deprecated)
        if not bot_name:
            return None
        
        # Load bot-specific SOUL.md
        soul_content = self.soul_manager.get_bot_soul(bot_name)
        if soul_content:
            return f"## SOUL.md (Bot: {bot_name})\n\n{soul_content}"
        
        return None
    
    def _load_identity_for_bot(self, bot_name: Optional[str] = None) -> Optional[str]:
        """Load IDENTITY.md for a bot.
        
        Args:
            bot_name: Bot name to load specific IDENTITY
        
        Returns:
            Formatted IDENTITY content or None
        """
        # If no bot specified, try workspace-level IDENTITY
        if not bot_name:
            identity_file = self.workspace / "IDENTITY.md"
            if identity_file.exists():
                content = identity_file.read_text(encoding="utf-8")
                return f"## IDENTITY.md\n\n{content}"
            return None
        
        # Load bot-specific IDENTITY.md if it exists in workspace
        bot_identity_file = self.workspace / "bots" / bot_name / "IDENTITY.md"
        if bot_identity_file.exists():
            content = bot_identity_file.read_text(encoding="utf-8")
            return f"## IDENTITY.md (Bot: {bot_name})\n\n{content}"
        
        # Fall back to template IDENTITY.md from theme
        from nanobot.templates import get_identity_template_for_bot
        template_content = get_identity_template_for_bot(bot_name)
        if template_content:
            return f"## IDENTITY.md (Bot: {bot_name})\n\n{template_content}"
        
        return None
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        bot_name: Optional[str] = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        memory_context: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            bot_name: Optional bot name for personality injection.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.
            memory_context: Optional memory context from previous conversations.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt with optional bot personality
        system_prompt = self.build_system_prompt(
            skill_names=skill_names,
            bot_name=bot_name
        )
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        
        # Add memory context if provided
        if memory_context:
            system_prompt += f"\n\n## Memory Context\n{memory_context}"
        
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
            reasoning_content: Thinking output (Kimi, DeepSeek-R1, etc.).
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        # Thinking models reject history without this
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        
        messages.append(msg)
        return messages
