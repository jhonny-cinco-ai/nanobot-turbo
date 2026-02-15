# Migration Analysis: "nanobot" → "leader" Role Rename

## Executive Summary

This document outlines all files and code locations that would need changes to rename the "nanobot" role to "leader" when used in role/participant context. The current codebase uses "nanobot" as both:
1. **Package name** (the Python package itself)
2. **Bot name/role** (a participant in multi-agent orchestration)

This migration focuses on **changing only the role/participant usage**, leaving package names and module references intact.

---

## Impact Overview

| Category | Scope | Count | Risk |
|----------|-------|-------|------|
| Core Role Definition | `role_card.py` | 1 file | **MEDIUM** |
| Dispatcher/Routing | `dispatch.py` | 1 file | **HIGH** |
| Agent Logic | `agent/` modules | 6-7 files | **HIGH** |
| Room Management | `bots/room_manager.py` | 1 file | **MEDIUM** |
| Bot Implementations | `bots/implementations.py` | 1 file | **LOW** |
| Work Logging | `agent/work_log.py` | 1 file | **HIGH** |
| Documentation/Templates | Multiple docs | 10+ files | **LOW** |

---

## Detailed File Changes Required

### 1. **Core Role Definition** (MUST CHANGE)

#### File: `nanobot/models/role_card.py`
**Lines affected: 55-66**

```python
# CURRENT (lines 54-66)
BUILTIN_BOTS: Dict[str, RoleCard] = {
    "nanobot": RoleCard(
        bot_name="nanobot",
        domain=RoleCardDomain.COORDINATION,
        capabilities=BotCapabilities(
            can_invoke_bots=True,
            can_do_heartbeat=True,
            can_access_web=True,
            can_exec_commands=True,
            can_send_messages=True,
            max_concurrent_tasks=3,
        ),
    ),
    # ... rest of bots
```

**Changes needed:**
- [ ] Rename dict key from `"nanobot"` to `"leader"`
- [ ] Rename `bot_name` parameter from `"nanobot"` to `"leader"`
- Note: Keep the function `get_role_card()` and `list_bots()` working correctly

---

### 2. **Dispatcher & Routing** (MUST CHANGE - HIGHEST IMPACT)

#### File: `nanobot/bots/dispatch.py`
**Lines affected: 50-62, 107, 110, 126-127, 131, 242-252**

**Changes needed:**

1. **Bot mention mapping (lines 50-62):**
   ```python
   # CURRENT
   BOT_MENTIONS = {
       "@leader": "nanobot",      # ← Change value
       "@nanobot": "nanobot",     # ← Change value
       "@coordinator": "nanobot", # ← Change value
       # ... rest
   }
   
   # CHANGED TO
   BOT_MENTIONS = {
       "@leader": "leader",       # ← Maps @leader to leader
       "@nanobot": "leader",      # ← Keep for backwards compatibility OR remove
       "@coordinator": "leader",  # ← Maps @coordinator to leader
       # ... rest
   }
   ```
   
2. **Default dispatch logic (lines 107, 110, 126-127, 131):**
   - Replace all `["nanobot"]` with `["leader"]`
   - Replace all `"nanobot"` string literals with `"leader"`
   - Line 107: `["nanobot"]` → `["leader"]`
   - Line 110: `primary_bot="nanobot"` → `primary_bot="leader"`
   - Line 126: `["nanobot"]` → `["leader"]`
   - Line 127: `if p != "nanobot"` → `if p != "leader"`
   - Line 131: `primary_bot="nanobot"` → `primary_bot="leader"`

3. **Project suggestion templates (lines 241-252):**
   ```python
   suggestions = {
       "web": ["nanobot", "coder", "creative"],        # ← Change
       "mobile": ["nanobot", "coder", "creative"],      # ← Change
       "research": ["nanobot", "researcher"],           # ← Change
       "audit": ["nanobot", "auditor"],                 # ← Change
       "marketing": ["nanobot", "social", "creative"],  # ← Change
       "social": ["nanobot", "social"],                 # ← Change
       "content": ["nanobot", "creative", "social"],    # ← Change
       "general": ["nanobot"],                          # ← Change
   }
   ```

---

### 3. **Agent Work Logging** (MUST CHANGE - HIGH IMPACT)

#### File: `nanobot/agent/work_log.py`
**Multiple occurrences throughout the file**

**Changes needed:**
- [ ] Line ~20: `participants: List[str] = field(default_factory=lambda: ["nanobot"])` → `["leader"]`
- [ ] Line ~24: `bot_name: str = "nanobot"` → `"leader"`
- [ ] Line ~25: Comment `# Bot identity (single-bot: always "nanobot")` → update
- [ ] Line ~26: `triggered_by: str = "user"` comments mentioning nanobot
- [ ] Search for all comparisons with `"nanobot"`:
  - `self.bot_name != "nanobot"` → `self.bot_name != "leader"`
  - Default arguments with `bot_name: str = "nanobot"` → `= "leader"`
  - `triggered_by="nanobot"` → `triggered_by="leader"`
  - `coordinator: Optional[str] = None  # "nanobot" if in coordinator mode`

**Search pattern:** All occurrences of `"nanobot"` in this file need evaluation

---

### 4. **Room Management** (MUST CHANGE)

#### File: `nanobot/bots/room_manager.py`
**Occurrences: 2-3**

**Changes needed:**
- [ ] Default participants initialization:
  - `participants=["nanobot"]` → `participants=["leader"]`
  - In docstrings/comments mentioning default participants

---

### 5. **Bot Implementations** (MUST CHANGE)

#### File: `nanobot/bots/implementations.py`
**Occurrences: 1-2**

**Changes needed:**
- [ ] Constructor call: `get_role_card("nanobot")` → `get_role_card("leader")`
- [ ] Any direct references to `"nanobot"` role

---

### 6. **Agent Context & Routing** (MUST CHANGE)

#### File: `nanobot/agent/context.py`
**Occurrences: ~2**

**Changes needed:**
- [ ] `safe_bot_name = bot_name or "nanobot"` → `or "leader"`
- [ ] `is_leader = safe_bot_name == "nanobot"` → `== "leader"`

---

### 7. **Agent Loop** (MUST CHANGE)

#### File: `nanobot/agent/loop.py`
**Occurrences: ~3**

**Changes needed:**
- [ ] Default bot_name parameter: `bot_name: str = "nanobot"` → `= "leader"`
- [ ] Room participants initialization: `["nanobot"]` → `["leader"]`
- [ ] Soul file path: `"bots" / "nanobot"` → `"bots" / "leader"`
- [ ] Any conditional checks on bot_name

---

### 8. **Bot Invoker** (MUST CHANGE)

#### File: `nanobot/agent/bot_invoker.py`
**Occurrences: ~3**

**Changes needed:**
- [ ] Conditional: `if bot_name == "nanobot"` → `== "leader"`
- [ ] Bot creation: `bot_name="nanobot"` → `= "leader"`
- [ ] Triggered_by assignments: `triggered_by="nanobot"` → `= "leader"`

---

### 9. **Agent Skills** (CONDITIONAL CHANGE)

#### File: `nanobot/agent/skills.py`
**Occurrences: ~1**

**Changes needed:**
- [ ] Check context: `data.get("nanobot", {})` → `data.get("leader", {})`
- **Note:** Depends on skill file structure and whether it's bot-specific config

---

### 10. **Documentation & Templates** (SHOULD CHANGE)

#### Files affected:
- `ROOM_INTEGRATION_SUMMARY.md` - Multiple references (participants lists)
- `ROOM_QUESTIONS_ANSWERED.md` - Example output, command outputs
- `FUTURE_README.md` - Examples with bot mentions
- `docs/room_integration_changelog.md` - Examples and documentation
- `docs/room_interaction_cli_workflow.md` - CLI examples
- `docs/room_integration_cli.md` - CLI examples
- `docs/multi_bot_architecture_verification.md` - Architecture docs
- README.md - Bot listings and examples
- `docs/ROUTING_ENHANCEMENT_COMPLETE.md` - Routing examples

**Changes needed:**
- [ ] Replace `@nanobot` mentions with `@leader` in examples
- [ ] Update bot participant lists: `nanobot, coder, creative` → `leader, coder, creative`
- [ ] Update output examples showing participant lists
- [ ] Update role descriptions referencing "nanobot"

---

### 11. **Bot Template Files** (SHOULD CHANGE)

#### Directory: `workspace/bots/nanobot/`

**Files to rename:**
- [ ] Rename directory: `workspace/bots/nanobot/` → `workspace/bots/leader/`

**Files to update within:**
- [ ] `SOUL.md` - Update bot identity/references
- [ ] `AGENTS.md` - Update role instructions
- [ ] `IDENTITY.md` - Update identity references (if exists)
- Any other template files

---

## Backwards Compatibility Considerations

### Option A: Hard Migration (Breaking Change)
- Complete rename everywhere
- Update all examples and documentation
- Update any user configurations
- **Risk:** Users with existing rooms/configurations mentioning "nanobot" role will break

### Option B: Soft Migration (With Alias)
Implement both names as aliases:

```python
# In dispatch.py
BOT_MENTIONS = {
    "@leader": "leader",
    "@nanobot": "leader",      # ← Keep as alias
    "@coordinator": "leader",
}

# In role_card.py
BUILTIN_BOTS = {
    "leader": RoleCard(...),
    "nanobot": RoleCard(...),  # ← Alias pointing to same config
}
```

**Advantage:** Users with existing "nanobot" references still work
**Disadvantage:** Maintains duplicate configuration

---

## Implementation Strategy

### Phase 1: Core Changes (REQUIRED) ✅ COMPLETE
1. ✅ Update `role_card.py` - BUILTIN_BOTS definition
2. ✅ Update `dispatch.py` - All mention mappings and defaults
3. ✅ Update `work_log.py` - All default values and comparisons
4. ✅ Update `room_manager.py` - Default participants
5. ✅ Update `bot_invoker.py` - Role checks
6. ✅ Update `context.py` - Role logic
7. ✅ Update `loop.py` - Initialization and file paths
8. ✅ Update `implementations.py` - RoleCard lookup
9. ✅ Update `skills.py` - Metadata parsing

### Phase 2: Supporting Changes ✅ COMPLETE
1. ✅ All CLI and UI files updated (15+ files)
2. ✅ Theme and soul configuration updated
3. ✅ Database migrations updated
4. ✅ All runtime role checks updated
5. ⚠️  Template directory (workspace/bots/nanobot/) doesn't exist yet - will be created on first use

### Phase 3: Documentation & Examples ✅ COMPLETE
1. ✅ Updated all markdown documentation
2. ✅ Updated example commands and outputs
3. ✅ Updated guides with leader role references
4. ⏳ Inline code comments (non-critical, as commands.py still being worked on)

### Phase 4: Testing (PENDING)
1. [ ] Test room creation with new role
2. [ ] Test @leader mentions
3. [ ] Test default routing
4. [ ] Test multi-bot coordination
5. [ ] Test backwards compatibility (if implementing Option B)

---

## Testing Checklist

- [ ] Room creation includes "leader" as default participant
- [ ] `@leader` mentions work correctly
- [ ] `@nanobot` mentions work (if keeping alias)
- [ ] `@coordinator` mentions work
- [ ] Default dispatch routes through "leader"
- [ ] Work logs record "leader" correctly
- [ ] Role card lookup works for "leader"
- [ ] Template loading works for leader bot
- [ ] SOUL.md and AGENTS.md load correctly
- [ ] CLI shows "leader" in participant lists
- [ ] Multi-bot coordination still works
- [ ] Project room suggestions include "leader"

---

## Estimated Scope

| Task | Files | Complexity | Time |
|------|-------|-----------|------|
| Code changes | 9 files | HIGH | 2-3 hours |
| Template rename | 1 directory | LOW | 15 mins |
| Documentation | 10+ files | LOW | 1-2 hours |
| Testing | N/A | MEDIUM | 1-2 hours |
| **Total** | **20+ files** | **MEDIUM-HIGH** | **4-8 hours** |

---

## Risk Assessment

### High Risk Areas
1. **dispatch.py** - Touches core routing logic; affects all messages
2. **work_log.py** - Affects logging; widespread string comparisons
3. **role_card.py** - Central configuration; impacts role lookup

### Medium Risk Areas
1. **Template directory rename** - Must update file loading paths
2. **Documentation examples** - Could confuse users if not updated

### Low Risk Areas
1. **Implementations.py** - Single call site
2. **Skills.py** - Depends on usage pattern

---

## Success Criteria

✅ All bot role mentions use "leader" instead of "nanobot"
✅ Backwards compatibility maintained (with alias) OR all user configs updated
✅ All participant lists in documentation updated
✅ All examples show `@leader` mentions
✅ Room creation defaults to "leader" participant
✅ Multi-bot orchestration works seamlessly
✅ Tests pass with new role name
✅ No breaking changes to API unless intended (Option A)

