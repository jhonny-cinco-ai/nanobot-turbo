# Full Flow Workflow

<purpose>
Handle BUILD intent - full structured discovery flow: Discovery → Synthesis → Approval → Execution → Review. Used when user wants to create something concrete.
</purpose>

<context>
- Intent: BUILD (detected in intent-detection or escalated from LIGHT)
- User goal: What they want to build
- Previous context: If escalated, exploration results from LIGHT
</context>

<philosophy>
**Collaborative clarification.** Multiple bots ask questions in the room. User sees the crew working together to understand their vision.

**User approves before building.** No work happens until user says "yes, that's what I want." Prevents wasted effort on wrong thing.
</philosophy>

<scope_guardrail>
**Minimum 2 bots must participate.** Shows "crew" not single assistant.

**Synthesis must be approved.** If user rejects synthesis, loop back to discovery with feedback.
</scope_guardrail>

<process>

<step name="initialize_project>
Create project state for FULL flow.

```python
state_manager = ProjectStateManager(room_id)
state_manager.start_full_flow(
    user_goal=message,
    escalated_from=context.get('origin'),  # "LIGHT" or None
    previous_context=context.get('exploration_result')
)

# Escalated context adds depth
if escalated_from == "LIGHT":
    # Pre-populate some answers from exploration
    state_manager.add_discovery_entry(
        bot="user",
        content=f"From exploration: {previous_context}"
    )
```
</step>

<step name="discovery_phase">
**Phase 1: DISCOVERY**

Multiple bots ask clarifying questions in rounds.

```python
# Select bots to participate
bots = select_relevant_bots(user_goal)

# Round 1: Bot 1 asks
bot_1 = bots[0]
question_1 = generate_question(
    goal=user_goal,
    bot_role=bot_1,
    round=1,
    existing_questions=[]
)
```

**Question guidelines:**
- One question per bot response
- Specific to bot's domain
- Not yes/no - should reveal preferences

```python
# Log question
state_manager.log_question(bot=bot_1, question=question_1)

# Present to user
response = f"@{bot_1}: {question_1}"
```

**After user responds:**
- Log answer
- Check if discovery complete

```python
# Discovery complete when:
# - 2+ bots have asked questions
# - 3+ questions total
# - Current bot gave substantive info (not just Qs)

if is_discovery_complete(state):
    return transition_to_synthesis()
else:
    return next_discovery_question()
```
</step>

<step name="synthesis_phase>
**Phase 2: SYNTHESIS**

Leader collects all Q&A and generates project brief.

```python
synthesis = synthesize_project_brief(
    user_goal=state.user_goal,
    discovery_log=state.discovery_log
)

# Synthesis structure:
synthesis = {
    "title": "Project Name",
    "goal": "One sentence describing what to build",
    "scope": {
        "included": ["feature 1", "feature 2"],
        "excluded": ["feature explicitly out"]
    },
    "constraints": {
        "budget": "...",
        "timeline": "...",
        "platform": "..."
    },
    "unknowns": ["questions not answered"],
    "next_steps": {
        "researcher": "...",
        "coder": "...",
        "creative": "..."
    }
}

state_manager.set_synthesis(synthesis)
```
</step>

<step name="approval_phase>
**Phase 3: APPROVAL**

Present synthesis to user for approval.

```python
approval_content = format_for_approval(synthesis)

response = f"""
## 📋 Project Brief

### 🎯 Goal
{synthesis.goal}

### ✅ In Scope
{format_list(synthesis.scope.included)}

### ❌ Out of Scope  
{format_list(synthesis.scope.excluded)}

### 🔒 Constraints
{format_constraints(synthesis.constraints)}

### ❓ Need More Info
{format_unknowns(synthesis.unknowns)}

### 🚀 Proposed Next Steps
{format_next_steps(synthesis.next_steps)}

---

**Does this look right?**

- Reply **"yes"** or **"approved"** to proceed
- Reply with changes: "Can you adjust X?" 
- Say **"cancel"** to start over
"""
```
</step>

<step name="handle_approval_response>
Process user's approval decision.

```python
response = parse_approval_response(user_message)

if response.is_approved():
    state_manager.approve(approved=True)
    return transition_to_execution()

elif response.is_rejection():
    # User wants changes - loop back to discovery
    state_manager.approve(approved=False, feedback=response.feedback)
    state_manager.add_discovery_entry(
        bot="user",
        content=f"FEEDBACK: {response.feedback}"
    )
    return continue_discovery(feedback=response.feedback)

elif response.is_cancellation():
    return cancel_and_reset()
```
</step>

<step name="execution_phase>
**Phase 4: EXECUTION**

Delegate work to specialist bots based on synthesis.

```python
# Leader coordinates delegation
execution_plan = synthesis.next_steps

# Execute in waves (GSD pattern)
wave_1 = [task for task in execution_plan if not task.has_dependencies]
wave_2 = [task for task in execution_plan if task.depends_on(wave_1)]

for task in wave_1:
    # Each bot executes their task
    result = await execute_task(task, bot=task.assigned_bot)
    state_manager.log_execution(task, result)

for task in wave_2:
    # Wait for dependencies, then execute
    result = await execute_task(task, bot=task.assigned_bot)
    state_manager.log_execution(task, result)
```
</step>

<step name="review_phase>
**Phase 5: REVIEW**

Present results to user for acceptance.

```python
# Aggregate results from all bots
results = state_manager.get_execution_results()

response = f"""
## ✅ Work Complete

Here's what was accomplished:

{format_results(results)}

---

**Does this meet your needs?**

- **"Perfect"** or **"yes"** → Complete (IDLE)
- **"Adjust X"** → Make changes
- **"Not quite"** → Explain what's wrong, fix
"""
```
</step>

<step name="complete_project>
Finalize project and return to IDLE.

```python
# Log completion
state_manager.complete(
    final_results=results,
    user_satisfaction=response.satisfaction
)

# Archive project (for Phase 2 session migration)
state_manager.archive()

return OutboundMessage(
    content="Great work! Let me know if you need anything else.",
    metadata={"flow": "FULL", "completed": True}
)
```
</step>

</process>

<success_criteria>
- [ ] Project state initialized
- [ ] Discovery: 2+ bots participate
- [ ] Discovery: Questions logged properly
- [ ] Discovery: Complete triggers synthesis
- [ ] Synthesis: Valid JSON structure
- [ ] Synthesis: All sections populated
- [ ] Approval: Presented clearly
- [ ] Approval: Yes → execution
- [ ] Approval: No → discovery loop
- [ ] Approval: Cancel handled
- [ ] Execution: Tasks delegated
- [ ] Execution: Results aggregated
- [ ] Review: User accepts
- [ ] Complete: Archive + IDLE
</success_criteria>

<output_state>
```python
@dataclass
class FullResult:
    iteration: int          # How many discovery loops
    discovery_log: List     # All Q&A
    synthesis: Dict         # Project brief
    approved: bool
    execution_results: Dict # Task results
    user_satisfaction: str
    next_state: str       # Always "IDLE" on completion
```
</output_state>

<example_traces>

**Example 1: Full Flow - Happy Path**
```
User: "Build me a website for my plumbing business"

→ Intent: BUILD
→ Start FULL flow

DISCOVERY:
Q1 (Researcher): "What's the main purpose - just info or booking jobs?"
User: "Mainly info, maybe booking later"

Q2 (Creative): "Do you have brand colors or should I design fresh?"
User: "No brand yet, go for something trustworthy and professional"

Q3 (Coder): "Any hosting preference or technical requirements?"
User: "Not sure, what's easiest?"

→ Synthesis generated
→ Presented to user

APPROVAL:
User: "Yes, that's exactly right!"

EXECUTION:
→ Researcher: Market research
→ Creative: Design mockups  
→ Coder: Build website
→ Results aggregated

REVIEW:
User: "This looks amazing, thank you!"
→ Complete → IDLE
```

**Example 2: Full Flow - Rejection Loop**
```
[Same start]

DISCOVERY: [same questions]

SYNTHESIS: Presented

APPROVAL:
User: "I think you missed the booking part - I definitely need booking"

→ Rejection logged
→ Back to DISCOVERY with feedback

DISCOVERY (round 2):
Q1 (Leader): "I understand you need booking functionality. How should that work?"
User: "Customers pick date/time, get confirmation"

Q2 (Coder): "Any preferences for booking system - built-in or integrated?"
User: "Integrated, like Calendly"

→ New synthesis
→ Presented

APPROVAL:
User: "Yes, that's better!"

EXECUTION: [continues...]
```

**Example 3: Escalated from LIGHT**
```
User: "Can I make money from gardening and photography?"

→ LIGHT flow
→ Explored options
→ User: "I like option 3, let's build it!"

→ Escalate to FULL
→ Context: exploration results + chosen option

DISCOVERY:
→ Some questions already answered from exploration
→ Ask remaining questions

SYNTHESIS: [continues...]
```

</example_traces>
