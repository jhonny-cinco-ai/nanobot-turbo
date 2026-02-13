"""Explanation generation for coordination decisions.

Provides clear, human-readable explanations of why decisions were made,
why bots were selected, how consensus was reached, and why failures occurred.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Explanation:
    """A generated explanation for a coordination decision."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""                      # What is being explained
    explanation_type: str = ""             # Type of explanation
    
    # The explanation content
    summary: str = ""                      # Brief summary
    details: List[str] = field(default_factory=list)  # Detailed points
    reasoning_chain: List[str] = field(default_factory=list)  # Step-by-step
    
    # Supporting evidence
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0                # Confidence in explanation
    
    # Alternatives considered
    alternatives: List[str] = field(default_factory=list)
    why_chosen: str = ""                   # Why this over alternatives
    
    timestamp: datetime = field(default_factory=datetime.now)


class ExplanationEngine:
    """Generates clear explanations for coordination decisions.
    
    Explains:
    - Why specific bots were selected
    - How consensus was reached
    - Why failures occurred
    - What dissent existed and why
    """
    
    def __init__(self):
        """Initialize explanation engine."""
        self.explanations: Dict[str, Explanation] = {}
    
    def explain_bot_selection(
        self,
        selected_bot: str,
        available_bots: List[str],
        domain: str,
        expertise_scores: Dict[str, float],
        task_complexity: str = "medium"
    ) -> Explanation:
        """Generate explanation for why a bot was selected.
        
        Args:
            selected_bot: The bot that was chosen
            available_bots: All bots that could have been selected
            domain: Task domain
            expertise_scores: Score per bot
            task_complexity: Complexity level
            
        Returns:
            Explanation object
        """
        selected_score = expertise_scores.get(selected_bot, 0)
        
        # Sort bots by expertise
        sorted_bots = sorted(
            expertise_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Generate summary
        summary = f"{selected_bot} was selected for {domain} task " \
                 f"based on expertise score of {selected_score:.0%}"
        
        # Generate details
        details = [
            f"Task domain: {domain}",
            f"Task complexity: {task_complexity}",
            f"Available bots: {len(available_bots)}",
            f"{selected_bot}'s expertise score: {selected_score:.2f}",
        ]
        
        # Add comparison with other bots
        other_bots = [(bot, score) for bot, score in sorted_bots if bot != selected_bot]
        if other_bots:
            details.append(f"Next best option: {other_bots[0][0]} (score: {other_bots[0][1]:.2f})")
            details.append(f"Selection advantage: {selected_score - other_bots[0][1]:.2f} points")
        
        # Build reasoning chain
        reasoning_chain = [
            f"1. Identified {len(available_bots)} bots available for {domain}",
            f"2. Evaluated each bot's expertise in {domain}",
            f"3. {selected_bot} had highest score at {selected_score:.0%}",
            f"4. Task assigned to {selected_bot}",
        ]
        
        # Build evidence
        evidence = {
            "domain": domain,
            "task_complexity": task_complexity,
            "expertise_scores": expertise_scores,
            "selection_method": "expertise_based",
        }
        
        explanation = Explanation(
            subject=f"Bot Selection for {domain}",
            explanation_type="bot_selection",
            summary=summary,
            details=details,
            reasoning_chain=reasoning_chain,
            evidence=evidence,
            confidence=selected_score,
            alternatives=[bot for bot, _ in other_bots[:3]],
            why_chosen=f"Highest expertise score in {domain} domain"
        )
        
        self.explanations[explanation.id] = explanation
        return explanation
    
    def explain_consensus(
        self,
        decision: str,
        participants: List[str],
        positions: Dict[str, str],
        confidence_scores: Dict[str, float],
        voting_strategy: str = "majority"
    ) -> Explanation:
        """Generate explanation for how consensus was reached.
        
        Args:
            decision: The final consensus decision
            participants: Bot IDs who participated
            positions: Dict of bot_id -> position
            confidence_scores: Dict of bot_id -> confidence
            voting_strategy: Strategy used (unanimous, majority, weighted)
            
        Returns:
            Explanation object
        """
        # Count support for decision
        supporters = [bot for bot, pos in positions.items() if pos == decision]
        support_rate = len(supporters) / len(participants) if participants else 0
        
        # Calculate average confidence of supporters
        avg_confidence = sum(
            confidence_scores.get(bot, 0.5) for bot in supporters
        ) / len(supporters) if supporters else 0
        
        summary = f"Team consensus: '{decision}' with {len(supporters)}/{len(participants)} " \
                 f"bots in agreement ({support_rate:.0%})"
        
        details = [
            f"Decision method: {voting_strategy}",
            f"Participants: {len(participants)} bots",
            f"Supporting bots: {', '.join(supporters)}",
            f"Average confidence: {avg_confidence:.0%}",
        ]
        
        # Add position breakdown
        unique_positions = set(positions.values())
        for pos in unique_positions:
            count = sum(1 for p in positions.values() if p == pos)
            bots = [b for b, p in positions.items() if p == pos]
            details.append(f"  - '{pos}': {count} bot(s) - {', '.join(bots)}")
        
        # Build reasoning chain
        reasoning_chain = [
            f"1. {len(participants)} bots participated in decision",
            f"2. Used {voting_strategy} voting strategy",
            f"3. {len(supporters)} bots ({support_rate:.0%}) supported '{decision}'",
        ]
        
        if voting_strategy == "weighted":
            total_weight = sum(confidence_scores.values())
            decision_weight = sum(
                confidence_scores.get(bot, 0) for bot in supporters
            )
            reasoning_chain.append(
                f"4. Weighted vote: {decision_weight:.1f}/{total_weight:.1f} "
                f"({decision_weight/total_weight:.0%})"
            )
        
        reasoning_chain.append(f"5. Consensus reached with {avg_confidence:.0%} average confidence")
        
        evidence = {
            "voting_strategy": voting_strategy,
            "positions": positions,
            "confidence_scores": confidence_scores,
            "support_rate": support_rate,
            "agreement_count": len(supporters),
        }
        
        explanation = Explanation(
            subject=f"Consensus Decision: {decision}",
            explanation_type="consensus",
            summary=summary,
            details=details,
            reasoning_chain=reasoning_chain,
            evidence=evidence,
            confidence=support_rate * avg_confidence,
            alternatives=list(unique_positions - {decision}),
            why_chosen=f"Reached {voting_strategy} threshold with {support_rate:.0%} support"
        )
        
        self.explanations[explanation.id] = explanation
        return explanation
    
    def explain_failure(
        self,
        task_id: str,
        error: str,
        assigned_bot: str,
        recovery_attempts: int = 0,
        context: Optional[Dict[str, Any]] = None
    ) -> Explanation:
        """Generate explanation for why a task failed.
        
        Args:
            task_id: The failed task ID
            error: Error message
            assigned_bot: Bot that was assigned
            recovery_attempts: Number of recovery attempts made
            context: Additional context
            
        Returns:
            Explanation object
        """
        summary = f"Task {task_id} failed while being executed by {assigned_bot}"
        
        details = [
            f"Assigned bot: {assigned_bot}",
            f"Error: {error}",
        ]
        
        if recovery_attempts > 0:
            details.append(f"Recovery attempts: {recovery_attempts}")
        
        # Analyze error type
        error_categories = {
            "timeout": "Task took too long to complete",
            "error": "An error occurred during execution",
            "unavailable": "Required resource was unavailable",
            "invalid": "Task requirements were invalid",
            "blocked": "Task was blocked by dependencies",
        }
        
        error_type = "error"
        for category in error_categories:
            if category in error.lower():
                error_type = category
                details.append(f"Error category: {error_categories[category]}")
                break
        
        # Build reasoning chain
        reasoning_chain = [
            f"1. Task {task_id} assigned to {assigned_bot}",
            f"2. {assigned_bot} attempted to execute task",
            f"3. Error occurred: {error}",
        ]
        
        if recovery_attempts > 0:
            reasoning_chain.append(f"4. {recovery_attempts} recovery attempts made")
            reasoning_chain.append("5. All recovery attempts failed")
        
        reasoning_chain.append("6. Task marked as failed")
        
        # Generate suggestions
        suggestions = []
        if "expertise" in error.lower():
            suggestions.append("Consider assigning to bot with higher expertise")
        if "timeout" in error.lower():
            suggestions.append("Consider breaking task into smaller sub-tasks")
        if "dependency" in error.lower() or "blocked" in error.lower():
            suggestions.append("Check task dependencies and resolve blockers first")
        
        evidence = {
            "task_id": task_id,
            "assigned_bot": assigned_bot,
            "error": error,
            "error_type": error_type,
            "recovery_attempts": recovery_attempts,
            "context": context or {},
        }
        
        if suggestions:
            evidence["suggestions"] = suggestions
        
        explanation = Explanation(
            subject=f"Task Failure: {task_id}",
            explanation_type="failure",
            summary=summary,
            details=details,
            reasoning_chain=reasoning_chain,
            evidence=evidence,
            confidence=0.9,  # High confidence we know it failed
            alternatives=suggestions,
            why_chosen="Error occurred during execution that could not be recovered"
        )
        
        self.explanations[explanation.id] = explanation
        return explanation
    
    def explain_dissent(
        self,
        decision: str,
        positions: Dict[str, str],
        dissenting_bots: List[str],
        reasons: Optional[Dict[str, str]] = None
    ) -> Explanation:
        """Generate explanation of dissenting views.
        
        Args:
            decision: The decision that was made
            positions: All bot positions
            dissenting_bots: Bots who disagreed
            reasons: Optional dict of bot_id -> reason for dissent
            
        Returns:
            Explanation object
        """
        summary = f"{len(dissenting_bots)} bot(s) disagreed with decision: '{decision}'"
        
        details = [
            f"Final decision: {decision}",
            f"Dissenting bots: {', '.join(dissenting_bots)}",
        ]
        
        # Detail each dissenting position
        dissenting_positions = set()
        for bot in dissenting_bots:
            pos = positions.get(bot, "unknown")
            dissenting_positions.add(pos)
            reason = reasons.get(bot, "No specific reason given") if reasons else "No specific reason given"
            details.append(f"  - {bot} preferred '{pos}': {reason}")
        
        # Build reasoning chain
        reasoning_chain = [
            f"1. Team vote resulted in '{decision}'",
            f"2. {len(dissenting_bots)} bot(s) held alternative view(s)",
            f"3. Dissenting positions: {', '.join(dissenting_positions)}",
            "4. Decision was made based on majority/support threshold",
            "5. Dissent was noted and documented",
        ]
        
        evidence = {
            "final_decision": decision,
            "all_positions": positions,
            "dissenting_bots": dissenting_bots,
            "dissenting_positions": list(dissenting_positions),
            "reasons": reasons or {},
        }
        
        explanation = Explanation(
            subject=f"Dissent on Decision: {decision}",
            explanation_type="dissent",
            summary=summary,
            details=details,
            reasoning_chain=reasoning_chain,
            evidence=evidence,
            confidence=0.8,
            alternatives=list(dissenting_positions),
            why_chosen="Decision followed voting/consensus protocol despite minority dissent"
        )
        
        self.explanations[explanation.id] = explanation
        return explanation
    
    def explain_routing(
        self,
        request: str,
        analysis: Dict[str, Any],
        selected_bots: List[str],
        approach: str
    ) -> Explanation:
        """Generate explanation for routing decision.
        
        Args:
            request: User's original request
            analysis: Analysis of the request
            selected_bots: Bots selected to handle request
            approach: Approach taken (direct, team, parallel, etc.)
            
        Returns:
            Explanation object
        """
        domains = analysis.get("domains", [])
        complexity = analysis.get("complexity", "medium")
        
        summary = f"Request routed to {', '.join(selected_bots)} using {approach} approach"
        
        details = [
            f"Request domains: {', '.join(domains) if domains else 'general'}",
            f"Complexity: {complexity}",
            f"Approach: {approach}",
            f"Selected bots: {', '.join(selected_bots)}",
        ]
        
        # Add complexity rationale
        if complexity == "high":
            details.append("High complexity requires team coordination")
        elif complexity == "low":
            details.append("Low complexity allows direct handling")
        
        # Add multi-domain rationale
        if len(domains) > 1:
            details.append(f"Multiple domains ({len(domains)}) require multi-bot approach")
        
        reasoning_chain = [
            "1. Request analyzed for content and complexity",
            f"2. Identified {len(domains)} domain(s): {', '.join(domains) if domains else 'general'}",
            f"3. Complexity assessed as {complexity}",
            f"4. {approach} approach selected based on complexity and domains",
            f"5. Assigned to {', '.join(selected_bots)}",
        ]
        
        evidence = {
            "request_preview": request[:100] + "..." if len(request) > 100 else request,
            "analysis": analysis,
            "approach": approach,
            "selected_bots": selected_bots,
        }
        
        explanation = Explanation(
            subject="Request Routing Decision",
            explanation_type="routing",
            summary=summary,
            details=details,
            reasoning_chain=reasoning_chain,
            evidence=evidence,
            confidence=0.85,
            alternatives=["different_bot_selection"],
            why_chosen=f"Best match for {complexity} complexity and {len(domains)} domain(s)"
        )
        
        self.explanations[explanation.id] = explanation
        return explanation
    
    def get_explanation(self, explanation_id: str) -> Optional[Explanation]:
        """Retrieve a stored explanation.
        
        Args:
            explanation_id: The explanation ID
            
        Returns:
            Explanation or None
        """
        return self.explanations.get(explanation_id)
    
    def format_explanation(
        self,
        explanation: Explanation,
        detail_level: str = "detailed"
    ) -> str:
        """Format explanation for display.
        
        Args:
            explanation: The explanation to format
            detail_level: "brief", "detailed", or "full"
            
        Returns:
            Formatted string
        """
        lines = [
            f"=== {explanation.subject} ===",
            f"Type: {explanation.explanation_type}",
            "",
            "SUMMARY:",
            f"  {explanation.summary}",
        ]
        
        if detail_level in ["detailed", "full"]:
            lines.extend([
                "",
                "DETAILS:",
            ])
            for detail in explanation.details:
                lines.append(f"  • {detail}")
        
        if detail_level == "full":
            lines.extend([
                "",
                "REASONING:",
            ])
            for step in explanation.reasoning_chain:
                lines.append(f"  {step}")
            
            if explanation.alternatives:
                lines.extend([
                    "",
                    "ALTERNATIVES CONSIDERED:",
                ])
                for alt in explanation.alternatives:
                    lines.append(f"  • {alt}")
            
            lines.extend([
                "",
                f"WHY CHOSEN: {explanation.why_chosen}",
            ])
        
        lines.extend([
            "",
            f"Confidence: {explanation.confidence:.0%}",
        ])
        
        return "\n".join(lines)
    
    def generate_report(
        self,
        task_id: Optional[str] = None,
        explanation_type: Optional[str] = None
    ) -> List[Explanation]:
        """Generate report of explanations.
        
        Args:
            task_id: Filter by task
            explanation_type: Filter by type
            
        Returns:
            List of explanations
        """
        explanations = list(self.explanations.values())
        
        if task_id:
            explanations = [
                e for e in explanations
                if e.evidence.get("task_id") == task_id
            ]
        
        if explanation_type:
            explanations = [
                e for e in explanations
                if e.explanation_type == explanation_type
            ]
        
        return sorted(explanations, key=lambda e: e.timestamp, reverse=True)
