"""Audit trail system for reasoning transparency.

Captures and tracks all coordination decisions, actions, and provides
full transparency into the decision-making process.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(str, Enum):
    """Types of events to audit."""
    DECISION_MADE = "decision_made"              # A decision was reached
    BOT_SELECTION = "bot_selection"              # Bot was selected for task
    CONSENSUS_REACHED = "consensus_reached"      # Team consensus achieved
    DISPUTE_DETECTED = "dispute_detected"        # Disagreement identified
    DISPUTE_RESOLVED = "dispute_resolved"        # Disagreement resolved
    TASK_ASSIGNED = "task_assigned"              # Task assigned to bot
    TASK_COMPLETED = "task_completed"            # Task finished
    TASK_FAILED = "task_failed"                  # Task failed
    ESCALATION = "escalation"                    # Escalated to user
    MESSAGE_SENT = "message_sent"                # Inter-bot message
    VOTING = "voting"                            # Vote cast
    REASONING = "reasoning"                      # Reasoning captured


class AuditEventSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """A single event in the audit trail.
    
    Captures what happened, who was involved, why it happened,
    and when it occurred.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: AuditEventType = AuditEventType.DECISION_MADE
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Who/what was involved
    task_id: Optional[str] = None
    bot_ids: List[str] = field(default_factory=list)
    user_id: Optional[str] = None
    
    # What happened
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    # Why it happened
    reasoning: str = ""
    rationale: Optional[str] = None
    
    # Impact assessment
    severity: AuditEventSeverity = AuditEventSeverity.INFO
    confidence: float = 0.0  # Confidence in this event (0.0-1.0)
    
    # Related events
    related_event_ids: List[str] = field(default_factory=list)
    
    # Escalation tracking
    escalated: bool = False
    escalation_reason: Optional[str] = None


@dataclass
class DecisionAuditRecord:
    """Comprehensive record of a coordination decision.
    
    Combines all information about a decision for full transparency.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""                          # Original decision ID
    timestamp: datetime = field(default_factory=datetime.now)
    
    # The decision
    final_decision: str = ""
    confidence: float = 0.0
    
    # Who participated
    participants: List[str] = field(default_factory=list)
    expertises: Dict[str, float] = field(default_factory=dict)  # bot_id -> score
    
    # What was considered
    options: List[str] = field(default_factory=list)
    positions: Dict[str, str] = field(default_factory=dict)  # bot_id -> position
    
    # Process used
    process_type: str = ""                         # consensus, vote, expertise, etc.
    process_details: Dict[str, Any] = field(default_factory=dict)
    
    # Full reasoning chain
    reasoning: str = ""
    reasoning_steps: List[str] = field(default_factory=list)
    
    # Dissent and concerns
    dissenting_views: List[str] = field(default_factory=list)
    concerns_raised: List[str] = field(default_factory=list)
    
    # Outcome tracking
    outcome: Optional[str] = None
    outcome_timestamp: Optional[datetime] = None
    outcome_verified: bool = False


class AuditTrail:
    """Comprehensive audit trail for coordination decisions.
    
    Logs every decision, action, and event for full transparency
    and accountability in multi-agent coordination.
    """
    
    def __init__(self):
        """Initialize audit trail."""
        self.events: Dict[str, AuditEvent] = {}
        self.decisions: Dict[str, DecisionAuditRecord] = {}
        self.task_audits: Dict[str, List[str]] = {}  # task_id -> list of event_ids
        self.bot_audits: Dict[str, List[str]] = {}   # bot_id -> list of event_ids
    
    def log_event(
        self,
        event_type: AuditEventType,
        description: str,
        task_id: Optional[str] = None,
        bot_ids: Optional[List[str]] = None,
        reasoning: str = "",
        details: Optional[Dict[str, Any]] = None,
        severity: AuditEventSeverity = AuditEventSeverity.INFO,
        confidence: float = 0.0,
        related_events: Optional[List[str]] = None
    ) -> str:
        """Log a single audit event.
        
        Args:
            event_type: Type of event
            description: Human-readable description
            task_id: Associated task ID
            bot_ids: Bot IDs involved
            reasoning: Why this event occurred
            details: Additional structured data
            severity: Event severity
            confidence: Confidence level (0.0-1.0)
            related_events: IDs of related audit events
            
        Returns:
            Event ID
        """
        event = AuditEvent(
            event_type=event_type,
            description=description,
            task_id=task_id,
            bot_ids=bot_ids or [],
            reasoning=reasoning,
            details=details or {},
            severity=severity,
            confidence=confidence,
            related_event_ids=related_events or []
        )
        
        self.events[event.id] = event
        
        # Index by task
        if task_id:
            if task_id not in self.task_audits:
                self.task_audits[task_id] = []
            self.task_audits[task_id].append(event.id)
        
        # Index by bot
        for bot_id in (bot_ids or []):
            if bot_id not in self.bot_audits:
                self.bot_audits[bot_id] = []
            self.bot_audits[bot_id].append(event.id)
        
        return event.id
    
    def log_decision(
        self,
        decision: DecisionAuditRecord
    ) -> str:
        """Log a comprehensive decision record.
        
        Args:
            decision: Complete decision audit record
            
        Returns:
            Decision audit record ID
        """
        self.decisions[decision.id] = decision
        
        # Create associated event
        self.log_event(
            event_type=AuditEventType.DECISION_MADE,
            description=f"Decision: {decision.final_decision}",
            task_id=decision.task_id if hasattr(decision, 'task_id') else None,
            bot_ids=decision.participants,
            reasoning=decision.reasoning,
            details={
                "decision_audit_id": decision.id,
                "decision_id": decision.decision_id,
                "process_type": decision.process_type,
                "confidence": decision.confidence,
            },
            confidence=decision.confidence
        )
        
        return decision.id
    
    def log_bot_selection(
        self,
        task_id: str,
        selected_bot: str,
        available_bots: List[str],
        domain: str,
        expertise_scores: Dict[str, float],
        reasoning: str = ""
    ) -> str:
        """Log bot selection for transparency.
        
        Args:
            task_id: The task
            selected_bot: Bot ID selected
            available_bots: All bots that could have been selected
            domain: Domain of the task
            expertise_scores: Score per bot
            reasoning: Why this bot was chosen
            
        Returns:
            Event ID
        """
        details = {
            "selected_bot": selected_bot,
            "available_bots": available_bots,
            "domain": domain,
            "expertise_scores": expertise_scores,
            "selection_method": "expertise-based",
        }
        
        if not reasoning:
            reasoning = f"Selected {selected_bot} based on highest expertise score " \
                       f"({expertise_scores.get(selected_bot, 0):.2f}) in {domain}"
        
        return self.log_event(
            event_type=AuditEventType.BOT_SELECTION,
            description=f"Bot {selected_bot} selected for task {task_id}",
            task_id=task_id,
            bot_ids=[selected_bot],
            reasoning=reasoning,
            details=details,
            confidence=expertise_scores.get(selected_bot, 0.5)
        )
    
    def log_consensus(
        self,
        task_id: str,
        decision: str,
        participants: List[str],
        agreement_rate: float,
        reasoning: str = ""
    ) -> str:
        """Log team consensus achievement.
        
        Args:
            task_id: The task
            decision: The consensus decision
            participants: Bots who agreed
            agreement_rate: Percentage in agreement (0.0-1.0)
            reasoning: Why consensus was reached
            
        Returns:
            Event ID
        """
        details = {
            "decision": decision,
            "agreement_rate": agreement_rate,
            "participant_count": len(participants),
        }
        
        if not reasoning:
            reasoning = f"Team reached {agreement_rate:.0%} agreement on: {decision}"
        
        return self.log_event(
            event_type=AuditEventType.CONSENSUS_REACHED,
            description=f"Consensus: {decision}",
            task_id=task_id,
            bot_ids=participants,
            reasoning=reasoning,
            details=details,
            confidence=agreement_rate
        )
    
    def log_escalation(
        self,
        decision_id: str,
        reason: str,
        task_id: Optional[str] = None,
        severity: AuditEventSeverity = AuditEventSeverity.WARNING
    ) -> str:
        """Log escalation to user.
        
        Args:
            decision_id: The decision that was escalated
            reason: Why escalation occurred
            task_id: Associated task
            severity: Escalation severity
            
        Returns:
            Event ID
        """
        event = AuditEvent(
            event_type=AuditEventType.ESCALATION,
            description=f"Decision {decision_id} escalated to user",
            task_id=task_id,
            reasoning=reason,
            details={"decision_id": decision_id},
            severity=severity,
            escalated=True,
            escalation_reason=reason
        )
        
        self.events[event.id] = event
        return event.id
    
    def get_decision_timeline(
        self,
        decision_id: str
    ) -> List[AuditEvent]:
        """Get timeline of events for a decision.
        
        Args:
            decision_id: The decision ID
            
        Returns:
            Chronological list of events
        """
        # Find all events related to this decision
        related_events = []
        
        for event in self.events.values():
            # Check if event directly references decision
            if event.details.get("decision_id") == decision_id:
                related_events.append(event)
            # Check if event is a decision record
            elif event.details.get("decision_audit_id") == decision_id:
                related_events.append(event)
        
        # Sort by timestamp
        return sorted(related_events, key=lambda e: e.timestamp)
    
    def get_task_audit_log(
        self,
        task_id: str,
        event_types: Optional[List[AuditEventType]] = None
    ) -> List[AuditEvent]:
        """Get audit log for a specific task.
        
        Args:
            task_id: The task ID
            event_types: Optional filter by event types
            
        Returns:
            List of audit events
        """
        event_ids = self.task_audits.get(task_id, [])
        events = [self.events[eid] for eid in event_ids if eid in self.events]
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        return sorted(events, key=lambda e: e.timestamp)
    
    def get_decision_record(
        self,
        decision_audit_id: str
    ) -> Optional[DecisionAuditRecord]:
        """Get comprehensive decision record.
        
        Args:
            decision_audit_id: The decision audit record ID
            
        Returns:
            Decision audit record or None
        """
        return self.decisions.get(decision_audit_id)
    
    def get_bot_activity(
        self,
        bot_id: str,
        event_types: Optional[List[AuditEventType]] = None
    ) -> List[AuditEvent]:
        """Get audit log for a specific bot.
        
        Args:
            bot_id: The bot ID
            event_types: Optional filter by event types
            
        Returns:
            List of audit events
        """
        event_ids = self.bot_audits.get(bot_id, [])
        events = [self.events[eid] for eid in event_ids if eid in self.events]
        
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        
        return sorted(events, key=lambda e: e.timestamp)
    
    def export_trail(
        self,
        task_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Export audit trail for analysis.
        
        Args:
            task_id: Filter by task
            bot_id: Filter by bot
            start_time: Filter by start time
            end_time: Filter by end time
            
        Returns:
            Dictionary with audit data
        """
        events = []
        
        for event in self.events.values():
            # Apply filters
            if task_id and event.task_id != task_id:
                continue
            if bot_id and bot_id not in event.bot_ids:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            
            events.append({
                "id": event.id,
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat(),
                "task_id": event.task_id,
                "bot_ids": event.bot_ids,
                "description": event.description,
                "reasoning": event.reasoning,
                "details": event.details,
                "severity": event.severity.value,
                "confidence": event.confidence,
            })
        
        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])
        
        return {
            "export_timestamp": datetime.now().isoformat(),
            "filter_task_id": task_id,
            "filter_bot_id": bot_id,
            "event_count": len(events),
            "events": events,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit trail statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_events": len(self.events),
            "total_decisions": len(self.decisions),
            "events_by_type": {},
            "events_by_severity": {},
            "tasks_audited": len(self.task_audits),
            "bots_audited": len(self.bot_audits),
            "escalations": 0,
            "high_confidence_events": 0,
        }
        
        for event in self.events.values():
            # Count by type
            type_key = event.event_type.value
            stats["events_by_type"][type_key] = \
                stats["events_by_type"].get(type_key, 0) + 1
            
            # Count by severity
            sev_key = event.severity.value
            stats["events_by_severity"][sev_key] = \
                stats["events_by_severity"].get(sev_key, 0) + 1
            
            # Count escalations
            if event.escalated:
                stats["escalations"] += 1
            
            # Count high confidence
            if event.confidence >= 0.8:
                stats["high_confidence_events"] += 1
        
        return stats
