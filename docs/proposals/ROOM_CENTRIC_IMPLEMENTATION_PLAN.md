# Two-Phase Room-Centric Architecture Implementation Plan

> **⚠️ DEPRECATED**: See [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) for the latest phased approach.

## Executive Summary

This document outlines the original two-phase implementation strategy. For the current implementation plan with the hybrid flow approach, see the consolidated [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md).

**Current Status:** Phase 1 COMPLETE 

**Phase 1 (Foundation):** Hybrid Approach - 3 weeks  
**Phase 2 (Architecture):** Full Room-Centric Migration - 7 weeks  
**Total Duration:** 10 weeks  
**Risk Level:** Low → Medium (gradual increase)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CURRENT STATE (Channel-Centric)                  │
│  telegram:123456 ──┐                                                │
│  slack:C123ABC ────┼── Isolated sessions, Leader-filtered responses │
│  cli:default ──────┘                                                │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1 (Weeks 1-3): Hybrid Foundation                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ DM Rooms     │  │ Multi-Bot    │  │ Affinity     │               │
│  │ /peek        │  │ @all/@crew   │  │ Relations    │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                     │
│  • Keep channel:chat_id sessions                                    │
│  • Add bot-to-bot room files                                        │
│  • Simultaneous bot responses                                       │
│  • No breaking changes                                              │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2 (Weeks 4-10): Full Room-Centric Architecture               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Session      │  │ Cross-       │  │ Task Rooms   │               │
│  │ Migration    │  │ Channel Sync │  │ Lifecycle    │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                     │
│  • room:{id} session keys                                           │
│  • Unified cross-channel history                                    │
│  • Automatic task room archiving                                    │
│  • Config flag for gradual rollout                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Hybrid Foundation (Weeks 1-3)

### Goals
1. Deliver user-facing features quickly without breaking changes
2. Enable transparent bot-to-bot communication
3. Create communal multi-bot experience
4. Validate the approach before major architectural changes

### Week 1: Bot-to-Bot DM Rooms

#### Objective
Create persistent, observable rooms for bot-to-bot conversations that users can peek into.

#### Implementation Details

**1.1 DM Room Data Model**
```python
# nanofolks/models/bot_dm_room.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum

class BotMessageType(Enum):
    QUERY = "query"           # Question expecting reply
    RESPONSE = "response"     # Reply to query
    INFO = "info"             # Information sharing
    ESCALATION = "escalation" # Problem report

@dataclass
class BotDMMessage:
    """A message in a bot-to-bot DM room."""
    id: str
    timestamp: datetime
    sender_bot: str           # e.g., "leader"
    recipient_bot: str        # e.g., "researcher"
    message_type: BotMessageType
    content: str
    context: dict = field(default_factory=dict)
    reply_to: Optional[str] = None  # ID of message being replied to
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "sender_bot": self.sender_bot,
            "recipient_bot": self.recipient_bot,
            "message_type": self.message_type.value,
            "content": self.content,
            "context": self.context,
            "reply_to": self.reply_to
        }

@dataclass
class BotDMRoom:
    """A DM room between two bots (or one-to-many for group DMs)."""
    room_id: str              # e.g., "dm-leader-researcher"
    bot_a: str                # e.g., "leader"
    bot_b: str                # e.g., "researcher"
    created_at: datetime
    messages: List[BotDMMessage] = field(default_factory=list)
    is_group: bool = False    # True if more than 2 bots
    
    @property
    def display_name(self) -> str:
        """Human-readable name for the room."""
        if self.is_group:
            return f"Group: {', '.join([self.bot_a, self.bot_b])}"
        return f"DM: @{self.bot_a} ↔ @{self.bot_b}"
```

**1.2 DM Room Manager**
```python
# nanofolks/bots/dm_room_manager.py
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime
from loguru import logger

class BotDMRoomManager:
    """Manages bot-to-bot DM rooms with persistence."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.dm_rooms_dir = workspace / ".nanofolks" / "dm_rooms"
        self.dm_rooms_dir.mkdir(parents=True, exist_ok=True)
    
    def get_or_create_dm_room(self, bot_a: str, bot_b: str) -> BotDMRoom:
        """Get existing DM room or create new one."""
        room_id = self._generate_room_id(bot_a, bot_b)
        room_path = self.dm_rooms_dir / f"{room_id}.jsonl"
        
        if room_path.exists():
            return self._load_room(room_path)
        
        # Create new room
        room = BotDMRoom(
            room_id=room_id,
            bot_a=bot_a,
            bot_b=bot_b,
            created_at=datetime.now()
        )
        self._save_room(room)
        logger.info(f"Created DM room: {room_id}")
        return room
    
    def _generate_room_id(self, bot_a: str, bot_b: str) -> str:
        """Generate consistent room ID (order-independent)."""
        bots = sorted([bot_a, bot_b])
        return f"dm-{bots[0]}-{bots[1]}"
    
    def log_message(
        self,
        sender_bot: str,
        recipient_bot: str,
        content: str,
        message_type: BotMessageType = BotMessageType.INFO,
        context: Optional[dict] = None,
        reply_to: Optional[str] = None
    ) -> str:
        """Log a message to the appropriate DM room."""
        room = self.get_or_create_dm_room(sender_bot, recipient_bot)
        
        import uuid
        message = BotDMMessage(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            sender_bot=sender_bot,
            recipient_bot=recipient_bot,
            message_type=message_type,
            content=content,
            context=context or {},
            reply_to=reply_to
        )
        
        room.messages.append(message)
        self._append_message(room, message)
        
        return message.id
    
    def _append_message(self, room: BotDMRoom, message: BotDMMessage):
        """Append single message to room file."""
        room_path = self.dm_rooms_dir / f"{room.room_id}.jsonl"
        with open(room_path, 'a') as f:
            f.write(json.dumps(message.to_dict()) + '\n')
    
    def get_conversation_history(
        self,
        bot_a: str,
        bot_b: str,
        limit: int = 50
    ) -> List[BotDMMessage]:
        """Get conversation history between two bots."""
        room_id = self._generate_room_id(bot_a, bot_b)
        room_path = self.dm_rooms_dir / f"{room_id}.jsonl"
        
        if not room_path.exists():
            return []
        
        messages = []
        with open(room_path, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    messages.append(self._dict_to_message(data))
                except json.JSONDecodeError:
                    continue
        
        return messages[-limit:]  # Return last N messages
    
    def list_all_dm_rooms(self) -> List[dict]:
        """List all DM rooms with metadata."""
        rooms = []
        for room_file in self.dm_rooms_dir.glob("dm-*.jsonl"):
            room_id = room_file.stem
            # Parse room_id: dm-bot_a-bot_b
            parts = room_id.split('-')
            if len(parts) >= 3:
                rooms.append({
                    "room_id": room_id,
                    "bot_a": parts[1],
                    "bot_b": parts[2],
                    "message_count": self._count_messages(room_file),
                    "last_activity": self._get_last_activity(room_file)
                })
        return rooms
    
    def _count_messages(self, room_file: Path) -> int:
        """Count messages in a room file."""
        try:
            with open(room_file, 'r') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    def _get_last_activity(self, room_file: Path) -> Optional[str]:
        """Get timestamp of last message."""
        try:
            with open(room_file, 'r') as f:
                lines = f.readlines()
                if lines:
                    last = json.loads(lines[-1].strip())
                    return last.get('timestamp')
        except:
            pass
        return None
```

**1.3 Enhanced Bot Base Class**
```python
# nanofolks/bots/base.py - Additions to SpecialistBot

async def ask_bot(
    self,
    recipient_bot: str,
    question: str,
    context: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 60
) -> tuple[bool, Optional[str]]:
    """Ask another bot a question and wait for answer.
    
    Now with DM room logging for transparency.
    """
    from nanofolks.bots.dm_room_manager import BotDMRoomManager, BotMessageType
    
    # Log the query to DM room
    dm_manager = BotDMRoomManager(self.workspace)
    query_id = dm_manager.log_message(
        sender_bot=self.role_card.bot_name,
        recipient_bot=recipient_bot,
        content=question,
        message_type=BotMessageType.QUERY,
        context=context
    )
    
    # Send message via bus
    success, reply = await self._send_and_wait(
        recipient_bot, question, context, timeout_seconds
    )
    
    if success and reply:
        # Log the response to DM room
        dm_manager.log_message(
            sender_bot=recipient_bot,
            recipient_bot=self.role_card.bot_name,
            content=reply,
            message_type=BotMessageType.RESPONSE,
            context={"reply_to": query_id}
        )
    
    return success, reply
```

**1.4 CLI /peek Command**
```python
# nanofolks/cli/commands.py - Add to commands

@cmd_group.command()
@click.argument('room_id')
@click.option('--limit', '-n', default=20, help='Number of messages to show')
@click.pass_obj
async def peek(obj, room_id: str, limit: int):
    """Peek into a bot-to-bot DM room conversation.
    
    Examples:
        nanofolks peek dm-leader-researcher
        nanofolks peek dm-coder-auditor --limit 50
    """
    from nanofolks.bots.dm_room_manager import BotDMRoomManager
    
    workspace = obj['workspace']
    dm_manager = BotDMRoomManager(workspace)
    
    # Parse room_id: dm-bot_a-bot_b
    if not room_id.startswith('dm-'):
        click.echo("❌ Invalid room ID. Format: dm-bot_a-bot_b", err=True)
        return
    
    parts = room_id.split('-')
    if len(parts) != 3:
        click.echo("❌ Invalid room ID format. Use: dm-bot_a-bot_b", err=True)
        return
    
    bot_a, bot_b = parts[1], parts[2]
    
    # Get conversation history
    messages = dm_manager.get_conversation_history(bot_a, bot_b, limit=limit)
    
    if not messages:
        click.echo(f"📭 No messages in {room_id} yet")
        return
    
    # Display formatted conversation
    click.echo(f"\n🔍 Bot-to-Bot Conversation: @{bot_a} ↔ @{bot_b}")
    click.echo("=" * 60)
    
    for msg in messages:
        timestamp = msg.timestamp.strftime("%H:%M")
        sender = msg.sender_bot
        
        # Format based on message type
        if msg.message_type.value == "query":
            prefix = "❓"
        elif msg.message_type.value == "response":
            prefix = "💬"
        elif msg.message_type.value == "escalation":
            prefix = "🚨"
        else:
            prefix = "📝"
        
        click.echo(f"\n{prefix} [{timestamp}] @{sender}:")
        click.echo(f"   {msg.content}")
    
    click.echo("\n" + "=" * 60)
    click.echo(f"📊 Total messages: {len(messages)}")
```

**1.5 Auto-Create DM Rooms on Startup**
```python
# nanofolks/bots/room_manager.py - Enhancements

def ensure_dm_rooms_exist(self):
    """Create DM rooms for all bot pairs on startup."""
    from nanofolks.bots.dm_room_manager import BotDMRoomManager
    
    bots = ["leader", "researcher", "coder", "social", "creative", "auditor"]
    dm_manager = BotDMRoomManager(self.workspace)
    
    # Create DM rooms for all pairs
    for i, bot_a in enumerate(bots):
        for bot_b in bots[i+1:]:
            room = dm_manager.get_or_create_dm_room(bot_a, bot_b)
            logger.debug(f"Ensured DM room exists: {room.room_id}")
```

#### Testing Checklist
- [x] DM rooms created automatically on startup
- [x] `ask_bot()` logs messages to DM room
- [x] `/peek dm-leader-researcher` displays conversation
- [x] Messages persisted across restarts
- [x] Both directions of conversation captured
- [ ] Group DM rooms work (3+ bots)

---

### Week 2: Multi-Bot Response Modes ✅ COMPLETE

#### Objective
Enable simultaneous responses from multiple bots for `@all` and `@crew` mentions, creating the communal experience.

#### Implementation Details

**Status:** Implementation complete in:
- `nanofolks/bots/dispatch.py` - Enhanced with MULTI_BOT and CREW_CONTEXT modes
- `nanofolks/agent/multi_bot_generator.py` - New parallel response generator
- `nanofolks/agent/loop.py` - Multi-bot handling integrated

**2.1 Enhanced Dispatch Modes**
```python
# nanofolks/bots/dispatch.py

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

class DispatchMode(Enum):
    """How to dispatch messages to bots."""
    LEADER_FIRST = "leader_first"      # Current: Leader handles everything
    DIRECT_BOT = "direct_bot"          # Current: Single bot response
    DM = "dm"                          # Current: Direct message
    MULTI_BOT = "multi_bot"            # NEW: All bots respond (@all)
    CREW_CONTEXT = "crew_context"      # NEW: Relevant bots respond (@crew)
    CREW_DISCUSSION = "crew_discuss"   # NEW: Bots discuss among themselves

@dataclass
class DispatchResult:
    mode: DispatchMode
    primary_bot: str
    secondary_bots: List[str]          # Bots that should also respond
    context_aware: bool                # Whether to filter by relevance
    reason: str
    
class BotDispatch:
    """Enhanced dispatch with multi-bot support."""
    
    def dispatch(self, message: str, room: Room) -> DispatchResult:
        """Determine how to dispatch a message."""
        
        # Check for @all mention
        if "@all" in message.lower():
            return DispatchResult(
                mode=DispatchMode.MULTI_BOT,
                primary_bot="leader",  # Leader still coordinates
                secondary_bots=room.participants,
                context_aware=False,
                reason="User tagged @all - all bots respond"
            )
        
        # Check for @crew mention
        if "@crew" in message.lower():
            relevant_bots = self._select_relevant_bots(message, room.participants)
            return DispatchResult(
                mode=DispatchMode.CREW_CONTEXT,
                primary_bot="leader",
                secondary_bots=relevant_bots,
                context_aware=True,
                reason="User tagged @crew - relevant bots respond"
            )
        
        # Check for specific bot mentions
        mentioned = self._extract_mentions(message)
        if mentioned:
            if len(mentioned) == 1:
                return DispatchResult(
                    mode=DispatchMode.DIRECT_BOT,
                    primary_bot=mentioned[0],
                    secondary_bots=[],
                    context_aware=False,
                    reason=f"Direct mention of @{mentioned[0]}"
                )
            else:
                return DispatchResult(
                    mode=DispatchMode.MULTI_BOT,
                    primary_bot="leader",
                    secondary_bots=mentioned,
                    context_aware=False,
                    reason=f"Multiple mentions: {', '.join(mentioned)}"
                )
        
        # Default: Leader first
        return DispatchResult(
            mode=DispatchMode.LEADER_FIRST,
            primary_bot="leader",
            secondary_bots=[],
            context_aware=True,
            reason="No specific routing - leader handles"
        )
    
    def _select_relevant_bots(self, message: str, all_bots: List[str]) -> List[str]:
        """Select bots relevant to the message content."""
        message_lower = message.lower()
        
        # Keywords that trigger specific bots
        bot_keywords = {
            "coder": ["code", "programming", "bug", "fix", "python", "javascript", "api", "database", "sql"],
            "researcher": ["research", "data", "analyze", "market", "competitor", "trend", "survey"],
            "creative": ["design", "visual", "logo", "brand", "color", "ui", "ux", "mockup"],
            "social": ["post", "tweet", "engagement", "audience", "viral", "hashtag", "content"],
            "auditor": ["audit", "quality", "compliance", "security", "review", "check"],
            "leader": ["plan", "coordinate", "delegate", "prioritize", "team", "schedule"]
        }
        
        relevance_scores = {}
        for bot in all_bots:
            score = 0
            keywords = bot_keywords.get(bot, [])
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            relevance_scores[bot] = score
        
        # Return bots with score > 0, or all if none match
        relevant = [bot for bot, score in relevance_scores.items() if score > 0]
        return relevant if relevant else all_bots[:3]  # Max 3 if no clear match
```

**2.2 Multi-Bot Response Generator**
```python
# nanofolks/agent/multi_bot_generator.py

import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass
from loguru import logger

@dataclass
class BotResponse:
    """Response from a single bot."""
    bot_name: str
    content: str
    confidence: float
    response_time_ms: int
    metadata: Dict[str, Any]

class MultiBotResponseGenerator:
    """Generate responses from multiple bots simultaneously."""
    
    def __init__(self, provider, context_builder):
        self.provider = provider
        self.context_builder = context_builder
    
    async def generate_responses(
        self,
        user_message: str,
        room: Room,
        bot_names: List[str],
        mode: DispatchMode
    ) -> List[BotResponse]:
        """Generate responses from multiple bots in parallel."""
        
        logger.info(f"Generating multi-bot responses from: {', '.join(bot_names)}")
        
        # Create tasks for each bot
        tasks = []
        for bot_name in bot_names:
            task = self._generate_single_response(
                bot_name=bot_name,
                user_message=user_message,
                room=room,
                other_bots=bot_names  # Let bot know who else is responding
            )
            tasks.append(task)
        
        # Execute all in parallel
        import time
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = (time.time() - start_time) * 1000
        
        # Process results
        bot_responses = []
        for i, result in enumerate(responses):
            bot_name = bot_names[i]
            
            if isinstance(result, Exception):
                logger.error(f"[{bot_name}] Failed to generate response: {result}")
                bot_responses.append(BotResponse(
                    bot_name=bot_name,
                    content=f"❌ Error: Could not generate response",
                    confidence=0.0,
                    response_time_ms=0,
                    metadata={"error": str(result)}
                ))
            else:
                bot_responses.append(result)
        
        logger.info(f"Generated {len(bot_responses)} responses in {total_time:.0f}ms")
        return bot_responses
    
    async def _generate_single_response(
        self,
        bot_name: str,
        user_message: str,
        room: Room,
        other_bots: List[str]
    ) -> BotResponse:
        """Generate response for a single bot."""
        import time
        
        start_time = time.time()
        
        try:
            # Build context with communal awareness
            context = self._build_communal_context(
                bot_name=bot_name,
                user_message=user_message,
                room=room,
                other_bots=other_bots
            )
            
            # Generate response
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": user_message}
                ],
                model=self._get_bot_model(bot_name)
            )
            
            response_time = (time.time() - start_time) * 1000
            
            return BotResponse(
                bot_name=bot_name,
                content=response.content,
                confidence=getattr(response, 'confidence', 0.8),
                response_time_ms=int(response_time),
                metadata={
                    "model": self._get_bot_model(bot_name),
                    "tokens_used": getattr(response, 'tokens_used', 0)
                }
            )
            
        except Exception as e:
            logger.error(f"[{bot_name}] Response generation failed: {e}")
            raise
    
    def _build_communal_context(
        self,
        bot_name: str,
        user_message: str,
        room: Room,
        other_bots: List[str]
    ) -> str:
        """Build context that includes awareness of other bots."""
        
        # Get bot's role card
        from nanofolks.models import get_role_card
        role_card = get_role_card(bot_name)
        
        # Get bot's identity
        identity = self._load_bot_identity(bot_name)
        
        # Build context
        context_parts = [
            f"# You are @{bot_name}",
            f"",
            f"## Role",
            role_card.format_for_prompt() if role_card else f"Domain: {bot_name}",
            f"",
            f"## Identity",
            identity or f"You are {bot_name}, a specialist bot.",
            f"",
            f"## Current Context",
            f"Room: {room.display_name}",
            f"Other bots present: {', '.join(other_bots)}",
            f"You are responding as part of a group conversation.",
            f"",
            f"## Instructions",
            f"- Respond in your unique voice and personality",
            f"- You can reference what other bots might say",
            f"- Be concise but characterful (2-3 sentences max)",
            f"- Show your domain expertise",
            f"- Use your specific tone (professional, casual, technical, etc.)",
        ]
        
        return "\n".join(context_parts)
```

**2.3 Agent Loop Integration**
```python
# nanofolks/agent/loop.py - Modifications to handle multi-bot

async def _process_message(self, msg: MessageEnvelope) -> MessageEnvelope | None:
    """Process a message with multi-bot support."""
    
    # ... existing code ...
    
    # Get dispatch result
    dispatch_result = self.dispatcher.dispatch(msg.content, room)
    
    if dispatch_result.mode in [DispatchMode.MULTI_BOT, DispatchMode.CREW_CONTEXT]:
        # Handle multi-bot response
        return await self._handle_multi_bot_response(
            msg, dispatch_result, room, session
        )
    else:
        # Handle single bot (existing logic)
        return await self._handle_single_bot_response(
            msg, dispatch_result, room, session
        )

async def _handle_multi_bot_response(
    self,
    msg: MessageEnvelope,
    dispatch: DispatchResult,
    room: Room,
    session: Session
) -> MessageEnvelope:
    """Handle responses from multiple bots."""
    
    from nanofolks.agent.multi_bot_generator import MultiBotResponseGenerator
    
    # Generate responses
    generator = MultiBotResponseGenerator(self.provider, self.context)
    responses = await generator.generate_responses(
        user_message=msg.content,
        room=room,
        bot_names=dispatch.secondary_bots,
        mode=dispatch.mode
    )
    
    # Format combined response
    combined_content = self._format_multi_bot_response(responses)
    
    # Log to work log
    for response in responses:
        self.work_log_manager.log(
            level=LogLevel.INFO,
            category="multi_bot_response",
            message=f"@{response.bot_name} responded",
            details={
                "bot": response.bot_name,
                "content_preview": response.content[:100],
                "confidence": response.confidence
            }
        )
    
    return MessageEnvelope(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=combined_content,
        metadata={
            "multi_bot": True,
            "responding_bots": [r.bot_name for r in responses],
            "mode": dispatch.mode.value
        }
    )

def _format_multi_bot_response(self, responses: List[BotResponse]) -> str:
    """Format multiple bot responses into cohesive output."""
    
    # Bot emoji mapping
    bot_emojis = {
        "leader": "👑",
        "researcher": "📊",
        "coder": "🤖",
        "social": "📱",
        "creative": "🎨",
        "auditor": "🔍"
    }
    
    parts = []
    for response in responses:
        emoji = bot_emojis.get(response.bot_name, "🤖")
        parts.append(f"{emoji} **@{response.bot_name}:**\n{response.content}\n")
    
    return "\n".join(parts)
```

**2.4 CLI Display for Multi-Bot**
```python
# nanofolks/cli/room_ui.py - Enhance display

def display_multi_bot_response(
    self,
    responses: List[BotResponse],
    console: Console
):
    """Display multi-bot responses with formatting."""
    
    bot_emojis = {
        "leader": "👑",
        "researcher": "📊",
        "coder": "🤖",
        "social": "📱",
        "creative": "🎨",
        "auditor": "🔍"
    }
    
    for i, response in enumerate(responses):
        emoji = bot_emojis.get(response.bot_name, "🤖")
        
        # Create panel for each bot
        panel = Panel(
            response.content,
            title=f"{emoji} @{response.bot_name}",
            border_style=self._get_bot_color(response.bot_name),
            title_align="left"
        )
        
        console.print(panel)
        
        # Add small delay between responses for dramatic effect
        if i < len(responses) - 1:
            time.sleep(0.3)

def _get_bot_color(self, bot_name: str) -> str:
    """Get color for bot."""
    colors = {
        "leader": "blue",
        "researcher": "cyan",
        "coder": "green",
        "social": "magenta",
        "creative": "yellow",
        "auditor": "red"
    }
    return colors.get(bot_name, "white")
```

#### Testing Checklist
- [x] `@all` triggers responses from all room participants
- [x] `@crew` selects relevant bots based on keywords
- [x] Bot mentions work (single and multiple)
- [x] Responses generated in parallel
- [x] Each bot responds with unique personality
- [x] Formatted output with bot emojis/names
- [x] Works in CLI

---

### Week 3: Affinity & Relationships ✅ COMPLETE

#### Objective
Inject bot relationship dynamics from IDENTITY.md into communal contexts, enabling bots to reference each other and show personality-based interactions.

#### Implementation Details

**Status:** Implementation complete in:
- `nanofolks/identity/relationship_parser.py` - NEW
- `nanofolks/agent/affinity_context.py` - NEW
- `nanofolks/agent/cross_reference.py` - NEW
- `nanofolks/agent/multi_bot_generator.py` - MODIFIED (affinity integration)

**3.1 Relationship Parser**
```python
# nanofolks/identity/relationship_parser.py

import re
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class BotRelationship:
    """Relationship between two bots."""
    target_bot: str
    affinity: float  # 0.0 to 1.0
    description: str
    interaction_style: str  # "agreeable", "challenging", "neutral"

class RelationshipParser:
    """Parse relationship sections from IDENTITY.md files."""
    
    def parse_relationships(self, identity_content: str) -> List[BotRelationship]:
        """Extract relationships from IDENTITY.md content."""
        
        relationships = []
        
        # Look for "## Relationships" or "### Relationships" section
        relationship_section = self._extract_section(
            identity_content, 
            ["## Relationships", "### Relationships", "## Relationships with Others"]
        )
        
        if not relationship_section:
            return relationships
        
        # Parse bullet points
        lines = relationship_section.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                relationship = self._parse_relationship_line(line)
                if relationship:
                    relationships.append(relationship)
        
        return relationships
    
    def _parse_relationship_line(self, line: str) -> Optional[BotRelationship]:
        """Parse a single relationship line.
        
        Expected formats:
        - Researcher: High affinity, we agree on most things
        - Creative (low affinity): Sometimes too dreamy
        - Auditor [0.3]: Keeps us honest but can be rigid
        """
        # Remove bullet marker
        line = line.lstrip('-*').strip()
        
        # Try to extract bot name
        bot_match = re.match(r'^(\w+)\s*[:\[(]', line)
        if not bot_match:
            return None
        
        target_bot = bot_match.group(1).lower()
        rest = line[len(bot_match.group(0))-1:].strip(':[]')
        
        # Try to extract affinity score
        affinity = self._extract_affinity(rest)
        
        # Determine interaction style
        interaction_style = self._determine_interaction_style(affinity, rest)
        
        # Clean up description
        description = self._clean_description(rest)
        
        return BotRelationship(
            target_bot=target_bot,
            affinity=affinity,
            description=description,
            interaction_style=interaction_style
        )
    
    def _extract_affinity(self, text: str) -> float:
        """Extract affinity score from text."""
        # Check for explicit score: [0.8] or (0.8)
        score_match = re.search(r'[\[(](0?\.\d+)[\])]', text)
        if score_match:
            return float(score_match.group(1))
        
        # Check for keywords
        text_lower = text.lower()
        if any(word in text_lower for word in ['high', 'trusted', 'close', 'friend']):
            return 0.8
        elif any(word in text_lower for word in ['medium', 'respect', 'colleague']):
            return 0.5
        elif any(word in text_lower for word in ['low', 'distant', 'challenging', 'disagree']):
            return 0.2
        
        return 0.5  # Default
    
    def _determine_interaction_style(self, affinity: float, text: str) -> str:
        """Determine interaction style based on affinity and text."""
        text_lower = text.lower()
        
        if 'challenge' in text_lower or 'disagree' in text_lower:
            return "challenging"
        elif affinity > 0.7:
            return "agreeable"
        elif affinity < 0.4:
            return "distant"
        else:
            return "neutral"
    
    def _clean_description(self, text: str) -> str:
        """Clean up description text."""
        # Remove affinity scores
        text = re.sub(r'\s*[\[(]\d*\.?\d+[\])]\s*', ' ', text)
        # Clean up extra spaces
        text = ' '.join(text.split())
        return text.strip()
```

**3.2 Affinity-Aware Context Builder**
```python
# nanofolks/agent/affinity_context.py

from typing import List, Dict
from nanofolks.identity.relationship_parser import RelationshipParser, BotRelationship

class AffinityContextBuilder:
    """Build context that includes bot relationship dynamics."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.relationship_parser = RelationshipParser()
        self._relationship_cache: Dict[str, List[BotRelationship]] = {}
    
    def build_affinity_context(
        self,
        bot_name: str,
        other_bots: List[str]
    ) -> str:
        """Build relationship context for communal interactions."""
        
        # Load relationships for this bot
        relationships = self._get_bot_relationships(bot_name)
        
        # Filter to only bots present in the room
        relevant_relationships = [
            r for r in relationships 
            if r.target_bot in other_bots
        ]
        
        if not relevant_relationships:
            return ""  # No relationship context
        
        # Build context sections
        sections = []
        sections.append("## Your Relationships with Other Bots")
        sections.append("")
        
        for rel in relevant_relationships:
            # Format based on affinity
            if rel.affinity >= 0.7:
                tone = "You work well together and often agree"
            elif rel.affinity <= 0.4:
                tone = "You sometimes have productive disagreements"
            else:
                tone = "You have a professional working relationship"
            
            sections.append(f"**@{rel.target_bot}** (Affinity: {rel.affinity:.1f})")
            sections.append(f"- {rel.description}")
            sections.append(f"- {tone}")
            sections.append(f"- Interaction style: {rel.interaction_style}")
            sections.append("")
        
        sections.append("## Guidelines for Group Conversation")
        sections.append("- You can reference what other bots say (e.g., 'Coder makes a good point...')")
        sections.append("- Show your relationship dynamics in your responses")
        sections.append("- It's okay to agree or disagree based on your affinity")
        sections.append("- Be natural and conversational")
        sections.append("")
        
        return "\n".join(sections)
    
    def _get_bot_relationships(self, bot_name: str) -> List[BotRelationship]:
        """Get cached or load relationships for a bot."""
        
        if bot_name in self._relationship_cache:
            return self._relationship_cache[bot_name]
        
        # Load IDENTITY.md
        identity_path = self.workspace / "bots" / bot_name / "IDENTITY.md"
        
        if not identity_path.exists():
            return []
        
        try:
            with open(identity_path, 'r') as f:
                content = f.read()
            
            relationships = self.relationship_parser.parse_relationships(content)
            self._relationship_cache[bot_name] = relationships
            return relationships
            
        except Exception as e:
            logger.warning(f"Failed to parse relationships for {bot_name}: {e}")
            return []
```

**3.3 Enhanced Communal Context**
```python
# nanofolks/agent/context.py - Update _build_communal_context

def _build_communal_context(
    self,
    bot_name: str,
    user_message: str,
    room: Room,
    other_bots: List[str]
) -> str:
    """Build context with communal awareness and affinity relationships."""
    
    from nanofolks.models import get_role_card
    from nanofolks.agent.affinity_context import AffinityContextBuilder
    
    # Get base context components
    role_card = get_role_card(bot_name)
    identity = self._load_bot_identity(bot_name)
    
    # Get affinity context
    affinity_builder = AffinityContextBuilder(self.workspace)
    affinity_context = affinity_builder.build_affinity_context(bot_name, other_bots)
    
    # Build full context
    context_parts = [
        f"# You are @{bot_name}",
        f"",
        f"## Your Role",
        role_card.format_for_prompt() if role_card else f"Domain: {bot_name}",
        f"",
        f"## Your Identity",
        identity or f"You are {bot_name}, a specialist bot.",
    ]
    
    # Add affinity context if available
    if affinity_context:
        context_parts.extend(["", affinity_context])
    
    # Add current situation
    context_parts.extend([
        f"",
        f"## Current Situation",
        f"Room: {room.display_name}",
        f"Present bots: {', '.join(other_bots)}",
        f"This is a group conversation with multiple bots.",
        f"",
        f"## User's Message",
        f"{user_message}",
        f"",
        f"## How to Respond",
        f"1. Respond in your unique voice and personality",
        f"2. Be concise (2-3 sentences)",
        f"3. Show your domain expertise",
        f"4. Reference other bots if relevant to the discussion",
    ])
    
    return "\n".join(context_parts)
```

**3.4 Cross-Reference Injection**
```python
# nanofolks/agent/cross_reference.py

class CrossReferenceInjector:
    """Inject cross-references between bot responses."""
    
    def inject_references(
        self,
        responses: List[BotResponse],
        room_team: str
    ) -> List[BotResponse]:
        """Add cross-references where bots mention each other."""
        
        # Only inject references in some cases (not all responses)
        import random
        if random.random() > 0.3:  # 30% chance
            return responses
        
        # Find a response that can reference another
        for i, response in enumerate(responses):
            if len(responses) > 1:
                # Pick another bot to reference
                other_bots = [r for r in responses if r.bot_name != response.bot_name]
                if other_bots:
                    target = random.choice(other_bots)
                    
                    # Add reference
                    reference = self._generate_reference(
                        from_bot=response.bot_name,
                        to_bot=target.bot_name,
                        team=room_team
                    )
                    
                    response.content = f"{reference} {response.content}"
        
        return responses
    
    def _generate_reference(self, from_bot: str, to_bot: str, team: str) -> str:
        """Generate a natural reference."""
        
        # Team-specific references
        references = {
            "pirate": [
                f"Aye, {to_bot} has the right of it. ",
                f"As {to_bot} would say aboard this ship... ",
                f"{to_bot} speaks true. ",
            ],
            "space": [
                f"Commander {to_bot} makes a valid point. ",
                f"As {to_bot} noted in the briefing... ",
                f"{to_bot}'s analysis is correct. ",
            ],
            "corporate": [
                f"I agree with {to_bot}'s assessment. ",
                f"Building on {to_bot}'s point... ",
                f"{to_bot} raises an important consideration. ",
            ],
            "default": [
                f"{to_bot} makes a good point. ",
                f"As {to_bot} mentioned... ",
                f"I agree with {to_bot}. ",
            ]
        }
        
        import random
        refs = references.get(team, references["default"])
        return random.choice(refs)
```

#### Testing Checklist
- [x] Relationships parsed from IDENTITY.md (or inferred from teams)
- [x] Affinity scores extracted correctly
- [x] High affinity bots show agreement
- [x] Low affinity bots show productive tension
- [x] Cross-references added naturally
- [x] Team-specific interaction styles work
- [x] Context size manageable (not too large)

---

## Phase 1 Summary

### Current Status (ALL COMPLETE - Phase 1 DONE!)

1. **Bot-to-Bot DM Rooms** ✅ COMPLETE
   - ✅ Persistent storage in `.nanofolks/dm_rooms/`
   - ✅ `/peek dm-bot_a-bot_b` command  
   - ✅ Auto-created on startup
   - ✅ Integrated with `ask_bot()`

2. **Multi-Bot Response Modes** ✅ COMPLETE
   - ✅ `@all` - All bots respond
   - ✅ `@crew` - Relevant bots respond (keyword-based selection)
   - ✅ Parallel response generation with `MultiBotResponseGenerator`
   - ✅ Formatted output with bot emojis
   - ✅ Integrated into agent loop
   - ✅ Work log tracking for multi-bot responses

3. **Affinity & Relationships** ✅ COMPLETE
   - ✅ Parse IDENTITY.md relationships (RelationshipParser)
   - ✅ Infer relationships from teams (fallback)
   - ✅ Affinity scores (0.0-1.0)
   - ✅ Dynamic context injection (AffinityContextBuilder)
   - ✅ Cross-reference generation (CrossReferenceInjector)
   - ✅ Team-aware interactions

### Files Created/Modified (Phase 1 Complete - All 3 Weeks):
```
nanofolks/
├── models/
│   └── bot_dm_room.py              # ✅ NEW - Week 1
├── bots/
│   ├── dm_room_manager.py          # ✅ NEW - Week 1
│   ├── base.py                     # ✅ MODIFIED - Week 1 (ask_bot logging)
│   └── dispatch.py                 # ✅ MODIFIED - Week 2 (multi-bot modes)
├── agent/
│   ├── multi_bot_generator.py      # ✅ NEW - Week 2 (enhanced Week 3)
│   ├── affinity_context.py          # ✅ NEW - Week 3
│   ├── cross_reference.py           # ✅ NEW - Week 3
│   └── loop.py                     # ✅ MODIFIED - Weeks 2 & 3
├── identity/
│   └── relationship_parser.py      # ✅ NEW - Week 3
└── cli/
    └── commands.py                 # ✅ MODIFIED - Week 1 (peek command)
```

### No Breaking Changes:
- ✅ Existing sessions continue to work
- ✅ Single-bot mode unchanged
- ✅ Backward compatible
- ✅ Config flag not needed

---

## Phase 2: Full Room-Centric Architecture (Weeks 4-10)

### Prerequisites
- Phase 1 complete and stable
- User feedback collected
- Performance validated

### Week 4-5: Session Architecture Migration

#### Objective
Migrate from `channel:chat_id` to `room:{id}` session keys while maintaining backward compatibility.

#### Implementation

**4.1 Dual-Mode Session Manager**
```python
# nanofolks/session/manager.py

class SessionManager:
    """Session manager supporting both legacy and room-centric modes."""
    
    def __init__(self, workspace: Path, config: Config):
        self.workspace = workspace
        self.config = config
        self.use_room_centric = config.use_room_centric
        
        # Separate storage directories
        self.legacy_dir = workspace / ".nanofolks" / "sessions"
        self.room_dir = workspace / ".nanofolks" / "room_sessions"
        
        self.room_dir.mkdir(parents=True, exist_ok=True)
    
    def get_session(self, key: str) -> Session:
        """Get session by key (handles both modes)."""
        
        if self.use_room_centric or key.startswith("room:"):
            # Room-centric mode
            return self._get_room_session(key)
        else:
            # Legacy mode
            return self._get_legacy_session(key)
    
    def _get_room_session(self, room_key: str) -> Session:
        """Get or create room-based session."""
        
        # Extract room_id from key (e.g., "room:general" -> "general")
        room_id = room_key.replace("room:", "")
        
        session_path = self.room_dir / f"room_{room_id}.jsonl"
        
        if session_path.exists():
            return self._load_session(session_path)
        
        # Create new room session
        return Session(
            key=room_key,
            messages=[],
            created_at=datetime.now()
        )
    
    def migrate_workspace(self) -> MigrationReport:
        """Migrate all legacy sessions to room-centric."""
        
        report = MigrationReport()
        
        for legacy_file in self.legacy_dir.glob("*.jsonl"):
            try:
                # Parse legacy filename: telegram_123456.jsonl
                parts = legacy_file.stem.split('_', 1)
                if len(parts) != 2:
                    continue
                
                channel, chat_id = parts
                
                # Determine room mapping
                room_id = self._map_channel_to_room(channel, chat_id)
                
                # Load legacy session
                legacy_session = self._load_session(legacy_file)
                
                # Create room session
                room_session = Session(
                    key=f"room:{room_id}",
                    messages=legacy_session.messages,
                    created_at=legacy_session.created_at,
                    metadata={
                        "migrated_from": str(legacy_file),
                        "original_channel": channel,
                        "original_chat_id": chat_id
                    }
                )
                
                # Save room session
                self._save_session(
                    self.room_dir / f"room_{room_id}.jsonl",
                    room_session
                )
                
                report.successful += 1
                
            except Exception as e:
                report.failed += 1
                report.errors.append(f"{legacy_file}: {e}")
        
        return report
```

**4.2 Migration CLI Command**
```python
# nanofolks/cli/commands.py

@cli.command()
@click.option('--dry-run', is_flag=True, help='Preview migration without changes')
@click.option('--backup', is_flag=True, default=True, help='Create backup of legacy sessions')
@click.pass_obj
async def migrate_sessions(obj, dry_run: bool, backup: bool):
    """Migrate legacy channel-based sessions to room-centric architecture."""
    
    workspace = obj['workspace']
    
    click.echo("🔧 Session Migration Tool")
    click.echo("=" * 50)
    
    # Check for legacy sessions
    legacy_dir = workspace / ".nanofolks" / "sessions"
    if not legacy_dir.exists():
        click.echo("✅ No legacy sessions found. Already room-centric!")
        return
    
    legacy_files = list(legacy_dir.glob("*.jsonl"))
    if not legacy_files:
        click.echo("✅ No legacy sessions to migrate")
        return
    
    click.echo(f"\n📁 Found {len(legacy_files)} legacy session files:")
    for f in legacy_files[:5]:
        click.echo(f"  - {f.name}")
    if len(legacy_files) > 5:
        click.echo(f"  ... and {len(legacy_files) - 5} more")
    
    if dry_run:
        click.echo("\n🔍 DRY RUN - No changes will be made")
        click.echo("Run without --dry-run to perform migration")
        return
    
    # Confirm
    if not click.confirm("\n⚠️  This will migrate all sessions. Continue?"):
        click.echo("❌ Migration cancelled")
        return
    
    # Create backup
    if backup:
        backup_dir = workspace / ".nanofolks" / "sessions_backup"
        shutil.copytree(legacy_dir, backup_dir)
        click.echo(f"✅ Backup created: {backup_dir}")
    
    # Perform migration
    config = load_config()
    manager = SessionManager(workspace, config)
    
    with click.progressbar(length=len(legacy_files), label='Migrating') as bar:
        report = manager.migrate_workspace()
        bar.update(len(legacy_files))
    
    # Report results
    click.echo("\n📊 Migration Results:")
    click.echo(f"  ✅ Successful: {report.successful}")
    click.echo(f"  ❌ Failed: {report.failed}")
    
    if report.errors:
        click.echo("\n⚠️  Errors:")
        for error in report.errors[:5]:
            click.echo(f"    {error}")
    
    # Enable room-centric mode
    if report.failed == 0:
        click.echo("\n🎉 Migration complete!")
        click.echo("Enable room-centric mode in config.yaml:")
        click.echo("  use_room_centric: true")
    else:
        click.echo("\n⚠️  Migration completed with errors")
        click.echo("Review errors above before enabling room-centric mode")
```

#### Testing Checklist
- [ ] Legacy sessions load correctly
- [ ] Room sessions create properly
- [ ] Migration tool works
- [ ] Backup created before migration
- [ ] Config flag toggles between modes
- [ ] Gradual rollout possible per workspace

---

### Week 6-7: Cross-Channel Synchronization

#### Objective
Enable unified conversation history across all channels with message broadcasting.

#### Implementation

**5.1 Channel-to-Room Mapping Config**
```yaml
# config.yaml
channels:
  discord:
    token: "${DISCORD_TOKEN}"
    room_mappings:
      "general": "a7f3k9d2-Weekly-Web-Findings"
      "project-alpha": "k9m2p4q8-Project-Alpha"
      "dm-coder": "dm-leader-coder"
      
  slack:
    token: "${SLACK_TOKEN}"
    room_mappings:
      "C123ABC": "general"
      "C456DEF": "project-alpha"
      
  telegram:
    token: "${TELEGRAM_TOKEN}"
    default_room: "general"
    room_mappings:
      "123456789": "dm-leader"        # Private chat
      "-1009876543210": "general"      # Group chat
      
  cli:
    default_room: "general"
```

**5.2 Cross-Channel Broadcaster**
```python
# nanofolks/channels/broadcaster.py

class CrossChannelBroadcaster:
    """Broadcast messages across all channels linked to a room."""
    
    def __init__(self, config: Config):
        self.config = config
        self.channel_adapters = {}  # platform -> adapter
    
    def register_adapter(self, platform: str, adapter: ChannelAdapter):
        """Register a channel adapter."""
        self.channel_adapters[platform] = adapter
    
    async def broadcast_to_room(
        self,
        room_id: str,
        message: Message,
        exclude_channel: Optional[str] = None
    ):
        """Broadcast message to all channels linked to room."""
        
        # Get linked channels
        linked = self._get_linked_channels(room_id)
        
        for channel_info in linked:
            platform = channel_info['platform']
            channel_id = channel_info['channel_id']
            
            # Skip the source channel
            if exclude_channel and channel_id == exclude_channel:
                continue
            
            # Get adapter
            adapter = self.channel_adapters.get(platform)
            if not adapter:
                continue
            
            # Send message
            try:
                await adapter.send_message(channel_id, message)
            except Exception as e:
                logger.error(f"Failed to broadcast to {platform}:{channel_id}: {e}")
    
    async def handle_incoming_message(
        self,
        platform: str,
        channel_id: str,
        message: Message
    ):
        """Handle message from any channel."""
        
        # Map to room
        room_id = self._get_room_for_channel(platform, channel_id)
        
        if not room_id:
            logger.warning(f"No room mapping for {platform}:{channel_id}")
            return
        
        # Store in room session
        await self._store_in_room(room_id, message)
        
        # Process message (invoke bots, etc.)
        response = await self._process_room_message(room_id, message)
        
        if response:
            # Broadcast response to all linked channels
            await self.broadcast_to_room(
                room_id,
                response,
                exclude_channel=channel_id  # Don't echo back to source
            )
    
    def _get_linked_channels(self, room_id: str) -> List[dict]:
        """Get all channels linked to a room."""
        linked = []
        
        for platform, mappings in self.config.channels.items():
            room_mappings = mappings.get('room_mappings', {})
            for channel_id, mapped_room in room_mappings.items():
                if mapped_room == room_id:
                    linked.append({
                        'platform': platform,
                        'channel_id': channel_id
                    })
        
        return linked
```

**5.3 Unified Message Format**
```python
# nanofolks/models/unified_message.py

@dataclass
class UnifiedMessage:
    """Message format that works across all channels."""
    
    id: str
    timestamp: datetime
    room_id: str
    
    # Content
    role: str  # "user", "assistant", "system"
    content: str
    
    # Source tracking
    source_channel: str  # "discord", "slack", "telegram", "cli"
    source_channel_id: str  # Platform-specific ID
    sender_id: str  # User ID on that platform
    sender_name: str  # Display name
    
    # Cross-platform metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Multi-bot specific
    bot_responses: List[dict] = field(default_factory=list)  # If multi-bot mode
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "room_id": self.room_id,
            "role": self.role,
            "content": self.content,
            "source_channel": self.source_channel,
            "source_channel_id": self.source_channel_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "metadata": self.metadata,
            "bot_responses": self.bot_responses
        }
```

#### Testing Checklist
- [ ] Message from Telegram appears in Discord
- [ ] Message from Discord appears in CLI
- [ ] All channels show same conversation
- [ ] Proper source attribution
- [ ] No infinite loops
- [ ] Handles channel disconnections

---

### Week 8-9: Advanced Room Features

#### Objective
Implement TASK rooms, archiving, and lifecycle management.

#### Implementation

**6.1 TASK Room Type**
```python
# nanofolks/models/room.py - Add TASK type

class RoomType(Enum):
    OPEN = "open"
    PROJECT = "project"
    DIRECT = "direct"
    COORDINATION = "coordination"
    TASK = "task"  # NEW

@dataclass
class TaskRoom(Room):
    """Temporary room for specific tasks with auto-archive."""
    
    type: RoomType = RoomType.TASK
    
    # Task-specific fields
    task_id: str
    parent_room_id: str  # Link back to project/open room
    assigned_bots: List[str]
    deadline: Optional[datetime] = None
    status: str = "active"  # "active", "completed", "archived"
    
    # Auto-archive settings
    auto_archive: bool = True
    archive_on_complete: bool = True
    archive_after_days: int = 7
    
    def mark_complete(self, summary: str):
        """Mark task as complete and prepare for archiving."""
        self.status = "completed"
        self.completed_at = datetime.now()
        self.completion_summary = summary
        
        # Post summary to parent room
        self._notify_parent_room(summary)
        
        # Schedule archiving
        if self.archive_on_complete:
            self._schedule_archive()
    
    def _schedule_archive(self):
        """Schedule room for archiving after delay."""
        from nanofolks.scheduler import schedule_task
        
        archive_date = datetime.now() + timedelta(days=self.archive_after_days)
        schedule_task(
            task_id=f"archive_{self.room_id}",
            run_at=archive_date,
            action=self.archive
        )
```

**6.2 Room Lifecycle Manager**
```python
# nanofolks/bots/room_lifecycle_manager.py

class RoomLifecycleManager:
    """Manages room creation, archiving, and deletion."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.room_manager = RoomManager(workspace)
        self.archived_dir = workspace / ".nanofolks" / "archived_rooms"
        self.archived_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_task_room(
        self,
        name: str,
        parent_room_id: str,
        assigned_bots: List[str],
        deadline: Optional[datetime] = None
    ) -> TaskRoom:
        """Create a new task room."""
        
        import uuid
        short_id = self._generate_short_id()
        room_id = f"{short_id}-{name.replace(' ', '-')}"
        
        room = TaskRoom(
            room_id=room_id,
            display_name=name,
            type=RoomType.TASK,
            participants=assigned_bots,
            task_id=str(uuid.uuid4()),
            parent_room_id=parent_room_id,
            assigned_bots=assigned_bots,
            deadline=deadline,
            created_at=datetime.now()
        )
        
        # Save room
        self.room_manager.save_room(room)
        
        # Notify parent room
        await self._notify_room_created(room, parent_room_id)
        
        return room
    
    async def archive_room(self, room_id: str):
        """Archive a room (move to archive, keep searchable)."""
        
        room = self.room_manager.get_room(room_id)
        if not room:
            return
        
        # Move session file to archive
        session_file = self.workspace / ".nanofolks" / "room_sessions" / f"room_{room_id}.jsonl"
        archive_file = self.archived_dir / f"room_{room_id}.jsonl"
        
        if session_file.exists():
            shutil.move(session_file, archive_file)
        
        # Update room status
        room.is_archived = True
        room.archived_at = datetime.now()
        self.room_manager.save_room(room)
        
        logger.info(f"Archived room: {room_id}")
    
    async def restore_room(self, room_id: str) -> Optional[Room]:
        """Restore an archived room."""
        
        # Move session file back
        archive_file = self.archived_dir / f"room_{room_id}.jsonl"
        session_file = self.workspace / ".nanofolks" / "room_sessions" / f"room_{room_id}.jsonl"
        
        if archive_file.exists():
            shutil.move(archive_file, session_file)
        
        # Update room
        room = self.room_manager.get_room(room_id)
        if room:
            room.is_archived = False
            room.archived_at = None
            self.room_manager.save_room(room)
        
        return room
    
    def search_archived_rooms(self, query: str) -> List[Room]:
        """Search through archived rooms."""
        
        results = []
        for archive_file in self.archived_dir.glob("room_*.jsonl"):
            # Load and search
            room_id = archive_file.stem.replace("room_", "")
            
            # Simple search in content
            with open(archive_file, 'r') as f:
                content = f.read()
                if query.lower() in content.lower():
                    room = self.room_manager.get_room(room_id)
                    if room:
                        results.append(room)
        
        return results
```

**6.3 CLI Commands for Room Management**
```python
# nanofolks/cli/commands.py

@cli.group()
def room():
    """Room management commands."""
    pass

@room.command('create')
@click.argument('name')
@click.option('--type', 'room_type', default='open',
              type=click.Choice(['open', 'project', 'task']))
@click.option('--bots', '-b', multiple=True, help='Bots to include')
@click.option('--deadline', help='Deadline (for project/task rooms)')
@click.pass_obj
async def room_create(obj, name: str, room_type: str, bots: tuple, deadline: str):
    """Create a new room."""
    
    workspace = obj['workspace']
    room_manager = RoomManager(workspace)
    lifecycle_manager = RoomLifecycleManager(workspace)
    
    if room_type == 'task':
        room = await lifecycle_manager.create_task_room(
            name=name,
            parent_room_id="general",  # Default
            assigned_bots=list(bots) if bots else ["leader"],
            deadline=parse_date(deadline) if deadline else None
        )
    else:
        room = room_manager.create_room(
            name=name,
            room_type=RoomType(room_type),
            participants=list(bots) if bots else ["leader"]
        )
    
    click.echo(f"✅ Created room: {room.display_name}")
    click.echo(f"   Room ID: {room.room_id}")
    click.echo(f"   Type: {room_type}")
    click.echo(f"   Bots: {', '.join(room.participants)}")

@room.command('archive')
@click.argument('room_id')
@click.pass_obj
async def room_archive(obj, room_id: str):
    """Archive a room."""
    
    workspace = obj['workspace']
    lifecycle_manager = RoomLifecycleManager(workspace)
    
    await lifecycle_manager.archive_room(room_id)
    click.echo(f"📦 Archived room: {room_id}")

@room.command('list')
@click.option('--archived', is_flag=True, help='Show archived rooms')
@click.option('--all', 'show_all', is_flag=True, help='Show all rooms including archived')
@click.pass_obj
def room_list(obj, archived: bool, show_all: bool):
    """List rooms."""
    
    workspace = obj['workspace']
    room_manager = RoomManager(workspace)
    
    if archived or show_all:
        lifecycle_manager = RoomLifecycleManager(workspace)
        rooms = room_manager.list_all_rooms(include_archived=True)
    else:
        rooms = room_manager.list_active_rooms()
    
    click.echo("\n📋 Rooms:")
    click.echo("-" * 60)
    
    for room in rooms:
        status = "📦" if getattr(room, 'is_archived', False) else "✅"
        click.echo(f"{status} {room.display_name}")
        click.echo(f"   ID: {room.room_id}")
        click.echo(f"   Type: {room.type.value}")
        click.echo(f"   Bots: {', '.join(room.participants)}")
        click.echo()

@room.command('search')
@click.argument('query')
@click.option('--archived', is_flag=True, help='Search archived rooms')
@click.pass_obj
def room_search(obj, query: str, archived: bool):
    """Search room content."""
    
    workspace = obj['workspace']
    
    if archived:
        lifecycle_manager = RoomLifecycleManager(workspace)
        rooms = lifecycle_manager.search_archived_rooms(query)
        click.echo(f"\n🔍 Found {len(rooms)} archived rooms matching '{query}':")
    else:
        room_manager = RoomManager(workspace)
        rooms = room_manager.search_rooms(query)
        click.echo(f"\n🔍 Found {len(rooms)} rooms matching '{query}':")
    
    for room in rooms:
        click.echo(f"  - {room.display_name} ({room.room_id})")
```

#### Testing Checklist
- [ ] Task rooms auto-create on delegation
- [ ] Task completion triggers archiving
- [ ] Parent room receives summary
- [ ] Archived rooms searchable
- [ ] Rooms restorable from archive
- [ ] Room lifecycle events logged

---

### Week 10: Integration & Polish

#### Objective
Integrate all components, optimize performance, and finalize documentation.

#### Tasks

**7.1 Integration Testing**
- End-to-end tests for cross-channel flow
- Performance tests for multi-bot responses
- Load testing for concurrent rooms
- Migration testing with real data

**7.2 Performance Optimization**
- Cache relationship parsing
- Optimize message broadcasting
- Lazy loading for room history
- Connection pooling for channels

**7.3 Documentation**
- Update README with new features
- Migration guide for existing users
- API documentation for room system
- Best practices guide

**7.4 Deployment Strategy**
```python
# Gradual rollout
ROLLOUT_STAGES = [
    {
        "stage": 1,
        "description": "Beta testing with select users",
        "features": ["dm_rooms", "multi_bot"],
        "channels": ["cli"]
    },
    {
        "stage": 2,
        "description": "CLI and Discord rollout",
        "features": ["dm_rooms", "multi_bot", "affinity"],
        "channels": ["cli", "discord"]
    },
    {
        "stage": 3,
        "description": "Full channel support",
        "features": ["all"],
        "channels": ["all"]
    },
    {
        "stage": 4,
        "description": "Room-centric migration",
        "features": ["room_centric"],
        "channels": ["all"]
    }
]
```

#### Final Deliverables
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Migration guide published
- [ ] Rollout plan ready

---

## GSD Template Integration for Phase 2

For Phase 2 execution and planning, we can leverage additional GSD templates:

### 1. Roadmap Template (roadmap.md)

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/roadmap.md

**How to adapt for Task Rooms:**

```markdown
# Roadmap: [Project Name]

## Phases

- [ ] **Phase 1: [Name]** - [One-line description]
- [ ] **Phase 2: [Name]** - [One-line description]

## Phase Details

### Phase 1: [Name]
**Goal**: [What this phase delivers]
**Success Criteria**:
  1. [Observable behavior from user perspective]
  2. [Observable behavior from user perspective]
**Plans**:
- [ ] 01-01: [Brief description]
- [ ] 01-02: [Brief description]
```

**Usage in nanofolks:** Use for TASK rooms that span multiple phases, with progress tracking.

### 2. Phase Prompt Template (phase-prompt.md)

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/phase-prompt.md

**Adopt wave-based parallel execution:**

```yaml
---
phase: XX-name
plan: NN
type: execute
wave: N                     # Execution wave (1, 2, 3...)
depends_on: []              # Plan IDs this plan requires
files_modified: []          # Files this plan modifies
autonomous: true            # false if has checkpoints
---

<objective>
[What this plan accomplishes]
</objective>

<tasks>
<task type="auto">
  <name>Task 1: [Action-oriented name]</name>
  <files>path/to/file.ext</files>
  <action>[Specific implementation]</action>
  <verify>[Command or check]</verify>
  <done>[Measurable acceptance criteria]</done>
</task>
</tasks>
```

**Key patterns to adopt:**
- **Wave execution:** Pre-computed dependency order (wave 1, 2, 3...)
- **Autonomy flag:** Control whether execution needs user checkpoints
- **Vertical slices:** Group by feature, not by layer

### 3. Verification Report Template (verification-report.md)

**Source:** https://github.com/gsd-build/get-shit-done/blob/main/get-shit-done/templates/verification-report.md

For the Room Lifecycle phase, use for automated verification of completed tasks:

```markdown
# Verification Report: [Task/Room Name]

## Verification Summary
- Status: [PASS/FAIL]
- Verified at: [timestamp]

## Checks Performed

### [Check 1]
- Expected: [what should be true]
- Actual: [what was found]
- Status: ✅/❌

### [Check 2]
- Expected: [what should be true]
- Actual: [what was found]
- Status: ✅/❌

## Issues Found
[None if all pass, otherwise list issues]
```

### Integration Points

| GSD Feature | Where to Use | Phase 2 Week |
|-------------|--------------|--------------|
| Roadmap template | TASK room planning | Week 8-9 |
| Wave execution | Bot delegation | Week 8-9 |
| Verification reports | Room completion | Week 9 |

---

## Phase 2 Summary

### Deliverables by End of Week 10:

1. **Session Architecture**
   - ✅ Room-based session keys
   - ✅ Dual-mode session manager
   - ✅ Migration tool
   - ✅ Gradual rollout support

2. **Cross-Channel Sync**
   - ✅ Unified message format
   - ✅ Message broadcasting
   - ✅ Channel-to-room mapping
   - ✅ Real-time synchronization

3. **Advanced Rooms**
   - ✅ TASK room type
   - ✅ Auto-archive lifecycle
   - ✅ Room restoration
   - ✅ Archive search

4. **Integration**
   - ✅ End-to-end testing
   - ✅ Performance optimization
   - ✅ Complete documentation
   - ✅ Deployment ready

---

## Combined Timeline

```
Week 1  │ Phase 1: DM Rooms
Week 2  │ Phase 1: Multi-Bot Responses
Week 3  │ Phase 1: Affinity & Relationships
        │ 
Week 4  │ Phase 2: Session Migration
Week 5  │ Phase 2: Migration Tool & Testing
Week 6  │ Phase 2: Cross-Channel Sync
Week 7  │ Phase 2: Channel Adapters
Week 8  │ Phase 2: Task Rooms
Week 9  │ Phase 2: Room Lifecycle
Week 10 │ Phase 2: Integration & Polish
```

---

## Risk Mitigation

### Phase 1 Risks (Low)
| Risk | Mitigation |
|------|-----------|
| DM rooms fill disk | Auto-cleanup after 30 days |
| Multi-bot too slow | Parallel generation + timeout |
| Affinity context too large | Limit relationships included |

### Phase 2 Risks (Medium)
| Risk | Mitigation |
|------|-----------|
| Migration fails | Backup + rollback capability |
| Cross-channel sync conflicts | Timestamp-based ordering |
| Breaking changes | Config flag for gradual rollout |
| Performance degradation | Caching + lazy loading |

---

## Success Metrics

### Phase 1 Success
- DM rooms created for all bot pairs ✅
- `/peek` command functional ✅
- `@all` triggers multi-bot responses ✅
- User feedback positive ✅

### Phase 2 Success
- Sessions migrated without data loss ✅
- Cross-channel sync working ✅
- All channels unified ✅
- Performance < 100ms per message ✅

---

## Conclusion

This two-phase approach delivers:

**Immediate Value (3 weeks):**
- Transparent bot communication
- Communal multi-bot experience
- No breaking changes

**Long-term Architecture (7 weeks):**
- True room-centric design
- Cross-platform unification
- Scalable foundation

**The hybrid approach is the smart path forward!** 🚀
