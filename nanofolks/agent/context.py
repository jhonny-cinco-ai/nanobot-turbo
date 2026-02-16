"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from nanofolks.memory.store import TurboMemoryStore
from nanofolks.memory.embeddings import EmbeddingProvider
from nanofolks.agent.skills import SkillsLoader
from nanofolks.config.loader import load_config
from nanofolks.soul import SoulManager
from nanofolks.security.keyvault import get_keyvault


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
            # Initialize embedding provider for semantic search
            self.embedding_provider = EmbeddingProvider(config.memory.embedding)
        else:
            self.memory = None
            self.embedding_provider = None
            
        self.skills = SkillsLoader(workspace)
        self.soul_manager = SoulManager(workspace)
        
        # Cache for cleaned file content: {file_path: (mtime, cleaned_content)}
        self._content_cache: dict[str, tuple[float, str]] = {}
    
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
    
    def build_api_keys_section(self) -> str:
        """Build section showing available API keys (symbolic references only).
        
        This shows the LLM which keys are available using symbolic references
        like {{brave_key}} instead of actual keys. The actual keys are resolved
        at execution time.
        
        Returns:
            Formatted API keys section for system prompt, or empty string
        """
        try:
            keyvault = get_keyvault()
            available_keys = keyvault.list_references()
            
            if not available_keys:
                return ""
            
            # Build the section
            lines = ["# Available API Keys", ""]
            lines.append("The following API keys are available for tool execution:")
            lines.append("")
            
            for key_ref in available_keys:
                # Extract key name from {{key_name}}
                key_name = key_ref.strip("{}")
                lines.append(f"- {key_name}: {key_ref} (configured)")
            
            lines.append("")
            lines.append("Use these symbolic references when calling tools that require API keys.")
            lines.append("Example: To use web search, pass api_key=\"{{brave_key}}\"")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.debug(f"Could not build API keys section: {e}")
            return ""
    
    def _get_tool_permissions(self, bot_name: str) -> Optional[str]:
        """Get tool permissions section for a bot.
        
        Args:
            bot_name: Bot name to get permissions for
            
        Returns:
            Formatted tool permissions section or None
        """
        from nanofolks.agent.tools.permissions import (
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
        """Build identity section customized for the bot using IDENTITY.md files.
        
        This method loads the bot's personality from IDENTITY.md (workspace-specific
        or theme template), NOT from hardcoded templates. This enables the multi-bot
        architecture where each bot has unique personality, relationships, and quirks.
        
        Falls back to generic template only if no IDENTITY.md exists.
        """
        from nanofolks.models import get_role_card
        
        safe_bot_name = bot_name or "leader"
        is_leader = safe_bot_name == "leader"
        
        # Try to load IDENTITY.md for this bot
        identity_content = self._load_identity_for_bot(safe_bot_name)
        
        if identity_content:
            # Use the loaded identity (from workspace or theme template)
            # Remove the "## IDENTITY.md" header to get just the content
            if identity_content.startswith("## IDENTITY.md"):
                identity_body = identity_content.split("\n\n", 1)[1] if "\n\n" in identity_content else ""
            else:
                identity_body = identity_content
            
            # Add runtime context after the identity
            runtime_context = f"""
## Current Context
Time: {now} ({tz})
Runtime: {runtime}
Workspace: {workspace_path}
Bot Path: {workspace_path}/bots/{safe_bot_name}/"""
            
            return identity_body + runtime_context
        
        # Fallback: Generate from role_card if no IDENTITY.md
        role_card = get_role_card(safe_bot_name)
        
        if role_card:
            # Build identity from role card + generic structure
            domain = role_card.domain.value if role_card.domain else "specialist"
            capabilities = role_card.capabilities
            
            tools_list = []
            if capabilities.can_read_files:
                tools_list.append("file operations")
            if capabilities.can_execute_code:
                tools_list.append("code execution")
            if capabilities.can_use_shell:
                tools_list.append("shell commands")
            if capabilities.can_browse_web:
                tools_list.append("web access")
            
            tools_str = ", ".join(tools_list) if tools_list else "specialized tools"
            
            return f"""# @{safe_bot_name}

You are @{safe_bot_name}, a {domain} specialist on the nanofolks team.

## Your Role
Your domain is {domain}. You have expertise in: {tools_str}
Focus on your area of specialization and provide expert responses.

## Tools
You have access to: {tools_str}
Use them to accomplish tasks within your domain.

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}/bots/{safe_bot_name}/

## Guidelines
- Stay focused on {domain} expertise
- Provide detailed, expert responses in your area
- Use available tools to accomplish tasks
- Suggest invoking another bot if task is outside your expertise"""
        
        # Ultimate fallback: generic bot
        return f"""# @{safe_bot_name}

You are @{safe_bot_name}, a specialist bot on the nanofolks team.

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}/bots/{safe_bot_name}/"""
    
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
            
            # Other bootstrap files (USER.md, TOOLS.md)
            file_path = self.workspace / filename
            try:
                cleaned_content = self._get_cached_or_clean_file(file_path, filename)
                if cleaned_content:
                    parts.append(f"## {filename}\n\n{cleaned_content}")
            except Exception as e:
                logger.warning(f"Failed to load {filename}: {e}")
                continue
        
        return "\n\n".join(parts) if parts else ""
    
    def _load_agents_for_bot(self, bot_name: Optional[str] = None) -> Optional[str]:
        """Load AGENTS.md for a bot.
        
        Args:
            bot_name: Bot name to load specific AGENTS
        
        Returns:
            Formatted AGENTS content or None
        """
        # If no bot specified, return None
        if not bot_name:
            return None
        
        # Load bot-specific AGENTS.md
        try:
            agents_content = self.soul_manager.get_bot_agents(bot_name)
            
            if agents_content:
                # Use caching method to clean markdown
                # Create a temporary file path for cache key
                temp_path = self.workspace / "bots" / bot_name / "AGENTS.md"
                cleaned_content = self._get_cached_or_clean_file(temp_path, "AGENTS.md")
                if cleaned_content:
                    return f"## AGENTS.md (Bot: {bot_name})\n\n{cleaned_content}"
        except Exception as e:
            logger.warning(f"Failed to load AGENTS.md for {bot_name}: {e}")
        
        return None
    
    def _load_soul_for_bot(self, bot_name: Optional[str] = None) -> Optional[str]:
        """Load SOUL.md for a bot.
        
        Args:
            bot_name: Bot name to load specific SOUL
        
        Returns:
            Formatted SOUL content or None
        """
        # If no bot specified, return None
        if not bot_name:
            return None
        
        # Load bot-specific SOUL.md
        try:
            soul_content = self.soul_manager.get_bot_soul(bot_name)
            
            if soul_content:
                # Use caching method to clean markdown
                temp_path = self.workspace / "bots" / bot_name / "SOUL.md"
                cleaned_content = self._get_cached_or_clean_file(temp_path, "SOUL.md")
                if cleaned_content:
                    return f"## SOUL.md (Bot: {bot_name})\n\n{cleaned_content}"
        except Exception as e:
            logger.warning(f"Failed to load SOUL.md for {bot_name}: {e}")
        
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
            try:
                cleaned_content = self._get_cached_or_clean_file(identity_file, "IDENTITY.md")
                if cleaned_content:
                    return f"## IDENTITY.md\n\n{cleaned_content}"
            except Exception as e:
                logger.warning(f"Failed to load workspace IDENTITY.md: {e}")
            return None
        
        # Load bot-specific IDENTITY.md if it exists in workspace
        bot_identity_file = self.workspace / "bots" / bot_name / "IDENTITY.md"
        try:
            if bot_identity_file.exists():
                cleaned_content = self._get_cached_or_clean_file(bot_identity_file, "IDENTITY.md")
                if cleaned_content:
                    return f"## IDENTITY.md (Bot: {bot_name})\n\n{cleaned_content}"
        except Exception as e:
            logger.warning(f"Failed to load IDENTITY.md for {bot_name}: {e}")
        
        # Fall back to template IDENTITY.md from theme
        try:
            from nanofolks.templates import get_identity_template_for_bot
            template_content = get_identity_template_for_bot(bot_name)
            if template_content:
                # For templates, create a temp path for caching
                temp_path = self.workspace / ".cache" / f"identity_template_{bot_name}.md"
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_text(template_content)
                cleaned_content = self._get_cached_or_clean_file(temp_path, "IDENTITY.md")
                if cleaned_content:
                    return f"## IDENTITY.md (Bot: {bot_name})\n\n{cleaned_content}"
        except Exception as e:
            logger.warning(f"Failed to load IDENTITY.md template for {bot_name}: {e}")
        
        return None
    
    def _get_cached_or_clean_file(self, file_path: Path, filename: str) -> Optional[str]:
        """Get cleaned file content with caching based on modification time.
        
        This method caches cleaned markdown content to avoid re-cleaning
        files that haven't changed, significantly improving performance
        for long conversations.
        
        Args:
            file_path: Path to the markdown file
            filename: Name of the file (for cleaner selection)
            
        Returns:
            Cleaned content string or None if file can't be read
        """
        from nanofolks.utils.markdown_cleaner import (
            clean_markdown_content, 
            compact_agents_content,
            compact_soul_content
        )
        
        try:
            # Get current file modification time
            mtime = file_path.stat().st_mtime
            cache_key = str(file_path.resolve())
            
            # Check if we have cached content and it's still valid
            if cache_key in self._content_cache:
                cached_mtime, cached_content = self._content_cache[cache_key]
                if cached_mtime == mtime:
                    logger.debug(f"Using cached content for {filename}")
                    return cached_content
            
            # File is new or modified, need to clean it
            content = file_path.read_text(encoding="utf-8")
            
            # Select appropriate cleaner based on file type
            if "AGENTS" in filename.upper():
                cleaned_content = compact_agents_content(content)
            elif "SOUL" in filename.upper() or "IDENTITY" in filename.upper():
                cleaned_content = compact_soul_content(content)
            else:
                cleaned_content = clean_markdown_content(content, aggressive=False)
            
            # Validate: warn if cleaned content is <50% of original
            original_len = len(content)
            cleaned_len = len(cleaned_content)
            if cleaned_len < original_len * 0.5:
                logger.warning(
                    f"File {filename} was reduced to {cleaned_len/original_len:.1%} of original size. "
                    "May have lost important content."
                )
            
            # Cache the cleaned content with current mtime
            self._content_cache[cache_key] = (mtime, cleaned_content)
            
            return cleaned_content
            
        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            return None
        except PermissionError:
            logger.warning(f"Permission denied reading: {file_path}")
            return None
        except UnicodeDecodeError as e:
            logger.warning(f"Failed to decode {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading {file_path}: {e}")
            return None
    
    def get_semantic_memory_context(
        self, 
        query: str, 
        limit: int = 10, 
        threshold: float = 0.5,
        include_recent: bool = True,
        recent_limit: int = 5
    ) -> str:
        """Get memory context using semantic search for relevance.
        
        This method retrieves memories based on semantic similarity to the query,
        rather than just recency. It combines:
        1. Semantically relevant events (via embedding similarity)
        2. Important entities related to the query
        3. Recent activity (optional, for context continuity)
        
        Args:
            query: The user's query to search for relevant memories
            limit: Maximum number of semantically relevant events to retrieve
            threshold: Minimum similarity score (0-1) for semantic search
            include_recent: Whether to also include recent events
            recent_limit: Number of recent events to include if include_recent is True
            
        Returns:
            Formatted memory context string with relevant information
        """
        if not self.memory or not self.embedding_provider:
            return ""
        
        parts = []
        
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_provider.embed(query)
            
            # Search for semantically relevant events
            relevant_events = self.memory.search_events(
                query_embedding=query_embedding,
                limit=limit,
                threshold=threshold
            )
            
            if relevant_events:
                parts.append("## Relevant Past Activity")
                for event, similarity in relevant_events:
                    relevance = "high" if similarity > 0.7 else "medium" if similarity > 0.5 else "low"
                    parts.append(
                        f"- [{event.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                        f"({relevance} relevance) {event.event_type}: {event.content[:150]}"
                    )
            
            # Search for relevant entities using semantic similarity
            entities = self.memory.get_all_entities()
            if entities and query_embedding:
                # Get embeddings for entity names and calculate similarity
                from nanofolks.memory.embeddings import cosine_similarity
                
                relevant_entities = []
                for entity in entities:
                    if entity.name:
                        # Simple text matching for now (could be enhanced with entity embeddings)
                        entity_text = f"{entity.name} {entity.description or ''}"
                        entity_lower = entity_text.lower()
                        query_lower = query.lower()
                        
                        # Check if entity is mentioned in query or vice versa
                        if (entity.name.lower() in query_lower or 
                            any(word in entity_lower for word in query_lower.split()[:5])):
                            relevant_entities.append(entity)
                
                # Sort by event count (importance) and take top 5
                relevant_entities.sort(key=lambda e: e.event_count, reverse=True)
                relevant_entities = relevant_entities[:5]
                
                if relevant_entities:
                    parts.append("\n## Related Entities")
                    for entity in relevant_entities:
                        parts.append(
                            f"- {entity.name} ({entity.entity_type}): "
                            f"{entity.description or 'No description'} "
                            f"[{entity.event_count} interactions]"
                        )
            
            # Optionally include recent activity for context continuity
            if include_recent:
                # Get recent events from the default session or all events
                recent_events = []
                try:
                    # Try to get events by session (default session)
                    recent_events = self.memory.get_events_by_session(session_key="default", limit=recent_limit)
                except:
                    # Fallback to getting all events
                    recent_events = []
                
                # Filter out events already included in semantic search
                relevant_event_ids = {e[0].id for e in relevant_events}
                new_recent = [e for e in recent_events if e.id not in relevant_event_ids]
                
                if new_recent:
                    parts.append("\n## Recent Activity")
                    for event in new_recent:
                        parts.append(
                            f"- [{event.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                            f"{event.event_type}: {event.content[:100]}"
                        )
            
            # Get relevant learnings
            learnings = self.memory.get_all_learnings(active_only=True)
            if learnings:
                # Filter learnings by relevance to query
                query_words = set(query.lower().split())
                relevant_learnings = []
                
                for learning in learnings[:20]:  # Limit to first 20 for performance
                    learning_text = learning.content.lower()
                    if any(word in learning_text for word in query_words):
                        relevant_learnings.append(learning)
                
                if relevant_learnings:
                    parts.append("\n## Relevant Learned Preferences")
                    for learning in relevant_learnings[:3]:
                        parts.append(f"- {learning.content}")
            
            # Get latest summary if available
            summaries = self.memory.get_all_summary_nodes()
            if summaries:
                latest = max(summaries, key=lambda s: s.last_updated or datetime.min)
                parts.append(f"\n## Conversation Summary\n{latest.summary}")
            
        except Exception as e:
            # Fall back to recent events if semantic search fails
            logger.warning(f"Semantic memory search failed: {e}. Falling back to recent events.")
            return self._get_fallback_memory_context()
        
        return "\n".join(parts) if parts else ""
    
    def _get_fallback_memory_context(self) -> str:
        """Fallback to time-based memory context if semantic search fails."""
        if not self.memory:
            return ""
        
        return self.memory.get_memory_context(limit=20)
    
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
        room_id: str | None = None,
        room_type: str | None = None,
        participants: list[str] | None = None,
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
            room_id: Current room identifier (e.g., "general", "project-alpha").
            room_type: Type of room (open, project, direct, coordination).
            participants: List of bots participating in the room.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt with optional bot personality
        system_prompt = self.build_system_prompt(
            skill_names=skill_names,
            bot_name=bot_name
        )
        
        # Add API keys section (symbolic references only - keys never exposed to LLM)
        api_keys_section = self.build_api_keys_section()
        if api_keys_section:
            system_prompt += f"\n\n{api_keys_section}"
        
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        
        # Add room context if provided
        if room_id and room_id != "default":
            system_prompt += f"\n\n## Room Context\nRoom: #{room_id}"
            if room_type:
                system_prompt += f"\nType: {room_type}"
            if participants:
                system_prompt += f"\nParticipants: {', '.join(participants)}"
            system_prompt += "\n\nYou are collaborating in this room with other bots. Use @botname to mention specific bots when you need their expertise."
        
        # Add memory context if provided
        if memory_context:
            system_prompt += f"\n\n## Memory Context\n{memory_context}"
        elif self.memory and self.embedding_provider:
            # Generate semantic memory context based on current message
            try:
                semantic_memory = self.get_semantic_memory_context(
                    query=current_message,
                    limit=10,
                    threshold=0.5,
                    include_recent=True,
                    recent_limit=3
                )
                if semantic_memory:
                    system_prompt += f"\n\n## Memory Context\n{semantic_memory}"
            except Exception as e:
                logger.warning(f"Failed to generate semantic memory context: {e}")
        
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
