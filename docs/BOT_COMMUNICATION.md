# Bot-to-Bot Communication Guide

## Overview

Bots can communicate in **two ways**:

1. **Direct Messaging** (NEW) - Bot-to-bot for simple queries
2. **Through Leader** - Coordinator-mediated for complex tasks

## Communication Patterns

### Pattern 1: Direct Bot-to-Bot (Simple Queries)

**Use when:** Quick questions, information requests, clarifications

**Example: Social asks Coder about standards**

```python
# SocialBot needs coding standards info
success, answer = await social_bot.ask_bot(
    recipient_bot="coder",
    question="What are our Python naming conventions for public functions?",
    timeout_seconds=30
)

if success:
    # Use the answer in social content
    post_content = f"Our coding standards: {answer}"
    # Continue creating post...
else:
    # Fall back to Leader
    await social_bot.notify_coordinator(
        "Need coding standards from Coder but direct messaging failed",
        priority="normal"
    )
```

**Flow:**
```
SocialBot ──asks──> CoderBot
    │                   │
    │                   └── Answers
    │
    └── Uses answer to create post
```

**Benefits:**
- ✅ Fast (no Leader bottleneck)
- ✅ Efficient for simple queries
- ✅ Still logged in work logs
- ✅ Audit trail preserved

### Pattern 2: Through Leader (Complex Coordination)

**Use when:** Task delegation, multi-bot workflows, conflicts, approvals

**Example: Social needs research + creative for campaign**

```python
# SocialBot needs complex multi-bot coordination
await social_bot.notify_coordinator(
    message="Need research on coding trends and creative assets for campaign",
    priority="normal",
    data={
        "task": "Create social campaign about Python best practices",
        "needs": ["research", "creative"],
        "deadline": "2024-01-15"
    }
)
```

**Flow:**
```
SocialBot ──notifies──> Leader
                           │
                           ├── Delegates to Researcher
                           │       └── Provides trend data
                           │
                           ├── Delegates to Creative
                           │       └── Creates graphics
                           │
                           └── Combines outputs
                                   └── Sends to SocialBot
```

**Benefits:**
- ✅ Centralized coordination
- ✅ Leader can prioritize
- ✅ Better for complex workflows
- ✅ Full audit trail

### Pattern 3: Escalation (Critical Issues)

**Use when:** Problems, violations, need human attention

```python
# SocialBot detects issue
await social_bot.escalate_to_coordinator(
    message="Creative asset uses unverified copyrighted image",
    priority="high",
    data={
        "asset_id": "banner_001",
        "issue": "copyright_unverified",
        "risk": "legal"
    }
)
```

## When to Use Which Pattern

| Scenario | Use Direct? | Use Leader? | Why? |
|----------|------------|-------------|------|
| "What's the coding standard?" | ✅ | ❌ | Simple query |
| "Research this topic for me" | ❌ | ✅ | Task delegation |
| "Can you verify this fact?" | ✅ | ❌ | Quick check |
| "Create a campaign" | ❌ | ✅ | Multi-bot workflow |
| "Is this code secure?" | ✅ | ❌ | Simple audit |
| "Design + code this feature" | ❌ | ✅ | Complex coordination |
| "Emergency!" | ❌ | ✅ (escalate) | Needs human |
| "What's the API endpoint?" | ✅ | ❌ | Info lookup |

## Implementation Examples

### SocialBot asking CoderBot

```python
class SocialBot(SpecialistBot):
    async def create_tech_post(self, topic: str) -> str:
        # Need technical details from Coder
        success, tech_info = await self.ask_bot(
            "coder",
            f"Explain {topic} in simple terms for social media",
            timeout_seconds=45
        )
        
        if success:
            # Create post with technical info
            post = self._craft_post(topic, tech_info)
            return post
        else:
            # Escalate to Leader
            await self.escalate_to_coordinator(
                f"Failed to get tech info from Coder for post about {topic}"
            )
            return "Draft pending technical review"
```

### CreativeBot asking ResearcherBot

```python
class CreativeBot(SpecialistBot):
    async def design_infographic(self, topic: str) -> str:
        # Need research data for design
        success, research_data = await self.ask_bot(
            "researcher",
            f"Get key statistics and facts about {topic} for infographic",
            timeout_seconds=60
        )
        
        if success:
            # Use data in design
            design = self._create_visual(topic, research_data)
            
            # Get verification before finalizing
            verify_success, verification = await self.ask_bot(
                "researcher",
                f"Verify these facts are accurate: {research_data}",
                timeout_seconds=30
            )
            
            if verify_success and "accurate" in verification.lower():
                return design
            else:
                await self.escalate_to_coordinator(
                    "Research data needs verification before use in design"
                )
        else:
            await self.notify_coordinator(
                "Need research data for creative project"
            )
```

### CoderBot asking ResearcherBot

```python
class CoderBot(SpecialistBot):
    async def implement_feature(self, feature_spec: str) -> str:
        # Need to understand domain before coding
        success, domain_info = await self.ask_bot(
            "researcher",
            f"What are industry best practices for {feature_spec}?",
            timeout_seconds=60
        )
        
        if success:
            # Incorporate best practices
            implementation = self._code_with_practices(feature_spec, domain_info)
            return implementation
        else:
            # Proceed with caution, document assumptions
            implementation = self._code_with_todos(feature_spec)
            await self.notify_coordinator(
                "Implemented feature without research validation",
                data={"feature": feature_spec, "assumptions_made": True}
            )
            return implementation
```

## Message Types

### BotMessage Types

```python
class MessageType(Enum):
    QUERY = "query"           # Question expecting reply
    INFO = "info"             # Information (no reply expected)
    RESPONSE = "response"     # Reply to query
    TASK = "task"             # Work assignment (use Leader for this)
    ESCALATION = "escalation" # Problem requiring attention
```

### Direct Messaging Uses
- `QUERY` - Ask a question
- `INFO` - Share information
- `RESPONSE` - Answer a question

### Leader-Mediated Uses
- `TASK` - Delegate work (Leader only)
- `ESCALATION` - Report problems (Leader only)

## Best Practices

### DO:
- ✅ Use direct messaging for simple questions (< 1 minute to answer)
- ✅ Set appropriate timeouts (30-60 seconds for quick questions)
- ✅ Fall back to Leader if direct messaging fails
- ✅ Log all communications in work logs
- ✅ Be specific in questions

### DON'T:
- ❌ Use direct messaging for task delegation (use Leader)
- ❌ Send long-running requests directly (use Leader)
- ❌ Bypass Leader for multi-bot coordination
- ❌ Spam other bots with messages
- ❌ Send messages without context

### Example: Good Direct Message
```python
await self.ask_bot(
    "researcher",
    "What's the latest version of React as of today?",
    timeout_seconds=30
)
```

### Example: Bad Direct Message (Should Use Leader)
```python
# DON'T DO THIS
await self.ask_bot(
    "coder",
    "Build me a full authentication system with OAuth, JWT, and 2FA",
    timeout_seconds=30  # Way too short!
)
# SHOULD BE: notify_coordinator() with task delegation
```

## Audit Trail

All bot-to-bot messages are automatically logged:

```python
# In work_log.py
work_log.add_bot_message(
    bot_name="social",
    message="Asked coder about Python conventions",
    mentions=["@coder"],
    response_to=previous_step
)
```

This ensures:
- Full visibility into bot communications
- Audit trail for compliance
- Debugging capability
- Learning opportunities

## Error Handling

### Direct Messaging Failures

```python
success, result = await self.ask_bot("coder", "...")

if not success:
    # Options:
    # 1. Try Leader
    await self.notify_coordinator(
        f"Failed to reach Coder directly: {result}",
        priority="normal"
    )
    
    # 2. Escalate if critical
    await self.escalate_to_coordinator(
        f"Cannot get critical info from Coder: {result}"
    )
    
    # 3. Continue without (document assumption)
    await self.notify_coordinator(
        "Proceeding without Coder input due to communication failure",
        data={"assumption": "Using default standards"}
    )
```

### Timeout Handling

```python
success, result = await self.ask_bot(
    "researcher",
    "Complex analysis request...",
    timeout_seconds=120  # Longer for complex queries
)

if not success and "Timeout" in result:
    # Bot might be busy, try Leader
    await self.notify_coordinator(
        "Researcher busy, need analysis via Leader"
    )
```

## Advanced: Conversation Context

For multi-message exchanges:

```python
conversation_id = str(uuid.uuid4())

# First message
success, response1 = await self.ask_bot(
    "researcher",
    "What are React hooks?",
    context={"conversation_id": conversation_id}
)

# Follow-up in same conversation
if success:
    success, response2 = await self.ask_bot(
        "researcher",
        "Can you give me an example of useState?",
        context={
            "conversation_id": conversation_id,
            "reply_to": previous_message_id
        }
    )
```

## Summary

**Use Direct Messaging When:**
- Simple question (< 1 min to answer)
- Information lookup
- Quick verification
- Single-bot dependency

**Use Leader When:**
- Task delegation
- Multi-bot coordination
- Complex workflows
- Conflicts/arbitration
- Approvals required
- Emergency escalation

**The Hybrid Approach gives you the best of both worlds:**
- Speed of direct communication for simple things
- Coordination of Leader for complex things
- Full audit trail either way
