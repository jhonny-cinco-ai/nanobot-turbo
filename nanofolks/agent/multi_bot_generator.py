"""Multi-bot response generator for simultaneous bot responses.

This module handles generating responses from multiple bots in parallel
for @all and @crew mentions, creating a communal multi-bot experience.
"""

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from nanofolks.bots.dispatch import DispatchTarget
from nanofolks.providers.base import LLMProvider


@dataclass
class BotResponse:
    """Response from a single bot."""
    bot_name: str
    content: str
    confidence: float = 0.8
    response_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiBotResponseGenerator:
    """Generate responses from multiple bots simultaneously."""
    
    # Bot emoji mapping for display
    BOT_EMOJIS = {
        "leader": "👑",
        "researcher": "📊",
        "coder": "💻",
        "social": "📱",
        "creative": "🎨",
        "auditor": "🔍",
    }
    
    # Bot color mapping for CLI
    BOT_COLORS = {
        "leader": "blue",
        "researcher": "cyan",
        "coder": "green",
        "social": "magenta",
        "creative": "yellow",
        "auditor": "red",
    }
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        room_theme: str = "default",
    ):
        """Initialize the multi-bot response generator.
        
        Args:
            provider: LLM provider for generating responses
            workspace: Workspace path for loading bot identities
            model: Model to use (defaults to provider default)
            temperature: Temperature for response generation
            max_tokens: Max tokens per bot response
            room_theme: Theme for affinity customization
        """
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.room_theme = room_theme
        
        self._affinity_builder = None
        self._cross_ref_injector = None
    
    @property
    def affinity_builder(self):
        """Lazy-load affinity context builder."""
        if self._affinity_builder is None:
            from nanofolks.agent.affinity_context import AffinityContextBuilder
            self._affinity_builder = AffinityContextBuilder(self.workspace)
        return self._affinity_builder
    
    @property
    def cross_ref_injector(self):
        """Lazy-load cross-reference injector."""
        if self._cross_ref_injector is None:
            from nanofolks.agent.cross_reference import CrossReferenceInjector
            self._cross_ref_injector = CrossReferenceInjector(self.room_theme)
        return self._cross_ref_injector
    
    async def generate_responses(
        self,
        user_message: str,
        bot_names: List[str],
        mode: DispatchTarget,
        room_context: Optional[Dict[str, Any]] = None,
    ) -> List[BotResponse]:
        """Generate responses from multiple bots in parallel.
        
        Args:
            user_message: The user's message
            bot_names: List of bot names to generate responses from
            mode: Dispatch mode (MULTI_BOT or CREW_CONTEXT)
            room_context: Optional room context information
            
        Returns:
            List of BotResponse objects
        """
        logger.info(f"Generating multi-bot responses from: {', '.join(bot_names)} (mode: {mode.value})")
        
        # Create tasks for each bot
        tasks = []
        for bot_name in bot_names:
            task = self._generate_single_response(
                bot_name=bot_name,
                user_message=user_message,
                other_bots=[b for b in bot_names if b != bot_name],
                mode=mode,
                room_context=room_context,
            )
            tasks.append(task)
        
        # Execute all in parallel
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = (time.time() - start_time) * 1000
        
        # Process results
        bot_responses = []
        for i, result in enumerate(responses):
            bot_name = bot_names[i]
            
            if isinstance(result, Exception):
                logger.error(f"[{bot_name}] Failed to generate response: {result}")
                bot_responses.append(BotResponse(
                    bot_name=bot_name,
                    content=f"❌ I encountered an error while processing your request.",
                    confidence=0.0,
                    response_time_ms=0,
                    metadata={"error": str(result)}
                ))
            else:
                bot_responses.append(result)
        
        logger.info(f"Generated {len(bot_responses)} responses in {total_time:.0f}ms")
        
        # Inject cross-references between bots
        bot_responses = self.cross_ref_injector.inject_references(bot_responses)
        
        return bot_responses
    
    async def _generate_single_response(
        self,
        bot_name: str,
        user_message: str,
        other_bots: List[str],
        mode: DispatchTarget,
        room_context: Optional[Dict[str, Any]] = None,
    ) -> BotResponse:
        """Generate response for a single bot.
        
        Args:
            bot_name: Name of the bot
            user_message: User's message
            other_bots: List of other bots participating
            mode: Dispatch mode
            room_context: Optional room context
            
        Returns:
            BotResponse object
        """
        start_time = time.time()
        
        try:
            # Build context with communal awareness
            context = self._build_communal_context(
                bot_name=bot_name,
                user_message=user_message,
                other_bots=other_bots,
                mode=mode,
                room_context=room_context,
            )
            
            # Generate response using LLM
            response = await self.provider.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_message}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            
            response_time = int((time.time() - start_time) * 1000)
            
            return BotResponse(
                bot_name=bot_name,
                content=response.content or "",
                confidence=getattr(response, 'confidence', 0.8),
                response_time_ms=response_time,
                metadata={
                    "model": self.model,
                    "tokens_used": getattr(response, 'tokens_used', 0),
                }
            )
            
        except Exception as e:
            logger.error(f"[{bot_name}] Response generation failed: {e}")
            raise
    
    def _build_communal_context(
        self,
        bot_name: str,
        user_message: str,
        other_bots: List[str],
        mode: DispatchTarget,
        room_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build context that includes communal awareness.
        
        Args:
            bot_name: Name of the bot
            user_message: User's message
            other_bots: List of other participating bots
            mode: Dispatch mode
            room_context: Optional room context
            
        Returns:
            System prompt for the bot
        """
        # Load bot's identity/SOUL
        identity = self._load_bot_identity(bot_name)
        
        # Build context parts
        context_parts = [
            f"# You are @{bot_name}",
            "",
            "## Your Identity",
            identity or f"You are {bot_name}, a specialist bot.",
            "",
            "## Current Situation",
        ]
        
        # Add room context if available
        if room_context:
            room_name = room_context.get('name', 'this room')
            context_parts.append(f"Room: {room_name}")
        
        context_parts.extend([
            f"Other bots present: {', '.join(other_bots) if other_bots else 'None'}",
            f"This is a {'group' if mode == DispatchTarget.MULTI_BOT else 'context-aware'} conversation.",
            "",
            "## User's Message",
            user_message,
            "",
            "## How to Respond",
        ])
        
        # Mode-specific instructions
        if mode == DispatchTarget.MULTI_BOT:
            context_parts.extend([
                "- You are responding as part of a group (@all was mentioned)",
                "- Respond in your unique voice and personality",
                "- Be concise but characterful (2-3 sentences max)",
                "- Show your domain expertise",
                "- You can reference what other bots might say",
                "- Use your specific tone (professional, casual, technical, etc.)",
            ])
        else:  # CREW_CONTEXT
            context_parts.extend([
                "- You were selected as relevant to this message (@crew was mentioned)",
                "- Focus on your domain of expertise",
                "- Be concise (2-3 sentences max)",
                "- Provide specific, actionable insights",
            ])
        
        # Add affinity context for multi-bot mode
        if mode == DispatchTarget.MULTI_BOT and other_bots:
            affinity_context = self.affinity_builder.build_affinity_context(
                bot_name=bot_name,
                other_bots=other_bots,
            )
            if affinity_context:
                context_parts.extend(["", affinity_context])
        
        return "\n".join(context_parts)
    
    def _load_bot_identity(self, bot_name: str) -> Optional[str]:
        """Load bot's identity from SOUL.md or IDENTITY.md.
        
        Args:
            bot_name: Name of the bot
            
        Returns:
            Identity content or None
        """
        # Try SOUL.md first
        soul_path = self.workspace / "bots" / bot_name / "SOUL.md"
        if soul_path.exists():
            try:
                with open(soul_path, 'r') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load SOUL.md for {bot_name}: {e}")
        
        # Fallback to IDENTITY.md
        identity_path = self.workspace / "bots" / bot_name / "IDENTITY.md"
        if identity_path.exists():
            try:
                with open(identity_path, 'r') as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"Failed to load IDENTITY.md for {bot_name}: {e}")
        
        return None
    
    def format_multi_bot_response(
        self,
        responses: List[BotResponse],
        include_header: bool = True,
    ) -> str:
        """Format multiple bot responses into a cohesive output.
        
        Args:
            responses: List of BotResponse objects
            include_header: Whether to include a header
            
        Returns:
            Formatted string
        """
        parts = []
        
        if include_header:
            parts.append("🎭 **Multi-Bot Response**")
            parts.append("")
        
        for response in responses:
            emoji = self.BOT_EMOJIS.get(response.bot_name, "🤖")
            parts.append(f"{emoji} **@{response.bot_name}:**")
            parts.append(response.content)
            parts.append("")
        
        return "\n".join(parts)
    
    def get_bot_emoji(self, bot_name: str) -> str:
        """Get emoji for a bot.
        
        Args:
            bot_name: Name of the bot
            
        Returns:
            Emoji string
        """
        return self.BOT_EMOJIS.get(bot_name, "🤖")
    
    def get_bot_color(self, bot_name: str) -> str:
        """Get color for a bot.
        
        Args:
            bot_name: Name of the bot
            
        Returns:
            Color name string
        """
        return self.BOT_COLORS.get(bot_name, "white")
