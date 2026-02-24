# Role Card System Implementation Summary

## What Was Fixed/Implemented

### 1. Complete 6-Layer Role Card Structure

**Before:**
- Minimal dataclass with only: bot_name, domain, capabilities, version, metadata
- Missing: hard_bans, escalation_triggers, definition_of_done, inputs/outputs, metrics

**After:**
Full 6-layer structure based on the multi-agent architecture article:
1. **Domain** - What the bot owns (with detailed description)
2. **Inputs/Outputs** - What it receives and delivers
3. **Definition of Done** - When is "done" actually done
4. **Hard Bans** - What must NEVER be done (e.g., "No direct posting")
5. **Escalation Triggers** - When to stop and ask for help
6. **Metrics** - KPIs for performance tracking

### 2. Complete Role Cards for All 6 Bots

Each bot now has a complete, specific role card:

**Leader (Coordinator):**
- Hard bans: No production deploys without approval, no overriding specialists without reason
- Escalation: Legal risks, high-stakes decisions, bot conflicts

**Researcher:**
- Hard bans: No fabricated citations, no unverified claims as fact
- Escalation: Conflicting data, insufficient sources

**Coder:**
- Hard bans: No commits to main without PR, no hardcoded credentials
- Escalation: Security vulnerabilities, architectural decisions

**Social:**
- Hard bans: No direct posting (drafts only), no made-up statistics
- Escalation: Numeric claims, controversial topics

**Creative:**
- Hard bans: No invented facts, no copyrighted material
- Escalation: Brand guideline conflicts

**Auditor:**
- Hard bans: No approving security issues, no personal attacks, no fabricated findings
- Escalation: Critical vulnerabilities, compliance violations

### 3. File-Based Storage System

**New `RoleCardStorage` class:**
- Workspace overrides: `.nanofolks/role_cards/{bot_name}.yaml`
- Global overrides: `~/.config/nanofolks/role_cards/{bot_name}.yaml`
- Priority order: workspace → global → built-in defaults
- Editable by users and bots

**Key methods:**
```python
storage = get_role_card_storage(workspace_path)
role_card = storage.get_role_card("social")  # Loads with priority
storage.save_role_card(role_card, scope="workspace")
storage.save_bot_proposal(bot_name, changes, reason)  # For learning system
```

### 4. Role Cards in Prompt Context

**Context Builder Updated (`agent/context.py`):**

Prompt now loads in this order:
```
1. ROLE CARD (constraints & boundaries) ← NEW! Loaded FIRST
2. IDENTITY.md (personality & relationships)
3. SOUL.md (voice & tone)
4. AGENTS.md (task instructions)
5. Memory/Skills/Context
```

**New method `_get_role_card_section()`:**
- Loads role card with user override priority
- Formats as prompt-friendly text
- Includes all 6 layers (domain, inputs/outputs, DoD, hard bans, escalation, metrics)

### 5. Hard Ban Enforcement

**Fixed `can_perform_action()` in `bots/base.py`:**
```python
def can_perform_action(self, action: str, context: Optional[Dict] = None) -> tuple[bool, Optional[str]]:
    return self.role_card.check_hard_bans(action, context)
```

**New `check_hard_bans()` method:**
- Keyword matching against action descriptions
- Returns (is_allowed, violation_message)
- Can be enhanced with more sophisticated logic

### 6. Escalation System Integration

**New `should_escalate()` method:**
```python
def should_escalate(self, situation: str, confidence: float = 1.0) -> tuple[bool, str]:
    # Checks escalation_triggers
    # Also escalates on low confidence (< 50%)
```

**Usage in escalation flow:**
1. Bot detects trigger via `should_escalate()`
2. Bot calls `escalate_to_coordinator()` (already existed)
3. Coordinator logs to work log with `add_escalation()` (already existed)

### 7. Clear Separation of Concerns

**Three Complementary Systems:**

1. **ROLE CARD** - Constraints & Boundaries
   - What CAN and CANNOT be done
   - Hard bans, escalation triggers, DoD
   - SHRINKS behavior space
   - File: YAML in `.nanofolks/role_cards/`

2. **IDENTITY.md** - Personality & Relationships
   - Who the bot is
   - Backstory, quirks, relationships with other bots
   - File: `bots/{bot_name}/IDENTITY.md`

3. **SOUL.md** - Voice & Tone
   - How the bot speaks
   - Communication style, word choice
   - File: `bots/{bot_name}/SOUL.md`

4. **AGENTS.md** - Task Instructions
   - What to do
   - Specific workflows and guidelines
   - File: `bots/{bot_name}/AGENTS.md`

**No more redundancy!** Each system has a clear, distinct purpose.

## Files Modified

### 1. `nanofolks/models/role_card.py` (Complete Rewrite)
- Full 6-layer RoleCard dataclass
- All 6 bot role cards defined
- RoleCardStorage class for persistence
- Backward-compatible attributes (title, greeting, voice, display_name)

### 2. `nanofolks/agent/context.py` (Updated)
- Added `_get_role_card_section()` method
- Modified `build_system_prompt()` to include role cards FIRST
- Fixed capability attribute names (can_access_web, can_exec_commands)

### 3. `nanofolks/bots/base.py` (Updated)
- Fixed `can_perform_action()` to use new `check_hard_bans()` method
- Maintains backward compatibility with display name methods

### 4. `docs/ROLE_CARD_ARCHITECTURE.md` (New)
- Complete documentation of the new system
- Architecture explanation
- Usage examples
- Migration guide

## How to Use

### View Current Role Card
```python
from nanofolks.models import get_role_card

role_card = get_role_card("social")
print(role_card.format_for_prompt())
```

### Edit Role Card (User)
```python
from nanofolks.models import get_role_card_storage

storage = get_role_card_storage(Path("/path/to/workspace"))
role_card = storage.get_role_card("social")

# Modify
role_card.hard_bans.append("No posting about competitors without approval")

# Save
storage.save_role_card(role_card, scope="workspace")
```

### Or Edit YAML Directly
```yaml
# .nanofolks/role_cards/social.yaml
bot_name: social
domain: community
hard_bans:
  - No direct posting to social media (drafts only)
  - No making up statistics or numbers
  - No internal formats or tool traces in public content
escalation_triggers:
  - Numeric claims or comparisons requiring verification
  - Controversial or sensitive topics
```

### Bot Proposes Update (via Learning)
```python
storage.save_bot_proposal(
    bot_name="social",
    proposed_changes={"hard_bans": ["New ban learned from mistake"]},
    reason="Learned from incident where I leaked internal paths"
)
```

### Check Hard Bans in Code
```python
from nanofolks.bots import SocialBot

bot = SocialBot()
is_allowed, error = bot.can_perform_action("post directly to Twitter")
if not is_allowed:
    print(f"Blocked: {error}")  # "Action violates hard ban: 'No direct posting'"
```

## Integration with Existing Systems

### Turbo Memory Integration
- Hard ban violations are logged as lessons
- Future prompts include: "Remember: Never do X (violates ban Y)"
- Metrics feed into RPG-style stats

### Learning Exchange Integration
- Bots can propose role card updates via `save_bot_proposal()`
- Proposals saved as drafts requiring user approval
- Prevents bots from self-modifying without oversight

### Work Log Integration
- Escalations logged with `add_escalation()`
- Hard ban violations logged as errors
- Metrics tracked over time

### Context Builder Integration
- Role cards loaded FIRST in prompt assembly
- Ensures constraints are established before personality/voice
- Format is prompt-friendly with clear section headers

## Backward Compatibility

### API Compatibility
```python
# Old code still works
from nanofolks.models import get_role_card

role_card = get_role_card("researcher")
role_card.domain  # Still works
role_card.capabilities.can_access_web  # Still works
```

### New Features Available
```python
# New features accessible
role_card.hard_bans  # NEW
role_card.escalation_triggers  # NEW
role_card.definition_of_done  # NEW
role_card.check_hard_bans(action)  # NEW
role_card.should_escalate(situation)  # NEW
role_card.format_for_prompt()  # NEW
```

### Storage Priority
- Existing bot implementations use `get_role_card()` which now includes storage
- User overrides automatically take priority
- No code changes needed for existing bots

## Key Improvements

1. **Hard bans are now defined** - Clear prohibitions prevent common mistakes
2. **Escalation is explicit** - Bots know when to ask for help
3. **Completion criteria** - Definition of done for each bot type
4. **User editable** - YAML files users can modify
5. **Bot learning support** - Proposals for updates based on experience
6. **Prompt integration** - Role cards now included in system prompts
7. **Clear architecture** - No confusion between SOUL/IDENTITY/ROLE_CARD

## Next Steps

1. **Test the implementation** - Run through various scenarios
2. **Update bot checks** - Use `should_escalate()` in routine checks
3. **Add to agent loop** - Explicit hard ban checking before tool execution
4. **Monitor metrics** - Track role card effectiveness over time
5. **User feedback** - Gather feedback on default role cards
6. **Refine bans** - Adjust hard bans based on real usage patterns

## Design Philosophy

The new system follows the core principle from the article:

> **"Don't think 'what should it do?' Think 'if it screws up, what's the worst case?' Then write bans targeting those worst cases."**

Every hard ban exists because it could prevent a real problem:
- "No direct posting" → Prevents tweets without approval
- "No made-up citations" → Prevents research poisoning
- "No hardcoded credentials" → Prevents security leaks

The role card SHRINKS the behavior space, making bots more reliable and predictable.
