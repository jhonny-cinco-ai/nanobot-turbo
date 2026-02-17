# Phase 1.5: Communal Discovery Flow

## Executive Summary

Phase 1.5 introduces a **Discovery Phase** between the current Phase 1 (Multi-Bot Foundation) and Phase 2 (Session Migration). This phase addresses a key UX issue: the current model where Leader privately coordinates and returns summaries feels like "one assistant" rather than a true crew.

**Inspiration:** GSD (Get Shit Done) framework's `discuss → plan → execute → verify` cycle

**New Flow:**
```
INTENT DETECTION → ROUTE TO FLOW → EXECUTE → DONE
                    │
                    ├── CHAT (direct response)
                    ├── QUICK (1-2 Qs → answer)
                    ├── LIGHT (discovery → options)
                    └── FULL  (discovery → synthesis → approval → execute)
```

**Duration:** 3-4 weeks  
**Risk Level:** Low (additive feature, no breaking changes)

---

## Streamlined Architecture

### Unified State Machine (All Intents)

```
                    ┌─────────────────────────────────────────────┐
                    │           USER MESSAGE RECEIVED              │
                    └─────────────────────┬───────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │         INTENT DETECTION (new)              │
                    │   BUILD | EXPLORE | ADVICE | RESEARCH | TASK | CHAT │
                    └─────────────────────┬───────────────────────┘
                                          │
                    ┌─────────────────────┴───────────────────────┐
                    │              ROUTE TO FLOW                    │
                    └─────────────────────┬───────────────────────┘
                                          │
         ┌──────────────┬───────────────┬──┴────┬──────────────┬──────────────┐
         │              │               │       │              │              │
         ▼              ▼               ▼       ▼              ▼              ▼
    ┌─────────┐   ┌─────────┐    ┌─────────┐ ┌─────────┐  ┌─────────┐  ┌─────────┐
    │  CHAT   │   │  QUICK  │    │  LIGHT  │ │  FULL   │  │  TASK   │  │ (reuse) │
    │  flow   │   │  flow   │    │  flow   │ │  flow   │  │  flow   │  │         │
    └────┬────┘   └────┬────┘    └────┬────┘ └────┬────┘  └────┬────┘  └────┬────┘
         │              │               │       │              │              │
         └──────────────┴───────────────┴───────┴──────────────┴──────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────┐
                    │              BACK TO IDLE                    │
                    └─────────────────────────────────────────────┘
```

### Flow Types by Intent

| Intent | Flow | Phases | Description |
|--------|------|--------|-------------|
| **CHAT** | direct | - | Conversational, no structured flow |
| **ADVICE** | quick | Q → A | 1 clarifying question, then direct answer |
| **RESEARCH** | quick | Q → research → present | 1-2 questions, then present findings |
| **EXPLORE** | light | discovery → options | 2-3 questions, present 3-5 options |
| **TASK** | light | clarify → execute | Clarify, then execute specific task |
| **BUILD** | full | D→S→A→E→R | Full discovery → synthesis → approval → execution → review |

---

## Problem Statement

### Current Model (Phase 1)
```
User: "I want to build a website"
    ↓
Leader receives message
    ↓
Leader DMs Researcher: "Research this" (private)
Leader DMs Creative: "Design this" (private)
    ↓
Leader returns summary to user
    ↓
User sees: "Here's what we'll do..." (one voice)
```

### Desired Model (Phase 1.5)
```
User: "I want to build a website"
    ↓
DISCOVERY: All relevant bots ask clarifying questions IN THE ROOM
    ↓
SYNTHESIS: Leader collects all inputs, generates organized format
    ↓
APPROVAL: User reviews and approves the plan
    ↓
EXECUTION: Leader coordinates delegation
    ↓
REVIEW: User sees results
```

---

## Intent Detection Layer

The discovery flow should NOT apply to every user message. We need to detect intent first:

### Intent Types

| Intent | Description | Flow | Example |
|--------|-------------|------|---------|
| **BUILD** | User wants to create something concrete | Full discovery → synthesis → approval → execution | "Build me a website" |
| **EXPLORE** | User has interests/passion, wants business ideas | Light discovery → research → present options | "Can I make money from gardening + photography?" |
| **ADVICE** | User wants guidance on how to do something | Quick clarification → direct answer | "How do I organize weekly groceries?" |
| **RESEARCH** | User wants information on a topic | Minimal clarification → research → present findings | "Fun ways to teach my son math?" |
| **CHAT** | User just wants to converse | Direct conversational response | "That's interesting, tell me more" |
| **TASK** | User has a specific task needing completion | Light discovery → execute → review | "Write this email for me" |

### Your Examples Analyzed

```
1. "I love gardening and photography, I wonder if there is a way to make money off it?"
   → EXPLORE intent
   → Flow: Light discovery (what's your time/location/budget?) → Research options → Present 3-5 business ideas

2. "How can i organize my weekly food groceries?"
   → ADVICE intent  
   → Flow: Quick tip (categorize, batch, routine) → maybe 1 clarifying question → Direct advice

3. "Is there a way to teach my son math in a fun way?"
   → RESEARCH intent
   → Flow: What's his age? → Research gamification methods → Present options

4. "I want to build a website"
   → BUILD intent (original design)
   → Flow: Full discovery → synthesis → approval → execution
```

### Implementation

```python
# nanofolks/agent/intent_detector.py

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

class IntentType(Enum):
    BUILD = "build"           # Create something
    EXPLORE = "explore"       # Business/idea exploration
    ADVICE = "advice"         # Guidance request
    RESEARCH = "research"    # Information gathering
    CHAT = "chat"            # Conversational
    TASK = "task"            # Specific task completion

@dataclass
class Intent:
    intent_type: IntentType
    confidence: float
    entities: Dict[str, Any]  # Extracted entities
    suggested_bots: List[str] # Which bots should respond
    discovery_depth: str      # "full", "light", "minimal", "none"

class IntentDetector:
    """Detect user intent from message."""
    
    # Keywords that indicate intent type
    INTENT_PATTERNS = {
        IntentType.BUILD: [
            'build', 'create', 'make', 'develop', 'design',
            'build a', 'create a', 'make a', 'develop a'
        ],
        IntentType.EXPLORE: [
            'can i', 'could i', 'wonder if', 'ways to',
            'how to make money', 'business', 'start a',
            'is there a way', ' monetize', 'profit from'
        ],
        IntentType.ADVICE: [
            'how do i', 'how can i', 'what is the best way',
            'how should i', 'tips for', 'advice on',
            'help me', 'suggestions for'
        ],
        IntentType.RESEARCH: [
            'research', 'what are', 'find out', 'information',
            'tell me about', 'learn about', 'what is'
        ],
        IntentType.TASK: [
            'write', 'send', 'schedule', 'remind me',
            'calculate', 'convert', 'translate', 'summarize'
        ],
        IntentType.CHAT: [
            'what do you think', 'interesting', 'oh', 'wow',
            'tell me more', 'really?', 'nice', 'cool'
        ]
    }
    
    # How much discovery each intent needs
    DISCOVERY_DEPTH = {
        IntentType.BUILD: "full",       # Build → Synthesize → Approve → Execute
        IntentType.EXPLORE: "light",     # Quick Q → Research → Present options
        IntentType.ADVICE: "minimal",    # 1 Q max → Direct answer
        IntentType.RESEARCH: "minimal",  # 1-2 Q → Research → Present
        IntentType.TASK: "light",        # Clarify → Execute
        IntentType.CHAT: "none"          # Direct response
    }
    
    # Which bots respond to each intent
    SUGGESTED_BOTS = {
        IntentType.BUILD: ["leader", "researcher", "creative", "coder"],
        IntentType.EXPLORE: ["leader", "researcher", "creative"],
        IntentType.ADVICE: ["leader", "researcher"],
        IntentType.RESEARCH: ["researcher"],
        IntentType.TASK: ["leader", "coder"],
        IntentType.CHAT: ["leader"]
    }
    
    def detect(self, message: str) -> Intent:
        """Detect intent from user message."""
        
        message_lower = message.lower()
        scores = {}
        
        # Score each intent type
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if pattern in message_lower:
                    score += 1
                    # Bonus for exact phrase match
                    if pattern in message:
                        score += 0.5
            
            if score > 0:
                scores[intent_type] = score
        
        if not scores:
            # Default to CHAT if no match
            return Intent(
                intent_type=IntentType.CHAT,
                confidence=0.5,
                entities={},
                suggested_bots=self.SUGGESTED_BOTS[IntentType.CHAT],
                discovery_depth="none"
            )
        
        # Get highest scoring intent
        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent] / sum(scores.values())
        
        # Extract entities
        entities = self._extract_entities(message, best_intent)
        
        return Intent(
            intent_type=best_intent,
            confidence=confidence,
            entities=entities,
            suggested_bots=self.SUGGESTED_BOTS[best_intent],
            discovery_depth=self.DISCOVERY_DEPTH[best_intent]
        )
    
    def _extract_entities(self, message: str, intent_type: IntentType) -> Dict[str, Any]:
        """Extract relevant entities from message."""
        
        entities = {}
        
        # Extract domains/interests
        if intent_type in [IntentType.EXPLORE, IntentType.RESEARCH]:
            # Look for nouns that might be interests/topics
            import re
            # Simple noun phrase extraction
            nouns = re.findall(r'\b(?:love|hate|like|enjoy|passion|interest)\s+(\w+)', message.lower())
            if nouns:
                entities['interests'] = nouns
            
            # Look for "X and Y" patterns
            combined = re.findall(r'(\w+)\s+(?:and|&)\s+(\w+)', message.lower())
            if combined:
                entities['combined_interests'] = combined[0]
        
        # Extract people mentioned
        people = re.findall(r'\b(?:my|son|daughter|wife|husband|friend|kid|kids|child|children)\b', message.lower())
        if people:
            entities['people'] = people
        
        return entities
    
    def route_to_flow(self, intent: Intent) -> str:
        """Determine which flow to use based on intent."""
        
        if intent.discovery_depth == "none":
            return "chat"
        elif intent.discovery_depth == "minimal":
            return "quick_discovery"
        elif intent.discovery_depth == "light":
            return "light_discovery"
        else:
            return "full_discovery"
```

### Flow Routing

```python
# In agent/loop.py - Modified _process_message

async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
    """Process message with intent detection."""
    
    # Step 1: Detect intent
    intent_detector = IntentDetector()
    intent = intent_detector.detect(msg.content)
    
    # Step 2: Route to appropriate flow
    flow = intent_detector.route_to_flow(intent)
    
    if flow == "chat":
        # Direct conversational response
        return await self._handle_chat(msg)
    
    elif flow == "quick_discovery":
        # 1-2 questions max, then answer
        return await self._handle_quick_discovery(msg, intent)
    
    elif flow == "light_discovery":
        # Light exploration, then present options
        return await self._handle_light_discovery(msg, intent)
    
    elif flow == "full_discovery":
        # Full discovery → synthesis → approval → execution
        return await self._handle_full_discovery(msg, intent)
```

### Quick Discovery Flow (for ADVICE/RESEARCH)

```
User: "How do I organize weekly groceries?"

→ Intent: ADVICE (confidence: 0.85)
→ Depth: minimal
→ Suggested bots: [leader, researcher]

Step 1: Ask ONE clarifying question
  Leader: "Do you meal prep or buy spontaneously?" (or skip if clear)

Step 2: Provide advice directly
  Researcher: "Here are 3 approaches..."
  Leader: Summary + specific recommendation

Step 3: Done (no execution needed)
```

### Light Discovery Flow (for EXPLORE/TASK)

```
User: "I love gardening and photography, can I make money from it?"

→ Intent: EXPLORE (confidence: 0.9)
→ Depth: light
→ Suggested bots: [leader, researcher, creative]

Step 1: Quick discovery (2-3 questions)
  Researcher: "What's your weekly time commitment?"
  Creative: "What's your photography style?"

Step 2: Research business models
  Researcher: Search 3-5 monetization options

Step 3: Present options (no approval needed)
  Leader: "Here are 5 ways to monetize..."

Step 4: Done (or escalate to full if user wants to build something)
```

### Escalation: When to Escalate to Full Discovery

If user says things like:
- "Let's do option 3" (wants to build)
- "Can you build that?" 
- "I want to create a website for this"
- "How would I actually start this?"

Then escalate from EXPLORE/ADVICE → BUILD:

```
EXPLORE/ADVICE:
  "Here are 5 ways to monetize your gardening + photography"
  
User: "I like option 3, can you help me build it?"
  
  → Escalate to BUILD intent
  → Start full discovery: "Great! To build [option 3], I need to ask a few questions..."
  → Continue full flow: DISCOVERY → SYNTHESIS → APPROVAL → EXECUTION
```

---

## GSD Framework Inspiration

### Core Patterns Adopted

| GSD Pattern | Nanofolks Implementation |
|-------------|------------------------|
| `discuss-phase` | DISCOVERY - Bots ask questions in-room |
| `plan-phase` | SYNTHESIS - Leader formats findings |
| `execute-phase` | EXECUTION - Delegation & work |
| `verify-work` | REVIEW - User acceptance |
| `STATE.md` | PROJECT_STATE.md - Cross-session memory |
| Fresh context per task | Fresh context per bot response |
| Wave execution | Wave-based question asking |

### Unified State Machine (All Intents)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STATE MACHINE (ALL FLOWS)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────┐  │
│  │  IDLE   │ ────▶ │  ROUTING   │ ────▶ │  ACTIVE    │ ────▶ │  IDLE   │  │
│  │         │      │             │      │  (varies)   │      │         │  │
│  └─────────┘      └─────────────┘      └─────────────┘      └─────────┘  │
│                           │                    │                              │
│                           │                    ▼                              │
│                           │           ┌─────────────────────┐               │
│                           │           │    SUB-PHASES      │               │
│                           │           ├─────────────────────┤               │
│                           │           │ CHAT: (none)       │               │
│                           │           │ QUICK: Q → A       │               │
│                           │           │ LIGHT: Qs → opts   │               │
│                           │           │ FULL: D→S→A→E→R   │               │
│                           │           └─────────────────────┘               │
│                           │                    │                              │
│                           │                    ▼                              │
│                           │           ┌─────────────────────┐               │
│                           │           │ COMPLETION TYPES    │               │
│                           │           ├─────────────────────┤               │
│                           │           │ - success           │               │
│                           │           │ - escalation        │               │
│                           │           │ - cancellation      │               │
│                           │           │ - timeout           │               │
│                           │           └─────────────────────┘               │
│                           │                                                   │
└───────────────────────────┼───────────────────────────────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  INTENT: BUILD  │  (example full flow)
                 └────────┬────────┘
                          │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ DISCOVERY │  │ SYNTHESIS │  │ APPROVAL   │
    │ (Qs in    │  │ (Leader   │  │ (User      │
    │  room)    │  │  formats)  │  │  reviews)  │
    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
          │                │                │
          │                │         ┌──────┴──────┐
          │                │         │             │
          │                │         ▼             ▼
          │                │    ┌────────┐   ┌────────┐
          │                │    │  YES   │   │   NO   │
          │                │    └───┬────┘   └───┬────┘
          │                │        │             │
          │                │        │             ▼
          │                │        │     ┌─────────────┐
          └───────────────┼────────┘     │   BACK TO   │
                          │              │  DISCOVERY  │
                          ▼              └─────────────┘
                   ┌────────────┐
                   │ EXECUTION  │
                   │ (delegation│
                   │  + work)  │
                   └─────┬──────┘
                         │
                         ▼
                   ┌────────────┐
                   │  REVIEW   │
                   │ (user OK) │
                   └───────────┘
```

### Completion Types

Every flow ends with one of these:

| Type | Description | Next Action |
|------|-------------|-------------|
| **success** | Flow completed normally | Return to IDLE |
| **escalation** | User wants to build on result | Start FULL flow |
| **cancellation** | User says "never mind" / "stop" | Return to IDLE |
| **timeout** | No response in X minutes | Return to IDLE (save state) |
| **error** | Bot/LLM failure | Retry or return to IDLE |

---

## Implementation Plan

### Week 1: State Machine & Project State Management

#### 1.1 Project State Manager

```python
# nanofolks/agent/project_state.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json

class ProjectPhase(Enum):
    """Project lifecycle phases."""
    IDLE = "idle"
    DISCOVERY = "discovery"
    SYNTHESIS = "synthesis"
    APPROVAL = "approval"
    EXECUTION = "execution"
    REVIEW = "review"

@dataclass
class ProjectState:
    """Current state of a project/task."""
    phase: ProjectPhase = ProjectPhase.IDLE
    user_goal: str = ""
    discovery_log: List[Dict[str, Any]] = field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    approval: Optional[Dict[str, Any]] = None
    execution_plan: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    iteration: int = 0  # How many times we've looped

class ProjectStateManager:
    """Manages project state across sessions."""
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_dir = workspace / ".nanofolks" / "project_states"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{room_id}.json"
        self._state: Optional[ProjectState] = None
    
    @property
    def state(self) -> ProjectState:
        """Load and cache state."""
        if self._state is None:
            self._state = self._load_state()
        return self._state
    
    def _load_state(self) -> ProjectState:
        """Load state from disk."""
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
        """Persist state to disk."""
        data = {
            'phase': self.state.phase.value,
            'user_goal': self.state.user_goal,
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
    
    def start_discovery(self, user_goal: str):
        """Begin a new discovery phase."""
        self.state.phase = ProjectPhase.DISCOVERY
        self.state.user_goal = user_goal
        self.state.discovery_log = []
        self.state.iteration += 1
        self._save_state()
    
    def log_discovery_entry(self, bot_name: str, question: str, 
                           is_question: bool = True):
        """Log a discovery question/answer."""
        self.state.discovery_log.append({
            'bot': bot_name,
            'content': question,
            'is_question': is_question,
            'timestamp': datetime.now().isoformat()
        })
        self._save_state()
    
    def complete_discovery(self):
        """Transition from discovery to synthesis."""
        self.state.phase = ProjectPhase.SYNTHESIS
        self._save_state()
    
    def set_synthesis(self, synthesis: Dict[str, Any]):
        """Set the synthesis document."""
        self.state.synthesis = synthesis
        self.state.phase = ProjectPhase.APPROVAL
        self._save_state()
    
    def approve(self, approved: bool, feedback: Optional[str] = None):
        """Handle user approval decision."""
        self.state.approval = {
            'approved': approved,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }
        
        if approved:
            self.state.phase = ProjectPhase.EXECUTION
        else:
            # Loop back to discovery if rejected
            self.state.phase = ProjectPhase.DISCOVERY
        
        self._save_state()
    
    def start_execution(self, execution_plan: Dict[str, Any]):
        """Begin execution phase."""
        self.state.execution_plan = execution_plan
        self.state.phase = ProjectPhase.EXECUTION
        self._save_state()
    
    def complete_execution(self):
        """Transition to review."""
        self.state.phase = ProjectPhase.REVIEW
        self._save_state()
    
    def complete_review(self):
        """Reset to idle."""
        self.state.phase = ProjectPhase.IDLE
        self._save_state()
    
    def get_context_for_bot(self, bot_name: str) -> str:
        """Get formatted context for a bot based on current state."""
        
        sections = [
            f"# Project Context",
            f"",
            f"## Current Phase: {self.state.phase.value.upper()}",
            f"",
        ]
        
        if self.state.user_goal:
            sections.extend([
                f"## User's Goal",
                f"{self.state.user_goal}",
                f"",
            ])
        
        if self.state.phase == ProjectPhase.DISCOVERY:
            sections.extend([
                f"## Discovery Phase",
                f"",
                f"**Your task:** Ask clarifying questions to understand the user's goal.",
                f"",
                f"**Instructions:**",
                f"- Ask questions that help refine the goal",
                f"- Ask ONE question per response (be concise)",
                f"- If you need more information, ask about:",
                f"  - Scope: What exactly should be built?",
                f"  - Constraints: Budget, timeline, platform?",
                f"  - Preferences: Style, features, competitors?",
                f"- Wait for user response before asking another question",
                f"",
            ])
            
            # Show what questions have been asked
            if self.state.discovery_log:
                sections.extend([
                    f"## Questions Already Asked",
                    f"",
                ])
                for entry in self.state.discovery_log:
                    if entry['is_question']:
                        sections.append(f"- @{entry['bot']}: {entry['content']}")
                sections.append("")
        
        elif self.state.phase == ProjectPhase.SYNTHESIS:
            sections.extend([
                f"## Synthesis Phase",
                f"",
                f"**Your task:** Review discovery log and create an organized brief.",
                f"",
            ])
        
        elif self.state.phase == ProjectPhase.APPROVAL:
            sections.extend([
                f"## Approval Phase",
                f"",
                f"**Your task:** Present the synthesized plan to the user.",
                f"",
            ])
        
        elif self.state.phase == ProjectPhase.EXECUTION:
            sections.extend([
                f"## Execution Phase",
                f"",
                f"**Your task:** Execute your assigned work.",
                f"",
            ])
        
        return "\n".join(sections)
```

---

### Week 2: Discovery Coordinator & Question Wave Execution

#### 2.1 Clarifying Question Detector

```python
# nanofolks/agent/discovery_coordinator.py

import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class QuestionType(Enum):
    """Types of clarifying questions."""
    SCOPE = "scope"           # What exactly should be built?
    CONSTRAINT = "constraint" # Budget, timeline, platform?
    PREFERENCE = "preference" # Style, features, competitors?
    CLARIFICATION = "clarification" # Something unclear?
    ASSUMPTION = "assumption" # Checking assumptions?

@dataclass
class DetectedQuestion:
    """A detected question from bot response."""
    text: str
    question_type: QuestionType
    is_genuine_question: bool  # Not rhetorical
    keywords: List[str]

class ClarifyingQuestionDetector:
    """Detect when a bot response contains clarifying questions."""
    
    QUESTION_KEYWORDS = {
        QuestionType.SCOPE: [
            'what', 'exactly', 'specifically', 'scope', 'include',
            'feature', 'functionality', 'build', 'create', 'make'
        ],
        QuestionType.CONSTRAINT: [
            'budget', 'cost', 'price', 'timeline', 'deadline',
            'when', 'by when', 'platform', 'technology', 'stack',
            'hosting', 'domain', 'deploy'
        ],
        QuestionType.PREFERENCE: [
            'prefer', 'like', 'want', 'style', 'design',
            'color', 'look', 'feel', 'brand', 'existing',
            'competitor', 'example', 'similar'
        ],
        QuestionType.CLARIFICATION: [
            'understand', 'clarify', 'confused', 'unclear',
            'mean', 'meaning', 'explain'
        ],
        QuestionType.ASSUMPTION: [
            'assume', 'assumption', 'presume', 'likely',
            'probably', 'should'
        ]
    }
    
    def detect(self, text: str) -> List[DetectedQuestion]:
        """Detect questions in bot response."""
        questions = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if it's a question
            is_question = '?' in sentence or self._is_implicit_question(sentence)
            
            if is_question:
                question_type = self._classify_question(sentence)
                keywords = self._extract_keywords(sentence)
                is_genuine = self._is_genuine_question(sentence, keywords)
                
                questions.append(DetectedQuestion(
                    text=sentence,
                    question_type=question_type,
                    is_genuine_question=is_genuine,
                    keywords=keywords
                ))
        
        return questions
    
    def _is_implicit_question(self, text: str) -> bool:
        """Detect questions without question marks."""
        text_lower = text.lower()
        
        # Question patterns without ?
        implicit_patterns = [
            r'\bwhat about\b',
            r'\bhow about\b',
            r'\bcan you tell me\b',
            r'\bi need to know\b',
            r'\bwould you like\b',
            r'\bdo you want\b',
            r'\blets clarify\b',
        ]
        
        return any(re.search(p, text_lower) for p in implicit_patterns)
    
    def _classify_question(self, text: str) -> QuestionType:
        """Classify the type of question."""
        text_lower = text.lower()
        
        # Score each type
        scores = {}
        for qtype, keywords in self.QUESTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[qtype] = score
        
        # Return highest scoring type
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return QuestionType.CLARIFICATION  # Default
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from question."""
        words = re.findall(r'\b\w+\b', text.lower())
        all_keywords = []
        for keywords in self.QUESTION_KEYWORDS.values():
            all_keywords.extend(keywords)
        
        return [w for w in words if w in all_keywords]
    
    def _is_genuine_question(self, text: str, keywords: List[str]) -> bool:
        """Determine if question is genuine or rhetorical."""
        text_lower = text.lower()
        
        # Rhetorical patterns
        rhetorical = [
            'isn\'t it',
            'wouldn\'t you',
            'obviously',
            'clearly',
            'as we know',
            'as mentioned',
        ]
        
        return not any(r in text_lower for r in rhetorical)
    
    def count_questions(self, bot_name: str, discovery_log: List[Dict]) -> int:
        """Count questions a bot has already asked."""
        return sum(
            1 for entry in discovery_log 
            if entry['bot'] == bot_name and entry.get('is_question', True)
        )
```

#### 2.2 Discovery Coordinator

```python
# nanofolks/agent/discovery_coordinator.py (continued)

from typing import Set

class DiscoveryCoordinator:
    """Coordinates the discovery phase - wave-based question asking."""
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_manager = ProjectStateManager(workspace, room_id)
        self.question_detector = ClarifyingQuestionDetector()
    
    async def start_discovery(self, user_goal: str) -> str:
        """Begin discovery phase."""
        self.state_manager.start_discovery(user_goal)
        
        # Select relevant bots to participate
        relevant_bots = self._select_relevant_bots(user_goal)
        
        # Build initial context
        context = self._build_discovery_context(relevant_bots)
        
        return context
    
    def _select_relevant_bots(self, goal: str) -> List[str]:
        """Select bots relevant to the user's goal."""
        goal_lower = goal.lower()
        
        bot_keywords = {
            "coder": ["build", "website", "app", "code", "program", "software", "api", "database"],
            "researcher": ["research", "market", "analyze", "data", "competitor", "find"],
            "creative": ["design", "brand", "logo", "visual", "content", "copy"],
            "social": ["post", "social", "marketing", "campaign", "audience"],
            "auditor": ["audit", "review", "check", "security", "quality"],
            "leader": ["plan", "coordinate", "strategy"]
        }
        
        scores = {}
        for bot, keywords in bot_keywords.items():
            score = sum(1 for kw in keywords if kw in goal_lower)
            scores[bot] = score
        
        # Return bots with score > 0, or default team
        relevant = [b for b, s in scores.items() if s > 0]
        return relevant if relevant else ["leader", "researcher", "creative"]
    
    def _build_discovery_context(self, bots: List[str]) -> str:
        """Build context for discovery phase."""
        
        sections = [
            "# Discovery Phase Started",
            "",
            f"User Goal: {self.state_manager.state.user_goal}",
            "",
            f"Participating Bots: {', '.join(f'@{b}' for b in bots)}",
            "",
            "## Instructions",
            "",
            "This is the DISCOVERY phase. The user has described a goal.",
            "",
            "Your task is to ask CLARIFYING questions to better understand",
            "what they want to build/create/achieve.",
            "",
            "## Guidelines:",
            "- Ask ONE question per response (be concise)",
            "- Focus on what you need to know to do your job",
            "- Questions should be specific to your domain",
            "- Wait for user response before asking more questions",
            "",
            "## Question Categories:",
            "- SCOPE: What exactly should be built?",
            "- CONSTRAINTS: Budget, timeline, platform?",
            "- PREFERENCES: Style, features, competitors?",
            "",
        ]
        
        return "\n".join(sections)
    
    def process_bot_response(self, bot_name: str, response: str) -> Dict:
        """Process a bot's response during discovery."""
        
        # Detect questions in response
        questions = self.question_detector.detect(response)
        
        genuine_questions = [q for q in questions if q.is_genuine_question]
        
        # Log to discovery log
        if genuine_questions:
            for q in genuine_questions:
                self.state_manager.log_discovery_entry(
                    bot_name=bot_name,
                    question=q.text,
                    is_question=True
                )
        
        # Check if discovery is complete
        is_complete = self._is_discovery_complete(bot_name, response)
        
        return {
            'questions_asked': len(genuine_questions),
            'total_in_log': len(self.state_manager.state.discovery_log),
            'is_complete': is_complete,
            'response': response
        }
    
    def _is_discovery_complete(self, current_bot: str, response: str) -> bool:
        """Determine if discovery phase is complete."""
        state = self.state_manager.state
        
        # Discovery is complete when:
        # 1. At least 2 bots have asked questions
        bots_with_questions = set(
            entry['bot'] for entry in state.discovery_log 
            if entry.get('is_question', True)
        )
        
        if len(bots_with_questions) < 2:
            return False
        
        # 2. At least 3 questions asked total
        if len(state.discovery_log) < 3:
            return False
        
        # 3. Current bot provided substantive content (not just questions)
        if self._is_only_questions(response):
            return False
        
        return True
    
    def _is_only_questions(self, text: str) -> bool:
        """Check if response is only questions."""
        sentences = re.split(r'[.!?]\s+', text)
        question_markers = ['?', 'what', 'how', 'when', 'where', 'why', 'which', 'can']
        
        for sentence in sentences:
            sentence = sentence.strip().lower()
            if sentence and not any(q in sentence for q in question_markers):
                return False
        
        return True
    
    def get_synthesis_prompt(self) -> str:
        """Generate prompt for synthesis phase."""
        state = self.state_manager.state
        
        sections = [
            "# Synthesis Phase",
            "",
            f"User's Original Goal: {state.user_goal}",
            "",
            "## Discovery Log (Questions & Answers)",
            "",
        ]
        
        # Group by bot
        by_bot = {}
        for entry in state.discovery_log:
            bot = entry['bot']
            if bot not in by_bot:
                by_bot[bot] = []
            by_bot[bot].append(entry)
        
        for bot, entries in by_bot.items():
            sections.append(f"### @{bot}")
            for entry in entries:
                prefix = "❓" if entry.get('is_question', True) else "💬"
                sections.append(f"- {prefix} {entry['content']}")
            sections.append("")
        
        sections.extend([
            "## Your Task",
            "",
            "As the Leader, synthesize all the questions and answers into",
            "a clear, organized PROJECT BRIEF.",
            "",
            "## Output Format",
            "",
            "```markdown",
            "# Project Brief",
            "",
            "## Goal",
            "[One sentence describing what to build]",
            "",
            "## Scope",
            "- [Key features to include]",
            "- [What's explicitly in scope]",
            "",
            "## Constraints",
            "- Budget: [If mentioned]",
            "- Timeline: [If mentioned]",
            "- Platform/Technology: [If mentioned]",
            "",
            "## Unknowns (needs user input)",
            "- [Questions that weren't answered]",
            "",
            "## Recommended Next Steps",
            "- [Suggested tasks for each bot]",
            "```",
            "",
        ])
        
        return "\n".join(sections)
```

---

### Week 3: Synthesis & Approval Gate

#### 3.1 Synthesis Generator

```python
# nanofolks/agent/synthesis_generator.py

class SynthesisGenerator:
    """Generate organized project briefs from discovery log."""
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_manager = ProjectStateManager(workspace, room_id)
    
    async def generate_synthesis(self, discovery_context: str) -> Dict[str, Any]:
        """Generate synthesis from discovery log."""
        
        state = self.state_manager.state
        
        # Parse discovery log into structured format
        structured = self._parse_discovery_log(state.discovery_log)
        
        # Generate synthesis using LLM
        synthesis_prompt = self._build_synthesis_prompt(structured)
        
        # This would call the LLM
        synthesis = await self._call_llm(synthesis_prompt)
        
        # Update state
        self.state_manager.set_synthesis(synthesis)
        
        return synthesis
    
    def _parse_discovery_log(self, log: List[Dict]) -> Dict:
        """Parse discovery log into structured format."""
        
        by_bot = {}
        questions = []
        answers = []
        
        for entry in log:
            bot = entry['bot']
            content = entry['content']
            is_question = entry.get('is_question', True)
            
            if bot not in by_bot:
                by_bot[bot] = []
            by_bot[bot].append(entry)
            
            if is_question:
                questions.append({'bot': bot, 'content': content})
            else:
                answers.append({'bot': bot, 'content': content})
        
        return {
            'questions': questions,
            'answers': answers,
            'by_bot': by_bot,
            'total_entries': len(log)
        }
    
    def _build_synthesis_prompt(self, structured: Dict) -> str:
        """Build prompt for synthesis generation."""
        
        sections = [
            "# Task: Generate Project Brief",
            "",
            "Analyze the following discovery conversation and create",
            "a structured project brief.",
            "",
            "## Original User Goal",
            f"{self.state_manager.state.user_goal}",
            "",
            "## Discovery Conversation",
            "",
        ]
        
        # Add questions
        sections.append("### Questions Asked:")
        for q in structured['questions']:
            sections.append(f"- @{q['bot']}: {q['content']}")
        sections.append("")
        
        # Add answers
        sections.append("### Answers Given:")
        for a in structured['answers']:
            sections.append(f"- @{a['bot']}: {a['content']}")
        sections.append("")
        
        sections.extend([
            "## Output Requirements",
            "",
            "Create a JSON object with the following structure:",
            "",
            "```json",
            "{",
            '  "title": "Project name/short description",',
            '  "goal": "One sentence on what to build",',
            '  "scope": {',
            '    "included": ["list of features"],',
            '    "excluded": ["explicitly out of scope"]',
            '  },',
            '  "constraints": {',
            '    "budget": "budget if mentioned",',
            '    "timeline": "timeline if mentioned",',
            '    "platform": "platform/tech if mentioned"',
            '  },',
            '  "unknowns": ["questions not answered"],',
            '  "next_steps": {',
            '    "researcher": "what researcher should do",',
            '    "coder": "what coder should do",',
            '    "creative": "what creative should do",',
            '    "social": "what social should do",',
            '    "auditor": "what auditor should do"',
            '  }',
            "}",
            "```",
            "",
            "Generate ONLY the JSON, no other text.",
        ])
        
        return "\n".join(sections)
    
    async def _call_llm(self, prompt: str) -> Dict:
        """Call LLM to generate synthesis."""
        # Placeholder - would integrate with provider
        pass
    
    def format_for_user(self, synthesis: Dict) -> str:
        """Format synthesis for display to user."""
        
        sections = [
            "# 📋 Project Brief",
            "",
            f"## 🎯 Goal",
            synthesis.get('goal', 'TBD'),
            "",
        ]
        
        # Scope
        scope = synthesis.get('scope', {})
        if scope.get('included'):
            sections.append("## ✅ In Scope")
            for item in scope['included']:
                sections.append(f"- {item}")
            sections.append("")
        
        if scope.get('excluded'):
            sections.append("## ❌ Out of Scope")
            for item in scope['excluded']:
                sections.append(f"- {item}")
            sections.append("")
        
        # Constraints
        constraints = synthesis.get('constraints', {})
        if any(constraints.values()):
            sections.append("## 🔒 Constraints")
            for key, value in constraints.items():
                if value:
                    sections.append(f"- **{key.title()}**: {value}")
            sections.append("")
        
        # Unknowns
        unknowns = synthesis.get('unknowns', [])
        if unknowns:
            sections.append("## ❓ Need More Info")
            for item in unknowns:
                sections.append(f"- {item}")
            sections.append("")
        
        # Next steps
        next_steps = synthesis.get('next_steps', {})
        if next_steps:
            sections.append("## 🚀 Proposed Next Steps")
            for bot, task in next_steps.items():
                if task:
                    emoji = {
                        'leader': '👑', 'researcher': '📊',
                        'coder': '💻', 'creative': '🎨',
                        'social': '📱', 'auditor': '🔍'
                    }.get(bot, '🤖')
                    sections.append(f"{emoji} **@{bot}**: {task}")
            sections.append("")
        
        sections.append("---")
        sections.append("")
        sections.append("**Approve this plan?** (Reply with `yes` or describe what to change)")
        
        return "\n".join(sections)
```

#### 3.2 Approval Gate

```python
# nanofolks/agent/approval_gate.py

class ApprovalGate:
    """Handle user approval of synthesis."""
    
    def __init__(self, workspace: Path, room_id: str):
        self.workspace = workspace
        self.room_id = room_id
        self.state_manager = ProjectStateManager(workspace, room_id)
    
    async def request_approval(self, synthesis: Dict) -> str:
        """Present synthesis to user and request approval."""
        
        # Format synthesis for display
        from nanofolks.agent.synthesis_generator import SynthesisGenerator
        generator = SynthesisGenerator(self.workspace, self.room_id)
        
        return generator.format_for_user(synthesis)
    
    def handle_response(self, user_response: str) -> Dict:
        """Process user's approval response."""
        
        response_lower = user_response.lower().strip()
        
        # Check for approval
        approval_phrases = ['yes', 'yep', 'sure', 'ok', 'okay', 'go ahead', 'looks good', 'approved']
        rejection_phrases = ['no', 'nope', 'change', 'instead', 'actually', 'wait']
        
        is_approved = any(phrase in response_lower for phrase in approval_phrases)
        
        if is_approved:
            self.state_manager.approve(approved=True)
            return {
                'approved': True,
                'message': "Great! Starting execution...",
                'next_phase': 'execution'
            }
        
        # Handle rejection/feedback
        feedback = user_response  # The user's changes/corrections
        
        # Log feedback for next discovery iteration
        self.state_manager.log_discovery_entry(
            bot_name='user',
            question=f"FEEDBACK: {feedback}",
            is_question=False
        )
        
        self.state_manager.approve(approved=False, feedback=feedback)
        
        return {
            'approved': False,
            'message': "Understood! Let me ask more questions to clarify...",
            'next_phase': 'discovery'
        }
    
    def get_execution_context(self) -> str:
        """Get context for execution phase."""
        
        state = self.state_manager.state
        synthesis = state.synthesis
        next_steps = synthesis.get('next_steps', {})
        
        sections = [
            "# Execution Phase Started",
            "",
            f"Project: {synthesis.get('title', 'Unnamed')}",
            "",
            "## Your Assigned Task",
            "",
        ]
        
        # Get task for this specific bot (would be parameterized)
        # For now, show all
        for bot, task in next_steps.items():
            if task:
                emoji = {
                    'leader': '👑', 'researcher': '📊',
                    'coder': '💻', 'creative': '🎨',
                    'social': '📱', 'auditor': '🔍'
                }.get(bot, '🤖')
                sections.append(f"{emoji} **@{bot}**: {task}")
        
        sections.extend([
            "",
            "## Execute your task and report back when complete.",
        ])
        
        return "\n".join(sections)
```

---

### Week 4: Integration & CLI Commands

#### 4.1 Agent Loop Integration

```python
# nanofolks/agent/loop.py - Discovery Flow Integration

class AgentLoop:
    # ... existing code ...
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """Process message with discovery flow support."""
        
        room = self._get_or_create_room(msg)
        state_manager = ProjectStateManager(self.workspace, room.id)
        current_phase = state_manager.state.phase
        
        if current_phase == ProjectPhase.IDLE:
            # Check if user is starting a new project
            if self._is_new_project(msg.content):
                return await self._handle_new_project(msg, room, state_manager)
        
        elif current_phase == ProjectPhase.DISCOVERY:
            return await self._handle_discovery(msg, room, state_manager)
        
        elif current_phase == ProjectPhase.SYNTHESIS:
            return await self._handle_synthesis(msg, room, state_manager)
        
        elif current_phase == ProjectPhase.APPROVAL:
            return await self._handle_approval(msg, room, state_manager)
        
        elif current_phase == ProjectPhase.EXECUTION:
            return await self._handle_execution(msg, room, state_manager)
        
        elif current_phase == ProjectPhase.REVIEW:
            return await self._handle_review(msg, room, state_manager)
        
        # Default: handle as normal
        return await self._handle_normal_message(msg, room)
    
    def _is_new_project(self, content: str) -> bool:
        """Check if user is starting a new project."""
        content_lower = content.lower()
        
        # Keywords that indicate new project intent
        new_project_keywords = [
            'build', 'create', 'make', 'develop',
            'start', 'begin', 'new project',
            'want to', 'i need', 'help me'
        ]
        
        return any(kw in content_lower for kw in new_project_keywords)
    
    async def _handle_new_project(
        self, 
        msg: InboundMessage, 
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Start a new project discovery flow."""
        
        # Begin discovery
        coordinator = DiscoveryCoordinator(self.workspace, room.id)
        context = await coordinator.start_discovery(msg.content)
        
        # Trigger first bot to ask a question
        first_bot = "leader"
        response = await self._generate_bot_response(
            bot_name=first_bot,
            context=context,
            user_message=msg.content
        )
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response,
            metadata={'phase': 'discovery', 'bot': first_bot}
        )
    
    async def _handle_discovery(
        self,
        msg: InboundMessage,
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Handle discovery phase."""
        
        coordinator = DiscoveryCoordinator(self.workspace, room.id)
        
        # Determine which bot should respond
        current_bot = self._get_next_discovery_bot(state_manager.state.discovery_log)
        
        # Generate response
        context = state_manager.get_context_for_bot(current_bot)
        response = await self._generate_bot_response(
            bot_name=current_bot,
            context=context,
            user_message=msg.content
        )
        
        # Process response (detect questions)
        result = coordinator.process_bot_response(current_bot, response)
        
        # Check if discovery is complete
        if result['is_complete']:
            coordinator.state_manager.complete_discovery()
            
            # Move to synthesis
            synthesis_gen = SynthesisGenerator(self.workspace, room.id)
            synthesis = await synthesis_gen.generate_synthesis(context)
            
            # Request approval
            approval_gate = ApprovalGate(self.workspace, room.id)
            approval_content = await approval_gate.request_approval(synthesis)
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=approval_content,
                metadata={'phase': 'approval'}
            )
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response,
            metadata={'phase': 'discovery', 'bot': current_bot}
        )
    
    def _get_next_discovery_bot(self, discovery_log: List[Dict]) -> str:
        """Determine which bot should ask next question."""
        
        # Count questions per bot
        bot_counts = {}
        for entry in discovery_log:
            if entry.get('is_question', True):
                bot = entry['bot']
                bot_counts[bot] = bot_counts.get(bot, 0) + 1
        
        # Prefer bots who haven't asked many questions yet
        all_bots = ['leader', 'researcher', 'creative', 'coder', 'social', 'auditor']
        
        for bot in all_bots:
            if bot not in bot_counts or bot_counts[bot] < 2:
                return bot
        
        return 'leader'  # Default
    
    async def _handle_synthesis(
        self,
        msg: InboundMessage,
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Handle synthesis (triggered after discovery complete)."""
        
        # Actually handled in discovery completion
        # This is a fallback
        approval_gate = ApprovalGate(self.workspace, room.id)
        synthesis = state_manager.state.synthesis
        content = await approval_gate.request_approval(synthesis)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=content,
            metadata={'phase': 'approval'}
        )
    
    async def _handle_approval(
        self,
        msg: InboundMessage,
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Handle approval phase."""
        
        approval_gate = ApprovalGate(self.workspace, room.id)
        result = approval_gate.handle_response(msg.content)
        
        if result['approved']:
            # Start execution
            execution_context = approval_gate.get_execution_context()
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=execution_context,
                metadata={'phase': 'execution'}
            )
        else:
            # Back to discovery
            coordinator = DiscoveryCoordinator(self.workspace, room.id)
            context = coordinator._build_discovery_context(
                ['leader', 'researcher', 'creative']
            )
            
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result['message'] + "\n\n" + context,
                metadata={'phase': 'discovery'}
            )
    
    async def _handle_execution(
        self,
        msg: InboundMessage,
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Handle execution phase."""
        
        # Similar to current multi-bot execution
        # But now with clearer task assignments from synthesis
        pass
    
    async def _handle_review(
        self,
        msg: InboundMessage,
        room: Room,
        state_manager: ProjectStateManager
    ) -> OutboundMessage:
        """Handle review phase."""
        
        # Complete review and reset to idle
        state_manager.complete_review()
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="Great work! Let me know if you need anything else.",
            metadata={'phase': 'idle'}
        )
```

#### 4.2 CLI Commands

```bash
# Project state commands

nanofolks project status              # Show current project state
nanofolks project state               # Same as status
nanofolks project reset               # Reset to idle (cancel current project)
nanofolks project log                 # Show discovery log
nanofolks project brief               # Show current project brief
```

```python
# nanofolks/cli/commands.py - Project commands

@cli.group()
def project():
    """Project state management."""
    pass

@project.command()
@click.pass_obj
def status(obj):
    """Show current project state."""
    workspace = obj['workspace']
    room_id = obj.get('room_id', 'default')
    
    state_manager = ProjectStateManager(workspace, room_id)
    state = state_manager.state
    
    click.echo(f"\n📊 Project Status")
    click.echo("=" * 40)
    click.echo(f"Phase: {state.phase.value.upper()}")
    click.echo(f"Iteration: {state.iteration}")
    
    if state.user_goal:
        click.echo(f"\n🎯 Goal: {state.user_goal}")
    
    if state.discovery_log:
        click.echo(f"\n❓ Questions asked: {len(state.discovery_log)}")
    
    if state.synthesis:
        click.echo(f"\n📋 Brief: {state.synthesis.get('title', 'Untitled')}")
    
    if state.approval:
        status = "✅ Approved" if state.approval['approved'] else "❌ Rejected"
        click.echo(f"\n{status}")

@project.command()
@click.pass_obj
@click.confirmation_option(prompt='Reset project state?')
def reset(obj):
    """Reset project to idle state."""
    workspace = obj['workspace']
    room_id = obj.get('room_id', 'default')
    
    state_manager = ProjectStateManager(workspace, room_id)
    state_manager.state.phase = ProjectPhase.IDLE
    state_manager._save_state()
    
    click.echo("✅ Project reset to idle")

@project.command()
@click.pass_obj
@click.option('--limit', '-n', default=20, help='Number of entries to show')
def log(obj, limit: int):
    """Show discovery log."""
    workspace = obj['workspace']
    room_id = obj.get('room_id', 'default')
    
    state_manager = ProjectStateManager(workspace, room_id)
    
    if not state_manager.state.discovery_log:
        click.echo("No discovery log yet")
        return
    
    click.echo(f"\n📜 Discovery Log (last {limit})")
    click.echo("=" * 50)
    
    for entry in state_manager.state.discovery_log[-limit:]:
        bot = entry['bot']
        content = entry['content']
        is_question = entry.get('is_question', True)
        
        prefix = "❓" if is_question else "💬"
        click.echo(f"\n{prefix} @{bot}:")
        click.echo(f"   {content}")
```

---

## File Structure

```
nanofolks/
├── agent/
│   ├── project_state.py           # NEW - Week 1
│   ├── discovery_coordinator.py   # NEW - Week 2
│   ├── synthesis_generator.py     # NEW - Week 3
│   ├── approval_gate.py           # NEW - Week 3
│   └── loop.py                   # MODIFIED - Week 4
├── models/
│   └── bot_dm_room.py            # EXISTING - Phase 1
├── bots/
│   ├── dispatch.py               # EXISTING - Phase 1
│   └── dm_room_manager.py        # EXISTING - Phase 1
├── identity/
│   └── relationship_parser.py    # EXISTING - Phase 1
└── cli/
    └── commands.py               # MODIFIED - Week 4
```

---

## State Files

```
.nanofolks/
├── project_states/
│   ├── default.json              # Project state for default room
│   ├── room_123.json             # Per-room project states
│   └── ...
└── dm_rooms/                     # Existing - Phase 1
```

---

## Testing Checklist

### Week 1: State Machine
- [ ] ProjectStateManager loads/saves correctly
- [ ] State transitions work (IDLE → DISCOVERY → SYNTHESIS → etc.)
- [ ] Iteration counter increments on loop-back
- [ ] CLI `project status` shows correct state

### Week 2: Discovery Coordinator
- [ ] Bot selection works based on keywords
- [ ] Question detection identifies genuine questions
- [ ] Discovery log records questions correctly
- [ ] Wave completion triggers synthesis

### Week 3: Synthesis & Approval
- [ ] Synthesis generates valid JSON structure
- [ ] User approval advances to execution
- [ ] Rejection loops back to discovery
- [ ] Feedback is logged

### Week 4: Integration
- [ ] Full flow works end-to-end
- [ ] CLI commands function correctly
- [ ] Backward compatibility maintained
- [ ] Edge cases handled (empty responses, etc.)

---

## Backward Compatibility

- [ ] Existing single-bot workflows unchanged
- [ ] Phase 1 features (@all, @crew, affinity) still work
- [ ] No breaking changes to existing commands
- [ ] Config flag not needed (automatic detection)

---

## Missing Pieces (Added)

### Cancellation Handling

Users need a way to stop/cancel ongoing flows:

```python
# Handle cancellation keywords
CANCEL_KEYWORDS = [
    'cancel', 'stop', 'never mind', 'forget it',
    'abort', 'quit', 'exit', 'never'
]

def handle_cancellation(self, user_message: str) -> bool:
    """Check if user wants to cancel."""
    return any(kw in user_message.lower() for kw in CANCEL_KEYWORDS)

# In agent loop:
if self.handle_cancellation(msg.content):
    state_manager.reset_to_idle()
    return OutboundMessage(
        content="Okay, cancelled. Let me know if you need anything else.",
        metadata={'cancelled': True}
    )
```

### Multi-Project Support

Allow multiple concurrent projects (per room):

```python
@dataclass
class ProjectState:
    # ... existing fields ...
    project_id: str = "default"  # Support multiple projects per room
    projects: Dict[str, Any] = field(default_factory=dict)  # Multiple projects

# Projects stored as:
# .nanofolks/project_states/room_id/default.json
# .nanofolks/project_states/room_id/project_abc.json
```

### Timeout Handling

Auto-return to IDLE after inactivity:

```python
class ProjectStateManager:
    TIMEOUT_MINUTES = 30
    
    def check_timeout(self) -> bool:
        """Check if project has timed out."""
        if self.state.phase == ProjectPhase.IDLE:
            return False
        
        last_update = datetime.fromisoformat(self.state.updated_at)
        elapsed = (datetime.now() - last_update).total_seconds() / 60
        
        if elapsed > self.TIMEOUT_MINUTES:
            # Save current state and return to idle
            self.state.phase = ProjectPhase.IDLE
            self._save_state()
            return True
        
        return False
```

---

## Integration with Phase 2

Phase 1.5 uses room-based state. Phase 2 migrates sessions to room-based keys. Here's how they integrate:

### Current (Phase 1.5):
```
Session key: telegram:123456 (per-channel)
State:       .nanofolks/project_states/default.json
```

### Phase 2 Target:
```
Session key: room:general (room-based)
State:       .nanofolks/project_states/room_general.json
```

### Migration Path:

| Phase 1.5 | Phase 2 | Notes |
|------------|---------|-------|
| `project_states/default.json` | `project_states/room_{id}.json` | Auto-migrated |
| `channel:chat_id` sessions | `room:{id}` sessions | Via migration tool |
| Intent detection | Still applies | No change needed |
| Discovery flows | Still applies | Room-scoped |

### Integration Point:
- Phase 1.5 writes state to `project_states/{room_id}.json`
- Phase 2 session migration reads this and maps to `room:{id}` sessions
- Both use the same room concept, just different storage layers

---

## Future Considerations (Phase 2+)

1. **Session Migration** - Move from channel:chat_id to room:{id} keys
2. **Cross-Channel Sync** - Unified history across Telegram, Slack, CLI
3. **Task Rooms** - Automatic room creation for long-running tasks
4. **Memory Integration** - Store project context in long-term memory

---

## GSD Template Integration

We can enhance the discovery flow implementation by adapting GSD (Get Shit Done) templates:

### 1. Discovery Template (discovery.md)

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/discovery.md

**How to adapt for nanofolks:**

```markdown
# Discovery: [topic]

## Summary
[2-3 paragraph executive summary - what was researched, what was found, what's recommended]

## Primary Recommendation
[What to do and why - be specific and actionable]

## Alternatives Considered
[What else was evaluated and why not chosen]

## Key Findings

### [Category 1]
- [Finding with source URL and relevance to our case]

### [Category 2]
- [Finding with source URL and relevance]

## Confidence Level
- HIGH: Sources confirm
- MEDIUM: WebSearch + sources confirm  
- LOW: Needs validation during execution
```

**Usage in nanofolks:** Apply this template when the EXPLORE intent needs to research options (e.g., "What are the best tools for X?").

### 2. Checkpoint Patterns (from phase-prompt.md)

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/phase-prompt.md

**Adopt the checkpoint:human-verify pattern for APPROVAL phase:**

```python
# In approval_gate.py - enhance with checkpoint patterns
class ApprovalCheckpointType(Enum):
    HUMAN_VERIFY = "checkpoint:human-verify"  # Visual/functional verification
    DECISION = "checkpoint:decision"           # Implementation choices
    HUMAN_ACTION = "checkpoint:human-action"    # Manual steps (rare)
```

**Key differences from current implementation:**
- Include `what-built` (what Claude built) + URL for verification
- Include `how-to-verify` (specific checks, not vague "verify it works")
- Include `resume-signal` (what user should type to proceed)

### 3. Summary Template (summary.md) for REVIEW phase

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/summary.md

**Enhance the REVIEW phase with structured output:**

```markdown
---
phase: XX-name
plan: YY
subsystem: [auth, ui, api, database, etc.]
tags: [searchable tech keywords]

# Dependency graph
requires:
  - phase: [prior phase]
    provides: [what that phase built]
provides:
  - [what this phase built/delivered]
affects: [phases that need this context]

# Tech tracking
tech-stack:
  added: [libraries/tools]
  patterns: [architectural patterns]
---

# Phase [X]: [Name] Summary

**[Substantive one-liner - NOT "phase complete"]**

## Performance
- Duration: [time]
- Tasks: [count]

## Accomplishments
- [Key outcome 1]
- [Key outcome 2]

## Decisions Made
[Key decisions with rationale]

## Next Phase Readiness
[What's ready for next phase]
[Any blockers]
```

### 4. State Template (state.md) for Session Continuity

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/state.md

**Enhance ProjectStateManager with:**

```markdown
# Project State

## Current Position
Phase: [X] of [Y] - [Status]
Last activity: [YYYY-MM-DD]

## Session Continuity
Last session: [YYYY-MM-DD HH:MM]
Stopped at: [Description]
Resume file: [Path if exists]

## Decisions
[Recent decisions affecting current work]

## Blockers/Concerns
[Issues affecting future work]
```

### Integration Priority

| Priority | Template | Where to Use | Effort |
|----------|----------|--------------|--------|
| **High** | discovery.md | LIGHT flow research | Medium |
| **High** | checkpoint:human-verify | APPROVAL phase | Low |
| **Medium** | summary.md | REVIEW phase | Medium |
| **Low** | state.md | Session continuity | Low |

---

## Summary

Phase 1.5 adds the **Communal Discovery Flow** inspired by GSD's structured approach:

### Key Improvements from Original Design:

1. **Unified Flow Router** - Handles all intent types (CHAT, QUICK, LIGHT, FULL)
2. **Completion Types** - success, escalation, cancellation, timeout, error
3. **Cancellation Handling** - User can always abort
4. **Multi-Project Support** - Multiple concurrent projects per room
5. **Timeout Handling** - Auto-cleanup after inactivity
6. **Phase 2 Integration** - Clear migration path

### The Flow:

| Intent | Flow | Example |
|--------|------|---------|
| CHAT | direct | "That's interesting!" |
| ADVICE | Q → A | "How do I organize groceries?" |
| RESEARCH | Q → research → present | "Fun math games for kids?" |
| EXPLORE | Qs → options | "Can I make money from gardening?" |
| TASK | clarify → execute | "Write this email" |
| BUILD | D→S→A→E→R | "Build me a website" |

This transforms from "one assistant" to "true crew" - users see bots collaborating, asking questions, and reaching understanding before executing.
