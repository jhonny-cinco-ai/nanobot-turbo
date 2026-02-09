"""Data models for the smart router."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RoutingTier(str, Enum):
    """Capability tiers for model selection."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    REASONING = "reasoning"


@dataclass
class RoutingDecision:
    """Result of a routing classification."""
    
    tier: RoutingTier
    model: str
    confidence: float
    layer: str  # "client" or "llm"
    reasoning: str
    estimated_tokens: int
    needs_tools: bool
    
    # Metadata for analytics
    metadata: dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass  
class ClassificationScores:
    """Scores from the 14-dimension classification system."""
    
    reasoning_markers: float = 0.0
    code_presence: float = 0.0
    simple_indicators: float = 0.0
    multi_step_patterns: float = 0.0
    technical_terms: float = 0.0
    token_count: float = 0.0
    creative_markers: float = 0.0
    question_complexity: float = 0.0
    constraint_count: float = 0.0
    imperative_verbs: float = 0.0
    output_format: float = 0.0
    domain_specificity: float = 0.0
    reference_complexity: float = 0.0
    negation_complexity: float = 0.0
    
    def calculate_weighted_sum(self, weights: dict[str, float]) -> float:
        """Calculate weighted sum of all scores."""
        total = 0.0
        for field_name, weight in weights.items():
            if hasattr(self, field_name):
                total += getattr(self, field_name) * weight
        return total
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "reasoning_markers": self.reasoning_markers,
            "code_presence": self.code_presence,
            "simple_indicators": self.simple_indicators,
            "multi_step_patterns": self.multi_step_patterns,
            "technical_terms": self.technical_terms,
            "token_count": self.token_count,
            "creative_markers": self.creative_markers,
            "question_complexity": self.question_complexity,
            "constraint_count": self.constraint_count,
            "imperative_verbs": self.imperative_verbs,
            "output_format": self.output_format,
            "domain_specificity": self.domain_specificity,
            "reference_complexity": self.reference_complexity,
            "negation_complexity": self.negation_complexity,
        }


@dataclass
class RoutingPattern:
    """A learned pattern for client-side classification."""
    
    regex: str
    tier: RoutingTier
    confidence: float
    examples: list[str]
    added_at: str
    success_rate: float = 0.0
    usage_count: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "regex": self.regex,
            "tier": self.tier.value,
            "confidence": self.confidence,
            "examples": self.examples,
            "added_at": self.added_at,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RoutingPattern":
        """Create from dictionary."""
        return cls(
            regex=data["regex"],
            tier=RoutingTier(data["tier"]),
            confidence=data["confidence"],
            examples=data.get("examples", []),
            added_at=data["added_at"],
            success_rate=data.get("success_rate", 0.0),
            usage_count=data.get("usage_count", 0),
        )
