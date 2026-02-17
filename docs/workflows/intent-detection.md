# Intent Detection Workflow

<purpose>
Detect user intent from incoming message and route to the appropriate flow (CHAT, QUICK, LIGHT, or FULL). This is the entry point for all user messages in Phase 1.5.
</purpose>

<context>
- Room context: Current room, participants, conversation history
- User: The human user sending the message
- Bots: Available specialist bots (leader, researcher, coder, creative, social, auditor)
- State: Current project state if in-progress flow exists
</context>

<philosophy>
**Match verbosity to intent.** A quick question deserves a quick response. A complex project deserves structured discovery. Don't over-engineer simple requests.

**Default to simplicity.** When in doubt, start light. User can always escalate if they want more depth.
</philosophy>

<scope_guardrail>
**Only route - don't execute.** Intent detection identifies the flow, it doesn't perform the work. Execution happens in the routed flow.

**Don't guess intent from single words.** Use keyword patterns + context. A message containing "build" might be CHAT if it's "I'm not going to build that" vs FULL if "build me a website".
</scope_guardrail>

<process>

<step name="check_active_flow">
Check if there's an active flow in progress.

```python
state = ProjectStateManager(room_id).get_state()

if state.phase != ProjectPhase.IDLE:
    # There's an active flow - route to its next step
    return route_to_active_flow(state)
```

**If active flow exists:** Continue to `route_to_active_flow`

**If IDLE:** Continue to `detect_intent`
</step>

<step name="detect_intent">
Analyze user message to determine intent type.

```python
intent_detector = IntentDetector()
intent = intent_detector.detect(message)
```

**Intent Types:**

| Intent | Keywords | Flow |
|--------|----------|------|
| BUILD | build, create, make, develop | FULL |
| EXPLORE | can i, could i, wonder if, ways to, make money | LIGHT |
| ADVICE | how do i, how can i, tips for, help me | QUICK |
| RESEARCH | research, what are, tell me about, learn about | QUICK |
| TASK | write, send, schedule, calculate, translate | LIGHT |
| CHAT | what do you think, interesting, nice, cool | CHAT |

**Algorithm:**
1. Score each intent type by keyword matches
2. Apply bonuses for exact phrase matches
3. Extract entities (interests, people, topics)
4. Return highest-scoring intent with confidence

**Output:**
```python
Intent(
    type: IntentType,
    confidence: float,  # 0.0 - 1.0
    entities: Dict,    # Extracted info
    suggested_bots: List[str],
    discovery_depth: str  # "none", "minimal", "light", "full"
)
```
</step>

<step name="route_to_flow">
Map detected intent to flow type.

```python
def route_to_flow(intent: Intent) -> str:
    depth = intent.discovery_depth
    
    if depth == "none":
        return "CHAT"
    elif depth == "minimal":
        return "QUICK"
    elif depth == "light":
        return "LIGHT"
    else:  # "full"
        return "FULL"
```
</step>

<step name="execute_flow">
Launch the appropriate flow with context.

```python
if flow == "CHAT":
    return await ChatFlow().execute(message, intent)
elif flow == "QUICK":
    return await QuickFlow().execute(message, intent)
elif flow == "LIGHT":
    return await LightFlow().execute(message, intent)
elif flow == "FULL":
    return await FullFlow().execute(message, intent)
```
</step>

<step name="handle_escalation">
Check for escalation signals after QUICK/LIGHT completion.

**Escalation triggers:**
- "Let's do option X" - wants to build on result
- "Can you build that?"
- "I want to create..."
- "How would I actually start this?"

```python
if is_escalation(message):
    # Convert to FULL flow
    return await FullFlow().execute(message, intent_updated)
```

**If escalation detected:**
- Preserve previous flow results as context
- Start FULL flow with enriched context
- User: "I see you want to build on that! Let me ask a few questions..."
</step>

<step name="handle_cancellation">
Check for cancellation keywords at any point.

**Cancel keywords:**
- cancel, stop, never mind, forget it, abort, quit

```python
if is_cancellation(message):
    ProjectStateManager(room_id).reset_to_idle()
    return OutboundMessage(
        content="Okay, cancelled. Let me know if you need anything else.",
        metadata={"cancelled": True}
    )
```

**On cancellation:**
1. Save current state to history (for potential resume)
2. Reset to IDLE
3. Acknowledge cancellation
</step>

</process>

<success_criteria>
- [ ] Active flow detection works
- [ ] Intent scoring produces correct type
- [ ] Confidence threshold applied appropriately
- [ ] Entity extraction captures interests/topics
- [ ] Flow routing matches discovery_depth
- [ ] Escalation signals detected
- [ ] Cancellation handled gracefully
- [ ] State persists across messages
</success_criteria>

<output_state>
```python
@dataclass
class IntentDetectionResult:
    flow: str                    # "CHAT" | "QUICK" | "LIGHT" | "FULL"
    intent: IntentType
    confidence: float
    suggested_bots: List[str]
    escalation_likely: bool      # User might want to build later
```
</output_state>

<example_traces>

**Example 1: CHAT**
```
User: "Oh that's really interesting! Tell me more"

→ Intent: CHAT (confidence: 0.9)
→ Flow: CHAT
→ Action: Leader responds conversationally
→ Result: Done (back to IDLE)
```

**Example 2: QUICK**
```
User: "How do I organize weekly groceries?"

→ Intent: ADVICE (confidence: 0.85)
→ Discovery depth: minimal
→ Flow: QUICK
→ Action: Ask 1 clarifying question → Provide advice
→ Result: Done (back to IDLE)
```

**Example 3: LIGHT → Escalation**
```
User: "Can I make money from gardening and photography?"

→ Intent: EXPLORE (confidence: 0.9)
→ Discovery depth: light
→ Flow: LIGHT
→ Action: 2-3 questions → Present 5 options

User: "I like option 3, can you build it?"

→ Escalation detected!
→ Flow: FULL (with LIGHT context)
→ Action: Full discovery → synthesis → approval → execution
```

**Example 4: Active Flow Interruption**
```
User: [in middle of FULL flow] "Actually never mind, cancel"

→ Cancellation detected
→ Action: Save state, reset to IDLE
→ Result: Back to IDLE
```

</example_traces>
