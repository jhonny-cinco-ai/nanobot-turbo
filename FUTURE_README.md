<div align="center">
  <img src="nanobot_logo.png" alt="Nanofolks" width="500">
  <h1>Nanofolks — Your crew's already on it.</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanobot-ai"><img src="https://static.pepy.tech/badge/nanobot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

Nanofolks is a platform for building friendly AI crews — teams of characters that collaborate to help you think, create, plan, and build.

Instead of interacting with a single assistant, Nanofolks lets you work alongside a group of AI specialists with distinct roles and personalities.

From pirate crews to space teams to creative collectives, your AI companions don't just respond — they work together.

## What Makes Nanofolks Different?

| | |
|---|---|
| ✨ | **Collaboration** over automation |
| 🎭 | **Characters** over tools |
| 🤝 | **Companionship** over commands |

It's not just an assistant — it's a team.

One that can help with:

- planning
- creative work
- coding
- research
- social media
- everyday life

and so much more!

## Built for Real Use

Nanofolks provides a flexible architecture for:

| | |
|---|---|
| 🧠 | multi-agent collaboration |
| 🧩 | role-based personalities |
| 🔧 | extensibility |
| 💬 | multi-platform interaction |

**Inspired by nanobot's simplicity, Nanofolks expands the concept into a more expressive, team-oriented system.**

> [!TIP]
> Nanofolks is a fork of [nanobot](https://github.com/HKUDS/nanobot). We maintain full compatibility while adding crew-based features.

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

Nanofolks doesn't just respond — it thinks through problems.

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
| **Summary** | Default — AI generates smart summaries |
| **Token-Limit** | Emergency — preserves recent messages only |
| **Off** | Manual — you control when to compact |

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

Nanofolks doesn't just wait for you to message it — it can proactively act.

### Scheduled Tasks (Cron)

```bash
# Every morning at 9am
nanobot cron add --name "morning" --message "What's on my calendar?" --cron "0 9 * * *"

# Hourly health checks
nanobot cron add --name "hourly" --message "Check system status" --every 3600
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
- **Audit trail** — Know what was done and when
- **Context continuity** — Pick up where you left off
- **Reference** — Look back at previous solutions
- **Learning** — Nanofolks improves from past work

### Access

Work logs are stored in the workspace and can be:
- Searched via memory commands
- Referenced in conversations
- Exported for external use

---

## 🤖 Multi-Bot Architecture

Nanofolks supports multiple AI characters working together as a crew.

### The Crew Concept

A "crew" is a group of AI characters, each with:
- **Personality** — How they respond
- **Role** — What they're good at
- **Expertise** — Specific knowledge domains

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
nanobot onboard
```

This will guide you through:

| Step | Description |
|------|-------------|
| **1. Crew Selection** | Choose from 6 themes |
| **2. Provider Setup** | Select your AI provider |
| **3. Model Selection** | Choose default model |
| **4. Optional Features** | Smart routing, voice |

### Crew Themes

| Theme | Description |
|-------|-------------|
| **Generalists** | Balanced team for everyday tasks |
| **Pirates** | Adventure-themed crew |
| **Space Crew** | Sci-fi exploration team |
| **Explorers** | Research-focused |
| **Creatives** | Writing and art |
| **Custom** | Build your own |

## Add Your API Key

After onboarding, add your API key to `~/.nanobot/config.json`:

```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

> [!TIP]
> Get API keys from: [OpenRouter](https://openrouter.ai/keys), [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), etc.

## Start Chatting

```bash
nanobot agent -m "Hello!"
```

Or enter interactive mode:

```bash
nanobot agent
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

4. Run: `nanobot gateway`

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
6. Run: `nanobot gateway`

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requires Node.js ≥18.

1. Link device:
   ```bash
   nanobot channels login
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
   nanobot channels login
   
   # Terminal 2
   nanobot gateway
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

5. Run: `nanobot gateway`

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
| `nanobot onboard` | First-time setup |
| `nanobot configure` | Interactive configuration |
| `nanobot agent -m "msg"` | Send a message |
| `nanobot agent` | Interactive chat mode |
| `nanobot gateway` | Start multi-channel gateway |

## Memory & Session

```bash
nanobot memory status       # Show memory statistics
nanobot memory search "query"  # Search memories
nanobot session status     # Show context usage
nanobot session compact    # Manual compaction
```

## Routing

```bash
nanobot routing status     # Show routing config
nanobot routing test "msg" # Test classification
nanobot routing analytics  # Show cost savings
```

## Skills

```bash
nanobot skills list        # List all skills
nanobot skills scan ./skill  # Security scan
nanobot skills approve name # Approve skill
```

## Scheduled Tasks

```bash
nanobot cron add --name "task" --message "Do X" --cron "0 9 * * *"
nanobot cron list
nanobot cron remove <id>
```

---

# Docker

## Basic Usage

```bash
# Build
docker build -t nanofolks .

# Initialize config
docker run -v ~/.nanobot:/root/.nanobot --rm nanofolks onboard

# Run gateway
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanofolks gateway
```

## Persisting Data

> [!TIP]
> The `-v ~/.nanobot:/root/.nanobot` flag mounts your config directory, so your settings and memory persist across restarts.

---

# Philosophy

Nanofolks isn't about replacing you.

It's about surrounding you with the right help — in a way that feels natural, collaborative, and even a little fun.

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

Nanofolks started as a fork of [nanobot](https://github.com/HKUDS/nanobot), a project by HKUDS. We're grateful for the foundation they built and continue to draw inspiration from their vision of making AI assistants accessible and fun.

This project is for educational, research, and technical exchange purposes only.

---

<p align="center">
  <em>Your crew's already on it.</em>
</p>
