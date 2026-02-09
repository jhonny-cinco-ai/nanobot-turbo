"""Client-side classifier for fast routing decisions."""

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ClassificationScores, RoutingDecision, RoutingPattern, RoutingTier


# Default 14-dimension weights (sum to 1.0)
DEFAULT_WEIGHTS = {
    "reasoning_markers": 0.18,
    "code_presence": 0.15,
    "simple_indicators": 0.12,
    "multi_step_patterns": 0.12,
    "technical_terms": 0.10,
    "token_count": 0.08,
    "creative_markers": 0.05,
    "question_complexity": 0.05,
    "constraint_count": 0.04,
    "imperative_verbs": 0.03,
    "output_format": 0.03,
    "domain_specificity": 0.02,
    "reference_complexity": 0.02,
    "negation_complexity": 0.01,
}

# Tier thresholds based on confidence score
DEFAULT_THRESHOLDS = {
    "simple": 0.0,
    "medium": 0.5,
    "complex": 0.85,
    "coding": 0.90,  # High threshold to ensure it's truly coding
    "reasoning": 0.97,
}

# Default patterns for initial classification
DEFAULT_PATTERNS = [
    RoutingPattern(
        regex=r"\b(prove|theorem|lemma|corollary|step by step|walk me through|explain why|derivation|formal proof)\b",
        tier=RoutingTier.REASONING,
        confidence=0.95,
        examples=["Prove that...", "Theorem states...", "Walk me through this algorithm"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"\b(refactor|architecture|distributed system|microservice|design pattern|security review|performance optimization)\b",
        tier=RoutingTier.COMPLEX,
        confidence=0.90,
        examples=["Refactor this codebase", "Design a distributed system"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"\b(debug|troubleshoot|complex algorithm|concurrency|threading|race condition|memory leak)\b",
        tier=RoutingTier.COMPLEX,
        confidence=0.85,
        examples=["Debug this issue", "Find the race condition"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"\b(write code|implement function|code review|unit test|integration test|api endpoint|database query|algorithm|data structure|fix bug|optimize code|refactor|code generator)\b",
        tier=RoutingTier.CODING,
        confidence=0.92,
        examples=["Write a function to sort an array", "Create an API endpoint", "Fix this bug"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"```[\w]*\n|^(function|class|def|async|await|import|const|let|var)\b",
        tier=RoutingTier.MEDIUM,
        confidence=0.80,
        examples=["Write a function to...", "Here's some code:"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"\b(search|find|look up|what is|how to|define|explain|translate|calculate)\b",
        tier=RoutingTier.SIMPLE,
        confidence=0.85,
        examples=["What is photosynthesis?", "How to cook pasta?", "Translate hello"],
        added_at=datetime.now().isoformat(),
    ),
    RoutingPattern(
        regex=r"\b(hi|hello|hey|greetings|bye|goodbye|thanks|good morning|good afternoon|good night)\b",
        tier=RoutingTier.SIMPLE,
        confidence=0.95,
        examples=["Hi there", "Hello!", "Goodbye", "Good morning"],
        added_at=datetime.now().isoformat(),
    ),
]


class ClientSideClassifier:
    """Fast client-side classifier using pattern matching and heuristics."""
    
    def __init__(
        self,
        patterns_file: Optional[Path] = None,
        min_confidence: float = 0.85,
        weights: Optional[dict[str, float]] = None,
        thresholds: Optional[dict[str, float]] = None,
    ):
        self.min_confidence = min_confidence
        self.weights = weights or DEFAULT_WEIGHTS
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.patterns_file = patterns_file
        self._patterns: list[RoutingPattern] = []
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load patterns from file or use defaults."""
        if self.patterns_file and self.patterns_file.exists():
            try:
                data = json.loads(self.patterns_file.read_text())
                self._patterns = [
                    RoutingPattern.from_dict(p) for p in data.get("patterns", [])
                ]
            except Exception:
                self._patterns = DEFAULT_PATTERNS.copy()
        else:
            self._patterns = DEFAULT_PATTERNS.copy()
    
    def classify(self, content: str) -> tuple[RoutingDecision, ClassificationScores]:
        """
        Classify content using client-side patterns and heuristics.
        
        Returns:
            Tuple of (RoutingDecision, ClassificationScores)
        """
        # Calculate 14-dimension scores
        scores = self._calculate_scores(content)
        
        # Calculate weighted confidence
        weighted_sum = scores.calculate_weighted_sum(self.weights)
        confidence = self._sigmoid(weighted_sum)
        
        # Determine tier based on confidence and patterns
        tier = self._determine_tier(confidence, content)
        
        # Check for pattern matches
        pattern_match = self._check_patterns(content)
        if pattern_match and pattern_match.confidence > confidence:
            tier = pattern_match.tier
            confidence = pattern_match.confidence
        
        decision = RoutingDecision(
            tier=tier,
            model="",  # Will be filled by tier config
            confidence=confidence,
            layer="client",
            reasoning=f"Client-side classification with confidence {confidence:.2f}",
            estimated_tokens=self._estimate_tokens(content, tier),
            needs_tools=self._needs_tools(content, tier),
            metadata={
                "scores": scores.to_dict(),
                "pattern_match": pattern_match.regex if pattern_match else None,
            },
        )
        
        return decision, scores
    
    def _calculate_scores(self, content: str) -> ClassificationScores:
        """Calculate all 14 dimension scores."""
        content_lower = content.lower()
        tokens = content.split()
        token_count = len(tokens)
        
        scores = ClassificationScores()
        
        # 1. Reasoning markers (0.18)
        reasoning_words = ["prove", "theorem", "lemma", "corollary", "step by step", 
                          "walk me through", "explain why", "derivation", "formal proof",
                          "demonstrate", "logical consequence"]
        scores.reasoning_markers = self._score_patterns(content_lower, reasoning_words)
        
        # 2. Code presence (0.15)
        code_indicators = ["function", "class", "def", "async", "await", "import",
                          "const", "let", "var", "return", "if", "for", "while",
                          "```", "(", ")", "{", "}", "[", "]"]
        code_score = self._score_patterns(content_lower, code_indicators)
        # Boost if code blocks present
        if "```" in content:
            code_score = min(1.0, code_score + 0.3)
        scores.code_presence = code_score
        
        # 3. Simple indicators (0.12)
        simple_words = ["what is", "define", "translate", "how to", "meaning of",
                       "what's", "what are", "difference between"]
        scores.simple_indicators = self._score_patterns(content_lower, simple_words)
        
        # 4. Multi-step patterns (0.12)
        multi_step = ["first", "then", "next", "after that", "step 1", "step 2",
                     "1.", "2.", "3.", "phase", "stage", "iteration"]
        scores.multi_step_patterns = self._score_patterns(content_lower, multi_step)
        
        # 5. Technical terms (0.10)
        technical = ["algorithm", "kubernetes", "distributed", "microservice",
                    "database", "api", "framework", "library", "protocol",
                    "architecture", "infrastructure", "deployment"]
        scores.technical_terms = self._score_patterns(content_lower, technical)
        
        # 6. Token count (0.08)
        if token_count < 50:
            scores.token_count = 0.1
        elif token_count < 200:
            scores.token_count = 0.5
        elif token_count < 500:
            scores.token_count = 0.7
        else:
            scores.token_count = 1.0
        
        # 7. Creative markers (0.05)
        creative = ["story", "poem", "creative", "imagine", "brainstorm", 
                   "write a", "generate ideas", "compose"]
        scores.creative_markers = self._score_patterns(content_lower, creative)
        
        # 8. Question complexity (0.05)
        question_marks = content.count("?")
        if question_marks == 0:
            scores.question_complexity = 0.0
        elif question_marks == 1:
            scores.question_complexity = 0.3
        else:
            scores.question_complexity = min(1.0, 0.3 + (question_marks - 1) * 0.2)
        
        # 9. Constraint count (0.04)
        constraints = ["at most", "at least", "minimum", "maximum", "limit",
                      "o(n)", "o(log n)", "efficient", "optimize"]
        scores.constraint_count = self._score_patterns(content_lower, constraints)
        
        # 10. Imperative verbs (0.03)
        imperative = ["build", "create", "implement", "design", "develop",
                     "write", "make", "setup", "configure", "deploy"]
        scores.imperative_verbs = self._score_patterns(content_lower, imperative)
        
        # 11. Output format (0.03)
        formats = ["json", "yaml", "xml", "csv", "markdown", "html",
                  "schema", "table", "list", "diagram"]
        scores.output_format = self._score_patterns(content_lower, formats)
        
        # 12. Domain specificity (0.02)
        domains = ["quantum", "blockchain", "machine learning", "ai", "genomics",
                  "bioinformatics", "cybersecurity", "cryptography"]
        scores.domain_specificity = self._score_patterns(content_lower, domains)
        
        # 13. Reference complexity (0.02)
        references = ["the docs", "the api", "the documentation", "above",
                     "previous", "earlier", "mentioned", "referenced"]
        scores.reference_complexity = self._score_patterns(content_lower, references)
        
        # 14. Negation complexity (0.01)
        negations = ["don't", "do not", "avoid", "without", "unless", 
                    "except", "but not", "rather than"]
        scores.negation_complexity = self._score_patterns(content_lower, negations)
        
        return scores
    
    def _score_patterns(self, content: str, patterns: list[str]) -> float:
        """Calculate pattern match score (0.0 to 1.0)."""
        if not patterns:
            return 0.0
        
        matches = sum(1 for pattern in patterns if pattern in content)
        # Normalize with diminishing returns
        return min(1.0, matches / len(patterns) * 2 + matches * 0.1)
    
    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for confidence calibration."""
        return 1.0 / (1.0 + math.exp(-x * 2))  # Scale factor of 2 for sharper transition
    
    def _determine_tier(self, confidence: float, content: str) -> RoutingTier:
        """Determine tier based on confidence score."""
        # Special rule: 2+ reasoning markers with high confidence
        reasoning_count = sum(1 for word in ["prove", "theorem", "step by step"] 
                             if word in content.lower())
        if reasoning_count >= 2 and confidence >= 0.95:
            return RoutingTier.REASONING
        
        # Special rule: Check for coding-specific patterns first
        coding_indicators = ["write code", "implement function", "code review", "unit test", 
                          "integration test", "api endpoint", "database query", "algorithm", 
                          "data structure", "fix bug", "optimize code", "refactor", "code generator"]
        coding_count = sum(1 for indicator in coding_indicators if indicator in content.lower())
        
        # High code presence + code-specific patterns = CODING tier
        if coding_count >= 1 and confidence >= self.thresholds["coding"]:
            return RoutingTier.CODING
        
        # Check thresholds
        if confidence >= self.thresholds["reasoning"]:
            return RoutingTier.REASONING
        elif confidence >= self.thresholds["complex"]:
            return RoutingTier.COMPLEX
        elif confidence >= self.thresholds["coding"]:
            return RoutingTier.CODING
        elif confidence >= self.thresholds["medium"]:
            return RoutingTier.MEDIUM
        else:
            return RoutingTier.SIMPLE
    
    def _check_patterns(self, content: str) -> Optional[RoutingPattern]:
        """Check for explicit pattern matches."""
        content_lower = content.lower()
        
        for pattern in self._patterns:
            if re.search(pattern.regex, content_lower, re.IGNORECASE):
                pattern.usage_count += 1
                return pattern
        
        return None
    
    def _estimate_tokens(self, content: str, tier: RoutingTier) -> int:
        """Estimate tokens needed based on content and tier."""
        base_tokens = len(content.split()) * 1.5  # Rough estimate
        
        tier_multipliers = {
            RoutingTier.SIMPLE: 50,
            RoutingTier.MEDIUM: 200,
            RoutingTier.COMPLEX: 1000,
            RoutingTier.CODING: 800,  # Between medium and complex
            RoutingTier.REASONING: 2000,
        }
        
        return int(base_tokens + tier_multipliers.get(tier, 200))
    
    def _needs_tools(self, content: str, tier: RoutingTier) -> bool:
        """Determine if tools are likely needed."""
        tool_indicators = [
            "search", "find", "look up", "web", "internet", "file",
            "read", "write", "execute", "run", "command", "shell",
            "code", "program", "script", "function", "class"
        ]
        
        content_lower = content.lower()
        tool_score = sum(1 for indicator in tool_indicators 
                        if indicator in content_lower)
        
        # Higher tiers more likely to need tools
        tier_boost = {
            RoutingTier.SIMPLE: 0,
            RoutingTier.MEDIUM: 1,
            RoutingTier.COMPLEX: 2,
            RoutingTier.REASONING: 1,
        }
        
        return tool_score + tier_boost.get(tier, 0) >= 2
    
    def save_patterns(self) -> None:
        """Save current patterns to file."""
        if self.patterns_file:
            data = {
                "patterns": [p.to_dict() for p in self._patterns],
                "version": "1.0",
            }
            self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
            self.patterns_file.write_text(json.dumps(data, indent=2))


def classify_content(
    content: str,
    patterns_file: Optional[Path] = None,
    min_confidence: float = 0.85,
) -> tuple[RoutingDecision, ClassificationScores]:
    """
    Convenience function for one-off classifications.
    
    Args:
        content: The message/content to classify
        patterns_file: Optional path to custom patterns file
        min_confidence: Minimum confidence for client-side classification
    
    Returns:
        Tuple of (RoutingDecision, ClassificationScores)
    """
    classifier = ClientSideClassifier(
        patterns_file=patterns_file,
        min_confidence=min_confidence,
    )
    return classifier.classify(content)
