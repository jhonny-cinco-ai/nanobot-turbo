# Room Integration Changelog

## Summary

Complete room context integration into the CLI agent experience. Users can now:
- See which room they're in
- View room participants and type
- Understand multi-bot collaboration
- Access room-specific work logs
- Use room context in the system prompt

---

## Changes by Component

### CLI Commands (`nanobot/cli/commands.py`)

#### Added Features

1. **Room Selection Parameter**
   ```python
   @app.command()
   def agent(
       message: str = typer.Option(None, "--message", "-m"),
       session_id: str = typer.Option("cli:default", "--session", "-s"),
       room: str = typer.Option("general", "--room", "-r"),  # NEW
       markdown: bool = typer.Option(True, "--markdown/--no-markdown"),
       logs: bool = typer.Option(False, "--logs/--no-logs"),
   ):
   ```
   
   - Users can specify `--room <name>` when starting agent
   - Falls back to "general" if room doesn't exist
   - Loads room from RoomManager

2. **Enhanced TUI Header**
   - Room name with emoji icon (🌐, 📁, 💬, 🤖)
   - Room type indicator (open, project, direct, coordination)
   - Activity status (🟢 Active, 🟡 Recent, 🔵 Idle)
   - Bot count
   - Participant list
   - Command help section

3. **/room Command**
   ```
   /room  # Shows room details
   ```
   - Display current room information
   - List participants
   - Show room type and metadata
   - Suggest management commands

4. **Room-Aware Prompt**
   ```python
   async def _read_interactive_input_async(room_id: str = "general"):
       # Prompt now shows: [#project-alpha] You:
   ```

5. **Room Status Formatter**
   ```python
   def _format_room_status(room) -> str:
       # Returns formatted room status with emoji, type, bots, activity
   ```

6. **Work Log Room Context**
   - Added room panel in explain output
   - Shows: Session, Room, Participants, Duration
   - Enhanced readability of room-based interactions

#### Modified Methods

- `agent()` - Loads and passes room context
- `_read_interactive_input_async()` - Accepts room_id parameter
- `explain_last_decision()` - Enhanced output with room context
- Interactive loop - Added /room command handler

---

### Agent Loop (`nanobot/agent/loop.py`)

#### Added Fields

```python
# Room context for multi-agent collaboration
self._current_room_id: str = "default"
self._current_room_type: str = "open"
self._current_room_participants: list[str] = ["leader"]
```

#### Modified Methods

1. **process_direct()**
   ```python
   async def process_direct(
       self,
       content: str,
       session_key: str = "cli:direct",
       channel: str = "cli",
       chat_id: str = "direct",
       room_id: str = "default",           # NEW
       room_type: str = "open",            # NEW
       participants: list | None = None,   # NEW
   ) -> str:
   ```
   
   - Sets room context for the session
   - Passes room context to work log manager
   - Makes room available to system prompt

2. **_process_message()**
   - Passes room context to `build_messages()`
   - Room info included in system prompt

#### Imports Added

```python
from nanobot.agent.work_log import RoomType
```

---

### Context Builder (`nanobot/agent/context.py`)

#### Modified Methods

1. **build_messages()**
   ```python
   def build_messages(
       self,
       history: list[dict[str, Any]],
       current_message: str,
       skill_names: list[str] | None = None,
       bot_name: Optional[str] = None,
       media: list[str] | None = None,
       channel: str | None = None,
       chat_id: str | None = None,
       memory_context: str | None = None,
       room_id: str | None = None,         # NEW
       room_type: str | None = None,       # NEW
       participants: list[str] | None = None,  # NEW
   ) -> list[dict[str, Any]]:
   ```

#### Room Context in System Prompt

Added to system prompt when room is not "default":

```python
## Room Context
Room: #project-alpha
Type: project
Participants: leader, coder, researcher

You are collaborating in this room with other bots. 
Use @botname to mention specific bots when you need their expertise.
```

---

## Usage Guide

### Starting in a Room

```bash
# Default general room
nanobot agent

# Specific room
nanobot agent --room project-alpha

# Single message in room
nanobot agent --room project-alpha --message "hello team"
```

### In Interactive Mode

```
[#project-alpha] You: hello

# Commands
/room     # Show room info
/explain  # Show work log with room context
/logs     # Summary
/how xyz  # Search logs
exit      # Leave room
```

### Work Log Filtering

```bash
# All logs for a room
nanobot explain -w #project-alpha

# Room-specific bot actions
nanobot explain -b @coder -w #project-alpha

# Coordination decisions in a room
nanobot explain --mode coordination -w #project-alpha
```

---

## Testing Scenarios

### Test 1: Default Room
```bash
$ nanobot agent
# Should load "general" room
# Header shows: 🌐 #general (open) • 1 bot • Status
# Prompt shows: [#general] You:
```

### Test 2: Existing Project Room
```bash
$ nanobot room create website-redesign --bots nanobot,coder
$ nanobot agent --room website-redesign
# Header shows: 📁 #website-redesign (project) • 2 bots
# Prompt shows: [#website-redesign] You:
```

### Test 3: Room Command
```bash
[#general] You: /room
# Output shows room details, type, participants
```

### Test 4: Multi-Bot Coordination
```bash
$ nanobot agent --room website-redesign
[#website-redesign] You: Design the homepage
# Agent response includes room context
# Can use @coder, @creative mentions
```

### Test 5: Work Log Room Context
```bash
[#website-redesign] You: Design the homepage
[#website-redesign] You: /explain
# Shows: Room: #website-redesign (project)
#        Participants: nanobot, coder, creative
```

### Test 6: Room Not Found
```bash
$ nanobot agent --room nonexistent
# Output: Room 'nonexistent' not found. Using 'general' room.
# Falls back to default room gracefully
```

### Test 7: Work Log Filtering
```bash
$ nanobot explain -w #website-redesign
# Shows only logs from that room
# Displays room context in header
```

---

## Data Flow Diagram

```
User: nanobot agent --room project-alpha
          │
          ▼
    ┌──────────────────┐
    │ RoomManager      │
    │ .get_room()      │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ Room Loaded                  │
    │ id: "project-alpha"          │
    │ type: RoomType.PROJECT       │
    │ participants: [...]          │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ TUI Header Rendered          │
    │ • Room name + emoji          │
    │ • Type indicator             │
    │ • Bot count                  │
    │ • Activity status            │
    └──────────┬───────────────────┘
               │
               ▼
    ┌──────────────────────────────┐
    │ Prompt Generated             │
    │ [#project-alpha] You:        │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ AgentLoop.process_direct()   │
    │ Sets room context            │
    │ Calls work_log_manager       │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ ContextBuilder.build_messages()
    │ • Includes room in system    │
    │   prompt                     │
    │ • Agent understands context  │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ LLM Call with Room Context   │
    │ System: "You're in room...   │
    │ with bots: ..."              │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ Response Generated           │
    │ (Room-aware response)        │
    └────────┬─────────────────────┘
             │
             ▼
    ┌──────────────────────────────┐
    │ Work Log Captured            │
    │ workspace_id: "project-alpha"│
    │ workspace_type: PROJECT      │
    │ participants: [...]          │
    └──────────────────────────────┘
```

---

## Backwards Compatibility

✅ **Fully backwards compatible**

- `--room` parameter is optional (defaults to "general")
- Existing sessions continue to work
- Old commands work unchanged
- Room context is additive, not breaking

---

## Performance Impact

- **Minimal**: Room loading is one-time at startup
- **No overhead**: Room context is already tracked in work logs
- **Efficient**: TUI rendering uses cached room data

---

## Future Enhancements

1. **Room History**
   ```bash
   /history    # Show recent messages in room
   /archive    # Archive and compress old rooms
   ```

2. **Room Switching**
   ```bash
   /switch #other-room    # Move to different room
   ```

3. **Room Artifacts**
   - Shared documents in room
   - Room-specific memory
   - Team notes

4. **Room Permissions**
   - Control bot access to rooms
   - Read-only rooms
   - Admin-only rooms

5. **Room Notifications**
   - Alert when bots join/leave
   - Participant change notifications
   - Important events

---

## Files Changed

| File | Lines | Changes |
|------|-------|---------|
| `nanobot/cli/commands.py` | ~100 | Room parameter, header display, /room command, work log enhancement |
| `nanobot/agent/loop.py` | ~20 | Room context fields, pass to context builder, work log integration |
| `nanobot/agent/context.py` | ~10 | Room parameters, system prompt addition |
| `docs/room_integration_cli.md` | NEW | Complete user guide |
| `docs/room_integration_changelog.md` | NEW | This file |

---

## Commit Summary

```
feat: Full room context integration in CLI agent

- Add --room parameter to agent command
- Display room context in TUI header with activity indicators
- Show room indicator in prompt [#room-id]
- Add /room command to display room details
- Integrate room context into system prompt
- Add room-aware work log display
- Track room participants in work logs
- Fall back gracefully if room not found
- Add comprehensive documentation

BREAKING CHANGE: None (fully backwards compatible)
```

---

## Verification Checklist

Before shipping, verify:

- [ ] Room parameter parsing works
- [ ] Room loading from RoomManager works
- [ ] Graceful fallback for missing rooms
- [ ] TUI header renders correctly with all fields
- [ ] Room indicator shows in prompt
- [ ] /room command displays all info
- [ ] Room context in system prompt
- [ ] Work logs capture room context
- [ ] /explain shows room in output
- [ ] All commands work in all room types
- [ ] No performance regression
- [ ] Backwards compatibility maintained
- [ ] Help text updated
- [ ] Documentation complete

---

## Summary

Room integration transforms the CLI agent from a single-context tool into a multi-context collaboration platform. Users can now:

✨ **See** which room they're in
✨ **Know** which bots are available
✨ **Understand** how decisions are made
✨ **Coordinate** across multiple team members
✨ **Track** conversations per room/project

All while maintaining a clean, intuitive CLI interface.
