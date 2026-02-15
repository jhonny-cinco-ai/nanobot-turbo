# Room Interaction & Workflow in CLI Agent

## Overview

This guide explains how rooms work when users interact with `nanobot agent`, including room initialization, switching, and creation directly from the CLI.

---

## Part 1: Default Room Initialization

### What Happens When User Runs `nanobot agent`

```bash
$ nanobot agent
```

#### Step-by-Step Flow

1. **RoomManager Initializes** (happens once per session)
   ```python
   room_manager = get_room_manager()
   ```
   
   The RoomManager:
   - Checks `~/.nanobot/rooms/` directory
   - Loads any existing room JSON files
   - **Automatically creates "general" room if it doesn't exist**

2. **Default Room Created** (first time only)
   ```json
   {
     "id": "general",
     "type": "open",
     "participants": ["nanobot"],
     "owner": "user",
     "created_at": "2026-02-15T10:30:00",
     "summary": "",
     "auto_archive": false,
     "coordinator_mode": false
   }
   ```
   Saved to: `~/.nanobot/rooms/general.json`

3. **Room Loaded in Agent Command**
   ```python
   current_room = room_manager.get_room("general")  # "general" is default
   ```

4. **User Sees Room Context**
   ```
   🌐 #general (open) • 1 bot • 🟢 Active
   Participants: leader
   
   [#general] You: 
   ```

### Important: General Room Always Exists

- **First Run**: Created automatically with just leader
- **Subsequent Runs**: Loaded from disk (`~/.nanobot/rooms/general.json`)
- **Guaranteed**: Always available as fallback
- **Default**: Used when no `--room` parameter specified

---

## Part 2: Existing Room Interaction

### Joining an Existing Room

```bash
$ nanobot agent --room project-alpha
```

#### What Happens

1. **RoomManager Loads Room**
   ```python
   current_room = room_manager.get_room("project-alpha")
   ```

2. **Room File Loaded**
   From: `~/.nanobot/rooms/project-alpha.json`
   ```json
   {
     "id": "project-alpha",
     "type": "project",
     "participants": ["nanobot", "coder", "researcher"],
     "owner": "user",
     "created_at": "2026-02-15T12:00:00"
   }
   ```

3. **Room Context Displayed**
   ```
   📁 #project-alpha (project) • 3 bots • 🟢 Active
   Participants: leader, coder, researcher
   ```

4. **Agent Understands Team**
   System prompt includes:
   ```
   Room: #project-alpha
   Type: project
   Participants: leader, coder, researcher
   You can coordinate with @coder and @researcher
   ```

### Room Not Found Behavior

```bash
$ nanobot agent --room nonexistent-room
```

**Output:**
```
Room 'nonexistent-room' not found. Using 'general' room.

🌐 #general (open) • 1 bot • 🟢 Active
Participants: leader

[#general] You: 
```

**Graceful Fallback:**
- ✅ No error
- ✅ Falls back to "general" automatically
- ✅ User can work normally
- ✅ To use desired room, create it first with `nanobot room create`

---

## Part 3: Creating Rooms Directly in CLI

### Current Workflow (Using Commands)

**Outside Agent:**
```bash
# Create a room
nanobot room create website-redesign --bots nanobot,coder,creative

# Then join it
nanobot agent --room website-redesign
```

### Proposed: In-Session Room Creation (New Feature)

Users should be able to create rooms directly in the CLI agent without exiting. Here's how to implement it:

#### Feature: `/create <room_name>` Command

```
[#general] You: /create website-redesign

nanobot: ✅ Created room #website-redesign (type: project)
         Add bots to the room? Use: /invite <room> <bot>
         Join it with: /switch website-redesign
```

#### Implementation

1. **Add `/create` Command Handler**
   ```python
   if command.startswith("/create "):
       room_name = command[8:].strip()
       room_manager = get_room_manager()
       try:
           # Create new project room
           new_room = room_manager.create_room(
               name=room_name,
               room_type=RoomType.PROJECT,
               participants=["nanobot"]
           )
           console.print(f"✅ Created room #{new_room.id}")
       except ValueError as e:
           console.print(f"❌ {e}")
   ```

2. **Add `/invite` Command Handler** (in-session)
   ```
   /invite <bot_name>
   
   Example: /invite coder
   → Invites @coder to current room
   ```

3. **Add `/switch` Command Handler** (change rooms in-session)
   ```
   /switch <room_id>
   
   Example: /switch website-redesign
   → Joins the website-redesign room
   → Prompt changes: [#website-redesign] You:
   → New participants shown in header
   ```

---

## Part 4: Proposed In-Session Room Management

Here's a complete design for managing rooms without exiting the CLI:

### New In-Session Commands

#### Command 1: `/create <name> [type]`
```bash
/create my-project                    # Creates project room
/create discussion general            # Creates general discussion room
/create research research             # Creates research room

# Room types: general, project, direct, coordination
```

**What it does:**
- Creates new room in `~/.nanobot/rooms/<name>.json`
- Initializes with ["nanobot"] as participants
- Shows confirmation
- User stays in current room (doesn't auto-switch)

**Example:**
```
[#general] You: /create website-redesign

✅ Room created: #website-redesign (project)

Available commands:
  /invite coder          Add bot to current room
  /switch website-redesign   Move to new room
  /room                  Show current room details

[#general] You: 
```

---

#### Command 2: `/invite <bot_name>` 
```bash
/invite coder           # Add to current room
/invite researcher
/invite creative

# Currently in #website-redesign, so they're added there
```

**What it does:**
- Adds bot to current room
- Updates `~/.nanobot/rooms/<current>.json`
- Shows who's now in the room
- Reloads prompt with new participants

**Example:**
```
[#website-redesign] You: /invite coder

✅ Invited coder to #website-redesign

Current participants (2):
  • nanobot
  • coder

[#website-redesign] You: 
```

---

#### Command 3: `/switch <room_id>`
```bash
/switch general           # Back to general
/switch website-redesign  # Move to project
/switch dm-researcher     # Direct message room
```

**What it does:**
- Changes current room
- Updates session context
- Reloads room header with new participants
- Updates prompt to show new room
- Room history not carried over (each room has own context)

**Example:**
```
[#general] You: /switch website-redesign

🔀 Switching rooms...

📁 #website-redesign (project) • 3 bots • 🟢 Active

Participants:
  nanobot
  coder
  creative

[#website-redesign] You: 
```

---

#### Command 4: `/list-rooms`
```bash
/list-rooms

🌐 #general (open) • 1 bot
📁 #website-redesign (project) • 3 bots • 🟢 Active
📁 #market-research (project) • 2 bots • 🔵 Idle
💬 #dm-researcher (direct) • 2 bots

Use /switch <room_id> to join a room
```

**What it does:**
- Lists all available rooms
- Shows activity status
- Shows participant count
- Helps users discover rooms

---

### Complete Workflow With In-Session Creation

```bash
$ nanobot agent

🌐 #general (open) • 1 bot • 🟢 Active
Participants: leader

Commands:
  /room         Show room details
  /create       Create new room
  /list-rooms   List all rooms
  /switch       Switch to another room
  /invite       Add bot to current room
  /explain, /logs, /how   Work log commands

[#general] You: I need to start a website project

nanobot: Great! Let me create a dedicated room for that.

[#general] You: /create website-redesign

✅ Room created: #website-redesign (project)

[#general] You: /invite coder

✅ Invited coder to #website-redesign

[#general] You: /invite creative

✅ Invited creative to #website-redesign

[#general] You: /switch website-redesign

🔀 Switching to #website-redesign...

📁 #website-redesign (project) • 3 bots • 🟢 Active
Participants: leader, coder, creative

[#website-redesign] You: Design the homepage

nanobot: Perfect! I'm coordinating with @coder and @creative
on the design. Let me break this down:

@coder - Handle the technical architecture
@creative - Create the visual design and UX

Here's my plan:
...

[#website-redesign] You: /explain

Work Log
Room: #website-redesign (project)
Participants: leader, coder, creative
Duration: 1.23s

Step 1: User requests design task
Step 2: User created room and invited team
Step 3: Agent understood team composition
Step 4: Agent coordinated task across team
```

---

## Part 5: Implementation Details

### Where to Add Command Handlers

**File:** `nanobot/cli/commands.py`

**Location:** Interactive loop (around line 960)

```python
# In the interactive loop, after /explain, /logs, /how commands

if command == "/create ":
    # Handle room creation
    
if command == "/invite ":
    # Handle bot invitation
    
if command == "/switch ":
    # Handle room switching
    
if command == "/list-rooms":
    # List all rooms
```

### Data Persistence

- **Created rooms**: Automatically saved to `~/.nanobot/rooms/<room_id>.json`
- **Participant changes**: Automatically saved via RoomManager
- **Room switching**: Doesn't save anything (just changes context)
- **No data loss**: All changes persisted immediately

### Session Handling

```python
# When switching rooms
self._current_room_id = new_room.id
self._current_room_type = new_room.type.value
self._current_room_participants = new_room.participants

# Next message uses new room context
# /explain shows the new room
```

### Work Log Tracking

```python
# Each command tracked in work log
work_log_manager.log(
    level=LogLevel.INFO,
    category="room_management",
    message=f"User created room: {room_name}",
    details={"room_id": room.id, "room_type": room.type.value}
)
```

---

## Part 6: User Experience Scenarios

### Scenario 1: Quick Project Setup

**Current:**
```bash
$ nanobot room create website --bots nanobot,coder
$ nanobot agent --room website
```

**With new feature:**
```bash
$ nanobot agent

[#general] You: /create website
[#general] You: /invite coder
[#general] You: /switch website

📁 #website (project) • 2 bots
[#website] You: Let's build the homepage
```

### Scenario 2: Multiple Projects In One Session

```bash
[#general] You: /create project-alpha
[#general] You: /create project-beta
[#general] You: /invite coder

[#general] You: /switch project-alpha
[#project-alpha] You: Start with the database schema
[#project-alpha] You: /switch project-beta
[#project-beta] You: Let's plan the UI

[#project-beta] You: /list-rooms
🌐 #general • 1 bot
📁 #project-alpha • 2 bots
📁 #project-beta • 2 bots

[#project-beta] You: /switch project-alpha
[#project-alpha] You: Check the schema progress
```

### Scenario 3: Direct Messages

```bash
[#general] You: /create dm-researcher direct

💬 #dm-researcher (direct) • 2 bots

[#general] You: /switch dm-researcher
[#dm-researcher] You: What's your research approach?

nanobot: I'm speaking directly with researcher now...
```

---

## Part 7: Room Persistence & History

### How Rooms Are Stored

**File Structure:**
```
~/.nanobot/
├── rooms/
│   ├── general.json              # Auto-created
│   ├── project-alpha.json        # User created
│   ├── website-redesign.json     # Created in CLI
│   └── dm-researcher.json        # Created in CLI
└── sessions/
    ├── cli_default.jsonl         # Session history
    └── cli_default_website.jsonl # Per-room history (optional)
```

### Room vs Session

| Aspect | Room | Session |
|--------|------|---------|
| **Storage** | `~/.nanobot/rooms/*.json` | `~/.nanobot/sessions/*.jsonl` |
| **Persistence** | Permanent (until deleted) | Per-session |
| **Participants** | All bots in room | N/A |
| **Context** | Shared among team | Per-session/channel |
| **Creation** | Explicit (CLI command) | Automatic (first message) |

---

## Part 8: Architecture Diagram

```
User: nanobot agent
  │
  ▼
RoomManager Initializes
  │
  ├─→ Load existing rooms from ~/.nanobot/rooms/
  │
  └─→ Create "general" room if missing
       │
       └─→ Save to general.json
           │
           ▼
User sees header:
🌐 #general (open) • 1 bot

[#general] You: /create website-redesign
  │
  ▼
CLI intercepts command
  │
  ├─→ RoomManager.create_room("website-redesign")
  │   │
  │   └─→ Create Room object
  │       │
  │       └─→ Save to website-redesign.json
  │
  └─→ User stays in #general
  
[#general] You: /invite coder
  │
  ▼
CLI intercepts command
  │
  ├─→ RoomManager.get_room("website-redesign")
  │   │
  │   └─→ Load from disk
  │
  ├─→ room.add_participant("coder")
  │
  └─→ RoomManager._save_room()
      │
      └─→ Update website-redesign.json

[#general] You: /switch website-redesign
  │
  ▼
CLI intercepts command
  │
  ├─→ self._current_room_id = "website-redesign"
  │
  ├─→ Reload header with new room
  │
  ├─→ Update prompt: [#website-redesign] You:
  │
  └─→ Pass room context to process_direct()
      │
      ▼
  AgentLoop uses new room context
  System prompt includes: Room: #website-redesign
                        Participants: leader, coder
```

---

## Part 9: Summary

### Current State (No In-Session Creation)

✅ General room auto-created
✅ Can join rooms with `--room` parameter
✅ Falls back gracefully to general
✅ Room context in system prompt
✅ Work logs track room context

❌ Can't create rooms without exiting CLI
❌ Can't switch rooms in-session
❌ Can't invite bots mid-conversation

### Proposed Enhancement (In-Session Creation)

✅ `/create <name>` - Create rooms without exiting
✅ `/invite <bot>` - Add bots mid-conversation
✅ `/switch <room>` - Change rooms in-session
✅ `/list-rooms` - Discover available rooms
✅ Full room persistence
✅ Seamless workflow

---

## Part 10: Implementation Roadmap

### Phase 1: Room Discovery (Current)
- ✅ Auto-create general room
- ✅ Load existing rooms
- ✅ Join with `--room` parameter
- ✅ Show room context

### Phase 2: In-Session Management (Proposed)
- [ ] `/create <name>` command
- [ ] `/invite <bot>` command
- [ ] `/switch <room>` command
- [ ] `/list-rooms` command
- [ ] Real-time room switching
- [ ] Work log per-room tracking

### Phase 3: Advanced Features (Future)
- [ ] `/archive <room>` - Archive old rooms
- [ ] `/remove <bot>` - Remove bot from room
- [ ] `/rename <old> <new>` - Rename room
- [ ] `/set-type <type>` - Change room type
- [ ] Room artifacts & shared memory
- [ ] Room permissions & access control

---

## Conclusion

The room system provides:

1. **Automatic Setup** - General room created and available immediately
2. **Flexible Joining** - Join any room with `--room` parameter
3. **Graceful Fallback** - Missing rooms → use general
4. **Rich Context** - Agent understands room and team
5. **Work Log Integration** - Track everything per room
6. **Proposed In-Session Mgmt** - Manage rooms without exiting CLI

Users can work naturally with rooms, starting with the automatic general room and expanding to team-based project rooms as needed.
