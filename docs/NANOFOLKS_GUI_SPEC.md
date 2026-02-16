# Nanofolks GUI Technical Specification

**Version:** 1.0  
**Date:** 2026-02-16  
**Status:** Draft  

## 1. Executive Summary

Nanofolks GUI is a cross-platform desktop application that provides a modern, intuitive interface for the Nanofolks AI assistant platform. It maintains full compatibility with the existing nanobot CLI architecture while adding a visual layer for non-technical users.

### Key Principles
- **Local-first**: All data stored locally, privacy by design
- **Equal interfaces**: GUI and messaging channels are peers
- **Security by default**: Tailscale required for external access
- **User control**: OSS users can override security with clear warnings
- **Unified sync**: All room activity synchronized across all interfaces

---

## 2. Architecture Overview

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Nanofolks Desktop App                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Frontend (Svelte 5 + Wails v2)                     │   │
│  │  ├─ Chat Interface                                  │   │
│  │  ├─ Room Management                                 │   │
│  │  ├─ Settings/Configuration                          │   │
│  │  └─ Bot Coordination View                           │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Backend (Go 1.21+)                                 │   │
│  │  ├─ Agent Loop (6-bot coordination)                 │   │
│  │  ├─ Memory System (SQLite)                          │   │
│  │  ├─ Gateway Server (WebSocket + REST)               │   │
│  │  ├─ Channel Connectors (Telegram, WhatsApp, etc.)   │   │
│  │  └─ Configuration Manager                          │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Data Layer                                         │   │
│  │  └─ ~/.nanofolks/                                   │   │
│  │      ├─ config.json                                 │   │
│  │      ├─ workspaces/*.json                          │   │
│  │      └─ memory.db                                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket/REST
                              ▼
                    ┌─────────────────────┐
                    │   Tailscale Mesh    │
                    │   (100.x.x.x)       │
                    └─────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │   WhatsApp   │  │  Telegram    │  │    Phone     │
    │   (Phone)    │  │   (Phone)    │  │   Web GUI    │
    └──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 Deployment Modes

#### Mode A: Desktop (Default)
- **Components:** GUI + Core + Optional Gateway
- **Use Case:** Personal use, maximum privacy
- **Security:** Localhost only, no external exposure

#### Mode B: Desktop + Channels
- **Components:** Full stack + Channel connectors
- **Use Case:** Mobile companion via messaging apps
- **Security:** Tailscale required for gateway

#### Mode C: Server (Docker)
- **Components:** Web GUI + Core + Gateway
- **Use Case:** Cloud VPS, team access, always-on
- **Security:** Tailscale + Docker networking

### 2.3 Security Model

```
┌─────────────────────────────────────────────┐
│           Security Levels                    │
├─────────────────────────────────────────────┤
│                                             │
│  🟢 LEVEL 1: SECURE (Default)               │
│     • Tailscale/WireGuard active            │
│     • Gateway binds to 100.x.x.x only       │
│     • MagicDNS: pc-name.tailnet-name.ts.net │
│     • No public IP exposure                 │
│                                             │
│  🟡 LEVEL 2: LAN ONLY                       │
│     • Local network access only (192.168.x) │
│     • No internet exposure                  │
│     • Suitable for home/office use          │
│                                             │
│  🔴 LEVEL 3: DANGER ZONE (Explicit opt-in)  │
│     • ⚠️ INSECURE: Public IP exposed        │
│     • Big red banner in GUI                 │
│     • Only for advanced users               │
│     • Must acknowledge security warning     │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| **Backend Language** | Go | 1.21+ | Performance, concurrency, single binary |
| **Frontend Framework** | Svelte 5 | 5.x | Reactivity, small bundles, fast rendering |
| **Desktop Framework** | Wails v2 | 2.x | Native performance, Go bindings, cross-platform |
| **UI Library** | Skeleton | 2.x | Svelte-native, Tailwind-based, accessible |
| **Database** | SQLite | 3.x | Zero config, portable, battle-tested |
| **ORM/DB** | sqlc + modernc.org/sqlite | latest | Type-safe SQL, pure Go driver |
| **WebSocket** | gorilla/websocket | latest | Reliable, widely used |
| **HTTP Router** | chi | latest | Lightweight, idiomatic Go |
| **Configuration** | Viper | latest | Multi-format support, env vars |
| **Validation** | go-playground/validator | latest | Struct validation |
| **Tailscale SDK** | tailscale.com/client/tailscale | latest | Official client |
| **AI Providers** | OpenAI, Anthropic, etc. | API latest | Multiple LLM support |
| **Speech-to-Text** | Whisper API (OpenAI) | API latest | High accuracy, handles noise |

---

## 4. Project Structure

```
nanofolks/
├── README.md
├── LICENSE
├── Makefile
├── go.mod
├── go.sum
│
├── backend/
│   ├── cmd/
│   │   ├── desktop/
│   │   │   └── main.go              # Desktop entry point
│   │   └── server/
│   │       └── main.go              # Server entry point
│   │
│   ├── internal/
│   │   ├── agent/
│   │   │   ├── loop.go              # Main agent loop
│   │   │   ├── bots.go              # 6-bot definitions
│   │   │   ├── dispatch.go          # Message routing
│   │   │   └── coordinator.go       # Multi-bot coordination
│   │   │
│   │   ├── memory/
│   │   │   ├── store.go             # SQLite operations
│   │   │   ├── entities.go          # Entity extraction
│   │   │   ├── search.go            # Full-text search
│   │   │   └── embeddings.go        # Vector storage
│   │   │
│   │   ├── rooms/
│   │   │   ├── manager.go           # Workspace CRUD
│   │   │   ├── participants.go      # Bot management
│   │   │   └── sync.go              # Cross-interface sync
│   │   │
│   │   ├── gateway/
│   │   │   ├── server.go            # HTTP/WebSocket server
│   │   │   ├── channels.go          # Channel connectors
│   │   │   ├── telegram.go          # Telegram bot
│   │   │   ├── whatsapp.go          # WhatsApp connector
│   │   │   ├── discord.go           # Discord bot
│   │   │   └── slack.go             # Slack connector
│   │   │
│   │   ├── config/
│   │   │   ├── loader.go            # Config file I/O
│   │   │   ├── schema.go            # Config types
│   │   │   └── validation.go        # Config validation
│   │   │
│   │   ├── security/
│   │   │   ├── tailscale.go         # Tailscale integration
│   │   │   ├── sanitizer.go         # Secret masking
│   │   │   └── validator.go         # Security level checks
│   │   │
│   │   ├── skills/
│   │   │   ├── registry.go          # Skill management
│   │   │   ├── scanner.go           # Security scanner
│   │   │   └── marketplace.go       # Skill marketplace
│   │   │
│   │   └── api/
│   │       ├── types.go             # Shared types
│   │       ├── handlers.go          # HTTP handlers
│   │       └── websocket.go         # WS handlers
│   │
│   └── pkg/
│       └── utils/
│           ├── logger.go
│           └── helpers.go
│
├── frontend/                        # Svelte 5 + Wails
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   │
│   ├── src/
│   │   ├── app.html
│   │   ├── app.postcss
│   │   │
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   │   ├── chat/
│   │   │   │   │   ├── MessageList.svelte
│   │   │   │   │   ├── MessageRenderer.svelte
│   │   │   │   │   ├── MessageInput.svelte
│   │   │   │   │   ├── CodeBlock.svelte
│   │   │   │   │   ├── ThinkingBubble.svelte
│   │   │   │   │   └── MentionPicker.svelte
│   │   │   │   │
│   │   │   │   ├── rooms/
│   │   │   │   │   ├── RoomList.svelte
│   │   │   │   │   ├── RoomHeader.svelte
│   │   │   │   │   ├── CreateRoomModal.svelte
│   │   │   │   │   └── BotSelector.svelte
│   │   │   │   │
│   │   │   │   ├── bots/
│   │   │   │   │   ├── BotStatus.svelte
│   │   │   │   │   ├── BotAvatar.svelte
│   │   │   │   │   └── BotCoordination.svelte
│   │   │   │   │
│   │   │   │   ├── settings/
│   │   │   │   │   ├── SettingsPanel.svelte
│   │   │   │   │   ├── ProviderConfig.svelte
│   │   │   │   │   ├── ChannelConfig.svelte
│   │   │   │   │   ├── GatewayConfig.svelte
│   │   │   │   │   ├── MemoryConfig.svelte
│   │   │   │   │   ├── SecurityConfig.svelte
│   │   │   │   │   └── AppearanceConfig.svelte
│   │   │   │   │
│   │   │   │   └── layout/
│   │   │   │       ├── Sidebar.svelte
│   │   │   │       ├── Header.svelte
│   │   │   │       ├── StatusBar.svelte
│   │   │   │       └── SplitView.svelte
│   │   │   │
│   │   │   ├── stores/
│   │   │   │   ├── chat.ts            # Chat messages
│   │   │   │   ├── rooms.ts           # Workspaces
│   │   │   │   ├── bots.ts            # Bot states
│   │   │   │   ├── config.ts          # Settings
│   │   │   │   ├── ui.ts              # UI state
│   │   │   │   └── websocket.ts       # WS connection
│   │   │   │
│   │   │   ├── types/
│   │   │   │   └── index.ts           # TypeScript types
│   │   │   │
│   │   │   └── wailsjs/               # Auto-generated by Wails
│   │   │       ├── go/
│   │   │       └── runtime/
│   │   │
│   │   └── routes/
│   │       ├── +layout.svelte
│   │       ├── +page.svelte           # Main app
│   │       ├── onboarding/
│   │       │   └── +page.svelte
│   │       └── chat/
│   │           └── [roomId]/
│   │               └── +page.svelte
│   │
│   └── static/
│       ├── logo.png
│       └── favicon.png
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── entrypoint.sh
│
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── deployment.md
│
└── scripts/
    ├── build.sh
    ├── release.sh
    └── install.sh
```

---

## 5. Data Models

### 5.1 Core Types

```go
// Room (Workspace)
type Room struct {
    ID            string    `json:"id" db:"id"`
    Name          string    `json:"name" db:"name"`
    Type          RoomType  `json:"type" db:"type"` // general, project, dm
    Participants  []string  `json:"participants" db:"participants"` // bot names
    CreatedAt     time.Time `json:"createdAt" db:"created_at"`
    UpdatedAt     time.Time `json:"updatedAt" db:"updated_at"`
    Summary       string    `json:"summary" db:"summary"`
    IsDM          bool      `json:"isDm" db:"is_dm"`
    DMTarget      string    `json:"dmTarget,omitempty" db:"dm_target"` // bot name for DMs
}

// Message
type Message struct {
    ID            string    `json:"id" db:"id"`
    RoomID        string    `json:"roomId" db:"room_id"`
    Content       string    `json:"content" db:"content"`
    Type          MsgType   `json:"type" db:"type"` // text, code, thinking, tool_result
    Sender        string    `json:"sender" db:"sender"` // user or bot name
    IsBot         bool      `json:"isBot" db:"is_bot"`
    Timestamp     time.Time `json:"timestamp" db:"timestamp"`
    Metadata      JSON      `json:"metadata" db:"metadata"` // For json-render components
    ReplyTo       string    `json:"replyTo,omitempty" db:"reply_to"`
    EditedAt      time.Time `json:"editedAt,omitempty" db:"edited_at"`
}

// Bot Definition
type Bot struct {
    Name          string    `json:"name"`
    Role          string    `json:"role"`
    Description   string    `json:"description"`
    Avatar        string    `json:"avatar"`
    Color         string    `json:"color"` // Hex color
    Model         string    `json:"model"`
    Temperature   float64   `json:"temperature"`
    SystemPrompt  string    `json:"systemPrompt"`
    Skills        []string  `json:"skills"`
    Status        BotStatus `json:"status"`
    IsEnabled     bool      `json:"isEnabled"`
}

type BotStatus string
const (
    BotStatusOnline   BotStatus = "online"
    BotStatusThinking BotStatus = "thinking"
    BotStatusOffline  BotStatus = "offline"
    BotStatusAway     BotStatus = "away"
)

// Configuration
type Config struct {
    Providers     ProvidersConfig    `json:"providers"`
    Channels      ChannelsConfig     `json:"channels"`
    Gateway       GatewayConfig      `json:"gateway"`
    Memory        MemoryConfig       `json:"memory"`
    Routing       RoutingConfig      `json:"routing"`
    Appearance    AppearanceConfig   `json:"appearance"`
    Security      SecurityConfig     `json:"security"`
}

type GatewayConfig struct {
    Enabled       bool   `json:"enabled"`
    Port          int    `json:"port"`
    BindAddress   string `json:"bindAddress"`
    UseTailscale  bool   `json:"useTailscale"`
    SecurityLevel string `json:"securityLevel"` // secure, lan, insecure
}

type SecurityConfig struct {
    SanitizeSecrets   bool     `json:"sanitizeSecrets"`
    SkillScanning     bool     `json:"skillScanning"`
    AllowedPaths      []string `json:"allowedPaths"`
    RequireTailscale  bool     `json:"requireTailscale"`
}
```

### 5.2 Database Schema (SQLite)

```sql
-- Rooms table
CREATE TABLE rooms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    participants TEXT NOT NULL, -- JSON array
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    summary TEXT,
    is_dm BOOLEAN DEFAULT FALSE,
    dm_target TEXT
);

-- Messages table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    room_id TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL,
    sender TEXT NOT NULL,
    is_bot BOOLEAN DEFAULT FALSE,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT, -- JSON
    reply_to TEXT,
    edited_at DATETIME,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

-- Full-text search index
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    sender,
    room_id UNINDEXED,
    content_rowid=rowid
);

-- Bot states
CREATE TABLE bot_states (
    bot_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_activity DATETIME,
    current_task TEXT,
    workspace_id TEXT
);

-- Configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. API Specification

### 6.1 WebSocket Events

```typescript
// Client → Server
interface ClientEvents {
    'message:send': {
        roomId: string;
        content: string;
        replyTo?: string;
    };
    
    'typing:start': {
        roomId: string;
    };
    
    'typing:stop': {
        roomId: string;
    };
    
    'room:join': {
        roomId: string;
    };
    
    'room:leave': {
        roomId: string;
    };
}

// Server → Client
interface ServerEvents {
    'message:received': {
        message: Message;
    };
    
    'message:stream': {
        messageId: string;
        content: string;
        isComplete: boolean;
    };
    
    'bot:status': {
        botName: string;
        status: BotStatus;
        currentTask?: string;
    };
    
    'typing:update': {
        roomId: string;
        user: string;
        isTyping: boolean;
    };
    
    'room:updated': {
        room: Room;
    };
    
    'error': {
        code: string;
        message: string;
    };
}
```

### 6.2 REST Endpoints

```yaml
# Rooms
GET    /api/v1/rooms              # List all rooms
POST   /api/v1/rooms              # Create room
GET    /api/v1/rooms/:id          # Get room details
PATCH  /api/v1/rooms/:id          # Update room
DELETE /api/v1/rooms/:id          # Delete room
POST   /api/v1/rooms/:id/bots     # Add bot to room
DELETE /api/v1/rooms/:id/bots/:bot # Remove bot from room

# Messages
GET    /api/v1/rooms/:id/messages  # Get messages (paginated)
POST   /api/v1/rooms/:id/messages  # Send message
GET    /api/v1/messages/search     # Search messages

# Bots
GET    /api/v1/bots               # List all bots
GET    /api/v1/bots/:name         # Get bot details
PATCH  /api/v1/bots/:name         # Update bot config
GET    /api/v1/bots/:name/status  # Get bot status

# Configuration
GET    /api/v1/config             # Get full config
PATCH  /api/v1/config             # Update config
POST   /api/v1/config/validate    # Validate config

# Gateway/Channels
GET    /api/v1/gateway/status     # Gateway status
POST   /api/v1/gateway/start      # Start gateway
POST   /api/v1/gateway/stop       # Stop gateway
GET    /api/v1/channels           # List channel connectors
PATCH  /api/v1/channels/:type     # Update channel config

# Export
POST   /api/v1/export/pdf         # Export to PDF
POST   /api/v1/export/markdown    # Export to Markdown
POST   /api/v1/export/json        # Export to JSON

# System
GET    /api/v1/health             # Health check
GET    /api/v1/stats              # Performance stats
POST   /api/v1/restart            # Restart service
```

---

## 7. Component Specifications

### 7.1 Message Renderer (json-render)

```typescript
// Message structure from AI
interface RenderMessage {
    type: 'multi-part';
    parts: RenderPart[];
}

type RenderPart = 
    | TextPart
    | CodePart
    | ThinkingPart
    | MermaidPart
    | ToolResultPart
    | FilePart;

interface TextPart {
    type: 'text';
    content: string;
    markdown?: boolean;
}

interface CodePart {
    type: 'code';
    language: string;
    content: string;
    filename?: string;
}

interface ThinkingPart {
    type: 'thinking';
    content: string;
    isVisible: boolean;
}

interface MermaidPart {
    type: 'mermaid';
    diagram: string;
}

interface ToolResultPart {
    type: 'tool_result';
    tool: string;
    input: any;
    output: string;
    success: boolean;
}

interface FilePart {
    type: 'file';
    name: string;
    size: number;
    mimeType: string;
    content?: string;
}
```

### 7.2 Component Registry

```typescript
// Frontend component mapping
const componentRegistry = {
    'text': TextMessage,
    'code': CodeBlock,
    'thinking': ThinkingBubble,
    'mermaid': MermaidDiagram,
    'tool_result': ToolResult,
    'file': FileAttachment,
    'metric': MetricCard,
    'chart': ChartComponent,
    'alert': AlertMessage,
    'button': ActionButton,
    'progress': ProgressBar
};
```

---

## 8. User Interface Design

### 8.1 Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Header                                                     │
│  [Logo] [Room Name]                    [Search] [Settings] │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  Sidebar     │  Chat Area                                   │
│              │                                              │
│  WORKSPACES  │  ┌────────────────────────────────────────┐ │
│  📁 General  │  │ Messages                               │ │
│  📁 Coding   │  │ [Bot] Hello!                          │ │
│  📁 Research │  │ [User] Can you help?                  │ │
│              │  │ [Bot] Thinking...                     │ │
│  DIRECT MSGS │  └────────────────────────────────────────┘ │
│  💬 @coder   │                                              │
│  💬 @research│  Input Area                                  │
│              │  [Attach] [Mention] [Voice] [Text Input] [Send]│
│  BOT FLEET   │                                              │
│  🟢 Leader   │                                              │
│  🟡 Coder    │                                              │
│  🟢 Research │                                              │
│              │                                              │
├──────────────┴──────────────────────────────────────────────┤
│  Status Bar                                                 │
│  [Tailscale: 🟢 Connected] [Gateway: 🟢 Running] [Memory: 45%]│
└─────────────────────────────────────────────────────────────┘
```

### 8.2 Settings Panel Structure

```
Settings
├── 🤖 Providers
│   ├── OpenRouter (API Key, Default Model)
│   ├── Anthropic (API Key)
│   ├── OpenAI (API Key)
│   └── [+ Add Provider]
│
├── 💬 Channels
│   ├── Telegram (Toggle, Bot Token)
│   ├── WhatsApp (Toggle, QR Code)
│   ├── Discord (Toggle, Bot Token)
│   ├── Slack (Toggle, App Token)
│   └── [+ Add Channel]
│
├── 🌐 Gateway
│   ├── Enable Gateway (Toggle)
│   ├── Port (Default: 18790)
│   ├── Security Level
│   │   ├── 🟢 Secure (Tailscale only)
│   │   ├── 🟡 LAN Only
│   │   └── 🔴 Insecure (⚠️ Warning)
│   └── Tailscale Status
│
├── 🧠 Memory
│   ├── Enable Memory (Toggle)
│   ├── Database Location
│   ├── Max Size
│   └── Export/Import
│
├── 🛡️ Security
│   ├── Sanitize Secrets (Toggle)
│   ├── Skill Verification (Toggle)
│   └── Allowed File Paths
│
├── 🎨 Appearance
│   ├── Theme (Dark/Light/System)
│   ├── Font Size
│   ├── Compact Mode (Toggle)
│   └── Message Density
│
├── ⌨️ Shortcuts
│   ├── New Room (Ctrl+N)
│   ├── Search (Ctrl+K)
│   ├── Settings (Ctrl+,)
│   └── [Customize]
│
└── 🔄 Updates
    ├── Auto-update (Toggle)
    ├── Current Version
    └── Check for Updates
```

---

## 9. Implementation Phases

### Phase 1: Core Foundation (Weeks 1-4)

**Week 1: Project Setup**
- [ ] Initialize Go module and project structure
- [ ] Setup Wails v2 with Svelte 5 template
- [ ] Configure build system (Makefile, GitHub Actions)
- [ ] Setup Tailwind + Skeleton UI
- [ ] Implement basic layout components

**Week 2: Backend Core**
- [ ] SQLite schema and migrations
- [ ] Room management (CRUD operations)
- [ ] Message storage and retrieval
- [ ] Basic agent loop integration

**Week 3: Frontend Core**
- [ ] Room list sidebar
- [ ] Chat interface
- [ ] Message input with markdown
- [ ] Settings panel structure

**Week 4: Integration**
- [ ] Wails bindings (Go ↔ Svelte)
- [ ] Configuration persistence
- [ ] Dark/light mode
- [ ] Basic error handling

### Phase 2: Intelligence (Weeks 5-8)

**Week 5: Advanced Chat**
- [ ] json-render message components
- [ ] Code syntax highlighting
- [ ] File attachments (drag & drop)
- [ ] Message search

**Week 6: Bot Management**
- [ ] Bot status indicators
- [ ] Mention picker (@ autocomplete)
- [ ] Bot configuration per room
- [ ] Create room with bot selection

**Week 7: Configuration**
- [ ] Provider settings UI
- [ ] Channel configuration
- [ ] Gateway settings with security warnings
- [ ] Import/export settings

**Week 8: Voice & Export**
- [ ] Voice input (press-and-hold)
- [ ] Export to PDF
- [ ] Export to Markdown
- [ ] Export to JSON

### Phase 3: Gateway & Channels (Weeks 9-10)

**Week 9: Gateway Implementation**
- [ ] WebSocket server
- [ ] REST API endpoints
- [ ] Tailscale integration
- [ ] Security level enforcement

**Week 10: Channel Connectors**
- [ ] Telegram integration
- [ ] Message sync (GUI ↔ Channels)
- [ ] Unified message history
- [ ] Gateway status monitoring

### Phase 4: Server Mode (Weeks 11-12)

**Week 11: Docker & Server**
- [ ] Dockerfile optimization
- [ ] Docker Compose setup
- [ ] Web GUI mode (serve via HTTP)
- [ ] Reverse proxy configuration

**Week 12: Deployment**
- [ ] Auto-updater
- [ ] Release workflow
- [ ] Documentation
- [ ] Performance optimization

### Phase 5: Advanced Features (Weeks 13-16)

**Week 13-14: Collaboration**
- [ ] Bot coordination view
- [ ] Split view (multiple rooms)
- [ ] Advanced keyboard shortcuts
- [ ] Command palette

**Week 15-16: Polish**
- [ ] Skill marketplace UI
- [ ] Performance dashboard
- [ ] Mobile-responsive testing
- [ ] Beta testing & bug fixes

---

## 10. Deployment Specifications

### 10.1 Desktop Build

```bash
# macOS
wails build -platform darwin/universal

# Windows
wails build -platform windows/amd64

# Linux
wails build -platform linux/amd64
```

### 10.2 Docker Deployment

```dockerfile
# Dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY backend/ ./
RUN go mod download
RUN go build -o nanofolks-server ./cmd/server

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/nanofolks-server .
COPY --from=builder /app/frontend/dist ./frontend/dist
EXPOSE 18790
CMD ["./nanofolks-server"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  nanofolks:
    image: nanofolks/nanofolks:latest
    container_name: nanofolks
    ports:
      - "127.0.0.1:18790:18790"  # Localhost only by default
    volumes:
      - ./data:/root/.nanofolks
      - ./skills:/app/skills
    environment:
      - NANOFOKS_SECURITY_LEVEL=secure
      - NANOFOKS_TAILSCALE_REQUIRED=true
    networks:
      - nanofolks-network
    restart: unless-stopped

networks:
  nanofolks-network:
    driver: bridge
```

### 10.3 Tailscale Setup

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
tailscale up

# Get Tailscale IP
tailscale ip -4

# Configure Nanofolks to bind to Tailscale IP
# Settings → Gateway → Bind Address: 100.x.x.x
```

---

## 11. Security Considerations

### 11.1 Secret Management

```go
// Secrets are never stored in plain text in config
type SecretStore interface {
    Get(key string) (string, error)
    Set(key string, value string) error
    Delete(key string) error
}

// Platform-specific implementations:
// - macOS: Keychain
// - Windows: Credential Manager
// - Linux: Secret Service (libsecret)
// - Server: Environment variables or Docker secrets
```

### 11.2 API Key Sanitization

```go
// All logs and UI displays sanitize secrets
func SanitizeSecrets(text string) string {
    patterns := []string{
        `sk-or-v1-[a-zA-Z0-9]{20,}`,  // OpenRouter
        `sk-ant-[a-zA-Z0-9]{20,}`,     // Anthropic
        `sk-[a-zA-Z0-9]{20,}`,         // OpenAI
    }
    // Replace with masked versions
}
```

### 11.3 Security Levels

```go
type SecurityLevel int

const (
    SecurityLevelSecure SecurityLevel = iota   // Tailscale required
    SecurityLevelLAN                           // Local network only
    SecurityLevelInsecure                      // Any interface (warning)
)

func ValidateSecurityLevel(level SecurityLevel, hasTailscale bool) error {
    if level == SecurityLevelSecure && !hasTailscale {
        return fmt.Errorf("Security level 'secure' requires Tailscale")
    }
    return nil
}
```

---

## 12. Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **App Launch** | < 2 seconds | Cold start on SSD |
| **Message Send** | < 100ms | Local SQLite write |
| **Room Switch** | < 50ms | Render 50 messages |
| **Search** | < 200ms | Full-text search on 10k messages |
| **Memory** | < 200MB | Idle with 5 rooms open |
| **Bundle Size** | < 50MB | Desktop installer |
| **Binary Size** | < 30MB | Single executable |

---

## 13. Testing Strategy

### 13.1 Backend Tests

```go
// Unit tests
backend/internal/*_test.go

// Integration tests  
backend/test/integration/*_test.go

// E2E tests
backend/test/e2e/*_test.go
```

### 13.2 Frontend Tests

```typescript
// Component tests
frontend/src/lib/components/**/*.test.ts

// Store tests
frontend/src/lib/stores/**/*.test.ts

// E2E tests (Playwright)
frontend/e2e/*.spec.ts
```

### 13.3 Manual Testing Checklist

- [ ] Create room with each theme
- [ ] Send messages with @mentions
- [ ] Test DM conversations
- [ ] Configure all providers
- [ ] Enable/disable channels
- [ ] Export to all formats
- [ ] Test voice input
- [ ] Verify Tailscale integration
- [ ] Test security level warnings
- [ ] Verify dark/light mode

---

## 14. Future Roadmap

### Phase 6: Multi-Device Sync (Post-MVP)

- [ ] GUI Gateway for PC-to-PC sync
- [ ] Distributed state synchronization
- [ ] Conflict resolution
- [ ] End-to-end encryption for sync

### Phase 7: Advanced Features

- [ ] Plugin system for custom components
- [ ] Advanced analytics dashboard
- [ ] Team collaboration features
- [ ] White-label customization

### Phase 8: Mobile

- [ ] PWA with offline support
- [ ] Native mobile apps (Capacitor)
- [ ] Push notifications
- [ ] Biometric authentication

---

## 15. Appendices

### A. Environment Variables

```bash
# Core
NANOFOLKS_CONFIG_DIR=/path/to/config
NANOFOLKS_DATA_DIR=/path/to/data
NANOFOLKS_LOG_LEVEL=debug|info|warn|error

# Gateway
NANOFOLKS_GATEWAY_ENABLED=true
NANOFOLKS_GATEWAY_PORT=18790
NANOFOLKS_GATEWAY_BIND=127.0.0.1
NANOFOLKS_SECURITY_LEVEL=secure|lan|insecure

# Tailscale
NANOFOLKS_TAILSCALE_REQUIRED=true
NANOFOLKS_TAILSCALE_AUTH_KEY=tskey-...

# Development
NANOFOLKS_DEV_MODE=true
NANOFOLKS_HOT_RELOAD=true
```

### B. File Locations

```
macOS:   ~/Library/Application Support/nanofolks/
Windows: %APPDATA%/nanofolks/
Linux:   ~/.config/nanofolks/
Docker:  /root/.nanofolks/ (volume mounted)
```

### C. Related Documentation

- [Wails Documentation](https://wails.io/docs/)
- [Svelte 5 Documentation](https://svelte.dev/docs/svelte)
- [Skeleton UI Documentation](https://www.skeleton.dev/)
- [Tailscale Documentation](https://tailscale.com/kb/)

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-16  
**Authors:** Nanofolks Team  
**Status:** Draft - Ready for Implementation
