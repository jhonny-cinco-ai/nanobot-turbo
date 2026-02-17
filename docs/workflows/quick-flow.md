# Quick Flow Workflow

<purpose>
Handle ADVICE and RESEARCH intents - quick clarification followed by direct answer. Maximum 2 bot interactions.
</purpose>

<context>
- Intent: ADVICE or RESEARCH (detected in intent-detection)
- Entities: Extracted topics, interests, people
- Suggested bots: leader + researcher (typically)
</context>

<philosophy>
**Minimal friction, maximum value.** User wants an answer, not a process. Get just enough context to give a good answer, then deliver.

**Answer first, context second.** Lead with the advice/research findings, then acknowledge what you asked.
</philosophy>

<scope_guardrail>
**Max 2 questions.** If more needed, either provide answer with assumptions or escalate to LIGHT.

**Skip questions if clear.** If intent + entities are strong enough, skip straight to answer.
</scope_guardrail>

<process>

<step name="analyze_clarity>
Determine if we have enough context to answer.

```python
# Check intent entities
has_topic = len(intent.entities.get('topics', [])) > 0
has_people = len(intent.entities.get('people', [])) > 0
has_context = has_topic or has_people

# Strong signal = skip questions
if intent.confidence > 0.8 and has_context:
    return proceed_to_answer()
else:
    return ask_one_question()
```
</step>

<step name="ask_one_question>
Ask ONE clarifying question if needed.

```python
# Determine what we need to know
question = determine_missing_info(intent)

# Format as bot response
response = f"""
Based on what you've shared, I can give you some guidance!

But first: {question}

(This helps me tailor the advice to your situation)
"""
```

**Question selection by intent:**

| Intent | Typical Question |
|--------|------------------|
| ADVICE | "What's your experience level?" / "Any constraints I should know?" |
| RESEARCH | "How deep should I go?" / "Any specific aspects you want focused on?" |
</step>

<step name="collect_answer>
After user responds (or immediately if skipped questions), gather answer.

```python
# For ADVICE: Synthesize best practices
if intent.type == ADVICE:
    answer = synthesize_advice(
        topic=intent.entities['topic'],
        constraints=user_constraints,
        expertise_level=user_level
    )

# For RESEARCH: Present findings
elif intent.type == RESEARCH:
    answer = conduct_research(
        topic=intent.entities['topic'],
        depth='summary'  # Quick mode
    )
```
</step>

<step name="format_response>
Present the answer with bot personality.

```python
# Leader coordinates, Researcher provides content
response = f"""
## {answer.title}

{answer.content}

### Quick Summary
- {answer.key_point_1}
- {answer.key_point_2}
- {answer.key_point_3}

---

**Follow up?** I can dive deeper into any of these, or help you take the next step!
"""
```
</step>

<step name="handle_followup>
Check for follow-up or escalation.

```user_response>
User might:
1. Ask follow-up → Answer more (stay in QUICK)
2. Want to build → Escalate to FULL
3. Say thanks → Done (IDLE)
4. New topic → Restart intent detection
</user_response>

```python
if is_build_intent(user_response):
    return escalate_to_full(user_response, quick_context)
elif is_followup(user_response):
    return continue_quick_answer(user_response)
else:
    return reset_to_idle()
```
</step>

</process>

<success_criteria>
- [ ] Questions asked only when needed
- [ ] Max 1 question before answer
- [ ] Answer is actionable and specific
- [ ] Bot personality shows
- [ ] Follow-up handled appropriately
- [ ] Escalation detected and executed
- [ ] Returns to IDLE when done
</success_criteria>

<output_state>
```python
@dataclass
class QuickResult:
    intent: IntentType  # ADVICE or RESEARCH
    questions_asked: int
    answer_provided: str
    escalation_triggered: bool
    next_state: str  # "IDLE" or "FULL"
```
</output_state>

<example_traces>

**Example 1: ADVICE - Clear Question**
```
User: "How do I organize weekly groceries?"

→ Intent: ADVICE (confidence: 0.85)
→ Entity: topic="groceries", action="organize"
→ Question needed: "Any budget constraints?"

User: "Around $100/week"

→ Answer: "Here's my 3-tier approach..."
→ Response formatted with personality
→ User: "Thanks!" → IDLE
```

**Example 2: RESEARCH - Strong Signal**
```
User: "What are fun ways to teach a 7-year-old math?"

→ Intent: RESEARCH (confidence: 0.95)
→ Entity: topic="math", people="7-year-old"
→ Skip questions (strong signal)

→ Research conducted
→ Answer presented
→ User: "These are great! Can you help me create one?" → Escalate to FULL
```

**Example 3: ADVICE - Follow-up**
```
User: "How do I organize weekly groceries?"

→ Question: "What's your household size?"

User: "Just me"

→ Answer provided
→ User: "What about meal prep?"

→ Follow-up detected
→ Additional advice provided
→ User: "Perfect, thanks!" → IDLE
```

</example_traces>
