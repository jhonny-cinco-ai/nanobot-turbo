"""Cross-reference injector for adding inter-bot references to responses.

This module adds natural references between bots in multi-bot responses,
showing relationship dynamics and creating a more communal feel.
"""

import random
from typing import List, Optional

from nanofolks.agent.multi_bot_generator import BotResponse


class CrossReferenceInjector:
    """Inject cross-references between bot responses."""
    
    def __init__(self, room_theme: str = "default"):
        """Initialize CrossReferenceInjector.
        
        Args:
            room_theme: Theme for style customization
        """
        self.room_theme = room_theme
    
    def inject_references(
        self,
        responses: List[BotResponse],
    ) -> List[BotResponse]:
        """Add cross-references where bots mention each other.
        
        Args:
            responses: List of bot responses
            
        Returns:
            Modified responses with cross-references
        """
        if len(responses) < 2:
            return responses
        
        references_added = 0
        
        for i, response in enumerate(responses):
            if random.random() > 0.4:
                continue
            
            other_responses = [r for r in responses if r.bot_name != response.bot_name]
            if not other_responses:
                continue
            
            target = random.choice(other_responses)
            
            reference = self._generate_reference(
                from_bot=response.bot_name,
                to_bot=target.bot_name,
            )
            
            if reference:
                response.content = f"{reference}{response.content}"
                references_added += 1
        
        return responses
    
    def _generate_reference(
        self,
        from_bot: str,
        to_bot: str,
    ) -> Optional[str]:
        """Generate a natural reference to another bot.
        
        Args:
            from_bot: Bot making the reference
            to_bot: Bot being referenced
            
        Returns:
            Reference string or None
        """
        references = self._get_theme_references()
        
        ref = random.choice(references)
        return ref.format(to_bot=to_bot)
    
    def _get_theme_references(self) -> List[str]:
        """Get reference templates based on room theme.
        
        Returns:
            List of reference format strings
        """
        theme = self.room_theme.lower()
        
        if "pirate" in theme:
            return [
                "Arr, {to_bot} be right about this. ",
                "As {to_bot} would say... ",
                "{to_bot} speaks true, me hearties. ",
            ]
        elif "rock" in theme or "band" in theme:
            return [
                "{to_bot} is totally on the same wavelength. ",
                "Like {to_bot} always says, ",
                " {to_bot} really gets the vibe. ",
            ]
        elif "space" in theme:
            return [
                "Commander {to_bot} confirms this. ",
                "As noted in the briefing by {to_bot}, ",
                "{to_bot}'s analysis is correct. ",
            ]
        elif "executive" in theme or "corp" in theme:
            return [
                "I agree with {to_bot}'s assessment. ",
                "Building on {to_bot}'s point... ",
                "{to_bot} raises an important consideration. ",
            ]
        elif "swat" in theme:
            return [
                "{to_bot} has eyes on this. ",
                "Per {to_bot}'s intel... ",
                "{to_bot} confirms the target. ",
            ]
        else:
            return [
                "{to_bot} makes a good point. ",
                "As {to_bot} mentioned... ",
                "I agree with {to_bot}. ",
            ]
