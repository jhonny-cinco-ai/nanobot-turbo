# nanofolks Swift Port Plan

**Purpose**: Native macOS implementation leveraging true OS-level integration  
**Scope**: Full parity with Python architecture + deep macOS system control  
**Rationale**: Desktop agent requiring real filesystem, browser, and app automation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        nanofolks Swift App                          │
├─────────────────────────────────────────────────────────────────────┤
│  UI Layer (SwiftUI)                                                 │
│  - Main window, room list, chat view                               │
│  - Bot configuration panels                                         │
│  - Settings & preferences                                           │
├─────────────────────────────────────────────────────────────────────┤
│  Agent Core (Swift)                                                 │
│  - Agent loop & orchestration                                       │
│  - Intent detection & flow routing                                  │
│  - Multi-bot generator & coordination                               │
│  - Memory & embeddings                                              │
├─────────────────────────────────────────────────────────────────────┤
│  System Integration (Swift/macOS APIs)                             │
│  - Filesystem tools (NSWorkspace, FileManager)                     │
│  - Browser automation (Safari + AppleScript)                       │
│  - App control (NSRunningApplication, Accessibility)              │
│  - Shell execution (Process/NSTask)                                 │
│  - Notifications (UserNotifications)                                │
├─────────────────────────────────────────────────────────────────────┤
│  Data Layer (SwiftData/SQLite)                                      │
│  - Room/session persistence                                         │
│  - Message storage                                                   │
│  - Memory store & vector index                                      │
├─────────────────────────────────────────────────────────────────────┤
│  Nanofolks Cloud (Control Plane + LLM Proxy)                        │
│  - Login (OpenAuth or equivalent)                                   │
│  - Entitlements + metering + billing integration (e.g., Polar)      │
│  - Usage ledger + limits (monthly budget + overage)                 │
│  - Provider routing (gateway/router) + model allowlist (5-10 models)│
│  - Minimal user/profile metadata (e.g., Supabase/Convex)            │
├─────────────────────────────────────────────────────────────────────┤
│  External Providers                                                 │
│  - LLM gateways/routers (e.g., Vercel AI Gateway, OpenRouter)        │
│  - Direct LLM providers (OpenAI, Anthropic, etc.)                    │
│  - Experimental/specialized models (optional; later)                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Product & Platform Decisions (v1)

**Distribution**: Direct download from website (not App Store). Plan for notarization, hardened runtime, and an auto-update mechanism (e.g., Sparkle).

**Login**: Required to use the app (because v1 relies on online LLM calls). Design for graceful degradation when backend/provider is unavailable (view history, search local memory, drafts), but block new requests.

**Data philosophy**: Local-first. “Important user data” (agent memory/learning, room history) stays on-device by default. The server stores only what’s needed for auth, billing, metering, and abuse prevention.

**Backend role**: A thin “control plane” + LLM proxy. The macOS app never calls gateway/router or LLM providers directly in v1.

**Provider strategy**:
- Start with a gateway/router behind the proxy (simplifies multi-provider support and failover).
- Curate an allowlist of ~5–10 models (keep UX simple and costs predictable).
- Keep the interface abstract so we can later route directly to providers and/or add specialized/experimental models (including self-hosted options) without changing the client.

**Pricing strategy**:
- Subscription plans include a monthly usage budget (recommend token-based budgets; optionally display “~N standard requests”).
- Optional overage pay-as-you-go after included budget is exhausted (configurable per plan).

**Tenancy**:
- Single-user accounts for v1.
- Future-proof for teams by attaching entitlements/usage to an `account_id` (even if `account_id == user_id` in v1).

---

## Cloud Control Plane (Backend) – Scope for v1

### Why this exists
- Avoid shipping shared provider keys in the macOS app.
- Enforce plans/limits and compute usage consistently.
- Centralize billing state (active/canceled/past-due), abuse prevention, and provider routing.

### Minimal responsibilities
- **Auth**: login + session issuance (access token + refresh token).
- **Device registration**: bind sessions to `device_id`, allow revocation.
- **Entitlements**: plan lookup, included budget, overage setting, rate limits.
- **LLM proxy**: `/chat` and `/embeddings` endpoints; forward requests; record usage.
- **Metering**: append-only usage ledger + periodic rollups; emit billing events.
- **Admin** (minimal): user search, entitlement status, usage this period, revoke device, disable account.

### Suggested API surface (v1)
- `POST /auth/login` (or OAuth callback flow)
- `POST /auth/refresh`
- `POST /devices/register`
- `GET /me`
- `GET /me/entitlements`
- `GET /me/usage`
- `POST /llm/chat`
- `POST /llm/embeddings`
- `POST /webhooks/billing` (e.g., Polar webhook endpoint)
- `GET /admin/users?q=...`
- `GET /admin/users/:id`
- `POST /admin/users/:id/disable`
- `POST /admin/devices/:id/revoke`

### Data model (v1, team-ready)
- `accounts`: id, created_at, status, billing_customer_id
- `users`: id, email, created_at, status
- `memberships`: account_id, user_id, role (`owner` for v1)
- `devices`: id, account_id, user_id, created_at, last_seen_at, revoked_at
- `entitlements`: account_id, plan_id, period_start, period_end, included_budget, overage_enabled
- `usage_ledger`: id, account_id, user_id, device_id, ts, model, input_tokens, output_tokens, total_tokens, request_id, status
- `usage_rollups`: account_id, period_start, period_end, total_tokens (optional cache)

---

## Swift Layout

```
 nanofolks-swift/
 ├── Sources/
 │   ├── nanofolks/                    # Main app target
 │   │   ├── App/                      # App entry, main window
 │   │   ├── Views/                    # SwiftUI views
 │   │   ├── ViewModels/               # ObservableObject view models
 │   │   └── Resources/                # Assets, localizations
 │   ├── Agent/                        # Core agent logic
 │   │   ├── Loop.swift                # Agent loop
 │   │   ├── Intent/                   # Intent detection & routing
 │   │   ├── Context/                  # Context building
 │   │   ├── MultiBot/                 # Multi-bot coordination
 │   │   └── Orchestration/            # Pipeline orchestration
 │   ├── Bots/                         # Bot definitions & dispatch
 │   │   ├── Definitions.swift         # Bot registry
 │   │   ├── Dispatch.swift            # Bot dispatching
 │   │   ├── Coordinator.swift         # Multi-bot coordination
 │   │   └── Reasoning/                # Per-bot reasoning configs
 │   ├── Memory/                       # Memory & knowledge
 │   │   ├── Store.swift               # Memory store
 │   │   ├── Models.swift              # Memory models
 │   │   ├── Embeddings.swift          # Embedding generation
 │   │   ├── VectorIndex.swift         # Vector indexing
 │   │   ├── Retrieval.swift           # Context retrieval
 │   │   ├── Summaries.swift           # Memory summarization
 │   │   └── Preferences.swift         # User preferences
 │   ├── Rooms/                        # Room management
 │   │   ├── Manager.swift              # Room manager
 │   │   ├── Models.swift              # Room models
 │   │   ├── Sessions.swift            # Room-centric sessions
 │   │   └── DMRooms.swift              # Bot-to-bot DM rooms
 │   ├── Broker/                       # Message broker
 │   │   ├── RoomBroker.swift          # Per-room FIFO broker
 │   │   ├── GroupCommit.swift         # Batch durability
 │   │   └── Queue.swift               # Message queue
 │   ├── Bus/                          # Event bus
 │   │   ├── Events.swift              # MessageEnvelope types
 │   │   └── Bus.swift                 # Event distribution
 │   ├── Providers/                    # LLM providers
 │   │   ├── Registry.swift            # Provider registry
 │   │   ├── Base.swift                # Provider protocol
 │   │   ├── OpenAI.swift              # OpenAI provider
 │   │   ├── Anthropic.swift           # Anthropic provider
 │   │   └── LiteLLM.swift             # LiteLLM compatibility
 │   ├── Backend/                      # Control plane integration
 │   │   ├── Client.swift              # HTTP client to Nanofolks Cloud
 │   │   ├── Auth.swift                # Login/session + refresh + device registration
 │   │   ├── Entitlements.swift        # Plan/limits + usage remaining
 │   │   └── Models.swift              # DTOs (Codable)
 │   ├── Channels/                     # Channel connectors
 │   │   ├── Manager.swift            # Channel manager
 │   │   ├── Base.swift               # Channel protocol
 │   │   ├── Telegram.swift           # Telegram connector
 │   │   ├── Discord.swift            # Discord connector
 │   │   ├── Slack.swift              # Slack connector
 │   │   └── CLI.swift                # CLI channel
 │   ├── SystemControl/               # macOS-specific (DIFFERENT FROM GO)
 │   │   ├── Workspace.swift           # NSWorkspace wrappers
 │   │   ├── Browser.swift             # Safari/browser automation
 │   │   ├── Filesystem.swift          # File operations
 │   │   ├── Shell.swift               # Shell execution
 │   │   ├── Accessibility.swift      # UI automation
 │   │   ├── AppleScript.swift        # Scripting bridge
 │   │   └── Notifications.swift      # System notifications
 │   ├── Tools/                        # Agent tools
 │   │   ├── Registry.swift            # Tool registry
 │   │   ├── Base.swift               # Tool protocol
 │   │   ├── Permissions.swift        # Per-bot tool permissions
 │   │   ├── MCP.swift                # MCP client
 │   │   └── Skills/                  # Skill execution
 │   ├── Security/                    # Security layer
 │   │   ├── Keyring.swift            # Keychain access
 │   │   ├── KeyVault.swift           # Secret storage
 │   │   ├── Sanitizer.swift          # Log sanitization
 │   │   ├── CredentialDetector.swift # Credential detection
 │   │   └── AuditLogger.swift       # Audit trail
 │   ├── Routines/                    # Scheduling
 │   │   ├── Service.swift            # Routine service
 │   │   ├── Engine.swift             # Routine execution engine
 │   │   ├── TeamRoutines.swift       # Team routines
 │   │   └── Dashboard.swift          # Dashboard server
 │   ├── Identity/                    # Identity & teams
 │   │   ├── TeamManager.swift        # Team management
 │   │   ├── SoulManager.swift        # SOUL.md management
 │   │   ├── Templates.swift          # Identity templates
 │   │   └── RoleParser.swift         # Role card parsing
 │   ├── Config/                      # Configuration
 │   │   ├── Schema.swift             # Config schema
 │   │   └── Loader.swift             # Config loading
 │   └── Utils/                       # Utilities
 │       ├── IDs.swift                # ID normalization
 │       └── Logging.swift            # Logging setup
 └── Tests/
     └── nanofolks-tests/
```

---

## V1 Parity Matrix

### Core Runtime & Orchestration

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Agent loop + orchestration | `agent/loop.py` | `Agent/Loop.swift` | Must preserve multi-bot pipeline | Use Swift actors for concurrency |
| Intent detection + flow router | `agent/intent_detector.py`, `agent/intent_flow_router.py` | `Agent/Intent/` | QUICK/FULL flows and cancellation | Swift regex / NaturalLanguage |
| Project state + phases | `agent/project_state.py` | `Agent/ProjectState.swift` | Persist flow state by room/session | SwiftData persistence |
| Multi-bot generator | `agent/multi_bot_generator.py` | `Agent/MultiBot/` | Simultaneous responses | Swift AsyncSequence |
| Tag parsing system | `systems/tag_handler.py` | `Agent/TagHandler.swift` | `@bot` and `#room` tags | Native Swift string processing |

---

### Rooms, Sessions, Messaging, Broker

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Room manager + mappings | `bots/room_manager.py` | `Rooms/Manager.swift` | Channel↔room mapping | SwiftData @Model |
| Room model | `models/room.py` | `Rooms/Models.swift` | Schema matching | @Model class |
| Room-centric sessions | `session/dual_mode.py` | `Rooms/Sessions.swift` | Room-keyed sessions | SQLite.swift |
| CAS storage | `storage/cas_storage.py` | `Storage/CASStorage.swift` | Conflict-free writes | Swift actor + SQLite |
| Per-room broker | `broker/room_broker.py` | `Broker/RoomBroker.swift` | FIFO per room | Swift actor |
| Group commit | `broker/group_commit.py` | `Broker/GroupCommit.swift` | Batch durability | Swift async/await |
| Bus + queue | `bus/*` | `Bus/` | Event bus parity | Combine framework |
| Bot DM rooms | `bots/dm_room_manager.py` | `Rooms/DMRooms.swift` | Persistent DM history | SwiftData |

---

### Bots & Coordination

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Bot definitions + registry | `bots/definitions.py` | `Bots/Definitions.swift` | Preserve roles and configs | Swift enum/struct |
| Dispatch + coordinator | `bots/dispatch.py`, `coordinator/*` | `Bots/Dispatch.swift`, `Bots/Coordinator.swift` | Audit, decisions | Swift actor for thread safety |
| Bot reasoning configs | `bots/reasoning_configs.py`, `reasoning/config.py` | `Bots/Reasoning/` | Per-bot reasoning modes | Configuration objects |

---

### Memory & Knowledge

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Memory store + models | `memory/store.py`, `memory/models.py` | `Memory/Store.swift`, `Memory/Models.swift` | Schema and CRUD | SwiftData @Model |
| Embeddings + vector index | `memory/embeddings.py`, `memory/vector_index.py` | `Memory/Embeddings.swift`, `Memory/VectorIndex.swift` | Vector memory | **swift-embeddings (bge-small)** |
| Retrieval + summaries + graph | `memory/retrieval.py`, `memory/summaries.py`, `memory/graph.py` | `Memory/Retrieval.swift`, `Memory/Summaries.swift`, `Memory/Graph.swift` | Context building | Swift async/await |
| Background jobs | `memory/background.py` | `Memory/Background.swift` | Long-running tasks | Swift Concurrency TaskGroup |

---

### Tools, Skills, MCP

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Tool registry + base tools | `agent/tools/*.py` | `Tools/` | File, shell, web, memory, MCP | **Deep macOS integration** |
| Tool permissions | `agent/tools/permissions.py` | `Tools/Permissions.swift` | Per-bot restrictions | Swift actor |
| MCP client | `agent/tools/mcp.py` | `Tools/MCP.swift` | Secret resolution | URLSession |
| Skill packs | `skills/*` | `Tools/Skills/` | Discover and run local skills | FileManager + Process |

---

### Security

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Keyring + keyvault | `security/keyring_manager.py`, `security/keyvault.swift` | `Security/Keyring.swift`, `Security/KeyVault.swift` | Local-first secrets | Security.framework |
| Secure memory + sanitization | `security/secure_memory.py`, `security/sanitizer.py` | `Security/SecureMemory.swift`, `Security/Sanitizer.swift` | Sanitize logs/UI | Swift string processing |
| Credential detection + audit | `security/credential_detector.py`, `security/audit_logger.py` | `Security/CredentialDetector.swift`, `Security/AuditLogger.swift` | Scan and audit | Regex patterns |
| Symbolic converter | `security/symbolic_converter.py` | `Security/SymbolicConverter.swift` | MCP secret resolution | String processing |

---

### Providers and Channels

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Provider registry + LLM | `providers/*` | `Providers/` | LiteLLM compatibility | URLSession networking |
| Channel manager + connectors | `channels/*` | `Channels/` | Telegram, Discord, Slack, Email | URLSession + AsyncStream |

---

### Identity, Teams, Templates, Soul

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Team manager | `teams/manager.py` | `Identity/TeamManager.swift` | Team selection | SwiftData |
| Templates + discovery | `templates/*` | `Identity/Templates.swift` | Team/identity/soul templates | FileManager |
| Soul manager | `soul/manager.py` | `Identity/SoulManager.swift` | SOUL.md + IDENTITY/ROLE | FileManager |
| Identity + role parsing | `identity/*`, `models/role_card.py` | `Identity/RoleParser.swift` | Role cards and relationships | String processing |

---

### Routines & Scheduling

| Subsystem | Python Source | Swift v1 Target | Parity Notes | Swift-Specific |
|---|---|---|---|---|
| Routines service + types | `routines/*` | `Routines/Service.swift`, `Routines/Models.swift` | Timezone support | Swift Date/Calendar |
| Team routines manager | `routines/team/*` | `Routines/TeamRoutines.swift` | Checks and notifications | Timer + NotificationCenter |
| Dashboard server | `routines/team/dashboard_server.py` | `Routines/Dashboard.swift` | HTTP + WS metrics | Vapor or native HTTP |

---

### Local Models & Intelligence Layer

Your Python codebase already supports local models via LiteLLM. The Swift port can leverage the same capabilities:

#### Supported Local Models (from existing Python)

| Provider | Implementation | Swift Integration |
|----------|---------------|------------------|
| **Ollama** | OpenAI-compatible API | URLSession → `http://localhost:11434/v1/chat/completions` |
| **LM Studio** | OpenAI-compatible API | URLSession → `http://localhost:1234/v1/chat/completions` |
| **llama.cpp server** | OpenAI-compatible API | URLSession → `http://localhost:8080/v1/chat/completions` |
| **Apple Foundation Models** | Native Apple Silicon | Use `LLM` framework (macOS 14.4+) |

#### Swift Provider Architecture

```swift
// Local Ollama/LM Studio provider (OpenAI-compatible)
class LocalLLMProvider: LLMProvider {
    private let baseURL: URL
    private let model: String
    
    func chat(messages: [Message]) async throws -> LLMResponse {
        let url = baseURL.appendingPathComponent("v1/chat/completions")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "model": model,
            "messages": messages.map { ["role": $0.role, "content": $0.content] },
            "stream": false
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        // Parse OpenAI-compatible response...
    }
}

// Apple Intelligence (native on Apple Silicon)
class AppleIntelligenceProvider: LLMProvider {
    func chat(messages: [Message]) async throws -> LLMResponse {
        // Use Apple's LLM framework (macOS 14.4+)
        let llm = LLM(model: "com.apple.on-device")
        let response = try await llm.generate(messages: messages)
        return LLMResponse(content: response)
    }
}
```

#### Local Embeddings

Your Python uses FastEmbed with `BAAI/bge-small-en-v1.5`. Swift has equivalent options:

##### Option 1: swift-embeddings (Recommended - Pure Swift/MLX)

```swift
// Native Swift using MLX - no Python dependencies
import SwiftEmbeddings

class NativeEmbeddingProvider {
    private var modelContainer: ModelContainer?
    
    func load() async throws {
        // bge-small-en-v1.5 (same as Python!)
        modelContainer = try await Bert.loadModelBundle(
            from: "BAAI/bge-small-en-v1.5",
            loadConfig: .default
        )
    }
    
    func embed(texts: [String]) async throws -> [[Float]] {
        guard let container = modelContainer else { 
            throw EmbeddingError.notLoaded 
        }
        
        return try await container.perform { model, tokenizer, pooling in
            let inputs = texts.map { tokenizer.encode(text: $0) }
            // ... process through model
            return embeddings.map { $0.asArray(Float.self) }
        }
    }
}
```

**Hardware:** ~40MB VRAM (any M1+ Mac, even 8GB RAM models)

##### Option 2: mlx-embeddings (Python via MLX)

```swift
// Python mlx-embeddings called from Swift
// pip install mlx-embeddings
// Downloads mlx-community/bge-small-en-v1.5-8bit (35.5 MB)
```

##### Option 3: Ollama (if already running)

```swift
// Local Ollama - if you already run Ollama for LLM
class LocalEmbeddingProvider {
    private let baseURL = URL(string: "http://localhost:11434")!
    
    func embed(texts: [String]) async throws -> [[Float]] {
        let url = baseURL.appendingPathComponent("v1/embeddings")
        
        var results: [[Float]] = []
        for text in texts {
            let body: [String: Any] = [
                "model": "nomic-embed-text",  // or bge-small if pulled
                "input": text
            ]
            // ... HTTP request
        }
        return results
    }
}
```

##### Default Model: `BAAI/bge-small-en-v1.5`

This matches your Python config exactly:

#### Config Integration

The Swift config should mirror your Python schema:

```swift
struct LLMConfig {
    var provider: LLMProviderType  // .openai, .anthropic, .ollama, .lmStudio, .apple
    var apiKey: String?
    var apiBase: String?  // e.g., "http://localhost:11434"
    var defaultModel: String
    var useLocalModel: Bool
    var localModel: String  // e.g., "llama3", "mistral"
    
    var embeddingProvider: EmbeddingProviderType  // .native (MLX), .ollama, .api
    // Default: BAAI/bge-small-en-v1.5 (same as Python FastEmbed)
    var embeddingLocalModel: String = "BAAI/bge-small-en-v1.5"
}
```

#### Fallback Strategy

Your Python code already implements fallback (local first → API). Swift can do the same:

```swift
func chatWithFallback(messages: [Message]) async throws -> LLMResponse {
    // Try local first
    if config.useLocalModel {
        do {
            return try await localProvider.chat(messages: messages)
        } catch {
            logger.warning("Local model failed: \(error), falling back to API")
        }
    }
    // Fallback to cloud API
    return try await cloudProvider.chat(messages: messages)
}
```

---

## Python Dependencies → Swift Mapping

### Database & Storage

| Python | Swift | Strategy |
|--------|-------|----------|
| `sqlite3` (built-in) | **SQLite.swift** | Direct mapping - same SQLite, Swift wrapper |
| `hnswlib` | **Custom + MLX** | Use swift-embeddings for vector ops, or simple in-memory index |

### TurboMemoryStore Database Schema

The memory system uses these SQLite tables:

```swift
// SwiftData or SQLite.swift implementation
struct Event { id, content, timestamp, roomId, botId, embedding }
struct Entity { id, name, type, properties, timestamp }
struct Edge { id, sourceId, targetId, relationType }
struct Fact { id, subject, predicate, object, confidence }
struct Topic { id, name, embedding }
struct SummaryNode { id, content, timestamp, parentId }
struct Learning { id, content, botId, tags, timestamp }
struct Migration { id, name, appliedAt }
```

**Key:** WAL mode for concurrency (same as Python).

### LLM & Embeddings

| Python | Swift | Strategy |
|--------|-------|----------|
| `litellm` | **Custom URLSession** | Reimplement: OpenAI, Anthropic, Ollama, LM Studio APIs |
| `fastembed` | **swift-embeddings** | Native MLX with bge-small-en-v1.5 |
| `hnswlib` | **swift-embeddings** | Vector operations via MLX |

### Web & Networking

| Python | Swift | Strategy |
|--------|-------|----------|
| `httpx` | **URLSession** | Built-in |
| `websockets` | **URLSessionWebSocketTask** | Built-in |
| `scrapling` | **URLSession + SwiftSoup** | HTML parsing |
| `readability-lxml` | **SwiftSoup** | HTML extraction |

### Data Processing

| Python | Swift | Strategy |
|--------|-------|----------|
| `pypdf` | **PDFKit** | Built-in macOS |
| `pydantic` | **Codable** | Built-in Swift |
| `json-repair` | **Custom** | Simple JSON fixing |

### Channels (Telegram, Discord, Slack, etc.)

| Python | Swift | Strategy |
|--------|-------|----------|
| `python-telegram-bot` | **URLSession** | REST API calls |
| `slack-sdk` | **URLSession** | REST API calls |
| `python-socketio` | **URLSessionWebSocketTask** | Socket.IO protocol |

### MCP & Tools

| Python | Swift | Strategy |
|--------|-------|----------|
| `mcp` | **Custom** | JSON-RPC over stdio (same protocol) |
| `keyring` | **Security.framework** | Keychain access |

### CLI & UI

| Python | Swift | Strategy |
|--------|-------|----------|
| `typer` | **SwiftUI** | Native menu bar + window |
| `rich` | **SwiftUI** | Native styling |
| `prompt-toolkit` | **SwiftUI** | Input handling |

### Scheduling & Cron

| Python | Swift | Strategy |
|--------|-------|----------|
| `croniter` | **Swift Date + Calendar** | Reimplement cron parsing |

### Logging & Monitoring

| Python | Swift | Strategy |
|--------|-------|----------|
| `loguru` | **swift-log** | Structured logging |
| `croniter` | **Custom** | Schedule parsing |

### macOS-Specific

| Python | Swift | Strategy |
|--------|-------|----------|
| `apple-fm-sdk` | **LLM framework** | Native Apple Intelligence |

---

## Dependency Summary

| Strategy | Count | Examples |
|----------|-------|----------|
| **Built-in Swift** | 12+ | URLSession, PDFKit, Security, SwiftData, Codable |
| **SPM Package** | 4 | swift-embeddings, SQLite.swift, swift-log, MLX |
| **Reimplement** | 5 | LLM provider, MCP, channel connectors, cron |
| **API Calls** | 2 | GLiner → LLM, hnswlib → MLX vector ops |

---

## System Control Layer (Key Differentiator)

This is where Swift shines vs Go/Python:

### macOS APIs to Leverage

| Capability | Swift API | Use Case |
|------------|-----------|----------|
| Open apps/folders | `NSWorkspace.shared.open()` | File browser, app launching |
| File operations | `FileManager`, `NSFileCoordinator` | Read/write with security |
| Browser control | `SafariServices`, AppleScript | Open URLs, fill forms |
| UI automation | `AXUIElement` (Accessibility) | Click, type, read UI |
| App control | `NSRunningApplication` | List running apps, activate |
| Shell commands | `Process` (formerly NSTask) | Execute commands |
| System notifications | `UserNotifications` | Alert the user |
| Speech synthesis | `AVSpeechSynthesizer` | Voice output |
| Speech recognition | `Speech` framework | Voice input |
| Calendar/Contacts | EventKit, Contacts | System integration |
| Shortcuts | `Intents` framework | Run macOS Shortcuts |
| Screen capture | `CGWindowListCreateImage` | Screenshot tools |
| Clipboard | `NSPasteboard` | Copy/paste automation |

### Browser Automation Strategy

```
┌─────────────────────────────────────────────────────┐
│              Browser Automation Layer               │
├─────────────────────────────────────────────────────┤
│  1. AppleScript directly to Safari                  │
│     - open location, get URL of document            │
│     - Interact with DOM via JavaScript              │
├─────────────────────────────────────────────────────┤
│  2. SFSafariViewController (for embedded)          │
├─────────────────────────────────────────────────────┤
│  3. Accessibility API (AXUIElement)                 │
│     - Read button labels, click elements            │
│     - Works with any app, not just browsers         │
└─────────────────────────────────────────────────────┘
```

### File System Tools

```swift
// Example: Swift-native filesystem tool
class FilesystemTool {
    func readFile(path: String) async throws -> String {
        let url = URL(fileURLWithPath: path)
        return try String(contentsOf: url, encoding: .utf8)
    }
    
    func writeFile(path: String, content: String) async throws {
        let url = URL(fileURLWithPath: path)
        try content.write(to: url, atomically: true, encoding: .utf8)
    }
    
    func openInFinder(path: String) {
        NSWorkspace.shared.selectFile(path, inFileViewerRootedAtPath: "")
    }
    
    func openWithApp(path: String, app: String) {
        NSWorkspace.shared.open(URL(fileURLWithPath: path), 
                                withApplicationAt: URL(fileURLWithPath: app))
    }
}
```

---

## macOS-Specific Features

### Menu Bar Agent Mode

```swift
// Nanofolks as a menu bar app (Agent app)
class NanofolksApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        MenuBarExtra("Nanofolks", systemImage: "person.3") {
            Button("Open Chat") { ... }
            Button("Quick Action") { ... }
            Divider()
            Button("Quit") { ... }
        }
        .menuBarExtraStyle(.menu)
        
        Window("Nanofolks", id: "main") { ... }
    }
}
```

### Touch Bar Support (if applicable)

### Notifications & Haptics

### Keyboard Shortcuts

### Share Extensions

---

## Dependencies

### Swift Package Manager

| Package | Purpose | macOS Support |
|---------|---------|---------------|
| **swift-embeddings** | Native MLX embeddings (bge-small!) | Native (MLX) |
| swift-llm | LLM API clients | Native |
| SQLite.swift | Database | Native |
| Soto | AWS SDK (if needed) | Native |
| swift-nio | Networking | Native |
| apple/swift-http-types | HTTP | Native |
| mlx | MLX framework (for swift-embeddings) | Native (Apple Silicon) |

### Frameworks (built-in)

- **Foundation** - Core utilities
- **SwiftUI** - UI framework
- **SwiftData** - Persistence (macOS 14+)
- **Combine** - Reactive programming
- **Security** - Keychain, encryption
- **UserNotifications** - System notifications
- **SafariServices** - Browser integration
- **Accessibility** - UI automation
- **Speech** - Voice input/output
- **EventKit** - Calendar integration
- **Intents** - Shortcuts integration
- **LLM** - Apple Intelligence (macOS 14.4+, Apple Silicon only)

---

## Porting Strategy

### Phase 0: Control Plane MVP (Weeks 0-1)
- [ ] Choose backend hosting (Railway/Vercel/VPS) and DB (Supabase/Convex)
- [ ] Implement OpenAuth login flow + session issuance
- [ ] Add billing provider webhook integration (e.g., Polar) + entitlement state
- [ ] Implement `/llm/chat` proxy (single model) + usage ledger
- [ ] Minimal admin UI/pages (user lookup + status + usage + revoke device)

### Phase 1: Walking Skeleton App (Weeks 1-2)
- [ ] Project setup with Swift Package Manager
- [ ] Backend client + auth (Keychain-stored refresh token, device registration)
- [ ] Minimal chat UI (send → stream/receive) wired to `/llm/chat`
- [ ] Local persistence (rooms + messages) with SQLite
- [ ] Logging and error handling

### Phase 2: Core Agent (Weeks 3-4)
- [ ] Agent loop implementation
- [ ] Intent detection
- [ ] Context building
- [ ] Tool registry and base tools

### Phase 3: System Integration (Weeks 5-6)
- [ ] Filesystem tools (NSWorkspace)
- [ ] Shell execution
- [ ] Browser automation
- [ ] Notifications

### Phase 4: Memory & Knowledge (Weeks 7-8)
- [ ] Memory store
- [ ] Embedding calls to LLM providers
- [ ] Retrieval and summarization
- [ ] Session compaction

### Phase 5: UI & Polish (Weeks 9-10)
- [ ] SwiftUI views
- [ ] Menu bar integration
- [ ] Settings and preferences
- [ ] Testing and polish

### Phase 6: Providers, Billing UX, Hardening (Weeks 11-12)
- [ ] LLM provider integrations
- [ ] Model allowlist UI (5–10 curated models) + cost/usage messaging
- [ ] Billing UX (plan/usage/upgrade) + enforced limits + overage behavior
- [ ] Auto-update + notarization pipeline for direct distribution
- [ ] MCP client
- [ ] Security layer

---

## Comparison: Swift vs Go vs Python

| Aspect | Swift | Go | Python (current) |
|--------|-------|-----|-------------------|
| **macOS Integration** | ✅ Native APIs | ❌ Shell only | ❌ Shell only |
| **Cross-platform** | Apple only | ✅ Excellent | ✅ Excellent |
| **LLM Integration** | ✅ URLSession + Apple Intelligence | ✅ Native | ✅ Native |
| **Local Embeddings** | ✅ swift-embeddings (bge-small) | ⚠️ External API | ✅ FastEmbed |
| **Concurrency** | ✅ Actors/async | ✅ Goroutines | ✅ AsyncIO |
| **UI Development** | ✅ SwiftUI | ⚠️ Web | ⚠️ Web |
| **Build size** | Medium | Small | Medium |
| **Startup time** | Fast | Fastest | Slow |

---

## Decision Criteria

### Choose Swift if:
- macOS-native experience is primary goal
- Deep OS integration needed (browser automation, accessibility)
- You're willing to be Apple-platform-only for v1

### Choose Go if:
- Cross-platform desktop is important
- You're okay with "shallow" OS integration (shell commands)
- Team has Go expertise

### Keep Python if:
- Rapid prototyping is priority
- Cross-platform is mandatory
- ML/NLP ecosystem is critical (for now, less relevant with LLM APIs)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Swift vector search | No native vector DB | ✅ Native MLX embeddings (bge-small), same as Python |
| Limited NLP libs | Intent detection harder | Use LLM for NER, regex fallback |
| Channel SDKs | Fewer Swift libs | Use REST APIs directly |
| Team expertise | Learning curve | LLM-assisted coding |
| Mandatory login/backend outage | App becomes unusable | Degrade gracefully (local history/search/drafts), robust retry + clear status UI |
| Direct distribution hardening | Install/update friction | Notarization + hardened runtime + auto-update mechanism |
| macOS permissions (AX/Apple Events) | Tooling unreliable | Guided onboarding + permission checks + fail-safe tool fallbacks |

---

**Status**: Planning  
**Next Step**: Confirm backend stack (hosting + DB + billing) and implement Phase 0 + Phase 1 walking skeleton
