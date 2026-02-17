"""Affinity context builder for injecting relationship dynamics into prompts.

This module builds context that includes bot relationship information,
enabling bots to reference each other and show personality-based interactions.
"""

import random
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from nanofolks.identity.relationship_parser import RelationshipParser, BotRelationship


class AffinityContextBuilder:
    """Build context that includes bot relationship dynamics."""
    
    def __init__(self, workspace: Path):
        """Initialize AffinityContextBuilder.
        
        Args:
            workspace: Workspace path
        """
        self.workspace = Path(workspace)
        self.relationship_parser = RelationshipParser(workspace)
    
    def build_affinity_context(
        self,
        bot_name: str,
        other_bots: List[str],
    ) -> str:
        """Build relationship context for communal interactions.
        
        Args:
            bot_name: Current bot name
            other_bots: List of other participating bots
            
        Returns:
            Formatted affinity context string
        """
        relationships = self.relationship_parser.get_bot_relationships(bot_name)
        
        relevant_relationships = [
            r for r in relationships 
            if r.target_bot in other_bots
        ]
        
        if not relevant_relationships:
            return ""
        
        sections = []
        sections.append("## Your Relationships with Other Bots")
        sections.append("")
        
        for rel in relevant_relationships:
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
    
    def get_affinity_score(self, bot_a: str, bot_b: str) -> float:
        """Get affinity score between two bots.
        
        Args:
            bot_a: First bot name
            bot_b: Second bot name
            
        Returns:
            Affinity score (0.0 to 1.0)
        """
        relationships = self.relationship_parser.get_bot_relationships(bot_a)
        
        for rel in relationships:
            if rel.target_bot == bot_b:
                return rel.affinity
        
        return 0.5
    
    def should_reference_other_bot(
        self,
        bot_name: str,
        other_bots: List[str],
    ) -> bool:
        """Determine if this bot should reference another bot.
        
        Args:
            bot_name: Current bot name
            other_bots: List of other participating bots
            
        Returns:
            True if bot should add cross-references
        """
        relationships = self.relationship_parser.get_bot_relationships(bot_name)
        
        high_affinity_count = sum(
            1 for r in relationships 
            if r.target_bot in other_bots and r.affinity >= 0.6
        )
        
        probability = min(high_affinity_count * 0.2, 0.5)
        
        return random.random() < probability
    
    def generate_reference(
        self,
        from_bot: str,
        to_bot: str,
        room_theme: str = "default",
    ) -> Optional[str]:
        """Generate a cross-reference to another bot.
        
        Args:
            from_bot: Bot making the reference
            to_bot: Bot being referenced
            room_theme: Theme for style customization
            
        Returns:
            Reference string or None
        """
        affinity = self.get_affinity_score(from_bot, to_bot)
        
        references = self._get_theme_references(room_theme, affinity)
        
        return random.choice(references) if references else None
    
    def _get_theme_references(self, theme: str, affinity: float) -> List[str]:
        """Get reference templates based on theme and affinity.
        
        Args:
            theme: Room theme
            affinity: Affinity score
            
        Returns:
            List of reference templates
        """
        theme_lower = theme.lower()
        
        if "pirate" in theme_lower or "pirate" in theme_lower:
            refs = [
                f"Arr, @{to_bot} be right about this. ",
                f"As @{to_bot} would say, ",
                f"@{to_bot} speaks true, me hearties. ",
            ]
        elif "rock" in theme_lower or "band" in theme_lower:
            refs = [
                f"@{to_bot} is on the same wavelength. ",
                f"Like @{to_bot} always says, ",
                f" @{to_bot} really gets it. ",
            ]
        elif "space" in theme_lower:
            refs = [
                f"Commander @{to_bot} confirms. ",
                f"As noted in the briefing by @{to_bot}, ",
                f"@{to_bot}'s analysis is correct. ",
            ]
        elif "executive" in theme_lower or "corp" in theme_lower:
            refs = [
                f"I agree with @{to_bot}'s assessment. ",
                f"Building on @{to_bot}'s point... ",
                f"@{to_bot} raises an important consideration. ",
            ]
        else:
            if affinity >= 0.7:
                refs = [
                    f"@{to_bot} makes a great point. ",
                    f"I agree with @{to_bot}. ",
                    f"@{to_bot} is absolutely right. ",
                ]
            elif affinity <= 0.4:
                refs = [
                    f"Though @{to_bot} might see it differently... ",
                    f"@{to_bot} has a valid perspective, even if I disagree. ",
                    f"Despite @{to_bot}'s reservations, ",
                ]
            else:
                refs = [
                    f"@{to_bot} makes a good point. ",
                    f"As @{to_bot} mentioned... ",
                    f"I agree with @{to_bot}. ",
                ]
        
        return refs
