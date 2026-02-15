# Advanced CLI UX Design - Room Management & Team Dashboard

## Overview

We'll enhance the CLI agent with:
1. **AI-assisted room creation** - User asks, Leader creates & invites bots
2. **In-session commands** - `/create`, `/invite`, `/switch`, `/list-rooms`
3. **Advanced UI** - Top menu bar + right sidebar with team & rooms
4. **Rich integration** - Leverage Rich + prompt_toolkit for better layout

---

## Part 1: Available UI Tools

### Rich Library (Already Imported)
- ✅ `Console` - Advanced text rendering
- ✅ `Table` - Formatted data tables
- ✅ `Panel` - Boxed content
- ✅ `Text` - Styled text
- ✅ `Markdown` - Markdown rendering
- ✅ `Layout` - **Can create layouts!** (Not yet imported)
- ✅ `Columns` - **Side-by-side content!** (Not yet imported)

### prompt_toolkit (Already Imported)
- ✅ `PromptSession` - Interactive input
- ✅ `HTML` - Styled prompts
- ✅ `FileHistory` - Command history
- ✅ `patch_stdout` - Clean output handling

### Current Capabilities
- Rich colors & styles
- Panels with borders
- Tables for data
- HTML-formatted prompts
- Async input handling
- Spinner/status indicators

---

## Part 2: Proposed Advanced UI Layout

### Current Layout (Simple)
```
🤖 nanobot v1.0 - Interactive mode
Room Context: 🌐 #general (open) • 1 bot
Participants: nanobot
[#general] You: 
```

### Proposed Layout (Advanced)
```
┌─────────────────────────────────────────────────────────────────────┬──────────────┐
│ 🤖 Nanobot Interactive - #general                                   │ TEAM & ROOMS │
├─────────────────────────────────────────────────────────────────────┼──────────────┤
│                                                                       │              │
│ [Chat area - 70% width]                                             │ BOTS (8)     │
│                                                                       │ ┌──────────┐ │
│ nanobot: Hello! How can I help?                                    │ │🧠Research│ │
│                                                                       │ │💻Code    │ │
│ [#general] You: Create a room for my website                       │ │🎨Create  │ │
│                                                                       │ │🤝Social  │ │
│ nanobot: I'll set up a room for your website project!             │ │✅Auditor │ │
│ I'm inviting Marcus (creative), Laura (researcher),                │ │👑Leader  │ │
│ and Johnny (coder) to help. Is that good?                          │ │          │ │
│                                                                       │ │          │ │
│ You: Yes, perfect!                                                  │ └──────────┘ │
│                                                                       │              │
│                                                                       │ ROOMS (3)    │
│                                                                       │ ┌──────────┐ │
│                                                                       │ │general   │ │
│                                                                       │ │website↔  │ │
│ [#website-project] You:                                            │ │market-ra-│ │
│                                                                       │ └──────────┘ │
└─────────────────────────────────────────────────────────────────────┴──────────────┘

Legend:
- Left (70%): Main chat interface
- Right (30%): Team roster + Room list
- Top: Status bar with current room
- Bottom: Input prompt
```

---

## Part 3: Feature Implementation Plan

### Feature 1: AI-Assisted Room Creation

**User Request:**
```
[#general] You: Leader, can you create a new room for building a website for my company?

nanobot: I'll help you set up a dedicated room for your website project!
         
         🔍 Analyzing task requirements...
         
         Based on your request, I recommend:
         • Room: company-website (project type)
         • Bots needed:
           ✓ @creative (Design & UX) - Marcus
           ✓ @researcher (Market & Competition) - Laura
           ✓ @coder (Development) - Johnny
         
         Is this team composition good for you?
         
You: Yes, create it!

nanobot: ✅ Room created: #company-website
         ✅ Invited @creative (Marcus)
         ✅ Invited @researcher (Laura)
         ✅ Invited @coder (Johnny)
         
         🔀 Switching to #company-website...
         
         Ready to start building your website!

[#company-website] You: 
```

**Implementation:**

```python
# In AgentLoop._process_message() or as a special handler
# Detect room creation requests using prompt analysis

ROOM_CREATION_PROMPT = """
You are an expert at understanding project requirements.
If the user is asking to create a room or start a project, 
recommend which specialist bots would be helpful.

Return JSON:
{
  "should_create_room": true/false,
  "room_name": "company-website",
  "room_type": "project",
  "recommended_bots": [
    {"name": "researcher", "reason": "Market analysis"},
    {"name": "coder", "reason": "Development"},
    {"name": "creative", "reason": "Design"}
  ],
  "summary": "Your website needs..."
}
"""

async def _detect_room_creation_intent(user_message: str) -> dict:
    """Check if user is asking to create a room."""
    response = await self.provider.chat(
        messages=[
            {"role": "system", "content": ROOM_CREATION_PROMPT},
            {"role": "user", "content": user_message}
        ],
        model=self.model,
    )
    try:
        return json.loads(response.content)
    except:
        return {"should_create_room": False}

async def _handle_room_creation_intent(intent: dict, session: Session):
    """Create room and invite bots based on intent."""
    if not intent["should_create_room"]:
        return None
    
    room_manager = get_room_manager()
    
    # Show user what we're about to do
    console.print("\n🔍 Analyzing task requirements...\n")
    console.print(f"[dim]{intent['summary']}[/dim]\n")
    
    console.print("[bold]Recommended team:[/bold]")
    for bot in intent["recommended_bots"]:
        console.print(f"  ✓ @{bot['name']:12} ({bot['reason']})")
    
    # Ask for confirmation
    from rich.prompt import Confirm
    if not Confirm.ask("\nCreate this room and invite these bots?", default=True):
        return None
    
    # Create room
    new_room = room_manager.create_room(
        name=intent["room_name"],
        room_type=RoomType.PROJECT,
        participants=["nanobot"]
    )
    
    # Invite bots
    for bot in intent["recommended_bots"]:
        bot_name = bot["name"]
        room_manager.invite_bot(new_room.id, bot_name)
        console.print(f"✅ Invited @{bot_name}")
    
    console.print(f"\n🔀 Switching to #{new_room.id}...\n")
    return new_room
```

---

### Feature 2: In-Session Commands

#### Command: `/create <name> [type]`

```python
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
            participants=["nanobot"]
        )
        console.print(f"\n✅ Created room #{new_room.id} ({room_type})")
        console.print(f"   Use: /invite <bot> to add bots")
        console.print(f"   Use: /switch {new_room.id} to join\n")
    except ValueError as e:
        console.print(f"\n[red]❌ {e}[/red]\n")
    continue
```

#### Command: `/invite <bot_name>` or `/invite <bot_name> <reason>`

```python
if command.startswith("/invite "):
    parts = command[8:].split(maxsplit=1)
    bot_name = parts[0].lower() if parts else None
    reason = parts[1] if len(parts) > 1 else "Team member"
    
    if not bot_name:
        console.print("[yellow]Usage: /invite <bot> [reason][/yellow]")
        continue
    
    room_manager = get_room_manager()
    if room_manager.invite_bot(room, bot_name):
        updated_room = room_manager.get_room(room)
        console.print(f"\n✅ {bot_name} invited to #{room}")
        console.print(f"   Participants ({len(updated_room.participants)}): " + 
                     ", ".join(updated_room.participants) + "\n")
        current_room = updated_room
    else:
        console.print(f"\n[yellow]⚠ Could not invite {bot_name}[/yellow]\n")
    continue
```

#### Command: `/switch <room_id>`

```python
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
    
    console.print(f"\n🔀 Switched to #{new_room_id}\n")
    console.print(_format_room_status(current_room))
    console.print(f"\nParticipants: {', '.join(current_room.participants)}\n")
    continue
```

#### Command: `/list-rooms` or `/rooms`

```python
if command in ["/list-rooms", "/rooms"]:
    room_manager = get_room_manager()
    rooms = room_manager.list_rooms()
    
    table = Table(title="Available Rooms")
    table.add_column("Room", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Bots", style="green")
    table.add_column("Status", style="yellow")
    
    for room_info in rooms:
        status = "🟢 Active" if room_info['is_default'] else "🔵 Idle"
        table.add_row(
            f"#{room_info['id']}",
            room_info['type'],
            str(room_info['participant_count']),
            status
        )
    
    console.print(f"\n{table}\n")
    console.print("[dim]Use /switch <room> to join a room[/dim]\n")
    continue
```

---

## Part 4: Advanced UI Implementation

### Using Rich Layout & Columns

**New imports needed:**
```python
from rich.layout import Layout
from rich.columns import Columns
from rich.live import Live
from rich.console import Console
```

### Advanced Interface Version

**For simple implementation (doesn't require layout changes):**

```python
def _render_team_sidebar() -> str:
    """Render team roster sidebar."""
    from rich.console import Console as RichConsole
    from rich.table import Table
    
    console_temp = RichConsole()
    
    # Get all available bots
    all_bots = [
        ("🧠", "researcher", "Research"),
        ("💻", "coder", "Code"),
        ("🎨", "creative", "Design"),
        ("🤝", "social", "Community"),
        ("✅", "auditor", "Quality"),
        ("🔧", "tools", "Tools"),
        ("👑", "nanobot", "Leader"),
    ]
    
    output = "[bold cyan]TEAM[/bold cyan]\n"
    for emoji, name, role in all_bots:
        output += f"{emoji} {name:12} {role}\n"
    
    return output

def _render_rooms_sidebar() -> str:
    """Render rooms list sidebar."""
    room_manager = get_room_manager()
    rooms = room_manager.list_rooms()
    
    output = "\n[bold cyan]ROOMS[/bold cyan]\n"
    for room_info in rooms:
        icon = _get_room_icon(room_info['type'])
        marker = "→ " if room_info['is_default'] else "  "
        output += f"{marker}{icon} {room_info['id']:15} ({room_info['participant_count']})\n"
    
    return output

def _render_status_bar(current_room, current_room_participants) -> str:
    """Render top status bar."""
    return f"[dim]Room:[/dim] [bold]{current_room.id}[/bold] • [dim]Bots:[/dim] [green]{len(current_room_participants)}[/green]"
```

**Display with sidebars (simple):**

```python
# In interactive loop, before prompt
async def run_interactive():
    while True:
        try:
            # Clear and show sidebar info
            _flush_pending_tty_input()
            
            # Show status
            console.print(_render_status_bar(current_room, current_room.participants), end="")
            console.print(" " * 50)  # Padding
            console.print(_render_team_sidebar())
            console.print(_render_rooms_sidebar())
            
            # Get input
            user_input = await _read_interactive_input_async(room)
            command = user_input.strip()
            ...
```

### Advanced Layout Version (For Future)

```python
# For true side-by-side layout with Rich
def _create_advanced_layout(current_room):
    """Create advanced layout with sidebar."""
    from rich.layout import Layout
    from rich.panel import Panel
    
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(
            Layout(name="main", ratio=2),
            Layout(name="sidebar", ratio=1),
            direction="horizontal"
        ),
        Layout(name="footer", size=1)
    )
    
    # Header
    layout["header"].update(Panel(
        f"🤖 Nanobot - Room: #{current_room.id}",
        style="bold blue"
    ))
    
    # Main chat area
    layout["main"].update(Panel("Chat history here...", title="Chat"))
    
    # Sidebar with team & rooms
    sidebar_content = _render_team_sidebar() + _render_rooms_sidebar()
    layout["sidebar"].update(Panel(sidebar_content, title="Team & Rooms"))
    
    # Footer
    layout["footer"].update(Panel("[#general] You: ", style="dim"))
    
    return layout
```

---

## Part 5: Complete User Flow Example

```bash
$ nanobot agent

🤖 nanobot v1.0 - Interactive mode

TEAM
🧠 researcher   Research
💻 coder        Code
🎨 creative     Design
🤝 social       Community
✅ auditor      Quality
👑 nanobot      Leader

ROOMS
→ 🌐 general           (1)
  
Room: general • Bots: 1

[#general] You: Leader, can you create a room for my website project?

nanobot: I'll help you set up a dedicated room for your website!

         🔍 Analyzing task requirements...
         
         For building a website, I recommend:
         • @creative (Design & UX)
         • @coder (Development)
         • @researcher (Market research)
         
         Create this room and invite these bots?

[y/N]: y

         ✅ Invited @creative
         ✅ Invited @coder
         ✅ Invited @researcher
         
         🔀 Switching to #website-project...

TEAM
🧠 researcher   Research      ✓ In room
💻 coder        Code           ✓ In room
🎨 creative     Design         ✓ In room
🤝 social       Community
✅ auditor      Quality
👑 nanobot      Leader         ✓ In room

ROOMS
  🌐 general           (1)
→ 📁 website-project   (4)

Room: website-project • Bots: 4

[#website-project] You: Let's start with the design

nanobot: Perfect! I'm coordinating with @creative on the visual
         design while @coder works on the architecture...

[#website-project] You: /list-rooms

┌────────────────┬──────┬──────┬────────┐
│ Room           │ Type │ Bots │ Status │
├────────────────┼──────┼──────┼────────┤
│ #general       │ open │  1   │ 🔵 Idle│
│ #website-proj  │ proj │  4   │ 🟢 Act │
└────────────────┴──────┴──────┴────────┘

[#website-project] You: /switch general

🔀 Switched to #general

Room: general • Bots: 1

[#general] You: Check status

nanobot: Your website project is progressing well in the
         #website-project room. Want to check on it?

[#general] You: /switch website-project

🔀 Switched to #website-project

[#website-project] You: 
```

---

## Part 6: Implementation Order

### Phase 1: Core In-Session Commands (2-3 hours)
- [ ] `/create <name> [type]` command
- [ ] `/invite <bot> [reason]` command
- [ ] `/switch <room>` command
- [ ] `/list-rooms` command
- [ ] Help text updates

### Phase 2: AI-Assisted Creation (4-5 hours)
- [ ] Detect room creation intent from user message
- [ ] LLM suggests room name, type, and bots
- [ ] Get user confirmation
- [ ] Auto-create and invite
- [ ] Switch to new room

### Phase 3: Enhanced UI (2-3 hours)
- [ ] Show team roster in sidebar
- [ ] Show room list in sidebar
- [ ] Status bar with current room
- [ ] Visual indicators for bots in current room
- [ ] Highlight current room in list

### Phase 4: Advanced Layout (4-5 hours) - Optional
- [ ] Use Rich Layout for true side-by-side
- [ ] Live updates to sidebar
- [ ] Smooth transitions
- [ ] History scrolling in chat area

---

## Part 7: Code Architecture

### New Files/Classes Needed

```python
# nanobot/cli/room_ui.py - New file for UI components

class TeamRoster:
    """Manages team display."""
    def __init__(self):
        self.bots = [
            ("🧠", "researcher", "Research"),
            ("💻", "coder", "Code"),
            ("🎨", "creative", "Design"),
            ("🤝", "social", "Community"),
            ("✅", "auditor", "Quality"),
            ("👑", "nanobot", "Leader"),
        ]
    
    def render(self, current_room) -> str:
        """Render team roster with room indicators."""
        pass
    
    def render_compact(self) -> str:
        """Render compact team list."""
        pass

class RoomList:
    """Manages room list display."""
    def render(self, current_room_id) -> str:
        """Render rooms with current room highlighted."""
        pass

class StatusBar:
    """Top status bar."""
    def render(self, current_room, participants_count) -> str:
        """Render current room status."""
        pass
```

### Existing Files to Modify

```python
# nanobot/cli/commands.py

# Add imports
from rich.layout import Layout  # Optional for advanced UI
from nanobot.cli.room_ui import TeamRoster, RoomList, StatusBar

# Add command handlers in interactive loop
if command.startswith("/create "):
    # Implementation
    
if command.startswith("/invite "):
    # Implementation
    
if command.startswith("/switch "):
    # Implementation
    
if command in ["/list-rooms", "/rooms"]:
    # Implementation

# Add AI-assisted room creation
async def _detect_room_creation_intent(user_message: str):
    # Implementation

async def _handle_room_creation_intent(intent: dict):
    # Implementation
```

---

## Part 8: Sample Data Structures

```python
# Room creation intent (returned by LLM)
intent = {
    "should_create_room": True,
    "room_name": "company-website",
    "room_type": "project",
    "summary": "Build a responsive website for your company",
    "recommended_bots": [
        {"name": "researcher", "reason": "Market research"},
        {"name": "coder", "reason": "Backend & frontend"},
        {"name": "creative", "reason": "UX/UI design"},
    ]
}

# Room list for display
rooms = [
    {
        "id": "general",
        "type": "open",
        "participants": 1,
        "is_default": True,
        "active": False
    },
    {
        "id": "website-project",
        "type": "project",
        "participants": 4,
        "is_default": False,
        "active": True
    }
]
```

---

## Part 9: Key Features Summary

✅ **AI-Assisted Room Creation**
- User asks, AI recommends bots
- User confirms
- Room created & bots invited
- Automatically switch to new room

✅ **In-Session Commands**
- `/create <name>` - Create room
- `/invite <bot>` - Add bot to current room
- `/switch <room>` - Change rooms
- `/list-rooms` - Show all rooms

✅ **Enhanced CLI UI**
- Team roster display
- Room list display
- Status bar
- Visual indicators
- Compact and readable

✅ **Natural Interaction**
- Users can ask, type commands, or mix both
- System responds intelligently
- Always know which room and team

---

## Summary

With **Rich** and **prompt_toolkit** already available, we can:

1. **Create advanced UI** showing team & rooms
2. **Add AI-assisted room creation** - user asks, bot creates & invites
3. **Implement all in-session commands** - `/create`, `/invite`, `/switch`, `/list-rooms`
4. **Maintain clean interface** - status bar + optional sidebar
5. **Smooth user experience** - natural conversation + commands

Everything can be built incrementally, with the basic version working immediately and enhanced UI as a future improvement.
