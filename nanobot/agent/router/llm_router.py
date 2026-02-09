"""LLM-assisted router for uncertain classifications."""

import json
from typing import Any, Optional

from nanobot.providers.base import LLMProvider

from .models import RoutingDecision, RoutingTier


# Detailed classification prompt
CLASSIFICATION_PROMPT = """You are a routing classifier for an AI assistant called nanobot. 

Analyze the user's message and classify it into ONE of these tiers:

SIMPLE: Quick questions, facts, definitions, translations, simple calculations, casual conversation.
Examples: "What's 2+2?", "Define photosynthesis", "Translate hello to French", "What day is it?"
Characteristics: Single answer, no reasoning needed, <50 tokens likely

MEDIUM: General coding tasks, file operations, web searches, explanations with examples, planning.
Examples: "Write a Python function to parse JSON", "Search for React best practices", "Explain how async/await works"
Characteristics: Some context needed, may use tools, 50-200 tokens likely

COMPLEX: Multi-step reasoning, complex algorithms, large codebases, debugging tricky issues, architectural decisions, security reviews.
Examples: "Debug why this distributed system is failing", "Design a database schema for this complex domain", "Refactor this 1000-line function"
Characteristics: Deep analysis needed, multiple steps, 200-1000 tokens likely

REASONING: Formal proofs, mathematical derivations, step-by-step logical reasoning, complex problem-solving requiring deep analysis.
Examples: "Prove this theorem", "Walk me through this algorithm step by step", "Analyze the time complexity"
Characteristics: Requires careful reasoning, chains of logic, >1000 tokens likely

Respond ONLY with a JSON object in this exact format:
{
    "tier": "SIMPLE|MEDIUM|COMPLEX|CODING|REASONING",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this tier was chosen",
    "estimated_tokens": 50|200|1000|2000,
    "needs_tools": true|false
}

User message to classify:
"""


class LLMRouter:
    """LLM-assisted classification for uncertain cases."""
    
    def __init__(
        self,
        provider: LLMProvider,
        model: str = "gpt-4o-mini",
        timeout_ms: int = 500,
        secondary_model: str | None = None,
    ):
        self.provider = provider
        self.model = model
        self.timeout_ms = timeout_ms
        self.secondary_model = secondary_model
    
    async def classify(self, content: str) -> RoutingDecision:
        """
        Classify content using LLM assistance.
        
        Args:
            content: The message/content to classify
        
        Returns:
            RoutingDecision with LLM-determined tier
        """
        # Build classification prompt
        messages = [
            {
                "role": "system",
                "content": "You are a routing classifier. Respond ONLY with valid JSON."
            },
            {
                "role": "user",
                "content": CLASSIFICATION_PROMPT + content
            }
        ]
        
        try:
            # Call LLM with short timeout
            response = await self._call_llm(messages)
            
            # Parse JSON response
            result = self._parse_response(response)
            
            return RoutingDecision(
                tier=RoutingTier(result["tier"].lower()),
                model="",  # Will be filled by tier config
                confidence=result["confidence"],
                layer="llm",
                reasoning=result["reasoning"],
                estimated_tokens=result["estimated_tokens"],
                needs_tools=result["needs_tools"],
                metadata={
                    "llm_model": self.model,
                    "raw_response": response,
                },
            )
            
        except Exception as e:
            # Fallback to secondary model if configured, then to MEDIUM on failure
            if self.secondary_model:
                try:
                    response = await self._call_llm(messages, model=self.secondary_model)
                    result = self._parse_response(response)
                    return RoutingDecision(
                        tier=RoutingTier(result["tier"].lower()),
                        model="",
                        confidence=result["confidence"],
                        layer="llm",
                        reasoning=result["reasoning"],
                        estimated_tokens=result["estimated_tokens"],
                        needs_tools=result["needs_tools"],
                        metadata={
                            "llm_primary": self.model,
                            "llm_secondary": self.secondary_model,
                            "raw_response": response,
                        },
                    )
                except Exception:
                    pass
            # Fallback to medium tier on error
            return RoutingDecision(
                tier=RoutingTier.MEDIUM,
                model="",
                confidence=0.5,
                layer="llm",
                reasoning=f"Error in LLM classification: {str(e)}. Defaulting to medium tier.",
                estimated_tokens=200,
                needs_tools=True,
                metadata={"error": str(e)},
            )
    
    async def _call_llm(self, messages: list[dict[str, Any]], model: str | None = None) -> str:
        """Call the LLM with timeout."""
        import asyncio
        
        # Create task for LLM call
        actual_model = model or self.model
        llm_task = asyncio.create_task(
            self.provider.chat(
                messages=messages,
                model=actual_model,
                max_tokens=200,  # Short response needed
                temperature=0.1,  # Low temperature for consistency
            )
        )
        
        # Wait with timeout
        try:
            response = await asyncio.wait_for(
                llm_task,
                timeout=self.timeout_ms / 1000.0
            )
            return response.content or ""
        except asyncio.TimeoutError:
            raise TimeoutError(f"LLM classification timed out after {self.timeout_ms}ms")
    
    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse LLM JSON response."""
        # Clean up response - sometimes LLM adds markdown or extra text
        content = content.strip()
        
        # Extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        result = json.loads(content)
        
        # Validate required fields
        required = ["tier", "confidence", "reasoning", "estimated_tokens", "needs_tools"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")
        
        # Normalize tier
        result["tier"] = result["tier"].upper()
        valid_tiers = ["SIMPLE", "MEDIUM", "COMPLEX", "CODING", "REASONING"]
        if result["tier"] not in valid_tiers:
            raise ValueError(f"Invalid tier: {result['tier']}")
        
        # Normalize confidence
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
        
        # Normalize estimated_tokens to standard values
        tokens = int(result["estimated_tokens"])
        if tokens <= 100:
            result["estimated_tokens"] = 50
        elif tokens <= 500:
            result["estimated_tokens"] = 200
        elif tokens <= 1500:
            result["estimated_tokens"] = 1000
        else:
            result["estimated_tokens"] = 2000
        
        # Normalize needs_tools
        if isinstance(result["needs_tools"], str):
            result["needs_tools"] = result["needs_tools"].lower() == "true"
        else:
            result["needs_tools"] = bool(result["needs_tools"])
        
        return result
