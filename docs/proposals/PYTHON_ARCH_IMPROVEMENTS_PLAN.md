# Python Architecture Improvements Plan

**Purpose**: Improve the current Python codebase while aligning with the upcoming Go port. This is an **incremental** plan: low‑risk fixes now, larger refactors later.

**Philosophy**: The platform is a team of bots with personalities. These improvements make that multi‑bot experience more consistent, reliable, and easier to evolve.

---

## Summary of Improvements

**Do Now (Python) — Low Risk, High ROI**
- ID normalization helpers (RoomID / SessionID)
- Single `MessageEnvelope` type
- Unified `SecretStore` interface
- Team vs Team naming cleanup
- `TeamProfile` read‑only aggregator

**Later (Go Port or Post‑Parity) — Higher Risk**
- Unify DM rooms into standard rooms
- Merge Cron + CrewRoutines into one scheduler
- Single orchestrator pipeline (tags → intent → dispatch → aggregation)
- `MemoryPolicy` per room
- Treat CLI/GUI as channels
- Explicit task ownership + handoff rules

---

## Do Now (Python)

### 1) ID Normalization Helpers
**Goal**: One canonical format for room/session IDs.

**Why**: Reduces bugs caused by mixed formats like `room:general`, `general`, `#general`, or `room:cli_default`.

**Touchpoints**:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/session/dual_mode.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/agent/intent_flow_router.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/agent/work_log_manager.py`

**Expected result**: A small utility module (`room_id.py` or similar) used everywhere.

---

### 2) Single `MessageEnvelope` Type
**Goal**: One message shape for broker, bus, channels, memory, and tools.

**Why**: Right now each layer has its own message shape. A single envelope makes multi‑bot flows reliable and portable to Go.

**Touchpoints**:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bus/events.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/broker/room_broker.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/channels/*`

**Expected result**: A shared dataclass used end‑to‑end, including metadata like `room_id`, `sender`, `bot_name`, `trace_id`, and `content_parts`.

---

### 3) Unified `SecretStore` Interface
**Goal**: One interface for Keyring, KeyVault, and symbolic references.

**Why**: Simplifies security and makes future Go port easier.

**Touchpoints**:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/security/keyring_manager.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/security/keyvault.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/security/symbolic_converter.py`

**Expected result**: One interface with platform drivers under the hood.

---

### 4) Team vs Team Naming Cleanup
**Goal**: Use consistent language in code and docs.

**Why**: The current code mixes “team” and “team” which makes the UX confusing.

**Touchpoints**:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/teams/manager.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/README.md`

**Expected result**: Clean and consistent naming for users and developers.

---

### 5) `TeamProfile` Read‑Only Aggregator
**Goal**: Provide a unified “team profile” object for each room.

**Why**: It simplifies multi‑bot orchestration and UI rendering.

**Touchpoints**:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/soul/manager.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/templates/*`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bots/reasoning_configs.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/agent/tools/permissions.py`

**Expected result**: A simple object that merges SOUL, identity, reasoning, and permissions.

---

## Later (Go Port or Post‑Parity)

### A) Unify DM Rooms into Standard Rooms
**Why later**: Requires storage migration and API changes.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bots/dm_room_manager.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bots/room_manager.py`

---

### B) Merge Cron + CrewRoutines Scheduler
**Why later**: Deep architectural change, best done cleanly in Go.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/routines/engine/*`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/routines/crew/*`

---

### C) Single Orchestrator Pipeline
**Why later**: Impacts core multi‑bot behavior and user flow.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/agent/intent_flow_router.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bots/dispatch.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/systems/tag_handler.py`

---

### D) `MemoryPolicy` per Room
**Why later**: Requires careful tuning to avoid regressions.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/memory/*`

---

### E) Treat CLI/GUI as Channels
**Why later**: Requires GUI channel design and a unified connector interface.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/cli/*`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/channels/*`

---

### F) Explicit Task Ownership + Handoff
**Why later**: Product‑level behavior change, needs design time.

Touchpoints:
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/bots/dispatch.py`
- `/Users/rickovelar/Desktop/WORK/AI_Experiments/nanofolks-project/nanofolks/nanofolks/coordinator/*`

---

## Suggested Order (Python)

1. ID normalization helpers
2. MessageEnvelope type
3. SecretStore unification
4. Team vs Team naming cleanup
5. TeamProfile aggregator

---

## Exit Criteria (Python)

- IDs are consistent in logs, sessions, and room metadata.
- MessageEnvelope is used across broker, bus, channels, and tools.
- Secrets resolve through one interface.
- Team/team language is consistent in UI and docs.
- TeamProfile can be queried for any room and bot.

