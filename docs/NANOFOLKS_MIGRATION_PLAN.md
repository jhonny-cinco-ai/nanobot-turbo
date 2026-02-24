# Nanobot to Nanofolks Migration Plan

## Executive Summary

This document outlines a comprehensive migration from **nanofolks** to **nanofolks** - a complete rebranding of the entire project. This is not a partial migration with fallbacks, but a full, systematic rename across all files, directories, configurations, and code.

**Current State:** ~150 Python files with "nanofolks" references
**Target State:** Zero "nanofolks" references, complete "nanofolks" branding

---

## Migration Scope

### 1. Root Package Rename

| Item | Current | Target | Files Affected |
|------|---------|--------|----------------|
| Package Name | `nanofolks-ai` | `nanofolks` | `pyproject.toml` |
| CLI App Name | `nanofolks` | `nanofolks` | `nanofolks/cli/*.py` |
| Root Directory | `./nanofolks/` | `./nanofolks/` | All Python imports |
| Logo | `🐈` | `🐱` (or new) | `nanofolks/__init__.py` |

### 2. Directory Structure Migration

```
Current:                          Target:
├── nanofolks/                      ├── nanofolks/
│   ├── agent/                    │   ├── agent/
│   ├── bots/                     │   ├── bots/
│   ├── channels/                 │   ├── channels/
│   ├── cli/                      │   ├── cli/
│   ├── config/                   │   ├── config/
│   ├── coordinator/              │   ├── coordinator/
│   ├── routines/                 │   ├── routines/
│   ├── memory/                   │   ├── memory/
│   ├── models/                   │   ├── models/
│   ├── providers/                │   ├── providers/
│   ├── session/                  │   ├── session/
│   ├── soul/                    │   ├── soul/
│   ├── teams/                   │   ├── teams/
│   └── utils/                    │   ├── utils/
```

### 3. User Data Directory Migration

| Item | Current | Target |
|------|---------|--------|
| Config Directory | `~/.nanofolks/` | `~/.nanofolks/` |
| Config File | `~/.nanofolks/config.json` | `~/.nanofolks/config.json` |
| Sessions | `~/.nanofolks/sessions/` | `~/.nanofolks/sessions/` |
| Workspace | `~/.nanofolks/workspace/` | `~/.nanofolks/workspace/` |
| Work Logs | `~/.nanofolks/work_logs.db` | `~/.nanofolks/work_logs.db` |
| Memory DB | `~/.nanofolks/memory.db` | `~/.nanofolks/memory.db` |
| Media | `~/.nanofolks/media/` | `~/.nanofolks/media/` |
| Bridge | `~/.nanofolks/bridge/` | `~/.nanofolks/bridge/` |
| History | `~/.nanofolks/history/` | `~/.nanofolks/history/` |
| Routines | `~/.nanofolks/routines_engine/` (legacy) | `~/.nanofolks/routines/` |
| Skill Verification | `.nanofolks/skill-verification/` | `.nanofolks/skill-verification/` |

### 4. Environment Variable Migration

| Current | Target |
|---------|--------|
| `NANOBOT_*` | `NANOFOLKS_*` |

### 5. Hardcoded Path Migration

| Location | Current Path | Target Path |
|----------|-------------|-------------|
| `schema.py` | `~/.nanofolks/workspace` | `~/.nanofolks/workspace` |
| `schema.py` | `~/.nanofolks/config.json` | `~/.nanofolks/config.json` |
| `schema.py` | `NANOBOT_` env prefix | `NANOFOLKS_` env prefix |
| `configure.py` | `/projects/nanofolks-turbo` | Update or remove |
| `configure.py` | `~/.nanofolks` | `~/.nanofolks` |
| `loader.py` | `~/.nanofolks/config.json` | `~/.nanofolks/config.json` |
| `loop.py` | `~/.nanofolks/config.json` | `~/.nanofolks/config.json` |
| `commands.py` | `~/.nanofolks/bridge/` | `~/.nanofolks/bridge/` |
| `commands.py` | `~/.nanofolks/history/` | `~/.nanofolks/history/` |
| `skills.py` | `.nanofolks/skill-verification/` | `.nanofolks/skill-verification/` |
| `telegram.py` | `~/.nanofolks/media/` | `~/.nanofolks/media/` |
| `discord.py` | `~/.nanofolks/media/` | `~/.nanofolks/media/` |
| `routing_stage.py` | `~/.nanofolks/routines_engine/` (legacy) | `~/.nanofolks/routines/` |
| `helpers.py` | `~/.nanofolks` | `~/.nanofolks` |

### 6. Python Import Migration

```python
# Before
from nanofolks import __logo__
from nanofolks.config.loader import load_config
from nanofolks.bots.base import SpecialistBot
from nanofolks.agent.loop import AgentLoop

# After
from nanofolks import __logo__
from nanofolks.config.loader import load_config
from nanofolks.bots.base import SpecialistBot
from nanofolks.agent.loop import AgentLoop
```

### 5. CLI Commands Migration

| Command | Current | Target |
|---------|---------|--------|
| Main CLI | `nanofolks agent` | `nanofolks agent` |
| Config | `nanofolks configure` | `nanofolks configure` |
| Team | `nanofolks team` | `nanofolks team` |
| Memory | `nanofolks memory` | `nanofolks memory` |

### 6. Bot Role Names

| Current | Target | Status |
|---------|--------|--------|
| `nanofolks` (leader) | `leader` | ✅ Already migrated |

The `nanofolks` → `leader` migration is already complete. All bot roles are now:
- `leader` (formerly nanofolks)
- `researcher`
- `coder`
- `creative`
- `social`
- `auditor`
- `coordinator`

**Note:** CLI help text still references `nanofolks` in some places (e.g., `bot_name` argument descriptions). These should be updated to use `leader` instead of `nanofolks`.

---

## Detailed File Migration Checklist

### Phase 1: Core Package Files (Critical)

| File | Changes Required |
|------|------------------|
| `pyproject.toml` | `name = "nanofolks-ai"` → `name = "nanofolks"` |
| `nanofolks/__init__.py` | Rename to `nanofolks/__init__.py`, update `__logo__` |
| `nanofolks/__main__.py` | Rename to `nanofolks/__main__.py`, update imports |

### Phase 2: CLI Module

| File | Changes Required |
|------|------------------|
| `nanofolks/cli/commands.py` | `name="nanofolks"` → `name="nanofolks"`, update all imports |
| `nanofolks/cli/main.py` | Update app name, imports |
| `nanofolks/cli/configure.py` | Update app name, imports |
| `nanofolks/cli/onboarding.py` | Update all "nanofolks" references |
| `nanofolks/cli/memory_commands.py` | Update app name, imports |
| `nanofolks/cli/room_ui.py` | Update imports |

### Phase 3: All Python Modules (150 files)

Every Python file needs:
1. Update import statements (`from nanofolks.X` → `from nanofolks.X`)
2. Update internal references
3. Update docstrings mentioning "nanofolks"
4. Update hardcoded paths (`~/.nanofolks/` → `~/.nanofolks/`)
5. Update environment variable prefixes (`NANOBOT_` → `NANOFOLKS_`)

**Affected Directories:**
- `nanofolks/agent/` (15+ files) - tools, loop, context, etc.
- `nanofolks/bots/` (8 files) - base, implementations, dispatch, etc.
- `nanofolks/channels/` (12 files)
- `nanofolks/config/` (3 files)
- `nanofolks/coordinator/` (5 files)
- `nanofolks/routines/` (multiple)
- `nanofolks/memory/` (13 files)
- `nanofolks/models/` (multiple)
- `nanofolks/providers/` (3 files)
- `nanofolks/session/` (multiple)
- `nanofolks/soul/` (multiple)
- `nanofolks/teams/` (3 files)
- `nanofolks/utils/` (3 files)

### Phase 4: Configuration Files & Hardcoded Paths

| File | Changes Required |
|------|------------------|
| `~/.nanofolks/config.json` | Rename to `~/.nanofolks/config.json` |
| `~/.nanofolks/team_config.json` | Migrate to new location |
| `~/.nanofolks/bot_custom_names.json` | Migrate to new location |
| `nanofolks/config/schema.py` | Update hardcoded paths (~/.nanofolks → ~/.nanofolks, NANOBOT_ → NANOFOLKS_) |
| `nanofolks/config/loader.py` | Update config path |
| `nanofolks/agent/loop.py` | Update protected_paths default |
| `nanofolks/cli/configure.py` | Update example paths |
| `nanofolks/cli/commands.py` | Update bridge, history paths |
| `nanofolks/utils/helpers.py` | Update data directory path |
| `nanofolks/channels/telegram.py` | Update media path |
| `nanofolks/channels/discord.py` | Update media path |
| `nanofolks/session/manager.py` | Update sessions path |
| `nanofolks/agent/skills.py` | Update verification dir |
| `nanofolks/agent/stages/routing_stage.py` | Update cron path |

### Phase 5: Documentation Files (52+ files)

All markdown files need "nanofolks" → "nanofolks" updates:
- `README.md` - Complete rewrite with new branding
- `FUTURE_README.md` - Update all references
- `START_HERE.md` - New user onboarding
- `docs/` - All documentation files

### Phase 6: Workspace Templates

| Directory | Changes |
|-----------|---------|
| `nanofolks/templates/` | Rename to `nanofolks/templates/` |
| `nanofolks/templates/soul/` | Update template references |
| `nanofolks/templates/identity/` | Update template references |

---

## Implementation Strategy

### Step 1: Create New Directory Structure

```bash
# Create new package directory
mkdir -p nanofolks

# Copy all files (will rename in next step)
cp -r nanofolks/* nanofolks/
```

### Step 2: Batch Replace All Imports

```bash
# Replace in all Python files
find nanofolks -name "*.py" -exec sed -i '' 's/from nanofolks\./from nanofolks./g' {} \;
find nanofolks -name "*.py" -exec sed -i '' 's/import nanofolks/import nanofolks/g' {} \;
```

### Step 3: Rename CLI App Names

```bash
# Update typer app names
find nanofolks -name "*.py" -exec sed -i '' 's/name="nanofolks"/name="nanofolks"/g' {} \;
```

### Step 4: Update Package Metadata

```toml
# pyproject.toml
name = "nanofolks"
```

### Step 5: Update Environment Variable Prefixes

```bash
# Replace environment variable prefixes
find nanofolks -name "*.py" -exec sed -i '' 's/NANOBOT_/NANOFOLKS_/g' {} \;
```

### Step 6: Update Hardcoded Paths

```bash
# Replace ~/.nanofolks with ~/.nanofolks
find nanofolks -name "*.py" -exec sed -i '' 's|~/.nanofolks|~/.nanofolks|g' {} \;

# Replace example paths like /projects/nanofolks-turbo
find nanofolks -name "*.py" -exec sed -i '' 's|/projects/nanofolks-turbo|/projects/nanofolks|g' {} \;
```

### Step 7: Update Data Directory References

```bash
# Create new config directory
mkdir -p ~/.nanofolks

# Move all data
mv ~/.nanofolks/config.json ~/.nanofolks/
mv ~/.nanofolks/sessions/ ~/.nanofolks/
mv ~/.nanofolks/workspace/ ~/.nanofolks/
mv ~/.nanofolks/work_logs.db ~/.nanofolks/
# ... etc
```

### Step 6: Update Documentation

```bash
# Replace all references
find . -name "*.md" -exec sed -i '' 's/nanofolks/nanofolks/g' {} \;
```

---

## Breaking Changes

### Users Must:

1. **Reinstall the package** - New package name `nanofolks`
2. **Migrate config** - Move `~/.nanofolks/` → `~/.nanofolks/`
3. **Update CLI commands** - `nanofolks agent` → `nanofolks agent`
4. **Re-download models** - If embeddings cache is invalidated

### Developers Must:

1. **Update imports** - `from nanofolks import X`
2. **Update CI/CD** - Any scripts using `nanofolks` command
3. **Update Docker images** - If applicable

---

## Migration Command Reference

### Pre-Migration Backup

```bash
# Backup entire project
cp -r nanofolks nanofolks_backup

# Backup user data
cp -r ~/.nanofolks ~/.nanofolks_backup
```

### Post-Migration Verification

```bash
# Verify no nanofolks references remain
find . -type f \( -name "*. -name "*.md" -o -name "*.py" -ojson" \) | xargs grep -l "nanofolks" | grep -v backup

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
| Phase 3: Python | 150 | 5-7 hours |
| Phase 4: Config & Paths | 15+ | 1 hour |
| Phase 5: Docs | 52+ | 2 hours |
| Phase 6: Templates | 20+ | 1 hour |

**Total Estimated: 10-13 hours**

---

## Rollback Plan

If migration fails:

1. **Restore from backup:**
   ```bash
   rm -rf nanofolks
   mv nanofolks_backup nanofolks
   rm -rf ~/.nanofolks
   mv ~/.nanofolks_backup ~/.nanofolks
   ```

2. **Keep dual support (temporary):**
   - Keep `nanofolks/` as wrapper that imports from `nanofolks/`
   - But this defeats the purpose of clean migration

---

## Decision Points

### 1. Package Name
- **Option A:** `nanofolks` (recommended - aligns with character names)
- **Option B:** `nano-folks` (hyphenated)
- **Option C:** `nanofolks-turbo` (keep current, but this is repo name)

### 2. Logo/Emoji
- Keep `🐈` cat emoji
- Or create new nanofolks-specific emoji

### 3. GitHub Repository
- Rename repository: `nanofolks-turbo` → `nanofolks`
- Or keep current repo name, update branding inside

### 4. Version Number
- Continue from `0.1.0` 
- Or start fresh at `1.0.0` (new project launch)

### 5.Backward Compatibility
- **Full migration** (no backward compat) - Recommended for clean break
- **Alias wrapper** (temporary) - Create `nanofolks` as alias to `nanofolks`

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
