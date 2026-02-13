# Phase 4: Coordinator Mode Design Document

## Overview

Phase 4 implements autonomous multi-bot orchestration through:
1. **CoordinatorMode** - State machine managing bot collaboration
2. **InterBotBus** - Message passing between bots
3. **TaskOrchestrator** - Task decomposition and delegation
4. **TeamSession** - Collaborative problem-solving sessions

## Architecture

### 1. Core Components

#### Message Types
```
BotMessage:
  - sender_id: str (which bot sent it)
  - recipient_id: str (target bot, "team" for broadcast)
  - message_type: str (request, response, report, discussion)
  - content: str (the message)
  - context: dict (metadata, references, constraints)
  - timestamp: datetime
  - conversation_id: str (threads messages)

TaskRequest:
  - task_id: str
  - title: str
  - description: str
  - domain: str (research, development, etc.)
  - priority: int (1-5)
  - requirements: list[str]
  - constraints: dict
  - assigned_to: str (bot_id)
  - status: str (pending, in_progress, completed, failed)
  - created_at: datetime
  - due_date: optional[datetime]

TaskResult:
  - task_id: str
  - bot_id: str
  - status: str (success, partial, failed)
  - result: str
  - confidence: float (0.0-1.0)
  - time_taken: float (seconds)
  - learnings: list[str] (what was learned)
  - follow_ups: list[TaskRequest] (new tasks discovered)
```

#### CoordinatorMode States
```
IDLE -> WAITING_FOR_REQUEST
WAITING_FOR_REQUEST -> ANALYZING (user message arrived)
ANALYZING -> TASK_DECOMPOSITION or ROUTE_TO_BOT
TASK_DECOMPOSITION -> DELEGATING
DELEGATING -> MONITORING
MONITORING -> ASSEMBLING_RESULTS or ERROR_HANDLING
ASSEMBLING_RESULTS -> PRESENTING
PRESENTING -> IDLE
ERROR_HANDLING -> RETRYING or ESCALATING
ESCALATING -> IDLE
```

#### InterBotBus
- Central message queue for bot communication
- Broadcast capabilities (message all bots)
- Unicast capabilities (direct messages)
- Message history with threading
- Conversation context management

### 2. Coordination Patterns

#### Pattern A: Simple Routing
```
User Request → nanobot analyzes domain
            → routes to single specialist
            → specialist completes task
            → result back to user
```

#### Pattern B: Sequential Collaboration
```
User Request → nanobot decomposes into steps
            → researcher gathers info
            → coder implements solution
            → auditor reviews
            → result back to user
```

#### Pattern C: Parallel Execution
```
User Request → nanobot creates 3 sub-tasks
            → researcher + coder + designer work in parallel
            → nanobot assembles results
            → presents to user
```

#### Pattern D: Team Discussion
```
User Scenario → nanobot frames discussion
            → each bot shares perspective
            → team deliberates
            → nanobot synthesizes consensus
            → presents recommendation
```

#### Pattern E: Escalation
```
Task assigned to bot
Bot encounters issue → requests assistance from team
Bot suggests 2 options → team votes
Majority decides → implementation continues
```

### 3. Task Delegation Strategy

#### Task Analysis
1. Parse user request
2. Identify domain(s)
3. Check complexity (single vs multi-bot)
4. Estimate time required
5. Check for parallel opportunities

#### Bot Selection
1. Get bot expertise scores from BotExpertise
2. Check hard bans for constraints
3. Load bot SOUL for personality fit
4. Consider current workload
5. Select optimal bot(s)

#### Dependency Management
- Track task dependencies (task B waits for A)
- Enable parallel execution of independent tasks
- Handle cascading failures
- Manage resource contention

### 4. Database Schema

#### New Tables

**bot_messages**
```sql
CREATE TABLE bot_messages (
    id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    conversation_id TEXT,
    context TEXT,  -- JSON
    timestamp REAL NOT NULL,
    FOREIGN KEY (sender_id) REFERENCES entities(id),
    FOREIGN KEY (recipient_id) REFERENCES entities(id),
    INDEX idx_messages_conversation,
    INDEX idx_messages_sender,
    INDEX idx_messages_timestamp
)
```

**tasks**
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    domain TEXT NOT NULL,
    priority INTEGER DEFAULT 3,
    assigned_to TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_by TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    due_date REAL,
    requirements TEXT,  -- JSON
    constraints TEXT,   -- JSON
    result TEXT,
    confidence REAL,
    parent_task_id TEXT,  -- For sub-tasks
    FOREIGN KEY (assigned_to) REFERENCES entities(id),
    FOREIGN KEY (created_by) REFERENCES entities(id),
    FOREIGN KEY (parent_task_id) REFERENCES tasks(id),
    INDEX idx_tasks_status,
    INDEX idx_tasks_assigned_to,
    INDEX idx_tasks_domain,
    INDEX idx_tasks_created_at
)
```

**task_dependencies**
```sql
CREATE TABLE task_dependencies (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (depends_on_task_id) REFERENCES tasks(id),
    UNIQUE(task_id, depends_on_task_id),
    INDEX idx_deps_task_id
)
```

### 5. Key Features

#### Conversation Threading
- Messages grouped by conversation_id
- Context preserved across bot interactions
- Replay capability for debugging
- History for learning

#### Workload Awareness
- Track current bot load
- Distribute work evenly
- Prevent bot overload
- Estimate completion time

#### Error Recovery
- Graceful handling of bot failures
- Automatic retry with backoff
- Escalation to team
- Learning from failures

#### Transparency
- User sees bot collaboration
- Messages can be displayed
- Reasoning is logged
- Decisions are explainable

## Implementation Plan

### Phase 4.1: Coordinator Bot & Message Bus (3-4 days)
1. Create Coordinator bot (inherits SpecialistBot)
2. Implement InterBotBus (messaging system)
3. Add bot discovery and registry
4. Create bot message model
5. Write 10+ tests

### Phase 4.2: Task Orchestration (4-5 days)
1. Implement Task model and storage
2. Create TaskOrchestrator (decomposition, delegation)
3. Implement task state machine
4. Add task dependency management
5. Write 15+ tests

### Phase 4.3: Team Sessions (3-4 days)
1. Implement TeamSession (multi-bot coordination)
2. Create coordination patterns (routing, delegation, discussion)
3. Add conversation threading
4. Implement consensus/voting
5. Write 15+ tests

### Phase 4.4: Integration (2-3 days)
1. Connect to existing AgentLoop
2. Integrate with ContextBuilder for SOUL loading
3. Connect to BotExpertise for routing decisions
4. Add inter-bot learning sharing
5. Write 10+ tests

### Phase 4.5: Documentation (2 days)
1. API documentation
2. Coordination pattern guide
3. Integration examples
4. Troubleshooting guide

**Total**: 2-2.5 weeks

## Code Structure

```
nanobot/
├── coordinator/
│   ├── __init__.py
│   ├── bot.py              (Coordinator bot implementation)
│   ├── bus.py              (InterBotBus - messaging)
│   ├── models.py           (BotMessage, Task, TaskResult)
│   ├── orchestrator.py     (TaskOrchestrator)
│   ├── session.py          (TeamSession)
│   ├── patterns.py         (Coordination patterns)
│   └── state_machine.py    (CoordinatorMode states)
└── memory/
    └── [existing]

tests/
├── phase4/
│   ├── test_coordinator_bot.py
│   ├── test_inter_bot_bus.py
│   ├── test_task_orchestrator.py
│   ├── test_team_session.py
│   └── test_integration.py
```

## Example Usage

### Simple Task Routing
```python
from nanobot.coordinator.session import TeamSession

session = TeamSession(team_members, memory_store, expertise)

# User asks a research question
result = session.handle_request(
    content="What are the latest trends in AI?",
    user_id="user123"
)
# Coordinator routes to researcher
# Researcher responds
# Nanobot presents result to user
```

### Complex Task Decomposition
```python
# User wants to build and launch a feature
result = session.handle_request(
    content="Build and test a login feature for the app",
    user_id="user123"
)
# Coordinator decomposes:
#   - Coder: Implement login backend
#   - Designer: Create UI mockups
#   - Auditor: Review security
#   - Researcher: Check best practices
# All run in parallel
# Results assembled and presented
```

### Team Discussion
```python
# User needs advice on a decision
result = session.handle_discussion(
    topic="Should we migrate to microservices?",
    context={"current_users": 10000, "growth_rate": "20% monthly"}
)
# Each bot shares perspective
# Team deliberates
# Consensus emerges
# Recommendation presented
```

## Success Criteria

- **Functionality**: All 4 coordination patterns working
- **Reliability**: 99%+ task completion rate
- **Performance**: Task completion in <30 seconds
- **Transparency**: All bot conversations logged and explainable
- **Learning**: Cross-pollination happens automatically
- **Tests**: 40+ tests, 80%+ coverage
- **Documentation**: Complete API + examples

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Message queue bottleneck | Low | Medium | Use async/queue with batching |
| State machine complexity | Medium | High | Thorough testing, state diagram |
| Circular dependencies | Low | High | Dependency validation, cycle detection |
| Bot failure during task | Medium | Medium | Automatic retry + escalation |
| Context switching overhead | Low | Low | Message caching, conversation context |

## Future Enhancements

1. **Adaptive Load Balancing** - Dynamically adjust task distribution
2. **Skill Development** - Bots improve expertise over time
3. **Emergent Behaviors** - Bots collaborate without explicit coordination
4. **Multi-workspace Teams** - Coordination across workspaces
5. **Human-in-the-loop** - User intervention at decision points
6. **Reasoning Transparency** - Explain why coordination happened
7. **Conflict Resolution** - Handle disagreement between bots
