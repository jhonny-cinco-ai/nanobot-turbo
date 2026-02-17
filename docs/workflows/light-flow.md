# Light Flow Workflow

<purpose>
Handle EXPLORE (business/idea exploration) and TASK (specific task completion) intents. More involved than QUICK but doesn't require full project structure.
</purpose>

<context>
- Intent: EXPLORE or TASK (detected in intent-detection)
- Entities: Extracted interests, constraints, requirements
- Suggested bots: leader + researcher + creative (EXPLORE) or leader + coder (TASK)
</context>

<philosophy>
**Explore options, don't commit.** LIGHT flow presents choices, not a plan. User picks direction, we help execute if needed.

**Present, then pause.** Give user options to consider. Don't assume they want to proceed until they say so.
</philosophy>

<scope_guardrail>
**Max 3 questions.** Enough to understand context, not enough to be a project.

**Present options, not a plan.** Output should be "Here are 3-5 approaches" not "Here's what we'll build."
</scope_guardrail>

<process>

<step name="start_discovery>
Initialize project state for LIGHT flow.

```python
state_manager = ProjectStateManager(room_id)
state_manager.start_light_flow(
    intent_type=intent.type,
    user_goal=message,
    entities=intent.entities
)
```
</step>

<step name="discovery_round_1>
Bot 1 asks first clarifying question.

```python
# Select first bot based on intent
first_bot = get_first_bot(intent.type)

question = generate_question(
    intent=intent,
    round=1,
    already_asked=[]
)

# Log question to discovery
state_manager.log_question(bot=first_bot, question=question)
```
</step>

<step name="discovery_round_2>
Bot 2 asks second question (if needed).

```python
# Check if we have enough context
if not enough_context(user_response):
    second_bot = get_second_bot(intent.type)
    
    question = generate_question(
        intent=intent,
        round=2,
        already_asked=[q1]
    )
    
    state_manager.log_question(bot=second_bot, question=question)
```
</step>

<step name="generate_options>
Based on intent, generate options.

**For EXPLORE (business ideas):**
```python
options = researcher.generate_business_options(
    interests=entities['interests'],
    constraints=discovered_constraints,
    count=5
)

# Options structure:
# [
#   {"title": "Option 1", "summary": "...", "pros": [], "cons": []},
#   {"title": "Option 2", ...},
#   ...
# ]
```

**For TASK (specific task):**
```python
tasks = coder.decompose_task(
    task_description=user_goal,
    constraints=discovered_constraints
)

# Tasks structure:
# [
#   {"step": 1, "action": "...", "deliverable": "..."},
#   ...
# ]
```
</step>

<step name="present_options>
Format and present options to user.

```python
response = f"""
## {intent.type === 'EXPLORE' ? 'Business Options' : 'Task Breakdown'}

Based on our conversation, here are your options:

"""

for i, option in enumerate(options, 1):
    response += f"""
### {i}. {option.title}
{option.summary}

**Pros:** {', '.join(option.pros)}
**Cons:** {', '.join(option.cons)}
"""

response += """

---

Which resonates with you? 

- Reply with a number (1-5)
- Or describe what you like: "I like option 3 but more like option 1"
- Or say "none" to start fresh

**Want to build one?** Just say "let's do option X" or "build this" and I'll help you create it!
"""
```
</step>

<step name="handle_selection>
Process user's selection or response.

```python
selection = parse_user_response(user_message)

if selection.is_number():
    chosen = options[selection.number - 1]
elif selection.is_built():
    # User wants to build
    return escalate_to_full(chosen, light_context)
else:
    # User wants modifications
    return adjust_options(selection.feedback)
```
</step>

<step name="handle_build_escalation>
If user wants to execute, escalate to FULL flow.

```python
# Preserve LIGHT context for FULL
full_context = {
    "origin": "LIGHT",
    "exploration_result": chosen_option,
    "discovered_constraints": constraints,
    "discovery_log": state_manager.get_log()
}

return escalate_to_full(user_message, full_context)
```
</step>

<step name="complete_light>
If user is satisfied (not escalating), complete flow.

```python
# Log completion
state_manager.complete(
    selected_option=chosen,
    user_satisfaction="high"  # or "moderate"
)

return OutboundMessage(
    content=f"""
Great choice: **{chosen.title}**!

{final_guidance_for_option}

Let me know if you want to:
- Dive deeper into this option
- Adjust the approach
- Actually build it (I can help with that!)

I'm here whenever you're ready to take the next step.
""",
    metadata={"flow": "LIGHT", "completed": True}
)
```
</step>

</process>

<success_criteria>
- [ ] Discovery state initialized
- [ ] Questions limited to 3 max
- [ ] Options relevant to intent
- [ ] Options presented clearly (numbered, pros/cons)
- [ ] Selection parsed correctly
- [ ] Escalation to FULL works
- [ ] Completion handled gracefully
- [ ] Returns to IDLE
</success_criteria>

<output_state>
```python
@dataclass
class LightResult:
    intent: IntentType  # EXPLORE or TASK
    questions_asked: int
    options_generated: int
    selected_option: Dict
    escalation_triggered: bool  # User wants to build
    next_state: str  # "IDLE" or "FULL"
```
</output_state>

<example_traces>

**Example 1: EXPLORE Flow**
```
User: "I love gardening and photography, can I make money from it?"

→ Intent: EXPLORE (confidence: 0.9)
→ Bots: leader, researcher, creative

Q1 (Researcher): "How much time can you commit weekly?"
User: "About 10 hours"

Q2 (Creative): "What's your photography style - nature, portraits, events?"
User: "Mainly nature and plants"

→ Generate 5 business options
→ Present options with pros/cons

User: "I like option 3, can you help me buildate to FULL
 it?"

→ Escal→ Context: discovery log + chosen option
```

**Example 2: TASK Flow**
```
User: "Write a professional email to my boss asking for a raise"

→ Intent: TASK
→ Bots: leader, coder (for drafting)

Q1 (Leader): "Any specific points you want to include?"
User: "My contributions this year and market rates"

→ Generate task breakdown:
1. Draft email structure
2. Research salary data
3. Write first draft

→ Present breakdown
User: "Yes, let's do this"

→ Execute task (email drafted)
→ Complete
```

**Example 3: LIGHT → Done**
```
[Same exploration scenario]

User: "Option 3 is perfect, thanks!"

→ Record selection
→ Provide final guidance
→ User: "Awesome, that's exactly what I needed!"
→ IDLE
```

</example_traces>
