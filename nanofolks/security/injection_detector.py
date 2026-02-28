"""Prompt injection detection for external content."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger


@dataclass
class InjectionMatch:
    """Represents a detected injection pattern."""
    pattern_name: str
    matched_text: str
    confidence: str  # "high", "medium", "low"
    position: tuple[int, int]


@dataclass
class InjectionDetectionResult:
    """Result of injection detection scan."""
    url: str
    scanned_at: datetime
    confidence: str  # "high", "medium", "low" (highest found)
    matches: list[InjectionMatch] = field(default_factory=list)
    action: str = "allow"  # "block", "warn", "allow"
    
    @property
    def is_blocked(self) -> bool:
        return self.action == "block"
    
    @property
    def is_warn(self) -> bool:
        return self.action == "warn"


# High confidence patterns - direct override attempts (BLOCK)
HIGH_CONFIDENCE_PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|earlier|above)\s+(instructions|prompts|commands)", "direct_override"),
    (r"disregard\s+(all\s+)?(previous|your\s+)?(instructions|system|guidelines)", "disregard_instructions"),
    (r"forget\s+(everything|all|your)\s+(instructions|training|guidelines)", "forget_instructions"),
    (r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be|you\s+must\s+act\s+as)", "role_manipulation"),
    (r"(new\s+system\s+instructions?|system\s*:\s*)", "system_override"),
    (r"override\s+(your\s+)?(instructions|safety|guidelines)", "override_safety"),
    (r"bypass\s+(your\s+)?(restrictions|guidelines|safety)", "bypass_safety"),
]

# Medium confidence patterns - action requests (WARN)
MEDIUM_CONFIDENCE_PATTERNS = [
    (r"instead\s+(of\s+)?respond\s+with", "respond_instead"),
    (r"always\s+(respond|start|begin)\s+your\s+response\s+with", "response_manipulation"),
    (r"(you\s+should|you\s+must|you\s+have\s+to|you\s+need\s+to).*(respond|answer|do\s+something)", "obligation_action"),
    (r"(respond|answer).*(with|using)\s+['\"]([^'\"]+)['\"]", "force_response"),
    (r"your\s+(task|job)\s+is\s+to", "task_reassignment"),
    (r"(forget|ignore)\s+what\s+you\s+(were|are)\s+(told|asked|said)", "memory_manipulation"),
]

# Low confidence patterns - subtle manipulation (LOG)
LOW_CONFIDENCE_PATTERNS = [
    (r"(as\s+an?|you\s+are\s+an?)\s+(AI|language\s+model|assistant|bot)", "ai_identification"),
    (r"this\s+is\s+(a|an)\s+(system|admin|developer)\s+(message|command|notice)", "authority_claim"),
    (r"(helpful|harmless|helpful).*assistant", "jailbreak_legacy"),
    (r"let's\s+play\s+(a\s+)?game", "roleplay_initiation"),
    (r"(in\s+the\s+following|from\s+now\s+on).*(respond|act|be)", "behavior_modification"),
    (r"remember\s+(that\s+)?(you|your)", "memory_injection"),
]


class InjectionDetector:
    """
    Detects prompt injection patterns in external content.
    
    Three-tier response:
    - high: Block content, don't send to LLM
    - medium: Allow but add warning metadata  
    - low: Allow, log for analysis
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Pre-compile all patterns for performance."""
        self._high_patterns = [
            (re.compile(p, re.IGNORECASE), name) 
            for p, name in HIGH_CONFIDENCE_PATTERNS
        ]
        self._medium_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in MEDIUM_CONFIDENCE_PATTERNS
        ]
        self._low_patterns = [
            (re.compile(p, re.IGNORECASE), name)
            for p, name in LOW_CONFIDENCE_PATTERNS
        ]
    
    def scan(self, text: str, url: str = "") -> InjectionDetectionResult:
        """
        Scan text for prompt injection patterns.
        
        Args:
            text: Content to scan
            url: Source URL for logging
            
        Returns:
            InjectionDetectionResult with confidence and action
        """
        if not self.enabled:
            return InjectionDetectionResult(
                url=url,
                scanned_at=datetime.now(),
                confidence="low",
                action="allow"
            )
        
        if not text:
            return InjectionDetectionResult(
                url=url,
                scanned_at=datetime.now(),
                confidence="low", 
                action="allow"
            )
        
        matches: list[InjectionMatch] = []
        
        # Check high confidence patterns first
        for pattern, name in self._high_patterns:
            for match in pattern.finditer(text):
                matches.append(InjectionMatch(
                    pattern_name=name,
                    matched_text=match.group(),
                    confidence="high",
                    position=(match.start(), match.end())
                ))
        
        # Check medium confidence patterns
        for pattern, name in self._medium_patterns:
            for match in pattern.finditer(text):
                # Skip if high confidence already found
                if not any(m.position == (match.start(), match.end()) for m in matches):
                    matches.append(InjectionMatch(
                        pattern_name=name,
                        matched_text=match.group(),
                        confidence="medium",
                        position=(match.start(), match.end())
                    ))
        
        # Check low confidence patterns
        for pattern, name in self._low_patterns:
            for match in pattern.finditer(text):
                if not any(m.position == (match.start(), match.end()) for m in matches):
                    matches.append(InjectionMatch(
                        pattern_name=name,
                        matched_text=match.group(),
                        confidence="low",
                        position=(match.start(), match.end())
                    ))
        
        # Determine overall confidence and action
        if any(m.confidence == "high" for m in matches):
            confidence = "high"
            action = "block"
        elif any(m.confidence == "medium" for m in matches):
            confidence = "medium" 
            action = "warn"
        elif matches:
            confidence = "low"
            action = "allow"
        else:
            confidence = "low"
            action = "allow"
        
        result = InjectionDetectionResult(
            url=url,
            scanned_at=datetime.now(),
            confidence=confidence,
            matches=matches,
            action=action
        )
        
        # Log findings
        if action != "allow":
            logger.warning(
                f"Injection detected in {url}: {action} ({confidence})",
                extra={
                    "url": url,
                    "action": action,
                    "confidence": confidence,
                    "matches": [
                        {"pattern": m.pattern_name, "text": m.matched_text}
                        for m in matches
                    ]
                }
            )
        
        return result
    
    def scan_async(self, text: str, url: str = ""):
        """Async wrapper for scan method."""
        return self.scan(text, url)


# Global instance
_default_detector = InjectionDetector()


def scan_for_injections(text: str, url: str = "") -> InjectionDetectionResult:
    """Convenience function using default detector."""
    return _default_detector.scan(text, url)


def is_content_safe(text: str, url: str = "") -> tuple[bool, str]:
    """
    Quick check if content is safe.
    
    Returns:
        (is_safe, reason)
    """
    result = scan_for_injections(text, url)
    if result.is_blocked:
        return False, f"High-confidence injection: {result.matches[0].pattern_name}"
    if result.is_warn:
        return True, "warn"
    return True, "safe"
