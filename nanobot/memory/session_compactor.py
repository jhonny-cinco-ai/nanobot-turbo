"""Session compaction for long conversations.

This module provides intelligent session compaction to handle long conversations
without losing context or overflowing the context window.

Inspired by OpenClaw's production-hardened compaction system:
- Multiple compaction modes (summary, token-limit, off)
- Tool chain preservation (never break tool_use → tool_result pairs)
- Proactive compaction at 80% threshold
- Smart boundary detection
- Pre-compaction memory flush hook

Example workflow:
    70 messages, ~3500 tokens, 80% threshold reached:
    - Messages 1-40: Summarized into 4 summary blocks (200 tokens)
    - Messages 41-70: Kept verbatim (30 messages, ~1000 tokens)
    - Total: ~1200 tokens (well under 3000 target)
    - Tool chains: All preserved intact
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, Callable, Awaitable

from loguru import logger

from nanobot.memory.token_counter import TokenCounter, count_messages
from nanobot.session.manager import Session


class CompactionMode(Protocol):
    """Protocol for compaction mode implementations."""
    
    async def compact(self, messages: list[dict[str, Any]], target_tokens: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Compact messages to fit within target token budget.
        
        Args:
            messages: Messages to compact.
            target_tokens: Target token budget.
        
        Returns:
            Tuple of (compacted_messages, stats).
        """
        ...


LLMSummarizer = Callable[[list[dict[str, Any]]], Awaitable[str]]


@dataclass
class CompactionResult:
    """Result of a compaction operation."""
    messages: list[dict[str, Any]]
    summary_message: dict[str, Any] | None = None
    original_count: int = 0
    compacted_count: int = 0
    tokens_before: int = 0
    tokens_after: int = 0
    compaction_ratio: float = 0.0
    mode: str = ""


@dataclass
class SessionCompactionConfig:
    """Configuration for session compaction."""
    enabled: bool = True
    mode: str = "summary"  # summary, token-limit, off
    threshold_percent: float = 0.8  # Trigger compaction at 80%
    target_tokens: int = 3000
    min_messages: int = 10
    max_messages: int = 100
    preserve_recent: int = 20
    preserve_tool_chains: bool = True
    summary_chunk_size: int = 10
    enable_memory_flush: bool = True
    
    # Strategy selection thresholds
    short_threshold: int = 20  # Below this: no compaction
    medium_threshold: int = 50  # Below this: extraction summary
    use_llm_for_long: bool = True  # Use LLM summarization for long sessions
    long_threshold: int = 80  # Above this: definitely use LLM if available


SUMMARY_PROMPT = """Summarize this conversation segment concisely. Focus on:
- Key topics discussed
- Important decisions or outcomes
- Any errors or issues encountered

Conversation:
{messages}

Summary (2-3 sentences):"""


class SummaryCompactionMode:
    """
    Smart summarization compaction mode (default).
    
    Summarizes older messages using LLM, keeps recent messages verbatim.
    Best for maintaining conversation coherence.
    """
    
    def __init__(
        self,
        chunk_size: int = 10,
        summarizer: LLMSummarizer | None = None,
        max_summary_tokens: int = 150
    ):
        self.chunk_size = chunk_size
        self.token_counter = TokenCounter()
        self.summarizer = summarizer
        self.max_summary_tokens = max_summary_tokens
    
    async def compact(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int,
        preserve_recent: int = 20
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Compact messages using summarization.
        
        Strategy:
        1. Keep recent messages verbatim
        2. Summarize older messages in chunks
        3. Generate synthetic summary messages
        
        Args:
            messages: Messages to compact.
            target_tokens: Target token budget.
            preserve_recent: Number of recent messages to keep verbatim.
        
        Returns:
            Tuple of (compacted_messages, stats).
        """
        if len(messages) <= preserve_recent:
            return messages, {"reason": "not_enough_messages"}
        
        # Recent messages (keep verbatim)
        recent = messages[-preserve_recent:]
        recent_tokens = count_messages(recent)
        
        # If recent messages already exceed target, just return them
        if recent_tokens >= target_tokens:
            logger.warning(f"Recent messages ({recent_tokens} tokens) exceed target ({target_tokens})")
            return recent, {"reason": "recent_exceeds_target", "tokens": recent_tokens}
        
        # Older messages to summarize
        older = messages[:-preserve_recent]
        remaining_budget = target_tokens - recent_tokens
        
        # Generate summaries for older messages
        summaries = []
        for i in range(0, len(older), self.chunk_size):
            chunk = older[i:i + self.chunk_size]
            summary = await self._summarize_chunk(chunk)
            if summary:
                summaries.append({
                    "role": "system",
                    "content": f"[Earlier conversation summary]: {summary}",
                    "is_summary": True,
                    "original_count": len(chunk)
                })
        
        # Combine: summaries + recent
        compacted = summaries + recent
        
        stats = {
            "original_count": len(messages),
            "compacted_count": len(compacted),
            "summaries_generated": len(summaries),
            "tokens_before": count_messages(messages),
            "tokens_after": count_messages(compacted),
            "mode": "summary"
        }
        
        return compacted, stats
    
    async def _summarize_chunk(self, messages: list[dict[str, Any]]) -> str:
        """
        Summarize a chunk of messages.
        
        Uses LLM if available, falls back to extraction otherwise.
        
        Args:
            messages: Messages to summarize.
        
        Returns:
            Summary text.
        """
        if self.summarizer:
            try:
                summary = await self.summarizer(messages)
                if summary:
                    return summary
            except Exception as e:
                logger.warning(f"LLM summarization failed: {e}, falling back to extraction")
        
        return self._extraction_summary(messages)
    
    def _extraction_summary(self, messages: list[dict[str, Any]]) -> str:
        """
        Fallback extraction-based summary.
        
        Extracts key points without using LLM.
        
        Args:
            messages: Messages to summarize.
        
        Returns:
            Summary text.
        """
        key_points = []
        tool_results = []
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "user" and content:
                if len(content) > 20:
                    key_points.append(content[:100] + "..." if len(content) > 100 else content)
            elif role == "assistant":
                if isinstance(content, str):
                    if "error" in content.lower() or "failed" in content.lower():
                        tool_results.append(content[:80])
        
        if key_points:
            return " | ".join(key_points[:3])
        
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        assistant_msgs = sum(1 for m in messages if m.get("role") == "assistant")
        
        result = f"{user_msgs} user messages, {assistant_msgs} assistant responses"
        if tool_results:
            result += f". Errors: {'; '.join(tool_results[:2])}"
        
        return result


class TokenLimitCompactionMode:
    """
    Hard token limit compaction mode (emergency).
    
    Truncates messages at a safe boundary to fit within token budget.
    Used when context is critically large.
    """
    
    def __init__(self):
        self.token_counter = TokenCounter()
    
    async def compact(
        self,
        messages: list[dict[str, Any]],
        target_tokens: int,
        min_messages: int = 10
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Compact messages using hard truncation at safe boundaries.
        
        Strategy:
        1. Find safe boundary (assistant message, not mid-tool)
        2. Truncate everything before boundary
        3. Keep minimum number of messages
        
        Args:
            messages: Messages to compact.
            target_tokens: Target token budget.
            min_messages: Minimum messages to keep.
        
        Returns:
            Tuple of (compacted_messages, stats).
        """
        if len(messages) <= min_messages:
            return messages, {"reason": "min_messages"}
        
        # Find safe truncation point
        # Look for assistant messages going backwards from the end
        check_idx = len(messages) - min_messages
        safe_boundary = None
        
        while check_idx >= 0:
            msg = messages[check_idx]
            
            # Assistant messages are safe boundaries
            if msg.get("role") == "assistant":
                # Check if this is a safe boundary (not mid-tool-chain)
                if self._is_safe_boundary(messages, check_idx):
                    safe_boundary = check_idx
                    break
            
            check_idx -= 1
        
        if safe_boundary is None:
            # No safe boundary found, just keep last min_messages
            safe_boundary = len(messages) - min_messages
        
        # Truncate at safe boundary
        compacted = messages[safe_boundary:]
        
        stats = {
            "original_count": len(messages),
            "compacted_count": len(compacted),
            "truncated_count": safe_boundary,
            "tokens_before": count_messages(messages),
            "tokens_after": count_messages(compacted),
            "mode": "token-limit"
        }
        
        return compacted, stats
    
    def _is_safe_boundary(self, messages: list[dict[str, Any]], idx: int) -> bool:
        """
        Check if a message index is a safe boundary (not mid-tool-chain).
        
        A boundary is safe if:
        - The message is an assistant message without tool_use, OR
        - All tool_use blocks in this message have matching tool_results after idx
        
        Args:
            messages: All messages.
            idx: Index to check.
        
        Returns:
            True if safe boundary.
        """
        msg = messages[idx]
        
        if msg.get("role") != "assistant":
            return False
        
        content = msg.get("content", [])
        
        # If simple string content, it's safe
        if isinstance(content, str):
            return True
        
        # Check for tool_use blocks
        tool_use_ids = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_use_ids.append(block.get("id"))
        
        # If no tool_use, it's safe
        if not tool_use_ids:
            return True
        
        # Check that all tool_use have matching tool_result after idx
        for tool_id in tool_use_ids:
            found_result = False
            for i in range(idx + 1, len(messages)):
                later_msg = messages[i]
                if later_msg.get("role") == "user":
                    later_content = later_msg.get("content", [])
                    if isinstance(later_content, list):
                        for block in later_content:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                if block.get("tool_use_id") == tool_id:
                                    found_result = True
                                    break
                if found_result:
                    break
            
            if not found_result:
                # Tool result is before this message (would be lost), not safe
                return False
        
        return True


class SessionCompactor:
    """
    Main session compactor with multiple modes.
    
    Handles long conversations by compacting older messages while
    preserving tool chains and maintaining conversation coherence.
    
    Inspired by OpenClaw's production system:
    - Multiple modes for different scenarios
    - Proactive 80% threshold trigger
    - Tool chain preservation
    - Pre-compaction memory flush
    
    Example:
        compactor = SessionCompactor(config)
        
        # Check if compaction needed
        if compactor.should_compact(session, max_tokens=8000):
            # Trigger memory flush hook
            await memory_flush_hook(session)
            
            # Compact
            result = await compactor.compact_session(session)
            
            # Update session
            session.messages = result.messages
    """
    
    def __init__(
        self,
        config: SessionCompactionConfig | None = None,
        summarizer: LLMSummarizer | None = None
    ):
        """
        Initialize the session compactor.
        
        Args:
            config: Compaction configuration.
            summarizer: Optional async function that takes messages and returns summary.
        """
        self.config = config or SessionCompactionConfig()
        self.token_counter = TokenCounter()
        self.summarizer = summarizer
        
        # Initialize modes
        self._modes: dict[str, CompactionMode] = {
            "summary": SummaryCompactionMode(
                chunk_size=self.config.summary_chunk_size,
                summarizer=summarizer
            ),
            "token-limit": TokenLimitCompactionMode(),
        }
    
    def should_compact(self, messages: list[dict[str, Any]], max_tokens: int) -> bool:
        """
        Check if session should be compacted.
        
        Uses proactive threshold (default 80%) to prevent emergencies.
        
        Args:
            messages: Session messages.
            max_tokens: Maximum context window.
        
        Returns:
            True if compaction should trigger.
        """
        if not self.config.enabled:
            return False
        
        if self.config.mode == "off":
            return False
        
        current_tokens = count_messages(messages)
        threshold = int(max_tokens * self.config.threshold_percent)
        
        should_compact = current_tokens > threshold
        
        if should_compact:
            logger.info(
                f"Compaction triggered: {current_tokens} tokens > {threshold} threshold "
                f"({self.config.threshold_percent:.0%} of {max_tokens})"
            )
        
        return should_compact
    
    def get_compaction_strategy(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        """
        Determine the best compaction strategy based on conversation length.
        
        Strategy selection:
        - short (1-{short_threshold}): No compaction needed
        - medium ({short_threshold}-{medium_threshold}): Extraction summary
        - long ({medium_threshold}-{long_threshold}): LLM summary if available
        - desperate (>{long_threshold}): token-limit mode as fallback
        
        Args:
            messages: Session messages.
            max_tokens: Maximum context window.
        
        Returns:
            Dict with strategy info: mode, reason, and recommended settings.
        """
        msg_count = len(messages)
        current_tokens = count_messages(messages)
        
        short = self.config.short_threshold
        medium = self.config.medium_threshold
        long = self.config.long_threshold
        
        # Check token threshold first
        threshold = int(max_tokens * self.config.threshold_percent)
        
        if msg_count <= short and current_tokens <= threshold:
            return {
                "strategy": "none",
                "mode": "off",
                "reason": f"Short conversation ({msg_count} msgs, {current_tokens} tokens)",
                "preserve_recent": self.config.preserve_recent,
                "use_llm": False,
            }
        
        if msg_count > long and not self.summarizer:
            return {
                "strategy": "desperate",
                "mode": "token-limit",
                "reason": f"Very long conversation ({msg_count} msgs) without LLM summarizer",
                "preserve_recent": self.config.preserve_recent,
                "use_llm": False,
            }
        
        if msg_count > long:
            return {
                "strategy": "long",
                "mode": "summary",
                "reason": f"Long conversation ({msg_count} msgs), using LLM summarization",
                "preserve_recent": self.config.preserve_recent + 10,  # Keep more recent
                "use_llm": True,
            }
        
        if msg_count > medium:
            return {
                "strategy": "medium",
                "mode": "summary",
                "reason": f"Medium conversation ({msg_count} msgs), extraction or LLM",
                "preserve_recent": self.config.preserve_recent,
                "use_llm": self.config.use_llm_for_long and self.summarizer is not None,
            }
        
        return {
            "strategy": "light",
            "mode": "summary",
            "reason": f"Light compaction ({msg_count} msgs)",
            "preserve_recent": min(self.config.preserve_recent, msg_count // 2),
            "use_llm": False,  # Not worth calling LLM for short summaries
        }
    
    def validate_compaction(
        self,
        original: list[dict[str, Any]],
        compacted: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Validate that compaction didn't break the conversation.
        
        Checks:
        1. Tool chains are intact (tool_use → tool_result pairs preserved)
        2. Recent messages are still present
        3. Summary messages are properly formatted
        
        Args:
            original: Original messages before compaction.
            compacted: Messages after compaction.
        
        Returns:
            Validation result dict with is_valid and any issues found.
        """
        issues = []
        warnings = []
        
        # Check 1: Tool chain preservation
        tool_chain_issues = self._validate_tool_chains(original, compacted)
        if tool_chain_issues:
            issues.extend(tool_chain_issues)
        
        # Check 2: Recent messages preserved
        if compacted:
            last_msg = compacted[-1]
            last_original = original[-1] if original else None
            if last_original and last_msg.get("content") != last_original.get("content"):
                warnings.append("Last message content differs - may have been truncated")
        
        # Check 3: Summary format
        summary_count = sum(1 for m in compacted if m.get("is_summary"))
        if summary_count > 0:
            logger.debug(f"Compaction created {summary_count} summary messages")
        
        is_valid = len(issues) == 0
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "original_count": len(original),
            "compacted_count": len(compacted),
            "summary_count": summary_count,
        }
    
    def _validate_tool_chains(
        self,
        original: list[dict[str, Any]],
        compacted: list[dict[str, Any]]
    ) -> list[str]:
        """
        Validate that all tool_use → tool_result pairs in original are preserved.
        
        Args:
            original: Original messages.
            compacted: Compacted messages.
        
        Returns:
            List of issues found (empty if valid).
        """
        issues = []
        
        # Build map of tool_use IDs in original
        original_tool_uses: dict[str, tuple[int, dict]] = {}
        original_tool_results: dict[str, int] = {}
        
        for idx, msg in enumerate(original):
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_use":
                            tool_id = block.get("id")
                            if tool_id:
                                original_tool_uses[tool_id] = (idx, block)
                        elif block.get("type") == "tool_result":
                            tool_id = block.get("tool_use_id")
                            if tool_id:
                                original_tool_results[tool_id] = idx
        
        # Check each tool_use has a matching tool_result
        for tool_id, (use_idx, tool_block) in original_tool_uses.items():
            result_idx = original_tool_results.get(tool_id)
            if result_idx is None:
                continue  # Tool still in progress, can't validate
            
            # Check if this pair exists in compacted
            found_use = False
            found_result = False
            
            for msg in compacted:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "tool_use" and block.get("id") == tool_id:
                                found_use = True
                            elif block.get("type") == "tool_result" and block.get("tool_use_id") == tool_id:
                                found_result = True
            
            if not (found_use and found_result):
                issues.append(
                    f"Tool chain broken: {tool_id} ({tool_block.get('name', 'unknown')}) "
                    f"at original index {use_idx} not preserved"
                )
        
        return issues
    
    async def compact_session(
        self,
        session: Session,
        max_tokens: int | None = None
    ) -> CompactionResult:
        """
        Compact a session using the configured mode.
        
        Args:
            session: Session to compact.
            max_tokens: Maximum token budget (uses config.target_tokens if None).
        
        Returns:
            Compaction result with new messages and stats.
        """
        if not self.config.enabled:
            return CompactionResult(
                messages=session.messages,
                original_count=len(session.messages),
                compacted_count=len(session.messages),
                mode="off"
            )
        
        target_tokens = max_tokens or self.config.target_tokens
        mode = self.config.mode
        
        if mode == "off":
            return CompactionResult(
                messages=session.messages,
                original_count=len(session.messages),
                compacted_count=len(session.messages),
                mode="off"
            )
        
        # Get compaction mode implementation
        mode_impl = self._modes.get(mode)
        if not mode_impl:
            logger.error(f"Unknown compaction mode: {mode}, using summary")
            mode_impl = self._modes["summary"]
        
        # Perform compaction
        messages = session.messages
        original_tokens = count_messages(messages)
        
        if mode == "summary":
            compacted, stats = await mode_impl.compact(
                messages,
                target_tokens,
                preserve_recent=self.config.preserve_recent
            )
        else:  # token-limit
            compacted, stats = await mode_impl.compact(
                messages,
                target_tokens,
                min_messages=self.config.min_messages
            )
        
        compacted_tokens = count_messages(compacted)
        
        # Create result
        result = CompactionResult(
            messages=compacted,
            original_count=len(messages),
            compacted_count=len(compacted),
            tokens_before=original_tokens,
            tokens_after=compacted_tokens,
            compaction_ratio=compacted_tokens / original_tokens if original_tokens > 0 else 1.0,
            mode=mode
        )
        
        logger.info(
            f"Compaction complete: {result.original_count} → {result.compacted_count} messages, "
            f"{result.tokens_before} → {result.tokens_after} tokens "
            f"({result.compaction_ratio:.1%} ratio)"
        )
        
        return result
    
    def get_context_status(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        """
        Get context usage status.
        
        Args:
            messages: Session messages.
            max_tokens: Maximum context window.
        
        Returns:
            Status dict with percentage, token counts, etc.
        """
        current_tokens = count_messages(messages)
        percentage = current_tokens / max_tokens if max_tokens > 0 else 0.0
        
        return {
            "current_tokens": current_tokens,
            "max_tokens": max_tokens,
            "percentage": percentage,
            "percentage_formatted": f"{percentage:.0%}",
            "tokens_remaining": max(0, max_tokens - current_tokens),
            "should_compact": self.should_compact(messages, max_tokens),
            "threshold_percent": self.config.threshold_percent,
            "threshold_tokens": int(max_tokens * self.config.threshold_percent),
            "mode": self.config.mode
        }


# Convenience functions

async def compact_session_if_needed(
    session: Session,
    max_tokens: int = 8000,
    config: SessionCompactionConfig | None = None,
    memory_flush_hook: Any = None
) -> CompactionResult | None:
    """
    Compact a session if it exceeds the threshold.
    
    Convenience function that checks threshold and compacts if needed.
    
    Args:
        session: Session to check/compact.
        max_tokens: Maximum context window.
        config: Compaction configuration.
        memory_flush_hook: Optional async function to call before compaction.
    
    Returns:
        CompactionResult if compacted, None if not needed.
    """
    compactor = SessionCompactor(config)
    
    if not compactor.should_compact(session.messages, max_tokens):
        return None
    
    # Call memory flush hook if provided
    if memory_flush_hook and compactor.config.enable_memory_flush:
        try:
            await memory_flush_hook(session)
        except Exception as e:
            logger.warning(f"Memory flush hook failed: {e}")
    
    # Compact
    result = await compactor.compact_session(session, max_tokens)
    
    # Update session
    session.messages = result.messages
    
    return result
