# Bot-Level Chain-of-Thought (CoT) Configuration

**Status**: Design Phase  
**Target**: Phase 7 Implementation  
**Last Updated**: 2026-02-13

## Overview

This document proposes a **bot-level Chain-of-Thought (CoT) configuration system** that integrates with our existing multi-bot architecture and smart routing system. The goal is to enable adaptive reasoning that considers:

1. **Bot specialization** - Each bot has domain-specific reasoning needs
2. **Routing tier** - Conversation complexity determines reasoning depth
3. **Tool context** - Specific tools may trigger reflection
4. **Token efficiency** - Avoid unnecessary overhead for simple tasks

## Motivation

Our current architecture includes:
- ✅ **6 specialized bots** with autonomous routines
- ✅ **Smart routing system** with tiered models (simple/medium/complex)
- ✅ **Session compaction** for context management
- ❌ **No adaptive reasoning** - Same approach for all tasks

The upstream commit `d335494` added interleaved CoT to the agent loop, but it's **always enabled** and adds overhead to every tool call. This is wasteful for:
- Simple tier conversations ("What's the weather?")
- SocialBot posting scheduled content
- CreativeBot checking asset status

**Solution**: Bot-level configuration with tier-aware defaults.

## Architecture

```
User Request
     │
     ▼
┌─────────────────────────────────────┐
│ Smart Router                        │
│  ├─ Detects complexity              │
│  └─ Selects tier (simple/medium/complex)│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ MultiTeamRoutinesManager               │
│  └─ Routes to appropriate bot       │
└──────────────┬──────────────────────┘
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐
│CoderBot│ │SocialBot│ │AuditorBot│
│  CoT:  │ │  CoT:   │ │  CoT:    │
│  true  │ │  false  │ │  minimal │
└────────┘ └────────┘ └────────┘
     │         │         │
     └─────────┴─────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Reasoning Engine                    │
│  ├─ Check bot config                │
│  ├─ Check routing tier              │
│  └─ Apply CoT if warranted          │
└─────────────────────────────────────┘
```

## Configuration Design

### 1. Data Model

```python
# nanofolks/reasoning/config.py
from dataclasses import dataclass
from typing import Optional, Set
from enum import Enum

class CoTLevel(Enum):
    """Chain-of-thought reasoning levels."""
    NONE = "none"           # No reflection, fastest
    MINIMAL = "minimal"     # Only after error/failure
    STANDARD = "standard"   # After complex tools
    FULL = "full"           # After every tool call

@dataclass
class ReasoningConfig:
    """Configuration for bot reasoning behavior."""
    
    # Primary setting
    cot_level: CoTLevel = CoTLevel.STANDARD
    
    # Tier overrides (optional)
    simple_tier_level: Optional[CoTLevel] = None  # Default: downgrade by 1
    medium_tier_level: Optional[CoTLevel] = None  # Default: use cot_level
    complex_tier_level: Optional[CoTLevel] = None # Default: upgrade by 1
    
    # Tool-specific triggers (always trigger CoT regardless of level)
    always_cot_tools: Set[str] = None  # {"spawn", "exec", "github"}
    
    # Tool-specific exclusions (never trigger CoT)
    never_cot_tools: Set[str] = None   # {"time", "weather"}
    
    # Custom prompt (optional)
    reflection_prompt: Optional[str] = None
    
    # Token budget
    max_reflection_tokens: int = 150
    
    def should_use_cot(self, tier: str, tool_name: str) -> bool:
        """Determine if CoT should be used for this context."""
        # Check exclusions first
        if self.never_cot_tools and tool_name in self.never_cot_tools:
            return False
        
        # Check mandatory triggers
        if self.always_cot_tools and tool_name in self.always_cot_tools:
            return True
        
        # Determine effective level based on tier
        effective_level = self._get_effective_level(tier)
        
        # Map level to behavior
        if effective_level == CoTLevel.NONE:
            return False
        elif effective_level == CoTLevel.FULL:
            return True
        elif effective_level == CoTLevel.MINIMAL:
            # Only for error-prone tools
            return tool_name in {"spawn", "exec", "eval"}
        else:  # STANDARD
            # After multi-step or complex tools
            return tool_name not in {"time", "date", "ping"}
    
    def _get_effective_level(self, tier: str) -> CoTLevel:
        """Get CoT level considering tier overrides."""
        tier_map = {
            "simple": self.simple_tier_level,
            "medium": self.medium_tier_level,
            "complex": self.complex_tier_level,
        }
        
        override = tier_map.get(tier)
        if override:
            return override
        
        # Default tier adjustments
        if tier == "simple" and self.cot_level != CoTLevel.NONE:
            # Downgrade simple tier by one level
            levels = [CoTLevel.NONE, CoTLevel.MINIMAL, CoTLevel.STANDARD, CoTLevel.FULL]
            idx = levels.index(self.cot_level)
            return levels[max(0, idx - 1)]
        elif tier == "complex" and self.cot_level != CoTLevel.FULL:
            # Upgrade complex tier by one level
            levels = [CoTLevel.NONE, CoTLevel.MINIMAL, CoTLevel.STANDARD, CoTLevel.FULL]
            idx = levels.index(self.cot_level)
            return levels[min(len(levels) - 1, idx + 1)]
        
        return self.cot_level
```

### 2. Bot-Specific Configurations

```python
# nanofolks/bots/reasoning_configs.py
from nanofolks.reasoning.config import ReasoningConfig, CoTLevel

# ResearcherBot: Analytical work benefits from reflection
RESEARCHER_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    always_cot_tools={"search", "analyze", "compare"},
    never_cot_tools={"time", "date"},
    reflection_prompt="Analyze the findings and determine next research steps.",
    max_reflection_tokens=200,
)

# CoderBot: Coding definitely needs step-by-step reasoning
CODER_REASONING = ReasoningConfig(
    cot_level=CoTLevel.FULL,  # Always reflect after code execution
    always_cot_tools={"spawn", "exec", "github", "eval"},
    never_cot_tools={"time"},
    reflection_prompt="Review the code execution results, check for errors, and plan the next implementation step.",
    max_reflection_tokens=250,
)

# SocialBot: Social posts are simple, minimal reasoning needed
SOCIAL_REASONING = ReasoningConfig(
    cot_level=CoTLevel.NONE,  # Social media posts don't need CoT
    simple_tier_level=CoTLevel.NONE,
    always_cot_tools=set(),   # No tools need CoT for social
    never_cot_tools={"*"},    # Never use CoT (all tools)
    reflection_prompt=None,
    max_reflection_tokens=0,
)

# AuditorBot: Sequential by nature, minimal reflection
AUDITOR_REASONING = ReasoningConfig(
    cot_level=CoTLevel.MINIMAL,
    always_cot_tools={"audit", "review"},
    never_cot_tools={"time", "list"},
    reflection_prompt="Verify audit results for accuracy.",
    max_reflection_tokens=100,
)

# CreativeBot: Creative work benefits from reflection
CREATIVE_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    always_cot_tools={"generate", "design", "edit"},
    never_cot_tools={"time", "date"},
    reflection_prompt="Evaluate the creative output and plan refinements.",
    max_reflection_tokens=180,
)

# nanofolksLeader: Strategic coordination needs full reasoning
COORDINATOR_REASONING = ReasoningConfig(
    cot_level=CoTLevel.FULL,
    always_cot_tools={"delegate", "coordinate", "notify"},
    never_cot_tools={"time", "ping"},
    reflection_prompt="Assess team status and prioritize coordination actions.",
    max_reflection_tokens=200,
)
```

### 3. Integration with Agent Loop

```python
# nanofolks/agent/loop.py modifications

class AgentLoop:
    def __init__(self, ...):
        # ... existing init ...
        
        # Load reasoning config for this bot
        from nanofolks.reasoning.config import get_reasoning_config
        self.reasoning_config = get_reasoning_config(bot_name)
    
    async def _process_message(self, msg: MessageEnvelope) -> MessageEnvelope | None:
        # ... existing processing ...
        
        # After tool execution, check if CoT is warranted
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                # Execute tool
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                messages = self.context.add_tool_result(
                    messages, tool_call.id, tool_call.name, result
                )
                
                # NEW: Check if we should add CoT reflection
                if self._should_use_cot(routing_ctx.tier, tool_call.name):
                    messages.append({
                        "role": "user",
                        "content": self._get_reflection_prompt()
                    })
    
    def _should_use_cot(self, tier: str, tool_name: str) -> bool:
        """Determine if CoT should be used."""
        if not self.reasoning_config:
            return False  # Default: no CoT
        return self.reasoning_config.should_use_cot(tier, tool_name)
    
    def _get_reflection_prompt(self) -> str:
        """Get the reflection prompt for this bot."""
        if self.reasoning_config and self.reasoning_config.reflection_prompt:
            return self.reasoning_config.reflection_prompt
        return "Reflect on the results and decide next steps."
```

### 4. Integration with Routing System

```python
# nanofolks/agent/routing/stage.py

class RoutingStage:
    """Enhanced routing with reasoning awareness."""
    
    async def execute(self, ctx: RoutingContext) -> None:
        # ... existing routing logic ...
        
        # Store tier in context for CoT decisions
        ctx.metadata["routing_tier"] = selected_tier
        
        # Optional: Adjust tier based on bot's reasoning config
        if ctx.bot and ctx.bot.reasoning_config:
            if ctx.bot.reasoning_config.cot_level == CoTLevel.NONE:
                # Bot doesn't use CoT, can use simpler model
                ctx.metadata["model_complexity"] = "reduced"
            elif ctx.bot.reasoning_config.cot_level == CoTLevel.FULL:
                # Bot needs heavy reasoning, ensure adequate model
                if selected_tier == "simple":
                    ctx.metadata["tier_override"] = "medium"
```

## Benefits

### 1. **Token Efficiency**
```
Scenario: Simple weather query via SocialBot
Without CoT config: ~50 extra tokens per tool call
With CoT config: 0 extra tokens (CoT disabled for SocialBot)
Savings: 100% for simple social tasks
```

### 2. **Domain Optimization**
- CoderBot: Full CoT catches code errors early
- SocialBot: No CoT overhead for simple posts
- ResearcherBot: Standard CoT for analytical depth

### 3. **Tier Awareness**
- Simple tier + SocialBot = No CoT (ultra-fast)
- Complex tier + CoderBot = Full CoT (deep reasoning)
- Medium tier + ResearcherBot = Standard CoT (balanced)

### 4. **Scalability**
Adding new bots is easy - just define their `ReasoningConfig`:

```python
# New bot example
DATA_SCIENTIST_REASONING = ReasoningConfig(
    cot_level=CoTLevel.STANDARD,
    always_cot_tools={"analyze", "visualize", "model"},
    reflection_prompt="Evaluate statistical significance and plan next analysis step.",
)
```

## Trade-offs

| Aspect | With CoT Config | Without (Always On) |
|--------|----------------|---------------------|
| Token Usage | Optimized per bot/task | Always high |
| Response Time | Faster for simple tasks | Consistently slower |
| Code Complexity | Moderate (config layer) | Simple (always add) |
| Reasoning Quality | Domain-optimized | Consistent but wasteful |
| Debugging | Harder (conditional logic) | Easier (always happens) |

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create `nanofolks/reasoning/config.py` with data models
2. Add reasoning configs to bot definitions
3. Modify `AgentLoop` to check reasoning config

### Phase 2: Integration
1. Connect reasoning config to routing system
2. Add reasoning metrics to work logs
3. Update dashboard to show reasoning stats

### Phase 3: Optimization
1. Collect token usage metrics per bot/tier
2. Fine-tune configurations based on data
3. Add automatic tier adjustment based on context

### Phase 4: Documentation & Testing
1. Document each bot's reasoning strategy
2. Add tests for conditional CoT logic
3. Create debugging tools for reasoning decisions

## Configuration Examples

### Example 1: CoderBot on Complex Task
```
Task: "Debug this Python script"
Tier: complex (detected by router)
Bot: CoderBot
Config: CoTLevel.FULL
Result: ✅ CoT enabled after every tool
Tokens: +250 per reflection, but catches errors early
```

### Example 2: SocialBot on Simple Task
```
Task: "Post good morning message"
Tier: simple
Bot: SocialBot  
Config: CoTLevel.NONE
Result: ❌ No CoT overhead
Tokens: +0 (fastest path)
```

### Example 3: ResearcherBot on Medium Task
```
Task: "Analyze Q4 sales data"
Tier: medium
Bot: ResearcherBot
Config: CoTLevel.STANDARD
Result: ⚖️ CoT after analysis tools, not after time/date
Tokens: +150 after heavy analysis only
```

## Metrics to Track

1. **Token Savings**
   - Compare with/without CoT config
   - Per bot, per tier breakdown

2. **Response Quality**
   - Error rates by bot/tier
   - User satisfaction scores

3. **Performance**
   - Latency by bot/tier
   - Iteration counts

4. **Cost Analysis**
   - Token cost savings
   - ROI of reasoning complexity

## Migration Path

From upstream "always-on" CoT:

1. **Default Behavior**: Start with `CoTLevel.STANDARD` for all bots
2. **Gradual Optimization**: Tune each bot based on domain needs
3. **A/B Testing**: Compare quality metrics before/after
4. **Full Deployment**: Enable optimized configs

## Conclusion

This bot-level CoT configuration system provides:

✅ **Adaptive reasoning** that matches task complexity  
✅ **Token efficiency** by avoiding unnecessary overhead  
✅ **Domain optimization** per bot specialization  
✅ **Backward compatibility** with gradual migration  
✅ **Extensibility** for future bots and use cases  

It transforms CoT from a blunt instrument into a precision tool that enhances our multi-bot architecture.

---

**Next Steps**: 
1. Review and approve design
2. Create implementation branch
3. Implement core infrastructure (Phase 1)
4. Test with CoderBot as pilot
5. Roll out to all bots

**Estimated Effort**: 2-3 days for full implementation
