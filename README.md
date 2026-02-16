<div align="center">
  <img src="nanofolks_logo.png" alt="Nanofolks" width="500">
  <h1>Nanofolks - Your crew's already on it.</h1>
  <p>
    <a href="https://pypi.org/project/nanofolks-ai/"><img src="https://img.shields.io/pypi/v/nanofolks-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanofolks-ai"><img src="https://static.pepy.tech/badge/nanofolks-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

Nanofolks is a platform for building friendly AI crews, teams of characters that collaborate to help you think, create, plan, and build.

Instead of a single assistant, you work alongside a crew of AI specialists with distinct roles and personalities.

From pirate captains to space explorers to creative misfits, your companions don't just respond. They work together.

Pick the kind of crew that fits you.

## What Makes Nanofolks Different?

| | |
|---|---|
| ✨ | **Collaboration** over automation |
| 🎭 | **Characters** over tools |
| 🤝 | **Companionship** over commands |

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

Nanofolks provides a flexible architecture for:

| | |
|---|---|
| 🧠 | multi-agent collaboration |
| 🧩 | role-based personalities |
| 🔧 | extensibility |
| 💬 | multi-platform interaction |

**Inspired by nanofolks's simplicity, Nanofolks expands the concept into a more expressive, team-oriented system.**

> [!TIP]
> Nanofolks is a fork of [nanofolks](https://github.com/HKUDS/nanofolks). We maintain full compatibility while adding crew-based features.

---

# Core Concepts

This section explains the architectural concepts behind Nanofolks. Understanding these will help you configure and customize your crew.

## 🧠 Memory System

Nanofolks has a production-hardened memory system that learns from every conversation.

### How It Works

| Phase | Description |
|-------|-------------|
| **Event Logging** | Every message (user and assistant) is stored in a local SQLite database with full conversation context |
| **Entity Extraction** | The system automatically identifies people, places, organizations, and concepts mentioned in conversations |
| **Knowledge Graph** | Entities are connected through relationships, creating a map of what you've discussed |
| **Preference Learning** | Nanofolks detects feedback patterns and learns your communication style, preferences, and habits over time |
| **Context Assembly** | When you send a message, Nanofolks retrieves relevant memories and assembles them into context |

### Why It Matters

Unlike simple chat histories, Nanofolks builds a persistent knowledge base that:
- Survives restarts and new conversations
- Connects related information across time
- Improves the more you use it

---

## 🔐 Secret Sanitizer

Nanofolks automatically protects sensitive information from being exposed.

### What It Detects

| Pattern | Examples |
|---------|----------|
| API keys | OpenRouter, Anthropic, OpenAI, Groq |
| Tokens | Bearer tokens, JWTs |
| Credentials | Passwords, database strings |
| Keys | Private keys, SSH credentials |

### Where It Applies

The sanitizer intercepts content at multiple points:

| Location | Protection |
|----------|------------|
| **AI Messages** | Secrets masked before reaching the LLM |
| **Log Files** | Nothing sensitive written to disk |
| **Session History** | Stored conversations have secrets removed |
| **Tool Outputs** | Results screened before display |

### Example

```
Input:  "My API key is sk-or-v1-abc123..."
Output: "My API key is sk-or-v1-ab***..." (masked)
```

---

## 🛡️ Skill Verification Flow

Skills extend Nanofolks' capabilities. Before any skill is used, it goes through security verification.

### The Workflow

```
┌─────────────────┐
│ 1. Auto-Detect │
│   New skills   │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 2. Risk Scoring │
│   Analyze code │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 3. Approval     │
│   Block if risk │
└────────┬────────┘
         ↓
┌─────────────────┐
│ 4. Runtime      │
│   Verification  │
└─────────────────┘
```

### Risk Levels

| Level | Icon | Examples |
|-------|------|----------|
| **Critical** | 🚫 | Credential theft, malware |
| **High** | ⚠️ | Shell injection, system mods |
| **Medium** | ⚡ | Obfuscation, suspicious downloads |
| **Low** | ℹ️ | Binary execution, external URLs |

---

## 💭 Chain of Thought

Nanofolks doesn't just respond. It thinks through problems.

### The Pattern

```
Observation → Thought → Action → Observation → Thought → (repeat)
```

### Multi-Turn Reasoning

For complex tasks, Nanofolks can:
- Break down problems into steps
- Plan before executing
- Reflect on intermediate results
- Correct mistakes mid-process

### Tool Execution Loop

When tools are needed, Nanofolks:
1. Decides which tool to use
2. Executes the tool
3. Observes the result
4. Incorporates results into thinking
5. Continues or responds

---

## 📦 Context Compaction

Long conversations can exceed AI model limits. Nanofolks intelligently manages this.

### The Problem

AI models have maximum context windows (typically 8K-200K tokens). Without management:
- Conversations eventually hit the limit
- Old context gets dropped
- Nanofolks "forgets" earlier parts of the conversation

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

Not every message needs the most powerful (and expensive) AI model. Nanofolks intelligently routes messages to appropriate models.

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

Typical usage (45% simple, 35% medium, 15% complex, 5% reasoning):

| Scenario | Cost per Million Tokens |
|----------|------------------------|
| **Without routing** | $75.00 (always best model) |
| **With routing** | $3.17 (blended) |
| **Savings** | **Up to 96%** 🎉 |

---

## 💓 Multi-Heartbeat System

Nanofolks doesn't just wait for you to message it. It can proactively act.

### Scheduled Tasks (Cron)

```bash
# Every morning at 9am
nanofolks cron add --name "morning" --message "What's on my calendar?" --cron "0 9 * * *"

# Hourly health checks
nanofolks cron add --name "hourly" --message "Check system status" --every 3600
```

### Proactive Wake-Up

The heartbeat system:
- Wakes Nanofolks at scheduled times
- Runs background tasks
- Can message you proactively
- Maintains state between runs

### Activity Tracking

Monitors when you're active to:
- Determine when to run background processing
- Avoid interrupting conversations
- Optimize memory extraction timing

---

## 📝 Work Logs

Nanofolks maintains persistent logs of completed work for future reference.

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
- **Learning** - Nanofolks improves from past work

### Access

Work logs are stored in the workspace and can be:
- Searched via memory commands
- Referenced in conversations
- Exported for external use

---

## 🤖 Multi-Bot Architecture

Nanofolks supports multiple AI characters working together as a crew.

### The Crew Concept

A "crew" is a group of 6 AI characters, each with:

- **Personality** - How they respond (from the theme)
- **Role** - What they're good at
- **Expertise** - Specific knowledge domains

### Your Team

Each Nanofolks crew has 6 bots:

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
├── bots/
│   ├── leader.yaml      # Primary bot
│   ├── specialist.yaml # Additional bots
│   └── creative.yaml
├── memory/             # Shared knowledge
├── skills/             # Crew skills
└── config.yaml         # Crew configuration
```

### Single Bot Mode

Not ready for a full crew? Nanofolks works perfectly as a single assistant:
- Default workspace has one bot
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

---

## 🏠 Rooms & Collaboration

Nanofolks uses **rooms** as collaboration spaces where your crew works together. Think of rooms as dedicated spaces for different projects, topics, or conversation types.

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

### Creating and Managing Rooms

Create rooms for different projects or contexts:

```bash
# Create a new project room
nanofolks room create project-alpha

# Invite bots to the room
nanofolks room invite project-alpha researcher
nanofolks room invite project-alpha coder
nanofolks room invite project-alpha creative

# See who's in the room
nanofolks room show project-alpha

# List all your rooms
nanofolks room list
```

### The @ Mention System

Use **@** to direct messages to specific bots or the entire crew:

#### Direct to a Bot
```
@researcher analyze market trends for Q3
→ ResearcherBot responds with analysis

@coder implement user authentication
→ CoderBot writes the code

@creative design a landing page hero
→ CreativeBot creates concepts
```

#### Broadcast to All
```
@all review this architecture proposal
→ All bots in the room respond with feedback

@crew brainstorm marketing ideas
→ Entire crew collaborates on ideas
```

#### Leader Coordination (Default)
```
I need help planning the product launch
→ Leader coordinates which bots should help
→ May involve researcher (market), creative (branding), coder (landing page)
```

### How @ Routing Works

When you send a message, Nanofolks intelligently routes it:

1. **@botname mentioned?** → Goes directly to that bot
2. **@all or @crew mentioned?** → Broadcast to all room participants
3. **No mention?** → Leader analyzes and coordinates response

```
You: @researcher find competitors in the AI space
    ↓
ResearcherBot: Here's what I found...

You: @all what do you think of this strategy?
    ↓
ResearcherBot: From a data perspective...
CreativeBot: The branding approach should be...
CoderBot: Technically, we could implement...
Leader: Let me synthesize these perspectives...
```

### Direct Messages (DMs)

Chat with a single bot privately without room context:

```bash
# DM a specific bot
nanofolks agent -m "@researcher analyze this data privately"

# Or enter interactive mode and use @ mentions
nanofolks agent
> @researcher what are the latest trends?
```

**DMs vs Rooms:**
- **DMs** → Private 1-on-1, bot's individual expertise
- **Rooms** → Collaborative, shared context, multiple perspectives

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
ResearcherBot: [shares findings]

You: @creative use that data for an infographic
CreativeBot: [accesses the same research context]

You: @coder build a dashboard with those stats
CoderBot: [references previous findings]
```

### CLI Commands for Rooms

| Command | Description |
|---------|-------------|
| `nanofolks room list` | Show all rooms |
| `nanofolks room create <name>` | Create new room |
| `nanofolks room invite <room> <bot>` | Add bot to room |
| `nanofolks room remove <room> <bot>` | Remove bot from room |
| `nanofolks room show <room>` | Show room details |

### Best Practices

**When to use @mentions:**
- ✅ Use `@botname` when you know exactly who should help
- ✅ Use `@all` for brainstorming or decisions needing multiple perspectives
- ✅ No mention for general questions (Leader coordinates)

**Room organization:**
- Create PROJECT rooms for specific initiatives
- Keep #general as OPEN for casual chat
- Use DIRECT when you need a bot's specific expertise privately
- Leader can auto-create rooms when you describe a project

---

# Quick Start

## Installation

### From Source (Recommended)

```bash
git clone https://github.com/nanofolks/nanofolks.git
cd nanofolks
pip install -e .
```

### With uv

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
| **1. Provider Setup** | Select your AI provider and API key |
| **2. Model Selection** | Choose default model |
| **3. Smart Routing** | Enable automatic model tier selection |
| **4. Evolutionary Mode** | Optional self-improvement features |
| **5. Team Theme** | Choose your crew's personality |

### Your Team

Each Nanofolks crew has 6 bots:

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
nanofolks agent -m "Hello!"
```

Or enter interactive mode:

```bash
nanofolks agent
```

---

# Chat Apps

Connect Nanofolks to your favorite messaging platforms.

| Channel | Setup | Notes |
|---------|-------|-------|
| **Telegram** | Easy | Bot token only |
| **Discord** | Easy | Bot token + intents |
| **WhatsApp** | Medium | Scan QR code |
| **Slack** | Medium | Socket mode |
| **Feishu** | Medium | WebSocket |
| **QQ** | Easy | App credentials |

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

# Configuration

## Providers

Nanofolks supports multiple AI providers:

| Provider | Purpose | Get Key |
|----------|---------|---------|
| **OpenRouter** | LLM gateway (recommended) | [openrouter.ai](https://openrouter.ai) |
| **Anthropic** | Claude direct | [console.anthropic.com](https://console.anthropic.com) |
| **OpenAI** | GPT direct | [platform.openai.com](https://platform.openai.com) |
| **DeepSeek** | DeepSeek direct | [platform.deepseek.com](https://platform.deepseek.com) |
| **Groq** | Fast inference + voice | [console.groq.com](https://console.groq.com) |
| **Gemini** | Google AI | [aistudio.google.com](https://aistudio.google.com) |
| **vLLM** | Local models | Run your own server |

## Smart Routing

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

## Environment Variables

Nanofolks also respects these env vars:

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
| `nanofolks agent -m "msg"` | Send a message |
| `nanofolks agent` | Interactive chat mode |
| `nanofolks gateway` | Start multi-channel gateway |

## Memory & Session

```bash
nanofolks memory status       # Show memory statistics
nanofolks memory search "query"  # Search memories
nanofolks session status     # Show context usage
nanofolks session compact    # Manual compaction
```

## Routing

```bash
nanofolks routing status     # Show routing config
nanofolks routing test "msg" # Test classification
nanofolks routing analytics  # Show cost savings
```

## Skills

```bash
nanofolks skills list        # List all skills
nanofolks skills scan ./skill  # Security scan
nanofolks skills approve name # Approve skill
```

## Scheduled Tasks

```bash
nanofolks cron add --name "task" --message "Do X" --cron "0 9 * * *"
nanofolks cron list
nanofolks cron remove <id>
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

# Philosophy

Nanofolks isn't about replacing you.

It's about expanding what you can do, by surrounding you with the right crew.

We believe AI should:
- Work *with* you, not *for* you
- Have personality and character
- Learn and improve over time
- Feel like a team, not a tool

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

Nanofolks started as a fork of [nanofolks](https://github.com/HKUDS/nanofolks), a project by HKUDS. We're grateful for the foundation they built and continue to draw inspiration from their vision of making AI assistants accessible and fun.

This project is for educational, research, and technical exchange purposes only.

---

<p align="center">
  <em>Your crew's already on it.</em>
</p>
