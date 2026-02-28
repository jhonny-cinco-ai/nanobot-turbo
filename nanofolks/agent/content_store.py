"""Content store for external web content - isolates fetched content from direct messages."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from nanofolks.security.injection_detector import (
    InjectionDetectionResult,
    scan_for_injections,
)


@dataclass
class FetchedContent:
    """Represents stored external content."""
    id: str
    url: str
    title: str | None
    content: str
    scanned_at: datetime
    scan_result: InjectionDetectionResult
    accessed: bool = False
    accessed_at: datetime | None = None
    
    @property
    def is_safe(self) -> bool:
        return not self.scan_result.is_blocked
    
    @property
    def needs_warning(self) -> bool:
        return self.scan_result.is_warn


class ContentStore:
    """
    Stores fetched web content separately from messages.
    
    Instead of embedding content directly in tool results,
    we store it here and return a reference ID. The LLM
    can then explicitly request the content via a tool.
    """
    
    def __init__(self, max_content_size: int = 500_000, ttl_hours: int = 24):
        """
        Initialize content store.
        
        Args:
            max_content_size: Maximum content size in characters
            ttl_hours: Time-to-live for cached content
        """
        self._store: dict[str, FetchedContent] = {}
        self._url_to_id: dict[str, list[str]] = {}  # URL -> content IDs
        self.max_content_size = max_content_size
        self.ttl_hours = ttl_hours
    
    async def store(
        self,
        url: str,
        content: str,
        title: str | None = None,
        scan: bool = True,
    ) -> tuple[str, InjectionDetectionResult]:
        """
        Store content and return ID.
        
        Args:
            url: Source URL
            content: Content to store
            title: Optional title
            scan: Whether to scan for injections
            
        Returns:
            Tuple of (content_id, scan_result)
        """
        # Truncate if too large
        if len(content) > self.max_content_size:
            logger.warning(f"Content from {url} truncated from {len(content)} to {self.max_content_size}")
            content = content[:self.max_content_size] + "\n[content truncated...]"
        
        # Scan for injections
        scan_result = scan_for_injections(content, url) if scan else InjectionDetectionResult(
            url=url,
            scanned_at=datetime.now(),
            confidence="low",
            action="allow"
        )
        
        # Generate ID
        content_id = f"fetch_{uuid.uuid4().hex[:12]}"
        
        # Store
        fetched = FetchedContent(
            id=content_id,
            url=url,
            title=title,
            content=content,
            scanned_at=scan_result.scanned_at,
            scan_result=scan_result,
        )
        self._store[content_id] = fetched
        
        # Track URL -> ID mapping
        if url not in self._url_to_id:
            self._url_to_id[url] = []
        self._url_to_id[url].append(content_id)
        
        # Cleanup old entries
        self._cleanup()
        
        logger.debug(f"Stored content {content_id} from {url}, scan: {scan_result.action}")
        
        return content_id, scan_result
    
    async def get(self, content_id: str) -> FetchedContent | None:
        """Retrieve content by ID."""
        content = self._store.get(content_id)
        if content:
            content.accessed = True
            content.accessed_at = datetime.now()
        return content
    
    async def get_by_url(self, url: str) -> list[FetchedContent]:
        """Get all content from a URL."""
        content_ids = self._url_to_id.get(url, [])
        return [self._store[id] for id in content_ids if id in self._store]
    
    def get_reference(self, content_id: str, url: str, scan_result: InjectionDetectionResult) -> str:
        """
        Generate a tool result reference string.
        
        This is what's returned to the LLM instead of the full content.
        """
        action_emoji = {
            "block": "⛔",
            "warn": "⚠️",
            "allow": "✅"
        }.get(scan_result.action, "✅")
        
        return f"""[Content from {url} | ID: {content_id} | Scan: {scan_result.action} {action_emoji}]

To read this content, use the read_fetched_content tool with ID: {content_id}"""
    
    def get_blocked_message(self, url: str, scan_result: InjectionDetectionResult) -> str:
        """Generate message when content is blocked."""
        return f"""[Content from {url} | Scan: BLOCKED ⛔]

This content was blocked due to potential security concerns 
(confidence: {scan_result.confidence}).

If you need this information, please try a different source 
or let the user know."""
    
    def _cleanup(self) -> None:
        """Remove expired content."""
        now = datetime.now()
        expired_ids = []
        
        for content_id, content in self._store.items():
            age_hours = (now - content.scanned_at).total_seconds() / 3600
            if age_hours > self.ttl_hours:
                expired_ids.append(content_id)
        
        for content_id in expired_ids:
            content = self._store.pop(content_id, None)
            if content:
                urls = self._url_to_id.get(content.url, [])
                if content_id in urls:
                    urls.remove(content_id)
                if not urls:
                    self._url_to_id.pop(content.url, None)
        
        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired content entries")
    
    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        return {
            "total_contents": len(self._store),
            "total_urls": len(self._url_to_id),
            "accessed": sum(1 for c in self._store.values() if c.accessed),
            "blocked": sum(1 for c in self._store.values() if c.scan_result.is_blocked),
            "warned": sum(1 for c in self._store.values() if c.scan_result.is_warn),
        }


# Global instance
_content_store: ContentStore | None = None


def get_content_store() -> ContentStore:
    """Get or create global content store instance."""
    global _content_store
    if _content_store is None:
        _content_store = ContentStore()
    return _content_store
