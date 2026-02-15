# Room Integration in CLI Agent

## Overview

Rooms are now fully integrated into the nanobot CLI agent experience. Users can now see which room they're in, view participants, and understand multi-bot collaboration directly from the terminal interface.

---

## Features Implemented

### 1. Room Selection with --room Parameter

**Command:**
```bash
nanobot agent --room <room_id>
```

**Examples:**
```bash
# Join the default general room
nanobot agent

# Join a specific project room
nanobot agent --room project-alpha

# Short form
nanobot agent -r project-alpha
```

**Behavior:**
- If room doesn't exist, falls back to "general" room with warning
- Room context is automatically loaded and passed through the conversation
- Room information is stored in work logs for transparency

---

### 2. Enhanced TUI Header with Room Context

When you start interactive mode, you now see:

```
🤖 nanobot v1.0 - AI Companion

Interactive mode

Room Context
🌐 #general (open) • 1 bot • 🟢 Active

Participants:
  leader

Commands:
  /room          Show room details
  /explain       Show how last decision was made
  /logs          Show work log summary
  /how <topic>   Search work log for specific topic
  exit           Exit conversation

[#general] You: 
```

**Room Status Indicators:**
- 🌐 **OPEN** - General discussion room (anyone can see)
- 📁 **PROJECT** - Focused project room with deadline
- 💬 **DIRECT** - 1-on-1 conversation with specific bot
- 🤖 **COORDINATION** - Autonomous multi-bot coordination

**Activity Status:**
- 🟢 **Active** - Message in last 5 minutes
- 🟡 **Recent** - Message in last hour
- 🔵 **Idle** - No recent activity

---

### 3. Room Indicator in Prompt

The prompt now shows the current room:

```
[#general] You: hello
[#project-alpha] You: analyze this
[#dm-researcher] You: what do you think?
```

This allows users to always know which room they're working in.

---

### 4. /room Command - Show Room Details

**Command:**
```
/room
```

**Output:**
```
📁 Room: #project-alpha
   Type: project
   Participants (3):
   • leader
   • coder
   • researcher

Use 'nanobot room invite project-alpha <bot>' to add bots
```

**Shows:**
- Room name and type
- All current participants (bots in the room)
- Commands to manage room

---

### 5. /explain Command - Room-Aware Work Logs

The `/explain` command now shows room context in the work log:

```
Work Log
┌──────────────────────────────────────────────┐
│ Session: cli:default                         │
│ Room: #project-alpha (project)              │
│ Participants: nanobot, coder, researcher    │
│ Duration: 2.34s                             │
└──────────────────────────────────────────────┘
```

**Room context includes:**
- Room ID and type
- List of participants in the room
- Any coordination or multi-bot interactions

---

### 6. Room Context in System Prompt

The agent now understands room context when responding:

**Implicit in system prompt:**
```
## Room Context
Room: #project-alpha
Type: project
Participants: leader, coder, researcher

You are collaborating in this room with other bots. 
Use @botname to mention specific bots when you need their expertise.
```

**What this enables:**
- Agent knows which bots are available in the room
- Agent can invoke specialist bots with @mentions
- Agent understands it's in collaborative mode
- Agent can coordinate work across team members

---

### 7. Work Log Room Filtering

**Command:**
```bash
nanobot explain -w #project-alpha
nanobot explain --workspace #project-alpha
```

**Use cases:**
- See all work logs for a specific project room
- Filter by room type (project vs general vs direct)
- Track multi-bot interactions in a specific context

---

## Usage Examples

### Example 1: Working on a Project

```bash
# Create a project room
nanobot room create website-redesign
nanobot room invite website-redesign coder
nanobot room invite website-redesign creative

# Join the room and start working
nanobot agent --room website-redesign
```

**You'll see:**
```
📁 #website-redesign (project) • 3 bots • 🟢 Active
Participants: leader, coder, creative
```

**Prompt shows:**
```
[#website-redesign] You: I need help designing the homepage
```

**Agent response uses room context:**
```
I can help! Since we have @coder and @creative in this room,
let me coordinate with them on the design.

@coder - I'll need technical architecture
@creative - Let's brainstorm the visual design
```

---

### Example 2: Research Task

```bash
# Create a research project
nanobot room create market-research
nanobot room invite market-research researcher
nanobot room invite market-research social

# Join and collaborate
nanobot agent --room market-research
```

**Conversation flow:**
```
[#market-research] You: Research the latest AI trends

leader: I'll coordinate with the team. @researcher, 
please gather the latest research. @social, check 
what people are talking about.

[#market-research] You: /explain

Work Log
Room: #market-research (project)
Participants: leader, researcher, social

Step 1: User requests research task
Step 2: Classified as low tier (simple delegation)
Step 3: Invoked @researcher for deep analysis
Step 4: Invoked @social for community sentiment
Step 5: Coordinated results
```

---

### Example 3: Direct Message to Bot

```bash
# Create a direct room for 1-on-1 with researcher
nanobot room create dm-researcher --bots leader,researcher

# Join the room
nanobot agent --room dm-researcher

[#dm-researcher] You: Tell me about your research methodology
```

**What you'll see:**
```
💬 #dm-researcher (direct) • 2 bots • 🟢 Active
Participants: leader, researcher
```

---

## Complete Command Reference

### Agent Command
```bash
nanobot agent [OPTIONS]

Options:
  --room, -r TEXT              Room to join (general, project-alpha, etc.)
  --session, -s TEXT           Session ID (default: cli:default)
  --message, -m TEXT           Single message mode
  --markdown/--no-markdown     Render as markdown (default: on)
  --logs/--no-logs            Show runtime logs (default: off)
```

### Room Management
```bash
# View all rooms
nanobot room list

# Create a new room
nanobot room create <name> [--bots bot1,bot2]

# Invite a bot
nanobot room invite <room_id> <bot_name>

# Remove a bot
nanobot room remove <room_id> <bot_name>

# Show room details
nanobot room show <room_id>
```

### In-Session Commands
```
/room          Show current room details
/explain       Show detailed work log for last interaction
/logs          Show work log summary
/how <topic>   Search work log for specific topic
exit           Leave the room and exit
```

---

## Work Log Integration

### Work logs now track:

1. **Room ID** - Which room the conversation happened in
2. **Room Type** - OPEN, PROJECT, DIRECT, or COORDINATION
3. **Participants** - List of bots in the room
4. **Bot Interactions** - When bots are invoked/coordinated
5. **Multi-agent decisions** - How coordinator bot delegated tasks

### Viewing Room-Specific Logs

```bash
# See all interactions in a project room
nanobot explain -w #website-redesign

# Focus on coordinator decisions
nanobot explain --mode coordination

# See bot-to-bot conversations
nanobot explain --mode conversations

# Filter by specific bot
nanobot explain -b @researcher -w #market-research
```

---

## Architecture

### Data Flow

```
User Input
    ↓
nanobot agent --room project-alpha
    ↓
RoomManager.get_room("project-alpha")
    ↓
Current Room Loaded
  - id: "project-alpha"
  - type: RoomType.PROJECT
  - participants: ["nanobot", "coder", "researcher"]
    ↓
TUI Header Displays
  - Room name, type, status
  - Participant list
  - Commands help
    ↓
Prompt Shows Room Indicator
  [#project-alpha] You: 
    ↓
AgentLoop.process_direct(
    message,
    room_id="project-alpha",
    room_type="project",
    participants=[...]
)
    ↓
Context.build_messages()
    ↓
System Prompt Includes Room Context
  "You are in room #project-alpha with bots: nanobot, coder, researcher"
    ↓
Work Log Captures Room Context
  - workspace_id: "project-alpha"
  - workspace_type: RoomType.PROJECT
  - participants: [...]
    ↓
Response Generated with Room Awareness
```

### Files Modified

| File | Changes |
|------|---------|
| `nanobot/cli/commands.py` | Added --room parameter, room header display, /room command, room-aware work log output |
| `nanobot/agent/loop.py` | Added room context fields, pass room to context builder, set room in work logs |
| `nanobot/agent/context.py` | Added room_id, room_type, participants to build_messages() |
| `nanobot/session/manager.py` | No changes (room not stored in session, loaded from RoomManager) |

---

## User Experience Improvements

### Before Integration
```
$ nanobot agent
🤖 nanobot v1.0 - Interactive mode

You: hello
nanobot: ...

You: /explain
# No room context shown
# Hard to understand which context you're in
```

### After Integration
```
$ nanobot agent --room project-alpha

🤖 nanobot v1.0 - Interactive mode

Room Context
📁 #project-alpha (project) • 3 bots • 🟢 Active

Participants:
  leader, coder, creative

Commands:
  /room, /explain, /logs, /how, exit

[#project-alpha] You: hello
nanobot: I can help! With coder and creative here, 
we can tackle this together.

You: /explain
# Shows room context in work log
# Clear visibility into room-based coordination
```

---

## Future Enhancements

1. **Room-Specific Memory** - Each room could have its own shared memory/artifacts
2. **Room Switching** - `/switch #other-room` to move between rooms in one session
3. **Room Archival** - Auto-archive inactive project rooms
4. **Room Permissions** - Control which bots can access which rooms
5. **Room Notifications** - Alert when room participants change
6. **Room History** - View previous conversations in a room

---

## Testing Checklist

- [ ] Start agent with default room
- [ ] Start agent with custom room (existing)
- [ ] Start agent with non-existent room (falls back to general)
- [ ] View room header with all fields populated
- [ ] Use /room command to show details
- [ ] Verify prompt shows room indicator
- [ ] Invoke bots with @mentions in room context
- [ ] Check /explain shows room in work log
- [ ] Verify room context in system prompt
- [ ] Test /how command with room filter

---

## Summary

Room integration in the CLI agent provides:

✅ Visual room context in TUI header
✅ Room indicator in prompt
✅ /room command for room info
✅ Room-aware work logs with context
✅ System prompt understands room collaboration
✅ Multi-bot coordination awareness
✅ Work log filtering by room
✅ Backwards compatible (default room if not specified)

Users can now see exactly which room they're in, who's available, and how the bots are coordinating - all directly from the terminal.
