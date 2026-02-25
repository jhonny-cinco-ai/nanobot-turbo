"""Unified orchestrator pipeline for message handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from loguru import logger

from nanofolks.systems.tag_handler import TagHandler
from nanofolks.utils.ids import session_to_room_id

if TYPE_CHECKING:
    from nanofolks.bus.events import MessageEnvelope
    from nanofolks.session.manager import Session
    from nanofolks.agent.loop import AgentLoop


class OrchestratorPipeline:
    """Single entrypoint for tag -> intent -> dispatch -> collect -> final."""

    def __init__(self, agent_loop: "AgentLoop") -> None:
        self.agent = agent_loop
        self.tag_handler = TagHandler()

    async def handle(self, msg: "MessageEnvelope", session: "Session") -> Optional["MessageEnvelope"]:
        """Run the orchestrator pipeline.

        Returns:
            MessageEnvelope if handled, else None (caller continues normal flow).
        """
        self._apply_tags(msg)

        # Dispatch: multi-bot triggers (explicit mentions, @all/@crew)
        dispatch_result = self.agent._check_multi_bot_dispatch(msg.content, session)
        if dispatch_result and dispatch_result.get("is_multi_bot"):
            msg.metadata.setdefault("dispatch", {})
            msg.metadata["dispatch"].update(
                {
                    "mode": dispatch_result.get("mode").value
                    if dispatch_result.get("mode")
                    else None,
                    "bots": dispatch_result.get("bots", []),
                    "reason": dispatch_result.get("reason"),
                }
            )
            return await self.agent._handle_multi_bot_response(msg, dispatch_result, session)

        # Intent flow routing (hybrid quick/full flows)
        if self.agent._hybrid_router_enabled:
            response = await self._handle_intent_flows(msg, session)
            if response is not None:
                return response

        # Default leader-first path
        msg.metadata.setdefault("dispatch", {})
        msg.metadata["dispatch"].setdefault("mode", "leader_first")
        return None

    def _apply_tags(self, msg: "MessageEnvelope") -> None:
        parsed = self.tag_handler.parse_tags(msg.content)
        msg.metadata.setdefault("tags", {})
        msg.metadata["tags"].update(
            {
                "bots": parsed.bots,
                "actions": parsed.actions,
            }
        )
        logger.debug(f"Tags parsed: bots={parsed.bots}, actions={parsed.actions}")

    async def _handle_intent_flows(
        self, msg: "MessageEnvelope", session: "Session"
    ) -> Optional["MessageEnvelope"]:
        from nanofolks.agent.project_state import ProjectStateManager
        from nanofolks.agent.intent_detector import FlowType
        from nanofolks.agent.intent_flow_router import IntentFlowRouter

        room_id = msg.room_id or session_to_room_id(msg.session_key) or "general"
        state_manager = ProjectStateManager(self.agent.workspace, room_id)

        # Check for timeout
        state_manager.check_timeout()

        if self.agent.hybrid_router is None:
            self.agent.hybrid_router = IntentFlowRouter(self.agent)

        intent = await self.agent.hybrid_router.detect_intent(msg.content)
        msg.metadata.setdefault("intent", {})
        msg.metadata["intent"].update(
            {
                "type": intent.intent_type.value,
                "confidence": intent.confidence,
                "flow": intent.flow_type.value,
            }
        )

        orchestrated = await self.agent.hybrid_router.route_state_machine(
            msg=msg,
            session=session,
            state_manager=state_manager,
            intent=intent,
            allow_full_start=False,
            allow_simultaneous=False,
        )
        if orchestrated is not None:
            return orchestrated

        if intent.flow_type == FlowType.FULL:
            # Store intent info for Leader to access
            session.metadata["_detected_intent"] = {
                "type": intent.intent_type.value,
                "confidence": intent.confidence,
                "suggested_bots": intent.suggested_bots,
            }

            intent_context = (
                f"\n[System: This request appears to be a {intent.intent_type.value} task. "
                f"Suggested team: {', '.join(intent.suggested_bots)}]\n"
            )
            session.messages.append({"role": "system", "content": intent_context})
            self.agent.sessions.save(session)
            logger.info(
                f"Intent detected: {intent.intent_type.value}, "
                "passing to Leader (Leader will decide if room needed)"
            )
            return None

        # SIMULTANEOUS / CHAT: fall through to normal flow (leader-first)
        return None
