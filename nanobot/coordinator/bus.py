"""Inter-bot message bus for coordination.

Provides centralized message passing and conversation management.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

from nanobot.coordinator.models import BotMessage, ConversationContext, MessageType


class InterBotBus:
    """Central message bus for bot-to-bot communication.
    
    Enables bots to:
    - Send messages to specific bots
    - Broadcast to all bots
    - Track conversations with threading
    - Query message history
    """
    
    def __init__(self, max_message_history: int = 1000):
        """Initialize the message bus.
        
        Args:
            max_message_history: Maximum messages to keep in memory
        """
        self.max_message_history = max_message_history
        
        # Message storage
        self._messages: List[BotMessage] = []
        
        # Conversation tracking
        self._conversations: Dict[str, ConversationContext] = {}
        
        # Inbox for each bot (recipient_id -> messages)
        self._inboxes: Dict[str, List[BotMessage]] = defaultdict(list)
        
        # Bot registrations (bot_id -> info)
        self._registered_bots: Dict[str, Dict] = {}
    
    def register_bot(self, bot_id: str, bot_name: str, domain: str) -> None:
        """Register a bot on the bus.
        
        Args:
            bot_id: Unique bot identifier
            bot_name: Human-readable name
            domain: Bot's domain (research, development, etc.)
        """
        self._registered_bots[bot_id] = {
            "name": bot_name,
            "domain": domain,
            "registered_at": datetime.now(),
            "message_count": 0,
        }
        logger.info(f"Bot registered: {bot_id} ({bot_name})")
    
    def list_bots(self) -> Dict[str, Dict]:
        """Get list of registered bots.
        
        Returns:
            Dictionary of bot_id -> bot_info
        """
        return self._registered_bots.copy()
    
    def send_message(self, message: BotMessage) -> str:
        """Send a message from one bot to another or broadcast.
        
        Args:
            message: The message to send
            
        Returns:
            Message ID
        """
        # Validate sender is registered
        if message.sender_id not in self._registered_bots:
            logger.warning(f"Unregistered bot tried to send message: {message.sender_id}")
        
        # Add to global message log
        self._messages.append(message)
        
        # Enforce history limit
        if len(self._messages) > self.max_message_history:
            self._messages.pop(0)
        
        # Add to conversation
        if message.conversation_id not in self._conversations:
            self._conversations[message.conversation_id] = ConversationContext(
                conversation_id=message.conversation_id,
                initiated_by=message.sender_id,
                subject=message.context.get("subject", ""),
            )
        
        self._conversations[message.conversation_id].add_message(message)
        
        # Route to inbox(es)
        if message.recipient_id == "team":
            # Broadcast to all bots except sender
            for bot_id in self._registered_bots:
                if bot_id != message.sender_id:
                    self._inboxes[bot_id].append(message)
            logger.info(
                f"Broadcast from {message.sender_id}: {message.content[:50]}... "
                f"({len(self._registered_bots)-1} recipients)"
            )
        else:
            # Direct message
            self._inboxes[message.recipient_id].append(message)
            logger.info(
                f"Message from {message.sender_id} to {message.recipient_id}: "
                f"{message.content[:50]}..."
            )
        
        # Update stats (only if registered)
        if message.sender_id in self._registered_bots:
            self._registered_bots[message.sender_id]["message_count"] += 1
        
        return message.id
    
    def get_inbox(self, bot_id: str, unread_only: bool = False) -> List[BotMessage]:
        """Get messages for a bot.
        
        Args:
            bot_id: The bot's ID
            unread_only: If True, only return unread messages
            
        Returns:
            List of messages
        """
        return self._inboxes.get(bot_id, [])
    
    def get_conversation(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> Optional[ConversationContext]:
        """Get a conversation by ID.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum messages to return
            
        Returns:
            Conversation context or None if not found
        """
        if conversation_id not in self._conversations:
            return None
        
        context = self._conversations[conversation_id]
        
        if limit:
            # Return only last N messages
            context.messages = context.messages[-limit:]
        
        return context
    
    def get_conversations_for_bot(
        self,
        bot_id: str,
        limit: int = 10
    ) -> List[ConversationContext]:
        """Get all conversations involving a bot.
        
        Args:
            bot_id: The bot's ID
            limit: Maximum conversations to return
            
        Returns:
            List of conversations
        """
        conversations = [
            ctx for ctx in self._conversations.values()
            if bot_id in ctx.participants or bot_id == ctx.initiated_by
        ]
        
        # Sort by most recent first
        conversations.sort(key=lambda c: c.last_message_at, reverse=True)
        
        return conversations[:limit]
    
    def search_messages(
        self,
        query: str,
        sender_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 50
    ) -> List[BotMessage]:
        """Search messages by content and filters.
        
        Args:
            query: Text to search for
            sender_id: Filter by sender
            message_type: Filter by message type
            limit: Maximum results
            
        Returns:
            List of matching messages
        """
        results = []
        
        for msg in reversed(self._messages):  # Search most recent first
            # Filter by sender
            if sender_id and msg.sender_id != sender_id:
                continue
            
            # Filter by message type
            if message_type and msg.message_type != message_type:
                continue
            
            # Search by content
            if query.lower() in msg.content.lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_conversation_summary(self, conversation_id: str) -> str:
        """Get a human-readable summary of a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Summary text
        """
        context = self.get_conversation(conversation_id)
        if not context:
            return f"Conversation {conversation_id} not found"
        
        lines = [
            f"=== {context.subject} ===",
            f"Initiated by: {context.initiated_by}",
            f"Participants: {', '.join(context.participants)}",
            f"Messages: {len(context.messages)}",
            "",
        ]
        
        for msg in context.messages[-10:]:  # Last 10 messages
            timestamp = msg.timestamp.strftime("%H:%M:%S")
            sender = msg.sender_id[:10]  # Truncate for readability
            msg_type = msg.message_type.value
            content = msg.content[:60]  # Truncate content
            lines.append(f"[{timestamp}] {sender} ({msg_type}): {content}...")
        
        return "\n".join(lines)
    
    def clear_inbox(self, bot_id: str) -> int:
        """Clear all messages in a bot's inbox.
        
        Args:
            bot_id: The bot's ID
            
        Returns:
            Number of messages cleared
        """
        count = len(self._inboxes.get(bot_id, []))
        self._inboxes[bot_id] = []
        return count
    
    def get_statistics(self) -> Dict[str, any]:
        """Get bus statistics.
        
        Returns:
            Dictionary with stats
        """
        total_messages = len(self._messages)
        total_conversations = len(self._conversations)
        total_inbox_messages = sum(len(msgs) for msgs in self._inboxes.values())
        
        # Message type distribution
        msg_type_counts = {}
        for msg in self._messages:
            msg_type = msg.message_type.value
            msg_type_counts[msg_type] = msg_type_counts.get(msg_type, 0) + 1
        
        return {
            "total_messages": total_messages,
            "total_conversations": total_conversations,
            "registered_bots": len(self._registered_bots),
            "pending_inbox_messages": total_inbox_messages,
            "message_types": msg_type_counts,
            "bot_message_counts": {
                bot_id: info["message_count"]
                for bot_id, info in self._registered_bots.items()
            },
        }
