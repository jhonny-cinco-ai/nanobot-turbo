# Room Interaction Questions - Answered

## Q1: Does "general" room automatically exist when user runs `nanobot agent`?

### Answer: YES ✅

**What Happens:**

1. **RoomManager initializes** when you first import it
   ```python
   room_manager = get_room_manager()
   ```

2. **Checks `~/.nanobot/rooms/` directory**
   - First time: Empty (no rooms exist yet)
   - Later: Loads existing room JSON files

3. **Automatically creates "general" room** if it doesn't exist
   ```python
   def _load_or_create_default(self) -> None:
       if self.DEFAULT_ROOM_ID not in self._rooms:
           self._create_default_room()
   ```

4. **Saved to disk permanently**
   ```json
   // ~/.nanobot/rooms/general.json
   {
     "id": "general",
     "type": "open",
     "participants": ["leader"],
     "owner": "user",
     "created_at": "2026-02-15T10:30:00",
     "auto_archive": false,
     "coordinator_mode": false
   }
   ```

5. **User sees it on first run**
   ```
   $ nanobot agent
   
   🌐 #general (open) • 1 bot • 🟢 Active
   Participants: leader
   
   [#general] You: 
   ```

**Key Facts:**
- ✅ Auto-created on first run
- ✅ Persistent (saved to disk)
- ✅ Always available as fallback
- ✅ Default when no `--room` specified
- ✅ Guaranteed to exist in every installation

---

## Q2: How does the user interact with the general room?

### Answer: Naturally - it's the default experience

**Basic Interaction:**

```bash
$ nanobot agent

# User sees room context automatically
🌐 #general (open) • 1 bot • 🟢 Active
Participants: leader

# User can talk to leader
[#general] You: hello

leader: Hello! How can I help?

# User can check room details
[#general] You: /room

📁 Room: #general
   Type: open
   Participants (1):
   • nanobot

# User can see work logs
[#general] You: /explain

Work Log
Session: cli:default
Room: #general (open)
Participants: leader
```

**What the User Knows:**
- They're in the "general" room
- Only nanobot is available
- They can check room details with `/room`
- Work logs show room context
- They can invite bots to expand the team

**User Capabilities in General Room:**

| Action | Command | Works? |
|--------|---------|--------|
| Chat with nanobot | Type message | ✅ Yes |
| Ask questions | Type message | ✅ Yes |
| See room info | `/room` | ✅ Yes |
| View work logs | `/explain` | ✅ Yes |
| Search logs | `/how <topic>` | ✅ Yes |
| Create new rooms | `nanobot room create` | ✅ Yes (external) |
| Invite bots | `nanobot room invite` | ✅ Yes (external) |
| Join another room | `nanobot agent --room X` | ✅ Yes (restart) |

---

## Q3: Can user add/create new rooms directly in the CLI without using `nanobot room` commands?

### Answer: Currently NO, but it should be YES

### Current Workflow (Awkward)

```bash
# User in CLI agent
[#general] You: I want to work on a project

nanobot: Great! Let me help.

# User has to exit agent to create room
[#general] You: exit
$ nanobot room create my-project --bots nanobot,coder,creative
$ nanobot agent --room my-project

[#my-project] You: Now we can work together
```

**Problems:**
- ❌ Have to exit the CLI
- ❌ Two separate commands
- ❌ Breaks conversation flow
- ❌ Clunky experience

### Proposed Workflow (What It Should Be)

```bash
# User in CLI agent - everything happens inline
[#general] You: /create my-project

✅ Created room #my-project (project)
   Use: /invite <bot> to add bots
   Use: /switch my-project to join

[#general] You: /invite coder

✅ Invited coder to #my-project
   Participants: nanobot, coder

[#general] You: /invite creative

✅ Invited creative to #my-project
   Participants: nanobot, coder, creative

[#general] You: /switch my-project

🔀 Switched to room #my-project

📁 #my-project (project) • 3 bots • 🟢 Active
Participants: nanobot, coder, creative

[#my-project] You: Let's build something amazing!
```

**Benefits:**
- ✅ No need to exit CLI
- ✅ Single conversation flow
- ✅ Fast room setup
- ✅ Intuitive commands
- ✅ Professional experience

---

## Q4: What are the exact commands needed for in-session room management?

### Answer: Four simple commands needed

#### Command 1: `/create <name> [type]`

**Syntax:**
```bash
/create my-project              # Creates project room
/create discussion general      # Creates general discussion
/create research research       # Creates research room
```

**Room Types Available:**
- `general` - Open discussion
- `project` - Focused team work
- `direct` - 1-on-1 conversation
- `coordination` - Autonomous bot coordination

**What It Does:**
1. Creates new Room object
2. Saves to `~/.nanobot/rooms/<name>.json`
3. Initializes with ["nanobot"] as participants
4. Shows confirmation
5. User stays in current room (doesn't auto-switch)

**Example:**
```
[#general] You: /create website-redesign

✅ Created room #website-redesign (project)
   Participants: nanobot
   
   Use: /invite <bot> to add team members
   Use: /switch website-redesign to join
   
[#general] You: 
```

---

#### Command 2: `/invite <bot_name>`

**Syntax:**
```bash
/invite coder
/invite researcher
/invite creative
/invite auditor
/invite social
```

**What It Does:**
1. Validates bot name
2. Adds bot to CURRENT room
3. Saves updated room to disk
4. Shows confirmation with new participant list

**Example:**
```
[#website-redesign] You: /invite coder

✅ Invited coder to #website-redesign
   Participants: nanobot, coder

[#website-redesign] You: /invite creative

✅ Invited creative to #website-redesign
   Participants: nanobot, coder, creative

[#website-redesign] You: 
```

**Important:**
- Adds to CURRENT room (not any room)
- User stays in same room
- Bots are now available for coordination

---

#### Command 3: `/switch <room_id>`

**Syntax:**
```bash
/switch website-redesign
/switch general
/switch dm-researcher
```

**What It Does:**
1. Validates room exists
2. Changes current room context
3. Reloads room header with new participants
4. Updates prompt to show new room
5. Subsequent messages go to new room

**Example:**
```
[#general] You: /switch website-redesign

🔀 Switching to #website-redesign...

📁 #website-redesign (project) • 3 bots • 🟢 Active
Participants: nanobot, coder, creative

[#website-redesign] You: 
```

**Important:**
- Doesn't save any history
- Each room is separate context
- Work logs show room change
- System prompt updated with new room context

---

#### Command 4: `/list-rooms`

**Syntax:**
```bash
/list-rooms
```

**What It Does:**
1. Lists all rooms in `~/.nanobot/rooms/`
2. Shows room type with emoji
3. Shows participant count
4. Shows activity status
5. Helps user discover available rooms

**Example:**
```
[#general] You: /list-rooms

🌐 #general              (open)      1 bot
📁 #website-redesign     (project)   3 bots  🟢 Active
📁 #market-research      (project)   2 bots  🔵 Idle
💬 #dm-researcher        (direct)    2 bots

Use /switch <room> to join a room

[#general] You: 
```

---

## Q5: Where would these commands be implemented?

### Answer: In the interactive loop in `commands.py`

**File Location:**
```
nanobot/cli/commands.py
Lines: 906-988 (interactive loop)
```

**Current Structure:**

```python
async def run_interactive():
    while True:
        user_input = await _read_interactive_input_async(room)
        command = user_input.strip().lower()
        
        # Existing commands
        if command == "/explain":
            # ... show work log
            
        if command == "/logs":
            # ... show summary
            
        if command == "/room":
            # ... show room details
        
        # ADD NEW COMMANDS HERE
        if command.startswith("/create "):
            # ... create room
        
        if command.startswith("/invite "):
            # ... invite bot
        
        if command.startswith("/switch "):
            # ... switch room
        
        if command == "/list-rooms":
            # ... list all rooms
        
        # Process message to agent
        with _thinking_ctx():
            response = await agent_loop.process_direct(
                user_input, 
                session_id,
                room_id=room
            )
```

**Implementation Code:**

```python
# Command 1: /create
if command.startswith("/create "):
    parts = command[8:].split()
    room_name = parts[0] if parts else None
    room_type = parts[1] if len(parts) > 1 else "project"
    
    if not room_name:
        console.print("[yellow]Usage: /create <name> [type][/yellow]")
        continue
    
    room_manager = get_room_manager()
    try:
        new_room = room_manager.create_room(
            name=room_name,
            room_type=RoomType(room_type),
            participants=["leader"]
        )
        console.print(f"\n✅ Created room #{new_room.id} ({room_type})")
        console.print(f"   Use: /invite <bot> to add team members")
        console.print(f"   Use: /switch {new_room.id} to join\n")
    except ValueError as e:
        console.print(f"\n[red]❌ {e}[/red]\n")
    continue

# Command 2: /invite
if command.startswith("/invite "):
    bot_name = command[8:].strip().lower()
    
    if not bot_name:
        console.print("[yellow]Usage: /invite <bot>[/yellow]")
        continue
    
    room_manager = get_room_manager()
    if room_manager.invite_bot(room, bot_name):
        updated_room = room_manager.get_room(room)
        console.print(f"\n✅ Invited {bot_name} to #{room}")
        console.print(f"   Participants: {', '.join(updated_room.participants)}\n")
        current_room = updated_room
    else:
        console.print(f"\n[yellow]⚠ Could not invite {bot_name}[/yellow]\n")
    continue

# Command 3: /switch
if command.startswith("/switch "):
    new_room_id = command[8:].strip().lower()
    
    if not new_room_id:
        console.print("[yellow]Usage: /switch <room>[/yellow]")
        continue
    
    room_manager = get_room_manager()
    new_room = room_manager.get_room(new_room_id)
    
    if not new_room:
        console.print(f"\n[red]❌ Room '{new_room_id}' not found[/red]\n")
        continue
    
    # Switch context
    room = new_room_id
    current_room = new_room
    
    console.print(f"\n🔀 Switched to room #{new_room_id}\n")
    console.print(_format_room_status(current_room))
    console.print(f"\n[dim]Participants:[/dim] {', '.join(current_room.participants)}\n")
    continue

# Command 4: /list-rooms
if command == "/list-rooms":
    room_manager = get_room_manager()
    rooms = room_manager.list_rooms()
    
    console.print()
    for room_info in rooms:
        icon = _get_room_icon(room_info['type'])
        type_label = room_info['type'].ljust(12)
        bot_count = f"{room_info['participant_count']} bot{'s' if room_info['participant_count'] != 1 else ''}"
        default = "⭐" if room_info['is_default'] else ""
        
        console.print(f"  {icon} #{room_info['id']:25} {type_label} {bot_count:12} {default}")
    
    console.print(f"\n[dim]Use /switch <room> to join a room[/dim]\n")
    continue
```

**Helper Function:**

```python
def _get_room_icon(room_type: str) -> str:
    """Get emoji icon for room type."""
    icons = {
        "open": "🌐",
        "project": "📁",
        "direct": "💬",
        "coordination": "🤖"
    }
    return icons.get(room_type, "📌")
```

---

## Q6: Complete User Experience Example

### Answer: Full workflow demonstration

```bash
$ nanobot agent

🤖 nanobot v1.0

Room Context
🌐 #general (open) • 1 bot • 🟢 Active

Participants:
  nanobot

Commands:
  /create         Create new room
  /invite         Add bot to room
  /switch         Change rooms
  /list-rooms     Show all rooms
  /room           Show room details
  /explain        Show work log
  /logs, /how     Search logs
  exit            Leave

[#general] You: I'm working on a website redesign project

nanobot: That's exciting! I can help you organize that.
         Would you like me to create a dedicated room for it?

[#general] You: Yes, please create a room called website-redesign

nanobot: Great! Let me set that up for you.

[#general] You: /create website-redesign

✅ Created room #website-redesign (project)
   Use: /invite <bot> to add team members
   Use: /switch website-redesign to join

[#general] You: Now invite the coder and creative bots

[#general] You: /invite coder

✅ Invited coder to #website-redesign
   Participants: nanobot, coder

[#general] You: /invite creative

✅ Invited creative to #website-redesign
   Participants: nanobot, coder, creative

[#general] You: Let's switch to that room

[#general] You: /switch website-redesign

🔀 Switched to room #website-redesign

📁 #website-redesign (project) • 3 bots • 🟢 Active

Participants:
  nanobot
  coder
  creative

[#website-redesign] You: Alright team, we need to design a homepage

leader: Perfect! With @coder and @creative here, we can tackle
         this comprehensively.

Here's my proposed plan:

1. **Technical Architecture** (@coder)
   - Responsive grid system
   - Performance optimization
   - SEO best practices

2. **Visual Design** (@creative)
   - Color palette
   - Typography hierarchy
   - Layout composition

3. **Coordination** (me)
   - Make sure everything works together
   - User experience continuity
   - Integration points

Shall we start with the wireframes?

[#website-redesign] You: Let's start with the technical architecture

leader: Great! Let me coordinate with @coder on the foundation.

[#website-redesign] You: /list-rooms

🌐 #general              (open)       1 bot (leader)
📁 #website-redesign     (project)    3 bots  🟢 Active
📁 #market-research      (project)    2 bots  🔵 Idle

Use /switch <room> to join a room

[#website-redesign] You: /explain

Work Log
┌─────────────────────────────────────────────┐
│ Session: cli:default                        │
│ Room: #website-redesign (project)          │
│ Participants: leader, coder, creative      │
│ Duration: 3.25s                            │
└─────────────────────────────────────────────┘

Step 1: User discusses project
Step 2: User creates room with /create
Step 3: User invites bots with /invite
Step 4: User switches to new room with /switch
Step 5: Agent coordinates across team
Step 6: Work log captures room context

[#website-redesign] You: Perfect! This is exactly what I needed
```

---

## Summary

| Question | Answer | Status |
|----------|--------|--------|
| Auto general room? | YES - created on first run | ✅ Complete |
| User interaction? | Automatic - it's the default | ✅ Complete |
| Create in CLI? | NO - but designed and ready | ⏳ Ready to build |
| What commands? | /create, /invite, /switch, /list-rooms | ✅ Designed |
| Where implement? | Interactive loop in commands.py | ✅ Designed |
| Full UX possible? | YES - all ready to go | ✅ Ready |

---

## Next Steps to Enable In-Session Rooms

1. **Add 4 command handlers** to interactive loop
2. **Add helper function** `_get_room_icon()`
3. **Update help text** with new commands
4. **Test all workflows**
5. **Document in CLI help**

**Estimated effort:** 2-3 hours of development

Everything is designed and documented - just needs implementation!
