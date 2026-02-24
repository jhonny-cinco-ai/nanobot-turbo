# Nanobot Multi-Bot Architecture Analysis

## Executive Summary

This document provides a comprehensive Python analysis of the `nanofolks agent` and `nanofolks gateway` commands, focusing on how the multi-bot architecture is implemented, how work logs are displayed, and how bot activity is shown to users.

---

## 1. NANOBOT AGENT COMMAND (`nanofolks agent`)

### Location
**File**: `nanofolks/cli/commands.py:827-969`

### Purpose
Interactive CLI mode for direct conversation with the nanofolks agent. This is the primary user interface for single-bot or multi-bot interaction.

### Command Flow

```python
# Entry point
def agent(
    message: str = typer.Option(None, "--message", "-m"),
    session_id: str = typer.Option("cli:default", "--session", "-s"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs"),
):
    """Interact with the agent directly."""
```

### Architecture Flow

```
User Input
    ↓
1. Load Config → load_config()
    ↓
2. Create MessageBus → async communication layer
    ↓
3. Create Provider → LiteLLMProvider for LLM calls
    ↓
4. Create AgentLoop → Core processing engine
    ↓
5a. Single Message Mode → process_direct() → Exit
    ↓
5b. Interactive Mode → prompt_toolkit loop
    ↓
User types message
    ↓
AgentLoop.process_direct()
    ↓
AgentLoop._process_message()
    ↓
LLM Call with Tools
    ↓
Response to User
```

### Key Components

#### AgentLoop (`nanofolks/agent/loop.py`)
The core message processing engine with these key responsibilities:

**Initialization** (lines 43-271):
- Initializes tools registry
- Sets up work_log_manager for transparency
- Creates BotInvoker for delegating to specialist bots
- Applies team to SOUL files on first start
- Configures memory system (if enabled)
- Sets up routing stage for smart model selection

**Message Processing** (lines 553-977):
```python
async def _process_message(self, msg: MessageEnvelope) -> MessageEnvelope | None:
    """Process a single inbound message."""
    # 1. Handle system messages (bot announcements)
    if msg.channel == "system":
        return await self._process_system_message(msg)
    
    # 2. Sanitize input for security
    sanitized_content = self.sanitizer.sanitize(msg.content)
    
    # 3. Log to work log manager
    self.work_log_manager.log(...)
    
    # 4. Mark activity for background processing
    if self.activity_tracker:
        self.activity_tracker.mark_activity()
    
    # 5. Get or create session
    session = self.sessions.get_or_create(key)
    
    # 6. Build memory context
    memory_context = self.context_assembler.assemble_context(...)
    
    # 7. Select model using smart routing
    selected_model = await self._select_model(msg, session)
    
    # 8. Agent loop with tool execution
    while iteration < self.max_iterations:
        response = await self.provider.chat(...)
        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, tool_call.arguments)
                # Log tool execution
                self.work_log_manager.log_tool(...)
        else:
            final_content = response.content
            break
    
    # 9. Save to session and memory
    session.add_message("user", sanitized_user_content)
    session.add_message("assistant", sanitized_assistant_content)
    
    # 10. Return outbound message
    return MessageEnvelope(channel=msg.channel, chat_id=msg.chat_id, content=final_content)
```

---

## 2. NANOBOT GATEWAY COMMAND (`nanofolks gateway`)

### Location
**File**: `nanofolks/cli/commands.py:544-817`

### Purpose
Starts the full nanofolks server with multi-bot support, channels (Telegram, Discord, Slack), routines, and dashboard.

### Command Flow

```python
# Entry point
def gateway(
    port: int = typer.Option(18790, "--port", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Start the nanofolks gateway."""
```

### Architecture Flow

```
Start Gateway
    ↓
1. Load Config
    ↓
2. Create MessageBus
    ↓
3. Create AgentLoop (Leader)
    ↓
4. Create RoutinesService
    ↓
5. Create Team Manager with 6 Bots:
   - NanobotLeader (Coordinator)
   - ResearcherBot
   - CoderBot
   - SocialBot
   - AuditorBot
   - CreativeBot
    ↓
6. Create DashboardService (port 9090)
    ↓
7. Create ChannelManager (Telegram, Discord, Slack, etc.)
    ↓
8. Start all services concurrently
    ↓
asyncio.gather(
    agent.run(),          # Process messages
    channels.start_all(), # Listen to chat platforms
    dashboard_service.start(),
)
```

### Multi-Bot Initialization (lines 648-746)

```python
# Create all 6 bot instances
from nanofolks.bots.implementations import (
    ResearcherBot, CoderBot, SocialBot, 
    AuditorBot, CreativeBot, NanobotLeader
)

# Load appearance configuration (teams and custom names)
appearance_config = get_appearance_config()
team_manager = appearance_config.team_manager

# Create bot instances with auto-initialization
researcher = ResearcherBus(
    bus=bus,
    workspace_id=str(config.workspace_path),
    workspace=config.workspace_path,
    team_manager=team_manager,
    custom_name=appearance_config.get_custom_name("researcher")
)
# ... similar for coder, social, auditor, creative, nanofolks

# Initialize team manager
multi_manager = MultiCrewRoutinesManager()
multi_manager.register_bot(researcher)
multi_manager.register_bot(coder)
multi_manager.register_bot(social)
multi_manager.register_bot(auditor)
multi_manager.register_bot(creative)
multi_manager.register_bot(nanofolks)
```

---

## 3. MULTI-BOT ARCHITECTURE IMPLEMENTATION

### Core Architecture: Leader-First with Specialist Bots

```
                    ┌─────────────────────────────────────┐
                    │           USER MESSAGE              │
                    └──────────────┬──────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────┐
                    │    BotDispatch.dispatch_message()   │
                    │        (nanofolks/bots/dispatch.py)   │
                    └──────────────┬──────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
    │  DM Direct   │      │ @bot Mention │      │ Default      │
    │              │      │              │      │ Leader First │
    └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
           │                     │                     │
           ▼                     ▼                     ▼
    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
    │ Direct Bot   │      │ Mentioned    │      │ nanofolks      │
    │ Response     │      │ Bot Direct   │      │ Leader       │
    └──────────────┘      └──────────────┘      └──────┬───────┘
                                                       │
                              ┌────────────────────────┼────────────────────────┐
                              │                        │                        │
                              ▼                        ▼                        ▼
                    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
                    │ @researcher      │    │ @coder           │    │ @creative        │
                    │ Deep Research    │    │ Implementation   │    │ Design           │
                    └──────────────────┘    └──────────────────┘    └──────────────────┘
```

### Bot Dispatch Rules (`nanofolks/bots/dispatch.py:74-135`)

```python
def dispatch_message(self, message: str, room: Optional[Room] = None,
                     is_dm: bool = False, dm_target: Optional[str] = None) -> DispatchResult:
    """Determine who should handle this message."""
    
    # Case 1: Direct Message (DM) - bypass leader
    if is_dm and dm_target:
        return DispatchResult(
            target=DispatchTarget.DM,
            primary_bot=dm_target,
            secondary_bots=[],
            reason=f"Direct message to @{dm_target}"
        )
    
    # Case 2: User tagged specific bot - bypass leader
    mentioned_bot = self._extract_mention(message)
    if mentioned_bot:
        if mentioned_bot == "all":
            return DispatchResult(
                target=DispatchTarget.DIRECT_BOT,
                primary_bot="nanofolks",  # Leader coordinates
                secondary_bots=room.participants if room else ["nanofolks"],
                reason="User tagged @all/@crew - leader coordinates all bots"
            )
        else:
            return DispatchResult(
                target=DispatchTarget.DIRECT_BOT,
                primary_bot=mentioned_bot,
                secondary_bots=[],
                reason=f"User tagged @{mentioned_bot} directly"
            )
    
    # Case 3: Default - Route through Leader first
    return DispatchResult(
        target=DispatchTarget.LEADER_FIRST,
        primary_bot="nanofolks",
        secondary_bots=[p for p in room.participants if p != "nanofolks"] if room else [],
        reason="Default: Leader coordinates response"
    )
```

### Bot Invocation Flow (Background Async)

When the Leader decides to delegate to a specialist bot:

```
Leader Agent
    ↓
invoke_tool.execute() → nanofolks/agent/tools/invoke.py
    ↓
BotInvoker.invoke() → nanofolks/agent/bot_invoker.py
    ↓
_invoke_async() - Fire and forget
    ↓
asyncio.create_task(_process_invocation(...))
    ↓
_process_invocation():
    1. Build bot system prompt from SOUL.md
    2. Call LLM with bot's context
    3. Execute tools if needed
    ↓
_announce_result():
    1. Create system message
    2. Publish to MessageBus
    ↓
AgentLoop._process_system_message():
    1. Receive system message
    2. Summarize for user
    3. Send response
```

### BotInvoker Implementation (`nanofolks/agent/bot_invoker.py`)

```python
class BotInvoker:
    """Manages bot invocations (always async)."""
    
    async def invoke(self, bot_name: str, task: str, context: Optional[str] = None, ...) -> str:
        """Invoke a specialist bot - always async."""
        invocation_id = str(uuid.uuid4())[:8]
        
        # Always async - fire and forget
        return await self._invoke_async(
            invocation_id=invocation_id,
            bot_name=bot_name,
            task=task,
            context=context,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
        )
    
    async def _process_invocation(self, invocation_id: str, bot_name: str, 
                                  task: str, context: Optional[str], ...) -> None:
        """Process a bot invocation and announce result when complete."""
        try:
            # Build system prompt for this bot from SOUL.md
            system_prompt = await self._build_bot_system_prompt(bot_name, task)
            
            # Build user message
            user_message = task
            if context:
                user_message = f"Context from Leader:\n{context}\n\n---\n\nTask:\n{task}"
            
            # Process through LLM with tool execution
            response = await self._call_bot_llm(bot_name, system_prompt, user_message, session_id)
            result = response or "Task completed but no response generated."
            
        except Exception as e:
            result = f"Error: {str(e)}"
            status = "error"
        finally:
            # Announce result back via system message
            await self._announce_result(invocation_id, bot_name, task, result, 
                                       origin_channel, origin_chat_id, status)
```

---

## 4. WORK LOGS SYSTEM

### Purpose
Comprehensive logging of all agent decisions, tool executions, and bot interactions for transparency and debugging.

### Data Model (`nanofolks/agent/work_log.py`)

```python
@dataclass
class WorkLogEntry:
    """A single entry in a work log."""
    timestamp: datetime
    level: LogLevel                    # INFO, THINKING, DECISION, TOOL, HANDOFF, etc.
    step: int                          # Sequential step number
    category: str                      # "memory", "tool", "routing", "bot_conversation"
    message: str                       # Human-readable description
    
    # Tool execution fields
    tool_name: Optional[str]
    tool_input: Optional[dict]
    tool_output: Optional[Any]
    tool_status: Optional[str]         # "success", "error", "timeout"
    
    # Multi-Agent Extension Fields
    room_id: str = "default"
    participants: List[str] = field(default_factory=lambda: ["nanofolks"])
    bot_name: str = "nanofolks"
    bot_role: str = "primary"
    triggered_by: str = "user"
    coordinator_mode: bool = False
    mentions: List[str] = field(default_factory=list)
    response_to: Optional[int] = None
```

### Storage
- **Database**: SQLite at `~/.nanofolks/work_logs.db`
- **Tables**: 
  - `work_logs` - Session-level information
  - `work_log_entries` - Individual log entries with multi-agent support

### Work Log Manager (`nanofolks/agent/work_log_manager.py`)

```python
class WorkLogManager:
    """Manages work logs for agent sessions with SQLite persistence."""
    
    def log(self, level: LogLevel, category: str, message: str,
            details: Optional[dict] = None, confidence: Optional[float] = None,
            duration_ms: Optional[int] = None, bot_name: str = "nanofolks",
            triggered_by: str = "user") -> Optional[WorkLogEntry]:
        """Add an entry to the current work log."""
        entry = self.current_log.add_entry(...)
        self._save_entry(entry)  # Persist to SQLite
        return entry
    
    def log_tool(self, tool_name: str, tool_input: dict, tool_output: any,
                tool_status: str, duration_ms: int) -> Optional[WorkLogEntry]:
        """Log a tool execution."""
        
    def log_bot_message(self, bot_name: str, message: str,
                       response_to: int = None, mentions: list = None) -> Optional[WorkLogEntry]:
        """Log a bot-to-bot communication message."""
        
    def log_escalation(self, reason: str, bot_name: str = "nanofolks") -> Optional[WorkLogEntry]:
        """Log an escalation that needs user attention."""
```

### How Work Logs Are Displayed

#### CLI Commands for Viewing Logs:

```bash
# In interactive mode
/explain              # Show detailed work log for last interaction
/logs                 # Show work log summary
/how "routing"        # Search for specific events

# Standalone commands
nanofolks explain                           # Explain last decision
nanofolks explain --mode summary            # Brief summary
nanofolks explain --mode debug              # Full technical details
nanofolks explain --mode coordination       # Focus on coordinator decisions
nanofolks explain -b @researcher            # See what researcher did
nanofolks how "web_search"                  # Search for tool calls
nanofolks workspace-logs                    # List recent logs
```

#### Display Format Examples:

**Summary Mode**:
```
Work Log Summary
Query: How do I implement authentication?
Steps: 12
Duration: 3.5s

Key Events:
  🎯 Step 3: Classified as medium tier
  🔧 Step 5: Executed web_search
  🔧 Step 7: Executed read_file
  🎯 Step 10: Selected secondary model after primary failure
```

**Detailed Mode**:
```
Detailed Work Log
==================================================
Session: cli:default
Query: How do I implement authentication?
Started: 2026-02-15 14:32:10
Duration: 3.5s

Steps:
--------------------------------------------------

ℹ️ Step 1 [INFO]
   Time: 14:32:10
   Category: general
   Message: Processing user message: How do I implement authentication?

🎯 Step 3 [DECISION]
   Time: 14:32:11
   Category: routing
   Message: Classified as medium tier
   Confidence: 85%
   
🔧 Step 5 [TOOL]
   Time: 14:32:12
   Category: tool_execution
   Message: Executed web_search
   Tool: web_search (success)
   Duration: 1200ms
```

---

## 5. BOT ACTIVITY & STATUS DISPLAY

### Dashboard (`nanofolks/crew_routines/dashboard.py`)

**Real-time monitoring at http://localhost:9090**

```python
class DashboardService:
    """Service for providing real-time dashboard metrics."""
    
    def __init__(self, manager: MultiCrewRoutinesManager = None, 
                 port: int = 9090, update_interval: float = 5.0):
        """Initialize dashboard service."""
        self.manager = manager
        self.port = port
        self.update_interval = update_interval
        self.metrics_buffer = MetricsBuffer(max_entries=1000)
    
    async def _update_metrics_loop(self) -> None:
        """Continuously collect and broadcast metrics every 5 seconds."""
        while self._running:
            metrics = await self._collect_metrics()
            self.metrics_buffer.add(metrics)
            await self._broadcast_to_clients(metrics)
            await asyncio.sleep(self.update_interval)
```

### Dashboard Display

The dashboard shows:
- **Team Health**: Overall success rate bar (0-100%)
- **Running Bots**: X/6 bots active
- **Total Runs**: Cumulative team routine executions
- **Failed Ticks**: Error count
- **Per-Bot Status**: Running/stopped, tick count, success rate
- **Alerts**: Any warnings or errors

### CLI Status Commands

```bash
nanofolks bot status           # Show all bots and routine status
nanofolks routines list        # Show scheduled routines
```

### How Bot Activity Is Shown

**When a bot is invoked (async)**:
1. User sees immediate confirmation: "@researcher (Navigator) is on the task. I'll share the results when ready."
2. Work log captures the handoff
3. Bot works in background
4. When complete, result announced as system message
5. Leader summarizes for user

**During bot execution**:
```python
# Work log captures:
- HANDOFF entry: "Delegating task to @researcher"
- Tool execution entries from specialist bot
- Completion entry: "@researcher completed the task"

# User sees:
[Bot @researcher (Navigator) completed]

Task: Research Python authentication libraries

Result:
[Research findings here...]

Summarize this naturally for the user...
```

---

## 6. KEY ARCHITECTURAL PATTERNS

### Pattern 1: MessageBus for Decoupled Communication

```python
# All communication goes through MessageBus
class MessageBus:
    inbound: asyncio.Queue[MessageEnvelope]    # External → Agent
    outbound: asyncio.Queue[MessageEnvelope]  # Agent → External
    system: asyncio.Queue[SystemMessage]      # Internal coordination
```

### Pattern 2: Tool Registry with Permissions

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None
    def execute(self, name: str, arguments: dict) -> str
    def get_definitions(self) -> List[dict]  # For LLM function calling
```

### Pattern 3: State per Bot via SOUL.md

```python
class ContextBuilder:
    def build_messages(self, bot_name: str = "nanofolks", ...) -> List[dict]:
        """Build system prompt with bot-specific SOUL.md"""
        soul = self._load_soul_for_bot(bot_name)
        identity = self._load_identity_for_bot(bot_name)
        agents = self._load_agents_for_bot(bot_name)
        # Combine into system prompt
```

### Pattern 4: Always-Async Bot Delegation

```python
# NEVER block the main agent waiting for bot response
async def invoke(bot_name: str, task: str) -> str:
    # Fire and forget
    asyncio.create_task(_process_invocation(...))
    # Return immediately with confirmation
    return f"@{bot_name} is on the task..."
```

---

## 7. SUMMARY

### Multi-Bot Architecture Highlights

1. **Leader-First Dispatch**: All messages go through nanofolks first, unless user directly mentions a bot or sends a DM
2. **Async Bot Invocation**: Specialist bots work in background and announce results via system messages
3. **State Isolation**: Each bot has its own SOUL.md, IDENTITY.md, and AGENTS.md for personality and permissions
4. **Unified Work Logging**: All bot interactions logged with multi-agent context (room_id, bot_name, mentions, etc.)
5. **Real-time Dashboard**: Live monitoring of all 6 bots at http://localhost:9090

### Work Log Display

- **Stored in**: SQLite database (`~/.nanofolks/work_logs.db`)
- **View via**: CLI commands (`explain`, `how`, `workspace-logs`)
- **Shows**: All decisions, tool executions, bot handoffs, errors, timing
- **Multi-bot support**: Each entry tracks which bot, room, and participants

### Bot Activity Display

- **Immediate**: User gets confirmation when bot is invoked
- **Background**: Bot works asynchronously
- **Completion**: Result announced and summarized by Leader
- **Monitoring**: Dashboard shows real-time bot status and health

---

## 8. FILE REFERENCE

| Component | File |
|-----------|------|
| Agent Command | `nanofolks/cli/commands.py:827-969` |
| Gateway Command | `nanofolks/cli/commands.py:544-817` |
| AgentLoop | `nanofolks/agent/loop.py` |
| BotInvoker | `nanofolks/agent/bot_invoker.py` |
| Invoke Tool | `nanofolks/agent/tools/invoke.py` |
| WorkLog Data Model | `nanofolks/agent/work_log.py` |
| WorkLog Manager | `nanofolks/agent/work_log_manager.py` |
| Bot Dispatch | `nanofolks/bots/dispatch.py` |
| Bot Implementations | `nanofolks/bots/implementations.py` |
| Dashboard | `nanofolks/crew_routines/dashboard.py` |
| MessageBus | `nanofolks/bus/queue.py` |
| ContextBuilder | `nanofolks/agent/context.py` |

---

*Analysis completed: 2026-02-15*
*Total lines of code analyzed: ~5000+*
