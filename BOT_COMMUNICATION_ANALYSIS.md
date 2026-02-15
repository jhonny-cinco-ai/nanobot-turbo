# Inter-Bot Communication & Information Handoff Analysis

## Overview

Nanobot has **three mechanisms** for bots to pass work and information to each other:

1. **Invoke Tool** - Async delegation (fire-and-forget with callback)
2. **Room/Shared Context** - Persistent knowledge graph for multi-agent rooms
3. **Message Tool** - Direct messaging between bots

**Current Reality**: The system works but has significant gaps.

---

## 1. Invoke Tool - Task Delegation

### How It Works

```
Bot A (Leader)
    ↓
[decide this task needs Bot B]
    ↓
invoke(bot="researcher", task="Research X")
    ↓
InvokeTool.execute()
    ↓
BotInvoker.invoke()
    ├─ Creates asyncio task (fire-and-forget)
    ├─ Launches Bot B in background
    └─ Returns immediately: "@researcher is on the task..."
    ↓
[Bot A continues with next task]
    
[Meanwhile, Bot B runs in background]
    ├─ Gets system prompt (SOUL.md + domain context)
    ├─ Receives full task instruction
    ├─ Processes through LLM
    ├─ Generates result
    └─ Announces result via system message
    ↓
[System message injected into original conversation]
    ↓
Bot A receives: "[Bot @researcher completed] Task: Research X. Result: ..."
```

### Code Flow

```python
# Bot A invokes
invoke(bot="coder", task="Write function to parse CSV")
    ↓
# BotInvoker._invoke_async()
asyncio.create_task(_process_invocation(...))
    ├─ Builds system prompt for coder (SOUL.md)
    ├─ Calls LLM: system_prompt + task
    ├─ Gets response
    └─ Announces result
    ↓
# Result comes back via system message
_announce_result()
    ↓
InboundMessage(
    channel="system",
    sender_id="invoke:coder",
    chat_id="cli:direct",
    content="[Bot @coder completed]\nTask: ...\nResult: ..."
)
```

### Characteristics

✅ **Async** - Doesn't block caller  
✅ **Background execution** - Can run in parallel  
✅ **Result callback** - Results come back automatically  
✅ **Simple API** - Just provide bot name and task  

❌ **No context passing** - Only plain string task description  
❌ **No file handoff** - Results are text only  
❌ **No progress tracking** - Fire-and-forget model  
❌ **No output validation** - No way to confirm what was produced  
❌ **Single string return** - All output is one message  
❌ **No structured output** - Can't extract specific data from result  

---

## 2. Room & Shared Context - Persistent Knowledge

### Structure

```python
Room:
    shared_context: SharedContext
        ├─ events: List[Dict]          # Timeline of what happened
        ├─ entities: Dict[str, Dict]   # Knowledge graph (people, concepts)
        ├─ facts: List[Dict]           # Verified truths with confidence
        └─ artifact_chain: List[Dict]  # Structured handoffs (currently unused)
    
    history: List[Message]             # All messages in room
    participants: List[str]            # Which bots are in room
    type: RoomType                     # OPEN, PROJECT, DIRECT, COORDINATION
```

### Example: Multi-Bot Room Collaboration

```
Scenario: Research → Analyze → Report workflow

1. Create room
room = Room(
    id="project-alpha",
    type=RoomType.PROJECT,
    participants=["leader", "researcher", "coder", "auditor"]
)

2. Researcher publishes findings
room.add_entity("competitor-x", {
    "name": "CompetitorX Inc",
    "pricing": "$99/month",
    "features": ["A", "B", "C"],
    "market_share": 0.25
})

3. Coder sees knowledge graph
context = room.shared_context
competitors = context.entities
# Can now build pricing comparison UI

4. Auditor verifies facts
room.add_fact(
    subject="CompetitorX",
    predicate="pricing_valid",
    obj="true",
    confidence=0.95
)

5. All bots see the artifact_chain
for artifact in room.shared_context.artifact_chain:
    # Process handoff
```

### Characteristics

✅ **Persistent memory** - Survives across executions  
✅ **Structured data** - Entities, facts, events  
✅ **Multi-bot visibility** - All participants see same context  
✅ **Knowledge graph** - Can model relationships  
✅ **Confidence scoring** - Track certainty of facts  

❌ **Not actively used** - Code exists but isn't wired up  
❌ **artifact_chain empty** - Handoff mechanism defined but not implemented  
❌ **No file artifacts** - Can't point to outputs (research.pdf, code.py)  
❌ **No automatic injection** - Context not fed to LLM prompts  
❌ **No query interface** - Hard to search/filter entities  
❌ **Manual management** - Bots must explicitly add things  

---

## 3. Message Tool - Direct Bot-to-Bot Communication

### How It Works

```python
# Bot A sends message
message(
    content="Hi @researcher, can you look at this?",
    channel="slack",
    chat_id="project-alpha"
)

# Message goes to user channel
# Other bots don't receive it automatically
# It's primarily user-facing, not bot-to-bot
```

### Current Usage

- ✅ Send notifications to users
- ✅ Report progress
- ✅ Ask clarifying questions
- ❌ Not designed for bot-to-bot handoff
- ❌ No structured message format
- ❌ No reply/acknowledgment mechanism

---

## What's Missing: A Real Example

### Desired Workflow: Research → Coder → Auditor

```
User: "Find 3 competitors, analyze their APIs, then validate the findings"

Current System:
    Leader → invoke(researcher, "Find 3 competitors")
        ↓ [Researcher completes]
        ↓ Announces: "Found CompetitorX, CompetitorY, CompetitorZ"
        ↓
    Leader reads text result, extracts competitor info manually
        ↓
    Leader → invoke(coder, "Analyze APIs of these competitors: ...")
        ↓ [Coder completes]
        ↓ Announces: "Compared 3 APIs, found differences..."
        ↓
    Leader reads text result, summarizes for auditor
        ↓
    Leader → invoke(auditor, "Validate these findings: ...")
        ↓ Done

Problems:
❌ Leader must act as intermediary
❌ Data passed as strings (copy-paste from messages)
❌ No structured handoff (API docs as files, not in message)
❌ No way to say "here are 3 JSON objects for next step"
❌ Auditor validates text, not structured data
❌ If auditor finds issue, loop back to coder requires manual rework


Better System (What's Needed):
    
    Researcher completes → writes "competitors.json"
    ├─ artifact_chain stores: {
    │       "producer": "researcher",
    │       "outputs": ["competitors.json"],
    │       "metadata": {...}
    │   }
    └─ Signals: "Done, outputs ready"
        ↓
    Coder invoked with artifact reference
    ├─ "Use the competitor data from researcher's competitors.json"
    ├─ Reads: competitors.json
    ├─ Analyzes APIs
    └─ Writes: "api-comparison.json"
        ├─ artifact_chain stores: {
        │       "producer": "coder",
        │       "inputs": ["competitors.json"],
        │       "outputs": ["api-comparison.json"],
        │   }
        └─ Signals: "Done, outputs ready"
            ↓
        Auditor invoked with artifact references
        ├─ "Validate the data in api-comparison.json using competitors.json"
        ├─ Reads both files
        ├─ Validates
        └─ Returns validation results
            ├─ artifact_chain: {
            │       "producer": "auditor",
            │       "inputs": ["api-comparison.json", "competitors.json"],
            │       "validation": {"status": "PASS", "issues": [...]}
            │   }
            └─ Done
                ↓
        User gets final result with full artifact chain visible
```

---

## Current Implementation Gaps

### Gap 1: No File-Based Handoff

```python
# Invoke returns string result
result = await invoker.invoke(
    bot_name="researcher",
    task="Find competitor info"
)

# Result is:
"I found CompetitorX Inc, CompetitorY Corp, CompetitorZ LLC.
CompetitorX Inc specializes in SaaS with pricing at $99/month..."

# Problems:
❌ Structured data buried in text
❌ Downstream bot must parse/extract
❌ No file references (where was data saved?)
❌ No way to pass multiple outputs
```

### Gap 2: No Artifact Chain Tracking

```python
# artifact_chain exists but is never used
room.shared_context.artifact_chain
# Always empty []

# Should contain:
[
    {
        "step": 1,
        "producer": "researcher",
        "task": "Research competitors",
        "outputs": ["competitors.json", "market-analysis.md"],
        "timestamp": "2025-02-15T10:00:00Z",
        "status": "DONE"
    },
    {
        "step": 2,
        "producer": "coder",
        "task": "Analyze APIs",
        "inputs": ["competitors.json"],
        "outputs": ["api-comparison.json"],
        "timestamp": "2025-02-15T10:15:00Z",
        "status": "DONE"
    }
]
```

### Gap 3: No Structured Output Specification

```python
# Invoke has no way to specify expected outputs
result = await invoker.invoke(
    bot_name="researcher",
    task="Find competitors"
    # No: expected_outputs=["competitors.json"]
    # No: output_format="json"
    # No: output_schema={...}
)

# Result is whatever bot decides (unstructured text)
```

### Gap 4: No Output Validation

```python
# No way to confirm outputs exist or are correct

# What's needed:
invoke(
    bot="researcher",
    task="Find competitors",
    expected_outputs=[
        {
            "path": "competitors.json",
            "validator": "json_schema",
            "schema": {...}
        }
    ],
    on_validation_failure="retry_with_prompt"
)
```

### Gap 5: No Progress Updates

```python
# Fire-and-forget model
# No intermediate updates
# User doesn't know if bot is:
# - Still working
# - Stuck
# - Completed step 1 of 3

# What's needed:
# Ability to emit progress:
# "Step 1/3: Researching CompetitorX..." 
# "Step 2/3: Analyzing API..."
```

### Gap 6: No Result Structuring

```python
# All results are text, no structured format

# Better:
result = InvocationResult(
    status="DONE",
    primary_output="Here's the summary...",
    artifacts=[
        Artifact(
            path="competitors.json",
            type="data",
            size_bytes=2048,
            content_hash="sha256:abc123"
        ),
        Artifact(
            path="market-analysis.md",
            type="document",
            size_bytes=8192
        )
    ],
    metadata={
        "execution_time_seconds": 45,
        "tokens_used": 2500,
        "model": "claude-3-sonnet"
    }
)
```

---

## Architecture Comparison

### Current (Text-Based Delegation)

```
┌─────────────────────────────────────────────────────┐
│ Bot A invokes: "research competitors"               │
└────────────────┬──────────────────────────────────┘
                 │
         ┌───────▼────────┐
         │ Bot B (text)   │
         │ Generates text │
         │ about companies│
         └───────┬────────┘
                 │
    ┌────────────▼────────────┐
    │ Result: plain text      │
    │ "CompX: $99/mo..."      │
    │ "CompY: $199/mo..."     │
    └────────────┬────────────┘
                 │
         ┌───────▼──────────┐
         │ Bot A parses it  │
         │ Extracts data    │
         │ Invokes Bot C    │
         └───────┬──────────┘
                 │
         ┌───────▼────────┐
         │ Bot C (text)   │
         │ But needs      │
         │ structured data│
         └────────────────┘
```

### What's Needed (File-Based Handoff)

```
┌──────────────────────────────────────────────────────┐
│ Bot A invokes: "research competitors"                │
│ expected_outputs: ["competitors.json"]               │
└────────────────┬───────────────────────────────────┘
                 │
         ┌───────▼────────────┐
         │ Bot B (structured) │
         │ Generates JSON     │
         │ Writes file        │
         └───────┬────────────┘
                 │
    ┌────────────▼─────────────┐
    │ Artifact created:        │
    │ competitors.json (valid) │
    │ artifact_chain updated   │
    └────────────┬─────────────┘
                 │
         ┌───────▼──────────────────┐
         │ Bot A sees artifact      │
         │ Knows: "competitors.json"│
         │ Invokes Bot C with ref   │
         └───────┬──────────────────┘
                 │
         ┌───────▼─────────────────┐
         │ Bot C (structured)      │
         │ Reads JSON directly     │
         │ Works with data         │
         │ Validates schema        │
         └─────────────────────────┘
```

---

## How to Fix

### Phase 1: Structured Handoff (1 week)

```python
# 1. Extend invoke to support outputs
@dataclass
class InvocationRequest:
    bot: str
    task: str
    context: Optional[str] = None
    expected_outputs: List[OutputSpec] = []  # NEW
    input_artifacts: List[str] = []          # NEW
    output_format: str = "text"              # NEW

@dataclass
class OutputSpec:
    path: str                    # Where to find it
    type: str                    # "json", "csv", "markdown"
    validator: Optional[str] = None
    required: bool = True

# 2. Extend InvocationResult
@dataclass
class InvocationResult:
    status: str                      # "DONE", "FAILED", "PARTIAL"
    summary: str                     # Text summary for user
    artifacts: List[Artifact] = []   # NEW: Files produced
    metadata: dict = field(default_factory=dict)

@dataclass
class Artifact:
    path: str
    type: str
    size_bytes: int
    content_hash: str
    created_at: datetime
```

### Phase 2: Artifact Chain (1 week)

```python
# Wire up the artifact_chain that already exists in Room

# When bot completes:
def mark_step_complete(
    room: Room,
    producer_bot: str,
    task: str,
    outputs: List[Artifact],
    inputs: List[str] = []
):
    room.shared_context.artifact_chain.append({
        "step": len(room.shared_context.artifact_chain) + 1,
        "producer": producer_bot,
        "task": task,
        "inputs": inputs,
        "outputs": [{"path": a.path, "type": a.type} for a in outputs],
        "timestamp": datetime.now().isoformat(),
        "status": "DONE"
    })
```

### Phase 3: Context Injection (3 days)

```python
# When building system prompt for invoked bot, include relevant artifacts

def build_system_prompt_with_artifacts(
    bot_name: str,
    room: Room,
    task: str
) -> str:
    system = get_bot_soul(bot_name)
    
    # Add artifact context
    recent_artifacts = [a for a in room.shared_context.artifact_chain[-5:]]
    
    if recent_artifacts:
        system += """
You have access to outputs from previous team members:
"""
        for artifact_entry in recent_artifacts:
            system += f"""
- {artifact_entry['producer']} produced:
  {', '.join(artifact_entry['outputs'])}
  Available at: {workspace}/artifacts/
"""
    
    return system
```

### Phase 4: Output Validation (2 days)

```python
# Add validation to bot_invoker

async def _validate_outputs(
    outputs: List[Artifact],
    expected: List[OutputSpec]
) -> bool:
    missing = []
    for spec in expected:
        if not any(a.path == spec.path for a in outputs):
            missing.append(spec.path)
    
    if missing:
        # Trigger retry with prompt
        return False
    return True
```

---

## Recommendation

**Don't implement Step Sequencer.** Instead, **fix the handoff system that already exists.**

Current state:
- ✅ Invoke tool works
- ✅ Room model exists
- ✅ artifact_chain is defined
- ❌ Just not connected together

**Implementation priority**:

1. **Structured outputs** (2 days) - Let bots declare what they produce
2. **Artifact tracking** (2 days) - Wire up artifact_chain
3. **Context injection** (1 day) - Give downstream bots the artifacts
4. **Output validation** (1 day) - Confirm outputs exist
5. **Progress updates** (1 day) - Stream intermediate messages

**Total: 1 week** to get proper file-based handoff working.

This gives you multi-step workflows (like Step Sequencer) but **without adding complexity**, because it's just wiring up what's already there.

---

## Code Changes Needed

### 1. Extend InvokeTool parameters

```python
@property
def parameters(self) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "bot": {...},
            "task": {...},
            "expected_outputs": {  # NEW
                "type": "array",
                "items": {"type": "string"},
                "description": "Expected output files (e.g., ['results.json'])"
            },
            "input_artifacts": {  # NEW
                "type": "array",
                "items": {"type": "string"},
                "description": "Input files to use (e.g., ['data.json'])"
            }
        }
    }
```

### 2. Update BotInvoker._announce_result()

```python
# Include artifact list in announcement
announce_content = f"""[Bot @{bot_name} completed]

Task: {task}

Outputs:
{format_artifacts(artifacts)}

Result:
{result}
"""
```

### 3. Connect room context

```python
# In _build_bot_system_prompt(), inject artifact_chain context
if room and room.shared_context.artifact_chain:
    system_prompt += "\nPrevious team outputs:\n"
    for entry in room.shared_context.artifact_chain:
        system_prompt += f"- {entry['producer']}: {entry['outputs']}\n"
```

---

## Summary

**Current system**: Async delegation with text results  
**Missing**: File handoff, artifact tracking, output validation  
**Solution**: Wire up existing Room/artifact_chain infrastructure  
**Effort**: 1 week  
**Benefit**: Multi-step workflows without Step Sequencer complexity  

The pieces are already there. Just need to connect them.
