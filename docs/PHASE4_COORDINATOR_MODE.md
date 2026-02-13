# Phase 4: Coordinator Mode - Multi-Agent Orchestration

## Overview

Phase 4 implements autonomous multi-bot orchestration enabling the team to work together on complex tasks. The Coordinator bot (nanobot) manages inter-bot communication, delegates work to specialists, and synthesizes results.

## Core Components

### 1. Message Bus (InterBotBus)
Central message routing system for bot-to-bot communication.

```python
from nanobot.coordinator import InterBotBus, BotMessage, MessageType

# Create and initialize bus
bus = InterBotBus()

# Register bots
bus.register_bot("researcher", "Navigator", "research")
bus.register_bot("coder", "Architect", "development")

# Send direct message
message = BotMessage(
    sender_id="researcher",
    recipient_id="coder",
    message_type=MessageType.REQUEST,
    content="Can you implement the data layer?"
)
msg_id = bus.send_message(message)

# Broadcast to team
broadcast = BotMessage(
    sender_id="researcher",
    recipient_id="team",
    message_type=MessageType.BROADCAST,
    content="Status update: Analysis complete"
)
bus.send_message(broadcast)

# Check inbox
inbox = bus.get_inbox("coder")
for msg in inbox:
    print(f"{msg.sender_id}: {msg.content}")
```

**Key Features:**
- Direct messaging between bots
- Team broadcasts
- Conversation threading
- Message history and search
- Thread-safe operations

### 2. Task Model
Represents units of work assigned to bots.

```python
from nanobot.coordinator import Task, TaskStatus, TaskPriority

# Create task
task = Task(
    title="Implement user authentication",
    description="Add JWT-based auth with refresh tokens",
    domain="development",
    assigned_to="coder",
    priority=TaskPriority.HIGH,
    requirements=["JWT support", "PostgreSQL"],
    due_date=datetime.now() + timedelta(days=3)
)

# Track lifecycle
task.mark_started()
# ... bot works on task ...
task.mark_completed(
    result="Auth system implemented and tested",
    confidence=0.95
)

# Query status
if task.is_overdue():
    print("Task is overdue!")

elapsed = task.time_elapsed()  # seconds
```

**Task Statuses:**
- PENDING: Waiting to be assigned
- ASSIGNED: Assigned to a bot
- IN_PROGRESS: Bot is working
- BLOCKED: Waiting for dependencies
- COMPLETED: Successfully done
- FAILED: Could not complete
- CANCELLED: Cancelled by user/system

### 3. Coordinator Bot
Orchestrates team collaboration and task delegation.

```python
from nanobot.coordinator import CoordinatorBot, InterBotBus
from nanobot.memory.bot_memory import BotExpertise
from nanobot.bots.definitions import NANOBOT_ROLE

# Setup
bus = InterBotBus()
expertise = BotExpertise(memory_store)
coordinator = CoordinatorBot(NANOBOT_ROLE, bus, expertise)

# Register team members
bus.register_bot("researcher", "Navigator", "research")
bus.register_bot("coder", "Architect", "development")
bus.register_bot("auditor", "Reviewer", "quality")

# Analyze request
analysis = coordinator.analyze_request(
    "Build and test a feature to track user engagement",
    user_id="user123"
)
# Returns: {
#     "complexity": "high",
#     "domains": ["development", "quality"],
#     "requires_team": True,
#     "recommended_approach": "decompose_and_delegate"
# }

# Find best bot for a task
best_bot = coordinator.find_best_bot(
    domain="development",
    available_bots=["coder", "researcher"]
)
# Returns: "coder" (based on expertise scores)

# Create and delegate task
task = coordinator.create_task(
    title="Implement engagement tracking",
    description="Add features to track user actions",
    domain="development",
    assigned_to="coder",
    requirements=["Real-time updates", "Analytics"],
    due_date=datetime.now() + timedelta(days=5)
)

# Handle results
coordinator.handle_task_result(
    task_id=task.id,
    result="Feature implemented with 95% test coverage",
    confidence=0.95,
    learnings=["WebSocket optimization critical"]
)

# Get team status
print(coordinator.get_team_status())
```

**Coordinator Responsibilities:**
- Analyze user requests
- Determine complexity and domain(s)
- Select appropriate bots
- Decompose into tasks
- Delegate to specialists
- Monitor progress
- Assemble results
- Facilitate team decisions

## Coordination Patterns

### Pattern A: Simple Routing
Route to single specialist based on domain.

```python
# User: "What's the latest in AI?"
analysis = coordinator.analyze_request(message, user_id)
# analysis["domains"] = ["research"]
# analysis["complexity"] = "medium"
# analysis["recommended_approach"] = "route_to_specialist"

best_bot = coordinator.find_best_bot("research", team_bots)
task = coordinator.create_task(
    title="Research AI trends",
    domain="research",
    assigned_to=best_bot
)
```

### Pattern B: Sequential Workflow
Decompose into sequential steps, each assigned to best specialist.

```python
# User: "Build a login system with security review"
# Decompose:
tasks = []

# Step 1: Architect design
design_task = coordinator.create_task(
    title="Design auth architecture",
    domain="design",
    assigned_to="designer",
    parent_task_id=None
)
tasks.append(design_task)

# Step 2: Implement (depends on design)
impl_task = coordinator.create_task(
    title="Implement auth system",
    domain="development",
    assigned_to="coder",
    parent_task_id=design_task.id
)
tasks.append(impl_task)

# Step 3: Security review (depends on implementation)
review_task = coordinator.create_task(
    title="Security audit",
    domain="quality",
    assigned_to="auditor",
    parent_task_id=impl_task.id
)
tasks.append(review_task)
```

### Pattern C: Parallel Execution
Execute independent tasks in parallel.

```python
# User: "Analyze market, design UI, and spec database"
# All can run in parallel

research_task = coordinator.create_task(
    title="Market analysis",
    domain="research",
    assigned_to="researcher"
)

design_task = coordinator.create_task(
    title="UI mockups",
    domain="design",
    assigned_to="designer"
)

dev_task = coordinator.create_task(
    title="Database schema",
    domain="development",
    assigned_to="coder"
)

# Wait for all to complete (in real system)
# Assemble results
```

### Pattern D: Team Discussion
Get perspectives from multiple bots.

```python
topic = "Should we migrate to microservices?"
context = {
    "current_users": 100000,
    "growth_rate": "50% yearly"
}

message = BotMessage(
    sender_id="nanobot",
    recipient_id="team",
    message_type=MessageType.DISCUSSION,
    content=f"Discussion: {topic}\nContext: {context}",
    context={"subject": topic}
)
bus.send_message(message)

# Each bot responds with perspective
# Nanobot synthesizes consensus
```

## Usage Examples

### Example 1: Simple Research Task

```python
# User asks: "What are the latest trends in AI?"
request = "What are the latest trends in AI?"

# Analyze
analysis = coordinator.analyze_request(request, "user123")
# -> domains: ["research"], complexity: "medium", route_to_specialist

# Create task
task = coordinator.create_task(
    title="Research AI trends",
    description=request,
    domain="research",
    assigned_to="researcher"
)

# Researcher works on it...

# Handle result
coordinator.handle_task_result(
    task_id=task.id,
    result="Key trends: LLMs, multimodal AI, reasoning...",
    confidence=0.9
)

# Present to user
print(task.result)
```

### Example 2: Complex Multi-Bot Workflow

```python
request = "Build and launch a mobile app for fitness tracking"

# Analysis
analysis = coordinator.analyze_request(request, "user123")
# -> domains: ["development", "design", "quality"]
# -> complexity: "high"
# -> requires_team: True
# -> approach: "parallel_delegation"

# Decompose into parallel tasks
design_task = coordinator.create_task(
    title="Design mobile app UI/UX",
    domain="design",
    assigned_to="designer",
    requirements=["iOS + Android", "Offline support"]
)

dev_task = coordinator.create_task(
    title="Implement backend API",
    domain="development",
    assigned_to="coder",
    requirements=["Real-time sync", "PostgreSQL"]
)

research_task = coordinator.create_task(
    title="Research fitness tracking best practices",
    domain="research",
    assigned_to="researcher",
    requirements=["Battery optimization", "Data privacy"]
)

# All three work in parallel...
# Collect results
design_result = coordinator.handle_task_result(design_task.id, design.result)
dev_result = coordinator.handle_task_result(dev_task.id, dev.result)
research_result = coordinator.handle_task_result(research_task.id, research.result)

# Coordinator integrates: design + API + best practices
integrated = f"""
Design: {design_result}
API: {dev_result}
Best Practices: {research_result}
"""

# QA Task
qa_task = coordinator.create_task(
    title="QA testing",
    domain="quality",
    assigned_to="auditor",
    requirements=["Full test coverage", "Performance benchmarks"]
)

# Final result
coordinator.handle_task_result(qa_task.id, qa_result)
```

### Example 3: Team Decision Making

```python
# Need consensus on architectural decision
question = "Should we use microservices or monolith?"
context = {
    "team_size": 10,
    "scaling_needs": "High",
    "deployment_frequency": "Daily"
}

# Frame discussion
msg = BotMessage(
    sender_id="nanobot",
    recipient_id="team",
    message_type=MessageType.DISCUSSION,
    content=f"Architectural decision: {question}\nContext: {context}",
    context={"subject": question}
)
bus.send_message(msg)

# Get responses
coder_response = "Microservices - better for scaling and parallel development"
designer_response = "Monolith simpler initially, but microservices allow better separation"
auditor_response = "Microservices have security/audit benefits"

# Synthesize
consensus = "Team consensus: Microservices architecture, start with 3 core services"
decision_task = coordinator.create_task(
    title="Implement microservices",
    description=consensus,
    domain="development",
    assigned_to="coder"
)
```

## Database Schema

### New Tables

**bot_messages**
- id, sender_id, recipient_id, message_type, content
- conversation_id, context, timestamp
- response_to_id (for threading)

**tasks**
- id, title, description, domain
- assigned_to, created_by, status
- created_at, started_at, completed_at, due_date
- requirements, constraints (JSON)
- result, confidence
- parent_task_id (for sub-tasks)

**task_dependencies**
- id, task_id, depends_on_task_id
- Enforces task ordering

## API Reference

### InterBotBus

```python
bus = InterBotBus(max_message_history=1000)

# Bot management
bus.register_bot(bot_id, bot_name, domain)
bots = bus.list_bots()

# Messaging
msg_id = bus.send_message(message)
inbox = bus.get_inbox(bot_id)
bus.clear_inbox(bot_id)

# Conversations
context = bus.get_conversation(conversation_id)
conversations = bus.get_conversations_for_bot(bot_id)
summary = bus.get_conversation_summary(conversation_id)

# Search and stats
results = bus.search_messages(query, sender_id, message_type)
stats = bus.get_statistics()
```

### CoordinatorBot

```python
coordinator = CoordinatorBot(role_card, bus, expertise)

# Analysis
analysis = coordinator.analyze_request(content, user_id)

# Bot selection
best_bot = coordinator.find_best_bot(domain, available_bots)

# Task management
task = coordinator.create_task(
    title, description, domain, assigned_to,
    requirements, due_date, parent_task_id
)
coordinator.handle_task_result(task_id, result, confidence, learnings)
coordinator.handle_task_failure(task_id, error, recovery_suggestion)

# Team coordination
status = coordinator.get_team_status()
msg_id = coordinator.broadcast_to_team(content, message_type)
```

## Performance Characteristics

- **Message latency**: <10ms (in-memory bus)
- **Task creation**: <50ms
- **Search index**: Full text search across message history
- **Scalability**: Tested with 100+ messages, 20+ tasks in flight
- **Memory**: ~1KB per message, ~2KB per task

## Testing

Run all Phase 4 tests:

```bash
pytest tests/phase4/test_coordinator.py -v
```

Test coverage:
- **BotMessage**: 2 tests
- **Task**: 4 tests
- **InterBotBus**: 6 tests
- **CoordinatorBot**: 8 tests

**Total**: 20 tests, all passing

## Integration Points

### With Memory System
- Load bot expertise for selection
- Store learnings from tasks
- Cross-pollinate insights

### With Agent Loop
- Route user requests to coordinator
- Display bot conversations
- Log coordination events

### With SOUL System
- Load bot personalities
- Inject into messages
- Customize coordination style

## Future Enhancements

1. **Adaptive Scheduling** - Distribute work based on bot load
2. **Dynamic Task Decomposition** - AI-driven workflow generation
3. **Conflict Resolution** - Handle disagreement between bots
4. **Emergent Behaviors** - Self-organizing team
5. **Human Oversight** - Escalation to user for critical decisions
6. **Reasoning Transparency** - Explain coordination decisions
7. **Learning from Coordination** - Improve routing over time
8. **Multi-workspace Teams** - Coordinate across workspaces

## Statistics

- **Models**: 8 dataclasses (Message, Task, Dependency, etc.)
- **InterBotBus**: 400+ lines
- **CoordinatorBot**: 350+ lines
- **Tests**: 20 comprehensive tests
- **Test Coverage**: 80%+
- **Message Types**: 8 (request, response, discussion, etc.)
- **Task Statuses**: 7 states with transitions
