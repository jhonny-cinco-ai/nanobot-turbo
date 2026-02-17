# Nanofolks Workflows Index

This directory contains the workflow definitions for Phase 1.5 (Communal Discovery Flow).

## Overview

```
                    ┌─────────────────────────────┐
                    │    USER MESSAGE RECEIVED    │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    INTENT DETECTION         │
                    │    (intent-detection.md)   │
                    └──────────────┬──────────────┘
                                   │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
      ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
      │  CHAT FLOW   │     │ QUICK FLOW   │     │  LIGHT FLOW  │
      │ (chat-flow)  │     │(quick-flow)  │     │(light-flow)  │
      │               │     │               │     │               │
      │ - 0 questions │     │ - 0-1 Qs     │     │ - 1-3 Qs     │
      │ - Conversational│   │ - Direct ans │     │ - Options    │
      │ - 1-2 responses│    │ - 1 bot      │     │ - 2-3 bots   │
      └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │ Escalation Path   │
                          │ (any → FULL)      │
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │   FULL FLOW        │
                          │  (full-flow.md)    │
                          │                    │
                          │ DISCOVERY          │
                          │   → SYNTHESIS      │
                          │   → APPROVAL       │
                          │   → EXECUTION      │
                          │   → REVIEW        │
                          └───────────────────┘
```

## Workflow Comparison

| Aspect | CHAT | QUICK | LIGHT | FULL |
|--------|------|-------|-------|------|
| **When** | Conversational | Advice/Research | Explore/Task | Build |
| **Questions** | 0 | 0-1 | 1-3 | 3+ |
| **Bots** | 1 | 1-2 | 2-3 | 3+ |
| **Output** | Response | Answer | Options | Project Brief |
| **Approval** | No | No | No (options) | Yes |
| **Escalate to FULL** | No | Maybe | Maybe | N/A |
| **Returns to IDLE** | Immediately | Immediately | After selection | After review |

## Intent → Flow Mapping

```
Intent Detection Result
        │
        ├── CHAT ──────────────→ Chat Flow
        │   (confidence < 0.5, no work keywords)
        │
        ├── QUICK ─────────────→ Quick Flow
        │   (ADVICE or RESEARCH intent)
        │   (discovery_depth = "minimal")
        │
        ├── LIGHT ─────────────→ Light Flow
        │   (EXPLORE or TASK intent)
        │   (discovery_depth = "light")
        │
        └── FULL ──────────────→ Full Flow
            (BUILD intent)
            (discovery_depth = "full")
            (or escalated from QUICK/LIGHT)
```

## Workflow Files

| File | Purpose |
|------|---------|
| [intent-detection.md](intent-detection.md) | Entry point - detect intent and route |
| [chat-flow.md](chat-flow.md) | Conversational responses |
| [quick-flow.md](quick-flow.md) | Advice and research requests |
| [light-flow.md](light-flow.md) | Exploration and task completion |
| [full-flow.md](full-flow.md) | Full project building |

## Key Patterns

### Escalation

Any flow can escalate to FULL:

```
User: [in QUICK] "That's great! Can you build it now?"
    ↓
Detected build intent
    ↓
Preserve QUICK context
    ↓
Start FULL with enriched context
```

### Cancellation

Any flow can be cancelled:

```
User: "Actually, never mind / cancel / stop"
    ↓
Save current state (optional resume)
    ↓
Reset to IDLE
    ↓
Acknowledge: "Okay, cancelled!"
```

### Timeout

After 30 minutes of inactivity:

```
No user response in 30 min
    ↓
Save current state
    ↓
Reset to IDLE
    ↓
On next message: "Welcome back! Starting fresh?"
```

## State Management

Each flow maintains state in `.nanofolks/project_states/{room_id}.json`:

```python
@dataclass
class ProjectState:
    phase: str                    # "IDLE", "DISCOVERY", "SYNTHESIS", "APPROVAL", "EXECUTION", "REVIEW"
    flow_type: str               # "CHAT", "QUICK", "LIGHT", "FULL"
    intent: IntentType
    user_goal: str
    discovery_log: List[Dict]    # Questions and answers
    synthesis: Dict              # Generated brief
    approval: Dict               # Approval status
    execution_results: Dict     # Task results
    iteration: int              # How many loops
    created_at: datetime
    updated_at: datetime
```

## Integration with Phase 1

These workflows complement Phase 1 features:

- **DM Rooms** - Bots can use DM rooms for private coordination during execution
- **@all/@crew** - Still work for requesting multiple bot responses
- **Affinity** - Relationship dynamics injected into bot contexts
- **Multi-bot** - Multiple bots can participate in any flow

## Future: Phase 2 Integration

In Phase 2, these workflows will integrate with:

- **Room Sessions** - `.nanofolks/room_sessions/{room_id}.json`
- **Cross-Channel** - Same flow works across Telegram, Slack, CLI
- **Task Rooms** - Long executions get persistent rooms
