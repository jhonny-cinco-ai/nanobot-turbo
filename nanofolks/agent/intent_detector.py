"""Intent Detection - Routes user messages to appropriate flow types."""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from loguru import logger


class IntentType(Enum):
    """Types of user intent."""
    BUILD = "build"
    EXPLORE = "explore"
    ADVICE = "advice"
    RESEARCH = "research"
    CHAT = "chat"
    TASK = "task"


class FlowType(Enum):
    """Flow types for handling intents."""
    SIMULTANEOUS = "simultaneous"
    QUICK = "quick"
    FULL = "full"


@dataclass
class Intent:
    """Represents a detected user intent."""
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_bots: List[str] = field(default_factory=list)
    flow_type: FlowType = FlowType.SIMULTANEOUS


class IntentDetector:
    """Detect user intent from message content.
    
    Maps user messages to intents and determines the appropriate
    flow type (simultaneous, quick, or full discovery).
    """

    INTENT_PATTERNS = {
        IntentType.BUILD: [
            'build a', 'create a', 'make a', 'develop a', 'design a',
            'build me', 'create me', 'make me', 'develop me',
            'build my', 'create my', 'make my',
            'i want to build', 'i want to create', 'i want to make',
            'start building', 'start creating',
        ],
        IntentType.EXPLORE: [
            'can i', 'could i', 'wonder if', 'ways to',
            'how to make money', 'how can i make money', 'monetize',
            'profit from', 'earn from', 'is there a way',
            'business idea', 'start a business', 'entrepreneur',
            'what if i combine', 'can i combine',
        ],
        IntentType.ADVICE: [
            'how do i', 'how can i', 'how should i',
            'what is the best way', 'what\'s the best way',
            'tips for', 'advice on', 'help me figure out',
            'what should i do', 'what do you recommend',
            'suggestions for', 'how would you',
        ],
        IntentType.RESEARCH: [
            'research', 'find out', 'learn about',
            'information on', 'looking for info', 'need to know',
            'fun ways', 'best ways', 'top ways',
            'what are the best', 'what are some',
        ],
        IntentType.TASK: [
            'write this', 'write an', 'write a',
            'send a', 'schedule a', 'remind me to',
            'calculate', 'convert', 'translate',
            'summarize', 'extract', 'analyze this',
            'fix this', 'debug this', 'review this',
        ],
        IntentType.CHAT: [
            'what do you think', 'interesting', 'oh', 'wow',
            'tell me more', 'really?', 'nice', 'cool',
            'that\'s', 'i see', 'hmm',
            'hello', 'hi', 'hey', 'how are you',
            'thanks', 'thank you', 'okay', 'sure',
        ]
    }

    FLOW_MAPPING = {
        IntentType.CHAT: FlowType.SIMULTANEOUS,
        IntentType.ADVICE: FlowType.QUICK,
        IntentType.RESEARCH: FlowType.QUICK,
        IntentType.EXPLORE: FlowType.FULL,
        IntentType.TASK: FlowType.FULL,
        IntentType.BUILD: FlowType.FULL,
    }

    SUGGESTED_BOTS = {
        IntentType.BUILD: ["leader"],
        IntentType.EXPLORE: ["leader"],
        IntentType.ADVICE: ["leader"],
        IntentType.RESEARCH: ["leader"],
        IntentType.TASK: ["leader"],
        IntentType.CHAT: ["leader"],
    }

    ALL_BOTS = ["leader", "researcher", "creative", "coder", "social", "auditor"]

    def detect(self, message: str) -> Intent:
        """Detect intent from user message.
        
        Args:
            message: The user's message content
            
        Returns:
            Intent with detected type, confidence, and suggested flow
        """
        message_lower = message.lower()
        scores: Dict[IntentType, float] = {}

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            score = self._calculate_intent_score(message_lower, patterns)
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return self._default_intent()

        best_intent = max(scores, key=lambda k: scores[k])
        total_score = sum(scores.values())
        confidence = scores[best_intent] / total_score

        entities = self._extract_entities(message, best_intent)

        return Intent(
            intent_type=best_intent,
            confidence=confidence,
            entities=entities,
            suggested_bots=self.SUGGESTED_BOTS[best_intent],
            flow_type=self.FLOW_MAPPING[best_intent]
        )

    def _calculate_intent_score(self, message_lower: str, patterns: List[str]) -> float:
        """Calculate intent score based on pattern matching."""
        score = 0.0
        for pattern in patterns:
            if pattern in message_lower:
                score += 1.0
                if message_lower.startswith(pattern) or pattern in message_lower.split()[0:2]:
                    score += 0.5
        return score

    def _default_intent(self) -> Intent:
        """Return default CHAT intent when no pattern matches."""
        return Intent(
            intent_type=IntentType.CHAT,
            confidence=0.5,
            entities={},
            suggested_bots=self.SUGGESTED_BOTS[IntentType.CHAT],
            flow_type=FlowType.SIMULTANEOUS
        )

    def _extract_entities(self, message: str, intent_type: IntentType) -> Dict[str, Any]:
        """Extract relevant entities from message."""
        entities = {}
        
        if intent_type in [IntentType.EXPLORE, IntentType.RESEARCH]:
            import re
            combined = re.findall(r'(\w+)\s+(?:and|&)\s+(\w+)', message.lower())
            if combined:
                entities['combined_interests'] = combined[0]

            people = re.findall(
                r'\b(?:my|son|daughter|wife|husband|friend|kid|kids|child|children)\b',
                message.lower()
            )
            if people:
                entities['people_mentioned'] = people

        if intent_type == IntentType.BUILD:
            import re
            project_type = re.search(
                r'(?:build|create|make|develop)\s+(?:a|an)?\s*(\w+)',
                message.lower()
            )
            if project_type:
                entities['project_type'] = project_type.group(1)

        return entities

    def get_all_bots_for_intent(self, intent: Intent) -> List[str]:
        """Get all bots that should respond for a given intent.
        
        For CHAT/SIMULTANEOUS, returns all bots for communal experience.
        For other intents, returns suggested bots.
        """
        if intent.flow_type == FlowType.SIMULTANEOUS:
            return self.ALL_BOTS
        return intent.suggested_bots


def get_intent_detector() -> IntentDetector:
    """Get IntentDetector instance."""
    return IntentDetector()
