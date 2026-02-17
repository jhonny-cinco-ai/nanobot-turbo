"""Intent Flow Router - Routes messages to appropriate flow based on detected intent."""

from typing import Optional, List, Any, TYPE_CHECKING

from loguru import logger

from nanofolks.agent.intent_detector import IntentDetector, Intent, IntentType, FlowType

if TYPE_CHECKING:
    from nanofolks.bus.events import InboundMessage, OutboundMessage
    from nanofolks.session.manager import Session


class IntentFlowRouter:
    """Routes messages to appropriate flow based on detected intent.
    
    Flow Types:
    - SIMULTANEOUS: All bots respond at once (CHAT intent)
    - QUICK: 1-2 questions then answer (ADVICE/RESEARCH intent)
    - FULL: Discovery → Synthesis → Approval → Execution (BUILD/TASK/EXPLORE intent)
    """

    CANCEL_KEYWORDS = [
        'cancel', 'stop', 'never mind', 'forget it',
        'abort', 'quit', 'exit', 'never',
    ]

    def __init__(self, agent_loop: "AgentLoop"):
        """Initialize the router.
        
        Args:
            agent_loop: Reference to the main AgentLoop for delegating responses
        """
        self.agent = agent_loop
        self.intent_detector = IntentDetector()
        self._quick_flow_state: dict = {}

    async def route(self, msg: "InboundMessage", session: "Session") -> "OutboundMessage":
        """Route message to appropriate flow based on intent.
        
        Args:
            msg: Inbound message
            session: Current session
            
        Returns:
            OutboundMessage with appropriate response
        """
        intent = self.intent_detector.detect(msg.content)
        
        logger.info(
            f"Intent detected: {intent.intent_type.value} "
            f"(confidence: {intent.confidence:.2f}, flow: {intent.flow_type.value})"
        )

        if self._is_cancellation(msg.content):
            return await self._handle_cancellation(msg)

        if intent.flow_type == FlowType.SIMULTANEOUS:
            return await self._handle_simultaneous(msg, intent, session)
        elif intent.flow_type == FlowType.QUICK:
            return await self._handle_quick(msg, intent, session)
        else:  # FULL
            return await self._handle_full(msg, intent, session)

    def _is_cancellation(self, content: str) -> bool:
        """Check if user wants to cancel current flow."""
        content_lower = content.lower()
        return any(kw in content_lower for kw in self.CANCEL_KEYWORDS)

    async def _handle_cancellation(self, msg: "InboundMessage") -> "OutboundMessage":
        """Handle cancellation request."""
        logger.info("User requested cancellation")
        
        from nanofolks.bus.events import OutboundMessage
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="Okay, cancelled. Let me know if you need anything else.",
            metadata={'cancelled': True, 'phase': 'idle'}
        )

    async def _handle_simultaneous(
        self, 
        msg: "InboundMessage", 
        intent: Intent,
        session: "Session"
    ) -> "OutboundMessage":
        """Handle CHAT intent - simultaneous multi-bot response.
        
        Uses existing Phase 1 multi-bot infrastructure for communal experience.
        """
        from nanofolks.bots.dispatch import DispatchTarget
        
        bots = self.intent_detector.get_all_bots_for_intent(intent)
        
        logger.info(f"Simultaneous flow: all bots responding: {', '.join(bots)}")
        
        dispatch_result = {
            'is_multi_bot': True,
            'mode': DispatchTarget.MULTI_BOT,
            'bots': bots,
            'primary_bot': 'leader',
            'reason': f'CHAT intent - simultaneous response',
        }
        
        return await self.agent._handle_multi_bot_response(msg, dispatch_result, session)

    async def _handle_quick(
        self,
        msg: "InboundMessage",
        intent: Intent,
        session: "Session"
    ) -> "OutboundMessage":
        """Handle ADVICE/RESEARCH intents - quick 1-2 questions then answer.
        
        This flow asks 1-2 clarifying questions, then provides the answer.
        """
        room_id = msg.session_key
        
        if room_id not in self._quick_flow_state:
            self._quick_flow_state[room_id] = {
                'intent': intent,
                'questions_asked': 0,
                'user_goal': msg.content,
                'user_answers': [],
            }
        
        state = self._quick_flow_state[room_id]
        
        if state['questions_asked'] < 1:
            state['user_answers'].append(msg.content)
            question = await self._generate_quick_question_llm(intent, state)
            state['questions_asked'] += 1
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=question,
                metadata={
                    'phase': 'quick_discovery',
                    'questions_asked': state['questions_asked'],
                    'intent': intent.intent_type.value,
                }
            )
        else:
            state['user_answers'].append(msg.content)
            answer = await self._generate_quick_answer_llm(intent, state, msg.content)
            del self._quick_flow_state[room_id]
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=answer,
                metadata={
                    'phase': 'complete',
                    'intent': intent.intent_type.value,
                }
            )

    async def _handle_full(
        self,
        msg: "InboundMessage",
        intent: Intent,
        session: "Session"
    ) -> "OutboundMessage":
        """Handle BUILD/TASK/EXPLORE intents - full discovery flow.
        
        This starts the structured discovery → synthesis → approval → execution flow.
        Creates a new project room for BUILD/TASK/EXPLORE intents.
        
        Leader decides which bots to invite based on analyzing the request.
        """
        from nanofolks.agent.project_state import ProjectStateManager, ProjectPhase
        from nanofolks.bots.room_manager import get_room_manager
        
        room_id = msg.session_key
        is_new_project = False
        
        if room_id == "general" or not room_id:
            room_manager = get_room_manager()
            
            room_name = self._extract_project_name(msg.content, intent)
            
            new_room = room_manager.create_project_room(room_name, bots=["leader"])
            room_id = new_room.id
            
            is_new_project = True
            logger.info(f"Created project room '{room_id}' with Leader. Leader will invite specialists as needed.")
        
        state_manager = ProjectStateManager(self.agent.workspace, room_id)
        
        if state_manager.state.phase == ProjectPhase.IDLE:
            bots_in_room = ["leader"]
            
            state_manager.start_discovery(
                msg.content, 
                intent.intent_type.value,
                bots_in_room
            )
            
            first_bot = bots_in_room[0] if bots_in_room else "leader"
            question = await self._generate_discovery_question_llm(first_bot, state_manager, intent)
            
            state_manager.log_discovery_entry(first_bot, question, is_question=True)
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=question,
                metadata={
                    'phase': 'discovery',
                    'bot': first_bot,
                    'intent': intent.intent_type.value,
                    'room_id': room_id,
                    'is_new_project': is_new_project,
                }
            )
        
        return await self._continue_full_flow(msg, state_manager, session)
    
    def _extract_project_name(self, content: str, intent: Intent) -> str:
        """Extract a project name from the user's message.
        
        Args:
            content: User's message content
            intent: Detected intent
            
        Returns:
            A name suitable for a project room
        """
        content_lower = content.lower()
        
        words = content_lower.split()
        for i, word in enumerate(words):
            if word in ['build', 'create', 'make', 'develop'] and i + 1 < len(words):
                project_name = ' '.join(words[i+1:]).strip('.,!?')
                if project_name:
                    return project_name[:50]
        
        for i, word in enumerate(words):
            if word in ['project', 'for', 'to'] and i + 1 < len(words):
                project_name = ' '.join(words[i+1:]).strip('.,!?')
                if project_name:
                    return project_name[:50]
        
        return f"project-{intent.intent_type.value.lower()}"
    
    async def _leader_decides_bots(self, content: str, intent: Intent) -> List[str]:
        """Leader decides which bots to invite based on analyzing the request.
        
        This is a keyword-based heuristic. In production, this could use LLM
        to analyze the request and determine appropriate team composition.
        
        Args:
            content: User's request
            intent: Detected intent
            
        Returns:
            List of bot names to invite to the project
        """
        content_lower = content.lower()
        bots = ["leader"]
        
        has_research = any(w in content_lower for w in [
            'research', 'data', 'analyze', 'market', 'competitor', 'information',
            'learn about', 'find out', 'investigate', 'study'
        ])
        
        has_creative = any(w in content_lower for w in [
            'design', 'creative', 'visual', 'brand', 'logo', 'image', 'photo',
            'art', 'style', 'content', 'write', 'copy', 'marketing', 'campaign'
        ])
        
        has_coding = any(w in content_lower for w in [
            'build', 'code', 'develop', 'website', 'app', 'api', 'software',
            'program', 'technical', 'database', 'functionality', 'feature'
        ])
        
        has_social = any(w in content_lower for w in [
            'social media', 'twitter', 'facebook', 'instagram', 'linkedin',
            'marketing', 'audience', 'community', 'engagement', 'followers'
        ])
        
        has_auditing = any(w in content_lower for w in [
            'review', 'audit', 'check', 'verify', 'validate', 'quality',
            'test', 'security', 'compliance', 'risk'
        ])
        
        if intent.intent_type.value in ['build', 'task', 'explore']:
            has_coding = True
            has_creative = True
        
        if intent.intent_type.value == 'build':
            has_research = True
        
        if has_research and "researcher" not in bots:
            bots.append("researcher")
        if has_creative and "creative" not in bots:
            bots.append("creative")
        if has_coding and "coder" not in bots:
            bots.append("coder")
        if has_social and "social" not in bots:
            bots.append("social")
        if has_auditing and "auditor" not in bots:
            bots.append("auditor")
        
        logger.info(f"Leader decided to invite: {bots} for request: {content[:50]}...")
        return bots

    async def _continue_full_flow(
        self,
        msg: "InboundMessage",
        state_manager: "ProjectStateManager",
        session: "Session"
    ) -> "OutboundMessage":
        """Continue an existing full discovery flow."""
        from nanofolks.agent.project_state import ProjectPhase
        
        state = state_manager.state
        
        if state.phase == ProjectPhase.DISCOVERY:
            return await self._continue_discovery(msg, state_manager)
        elif state.phase == ProjectPhase.APPROVAL:
            return await self._handle_approval(msg, state_manager)
        elif state.phase == ProjectPhase.EXECUTION:
            return await self._handle_execution(msg, state_manager)
        elif state.phase == ProjectPhase.REVIEW:
            return await self._handle_review(msg, state_manager)
        
        from nanofolks.bus.events import OutboundMessage
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="I'm not sure what to do next. Let's start fresh!",
            metadata={'phase': 'idle'}
        )

    async def _continue_discovery(
        self,
        msg: "InboundMessage",
        state_manager: "ProjectStateManager"
    ) -> "OutboundMessage":
        """Continue discovery phase."""
        from nanofolks.agent.project_state import ProjectPhase
        
        state_manager.log_discovery_entry("user", msg.content, is_question=False)
        
        if state_manager._is_discovery_complete():
            state_manager.complete_discovery()
            
            synthesis = await self._generate_synthesis_llm(state_manager)
            state_manager.set_synthesis(synthesis)
            
            formatted = self._format_synthesis(synthesis)
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=formatted,
                metadata={'phase': 'approval'}
            )
        
        next_bot = state_manager._get_next_bot()
        question = await self._generate_discovery_question_llm(next_bot, state_manager, None)
        state_manager.log_discovery_entry(next_bot, question, is_question=True)
        
        from nanofolks.bus.events import OutboundMessage
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=question,
            metadata={'phase': 'discovery', 'bot': next_bot}
        )

    async def _handle_approval(
        self,
        msg: "InboundMessage",
        state_manager: "ProjectStateManager"
    ) -> "OutboundMessage":
        """Handle approval response."""
        approved = self._check_approval(msg.content)
        
        if approved:
            state_manager.handle_approval(approved=True)
            
            execution_content = self._get_execution_context(state_manager)
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=execution_content,
                metadata={'phase': 'execution'}
            )
        else:
            state_manager.handle_approval(approved=False, feedback=msg.content)
            
            next_bot = state_manager._get_next_bot()
            question = f"Noted! {await self._generate_discovery_question_llm(next_bot, state_manager, None)}"
            state_manager.log_discovery_entry(next_bot, question, is_question=True)
            
            from nanofolks.bus.events import OutboundMessage
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=question,
                metadata={'phase': 'discovery'}
            )

    async def _handle_execution(
        self,
        msg: "InboundMessage",
        state_manager: "ProjectStateManager"
    ) -> "OutboundMessage":
        """Handle execution phase."""
        from nanofolks.agent.project_state import ProjectPhase
        state_manager.state.phase = ProjectPhase.REVIEW
        state_manager._save_state()
        
        from nanofolks.bus.events import OutboundMessage
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="All tasks complete! Ready for review. Let me know if anything needs changes.",
            metadata={'phase': 'review'}
        )

    async def _handle_review(
        self,
        msg: "InboundMessage",
        state_manager: "ProjectStateManager"
    ) -> "OutboundMessage":
        """Handle final review."""
        state_manager.complete_review()
        
        from nanofolks.bus.events import OutboundMessage
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="Great work! Let me know if you need anything else.",
            metadata={'phase': 'idle'}
        )

    async def _generate_quick_question_llm(self, intent: Intent, state: dict) -> str:
        """Generate a quick clarifying question using LLM."""
        prompt = f"""You are a helpful assistant. The user wants to {intent.intent_type.value.lower()}.

User's original request: {state['user_goal']}

Ask ONE brief clarifying question to better understand their needs. Be specific and helpful.

Question:"""

        try:
            response = await self.agent.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.agent.model,
                temperature=0.7,
                max_tokens=150,
            )
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM question generation failed: {e}")
            return self._fallback_quick_question(intent)

    def _fallback_quick_question(self, intent: Intent) -> str:
        """Fallback questions if LLM fails."""
        if intent.intent_type == IntentType.ADVICE:
            return "Just to clarify, what's your main constraint? (budget, time, or something else?)"
        elif intent.intent_type == IntentType.RESEARCH:
            return "What's the most important factor for you? (simplicity, effectiveness, cost?)"
        return "Can you tell me a bit more about what you're looking for?"

    async def _generate_quick_answer_llm(
        self, 
        intent: Intent, 
        state: dict, 
        user_context: str
    ) -> str:
        """Generate a quick answer after clarification using LLM."""
        answers = "\n".join(f"- {a}" for a in state['user_answers'])
        
        prompt = f"""You are a helpful assistant. The user wants to {intent.intent_type.value.lower()}.

Original request: {state['user_goal']}

Their answers to your questions:
{answers}

Provide a helpful, concise answer to their request. Be specific and actionable."""

        try:
            response = await self.agent.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.agent.model,
                temperature=0.7,
                max_tokens=500,
            )
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM answer generation failed: {e}")
            return f"Based on what you've shared, here's my advice regarding: {state['user_goal']}"

    async def _generate_discovery_question_llm(
        self,
        bot_name: str,
        state_manager: "ProjectStateManager",
        intent: Optional[Intent]
    ) -> str:
        """Generate a discovery phase question using LLM."""
        state = state_manager.state
        
        prompt = f"""You are @{bot_name}, a specialist in this team.

The user wants to: {state.user_goal}

Intent type: {state.intent_type}

Questions already asked:
"""
        for entry in state.discovery_log:
            prefix = "❓" if entry.get('is_question', True) else "💬"
            prompt += f"- @{entry['bot']}: {entry['content']}\n"

        prompt += f"""
Ask ONE clarifying question that @ {bot_name} needs answered to do their job effectively.
Be specific to your domain expertise.
Keep it brief (1-2 sentences)."""

        try:
            response = await self.agent.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.agent.model,
                temperature=0.7,
                max_tokens=150,
            )
            return response.content.strip()
        except Exception as e:
            logger.warning(f"LLM discovery question failed: {e}")
            return self._fallback_discovery_question(bot_name)

    def _fallback_discovery_question(self, bot_name: str) -> str:
        """Fallback discovery questions if LLM fails."""
        questions_by_bot = {
            "leader": "To get started, what's your ultimate goal for this?",
            "researcher": "What information or data would help inform our approach?",
            "creative": "What style or visual direction do you have in mind?",
            "coder": "Are there specific technical requirements or constraints?",
            "social": "Who is your target audience for this?",
            "auditor": "What quality standards or requirements should we meet?",
        }
        return questions_by_bot.get(bot_name, "Can you tell me more about what you need?")

    async def _generate_synthesis_llm(self, state_manager: "ProjectStateManager") -> dict:
        """Generate synthesis from discovery log using LLM."""
        state = state_manager.state
        
        prompt = f"""You are the Team Leader. Synthesize the discovery conversation into a project brief.

User's Original Goal: {state.user_goal}

Discovery Conversation:
"""
        for entry in state.discovery_log:
            prefix = "❓" if entry.get('is_question', True) else "💬"
            prompt += f"- @{entry['bot']}: {entry['content']}\n"

        prompt += """
Create a structured project brief in JSON format:

```json
{{
  "title": "Project name",
  "goal": "One sentence on what to build",
  "scope": {{
    "included": ["list of features"],
    "excluded": ["explicitly out of scope"]
  }},
  "constraints": {{
    "budget": "budget if mentioned",
    "timeline": "timeline if mentioned",
    "platform": "platform/tech if mentioned"
  }},
  "next_steps": {{
    "leader": "coordination task",
    "researcher": "research task", 
    "creative": "design task",
    "coder": "implementation task",
    "social": "outreach task",
    "auditor": "review task"
  }}
}}
```

Generate ONLY the JSON, no other text."""

        try:
            response = await self.agent.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.agent.model,
                temperature=0.5,
                max_tokens=800,
            )
            import json
            content = response.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            return json.loads(content.strip())
        except Exception as e:
            logger.warning(f"LLM synthesis generation failed: {e}")
            return self._fallback_synthesis(state_manager)

    def _fallback_synthesis(self, state_manager) -> dict:
        """Fallback synthesis if LLM fails."""
        return {
            "title": "Project Brief",
            "goal": state_manager.state.user_goal,
            "scope": {"included": ["Feature 1", "Feature 2"]},
            "constraints": {},
            "next_steps": {
                "leader": "Coordinate the team",
                "researcher": "Research market",
                "creative": "Design mockups",
                "coder": "Implement features",
            }
        }

    def _format_synthesis(self, synthesis: dict) -> str:
        """Format synthesis for user display."""
        sections = ["# 📋 Project Brief", "", f"## Goal: {synthesis.get('goal', 'TBD')}"]
        
        scope = synthesis.get('scope', {})
        if scope.get('included'):
            sections.extend(["", "## In Scope"])
            for item in scope['included']:
                sections.append(f"- {item}")
        
        constraints = synthesis.get('constraints', {})
        if constraints:
            sections.extend(["", "## Constraints"])
            for k, v in constraints.items():
                if v:
                    sections.append(f"- **{k}**: {v}")
        
        sections.extend(["", "---", "**Approve?** Reply 'yes' or describe changes."])
        return "\n".join(sections)

    def _check_approval(self, response: str) -> bool:
        """Check if user approved."""
        positive = ['yes', 'yep', 'sure', 'ok', 'okay', 'go ahead', 'looks good', 'approved']
        return any(p in response.lower() for p in positive)

    def _get_execution_context(self, state_manager: "ProjectStateManager") -> str:
        """Get execution instructions."""
        synthesis = state_manager.state.synthesis
        next_steps = synthesis.get('next_steps', {})
        
        sections = ["# 🚀 Execution Phase", ""]
        
        for bot, task in next_steps.items():
            if task:
                emoji = {'leader': '👑', 'researcher': '📊', 'coder': '💻', 
                        'creative': '🎨', 'social': '📱', 'auditor': '🔍'}.get(bot, '🤖')
                sections.append(f"{emoji} **@{bot}**: {task}")
        
        sections.extend(["", "Execute your tasks and report when complete."])
        return "\n".join(sections)


def get_intent_flow_router(agent_loop: "AgentLoop") -> IntentFlowRouter:
    """Get IntentFlowRouter instance."""
    return IntentFlowRouter(agent_loop)
