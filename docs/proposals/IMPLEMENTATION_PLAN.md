# Nanofolks Implementation Plan

## Executive Summary

This document outlines the complete implementation plan for Nanofolks, a multi-bot collaborative system. The plan has been restructured for clarity and coherence.

**Phase Structure:**
- Phase 1 ✅ COMPLETE: Multi-Bot Foundation
- Phase 2 ✅ COMPLETE: Intent Detection + IntentFlowRouter
- Phase 3 ✅ COMPLETE: Full Discovery Flow (Leader-first)
- Phase 4: Session Migration (deferred)

**Total Duration:** ~14 weeks

---

# Phase 1: Multi-Bot Foundation ✅ COMPLETE

## Overview

Phase 1 established the foundational multi-bot infrastructure, enabling bots to communicate and respond collectively without breaking existing functionality.

## Completed Components

### 1.1 Bot-to-Bot DM Rooms ✅
- **Location:** `.nanofolks/dm_rooms/`
- **Command:** `/peek dm-bot_a-bot_b`
- **Auto-created** on startup
- **Integrated** with `ask_bot()`

### 1.2 Multi-Bot Response Modes ✅
- `@all` - All bots respond simultaneously
- `@crew` - Relevant bots respond (keyword-based selection)
- **Parallel response generation** via `MultiBotResponseGenerator`
- **Formatted output** with bot emojis
- **Integrated** into agent loop

### 1.3 Affinity & Relationships ✅
- Parse IDENTITY.md relationships via `RelationshipParser`
- Infer relationships from themes (fallback)
- Affinity scores (0.0-1.0)
- Dynamic context injection via `AffinityContextBuilder`
- Cross-reference generation via `CrossReferenceInjector`
- Theme-aware interactions

## Files Created (Phase 1)

```
nanofolks/
├── models/
│   └── bot_dm_room.py              # Week 1
├── bots/
│   ├── dm_room_manager.py          # Week 1
│   ├── base.py                     # Week 1 (ask_bot logging)
│   └── dispatch.py                 # Week 2 (multi-bot modes)
├── agent/
│   ├── multi_bot_generator.py      # Week 2 (enhanced Week 3)
│   ├── affinity_context.py          # Week 3
│   ├── cross_reference.py           # Week 3
│   └── loop.py                     # Weeks 2 & 3
├── identity/
│   └── relationship_parser.py      # Week 3
└── cli/
    └── commands.py                 # Week 1 (peek command)
```

---

# Phase 2: Intent Detection + IntentFlow Router ✅ COMPLETE

## Duration: 3-4 weeks

## Problem Statement

Currently, all user messages are treated the same way. But different users need different interactions:

| User | Intent | Current Behavior | Desired Behavior |
|------|--------|------------------|------------------|
| Grandma (chat) | CHAT | Leader only | All bots join conversation |
| Teenager (research) | RESEARCH | One answer | 1-2 Qs → findings |
| Business owner | BUILD/TASK | Quick summary | Discovery → plan → execute |

## Solution: Hybrid Flow Router

Route user messages to the appropriate interaction model based on detected intent:

```
                    ┌─────────────────────────────────────┐
                    │      USER MESSAGE RECEIVED           │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │        INTENT DETECTION              │
                    │  BUILD | EXPLORE | ADVICE | RESEARCH | CHAT | TASK
                    └─────────────────┬───────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           │                          │                          │
           ▼                          ▼                          ▼
    ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
    │ SIMULTANEOUS│           │    QUICK   │           │    FULL     │
    │   (Phase 1) │           │  DISCOVERY │           │  DISCOVERY  │
    │             │           │             │           │             │
    │ @all style │           │ 1-2 Qs →   │           │ Questions → │
    │ Chat/bond  │           │ answer      │           │ Synthesis → │
    │             │           │             │           │ Approval →  │
    │             │           │             │           │ Execute     │
    └─────────────┘           └─────────────┘           └─────────────┘
```

## Intent Types

| Intent | Description | Flow | Example |
|--------|-------------|------|---------|
| **CHAT** | Conversational, companionship | Simultaneous | "That's interesting, tell me more" |
| **ADVICE** | Guidance on how to do something | Quick | "How do I organize weekly groceries?" |
| **RESEARCH** | Information gathering | Quick | "Fun ways to teach my son math?" |
| **EXPLORE** | Business/idea exploration | Light | "Can I make money from gardening + photography?" |
| **TASK** | Specific task completion | Full | "Write this email for me" |
| **BUILD** | Create something concrete | Full (Leader-first) | "Build me a website" |

## Flow Routing Logic

### Priority Order

```
1. Explicit @mentions (@all, @crew, @bot) → Always win
2. No mention + CHAT → Simultaneous (all bots in room respond)
3. No mention + ADVICE/RESEARCH → Quick flow (1-2 questions → answer)
4. No mention + BUILD/TASK/EXPLORE → Leader-first (Leader decides approach)
```

### Leader-First Logic

For BUILD, TASK, and EXPLORE intents, the system does NOT auto-route to discovery flow. Instead:

1. **Intent is detected** and stored as context for Leader
2. **Leader receives the message** with intent context attached
3. **Leader decides** how to handle:
   - Simple enough to handle directly? → Leader handles
   - Needs multiple specialists? → Leader creates project room and invites bots

This gives Leader autonomy to orchestrate complex tasks naturally.

### Examples

| Scenario | Behavior |
|----------|----------|
| "Build me a website" in #general (Leader only) | Intent = BUILD → Leader decides → Creates project room if needed |
| "Build me a website @all" | @all explicit → All respond simultaneously |
| "That's interesting!" in #general (Leader + Creative) | Intent = CHAT → Both respond |
| "How do I organize groceries?" | Intent = ADVICE → Quick flow |

### Room Philosophy

- **#general**: Default conversational room - Leader + any bots user adds
- **Project rooms**: Created on-demand for complex tasks
- **Leader**: Autonomous orchestrator that evaluates each request

### Leader-First Project Room Creation

When a BUILD/TASK/EXPLORE intent is detected in #general:

1. **Project room created** with just **Leader** (no other bots invited yet)
2. **Leader receives the request** with intent context
3. **Leader analyzes** the request and **decides which specialists to invite**:
   - "Build a website" → invites @researcher, @creative, @coder
   - "Build a recipe book" → invites @researcher, @creative (no coder)
   - "Create marketing campaign" → invites @creative, @social
4. **Discovery starts** with the team Leader assembled

This gives Leader autonomy to assemble the right team for each specific request, rather than hardcoding bot lists.

### Natural Onboarding Flow

```
User joins → Starts in #general → Talks to Leader
                                       ↓
                    "Build me a website"
                                       ↓
                    Leader creates #project-website
                    Leader invites specialists as needed
                                       ↓
                    Discovery begins in project room
```

Users don't need to know about rooms upfront - they just start chatting. Leader guides them naturally.

## Implementation

### 2.1 Intent Detector

```python
# nanofolks/agent/intent_detector.py

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any

class IntentType(Enum):
    BUILD = "build"
    EXPLORE = "explore"
    ADVICE = "advice"
    RESEARCH = "research"
    CHAT = "chat"
    TASK = "task"

@dataclass
class Intent:
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any]
    suggested_bots: List[str]
    flow_type: str  # "simultaneous", "quick", "full"

class IntentDetector:
    """Detect user intent and route to appropriate flow."""

    INTENT_PATTERNS = {
        IntentType.BUILD: ['build', 'create', 'make', 'develop', 'design'],
        IntentType.EXPLORE: ['can i', 'wonder if', 'ways to', 'make money', 'monetize'],
        IntentType.ADVICE: ['how do i', 'how can i', 'what is the best way', 'tips for'],
        IntentType.RESEARCH: ['research', 'what are', 'find out', 'tell me about'],
        IntentType.TASK: ['write', 'send', 'schedule', 'remind me', 'calculate'],
        IntentType.CHAT: ['what do you think', 'interesting', 'oh', 'wow', 'tell me more']
    }

    FLOW_MAPPING = {
        IntentType.CHAT: "simultaneous",
        IntentType.ADVICE: "quick",
        IntentType.RESEARCH: "quick",
        IntentType.EXPLORE: "full",  # Can escalate to build
        IntentType.TASK: "full",
        IntentType.BUILD: "full"
    }

    SUGGESTED_BOTS = {
        IntentType.BUILD: ["leader"],
        IntentType.EXPLORE: ["leader"],
        IntentType.ADVICE: ["leader"],
        IntentType.RESEARCH: ["leader"],
        IntentType.TASK: ["leader"],
        IntentType.CHAT: ["leader"],
    }

    def detect(self, message: str) -> Intent:
        """Detect intent from user message."""
        
        message_lower = message.lower()
        scores = {}

        for intent_type, patterns in self.INTENT_PATTERNS.items():
            score = sum(1 for p in patterns if p in message_lower)
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return Intent(
                intent_type=IntentType.CHAT,
                confidence=0.5,
                entities={},
                suggested_bots=self.SUGGESTED_BOTS[IntentType.CHAT],
                flow_type="simultaneous"
            )

        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent] / sum(scores.values())

        return Intent(
            intent_type=best_intent,
            confidence=confidence,
            entities={},
            suggested_bots=self.SUGGESTED_BOTS[best_intent],
            flow_type=self.FLOW_MAPPING[best_intent]
        )
```

### 2.2 Hybrid Flow Router

```python
# nanofolks/agent/hybrid_router.py

from nanofolks.agent.intent_detector import IntentDetector, Intent, IntentType
from nanofolks.agent.multi_bot_generator import MultiBotResponseGenerator
from nanofolks.agent.discovery_coordinator import DiscoveryCoordinator

class IntentFlowRouter:
    """Route messages to appropriate flow based on intent."""

    def __init__(self, agent_loop):
        self.agent = agent_loop
        self.intent_detector = IntentDetector()
        self.discovery_coordinator = None  # Initialized when needed

    async def route(self, msg: InboundMessage) -> OutboundMessage:
        """Route message to appropriate flow."""
        
        intent = self.intent_detector.detect(msg.content)
        
        if intent.flow_type == "simultaneous":
            return await self._handle_simultaneous(msg, intent)
        elif intent.flow_type == "quick":
            return await self._handle_quick(msg, intent)
        else:  # "full"
            return await self._handle_full(msg, intent)

    async def _handle_simultaneous(self, msg: InboundMessage, intent: Intent) -> OutboundMessage:
        """Handle CHAT intent - simultaneous multi-bot response."""
        # Uses existing Phase 1 multi-bot infrastructure
        return await self.agent._handle_multi_bot_response(
            msg, 
            bots=["leader", "researcher", "creative", "coder", "social", "auditor"],
            mode="simultaneous"
        )

    async def _handle_quick(self, msg: InboundMessage, intent: Intent) -> OutboundMessage:
        """Handle ADVICE/RESEARCH - quick 1-2 questions then answer."""
        
        # Check if we have pending questions (quick flow state)
        if self._has_pending_questions(msg.room_id):
            return await self._answer_quick(msg, intent)
        else:
            return await self._ask_quick_question(msg, intent)

    async def _handle_full(self, msg: InboundMessage, intent: Intent) -> OutboundMessage:
        """Handle BUILD/TASK/EXPLORE - full discovery flow."""
        
        # Initialize discovery coordinator
        self.discovery_coordinator = DiscoveryCoordinator(
            self.agent.workspace,
            msg.room_id
        )
        
        # Start discovery phase
        return await self.discovery_coordinator.start(msg.content, intent)

    def _has_pending_questions(self, room_id: str) -> bool:
        """Check if quick flow has pending questions."""
        # Check quick flow state
        return False  # Simplified
```

### 2.3 Agent Loop Integration

```python
# nanofolks/agent/loop.py - Modified

class AgentLoop:
    
    def __init__(self, /* ... */):
        # ... existing code ...
        self.hybrid_router = IntentFlowRouter(self)
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process message with hybrid flow routing."""
        
        # Check for cancellation
        if self._is_cancellation(msg.content):
            return await self._handle_cancellation(msg)
        
        # Check for project state continuation
        state_manager = ProjectStateManager(self.workspace, msg.room_id)
        
        if state_manager.state.phase != ProjectPhase.IDLE:
            # Continue existing flow
            return await self._continue_flow(msg, state_manager)
        
        # New message - use hybrid router
        return await self.hybrid_router.route(msg)
    
    def _is_cancellation(self, content: str) -> bool:
        """Check if user wants to cancel."""
        cancel_keywords = ['cancel', 'stop', 'never mind', 'forget it', 'abort']
        return any(kw in content.lower() for kw in cancel_keywords)
```

## Files Created (Phase 2)

```
nanofolks/agent/
├── intent_detector.py          # NEW - Intent detection
├── intent_flow_router.py       # NEW - Flow routing (includes discovery)
├── project_state.py            # NEW - State management
└── loop.py                   # MODIFIED - Integration
```

## Testing Checklist (Phase 2)

- [ ] Intent detector correctly identifies all 6 intent types
- [ ] CHAT → simultaneous flow (Phase 1 integration)
- [ ] ADVICE/RESEARCH → quick flow (1-2 Qs → answer)
- [ ] BUILD/TASK/EXPLORE → full discovery flow
- [ ] Cancellation keywords work in any phase
- [ ] Backward compatible with existing Phase 1 behavior

---

# Phase 3: Full Discovery Flow ✅ COMPLETE

## Duration: 3-4 weeks

## Overview

For BUILD, TASK, and EXPLORE intents, users go through a structured flow:

```
DISCOVERY → SYNTHESIS → APPROVAL → EXECUTION → REVIEW
```

This is inspired by GSD (Get Shit Done) framework's structured approach.

## Flow Details

### Discovery Phase
- **Who:** Multiple bots ask clarifying questions
- **How:** Wave-based (1 bot at a time)
- **Goal:** Understand user's need before building

### Synthesis Phase
- **Who:** Leader generates organized brief
- **Output:** Structured project brief (goal, scope, constraints, next steps)

### Approval Phase
- **Who:** User reviews and approves
- **Options:** "yes" to proceed, or feedback to iterate

### Execution Phase
- **Who:** Bots execute assigned tasks
- **Based:** On synthesis next_steps

### Review Phase
- **Who:** User confirms completion
- **Result:** Reset to IDLE

## Implementation

### 3.1 Project State Manager

```python
# nanofolks/agent/project_state.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

class ProjectPhase(Enum):
    IDLE = "idle"
    DISCOVERY = "discovery"
    SYNTHESIS = "synthesis"
    APPROVAL = "approval"
    EXECUTION = "execution"
    REVIEW = "review"

@dataclass
class ProjectState:
    phase: ProjectPhase = ProjectPhase.IDLE
    user_goal: str = ""
    intent_type: str = ""
    discovery_log: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    approval: Optional[Dict[str, Any]] = None
    execution_plan: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    iteration: int = 0

class ProjectStateManager:
    """Manages project state across sessions."""
    
    TIMEOUT_MINUTES = 30
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_dir = workspace / ".nanofolks" / "project_states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{room_id}.json"
        self._state: Optional[ProjectState] = None
    
    @property
    def state(self) -> ProjectState:
        if self._state is None:
            self._state = self._load_state()
        return self._state
    
    def _load_state(self) -> ProjectState:
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    data['created_at'] = datetime.fromisoformat(data['created_at'])
                    data['updated_at'] = datetime.fromisoformat(data['updated_at'])
                    data['phase'] = ProjectPhase(data['phase'])
                    return ProjectState(**data)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return ProjectState()
    
    def _save_state(self):
        data = {
            'phase': self.state.phase.value,
            'user_goal': self.state.user_goal,
            'intent_type': self.state.intent_type,
            'discovery_log': self.state.discovery_log,
            'synthesis': self.state.synthesis,
            'approval': self.state.approval,
            'execution_plan': self.state.execution_plan,
            'created_at': self.state.created_at.isoformat(),
            'updated_at': datetime.now().isoformat(),
            'iteration': self.state.iteration
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def start_discovery(self, user_goal: str, intent_type: str):
        """Begin discovery phase."""
        self.state.phase = ProjectPhase.DISCOVERY
        self.state.user_goal = user_goal
        self.state.intent_type = intent_type
        self.state.discovery_log = []
        self.state.iteration += 1
        self._save_state()
    
    def log_discovery_entry(self, bot_name: str, content: str, is_question: bool = True):
        """Log discovery question or answer."""
        self.state.discovery_log.append({
            'bot': bot_name,
            'content': content,
            'is_question': is_question,
            'timestamp': datetime.now().isoformat()
        })
        self._save_state()
    
    def complete_discovery(self):
        """Transition to synthesis."""
        self.state.phase = ProjectPhase.SYNTHESIS
        self._save_state()
    
    def set_synthesis(self, synthesis: Dict[str, Any]):
        """Set synthesis and move to approval."""
        self.state.synthesis = synthesis
        self.state.phase = ProjectPhase.APPROVAL
        self._save_state()
    
    def handle_approval(self, approved: bool, feedback: Optional[str] = None):
        """Handle user approval decision."""
        self.state.approval = {
            'approved': approved,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }
        
        if approved:
            self.state.phase = ProjectPhase.EXECUTION
        else:
            self.state.phase = ProjectPhase.DISCOVERY
        
        self._save_state()
    
    def start_execution(self, plan: Dict[str, Any]):
        """Begin execution."""
        self.state.execution_plan = plan
        self.state.phase = ProjectPhase.EXECUTION
        self._save_state()
    
    def complete_review(self):
        """Reset to idle."""
        self.state.phase = ProjectPhase.IDLE
        self._save_state()
    
    def check_timeout(self) -> bool:
        """Check if project timed out."""
        if self.state.phase == ProjectPhase.IDLE:
            return False
        
        elapsed = (datetime.now() - self.state.updated_at).total_seconds() / 60
        if elapsed > self.TIMEOUT_MINUTES:
            self.state.phase = ProjectPhase.IDLE
            self._save_state()
            return True
        return False
    
    def get_context(self, bot_name: str) -> str:
        """Get formatted context for a bot."""
        
        sections = [f"# Project Context", "", f"## Phase: {self.state.phase.value.upper()}"]
        
        if self.state.user_goal:
            sections.extend(["", f"## Goal", self.state.user_goal])
        
        if self.state.phase == ProjectPhase.DISCOVERY:
            sections.extend([
                "",
                "## Your Task",
                "Ask ONE clarifying question to understand the user's need.",
                "",
                "## Asked Questions"
            ])
            for entry in self.state.discovery_log:
                if entry['is_question']:
                    sections.append(f"- @{entry['bot']}: {entry['content']}")
        
        elif self.state.phase == ProjectPhase.EXECUTION:
            next_steps = self.state.synthesis.get('next_steps', {}) if self.state.synthesis else {}
            if bot_name in next_steps:
                sections.extend(["", f"## Your Task", next_steps[bot_name]])
        
        return "\n".join(sections)
```

### 3.2 Discovery Coordinator

```python
# nanofolks/agent/discovery_coordinator.py

class DiscoveryCoordinator:
    """Coordinates the full discovery flow."""
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_manager = ProjectStateManager(workspace, room_id)
    
    async def start(self, user_goal: str, intent: Intent) -> OutboundMessage:
        """Start new discovery flow."""
        
        self.state_manager.start_discovery(user_goal, intent.intent_type.value)
        
        # Select relevant bots
        bots = self._select_relevant_bots(user_goal, intent)
        
        # First bot asks question
        first_bot = bots[0]
        context = self.state_manager.get_context(first_bot)
        
        response = await self._generate_bot_response(first_bot, context, user_goal)
        
        self.state_manager.log_discovery_entry(first_bot, response, is_question=True)
        
        return OutboundMessage(content=response, metadata={'phase': 'discovery', 'bot': first_bot})
    
    async def continue_flow(self, user_response: str) -> OutboundMessage:
        """Continue discovery after user responds."""
        
        state = self.state_manager.state
        
        if state.phase == ProjectPhase.DISCOVERY:
            return await self._handle_discovery(user_response)
        elif state.phase == ProjectPhase.APPROVAL:
            return await self._handle_approval(user_response)
        elif state.phase == ProjectPhase.EXECUTION:
            return await self._handle_execution(user_response)
        elif state.phase == ProjectPhase.REVIEW:
            return await self._handle_review(user_response)
    
    async def _handle_discovery(self, user_response: str) -> OutboundMessage:
        """Handle discovery phase continuation."""
        
        # Log user's response
        self.state_manager.log_discovery_entry("user", user_response, is_question=False)
        
        # Check if discovery is complete
        if self._is_discovery_complete():
            # Move to synthesis
            synthesis = await self._generate_synthesis()
            self.state_manager.set_synthesis(synthesis)
            
            # Present to user for approval
            return OutboundMessage(
                content=self._format_synthesis(synthesis),
                metadata={'phase': 'approval'}
            )
        
        # Next bot asks question
        next_bot = self._get_next_bot()
        context = self.state_manager.get_context(next_bot)
        
        response = await self._generate_bot_response(next_bot, context, user_response)
        self.state_manager.log_discovery_entry(next_bot, response, is_question=True)
        
        return OutboundMessage(content=response, metadata={'phase': 'discovery', 'bot': next_bot})
    
    async def _handle_approval(self, user_response: str) -> OutboundMessage:
        """Handle approval response."""
        
        approved = self._check_approval(user_response)
        
        if approved:
            self.state_manager.handle_approval(approved=True)
            
            # Start execution
            return OutboundMessage(
                content=self._get_execution_context(),
                metadata={'phase': 'execution'}
            )
        else:
            # Back to discovery with feedback
            self.state_manager.handle_approval(approved=False, feedback=user_response)
            
            next_bot = self._get_next_bot()
            context = self.state_manager.get_context(next_bot)
            
            response = f"Noted! {self._get_next_question(next_bot, context)}"
            self.state_manager.log_discovery_entry(next_bot, response, is_question=True)
            
            return OutboundMessage(content=response, metadata={'phase': 'discovery'})
    
    async def _handle_execution(self, user_response: str) -> OutboundMessage:
        """Handle execution completion."""
        
        # Mark complete and move to review
        self.state_manager.state.phase = ProjectPhase.REVIEW
        self.state_manager._save_state()
        
        return OutboundMessage(
            content="All tasks complete! Ready for review. Let me know if anything needs changes.",
            metadata={'phase': 'review'}
        )
    
    async def _handle_review(self, user_response: str) -> OutboundMessage:
        """Handle final review."""
        
        self.state_manager.complete_review()
        
        return OutboundMessage(
            content="Great work! Let me know if you need anything else.",
            metadata={'phase': 'idle'}
        )
    
    def _select_relevant_bots(self, goal: str, intent: Intent) -> List[str]:
        """Select bots relevant to intent."""
        return intent.suggested_bots
    
    def _is_discovery_complete(self) -> bool:
        """Check if enough questions have been asked."""
        log = self.state_manager.state.discovery_log
        
        # At least 3 questions from at least 2 different bots
        questions = [e for e in log if e.get('is_question', True)]
        bots_with_questions = len(set(e['bot'] for e in questions))
        
        return len(questions) >= 3 and bots_with_questions >= 2
    
    def _get_next_bot(self) -> str:
        """Get next bot to ask question."""
        log = self.state_manager.state.discovery_log
        bots = self.state_manager.state.suggested_bots
        
        # Simple round-robin
        asked = set(e['bot'] for e in log if e.get('is_question', True))
        
        for bot in bots:
            if bot not in asked:
                return bot
        
        return bots[0]
    
    def _format_synthesis(self, synthesis: Dict) -> str:
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
                sections.append(f"- **{k}**: {v}")
        
        sections.extend(["", "---", "**Approve?** Reply 'yes' or describe changes."])
        
        return "\n".join(sections)
    
    def _check_approval(self, response: str) -> bool:
        """Check if user approved."""
        positive = ['yes', 'yep', 'sure', 'ok', 'okay', 'go ahead', 'looks good']
        return any(p in response.lower() for p in positive)
    
    def _get_execution_context(self) -> str:
        """Get execution instructions."""
        
        synthesis = self.state_manager.state.synthesis
        next_steps = synthesis.get('next_steps', {})
        
        sections = ["# 🚀 Execution Phase", ""]
        
        for bot, task in next_steps.items():
            if task:
                emoji = {'leader': '👑', 'researcher': '📊', 'coder': '💻', 
                        'creative': '🎨', 'social': '📱', 'auditor': '🔍'}.get(bot, '🤖')
                sections.append(f"{emoji} **@{bot}**: {task}")
        
        sections.extend(["", "Execute your tasks and report when complete."])
        
        return "\n".join(sections)
```

### 3.3 CLI Commands

```bash
# Project management
nanofolks project status     # Show current phase/state
nanofolks project reset      # Cancel and return to idle
nanofolks project log        # Show discovery log
nanofolks project brief      # Show current synthesis
```

## Files Created (Phase 3)

```
nanofolks/agent/
├── intent_flow_router.py       # Contains discovery flow logic
├── project_state.py            # State management
└── cli/commands.py            # project status/reset/log/brief commands
```

> Note: Discovery Coordinator logic is embedded directly in IntentFlowRouter for simplicity.

## Testing Checklist (Phase 3)

- [ ] Full flow: DISCOVERY → SYNTHESIS → APPROVAL → EXECUTION → REVIEW
- [ ] Approval triggers execution
- [ ] Rejection loops back to discovery
- [ ] Timeout auto-resets to idle
- [ ] Cancellation keywords work
- [ ] Project state persists across restarts

---

# Phase 4: Session Migration (Deferred)

## Overview

Migrate from `channel:chat_id` session keys to `room:{id}` keys.

## Why Defer

1. Phase 1-3 deliver full user value
2. Session migration is backend/storage focused
3. Risk increases with scope - better to validate user behavior first

## Future Implementation

See original `ROOM_CENTRIC_IMPLEMENTATION_PLAN.md` for:
- Dual-mode session manager
- Migration CLI tool
- Cross-channel synchronization

---

# Summary: User Experience by Intent

| User | Message | Intent | Flow | What Happens |
|------|---------|--------|------|--------------|
| Grandma | "Tell me about history!" | CHAT | Simultaneous | All bots join conversation |
| Teenager | "Fun math games for kids?" | RESEARCH | Quick | 1 Q → research → present |
| Business | "Build my website" | BUILD | Full | Discovery → Plan → Execute |
| Business | "Help with social media" | TASK | Full | Clarify → Execute |
| Any | "Can I make money from X?" | EXPLORE | Full | Discovery → Options |

---

# Appendix: Intent → Flow Decision Matrix

```
                    │ CHAT │ ADVICE │ RESEARCH │ EXPLORE │ TASK │ BUILD │
────────────────────┼──────┼────────┼──────────┼─────────┼──────┼───────│
Handler             │ Room │ Quick  │ Quick    │ Leader  │Leader│ Leader│
                    │Bots  │ Flow   │ Flow     │ First   │First │ First │
────────────────────┼──────┼────────┼──────────┼─────────┼──────┼───────│
All in Room         │  ✅  │        │          │         │      │       │
Quick (1-2 Qs)      │      │   ✅   │    ✅    │         │      │       │
Leader Orchestrates │      │        │          │    ✅    │  ✅  │   ✅   │
```

### Handler Legend
- **Room Bots**: All bots in the current room respond simultaneously
- **Quick Flow**: 1-2 clarifying questions → direct answer
- **Leader First**: Intent detected → Leader evaluates → decides room creation or direct handling

---

*Document Version: 2.2*  
*Last Updated: Leader-first project rooms + Leader decides bot invites*
