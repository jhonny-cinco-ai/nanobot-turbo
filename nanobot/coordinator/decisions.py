"""Decision-making and consensus systems for multi-agent coordination.

Implements voting, consensus algorithms, and dispute resolution mechanisms.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class VotingStrategy(str, Enum):
    """Strategies for reaching consensus."""
    UNANIMOUS = "unanimous"        # All bots must agree
    MAJORITY = "majority"          # >50% must agree
    WEIGHTED = "weighted"          # Votes weighted by expertise/confidence
    SIMPLE_PLURALITY = "plurality" # Most votes wins, even without majority


class DisagreementType(str, Enum):
    """Types of disagreement between bots."""
    FACTUAL = "factual"             # Different facts or assumptions
    METHODOLOGICAL = "methodological"  # Different approaches
    PRIORITY = "priority"           # Different priority levels
    PHILOSOPHICAL = "philosophical" # Different values or goals
    INCOMPLETE_INFO = "incomplete"  # Missing information


@dataclass
class BotPosition:
    """A bot's position on a decision."""
    bot_id: str
    position: str                   # What the bot supports/advocates
    confidence: float               # 0.0 to 1.0
    reasoning: str                  # Why the bot holds this position
    expertise_score: Optional[float] = None  # Bot's expertise in this domain
    

@dataclass
class Decision:
    """A decision made by the coordination team."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None   # Associated task ID
    decision_type: str = "consensus"  # Type of decision process used
    participants: List[str] = field(default_factory=list)  # Bot IDs involved
    positions: Dict[str, BotPosition] = field(default_factory=dict)  # Position per bot
    final_decision: str = ""        # The chosen option
    confidence: float = 0.0         # 0.0-1.0, how confident in decision
    reasoning: str = ""             # Explanation of decision
    dissent: Optional[str] = None   # Summary of dissenting views
    escalated: bool = False         # Was this escalated to user?
    timestamp: datetime = field(default_factory=datetime.now)
    

@dataclass
class Disagreement:
    """A disagreement between bots."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None
    disagreement_type: DisagreementType = DisagreementType.FACTUAL
    positions: Dict[str, BotPosition] = field(default_factory=dict)
    common_ground: str = ""         # What they agree on
    key_differences: List[str] = field(default_factory=list)  # What differs
    severity: float = 0.5           # 0.0 (minor) to 1.0 (critical)
    timestamp: datetime = field(default_factory=datetime.now)


class DecisionMaker:
    """Makes decisions through consensus and voting.
    
    Orchestrates team decision-making using various strategies:
    - Unanimous consensus for critical decisions
    - Majority voting for routine decisions
    - Weighted voting using bot expertise
    - Escalation when consensus can't be reached
    """
    
    def __init__(self):
        """Initialize decision maker."""
        self.decisions: Dict[str, Decision] = {}
        self.disagreements: Dict[str, Disagreement] = {}
    
    def create_consensus_vote(
        self,
        options: List[str],
        participants: List[str],
        positions: Dict[str, BotPosition],
        strategy: VotingStrategy = VotingStrategy.MAJORITY,
        task_id: Optional[str] = None
    ) -> Decision:
        """Create a consensus vote on a decision.
        
        Args:
            options: List of options to vote on
            participants: List of bot IDs participating
            positions: Dict mapping bot_id -> BotPosition
            strategy: Voting strategy to use
            task_id: Associated task ID
            
        Returns:
            Decision object with result
        """
        if not participants:
            raise ValueError("No participants for vote")
        
        if not positions:
            raise ValueError("No positions provided")
        
        if not options:
            raise ValueError("No options to vote on")
        
        # Validate all participants have positions
        missing = set(participants) - set(positions.keys())
        if missing:
            raise ValueError(f"Missing positions for bots: {missing}")
        
        # Count votes per option
        votes: Dict[str, float] = {option: 0.0 for option in options}
        vote_counts: Dict[str, int] = {option: 0 for option in options}
        
        for bot_id, position in positions.items():
            # Find which option this position supports
            for option in options:
                if self._option_matches_position(option, position.position):
                    if strategy == VotingStrategy.WEIGHTED and position.expertise_score:
                        votes[option] += position.expertise_score * position.confidence
                    else:
                        votes[option] += position.confidence
                    vote_counts[option] += 1
                    break
        
        # Determine winner based on strategy
        final_decision = self._resolve_vote(votes, vote_counts, participants, strategy)
        
        # Calculate confidence
        total_weight = sum(votes.values()) if votes.values() else 1.0
        decision_confidence = (votes.get(final_decision, 0.0) / total_weight) if total_weight > 0 else 0.0
        
        # Build decision object
        decision = Decision(
            task_id=task_id,
            decision_type="consensus",
            participants=participants,
            positions=positions,
            final_decision=final_decision,
            confidence=decision_confidence,
            reasoning=self._generate_voting_reasoning(positions, final_decision, strategy)
        )
        
        self.decisions[decision.id] = decision
        return decision
    
    def get_consensus(
        self,
        positions: Dict[str, BotPosition],
        required_agreement: float = 0.8
    ) -> Optional[str]:
        """Extract consensus from positions.
        
        Consensus exists when most bots agree on a position.
        
        Args:
            positions: Dict mapping bot_id -> BotPosition
            required_agreement: Threshold for consensus (0.0-1.0)
            
        Returns:
            Consensus position string, or None if no consensus
        """
        if not positions:
            return None
        
        # Group positions by their content
        position_groups: Dict[str, List[str]] = {}
        for bot_id, pos in positions.items():
            key = pos.position
            if key not in position_groups:
                position_groups[key] = []
            position_groups[key].append(bot_id)
        
        # Find position with highest agreement rate
        total_bots = len(positions)
        for position, bots in position_groups.items():
            agreement_rate = len(bots) / total_bots
            if agreement_rate >= required_agreement:
                return position
        
        return None
    
    def resolve_dispute(
        self,
        disagreement: Disagreement
    ) -> Decision:
        """Resolve a disagreement between bots.
        
        Args:
            disagreement: The disagreement to resolve
            
        Returns:
            Decision resolving the dispute
        """
        # Try to find common ground
        common_ground = self._find_common_ground(disagreement.positions)
        
        # Try to build consensus around common ground
        if common_ground:
            consensus = self.get_consensus(disagreement.positions)
            if consensus:
                decision = Decision(
                    task_id=disagreement.task_id,
                    decision_type="dispute_resolution",
                    participants=list(disagreement.positions.keys()),
                    positions=disagreement.positions,
                    final_decision=consensus,
                    confidence=0.7,
                    reasoning=f"Resolved dispute using common ground: {common_ground}",
                    dissent=self._summarize_dissent(disagreement.positions, consensus)
                )
                self.decisions[decision.id] = decision
                return decision
        
        # If no consensus, use expertise-weighted voting
        best_bot = self._find_most_expert_bot(disagreement.positions)
        decision = Decision(
            task_id=disagreement.task_id,
            decision_type="expertise_based",
            participants=list(disagreement.positions.keys()),
            positions=disagreement.positions,
            final_decision=disagreement.positions[best_bot].position,
            confidence=0.6,
            reasoning=f"Resolved based on expertise of {best_bot}",
            dissent=self._summarize_dissent(disagreement.positions, disagreement.positions[best_bot].position)
        )
        self.decisions[decision.id] = decision
        return decision
    
    def escalate(
        self,
        decision_id: str,
        reason: str = ""
    ) -> Decision:
        """Escalate a decision to user for review.
        
        Args:
            decision_id: The decision ID to escalate
            reason: Reason for escalation
            
        Returns:
            Updated Decision object
        """
        if decision_id not in self.decisions:
            raise ValueError(f"Decision not found: {decision_id}")
        
        decision = self.decisions[decision_id]
        decision.escalated = True
        if reason:
            decision.reasoning += f"\n[ESCALATED: {reason}]"
        
        return decision
    
    def get_decision(self, decision_id: str) -> Optional[Decision]:
        """Get a decision by ID.
        
        Args:
            decision_id: The decision ID
            
        Returns:
            Decision or None if not found
        """
        return self.decisions.get(decision_id)
    
    def get_decisions_for_task(self, task_id: str) -> List[Decision]:
        """Get all decisions for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of decisions for the task
        """
        return [d for d in self.decisions.values() if d.task_id == task_id]
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _option_matches_position(self, option: str, position: str) -> bool:
        """Check if an option matches a position."""
        return option.lower() == position.lower()
    
    def _resolve_vote(
        self,
        votes: Dict[str, float],
        vote_counts: Dict[str, int],
        participants: List[str],
        strategy: VotingStrategy
    ) -> str:
        """Resolve vote based on strategy."""
        if strategy == VotingStrategy.UNANIMOUS:
            # Check if any option has all votes
            for option, count in vote_counts.items():
                if count == len(participants):
                    return option
            # No unanimity, return highest voted
            return max(votes, key=votes.get)
        
        elif strategy == VotingStrategy.MAJORITY:
            # Require >50%
            majority_threshold = len(participants) / 2
            for option in sorted(vote_counts, key=vote_counts.get, reverse=True):
                if vote_counts[option] > majority_threshold:
                    return option
            # No majority, return highest voted
            return max(votes, key=votes.get)
        
        elif strategy == VotingStrategy.WEIGHTED:
            # Return highest weighted vote
            return max(votes, key=votes.get)
        
        else:  # SIMPLE_PLURALITY
            # Return option with most votes
            return max(vote_counts, key=vote_counts.get)
    
    def _generate_voting_reasoning(
        self,
        positions: Dict[str, BotPosition],
        final_decision: str,
        strategy: VotingStrategy
    ) -> str:
        """Generate reasoning for voting result."""
        lines = [f"Decision made using {strategy.value} voting."]
        lines.append(f"Final decision: {final_decision}")
        lines.append("Positions:")
        for bot_id, pos in positions.items():
            lines.append(f"  - {bot_id}: {pos.position} (confidence: {pos.confidence:.1%})")
        return "\n".join(lines)
    
    def _find_common_ground(self, positions: Dict[str, BotPosition]) -> str:
        """Find common themes or ground in positions."""
        if not positions:
            return ""
        
        # Extract common reasoning themes
        all_reasoning = " ".join(pos.reasoning for pos in positions.values())
        
        # Simple heuristic: find longest common substring
        if len(positions) <= 1:
            return ""
        
        position_list = list(positions.values())
        common = set(position_list[0].reasoning.split())
        
        for pos in position_list[1:]:
            common &= set(pos.reasoning.split())
        
        return " ".join(sorted(common)) if common else "shared objective"
    
    def _find_most_expert_bot(self, positions: Dict[str, BotPosition]) -> str:
        """Find bot with highest expertise score."""
        best_bot = max(
            positions.items(),
            key=lambda x: x[1].expertise_score or 0.0
        )
        return best_bot[0]
    
    def _summarize_dissent(self, positions: Dict[str, BotPosition], chosen: str) -> Optional[str]:
        """Summarize dissenting views."""
        dissenters = [
            f"{bot_id}: {pos.position}"
            for bot_id, pos in positions.items()
            if pos.position != chosen
        ]
        
        if not dissenters:
            return None
        
        return "Dissenting views: " + "; ".join(dissenters)


class DisputeResolver:
    """Resolves disagreements between bots.
    
    Analyzes conflicts, finds common ground, and helps reach resolution
    through mediation and escalation.
    """
    
    def __init__(self):
        """Initialize dispute resolver."""
        self.disagreements: Dict[str, Disagreement] = {}
        self.resolution_history: List[Tuple[str, str, str]] = []  # (disagreement_id, resolution, outcome)
    
    def detect_disagreement(
        self,
        positions: Dict[str, BotPosition]
    ) -> Optional[Disagreement]:
        """Detect if bots disagree on something.
        
        Args:
            positions: Dict mapping bot_id -> BotPosition
            
        Returns:
            Disagreement object if disagreement found, None otherwise
        """
        if len(positions) < 2:
            return None
        
        # Check if positions differ
        position_values = set(pos.position for pos in positions.values())
        if len(position_values) <= 1:
            return None  # Agreement
        
        # Disagreement detected
        disagreement = Disagreement(
            positions=positions,
            disagreement_type=self._infer_disagreement_type(positions)
        )
        
        self.disagreements[disagreement.id] = disagreement
        return disagreement
    
    def analyze_arguments(
        self,
        disagreement: Disagreement
    ) -> Dict[str, Any]:
        """Analyze arguments in a disagreement.
        
        Args:
            disagreement: The disagreement to analyze
            
        Returns:
            Analysis dictionary with key findings
        """
        analysis = {
            "num_positions": len(set(pos.position for pos in disagreement.positions.values())),
            "positions": {},
            "confidence_spread": 0.0,
            "reasoning_themes": {},
        }
        
        # Analyze each position
        confidences = []
        for bot_id, pos in disagreement.positions.items():
            analysis["positions"][bot_id] = {
                "position": pos.position,
                "confidence": pos.confidence,
                "reasoning": pos.reasoning,
                "expertise": pos.expertise_score
            }
            confidences.append(pos.confidence)
        
        # Calculate confidence spread
        if confidences:
            analysis["confidence_spread"] = max(confidences) - min(confidences)
        
        # Extract reasoning themes
        all_reasoning = " ".join(pos.reasoning for pos in disagreement.positions.values())
        words = all_reasoning.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 4:  # Only significant words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        analysis["reasoning_themes"] = sorted(
            word_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return analysis
    
    def find_common_ground(
        self,
        disagreement: Disagreement
    ) -> str:
        """Find common ground between disagreeing bots.
        
        Args:
            disagreement: The disagreement to analyze
            
        Returns:
            Summary of common ground
        """
        # Find shared interests or values in reasoning
        all_reasons = [pos.reasoning for pos in disagreement.positions.values()]
        
        common_themes = []
        
        # Check for shared goals
        for theme in ["goal", "objective", "aim", "need", "important", "critical"]:
            if sum(1 for reason in all_reasons if theme in reason.lower()) > len(all_reasons) / 2:
                common_themes.append(f"shared {theme}")
        
        if common_themes:
            disagreement.common_ground = f"Despite disagreement, bots share: {', '.join(common_themes)}"
        else:
            disagreement.common_ground = "Both positions aim to improve coordination"
        
        return disagreement.common_ground
    
    def make_final_decision(
        self,
        disagreement: Disagreement,
        decision_maker: DecisionMaker
    ) -> Decision:
        """Make a final decision when disagreement persists.
        
        Args:
            disagreement: The disagreement
            decision_maker: DecisionMaker to use for resolution
            
        Returns:
            Final decision
        """
        # Try expertise-weighted approach
        sorted_bots = sorted(
            disagreement.positions.items(),
            key=lambda x: (x[1].expertise_score or 0.0, x[1].confidence),
            reverse=True
        )
        
        if sorted_bots:
            chosen_bot, best_pos = sorted_bots[0]
            final_decision = best_pos.position
            confidence = best_pos.confidence * (best_pos.expertise_score or 0.7)
        else:
            final_decision = "escalate to user"
            confidence = 0.3
        
        decision = Decision(
            task_id=disagreement.task_id,
            decision_type="dispute_resolution",
            participants=list(disagreement.positions.keys()),
            positions=disagreement.positions,
            final_decision=final_decision,
            confidence=min(confidence, 1.0),
            reasoning=f"Resolved by selecting position from most expert and confident bot",
            dissent=self._build_dissent_summary(disagreement, final_decision)
        )
        
        self.resolution_history.append((disagreement.id, "expertise_weighted", "resolved"))
        
        return decision
    
    def get_disagreement(self, disagreement_id: str) -> Optional[Disagreement]:
        """Get a disagreement by ID.
        
        Args:
            disagreement_id: The disagreement ID
            
        Returns:
            Disagreement or None if not found
        """
        return self.disagreements.get(disagreement_id)
    
    def get_disagreements_for_task(self, task_id: str) -> List[Disagreement]:
        """Get all disagreements for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of disagreements for the task
        """
        return [d for d in self.disagreements.values() if d.task_id == task_id]
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _infer_disagreement_type(self, positions: Dict[str, BotPosition]) -> DisagreementType:
        """Infer the type of disagreement from positions."""
        # Simple heuristic: check reasoning for keywords
        all_reasoning = " ".join(pos.reasoning for pos in positions.values()).lower()
        
        if any(word in all_reasoning for word in ["how", "method", "approach", "way"]):
            return DisagreementType.METHODOLOGICAL
        
        if any(word in all_reasoning for word in ["important", "urgent", "critical", "priority"]):
            return DisagreementType.PRIORITY
        
        if any(word in all_reasoning for word in ["believe", "value", "goal", "principle"]):
            return DisagreementType.PHILOSOPHICAL
        
        if any(word in all_reasoning for word in ["need", "missing", "lack", "insufficient"]):
            return DisagreementType.INCOMPLETE_INFO
        
        return DisagreementType.FACTUAL
    
    def _build_dissent_summary(self, disagreement: Disagreement, chosen: str) -> Optional[str]:
        """Build summary of dissenting views."""
        dissenters = [
            f"{bot_id}: {pos.position} (confidence: {pos.confidence:.0%})"
            for bot_id, pos in disagreement.positions.items()
            if pos.position != chosen
        ]
        
        if not dissenters:
            return None
        
        return f"Dissenting views ({len(dissenters)} bots): " + "; ".join(dissenters)
