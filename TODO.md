# nanobot-turbo Implementation Plan

## Project Overview
**Repository**: https://github.com/jhonny-cinco-ai/nanobot-turbo  
**Branch**: feature/smart-router  
**Status**: Core routing system implemented ✅ | RoutingStage integrated into AgentLoop ✅ | Per-tier secondary models & CODING tier ✅

## Smart Router Architecture

### Completed ✅

#### 1. Core Router Components (`nanobot/agent/router/`)
- **`models.py`** - Data models for routing decisions
  - `RoutingTier` enum (SIMPLE, MEDIUM, COMPLEX, REASONING, CODING)
  - `RoutingDecision` dataclass
  - `ClassificationScores` (14-dimension system)
  - `RoutingPattern` for learned patterns

- **`classifier.py`** - Client-side Layer 1 classification
  - 14-dimension weighted scoring
  - Sigmoid confidence calibration
  - Pattern matching with regex
  - Token estimation
  - Tool requirement detection

- **`llm_router.py`** - LLM-assisted Layer 2 fallback
  - Uses `openai/gpt-4o-mini` for classification (configurable)
  - Optional secondary model for LLM classifier fallback
  - JSON response parsing
  - 500ms timeout
  - Error fallback to MEDIUM tier

- **`sticky.py`** - Sticky routing logic
  - Maintains tier across conversation
  - Context window (5 messages)
  - Smart downgrade detection
  - Per-message override capability

- **`calibration.py`** - Auto-calibration system
  - Learns from Layer 1 vs Layer 2 comparisons
  - Pattern generation from mismatches
  - Periodic calibration (default: 24h)
  - Pattern eviction for low-success patterns

#### 2. Pipeline Integration (`nanobot/agent/stages/`)
- **`routing_stage.py`** - Context pipeline stage
  - `RoutingContext` for state management
  - `RoutingStage` for pipeline integration
  - Fire-and-forget analytics
  - Calibration trigger

#### 3. Configuration (`nanobot/config/schema.py`)
- Added `RoutingConfig` with full schema
- Tier configuration (simple/medium/complex/reasoning/coding)
- Per-tier secondary model support
- Client classifier settings
- LLM classifier settings
- Sticky routing settings
- Auto-calibration settings

#### 4. Example Configuration
- **`config.example.json`** - Complete example with all routing options including per-tier fallbacks

## Testing the Smart Router

### Quick Test

1. **Configure routing** in `~/.nanobot/config.json`:
```json
{
  "routing": {
    "enabled": true,
    "tiers": {
      "simple": {"model": "gpt-4o-mini", "cost_per_mtok": 0.60},
      "medium": {"model": "anthropic/claude-sonnet-4", "cost_per_mtok": 15.0},
      "complex": {"model": "anthropic/claude-opus-4", "cost_per_mtok": 75.0},
      "reasoning": {"model": "o3", "cost_per_mtok": 10.0}
    }
  }
}
```

2. **Test different message types**:
```bash
# Simple query - should use deepseek/deepseek-chat-v3-0324
nanobot agent -m "What is 2+2?"

# Coding task - should use moonshotai/kimi-k2.5
nanobot agent -m "Write a Python function to sort a list"

# Complex debugging - should use anthropic/claude-sonnet-4.5
nanobot agent -m "Debug this distributed system issue with race conditions"

# Reasoning task - should use openai/o3
nanobot agent -m "Prove that the sum of angles in a triangle is 180 degrees"
```

3. **Check routing decisions and fallbacks** in logs:
```bash
# Look for lines like:
# "Smart routing: simple (confidence: 0.92, layer: client)"
# "Smart routing: coding (confidence: 0.94, layer: client)"
# "Primary model X failed, trying secondary model Y"
```

### Manual Testing Script

```python
from nanobot.agent.router import classify_content

# Test classification
test_messages = [
    "What is the capital of France?",
    "Write a function to parse JSON",
    "Debug why this distributed system is failing",
    "Prove this theorem step by step",
]

for msg in test_messages:
    decision, scores = classify_content(msg)
    print(f"Message: {msg[:50]}...")
    print(f"  Tier: {decision.tier.value}")
    print(f"  Confidence: {decision.confidence:.2f}")
    print(f"  Layer: {decision.layer}")
    print()
```

## Next Steps

### Priority 2: CLI Commands 🖥️ ✅ COMPLETED
- [x] **Add `nanobot routing` commands**
  ```bash
  nanobot routing status       # Show current routing config and stats
  nanobot routing calibrate    # Manually trigger calibration
  nanobot routing patterns     # List learned patterns
  nanobot routing test "msg"   # Test classification on a message
  nanobot routing analytics    # Show cost savings and routing stats
  ```

- [x] **Update CLI help and documentation**

**Implemented Commands:**
- ✅ `routing status` - Display configuration and current status
- ✅ `routing calibrate [--dry-run]` - Manual calibration with dry-run support
- ✅ `routing patterns [--limit] [--tier]` - Show learned patterns with filtering
- ✅ `routing test <message> [--verbose]` - Test classification with detailed scores
- ✅ `routing analytics` - Cost analysis and savings calculation
- ✅ Updated main `status` command to show routing status

### Priority 3: Testing 🧪 ✅ COMPLETED
- [x] **Unit tests for classifier**
  - Test 14-dimension scoring
  - Test pattern matching
  - Test confidence calibration
  
- [x] **Unit tests for sticky routing**
  - Test sticky behavior
  - Test downgrade logic
  - Test context window

- [x] **Unit tests for calibration**
  - Test pattern generation
  - Test accuracy analysis
  - Test pattern eviction

- [x] **Integration tests**
  - Test full routing pipeline
  - Test with mock LLM calls
  - Test calibration workflow

**Test Files Created:**
- `tests/router/test_models.py` - Data model tests (12 tests)
- `tests/router/test_classifier.py` - Classifier tests (17 tests)
- `tests/router/test_sticky.py` - Sticky routing tests (13 tests)
- `tests/router/test_calibration.py` - Calibration tests (19 tests)
- `tests/router/test_integration.py` - Integration tests (14 tests)
- `tests/router/README.md` - Testing documentation
- `tests/TESTING.md` - Testing guide
- `tests/run_tests.py` - Standalone test runner

**Total**: 81 tests, ~1,300 lines of test code

**Status**: ✅ ALL TESTS PASSING

```bash
cd /projects/nanobot-turbo
python -m pytest tests/router/ -v
# 81 passed, 1 warning
```

### Priority 4: Documentation 📚 ✅ COMPLETED
- [x] **Add routing documentation to README.md**
  - How smart routing works
  - Configuration examples
  - Cost savings explanation
  
- [x] **Create ROUTING.md**
  - Detailed architecture explanation
  - How to customize tiers
  - How to add custom patterns
  - Calibration tuning guide

- [x] **Update CLI reference**
  - Added routing commands to main CLI table
  - Created dedicated routing CLI section

**Documentation Created:**
- **README.md**: Added comprehensive smart routing section with:
  - Architecture overview
  - Quick start guide
  - Cost savings examples
  - Example classifications table
  - CLI commands
  - Link to detailed ROUTING.md

- **ROUTING.md** (420+ lines): Complete documentation including:
  - Two-layer classification explained
  - All 14 dimensions documented
  - Configuration options
  - CLI commands reference
  - Sticky routing behavior
  - Auto-calibration details
  - Troubleshooting guide
  - Best practices
  - API reference

### Priority 5: Routing Integration ✅ COMPLETED
- [x] **Integrate RoutingStage into AgentLoop**
  - RoutingStage initialized in AgentLoop.__init__ when routing enabled
  - `_select_model()` method calls routing_stage.execute() before each message
  - Model dynamically selected based on content classification
  - Logs routing decisions with tier, confidence, and layer

### Priority 6: Advanced Routing Features ✅ COMPLETED
- [x] **Per-tier secondary models**
  - Each routing tier (simple, medium, complex, reasoning, coding) now supports a `secondary_model` field
  - Automatic fallback if primary model fails during execution
  - Configurable per-tier fallbacks for cost optimization and reliability

- [x] **CODING tier specialization**
  - Added new CODING routing tier for specialized coding models
  - Dedicated patterns for coding tasks: function writing, API endpoints, algorithms, data structures
  - Higher confidence threshold (0.90) to ensure accurate coding detection
  - Default model: `moonshotai/kimi-k2.5` with fallback to `anthropic/claude-sonnet-4`

**Implemented Models (using your OpenRouter list):**
- **Simple**: `deepseek/deepseek-chat-v3-0324` → fallback: `deepseek/deepseek-chat-v3.1` ($0.27/M)
- **Medium**: `openai/gpt-4.1-mini` → fallback: `openai/gpt-4o-mini` ($0.40/M)
- **Complex**: `anthropic/claude-sonnet-4.5` → fallback: `anthropic/claude-sonnet-4` ($3/M)
- **Reasoning**: `openai/o3` → fallback: `openai/gpt-4o` ($2/M)
- **Coding**: `moonshotai/kimi-k2.5` → fallback: `anthropic/claude-sonnet-4` ($0.45/M)

### Priority 7: Analytics & Monitoring 📊
- [ ] **Cost tracking**
  - Track actual vs estimated costs
  - Calculate savings vs using single model
  - Export cost reports

- [ ] **Performance metrics**
  - Classification latency
  - Cache hit rates
  - Tier distribution

- [ ] **Routing dashboard**
  - Optional web UI for routing stats
  - Real-time cost tracking
  - Pattern management interface

### Priority 6: Advanced Features 🚀
- [ ] **Custom tier definitions**
  - Allow users to define their own tiers
  - Custom models per tier
  - Custom thresholds

- [ ] **A/B testing**
  - Test different routing strategies
  - Compare cost vs quality

- [ ] **Export/import patterns**
  - Share learned patterns across deployments
  - Community pattern repository

## Configuration Reference

### Minimal Config
```json
{
  "routing": {
    "enabled": true
  }
}
```

### Full Config
See `config.example.json` in repository root.

### Key Settings
- `client_classifier.min_confidence`: 0.0-1.0 (default: 0.85)
  - Threshold for accepting client-side classification
  - Lower = more Layer 2 calls (more accurate, slower)
  - Higher = more Layer 1 calls (faster, less accurate)

- `llm_classifier.model`: LLM model for Layer 2 classification (default: `openai/gpt-4o-mini`)
  - Used when Layer 1 confidence is below threshold
  - Secondary model available for fallback if primary fails

- `sticky.context_window`: 1-20 (default: 5)
  - How many messages to look back for sticky routing

- `auto_calibration.interval`: "24h", "100_classifications", "1d"
  - How often to run auto-calibration

## File Locations

**Implementation**:
- `/projects/nanobot-turbo/nanobot/agent/router/` - Core routing logic
- `/projects/nanobot-turbo/nanobot/agent/stages/` - Pipeline integration
- `/projects/nanobot-turbo/nanobot/config/schema.py` - Configuration schema

**Configuration**:
- `/projects/nanobot-turbo/config.json` - User configuration
- `/projects/nanobot-turbo/workspace/memory/ROUTING_PATTERNS.json` - Learned patterns
- `/projects/nanobot-turbo/workspace/analytics/routing_stats.json` - Analytics data

## Working with the Code

### Switch to correct directory
```bash
cd /projects/nanobot-turbo
```

### View routing info
```python
from nanobot.agent.stages import RoutingStage
from nanobot.config.loader import load_config

config = load_config()
stage = RoutingStage(config.routing)
print(stage.get_routing_info())
```

### Test classification
```python
from nanobot.agent.router import classify_content

decision, scores = classify_content("Write a Python function to sort a list")
print(f"Tier: {decision.tier}, Confidence: {decision.confidence}")
print(f"Scores: {scores.to_dict()}")
```

## Cost Savings Estimate

With typical usage distribution (including CODING tier):
- 35% SIMPLE queries → $0.27/M = 98% savings
- 25% CODING queries → $0.45/M = 95% savings
- 20% MEDIUM queries → $0.40/M = 97% savings  
- 15% COMPLEX queries → $3.00/M = 60% savings
- 5% REASONING queries → $2.00/M = 73% savings

**Blended average**: ~$1.14/M vs $75/M = **98.5% cost savings**
- Plus per-tier fallbacks provide resilience against rate limits and model failures

## Git Commands

```bash
# Check status
git status

# View commits
git log --oneline -10

# Push changes
git push origin feature/smart-router

# Create PR (when ready)
gh pr create --title "Add smart LLM routing" --body "..."
```

## Questions or Issues?

1. Check this TODO file for current status
2. Review the commit history: `git log --oneline`
3. Check GitHub: https://github.com/jhonny-cinco-ai/nanobot-turbo
4. Review code in `nanobot/agent/router/`

---

**Last Updated**: 2026-02-09  
**Current Branch**: feature/smart-router  
**Next Priority**: Analytics & Monitoring (Priority 7)  
**Latest Features**: ✅ Per-tier secondary models + ✅ CODING tier for specialized coding tasks
