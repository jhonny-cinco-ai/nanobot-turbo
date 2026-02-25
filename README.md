<div align="center">
  <img src="nanofolks_header.png" alt="nanofolks" width="660">
  <h1>nanofolks - Your crew's already on it.</h1>
  <p>
    <a href="https://pypi.org/project/nanofolks/"><img src="https://img.shields.io/pypi/v/nanofolks" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanofolks"><img src="https://static.pepy.tech/badge/nanofolks" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

nanofolks is a platform for building friendly AI crews, teams of characters that collaborate to help you think, create, plan, and build.

Instead of a single assistant, you work alongside a crew of AI specialists with distinct roles and personalities.

From pirate captains to space explorers to creative misfits, your companions don't just respond. They work together.

Pick the kind of crew that fits you.


## What Makes nanofolks Different?

| | |
|---|---|
| ✨ | **Collaboration** over automation |
| 🎭 | **Characters** over tools |
| 🤝 | **Companionship** over commands |
| 🏠 | **Room-centric** organization over fragmented sessions |

> It's not just an assistant. It's a team.

One that can help with:

- planning
- creative work
- coding
- research
- social media
- everyday life

and so much more!


## Built to work in real life.

nanofolks provides a flexible architecture for:

| | |
|---|---|
| 🧠 | multi-agent collaboration |
| 🧩 | role-based personalities |
| 🔧 | extensibility |
| 💬 | multi-platform interaction |
| 🏠 | room-centric session organization |

**Inspired by nanobot's simplicity, nanofolks expands the concept into a more expressive, team-oriented system.**

> [!TIP]
> nanofolks is a fork of [nanobot](https://github.com/HKUDS/nanobot). We maintain certain compatibility while adding crew-based features.

---


# Quick Start


## Installation

### System Dependencies (Optional - for secure keyring)

For secure API key storage on headless Linux servers:

```bash
# Ubuntu/Debian
apt install gnome-keyring libdbus-glib-1-2
```

This enables the OS Keychain/Keyring to store API keys securely instead of in config files.

### From Source (Recommended)

```bash
git clone https://github.com/nanofolks/nanofolks.git
cd nanofolks
pip install -e .
```

### With uv (Recommended for Mac/Local Dev)

`uv` is a modern, ultra-fast Python manager. It automatically manages virtual environments and Python versions for you without touching your system Python.

**1. Install nanofolks locally:**
```bash
git clone https://github.com/nanofolks/nanofolks.git
cd nanofolks
uv pip install -e .
```

*This creates a `.venv` directory instantly and installs nanofolks in "editable" mode.*

**2. Run with isolation:**
You don't need to "activate" anything. Just use `uv run`:
```bash
uv run nanofolks onboard
```

**Why use uv?**
- **Speed**: Installing is nearly instant.
- **Safety**: Everything stays in your project's `.venv` folder.
- **Python Management**: If a specific Python version is needed, `uv` downloads it for you automatically.

*Global installation alternative:*
```bash
uv tool install nanofolks
```

### With pip

```bash
pip install nanofolks
```

### Docker

```bash
docker build -t nanofolks .
```


## Setup

Run the onboarding wizard:

```bash
nanofolks onboard
```

This will guide you through:

| Step | Description |
|------|-------------|
| **1. Security** | Keyring check for secure API key storage |
| **2. Provider + Model** | Select your AI provider and default model |
| **3. Network Security** | Tailscale + secure ports info |
| **4. Team** | Choose your crew's personality |
| **5. Launch** | Create your workspace and crew |

Smart routing and evolutionary mode are enabled by default and can be changed anytime with `nanofolks configure`.

### Web Tools

nanofolks ships with a fast web search + robust page fetching pipeline:

- **Brave Search** for quick discovery (enable by adding a Brave API key).
- **Smart page fetching** with `web_fetch` using Readability.
- **Scrapling fallback** for hard/anti‑bot pages (enabled by default).
- **Agent‑browser** for authenticated actions (enabled by default, but always requires user confirmation).

Configure these in:

```bash
nanofolks configure
```

### Your Team

Each nanofolks crew has 6 bots:

| Bot | Role | What they do |
|-----|------|--------------|
| **Leader** (@nanofolks) | Coordinator | Plans, delegates, makes decisions |
| **Researcher** (@researcher) | Research | Analyzes, gathers information |
| **Coder** (@coder) | Development | Codes, debugs, builds |
| **Social** (@social) | Community | Engages, communicates |
| **Creative** (@creative) | Creative | Brainstorms, designs, creates |
| **Auditor** (@auditor) | Quality | Reviews, validates, tests |

That's it! Your crew is ready to go!


## Start Chatting

```bash
nanofolks chat -m "Hello!"
```

Or enter interactive mode:

```bash
nanofolks chat
```

---


# Chat Apps

Connect nanofolks to your favorite messaging platforms.

| Channel | Setup | Notes |
|---------|-------|-------|
| **Telegram** | Easy | Bot token only |
| **Discord** | Easy | Bot token + intents |
| **WhatsApp** | Medium | Scan QR code |
| **Slack** | Medium | Socket mode |

<details>
<summary><b>Telegram</b> (Recommended)</summary>

1. Create a bot: Search `@BotFather` on Telegram, send `/newbot`, follow prompts
2. Copy the token
3. Configure:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

4. Run: `nanofolks gateway`

</details>

<details>
<summary><b>Discord</b></summary>

1. Create an app at https://discord.com/developers/applications
2. Add a bot, enable **Message Content Intent**
3. Copy the bot token
4. Configure:

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```

5. Invite the bot to your server
6. Run: `nanofolks gateway`

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires Node.js ≥18.

1. Link device:
   ```bash
   nanofolks channels login
   # Scan QR with WhatsApp → Settings → Linked Devices
   ```

2. Configure:

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

3. Run both:
   ```bash
   # Terminal 1
   nanofolks channels login
   
   # Terminal 2
   nanofolks gateway
   ```

</details>

<details>
<summary><b>Slack</b></summary>

1. Create app at https://api.slack.com/apps
2. Enable Socket Mode, get App-Level Token
3. Add scopes: `chat:write`, `app_mentions:read`
4. Configure:

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-..."
    }
  }
}
```

5. Run: `nanofolks gateway`

</details>

---


# Core Concepts

This section explains the architectural concepts behind nanofolks. Understanding these will help you configure and customize your crew.


## 🤖 Multi-Bot Architecture

nanofolks supports multiple AI characters working together as a crew.

### The Crew Concept

A "crew" is a group of 6 AI characters, each with:

- **Personality** - How they respond (from the team)
- **Role** - What they're good at
- **Expertise** - Specific knowledge domains

### Teams & Personalities

nanofolks comes with **built-in teams** that give your crew distinct personalities:

| Team | Vibe | Example |
|-------|------|---------|
| **Pirate Crew** | Bold, adventurous | "Arr, let's find that treasure!" |
| **Space Crew** | Sci-fi, mission-focused | "Engaging warp drive..." |
| **Rock Band** | Creative, energetic | "Time to rock this!" |
| **Executive Suite** | Professional, corporate | "Let's discuss the quarterly objectives" |
| **SWAT Team** | Tactical, precise | "Moving in for the takedown" |
| **Feral Clowder** | Chaotic, cat-like | "*knocks things off desk*"

Choose a team during setup to give your crew personality!

### Your Team

Each nanofolks crew has 6 bots:

| Bot | Role | Expertise |
|-----|------|-----------|
| **Leader** (@leader) | Coordinates the crew | Planning, delegation, decision-making |
| **Researcher** (@researcher) | Deep research | Analysis, information gathering |
| **Coder** (@coder) | Technical implementation | Code, debugging, architecture |
| **Social** (@social) | Community engagement | Communication, user relations |
| **Creative** (@creative) | Creative work | Design, brainstorming, content |
| **Auditor** (@auditor) | Quality review | Validation, compliance, testing |

### How It Works

```
Workspace/
├── identity/            # Bot personalities & team styles
│   ├── pirate_crew/   # Pirate crew style
│   ├── space_crew/    # Space crew style
│   └── ...
├── role/               # Bot roles (Leader, Coder, Researcher...)
├── soul/               # Bot soul files (personality, greeting)
├── bots/               # Bot instructions
├── memory/             # Shared knowledge
├── skills/            # Crew skills
└── config.yaml        # Crew configuration
```

### Single Bot Mode

Not ready for a full crew? nanofolks works perfectly as a single assistant:
- Default General room has one bot
- Works in DM mode
- Same memory and learning capabilities
- Easy to add more bots later

### Why Multiple Bots?

| Benefit | Example |
|---------|---------|
| **Specialization** | Coding bot, research bot |
| **Personality** | Different characters for moods |
| **Collaboration** | Bots discuss and debate |
| **Reliability** | Backup if one is unavailable |

### Unified Orchestrator Pipeline

nanofolks runs every message through a single, consistent pipeline:

1. **Tag** — Parse explicit @bot mentions and action words.
2. **Intent** — Detect what the user wants (rule-based with LLM fallback when unsure).
3. **Dispatch** — Decide which bots should handle it (Leader-first by default).
4. **Collect** — Gather responses from assigned bots.
5. **Final** — Produce one clear response for the user.

This keeps multi-bot teamwork predictable and easy to debug, while still letting the Leader coordinate the crew.

### Sidekicks (Focused Helpers)

Bots can spawn short-lived sidekicks for focused sub-tasks. Sidekicks work with minimal context, return summaries to their parent bot, and never speak in the room directly. The parent bot merges results and responds in its own voice.


## 🧠 Memory System

nanofolks has a production-hardened memory system that learns from every conversation.

### How It Works

| Phase | Description |
|-------|-------------|
| **Event Logging** | Every message (user and assistant) is stored in a local SQLite database with full conversation context |
| **Entity Extraction** | The system automatically identifies people, places, organizations, and concepts mentioned in conversations |
| **Knowledge Graph** | Entities are connected through relationships, creating a map of what you've discussed |
| **Fast Semantic Search** | HNSW-based vector index enables millisecond-speed search over millions of memories |
| **Preference Learning** | nanofolks detects feedback patterns and learns your communication style, preferences, and habits over time |
| **Context Assembly** | When you send a message, nanofolks retrieves relevant memories and assembles them into context |

### Why It Matters

Unlike simple chat histories, nanofolks builds a persistent knowledge base that:
- Survives restarts and new conversations
- Connects related information across time
- Searches semantically (find "dog" when you search "pet")
- Improves the more you use it

---

## 💾 Session Storage & CAS

nanofolks uses **CAS (Compare-And-Set) storage** for conflict-free concurrent writes to session files.

### The Problem

When multiple channels (Telegram, Discord, WhatsApp) write to the same room simultaneously:
- Race conditions can corrupt session files
- Messages can be lost
- Data inconsistency between channels

### The Solution: CAS Storage

```
Traditional Write:     CAS Write:
Read → Write           Read → Hash → Compare → Write
   ↓                        ↓
Write (overwrites)    Match? → Write (or retry)
```

| Feature | Description |
|---------|-------------|
| **ETag Versioning** | Each write includes a content hash |
| **Conflict Detection** | Detects if another channel wrote first |
| **Auto-Merge** | Merges concurrent writes automatically |
| **Retry Logic** | Exponential backoff on conflicts |

### Multi-Channel Safety

CAS storage ensures:
- ✅ No file corruption from concurrent writes
- ✅ Message ordering preserved within rooms
- ✅ Safe fallback if one channel crashes
- ✅ Works alongside memory system (SQLite WAL)

### Configuration

CAS storage is **enabled by default**. To disable:

```json
{
  "storage": {
    "use_cas_storage": false
  }
}
```

Or via environment variable:
```bash
export NANOFOLKS_USE_CAS_STORAGE=false
```

> [!NOTE]
> The memory system uses SQLite with WAL mode, which already handles concurrency safely. CAS storage specifically protects session (chat history) files.

---


## 💭 Chain of Thought

nanofolks doesn't just respond. It thinks through problems.

### The Pattern

```
Observation → Thought → Action → Observation → Thought → (repeat)
```

### Multi-Turn Reasoning

For complex tasks, nanofolks can:
- Break down problems into steps
- Plan before executing
- Reflect on intermediate results
- Correct mistakes mid-process

### Tool Execution Loop

When tools are needed, nanofolks:
1. Decides which tool to use
2. Executes the tool
3. Observes the result
4. Incorporates results into thinking
5. Continues or responds

---


## 📦 Context Compaction

Long conversations can exceed AI model limits. nanofolks intelligently manages this.

### The Problem

AI models have maximum context windows (typically 8K-200K tokens). Without management:
- Conversations eventually hit the limit
- Old context gets dropped
- nanofolks "forgets" earlier parts of the conversation

### How Compaction Works

| Step | Description |
|------|-------------|
| **Token Tracking** | Real-time counting using tiktoken (not estimates) |
| **Threshold Warning** | 70% → shows warning in response |
| **Compaction Trigger** | 80% → triggers smart compression |
| **Tool Chain Safety** | Never separates tool calls from results |

### Compaction Modes

| Mode | When to Use |
|------|-------------|
| **Summary** | Default - AI generates smart summaries |
| **Token-Limit** | Emergency - preserves recent messages only |
| **Off** | Manual - you control when to compact |

### Large Output Handling

Tool outputs over 10KB are stored separately in SQLite to prevent:
- API errors from oversized payloads
- Context pollution
- Cost overruns

---


## 🎯 Tier-Aware Routing

Not every message needs the most powerful (and expensive) AI model. nanofolks intelligently routes messages to appropriate models.

### The Two-Layer System

```
User Message
    ↓
Layer 1: Client-Side Classification (~1ms)
  → Fast heuristic analysis
  → Handles ~85% of messages instantly
    ↓ (if ambiguous)
Layer 2: LLM-Assisted Classification (~200ms)
  → More accurate edge case handling
    ↓
Execute with Selected Model
```

### Tiers

| Tier | When Used | Example |
|------|-----------|---------|
| **Simple** | Quick questions | "What's the weather?" |
| **Medium** | General tasks | "Write me an email" |
| **Complex** | Detailed work | "Analyze this data" |
| **Reasoning** | Logic problems | "Prove this theorem" |
| **Coding** | Programming | "Debug this function" |

### Sticky Routing

Once a tier is selected, it "sticks" for the conversation context:
- Consistent responses
- Cost predictability
- Better coherence

### Cost Savings

> [!NOTE]
> These figures are estimates based on typical usage patterns. Actual savings depend on your message distribution and model selection. Run `nanofolks routing analytics` to see your real cost data.

Typical usage (45% simple, 35% medium, 15% complex, 5% reasoning):

| Scenario | Cost per Million Tokens |
|----------|------------------------|
| **Without routing** | $75.00 (always best model) |
| **With routing** | $3.17 (blended) |
| **Savings** | **Up to 96%** 🎉 |

### Smart Routing Configuration

Enable automatic model selection:

```json
{
  "routing": {
    "enabled": true,
    "tiers": {
      "simple": {"model": "gpt-4o-mini"},
      "medium": {"model": "claude-sonnet-4"},
      "complex": {"model": "claude-opus-4"},
      "reasoning": {"model": "o3"}
    }
  }
}
```


---


## 🛡️ Unified Security Architecture

nanofolks implements a unified security architecture that protects credentials across all entry points - from user chat input to automated tasks like routines and skill loading.

### Core Protection Layers

| Layer | What It Protects | Implementation |
|-------|------------------|----------------|
| **1. Secure Storage** | Keys at rest | OS Keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service) |
| **2. Symbolic References** | Keys in transit | `{{key_name}}` resolved at execution time, never sent to LLM |
| **3. Credential Detection** | Keys in user input | Auto-detects API keys/tokens before they reach LLM |
| **4. Runtime Resolution** | Keys at execution | KeyVault resolves refs only when tools actually run |
| **5. Safe Logging** | Keys in logs | Audit logs contain only references, never actual keys |
| **6. Defense in Depth** | Keys in edge cases | Secret Sanitizer (regex masking) as final fallback |

#### Layer 6: Secret Sanitizer (Defense in Depth)

The Secret Sanitizer serves as the final safety net, catching any credentials that might slip through the primary layers:

**What It Detects:**
- API keys (OpenRouter, Anthropic, OpenAI, Groq, etc.)
- Tokens (Bearer tokens, JWTs)
- Credentials (Passwords, database strings)
- Keys (Private keys, SSH credentials)

**Where It Applies:**

| Location | Protection |
|----------|------------|
| **AI Messages** | Secrets masked before reaching the LLM |
| **Log Files** | Nothing sensitive written to disk |
| **Session History** | Stored conversations have secrets removed |
| **Tool Outputs** | Results screened before display |

**Example:**
```
Input:  "My API key is sk-or-v1-abc123..."
Output: "My API key is sk-or-v1-ab***..." (masked)
```

> [!NOTE]
> The Secret Sanitizer is a **secondary** defense layer. The primary protection is the symbolic reference system (Layers 1-5) which prevents keys from ever being exposed.

### How It Works: The Security Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER INPUT                                                 │
│ "Create PR using token ghp_abc123xyz"                        │
└──────────────────────────┬────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. CREDENTIAL DETECTION                                       │
│ Detects: ghp_abc123xyz → github_token                        │
│ Converts to: "Create PR using token {{github_token}}"       │
└──────────────────────────┬────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. LLM PROCESSES (symbolic refs only)                        │
│ LLM sees: {{github_token}}                                   │
└──────────────────────────┬────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. TOOL EXECUTION                                             │
│ ToolRegistry.resolve_symbolic_params() → KeyVault.get()      │
│ {{github_token}} → ghp_abc123xyz (briefly in memory)       │
└──────────────────────────┬────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. AUDIT LOG                                                  │
│ Logged: "Used {{github_token}}" (never the actual key)     │
└─────────────────────────────────────────────────────────────┘
```

### Skill Security

Skills can execute arbitrary code and access files, so they undergo security scanning before being loaded.

#### Risk Levels

| Level | Description | Auto-load |
|-------|-------------|-----------|
| **Critical** | Executes shell commands, writes files, makes network calls | Never |
| **High** | Accesses sensitive directories or reads sensitive files | After approval |
| **Medium** | Uses external APIs or has broad file access | After approval |
| **Low** | Pure text transformation, no side effects | Always |

#### Scanning Process

1. **Auto-scan on Discovery** - When a new skill is detected, it's automatically scanned
2. **Risk Assessment** - The scanner analyzes the skill for:
   - Shell command execution (`subprocess`, `os.system`, etc.)
   - File system access patterns
   - Network requests
   - Environment variable usage
3. **Decision** - Based on risk level:
   - **Low/Medium** → Available but requires approval
   - **High/Critical** → Blocked until manually approved

#### Manual Approval

For skills that need review:

```bash
# After reviewing the skill code:
nanofolks skills approve <skill_name>

# Or scan a skill before adding:
nanofolks skills scan /path/to/skill
```

> [!TIP]
> Always review skill code before approving, especially those with **High** or **Critical** risk ratings.

---

## 🏠 Rooms & Collaboration

nanofolks uses **rooms** as collaboration spaces where your crew works together. Think of rooms as dedicated spaces for different projects, topics, or conversation types.

### What Are Rooms?

A **room** is a conversation context where:
- Multiple bots can participate together
- Context is shared among all participants
- Bots can @mention each other to collaborate
- Work gets coordinated through the Leader

### Room Types

| Type | Description | Use Case |
|------|-------------|----------|
| **OPEN** | General discussion room | Casual chat, #general |
| **PROJECT** | Focused team workspace | Specific projects with deadlines |
| **DIRECT** | 1-on-1 with a bot | Private DM with @researcher |
| **COORDINATION** | Leader-managed room | Autonomous coordination mode |

### Room Tasks

Each room can track **tasks** so your crew’s work stays organized. Tasks belong to a room, have an owner and status, and include **handoff history** when ownership changes. When the Leader assigns a bot, nanofolks also creates a matching room task automatically so progress stays visible.

### Room-Centric Architecture

nanofolks uses a **room-centric architecture** where everything is organized by room. This provides:

| Benefit | Description |
|---------|-------------|
| **Persistent Sessions** | Conversation history is stored per-room |
| **Cross-Platform Continuity** | Same room ID works across Telegram, Discord, CLI, etc. |
| **Organized Storage** | All data (sessions, memory, work logs) organized by room |
| **Easy Retrieval** | Find conversations by room name |

#### How It Works

```
room:general          → Default room for all conversations
room:project-abc123  → Project room (multi-platform)
```

#### Room Storage Architecture

```
~/.nanofolks/
├── rooms/
│   ├── general.json           # General room data
│   ├── project-abc123.json    # Project room
│   └── channel_mappings.json  # Maps channels to rooms
├── project_states/            # Per-room discovery/flow state
│   └── <room_id>.json
└── work_logs.db              # Per-room work logs
```

### The @ Mention System

Use **@** to direct messages to specific bots or the entire crew:

#### Direct to a Bot
```
@researcher analyze market trends for Q3
→ Researcher responds with analysis

@coder implement user authentication
→ Coder writes the code

@creative design a landing page hero
→ Creative creates concepts
```

#### Broadcast to All
```
@all review this architecture proposal
→ All bots in the room respond with feedback

@crew brainstorm marketing ideas
→ Entire crew collaborates
```

#### Leader Coordination (Default)
```
I need help planning the product launch
→ Leader coordinates which bots should help
→ May involve researcher (market), creative (branding), coder (landing page)
```

### How @ Routing Works

1. **@botname mentioned?** → Goes directly to that bot
2. **@all or @crew mentioned?** → Broadcast to all room participants
3. **No mention?** → Leader analyzes and coordinates response

#### Best Practices

**When to use @mentions:**
- ✅ Use `@botname` when you know exactly who should help
- ✅ Use `@all` for brainstorming or decisions needing multiple perspectives
- ✅ No mention for general questions (Leader coordinates)

**Room organization:**
- Create PROJECT rooms for specific initiatives
- Keep #general as OPEN for casual chat
- Use DIRECT when you need a bot's specific expertise privately
- Leader can auto-create rooms when you describe a project

### Room Creation by Leader

The Leader can create rooms automatically when you ask:

```
You: Create a room for the website redesign project
Leader: Created room 'website-redesign' with appropriate team members

You: Set up a space for the Q4 planning
Leader: Created 'q4-planning' room with researcher and creative
```

### Shared Context

Rooms maintain shared context across the conversation:

```
You: @researcher find data on renewable energy
Researcher: [shares findings]

You: @creative use that data for an infographic
Creative: [accesses the same research context]

You: @coder build a dashboard with those stats
Coder: [references previous findings]
```

---

## 💓 Multi-Heartbeat System

nanofolks doesn't just wait for you to message it. It can proactively act.

### Routines (Scheduled Tasks)

nanofolks supports routines (scheduled tasks). There are two kinds:

- **Your Routines**: reminders or recurring tasks you create
- **Team Routines**: background check-ins that keep the crew “alive”

You can control both from the CLI, without needing to know what a cron job is.

Example:

```bash
nanofolks routines add --name "morning" --message "What's on my calendar?" --schedule "0 9 * * *"
nanofolks routines list
nanofolks routines remove <id>
```

### Proactive Wake-Up

Team routines:
- Wakes nanofolks at scheduled times
- Runs background tasks
- Can message you proactively
- Maintains state between runs

### Activity Tracking

Monitors when you're active to:
- Determine when to run background processing
- Avoid interrupting conversations
- Optimize memory extraction timing


## 📝 Work Logs

nanofolks maintains persistent logs of completed work for future reference.

### What Gets Logged

| Type | Examples |
|------|----------|
| Task completions | Timestamps, outcomes |
| Tool executions | Results, errors |
| Research | Findings, sources |
| Artifacts | Generated files, code |

### Why It Matters

Work logs enable:
- **Audit trail** - Know what was done and when
- **Context continuity** - Pick up where you left off
- **Reference** - Look back at previous solutions
- **Learning** - nanofolks improves from past work

### Access

Work logs are stored in the workspace and can be:
- Searched via memory commands
- Referenced in conversations
- Exported for external use

---


# ⚙️ Configuration


## Providers

nanofolks supports multiple AI providers:

| Provider | Purpose | Get Key |
|----------|---------|---------|
| **OpenRouter** | LLM gateway (recommended) | [openrouter.ai](https://openrouter.ai) |
| **Anthropic** | Claude direct | [console.anthropic.com](https://console.anthropic.com) |
| **OpenAI** | GPT direct | [platform.openai.com](https://platform.openai.com) |
| **DeepSeek** | DeepSeek direct | [platform.deepseek.com](https://platform.deepseek.com) |
| **Groq** | Fast inference + voice | [console.groq.com](https://console.groq.com) |
| **Gemini** | Google AI | [aistudio.google.com](https://aistudio.google.com) |
| **vLLM** | Local models | Run your own server |


## Environment Variables

nanofolks also respects these env vars:

- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- And provider-specific keys for each supported provider

---


# CLI Commands


## Essential Commands

| Command | Description |
|---------|-------------|
| `nanofolks onboard` | First-time setup |
| `nanofolks configure` | Interactive configuration |
| `nanofolks chat -m "msg"` | Send a message |
| `nanofolks chat` | Interactive chat mode |
| `nanofolks gateway` | Start multi-channel gateway |
| `nanofolks metrics` | Show live broker/routines metrics |

## Memory & Session

```bash
nanofolks memory status       # Show memory statistics
nanofolks memory search "query"  # Search memories
nanofolks memory rebuild-index   # Rebuild semantic search index
nanofolks session status     # Show context usage
nanofolks session compact    # Manual compaction
```

## Routing

```bash
nanofolks routing status     # Show routing config
nanofolks routing test "msg" # Test classification
nanofolks routing analytics  # Show cost savings
```


## Rooms

```bash
nanofolks room create project-alpha  # Create a new project room
nanofolks room invite project-alpha researcher  # Invite bots
nanofolks room show project-alpha    # See who's in the room
nanofolks room list                  # List all your rooms
```

## Room Tasks

```bash
nanofolks room task list --room project-alpha
nanofolks room task list --room project-alpha --owner researcher
nanofolks room task add --room project-alpha --owner coder --priority high --due 2025-01-15 "Ship landing page"
nanofolks room task status --room project-alpha <task_id> done
nanofolks room task assign --room project-alpha <task_id> researcher --reason "Needs deep research"
nanofolks room task handoff --room project-alpha <task_id> creative --reason "Shift to design phase"
nanofolks room task history --room project-alpha <task_id>
```


## Skills

### How Skills Work

nanofolks uses **progressive loading** to keep responses fast:

1. **Skills Summary** - All available skills are listed in the system prompt with name, description, and file path
2. **On-Demand Loading** - When the agent needs a skill, it reads the skill file automatically
3. **Zero Overhead** - Full skill instructions only load when actually used

This keeps every conversation lightweight while giving access to all capabilities.

### Available Skills

| Skill | Description |
|-------|-------------|
| `humanizer` | Remove AI writing patterns from text |
| `github` | GitHub CLI integration |
| `weather` | Weather info (wttr.in, Open-Meteo) |
| `summarize` | URL, file, and YouTube summarization |
| `tmux` | Terminal session management |
| `skill-creator` | Create new skills |

### Adding Custom Skills

Place a `SKILL.md` file in `workspace/skills/your-skill/`. It will be auto-discovered and security-scanned before becoming available.

> [!TIP]
> See [Skill Security](#skill-security) below for details on the scanning process.

### Skill CLI Commands

```bash
nanofolks skills list              # List all available skills with status
nanofolks skills scan <path>       # Security scan a skill before adding
nanofolks skills approve <name>    # Manually approve a skill after review
```


## Scheduled Tasks

```bash
nanofolks routines add --name "task" --message "Do X" --schedule "0 9 * * *"
nanofolks routines list
nanofolks routines remove <id>
```

---


# Docker


## Basic Usage

```bash
# Build
docker build -t nanofolks .

# Initialize config
docker run -v ~/.nanofolks:/root/.nanofolks --rm nanofolks onboard

# Run gateway
docker run -v ~/.nanofolks:/root/.nanofolks -p 18790:18790 nanofolks gateway
```

## Persisting Data

> [!TIP]
> The `-v ~/.nanofolks:/root/.nanofolks` flag mounts your config directory, so your settings and memory persist across restarts.

---


# 💡 Philosophy

> **nanofolks isn't about replacing you.**
> 
> It's about expanding what you can do, by surrounding you with the right crew.

We believe AI should:
- ✨ Work *with* you, not *for* you
- 🎭 Have personality and character
- 📈 Learn and improve over time
- 🤝 Feel like a team, not a tool

---


# Links & Resources

| | |
|---|---|
| 📖 | **Documentation**: [docs/](docs/) |
| 🐛 | **Issues**: [GitHub Issues](https://github.com/nanofolks/nanofolks/issues) |
| 💬 | **Community**: [Discord](https://discord.gg/nanofolks) |
| ⭐ | **Star us**: [GitHub](https://github.com/nanofolks/nanofolks) |

---


# Credits

nanofolks started as a fork of [nanobot](https://github.com/HKUDS/nanobot), a project by HKUDS. We're grateful for the foundation they built and continue to draw inspiration from their vision of making AI assistants accessible and fun.

This project is for educational, research, and technical exchange purposes only.

---

<p align="center">
  <em>Your crew's already on it.</em>
</p>
