# Chat Flow Workflow

<purpose>
Handle direct conversational responses when user just wants to chat. No structured flow, no discovery, just natural conversation.
</purpose>

<context>
- Room context: Current room, participants
- User message: The conversational input
- Bot identity: Each bot has personality and expertise
</context>

<philosophy>
**Be conversational, not robotic.** Chat mode is about connection, not information transfer. Show personality, reference what others said, be human.

**Keep it light.** Chat responses should be 1-2 sentences. If user goes deep, escalate to QUICK.
</philosopher

<scope_guardrail>
**Max 2 responses then check.** After 2 conversational turns, prompt: "Want me to help you with something specific, or just chatting?"

**Don't drift into advice.** If user asks for advice, detect and escalate to QUICK flow.
</scope_guardrail>

<process>

<step name="identify_responder">
Determine which bot should respond.

```python
# For CHAT, Leader coordinates but any bot can respond
# Based on message content:
responder = select_bot_for_chat(message)
```

**Selection logic:**
- Reference to specific domain → that bot responds
- General conversation → Leader responds
- Humor/wit → Creative responds if relevant
</step>

<step name="build_context">
Build context for conversational response.

```python
context = f"""
You are @{responder}.

## Room Context
Room: {room.name}
Participants: {room.participants}

## Recent Conversation (last 3 messages)
{conversation_history[-3:]}

## User Message
{message}

## Instructions
- Respond naturally and conversationally (1-2 sentences)
- Show your personality
- If referencing another bot's message, acknowledge it
- Be helpful but don't over-explain
- Keep it light and engaging
"""
```
</step>

<step name="generate_response>
Generate conversational response.

```python
response = await LLM.chat(
    messages=[{"role": "system", "content": context}],
    model=bot_models[responder]  # Use bot's preferred model
)
```
</step>

<step name="format_output>
Format response for display.

```python
# Add emoji based on bot
emoji = bot_emojis[responder]

formatted = f"{emoji} **@{responder}:**\n{response.content}"
```
</step>

<step name="check_continuation>
After response, check if conversation is drifting toward structured work.

**Escalation triggers:**
- "Can you help me with..."
- "I need to..."
- "Can you research..."
- "How do I..."

```python
if detect_work_intent(user_next_message):
    # Preserve chat context
    return IntentDetectionResult(
        flow="QUICK",
        context={"chat_history": conversation_history}
    )
```

**If chat continues naturally:**
- Return to IDLE state
- Wait for next message
</step>

</process>

<success_criteria>
- [ ] Bot selected appropriately
- [ ] Response is conversational (1-2 sentences)
- [ ] Personality shows through
- [ ] References to other bots acknowledged
- [ ] Escalation detected when needed
- [ ] Returns to IDLE after completion
</success_criteria>

<output_state>
```python
@dataclass
class ChatResult:
    responder: str
    response: str
    escalation_triggered: bool
    next_state: str  # "IDLE" or flow to escalate to
```
</output_state>

<example_traces>

**Example 1: Simple Chat**
```
User: "Oh that's a really interesting point, Creative!"

→ Responder: creative (mentioned)
→ Response: "Thanks! I've been thinking about the color theory aspect..."
→ State: IDLE
```

**Example 2: Chat → Escalation**
```
User: "Haha that's funny! Actually, can you help me design a logo?"

→ Chat response first
→ User's follow-up triggers escalation
→ Detected work intent → escalate to QUICK/LIGHT
→ "Great! Let me ask a quick question about what you're looking for..."
```

**Example 3: Multi-Bot Chat**
```
User: "What does everyone think about the new feature?"

→ Leader coordinates
→ Multiple bots respond (researcher, coder, creative)
→ Each shows personality
→ State: IDLE
```

</example_traces>
