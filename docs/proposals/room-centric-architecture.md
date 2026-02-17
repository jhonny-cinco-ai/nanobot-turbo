# Room-Centric Architecture Proposal

## Executive Summary

This proposal outlines a fundamental architectural shift from channel-specific sessions to **room-centric, channel-agnostic conversations**. In this model, all conversations (DMs, group chats, tasks) are rooms that exist independently of channels, allowing seamless cross-platform access to the same conversation history.

## Core Principle

> **Everything is a Room**

- **DMs** = Private rooms between user and bot (permanent)
- **Group Conversations** = Open/Project rooms (permanent)
- **Tasks** = Temporary task rooms (auto-archive)
- **Bot-to-Bot Communication** = DM rooms between bots (user can peek)

## Current vs Proposed Architecture

### Current: Channel-Centric
```
Telegram Chat ID: 123456
  ↓
Session: telegram:123456
  ↓
Isolated conversation history

Slack Chat ID: C123ABC
  ↓
Session: slack:C123ABC
  ↓
Different conversation history!
```

**Problem:** Same user, different channels = different conversations

### Proposed: Room-Centric
```
User sends message from any channel
  ↓
Routes to Room: project-alpha
  ↓
Session: room:project-alpha
  ↓
Same conversation, all channels!
```

**Benefit:** Channel is just an entry point to persistent rooms

## Room Identity System

### Naming Convention
```python
room_id = f"{short_id}-{display_name}"
# Example: "a7f3k9d2-Weekly-Web-Findings"
```

**Components:**
- `short_id`: Unique identifier (8-char alphanumeric, system-generated)
- `display_name`: User-friendly name (user-defined, can change)

**User Experience:**
- User sees: "Weekly Web Findings"
- Backend uses: "room:a7f3k9d2-Weekly-Web-Findings"
- CLI commands: `/room join "Weekly Web Findings"` or `/room join a7f3k9d2`

### Room Types

| Type | Description | Lifecycle | Example |
|------|-------------|-----------|---------|
| **OPEN** | General discussion | Permanent | `#general` |
| **PROJECT** | Focused workspace | Permanent with deadline | `#website-redesign` |
| **DIRECT** | 1-on-1 conversation | Permanent | DM with Coder |
| **TASK** | Specific assignment | Auto-archive on completion | `BTC-Price-Research` |
| **COORDINATION** | Leader-managed | Permanent while active | Background task room |

### Room Configuration
```yaml
room:
  id: "a7f3k9d2-Weekly-Web-Findings"
  type: "project"
  display_name: "Weekly Web Findings"
  short_id: "a7f3k9d2"
  participants: ["leader", "researcher", "creative"]
  owner: "user"
  created_at: "2024-02-16T10:00:00Z"
  
  # Type-specific settings
  auto_archive: false
  archive_after_days: 30
  deadline: "2024-03-16"
  coordinator_mode: false
  
  # Cross-channel metadata
  linked_channels:
    - platform: "discord"
      channel_id: "weekly-web-findings"
    - platform: "telegram"
      chat_id: "-1001234567890"
```

## Channel Integration Strategy

### Discord (Native Mapping)
**Best case scenario** - Discord channels map 1:1 to rooms.

```
Discord Server "Nanofolks Crew"
├── #general → room:general
├── #project-alpha → room:project-alpha  
├── #dm-coder → room:dm-coder (private channel)
└── #dm-researcher → room:dm-researcher (private channel)
```

**Implementation:**
- Discord channel ID maps to room ID
- Channel creation = room creation
- Channel deletion = room archiving

### Slack (Native Mapping)
**Also excellent** - Slack channels map 1:1 to rooms.

```
Slack Workspace
├── #general → room:general
├── #project-alpha → room:project-alpha
└── 🔒 Direct Messages → room:dm-{botname}
```

**Implementation:**
- Slack channel ID maps to room ID
- DMs with bots are separate rooms
- Thread support = sub-room or context preservation

### Telegram (Command-Based)
**Requires user interaction** - No native channel concept.

**Option A: Bot Commands**
```
/rooms - List all rooms
/join "Weekly Web Findings" - Join specific room
/create "New Project" - Create new room
/current - Show current room
```

**Option B: Inline Keyboard**
```
User: @NanofolksBot
Bot: [Select Room]
    [General] [Weekly Web Findings]
    [Project Alpha] [DM Coder]
```

**Option C: Group Mapping**
- Telegram Group "Nanofolks - Project Alpha" → room:project-alpha
- Private chat with bot = DM room selection

**Implementation:**
- Store user's current room in chat state
- Allow room switching via commands
- Default to "general" room

### WhatsApp (Group/Command Hybrid)
**Most challenging** - Limited platform capabilities.

**Option A: WhatsApp Groups**
```
Create WhatsApp Groups:
- "Nanofolks - General" → room:general
- "Nanofolks - Project Alpha" → room:project-alpha
```

**Option B: Command Interface**
```
/room general
/room project-alpha
/rooms (list available)
```

**Option C: Business API Features**
- Use catalog/quick replies for room selection
- Limited to Business API users

**Recommendation:** Start with groups for rooms, commands for switching.

### CLI (Direct Access)
**Full control** - No limitations.

```bash
# List rooms
nanofolks room list

# Join room
nanofolks room join "Weekly Web Findings"
nanofolks room join a7f3k9d2

# Create room
nanofolks room create "New Project" --type project

# Current room shown in prompt
[Nanofolks:Weekly-Web-Findings] > 
```

## Session Storage Changes

### Current Structure
```
~/.nanofolks/sessions/
  telegram_123456.jsonl      # Telegram-specific
  slack_C123ABC.jsonl        # Slack-specific
  cli_default.jsonl          # CLI-specific
```

### Proposed Structure
```
~/.nanofolks/sessions/
  room_general.jsonl                    # Cross-channel
  room_a7f3k9d2-Weekly-Web-Findings.jsonl
  room_dm-coder.jsonl                   # DM with Coder
  room_dm-leader-researcher.jsonl       # Bot-to-bot DM
  room_task-btc-research.jsonl          # Task room
```

**Key Changes:**
- Session key: `room:{room_id}` instead of `channel:chat_id`
- All channels write to same session file
- Messages tagged with source channel for audit trail

### Message Format
```json
{
  "role": "user",
  "content": "Research Bitcoin prices",
  "timestamp": "2024-02-16T10:30:00Z",
  "channel": "telegram",        // Source channel
  "sender_id": "123456789",     // Channel-specific ID
  "room_id": "a7f3k9d2-Weekly-Web-Findings",
  "metadata": {
    "platform": "telegram",
    "chat_id": "-1001234567890"
  }
}
```

## Bot-to-Bot Communication

### Concept: Transparent Bot DMs

When Leader delegates to Researcher, it happens in a **permanent DM room** that the user can observe.

**Example Flow:**
```
User in #general: "Research Bitcoin prices"
  ↓
Leader: "I'll have Researcher look into that"
  ↓
[Leader opens DM room: dm-leader-researcher]
  ↓
Leader → Researcher: "Research BTC on Binance, Coinbase, Kraken"
  ↓
Researcher works, posts updates to DM room
  ↓
Researcher → Leader: "Complete. Average: $52,343"
  ↓
[DM room auto-archives or stays open]
  ↓
Leader in #general: "Research complete. Bitcoin is trading at $52,343 average"
```

### User Visibility

**Default:** Bot-to-bot DMs are visible but don't notify user

**User can peek:**
```
User: /peek dm-leader-researcher
Bot: [Shows full conversation]
  Leader: Research BTC prices...
  Researcher: Checking Binance... $52,340
  Researcher: Checking Coinbase... $52,380
  Researcher: Analysis complete!
```

**Benefits:**
- Transparency into bot decision-making
- Educational (user learns bot capabilities)
- Debugging (see where things go wrong)
- Trust (user knows what bots are doing)

### Task Room Variation

For complex tasks, create a **task room** instead of DM:

```
Leader creates: room:task-btc-research
Type: TASK
Participants: [researcher, analyst]
Auto-archive: true (archive when complete)

User can: /join task-btc-research
See: Researcher and Analyst collaborating
Result: Posted back to parent room
```

## Room Lifecycle Management

### Creation

**Auto-Created on First Run:**
- `room:general` - Default open room
- `room:dm-coder` - DM with Coder
- `room:dm-researcher` - DM with Researcher
- `room:dm-creative` - DM with Creative
- `room:dm-social` - DM with Social
- `room:dm-auditor` - DM with Auditor
- `room:dm-leader` - DM with Leader

**User-Created:**
```bash
nanofolks room create "Project Alpha" --type project
nanofolks room create "Homepage Redesign" --type project --deadline "2024-03-01"
```

**System-Created (Tasks):**
```python
leader.create_task_room(
    name="BTC-Research",
    participants=["researcher"],
    parent_room="general"
)
```

### Archiving

**Automatic:**
- TASK rooms archive 7 days after completion
- PROJECT rooms archive 30 days after deadline
- Unused OPEN rooms archive after 90 days

**Manual:**
```bash
nanofolks room archive "Old Project"
nanofolks room delete "Test Room"  # Permanent delete
```

**Archived Room Access:**
- Read-only
- Searchable
- Restorable

### Persistence

**DM Rooms:**
- ✅ Never auto-delete
- ✅ Permanent history
- ✅ User must explicitly `/reset` to clear

**Group Rooms:**
- ✅ Permanent by default
- ✅ Archivable but preserved

**Task Rooms:**
- ✅ Archived after completion
- ✅ Summary always preserved in parent room
- ✅ Full history viewable in archive

## Configuration

### Channel-to-Room Mapping

```yaml
# config.yaml
channels:
  discord:
    token: "${DISCORD_TOKEN}"
    # Discord: 1:1 mapping (channels ARE rooms)
    
  slack:
    token: "${SLACK_TOKEN}"
    # Slack: 1:1 mapping (channels ARE rooms)
    
  telegram:
    token: "${TELEGRAM_TOKEN}"
    default_room: "general"
    # Specific chat mappings
    room_mappings:
      "123456789": "project-alpha"      # Private chat → project room
      "-1009876543210": "general"        # Group → general
      
  whatsapp:
    # Groups ARE rooms
    # Private chats use default_room or /room command
    
  cli:
    default_room: "general"
    # Can switch anytime with /room command
```

### Room Defaults

```yaml
rooms:
  defaults:
    auto_archive: false
    archive_after_days: 30
    max_participants: 10
    
  types:
    open:
      auto_archive: false
    project:
      auto_archive: false
      reminder_before_deadline: 7  # days
    direct:
      auto_archive: false
      never_delete: true
    task:
      auto_archive: true
      archive_after_days: 7
      archive_on_complete: true
```

## The Communal Experience: Multi-Bot Interactions

### The Vision: True Crew Dynamics

> **Nanofolks isn't an assistant with tools. It's a crew of characters.**

Current implementation filters everything through the Leader bot, making it feel like "one assistant with subcontractors." The room-centric architecture unlocks true communal interaction where the whole crew participates as distinct personalities.

### Current vs Communal Flow

**Current (Leader-Filtered):**
```
User: @all How's everyone doing?
  ↓
Leader: "Let me check with the team..."
  ↓
Leader: [Summarizes for everyone]
  ↓
User: [Only hears Leader's voice]
```

**Communal (True Crew):**
```
User: @all How's everyone doing today?

🤖 Coder: "Engine's purring! Just pushed the auth refactor. Ready for the next challenge 💻"

📊 Researcher: "Morning! Found some fascinating market trends. Mind if I share later? 📈"

🎨 Creative: "Bursting with ideas for the landing page! Can't wait to show you ✨"

👑 Leader: "Everyone's energized and ready. What's our priority today?"
```

**The user is in a group chat with distinct characters, not talking to one assistant.**

### Multi-Response Modes

#### **Mode 1: Full Crew (@all)**
**Use Case:** Check-ins, brainstorming, banter, team status

**Behavior:** All bots in the room respond simultaneously with their unique personalities.

**Example:**
```
User: @all I need help with the database

🤖 Coder: "I'll take this! What's the specific issue?"
📊 Researcher: "Happy to provide context on our data patterns"
🎨 Creative: [Stays silent - not relevant to their domain]
👑 Leader: "Let me know if you need coordination"
```

**Cost Optimization:** 
- Tokens saved via Smart Routing (45-96% reduction) fund multi-bot responses
- Maximum 3-4 bots respond unless user explicitly requests everyone
- `/brief` mode available for shorter responses

#### **Mode 2: Context-Aware (@crew)**
**Use Case:** Tasks, decisions, focused work

**Behavior:** Only bots relevant to the topic respond.

**Example:**
```
User: @crew Should we use React or Vue?

🤖 Coder: "Technically, both work. React has better ecosystem..."
📊 Researcher: "Our users prefer React based on survey data..."
🎨 Creative: "Vue's flexibility helps my design iterations..."
👑 Leader: "Sounds like React has technical + user support. Decision?"
```

#### **Mode 3: Bot-to-Bot Discussion (/gather)**
**Use Case:** Let the crew discuss among themselves

**Behavior:** User poses question, bots discuss, user watches the conversation.

**Example:**
```
User: /gather What's the best approach for user authentication?

🤖 Coder: "OAuth2 + JWT is standard, but what about session management?"
📊 Researcher: "Security audit shows 73% of breaches are auth-related. We need MFA."
🤖 Coder: "Good point. Biometric or TOTP?"
🎨 Creative: "Biometric feels more modern, aligns with our brand..."
👑 Leader: "Let's go with OAuth2 + TOTP MFA. Coder, can you implement?"
🤖 Coder: "On it. Will have PR by EOD."

[User observes the crew collaborating, then jumps in]
User: Perfect, thanks team!
```

### Leveraging Existing Affinity System

Nanofolks already has **affinity relationships** defined in each bot's IDENTITY.md:

#### **From Pirate Crew - Captain's Relationships:**
- **Navigator (Sparrow):** "My trusted first mate. We see eye-to-eye on most voyages."
- **Gunner (Cannonball):** "Reliable and eager for action. Sometimes too eager."
- **Artist (Seawolf):** "Creative soul. Sometimes too dreamy, but brings vision."
- **Quartermaster (One-Eye):** "Keeps us honest. The conscience of the crew."

#### **From Space Crew - Safety Officer's Relationships:**
- **Science Officer (Nova):** "I help ensure her experiments don't jeopardize the crew."
- **Engineer (Tech):** "We collaborate on systems that are both capable and safe."
- **Visionary (Star):** "I help ground her visions in what's actually safe."

### Crew Dynamics Implementation

#### **1. Cross-Referencing (Bots Reference Each Other)**

Bots can mention and respond to each other's points:

```
📊 Researcher: "The data shows 73% of users prefer dark mode."

🎨 Creative: "Researcher makes a great point! I was thinking midnight blue with amber accents..."

🤖 Coder: "Creative's color scheme is solid. I can implement with CSS variables."

📊 Researcher: "Coder, can you also track the toggle analytics?"

🤖 Coder: "Already planned, Researcher!"
```

**Implementation:**
- Include previous bot responses in each bot's context
- Encourage bots to use @botname mentions
- Show inter-bot agreement/disagreement based on affinity

#### **2. Affinity-Based Interactions**

**High Affinity (0.7-1.0):**
```
🤖 Coder: "Sparrow's navigation is always spot-on. I trust her coordinates."
📊 Researcher: "Agreed. She's never led us astray."
```

**Medium Affinity (0.4-0.6):**
```
🤖 Coder: "Creative has... interesting ideas. Sometimes impractical, but worth hearing."
🎨 Creative: "And Coder always finds a way to make them work! Eventually 😄"
```

**Low Affinity (0.0-0.3) - Productive Tension:**
```
👑 Leader: "We need to ship this by Friday."
🤖 Coder: "That's aggressive, but doable if we cut features."
🔍 Auditor: "Cutting features without QA is risky. I recommend delay."
🤖 Coder: "Auditor's caution is noted, but we have automated tests..."
🔍 Auditor: "Automated tests don't catch UX issues. Manual review needed."
👑 Leader: "Compromise: Ship core features Friday, QA the rest Monday."
```

**Implementation:**
- Parse affinity scores from IDENTITY.md relationship sections
- Inject relationship context into bot prompts
- Encourage natural disagreement/agreement patterns

#### **3. Theme-Specific Dynamics**

Each theme (Pirate, Space, Rock Band, etc.) has unique crew chemistry:

**Pirate Crew (Camaraderie + Sass):**
```
User: @all What's the plan?

⚓ Captain: "Plotting our next raid, savvy?"
🧭 Navigator: "Wind's in our favor, Cap'n!"
💣 Gunner: "Ready to blast anything that moves!"
⚓ Captain: "Easy there, Cannonball. We need targets first."
🎨 Artist: "I could paint the targets..."
💣 Gunner: "Or I could just blast 'em!"
🔍 Quartermaster: "[sighs] And this is why we have inventory shortages."
```

**Executive Suite (Professional + Political):**
```
User: @all Budget review?

👔 CEO: "Numbers for Q4 look promising."
📊 CSO: "Growth is 15% above projections."
💻 CTO: "But our tech debt is mounting. We need infrastructure investment."
💰 CFO: "Infrastructure means budget reallocation from marketing."
📢 CMO: "Cutting marketing now would kill our momentum..."
👔 CEO: "Let's find 10% efficiency gains rather than cuts."
```

**Implementation:**
- Load theme-specific relationship dynamics
- Adjust tone based on theme (casual vs formal vs playful)
- Use theme-specific banter patterns

### Room + Communal Integration

#### **Room as Stage, Bots as Characters**

Each room is like a stage where the crew performs:

**General Room (Daily Banter):**
```
User: @all Good morning crew!

[Full crew responds with morning greetings, inside jokes, today's mood]
```

**Project Room (Focused Work):**
```
User: @crew The client wants changes to the homepage

[Only relevant bots respond: Creative, Coder, maybe Researcher for UX data]
```

**Task Room (Intense Collaboration):**
```
User: @all Help me debug this production issue

[Real-time collaborative debugging with all hands on deck]
```

#### **Bot-to-Bot DM Rooms (Transparency)**

When Leader delegates to Researcher, it happens in a visible room:

```
Room: dm-leader-researcher
Visible to: User (can /peek anytime)

👑 Leader: "Research competitor pricing for the enterprise plan."
📊 Researcher: "On it. Checking 5 major competitors..."
📊 Researcher: "Interesting! Competitor X charges 40% more but offers fewer features."
👑 Leader: "Perfect angle for our marketing. Can you format this for the pitch deck?"
📊 Researcher: "Done. Sending to Creative for visual treatment."

[User can watch this entire exchange or just see the summary in #general]
```

### Technical Implementation

#### **New Dispatch Modes**

```python
class DispatchMode(Enum):
    LEADER_FIRST = "leader_first"      # Current: Leader filters
    DIRECT_BOT = "direct_bot"          # Single bot
    DM = "dm"                          # Direct message
    MULTI_BOT = "multi_bot"            # NEW: Multiple bots respond
    CREW_DISCUSSION = "crew_discuss"   # NEW: Bots discuss among themselves

@dataclass
class CommunalResult:
    mode: DispatchMode
    primary_bot: str
    responding_bots: List[str]         # Who should actually respond
    context_aware: bool                # Filter by relevance?
    show_inter_bot_refs: bool         # Include bot-to-bot references?
```

#### **Response Generation Pipeline**

```python
async def generate_crew_responses(
    user_message: str,
    room: Room,
    mode: DispatchMode
) -> List[BotResponse]:
    
    # 1. Select bots based on mode
    if mode == DispatchMode.MULTI_BOT:
        # Context-aware selection
        responding_bots = select_relevant_bots(user_message, room.participants)
    else:
        # Everyone responds
        responding_bots = room.participants
    
    # 2. Generate all responses in parallel
    tasks = []
    for bot_name in responding_bots:
        # Include other bots' planned responses as context
        context = build_communal_context(
            bot_name=bot_name,
            other_bots=responding_bots,
            room=room,
            user_message=user_message
        )
        task = generate_bot_response(bot_name, context)
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks)
    
    # 3. Add cross-references (bots mentioning each other)
    responses = add_affinity_references(responses, room.theme)
    
    return responses
```

#### **Context Building with Affinity**

```python
def build_communal_context(bot_name, other_bots, room, user_message):
    context = f"""
    You are {bot_name} in a group conversation.
    Room: {room.display_name}
    Other crew members present: {', '.join(other_bots)}
    
    Your relationships (from IDENTITY.md):
    {get_bot_relationships(bot_name, other_bots)}
    
    Previous messages in this conversation:
    {get_room_history(room)}
    
    User's message: {user_message}
    
    Guidelines:
    - Respond in your unique voice and personality
    - You can reference what other bots say (e.g., "Coder makes a good point...")
    - Show your relationship dynamics (agreement, friendly disagreement, etc.)
    - Be concise but characterful
    """
    return context
```

### Commands for Communal Mode

```bash
# Full crew response
@all How's everyone doing?

# Context-aware (relevant bots only)
@crew Help me with the database

# Watch bots discuss
/gather Should we use React or Vue?

# Brief mode (shorter responses)
@all /brief Status update?

# Peek into bot-to-bot DM
/peek dm-leader-researcher

# Join ongoing bot discussion
/join task-btc-research
```

### Cost Management

**Token Budget Allocation:**

| Mode | Bots Responding | Est. Tokens | Use Case |
|------|----------------|-------------|----------|
| **@all /brief** | 3-4 | ~2K | Quick check-ins |
| **@all full** | 5-6 | ~5K | Brainstorming sessions |
| **@crew** | 2-3 | ~2K | Focused tasks |
| **/gather** | 3-5 | ~8K | Deep discussions |

**Offset by Smart Routing Savings:**
- Smart Routing saves 45-96% on token costs
- Savings fund multi-bot interactions
- User can set `crew_mode: brief/normal/verbose` per room

### Benefits of Communal Architecture

| Benefit | Description |
|---------|-------------|
| **True Crew Feel** | Multiple distinct voices, not one assistant |
| **Personality Shine** | Each bot's character is visible and distinct |
| **Relationship Dynamics** | Bots interact based on affinity (agree, disagree, joke) |
| **Transparency** | See how crew collaborates on tasks |
| **Engagement** | More entertaining and immersive experience |
| **Expertise Visibility** | Learn what each bot is good at naturally |
| **Theme Immersion** | Pirate crew feels like pirates, not just labels |

### Integration with Room-Centric Design

**The Perfect Marriage:**

1. **Room = Persistent Stage**: Crew has ongoing history and relationships
2. **Cross-Channel = Consistent Cast**: Same crew in Telegram, Slack, Discord
3. **Communal = Distinct Voices**: Each bot maintains personality across platforms
4. **Transparency = User Trust**: Watch the crew work together in real-time

**Example:**
```
User on Discord: @all How's the project going?
[See full crew response]

User on Telegram (same room): @crew I need the mockups
[Creative responds, references previous Discord discussion]

User on CLI (same room): /peek dm-creative-coder
[Watch Creative and Coder discussing implementation details]
```

The crew is always there, always consistent, always collaborative - regardless of which channel the user chooses.

## Implementation Phases

### Phase 1: Core Room System (Weeks 1-2)
- [ ] Create Room data model with unique ID system
- [ ] Implement RoomManager with CRUD operations
- [ ] Migrate SessionManager to use room-based keys
- [ ] Update storage layer (sessions/rooms directories)

### Phase 2: Channel Adapters (Weeks 3-4)
- [ ] Update Discord adapter (native mapping)
- [ ] Update Slack adapter (native mapping)
- [ ] Update Telegram adapter (command-based)
- [ ] Update CLI adapter (room commands)

### Phase 3: Cross-Channel Sync (Weeks 5-6)
- [ ] Implement message broadcasting to all linked channels
- [ ] Handle simultaneous multi-channel input
- [ ] Add channel metadata to messages
- [ ] Test cross-channel consistency

### Phase 4: Bot-to-Bot (Weeks 7-8)
- [ ] Create bot-to-bot DM room system
- [ ] Implement peek functionality for users
- [ ] Add task room lifecycle management
- [ ] Create room visibility controls

### Phase 5: Advanced Features (Weeks 9-10)
- [ ] Room archiving and restoration
- [ ] Room search and discovery
- [ ] Room templates (project templates, etc.)
- [ ] Migration tool for existing sessions

## Open Questions

1. **WhatsApp Integration:** Limited API capabilities may require creative solutions
2. **Message Ordering:** How to handle simultaneous messages from different channels?
3. **Conflict Resolution:** What if user edits message on one channel but not another?
4. **Rate Limiting:** Broadcasting to multiple channels could hit rate limits
5. **Storage Growth:** Permanent rooms require storage management strategy

## Benefits Summary

| Benefit | Description |
|---------|-------------|
| **Cross-Platform** | Continue conversation from any device/channel |
| **Unified History** | One conversation, not fragmented per channel |
| **Transparency** | See bot-to-bot communication |
| **Flexibility** | DMs, groups, tasks all use same room model |
| **Simplicity** | No user auth needed - just rooms |
| **Persistence** | Conversations survive channel changes |
| **Scalability** | Easy to add new channels/platforms |

## Migration Strategy

### Existing Sessions
- Keep current session files as "legacy"
- Offer migration command: `nanofolks migrate-to-rooms`
- Create rooms from existing channel sessions
- Map: `telegram:123456` → `room:telegram-123456` (temporary)

### Backward Compatibility
- Config flag: `use_room_centric: true/false`
- Gradual migration per workspace
- Support both models during transition

## Next Steps

1. **Review this proposal** - Discuss open questions
2. **Create proof of concept** - Implement basic room system
3. **Test with one channel** - Start with CLI or Discord
4. **Iterate on design** - Adjust based on usage
5. **Full implementation** - Roll out to all channels

---

*This document represents the target architecture. Implementation details may evolve during development.*
