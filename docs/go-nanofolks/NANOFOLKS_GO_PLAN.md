# Nanofolks Go Plan (Unified v1 + v2)

**Purpose**: One source of truth for Go v1 parity and Go v2 improvements.

**Scope**:
- v1 = full parity with the current Python architecture
- v2 = post‑parity improvements that strengthen reliability, scale, and UX

**Go layout (confirmed)**
- `backend/internal/*` for app internals
- `cmd/cli` for CLI binary
- `cmd/desktop` for GUI binary
- `cmd/server` for server binary
- `frontend/*` for the Wails/Svelte UI

---

**V1 Parity Matrix**

## Core Runtime & Orchestration

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Agent loop + orchestration | `nanofolks/agent/loop.py` | `backend/internal/agent/loop.go` | Must preserve multi-bot pipeline and tool hooks. | Not started |
| Intent detection + flow router | `nanofolks/agent/intent_detector.py`, `nanofolks/agent/intent_flow_router.py` | `backend/internal/agent/intent/*` | Required for QUICK/FULL flows and cancellation logic. | Not started |
| Project state + phases | `nanofolks/agent/project_state.py` | `backend/internal/agent/project_state.go` | Must persist flow state by room/session. | Not started |
| Multi-bot generator | `nanofolks/agent/multi_bot_generator.py` | `backend/internal/agent/multi_bot.go` | Parity for simultaneous responses. | Not started |
| Routing + calibration + sticky | `nanofolks/agent/router/*` | `backend/internal/routing/*` | Keep model tier routing and sticky behavior. | Not started |
| Tag parsing system | `nanofolks/systems/tag_handler.py` | `backend/internal/systems/tags.go` | Required for `@bot` and `#room` tags. | Not started |

---

## Rooms, Sessions, Messaging, Broker

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Room manager + mappings | `nanofolks/bots/room_manager.py` | `backend/internal/rooms/manager.go` | Includes channel↔room mapping and persistence. | Not started |
| Room model | `nanofolks/models/room.py` | `backend/internal/rooms/types.go` | Must match schema and serialization. | Not started |
| Room-centric sessions | `nanofolks/session/dual_mode.py` | `backend/internal/session/room_sessions.go` | Room-keyed sessions with file persistence. | Not started |
| CAS storage | `nanofolks/storage/cas_storage.py` | `backend/internal/storage/cas_storage.go` | Needed for conflict-free concurrent writes. | Not started |
| Per-room broker | `nanofolks/broker/room_broker.py` | `backend/internal/broker/room_broker.go` | FIFO guarantees per room. | Not started |
| Group commit | `nanofolks/broker/group_commit.py` | `backend/internal/broker/group_commit.go` | Required for batch durability. | Not started |
| Bus + queue | `nanofolks/bus/*` | `backend/internal/bus/*` | Message event bus parity. | Not started |
| Bot DM rooms | `nanofolks/bots/dm_room_manager.py` | `backend/internal/rooms/dm_manager.go` | Persistent bot-to-bot DM history. | Not started |

---

## Bots & Coordination

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Bot definitions + registry | `nanofolks/bots/definitions.py`, `nanofolks/models/bot_registry.py` | `backend/internal/bots/definitions.go` | Preserve roles and configs. | Not started |
| Dispatch + coordinator | `nanofolks/bots/dispatch.py`, `nanofolks/coordinator/*` | `backend/internal/coordination/*` | Includes audit, decisions, circuit breaker. | Not started |
| Bot reasoning configs | `nanofolks/bots/reasoning_configs.py`, `nanofolks/reasoning/config.py` | `backend/internal/reasoning/*` | Per-bot reasoning modes. | Not started |
| Bot checks | `nanofolks/bots/checks/*` | `backend/internal/routines/checks/*` | Used by routines engine. | Not started |

---

## Memory & Knowledge

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Memory store + models | `nanofolks/memory/store.py`, `nanofolks/memory/models.py` | `backend/internal/memory/store.go` | Preserve schema and CRUD. | Not started |
| Embeddings + vector index | `nanofolks/memory/embeddings.py`, `nanofolks/memory/vector_index.py` | `backend/internal/memory/embeddings/*` | Required for vector memory. | Not started |
| Retrieval + summaries + graph | `nanofolks/memory/retrieval.py`, `nanofolks/memory/summaries.py`, `nanofolks/memory/graph.py` | `backend/internal/memory/*` | Context building and summarization. | Not started |
| Compaction + background jobs | `nanofolks/memory/session_compactor.py`, `nanofolks/memory/background.py` | `backend/internal/memory/compaction/*` | Needed for long sessions. | Not started |
| Preferences | `nanofolks/memory/preferences.py` | `backend/internal/memory/preferences.go` | Personalization state. | Not started |

---

## Scheduling, Routines, Dashboard

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Routines service + types | `nanofolks/routines/*` | `backend/internal/routines/*` | Include timezone support and job persistence. | Not started |
| Team routines manager | `nanofolks/crew_routines/*` | `backend/internal/routines/manager/*` | Internal checks and notifications. | Not started |
| Dashboard server | `nanofolks/crew_routines/dashboard_server.py` | `backend/internal/routines/dashboard_server.go` | HTTP + WS metrics. | Not started |

---

## Tools, Skills, MCP

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Tool registry + base tools | `nanofolks/agent/tools/*` | `backend/internal/tools/*` | File, shell, web, memory, permissions, MCP. | Not started |
| Tool permissions | `nanofolks/agent/tools/permissions.py` | `backend/internal/tools/permissions.go` | Per-bot restrictions. | Not started |
| MCP client | `nanofolks/agent/tools/mcp.py` | `backend/internal/mcp/*` | Includes symbolic secret resolution. | Not started |
| Skill packs | `nanofolks/skills/*` | `backend/internal/skills/*` | Discover and run local skills. | Not started |

---

## Security

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Keyring + keyvault | `nanofolks/security/keyring_manager.py`, `nanofolks/security/keyvault.py` | `backend/internal/security/keys/*` | Local-first secret storage. | Not started |
| Secure memory + sanitization | `nanofolks/security/secure_memory.py`, `nanofolks/security/sanitizer.py` | `backend/internal/security/*` | Must sanitize logs and UI. | Not started |
| Credential detection + audit | `nanofolks/security/credential_detector.py`, `nanofolks/security/audit_logger.py` | `backend/internal/security/audit/*` | Scans and audit trail. | Not started |
| Symbolic converter | `nanofolks/security/symbolic_converter.py` | `backend/internal/security/symbolic.go` | For MCP secret resolution. | Not started |

---

## Providers and Channels

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Provider registry + LLM | `nanofolks/providers/*` | `backend/internal/providers/*` | Preserve LiteLLM compatibility. | Not started |
| Transcription | `nanofolks/providers/transcription.py` | `backend/internal/speech/*` | Used by voice input. | Not started |
| Channel manager + connectors | `nanofolks/channels/*` | `backend/internal/channels/*` | Telegram, Discord, Slack, WhatsApp, Email parity. | Not started |
| Bridge server | `bridge/*` | `backend/internal/bridge/*` | Port WhatsApp bridge or wrap TS server. | Not started |

---

## Identity, Teams, Templates, Soul

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Team manager | `nanofolks/teams/manager.py` | `backend/internal/teams/manager.go` | Team selection. | Not started |
| Templates + discovery | `nanofolks/templates/*` | `backend/internal/templates/*` | Team/identity/soul templates. | Not started |
| Soul manager | `nanofolks/soul/manager.py` | `backend/internal/soul/manager.go` | SOUL.md + IDENTITY/ROLE. | Not started |
| Identity + role parsing | `nanofolks/identity/*`, `nanofolks/models/role_card.py` | `backend/internal/identity/*` | Role cards and relationships. | Not started |

---

## Work Logs, Learning, UX

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Work log manager | `nanofolks/agent/work_log_manager.py` | `backend/internal/worklog/*` | Keep SQLite schema + analytics. | Not started |
| Learning exchange | `nanofolks/agent/learning_exchange.py` | `backend/internal/learning/*` | Insight storage parity. | Not started |
| CLI UX + commands | `nanofolks/cli/*` | `cmd/cli/*` | Full CLI parity alongside GUI. | Not started |

---

## Config, Utils, Tests

| Subsystem | Python Source | Go v1 Target | Parity Notes | Progress |
|---|---|---|---|---|
| Config schema + loader | `nanofolks/config/*` | `backend/internal/config/*` | Preserve env precedence and defaults. | Not started |
| Utils | `nanofolks/utils/*` | `backend/internal/utils/*` | Includes secure bind logic. | Not started |
| Tests | `tests/*` | `backend/test/*`, `frontend/e2e/*` | Test parity is part of v1. | Not started |

---

**V1 Parity Checklist**

### Core Runtime & Orchestration
- [ ] Agent loop + orchestration
- [ ] Intent detection + flow router
- [ ] Project state + phases
- [ ] Multi-bot generator
- [ ] Routing + calibration + sticky
- [ ] Tag parsing system

### Rooms, Sessions, Messaging, Broker
- [ ] Room manager + mappings
- [ ] Room model
- [ ] Room-centric sessions
- [ ] CAS storage
- [ ] Per-room broker
- [ ] Group commit
- [ ] Bus + queue
- [ ] Bot DM rooms

### Bots & Coordination
- [ ] Bot definitions + registry
- [ ] Dispatch + coordinator
- [ ] Bot reasoning configs
- [ ] Bot checks

### Memory & Knowledge
- [ ] Memory store + models
- [ ] Embeddings + vector index
- [ ] Retrieval + summaries + graph
- [ ] Compaction + background jobs
- [ ] Preferences

### Scheduling, Crew routines, Dashboard
- [ ] Cron service + types
- [ ] CrewRoutines models + manager
- [ ] Dashboard server

### Tools, Skills, MCP
- [ ] Tool registry + base tools
- [ ] Tool permissions
- [ ] MCP client
- [ ] Skill packs

### Security
- [ ] Keyring + keyvault
- [ ] Secure memory + sanitization
- [ ] Credential detection + audit
- [ ] Symbolic converter

### Providers and Channels
- [ ] Provider registry + LLM
- [ ] Transcription
- [ ] Channel manager + connectors
- [ ] Bridge server

### Identity, Teams, Templates, Soul
- [ ] Team manager
- [ ] Templates + discovery
- [ ] Soul manager
- [ ] Identity + role parsing

### Work Logs, Learning, UX
- [ ] Work log manager
- [ ] Learning exchange
- [ ] CLI UX + commands

### Config, Utils, Tests
- [ ] Config schema + loader
- [ ] Utils
- [ ] Tests

---

**Architecture Improvements (Port Opportunity)**

These improvements are recommended during the port process. Some can be done now in Python to de‑risk the port, others are best done in Go after parity.

**Do Now in Python (and carry into Go v1 design):**
- ID normalization helpers (RoomID / SessionID)
- Single MessageEnvelope type across broker/bus/channels/tools
- Unified SecretStore interface (keyring/keyvault/symbolic)
- Team vs Team naming cleanup
- TeamProfile read‑only aggregator (SOUL + identity + reasoning + permissions)

**Defer to Go Port (post‑parity or v2):**
- Unify DM rooms into standard rooms
- Merge Cron + CrewRoutines into one scheduler
- Single orchestrator pipeline (tags → intent → dispatch → aggregation)
- MemoryPolicy per room
- Treat CLI/GUI as channels
- Explicit task ownership + handoff rules

---

**V2 Plan (Post‑Parity)**

## Goals (Plain Language)
1. Make the system more reliable when multiple rooms, bots, and channels are active at the same time.
2. Make it easier to monitor and debug (better dashboards, metrics, and audit logs).
3. Make the AI memory smarter (better summaries, smarter retrieval).
4. Make skills, tools, and MCP safer and easier to extend.
5. Improve collaboration and UI without breaking local-first privacy.

---

## Improvements Carried from Python Plan
- Unify DM rooms into standard rooms
- Merge Cron + CrewRoutines into one scheduler
- Single orchestrator pipeline (tags → intent → dispatch → aggregation)
- MemoryPolicy per room
- Treat CLI/GUI as channels
- Explicit task ownership + handoff rules

---

## v2 Scope by System

### 1) Runtime Hardening
- Add backpressure and priority handling to room queues
- Add crash‑safe message replay for rooms
- Turn QUICK/FULL flow logic into a stronger state machine

### 2) Observability
- Unified metrics for team routines, user routines, and message queues
- More detailed audit logs with retention rules
- Configurable dashboard views for teams and rooms

### 3) Memory & Knowledge Enhancements
- Pluggable embedding engines
- Smarter long‑term summaries with confidence scores
- Memory cleanup rules

### 4) Tools, Skills, MCP
- More precise per‑bot tool permissions
- Skill verification workflows and a searchable marketplace
- Multi‑session MCP support

### 5) Channels + Bridge
- Standard channel interface so all connectors behave the same
- Decide to port the TS bridge to Go or wrap it as a managed subprocess
- Better room↔channel sync rules

### 6) Identity, Teams, and Collaboration
- Versioned team bundles
- Team presets to switch the entire crew’s personalities
- Shared team packs for multi‑device sync

### 7) UX (GUI + CLI)
- CLI parity hardened for long sessions
- GUI additions for room brokers, routines state, and team activity
- Unified export pipeline (PDF/MD/JSON) for GUI and CLI

---

## v2 Milestones

1. M1: Runtime Reliability
2. M2: Observability and Security
3. M3: Memory Upgrade
4. M4: Tools and Skills
5. M5: UI and Collaboration

---

## v2 Acceptance Criteria

- Every v1 subsystem remains intact and compatible
- v2 features are additive, not breaking
- The system remains local-first with clear security boundaries
