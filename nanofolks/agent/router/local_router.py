"""Local Apple Foundation Model router for experimental routing."""

import json
from typing import Any, Optional

from loguru import logger

from .models import RoutingDecision, RoutingTier


LOCAL_CLASSIFICATION_PROMPT = """Classify this message into one tier:
- SIMPLE: quick facts, greetings, thanks, simple questions
- MEDIUM: explanations, searches, simple tasks
- CODING: code writing, debugging, implementations
- COMPLEX: multi-step tasks, architecture, complex debugging
- REASONING: proofs, logic, math

Respond with only JSON:
{{"tier": "SIMPLE|MEDIUM|CODING|COMPLEX|REASONING", "reasoning": "why", "needs_tools": true|false}}

Message: {content}
"""


class LocalRouter:
    """
    Experimental local Apple Foundation Model router.

    Uses Apple's on-device Foundation Models (via python-apple-fm-sdk)
    for classification when available. Falls back gracefully if unavailable.
    """

    def __init__(
        self,
        fallback_to_api: bool = True,
    ):
        self.fallback_to_api = fallback_to_api
        self._model = None
        self._available = None
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if Apple Foundation Model is available."""
        try:
            import apple_fm_sdk as fm

            model = fm.SystemLanguageModel()
            is_available, reason = model.is_available()
            if is_available:
                self._model = model
                self._available = True
                logger.info("Apple Foundation Model is available for local routing")
            else:
                self._available = False
                logger.warning(f"Apple Foundation Model not available: {reason}")
        except ImportError:
            self._available = False
            logger.warning("apple-fm-sdk not installed, local routing unavailable")
        except Exception as e:
            self._available = False
            logger.warning(f"Failed to initialize Apple Foundation Model: {e}")

    def is_available(self) -> bool:
        """Check if local model is available."""
        return self._available is True

    async def classify(
        self,
        content: str,
    ) -> Optional[RoutingDecision]:
        """
        Classify content using local Apple Foundation Model.

        Args:
            content: The message/content to classify

        Returns:
            RoutingDecision if successful, None if should fallback to API
        """
        if not self.is_available():
            return None

        try:
            import apple_fm_sdk as fm

            prompt = LOCAL_CLASSIFICATION_PROMPT.format(content=content)

            session = fm.LanguageModelSession()
            response = await session.respond(prompt)
            logger.debug(f"Local model raw response: {response}")

            result = self._parse_response(response)
            logger.debug(f"Local model parsed result: {result}")

            # Use .get() with fallback to avoid KeyError like '"tier"'
            tier_str = result.get("tier", "medium").lower()

            return RoutingDecision(
                tier=RoutingTier(tier_str),
                model="apple-on-device",
                confidence=result.get("confidence", 0.8),
                layer="local",
                reasoning=result.get("reasoning", "Local model classification"),
                estimated_tokens=self._estimate_tokens(content),
                needs_tools=result.get("needs_tools", True),
                metadata={
                    "local_model": "apple-foundation",
                    "raw_response": response,
                },
            )

        except ImportError:
            logger.warning("apple-fm-sdk not installed")
            return None
        except Exception as e:
            logger.error(f"Local model classification failed: {e}")
            return None

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse the model's JSON response with robust cleaning."""
        content = response.strip()
        
        # 1. Handle markdown JSON blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(content)
            
            # Ensure it's a dictionary
            if not isinstance(result, dict):
                return self._fallback_parse(content)

            # 2. Key cleaning: remove accidental quotes from keys (e.g. '"tier"' -> 'tier')
            cleaned_result = {}
            for k, v in result.items():
                if isinstance(k, str):
                    cleaned_key = k.strip().strip('"').strip("'")
                    cleaned_result[cleaned_key] = v
                else:
                    cleaned_result[k] = v

            return {
                "tier": str(cleaned_result.get("tier", "medium")).upper(),
                "confidence": cleaned_result.get("confidence", 0.8),
                "reasoning": cleaned_result.get("reasoning", "Classified by local model"),
                "needs_tools": cleaned_result.get("needs_tools", True),
            }
        except Exception:
            # If JSON parsing fails at any level, use fallback text search
            return self._fallback_parse(response)

    def _fallback_parse(self, response: str) -> dict[str, Any]:
        """Fallback parsing when JSON is not valid (case-insensitive)."""
        response_lower = response.lower()
        if "simple" in response_lower:
            tier = "SIMPLE"
        elif "coding" in response_lower or "code" in response_lower:
            tier = "CODING"
        elif "complex" in response_lower:
            tier = "COMPLEX"
        elif "reasoning" in response_lower or "proof" in response_lower:
            tier = "REASONING"
        else:
            tier = "MEDIUM"

        return {
            "tier": tier,
            "confidence": 0.6,
            "reasoning": "Parsed from non-JSON response",
            "needs_tools": tier != "SIMPLE",
        }

    def _estimate_tokens(self, content: str) -> int:
        """Rough token estimation."""
        return len(content.split()) * 4 // 3
