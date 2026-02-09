"""Context pipeline stage for model routing."""

from pathlib import Path
from typing import Any, Optional

from nanobot.config.schema import RoutingConfig
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session

from ..router.calibration import CalibrationManager
from ..router.classifier import ClientSideClassifier
from ..router.llm_router import LLMRouter
from ..router.models import RoutingDecision
from ..router.sticky import StickyRouter


class RoutingContext:
    """Context object for routing decisions."""
    
    def __init__(
        self,
        message: Any,
        session: Session,
        default_model: str,
        config: RoutingConfig,
    ):
        self.message = message
        self.session = session
        self.model = default_model
        self.config = config
        self.decision: Optional[RoutingDecision] = None
        self.metadata: dict[str, Any] = {}
    
    def apply_decision(self, decision: RoutingDecision) -> None:
        """Apply routing decision to context."""
        self.decision = decision
        
        # Map tier to model
        tier_config = getattr(self.config.tiers, decision.tier.value, None)
        if tier_config:
            self.model = tier_config.model
        
        self.metadata["routing_tier"] = decision.tier.value
        self.metadata["routing_confidence"] = decision.confidence
        self.metadata["routing_layer"] = decision.layer


class RoutingStage:
    """
    Pipeline stage for intelligent model routing.
    
    Implements two-layer classification with sticky routing:
    1. Client-side pattern matching (fast)
    2. LLM-assisted classification (fallback)
    """
    
    def __init__(
        self,
        config: RoutingConfig,
        provider: Optional[LLMProvider] = None,
        workspace: Optional[Path] = None,
    ):
        self.config = config
        self.provider = provider
        self.workspace = workspace
        
        # Initialize components
        self._init_classifier()
        self._init_calibration()
    
    def _init_classifier(self) -> None:
        """Initialize the classification components."""
        # Client-side classifier
        patterns_file = None
        if self.workspace:
            patterns_file = self.workspace / "memory" / "ROUTING_PATTERNS.json"
        
        self.client_classifier = ClientSideClassifier(
            patterns_file=patterns_file,
            min_confidence=self.config.client_classifier.min_confidence,
        )
        
        # LLM router (if provider available)
        self.llm_router: Optional[LLMRouter] = None
        if self.provider:
            self.llm_router = LLMRouter(
                provider=self.provider,
                model=self.config.llm_classifier.model,
                timeout_ms=self.config.llm_classifier.timeout_ms,
            )
        
        # Sticky router (combines both layers)
        self.sticky_router = StickyRouter(
            client_classifier=self.client_classifier,
            llm_router=self.llm_router,
            context_window=self.config.sticky.context_window,
            downgrade_confidence=self.config.sticky.downgrade_confidence,
        )
    
    def _init_calibration(self) -> None:
        """Initialize calibration manager."""
        if self.workspace and self.config.auto_calibration.enabled:
            patterns_file = self.workspace / "memory" / "ROUTING_PATTERNS.json"
            analytics_file = self.workspace / "analytics" / "routing_stats.json"
            
            self.calibration = CalibrationManager(
                patterns_file=patterns_file,
                analytics_file=analytics_file,
                config=self.config.auto_calibration.model_dump(),
            )
        else:
            self.calibration = None
    
    async def execute(self, ctx: RoutingContext) -> RoutingContext:
        """
        Execute routing stage.
        
        Args:
            ctx: Routing context with message and session
        
        Returns:
            Modified context with selected model
        """
        # Run classification with sticky routing
        decision = await self.sticky_router.classify(
            content=ctx.message.content,
            session=ctx.session,
        )
        
        # Apply decision to context
        ctx.apply_decision(decision)
        
        # Record for calibration (fire-and-forget)
        if self.calibration:
            self._record_for_calibration(ctx, decision)
        
        # Check if calibration needed
        if self.calibration and self.calibration.should_calibrate():
            self._run_calibration()
        
        return ctx
    
    def _record_for_calibration(
        self,
        ctx: RoutingContext,
        decision: RoutingDecision,
    ) -> None:
        """Record classification for future calibration."""
        import asyncio
        
        record = {
            "content_preview": ctx.message.content[:200],
            "final_tier": decision.tier.value,
            "final_confidence": decision.confidence,
            "layer": decision.layer,
        }
        
        # Add comparison data if available
        if "feedback_comparison" in decision.metadata:
            comparison = decision.metadata["feedback_comparison"]
            record.update({
                "client_tier": comparison.get("client_tier"),
                "client_confidence": comparison.get("client_confidence"),
                "llm_tier": comparison.get("llm_tier"),
                "llm_confidence": comparison.get("llm_confidence"),
                "match": comparison.get("match"),
            })
        
        # Fire-and-forget recording
        asyncio.create_task(self._async_record(record))
    
    async def _async_record(self, record: dict) -> None:
        """Async recording to avoid blocking."""
        if self.calibration:
            self.calibration.record_classification(record)
    
    def _run_calibration(self) -> None:
        """Run calibration (fire-and-forget)."""
        import asyncio
        
        async def calibrate_async():
            if self.calibration:
                results = self.calibration.calibrate()
                # Log results
                print(f"Calibration completed: {results}")
        
        asyncio.create_task(calibrate_async())
    
    def get_routing_info(self) -> dict[str, Any]:
        """Get current routing configuration and stats."""
        info = {
            "tiers": {
                tier: {
                    "model": getattr(self.config.tiers, tier).model,
                    "cost_per_mtok": getattr(self.config.tiers, tier).cost_per_mtok,
                }
                for tier in ["simple", "medium", "complex", "reasoning"]
            },
            "client_confidence_threshold": self.config.client_classifier.min_confidence,
            "llm_classifier": {
                "model": self.config.llm_classifier.model,
                "timeout_ms": self.config.llm_classifier.timeout_ms,
            },
            "sticky": {
                "context_window": self.config.sticky.context_window,
                "downgrade_confidence": self.config.sticky.downgrade_confidence,
            },
        }
        
        if self.calibration:
            info["calibration"] = {
                "enabled": self.config.auto_calibration.enabled,
                "interval": self.config.auto_calibration.interval,
                "last_run": self.calibration._last_calibration.isoformat() if self.calibration._last_calibration else None,
                "total_classifications": len(self.calibration._classifications),
            }
        
        return info
