"""Role card data model for bot personality and constraints."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RoleCardDomain(Enum):
    """Domain/specialty of a bot."""

    COORDINATION = "coordination"  # nanobot - team coordinator
    RESEARCH = "research"  # @researcher - analysis and insights
    DEVELOPMENT = "development"  # @coder - implementation
    COMMUNITY = "community"  # @social - engagement
    DESIGN = "design"  # @creative - visual/content
    QUALITY = "quality"  # @auditor - review and compliance


@dataclass
class HardBan:
    """Non-negotiable rule that a bot MUST follow."""

    rule: str  # Rule description
    consequence: str  # What happens if violated
    severity: str  # "critical", "high", "medium"

    def __post_init__(self) -> None:
        """Validate severity."""
        valid_severities = {"critical", "high", "medium"}
        if self.severity not in valid_severities:
            raise ValueError(
                f"Severity must be one of {valid_severities}, got {self.severity}"
            )


@dataclass
class Affinity:
    """How well this bot works with another bot."""

    bot_name: str  # Name of the other bot
    score: float  # 0.0 to 1.0, higher = better working relationship
    reason: str  # Why they work well/poorly together
    can_produce_creative_tension: bool = False  # Productive friction?

    def __post_init__(self) -> None:
        """Validate affinity score."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Affinity score must be 0.0-1.0, got {self.score}")


@dataclass
class RoleCard:
    """Complete personality, constraints, and relationships for a bot."""

    bot_name: str  # "nanobot", "researcher", "coder", etc.
    domain: RoleCardDomain  # What this bot specializes in
    title: str  # Role title ("Captain", "Navigator", "Gunner", etc.)
    description: str  # What this bot does
    inputs: List[str]  # What this bot accepts as work
    outputs: List[str]  # What this bot produces

    # Constraints
    hard_bans: List[HardBan] = field(default_factory=list)
    """Rules the bot MUST follow"""

    capabilities: Dict[str, bool] = field(default_factory=dict)
    """What tools/features are enabled"""

    # Personality
    voice: str = ""
    """Communication style and tone"""

    greeting: str = ""
    """How bot introduces itself"""

    emoji: str = ""
    """Visual identifier for bot"""

    # Relationships
    affinities: List[Affinity] = field(default_factory=list)
    """Relationships with other bots"""

    # Metadata
    version: str = "1.0"
    author: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_affinity_with(self, bot_name: str) -> float:
        """Get affinity score with another bot.
        
        Args:
            bot_name: Name of other bot
            
        Returns:
            Affinity score (0.0-1.0), or 0.5 if not found (neutral)
        """
        for aff in self.affinities:
            if aff.bot_name == bot_name:
                return aff.score
        return 0.5  # neutral default

    def has_capability(self, capability: str) -> bool:
        """Check if bot has a capability enabled.
        
        Args:
            capability: Capability name
            
        Returns:
            True if capability is enabled
        """
        return self.capabilities.get(capability, False)

    def validate_action(self, action: str) -> Tuple[bool, Optional[str]]:
        """Check if action violates hard bans.
        
        Args:
            action: Action description
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        for ban in self.hard_bans:
            if self._matches_rule(action, ban.rule):
                error_msg = f"Hard ban: {ban.rule}. Consequence: {ban.consequence}"
                return False, error_msg
        return True, None

    def _matches_rule(self, action: str, rule: str) -> bool:
        """Simple rule matching using word-based fuzzy matching.
        
        Args:
            action: Action to check
            rule: Rule pattern
            
        Returns:
            True if action matches rule
        """
        # Extract key words from rule (filter out common words)
        rule_lower = rule.lower()
        action_lower = action.lower()
        
        # Direct substring match
        if rule_lower in action_lower:
            return True
        
        # Word-based matching - check if key words from rule appear in action
        ignore_words = {"without", "never", "dont", "don't", "no", "not"}
        rule_words = [w for w in rule_lower.split() if w not in ignore_words]
        action_words = action_lower.split()
        
        # If all non-trivial words from rule are in action, it's a match
        return all(any(w in aw for aw in action_words) for w in rule_words)

    def get_relationship_description(self, bot_name: str) -> str:
        """Get description of relationship with another bot.
        
        Args:
            bot_name: Name of other bot
            
        Returns:
            Description of relationship
        """
        for aff in self.affinities:
            if aff.bot_name == bot_name:
                return aff.reason
        return "No relationship defined"

    def to_dict(self) -> Dict[str, Any]:
        """Convert role card to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            "bot_name": self.bot_name,
            "domain": self.domain.value,
            "title": self.title,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "hard_bans": [
                {
                    "rule": ban.rule,
                    "consequence": ban.consequence,
                    "severity": ban.severity,
                }
                for ban in self.hard_bans
            ],
            "voice": self.voice,
            "greeting": self.greeting,
            "emoji": self.emoji,
            "affinities": [
                {
                    "bot_name": aff.bot_name,
                    "score": aff.score,
                    "reason": aff.reason,
                    "can_produce_creative_tension": aff.can_produce_creative_tension,
                }
                for aff in self.affinities
            ],
        }
