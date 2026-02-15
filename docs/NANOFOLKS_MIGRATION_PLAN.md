# Nanobot to Nanofolks Migration Plan

## Executive Summary

This document outlines a comprehensive migration from **nanobot** to **nanofolks** - a complete rebranding of the entire project. This is not a partial migration with fallbacks, but a full, systematic rename across all files, directories, configurations, and code.

**Current State:** 199 files containing "nanobot" references
**Target State:** Zero "nanobot" references, complete "nanofolks" branding

---

## Migration Scope

### 1. Root Package Rename

| Item | Current | Target | Files Affected |
|------|---------|--------|----------------|
| Package Name | `nanobot-ai` | `nanofolks` | `pyproject.toml` |
| CLI App Name | `nanobot` | `nanofolks` | `nanobot/cli/*.py` |
| Root Directory | `./nanobot/` | `./nanofolks/` | All Python imports |
| Logo | `🐈` | `🐱` (or new) | `nanobot/__init__.py` |

### 2. Directory Structure Migration

```
Current:                          Target:
├── nanobot/                      ├── nanofolks/
│   ├── agent/                    │   ├── agent/
│   ├── bots/                     │   ├── bots/
│   ├── channels/                 │   ├── channels/
│   ├── cli/                      │   ├── cli/
│   ├── config/                   │   ├── config/
│   ├── coordinator/              │   ├── coordinator/
│   ├── heartbeat/                │   ├── heartbeat/
│   ├── memory/                   │   ├── memory/
│   ├── models/                   │   ├── models/
│   ├── providers/                │   ├── providers/
│   ├── session/                  │   ├── session/
│   ├── soul/                    │   ├── soul/
│   ├── themes/                   │   ├── themes/
│   └── utils/                    │   ├── utils/
```

### 3. User Data Directory Migration

| Item | Current | Target |
|------|---------|--------|
| Config Directory | `~/.nanobot/` | `~/.nanofolks/` |
| Config File | `~/.nanobot/config.json` | `~/.nanofolks/config.json` |
| Sessions | `~/.nanobot/sessions/` | `~/.nanofolks/sessions/` |
| Workspace | `~/.nanobot/workspace/` | `~/.nanofolks/workspace/` |
| Work Logs | `~/.nanobot/work_logs.db` | `~/.nanofolks/work_logs.db` |
| Memory DB | `~/.nanobot/memory.db` | `~/.nanofolks/memory.db` |

### 4. Python Import Migration

```python
# Before
from nanobot import __logo__
from nanobot.config.loader import load_config
from nanobot.bots.base import SpecialistBot
from nanobot.agent.loop import AgentLoop

# After
from nanofolks import __logo__
from nanofolks.config.loader import load_config
from nanofolks.bots.base import SpecialistBot
from nanofolks.agent.loop import AgentLoop
```

### 5. CLI Commands Migration

| Command | Current | Target |
|---------|---------|--------|
| Main CLI | `nanobot agent` | `nanofolks agent` |
| Config | `nanobot configure` | `nanofolks configure` |
| Theme | `nanobot theme` | `nanofolks theme` |
| Memory | `nanobot memory` | `nanofolks memory` |

### 6. Bot Role Names

| Current | Target | Status |
|---------|--------|--------|
| `nanobot` (leader) | `leader` | ✅ Already migrated |

The `nanobot` → `leader` migration is already complete. All bot roles are now:
- `leader` (formerly nanobot)
- `researcher`
- `coder`
- `creative`
- `social`
- `auditor`

---

## Detailed File Migration Checklist

### Phase 1: Core Package Files (Critical)

| File | Changes Required |
|------|------------------|
| `pyproject.toml` | `name = "nanobot-ai"` → `name = "nanofolks"` |
| `nanobot/__init__.py` | Rename to `nanofolks/__init__.py`, update `__logo__` |
| `nanobot/__main__.py` | Rename to `nanofolks/__main__.py`, update imports |

### Phase 2: CLI Module

| File | Changes Required |
|------|------------------|
| `nanobot/cli/commands.py` | `name="nanobot"` → `name="nanofolks"`, update all imports |
| `nanobot/cli/main.py` | Update app name, imports |
| `nanobot/cli/configure.py` | Update app name, imports |
| `nanobot/cli/onboarding.py` | Update all "nanobot" references |
| `nanobot/cli/memory_commands.py` | Update app name, imports |
| `nanobot/cli/room_ui.py` | Update imports |

### Phase 3: All Python Modules (147 files)

Every Python file needs:
1. Update import statements (`from nanobot.X` → `from nanofolks.X`)
2. Update internal references
3. Update docstrings mentioning "nanobot"

**Affected Directories:**
- `nanobot/agent/` (10 files) - tools, loop, context, etc.
- `nanobot/bots/` (8 files) - base, implementations, dispatch, etc.
- `nanobot/channels/` (12 files)
- `nanobot/config/` (3 files)
- `nanobot/coordinator/` (5 files)
- `nanobot/heartbeat/` (multiple)
- `nanobot/memory/` (13 files)
- `nanobot/models/` (multiple)
- `nanobot/providers/` (3 files)
- `nanobot/session/` (multiple)
- `nanobot/soul/` (multiple)
- `nanobot/themes/` (3 files)
- `nanobot/utils/` (2 files)

### Phase 4: Configuration Files

| File | Changes Required |
|------|------------------|
| `~/.nanobot/config.json` | Rename to `~/.nanofolks/config.json` |
| `~/.nanobot/theme_config.json` | Migrate to new location |
| `~/.nanobot/bot_custom_names.json` | Migrate to new location |

### Phase 5: Documentation Files (52+ files)

All markdown files need "nanobot" → "nanofolks" updates:
- `README.md` - Complete rewrite with new branding
- `FUTURE_README.md` - Update all references
- `START_HERE.md` - New user onboarding
- `docs/` - All documentation files

### Phase 6: Workspace Templates

| Directory | Changes |
|-----------|---------|
| `nanobot/templates/` | Rename to `nanofolks/templates/` |
| `nanobot/templates/soul/` | Update template references |
| `nanobot/templates/identity/` | Update template references |

---

## Implementation Strategy

### Step 1: Create New Directory Structure

```bash
# Create new package directory
mkdir -p nanofolks

# Copy all files (will rename in next step)
cp -r nanobot/* nanofolks/
```

### Step 2: Batch Replace All Imports

```bash
# Replace in all Python files
find nanofolks -name "*.py" -exec sed -i '' 's/from nanobot\./from nanofolks./g' {} \;
find nanofolks -name "*.py" -exec sed -i '' 's/import nanobot/import nanofolks/g' {} \;
```

### Step 3: Rename CLI App Names

```bash
# Update typer app names
find nanofolks -name "*.py" -exec sed -i '' 's/name="nanobot"/name="nanofolks"/g' {} \;
```

### Step 4: Update Package Metadata

```toml
# pyproject.toml
name = "nanofolks"
```

### Step 5: Update Data Directory References

```bash
# Create new config directory
mkdir -p ~/.nanofolks

# Move all data
mv ~/.nanobot/config.json ~/.nanofolks/
mv ~/.nanobot/sessions/ ~/.nanofolks/
mv ~/.nanobot/workspace/ ~/.nanofolks/
mv ~/.nanobot/work_logs.db ~/.nanofolks/
# ... etc
```

### Step 6: Update Documentation

```bash
# Replace all references
find . -name "*.md" -exec sed -i '' 's/nanobot/nanofolks/g' {} \;
```

---

## Breaking Changes

### Users Must:

1. **Reinstall the package** - New package name `nanofolks`
2. **Migrate config** - Move `~/.nanobot/` → `~/.nanofolks/`
3. **Update CLI commands** - `nanobot agent` → `nanofolks agent`
4. **Re-download models** - If embeddings cache is invalidated

### Developers Must:

1. **Update imports** - `from nanofolks import X`
2. **Update CI/CD** - Any scripts using `nanobot` command
3. **Update Docker images** - If applicable

---

## Migration Command Reference

### Pre-Migration Backup

```bash
# Backup entire project
cp -r nanobot nanobot_backup

# Backup user data
cp -r ~/.nanobot ~/.nanobot_backup
```

### Post-Migration Verification

```bash
# Verify no nanobot references remain
find . -type f \( -name "*. -name "*.md" -o -name "*.py" -ojson" \) | xargs grep -l "nanobot" | grep -v backup

# Test imports
python3 -c "from nanofolks import __logo__; print(__logo__)"

# Test CLI
nanofolks --help
```

---

## Timeline Estimate

| Phase | Files | Estimated Time |
|-------|-------|----------------|
| Phase 1: Core | 3 | 30 min |
| Phase 2: CLI | 6 | 1 hour |
| Phase 3: Python | 147 | 4-6 hours |
| Phase 4: Config | 5 | 30 min |
| Phase 5: Docs | 52+ | 2 hours |
| Phase 6: Templates | 20+ | 1 hour |

**Total Estimated: 9-11 hours**

---

## Rollback Plan

If migration fails:

1. **Restore from backup:**
   ```bash
   rm -rf nanobot
   mv nanobot_backup nanobot
   rm -rf ~/.nanobot
   mv ~/.nanobot_backup ~/.nanobot
   ```

2. **Keep dual support (temporary):**
   - Keep `nanobot/` as wrapper that imports from `nanofolks/`
   - But this defeats the purpose of clean migration

---

## Decision Points

### 1. Package Name
- **Option A:** `nanofolks` (recommended - aligns with character names)
- **Option B:** `nano-folks` (hyphenated)
- **Option C:** `nanobot-turbo` (keep current, but this is repo name)

### 2. Logo/Emoji
- Keep `🐈` cat emoji
- Or create new nanofolks-specific emoji

### 3. GitHub Repository
- Rename repository: `nanobot-turbo` → `nanofolks`
- Or keep current repo name, update branding inside

### 4. Version Number
- Continue from `0.1.0` 
- Or start fresh at `1.0.0` (new project launch)

### 5.Backward Compatibility
- **Full migration** (no backward compat) - Recommended for clean break
- **Alias wrapper** (temporary) - Create `nanobot` as alias to `nanofolks`

---

## Next Steps

1. **Review this document** - Confirm migration scope
2. **Approve decision points** - Choose options above
3. **Create backup** - Before starting
4. **Execute in phases** - Test after each phase
5. **Update GitHub** - Repository rename after successful local test
6. **Announce** - Release notes, migration guide for users

---

*Document Version: 1.0*
*Created: 2026-02-15*
*Author: Development Team*
