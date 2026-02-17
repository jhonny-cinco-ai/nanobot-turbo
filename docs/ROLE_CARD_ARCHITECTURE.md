# Role Card Architecture Documentation

## Overview

The role card system has been completely redesigned based on the multi-agent architecture pattern. Each bot now has a **complete 6-layer role card** that defines constraints, boundaries, and responsibilities.

## Architecture: Three Complementary Systems

The bot configuration is now split into three complementary (not competing) systems:

### 1. ROLE CARD (Constraints & Boundaries)
**Purpose:** SHRINKS the behavior space by defining what CAN and CANNOT be done

**File:** Loaded from code defaults, editable at `.nanofolks/role_cards/{bot_name}.yaml`

**Contains:**
- **Domain:** What the bot owns
- **Inputs/Outputs:** What it receives and delivers
- **Definition of Done:** When "done" is actually done
- **Hard Bans:** What must NEVER be done (e.g., "No direct posting")
- **Escalation Triggers:** When to stop and ask for help
- **Metrics:** KPIs for performance tracking

**Example Hard Bans:**
```yaml
hard_bans:
  - No direct posting (drafts only)
  - No making up statistics or numbers
  - No internal formats or tool traces in public content
  - No deploying to production without approval
```

**In Prompt:** Loaded FIRST to establish constraints before personality

### 2. IDENTITY.md (Personality & Relationships)
**Purpose:** Defines WHO the bot is

**File:** `bots/{bot_name}/IDENTITY.md` or theme template

**Contains:**
- Who am I (backstory, origin)
- Relationships with other bots
- Quirks and personality traits
- What makes this bot unique

**Example:**
```markdown
## Who am I?
I am Xalt, the Social Media Director. I'm edgy, bold, and impatient...

## Relationships
- **Opus (Leader):** I respect their authority but push back on slow decisions
- **Brain (Researcher):** We often clash - I'm "ship it first" they're "show me data"
```

**In Prompt:** Loaded SECOND, after role card constraints

### 3. SOUL.md (Voice & Tone)
**Purpose:** Defines HOW the bot speaks

**File:** `bots/{bot_name}/SOUL.md` or theme template

**Contains:**
- Voice directives (speaking style)
- Tone guidelines
- Word choice preferences
- Communication patterns

**Example:**
```markdown
## Voice
Short commanding sentences. I track mission completion rates and demand explanations.

## Rules
Every message must contain:
1. One specific fact (number/name/result)
2. One action (who does what)

Never say "great work" or "sounds good" without citing what was great.
```

**In Prompt:** Loaded THIRD, after identity

### 4. AGENTS.md (Task Instructions)
**Purpose:** Defines WHAT the bot should do (specific tasks)

**File:** `bots/{bot_name}/AGENTS.md`

**Contains:**
- Specific instructions for tasks
- Workflow definitions
- Tool usage guidelines
- Output format requirements

**In Prompt:** Loaded LAST, provides specific task guidance

## Prompt Assembly Order

```
1. ROLE CARD (constraints & boundaries) ← ESTABLISH RULES FIRST
2. IDENTITY.md (who you are)           ← THEN PERSONALITY
3. SOUL.md (how you speak)             ← THEN VOICE
4. AGENTS.md (what to do)              ← THEN SPECIFIC TASKS
5. Memory/Skills/Context               ← FINALLY CONTEXT
```

This order ensures:
- **Hard bans** are established before any task execution
- **Constraints** shape how personality is expressed
- **Voice** applies within the defined boundaries
- **Tasks** are performed within the constraint framework

## Role Card Storage System

### Storage Locations (Priority Order)

1. **Workspace Override:** `.nanofolks/role_cards/{bot_name}.yaml`
   - User-editable per-project
   - Highest priority
   
2. **Global Override:** `~/.config/nanofolks/role_cards/{bot_name}.yaml`
   - User-editable globally
   - Applies across all projects
   
3. **Built-in Defaults:** Hardcoded in `nanofolks/models/role_card.py`
   - Fallback if no overrides exist
   - Always available

### User Editing

Users can edit role cards via:

```python
from nanofolks.models import get_role_card_storage, RoleCard

# Get storage manager
storage = get_role_card_storage(workspace_path)

# Load current role card
role_card = storage.get_role_card("social")

# Modify
role_card.hard_bans.append("No posting about competitors without approval")

# Save (scope: "workspace" or "global")
storage.save_role_card(role_card, scope="workspace")
```

Or directly edit YAML:

```yaml
# .nanofolks/role_cards/social.yaml
bot_name: social
domain: community
domain_description: "Community engagement and social media management"
inputs:
  - "Content drafts and variants"
  - "Community mentions and feedback"
outputs:
  - "Social media drafts (NOT direct posts)"
  - "Community response suggestions"
hard_bans:
  - "No direct posting to social media (drafts only)"
  - "No making up statistics or numbers"
escalation_triggers:
  - "Numeric claims or comparisons"
  - "Controversial or sensitive topics"
```

### Bot-Proposed Updates

Bots can propose role card updates through the learning system:

```python
# Bot proposes an update based on experience
storage.save_bot_proposal(
    bot_name="social",
    proposed_changes={"hard_bans": ["...new ban based on mistake..."]},
    reason="Learned from incident where I leaked internal paths"
)
```

Proposals are saved as `{bot_name}_proposal.yaml` and require user approval.

## Complete Role Card Structure

Each bot has a complete role card with all 6 layers:

### Leader (Coordinator)
```yaml
domain: coordination
domain_description: "Team coordination, task delegation, and final decision making"
inputs:
  - "User requests and requirements"
  - "Bot outputs and deliverables"
  - "Escalations requiring decisions"
outputs:
  - "Task assignments to specialist bots"
  - "Final decisions on escalations"
hard_bans:
  - "No deploying to production without approval"
  - "No overriding specialist bot expertise without good reason"
escalation_triggers:
  - "Legal or compliance risks"
  - "High-stakes decisions with unclear outcomes"
```

### Researcher
```yaml
domain: research
domain_description: "Information gathering, data analysis, and knowledge synthesis"
hard_bans:
  - "No making up citations or fabricating data"
  - "No presenting unverified information as fact"
escalation_triggers:
  - "Conflicting or contradictory data"
  - "Insufficient reliable sources"
```

### Coder
```yaml
domain: development
domain_description: "Code implementation, debugging, and technical solutions"
hard_bans:
  - "No committing directly to main/production without PR"
  - "No skipping tests or code review"
  - "No leaving hardcoded credentials or secrets"
escalation_triggers:
  - "Architectural decisions affecting multiple systems"
  - "Security vulnerabilities requiring immediate attention"
```

### Social
```yaml
domain: community
domain_description: "Community engagement and social media management"
hard_bans:
  - "No direct posting to social media (drafts only)"
  - "No making up statistics or numbers"
  - "No internal formats or tool traces in public content"
escalation_triggers:
  - "Numeric claims or comparisons requiring verification"
  - "Controversial or sensitive topics"
```

### Creative
```yaml
domain: design
domain_description: "Content creation, design assets, and creative strategy"
hard_bans:
  - "No inventing facts for creative content"
  - "No using copyrighted material without permission"
escalation_triggers:
  - "Conflicts between creative vision and brand guidelines"
```

### Auditor
```yaml
domain: quality
domain_description: "Quality assurance, compliance verification, and audit trails"
hard_bans:
  - "No approving work with critical security issues"
  - "No personal attacks or blame in feedback"
  - "No fabricating audit findings"
escalation_triggers:
  - "Critical security vulnerabilities"
  - "Compliance violations"
```

## Hard Ban Enforcement

### Runtime Checking

The `can_perform_action()` method in `SpecialistBot` checks actions against hard bans:

```python
def can_perform_action(self, action: str, context: Optional[Dict] = None) -> Tuple[bool, Optional[str]]:
    """Check if an action violates any hard bans."""
    return self.role_card.check_hard_bans(action, context)
```

### Usage in Agent Loop

The agent loop should check hard bans before executing tools:

```python
# Before executing a tool
is_allowed, error = bot.can_perform_action(
    action=f"Execute {tool_name}",
    context={"tool": tool_name, "args": tool_args}
)

if not is_allowed:
    # Log escalation
    work_log.add_escalation(f"Blocked action: {error}", bot_name=bot.name)
    # Return error to LLM
    return f"ERROR: This action violates hard ban - {error}"
```

## Escalation System

### Trigger Detection

Role cards define when bots should escalate to humans:

```python
def should_escalate(self, situation: str, confidence: float = 1.0) -> Tuple[bool, str]:
    """Determine if a situation requires escalation."""
    # Check escalation triggers
    for trigger in self.escalation_triggers:
        if matches_trigger(situation, trigger):
            return True, f"Escalation trigger matched: '{trigger}'"
    
    # Low confidence escalation
    if confidence < 0.5:
        return True, f"Low confidence ({confidence:.0%}) - requires human review"
    
    return False, ""
```

### Escalation Flow

1. Bot detects escalation trigger (via `should_escalate()`)
2. Bot calls `escalate_to_coordinator()` with details
3. Coordinator logs escalation in work log (`add_escalation()`)
4. User is notified of pending escalation
5. User provides guidance or takes over

## Integration with Turbo Memory

### Learning from Violations

When a hard ban is triggered:

1. Log the violation with context
2. Extract learning: "I tried to X, but it violates ban Y"
3. Save to turbo memory as a lesson
4. Future prompts include: "Remember: Never do X (violates ban Y)"

### Metrics Tracking

Role card metrics feed into RPG-style stats:

```python
metrics:
  - "Task completion rate"     → TRU (Trust) stat
  - "Research accuracy rate"   → WIS (Wisdom) stat  
  - "Engagement rate"          → VRL (Viral) stat
  - "Code quality score"       → CRE (Creative) stat
```

## Migration Guide

### For Existing Users

1. **No immediate action required** - Built-in defaults work out of the box
2. **Customize gradually** - Edit role cards as needed per bot
3. **Legacy compatibility** - Old bot capabilities still work

### For Bot Developers

1. **Update imports:**
   ```python
   from nanofolks.models import get_role_card
   # Now returns full RoleCard with all 6 layers
   ```

2. **Check hard bans before actions:**
   ```python
   is_allowed, error = bot.can_perform_action(action)
   if not is_allowed:
       # Handle violation
   ```

3. **Use escalation properly:**
   ```python
   should_escalate, reason = bot.role_card.should_escalate(situation)
   if should_escalate:
       await bot.escalate_to_coordinator(reason)
   ```

## Best Practices

### Writing Good Hard Bans

Don't ask "what should it do?" Ask "if it screws up, what's the worst case?"

**Bad:** "Be careful with social media"
**Good:** "No direct posting (drafts only)"

**Bad:** "Write good code"
**Good:** "No committing to main without PR review"

### Defining Escalation Triggers

Be specific about when human judgment is required:

**Bad:** "Ask for help when confused"
**Good:** "Escalate when numeric claims lack verification source"

### Metrics Selection

Choose 3-5 metrics that indicate bot health:
- **Input metrics:** What the bot processes (volume, quality)
- **Output metrics:** What the bot produces (completion rate, accuracy)
- **Quality metrics:** How well it performs (error rate, user satisfaction)

## Future Enhancements

### Affinity Matrix (Planned)

Track relationships between bots:
- High affinity → Cooperative, agreeable interactions
- Low affinity → Constructive friction, challenging discussions
- Dynamic updates based on interaction history

### RPG Stats Integration (Planned)

Map role card metrics to RPG-style attributes:
- **VRL (Viral):** Engagement/impact metrics
- **SPD (Speed):** Completion time metrics  
- **RCH (Reach):** Distribution/output metrics
- **TRU (Trust):** Success rate + relationship quality
- **WIS (Wisdom):** Knowledge accumulated
- **CRE (Creative):** Innovation/quality metrics

### Automated Role Card Evolution (Planned)

Bots propose role card updates based on:
- Violations detected (add new bans)
- Successful patterns (add to definition of done)
- Performance metrics (adjust escalation thresholds)

## Summary

The new role card system provides:

1. **Complete constraint definition** - 6 layers covering all aspects of bot behavior
2. **Clear separation of concerns** - Role cards (constraints) vs IDENTITY (personality) vs SOUL (voice)
3. **User editability** - File-based storage with workspace/global scope
4. **Bot learning integration** - Proposals for updates based on experience
5. **Runtime enforcement** - Hard ban checking before action execution
6. **Escalation framework** - Clear triggers for human intervention

This architecture ensures bots operate within well-defined boundaries while maintaining unique personalities and voices.
