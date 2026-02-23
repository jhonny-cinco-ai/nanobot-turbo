"""Template discovery for scanning and listing available teams."""

from pathlib import Path
from typing import List, Dict, Optional

from nanofolks.templates import SOUL_TEMPLATES_DIR, BOT_NAMES
from nanofolks.templates.parser import get_bot_metadata, parse_team_description


def discover_teams() -> List[str]:
    """Discover all available teams by scanning template directories.
    
    Returns:
        List of team names (directory names in templates/soul/)
    """
    teams = []
    if SOUL_TEMPLATES_DIR.exists():
        for item in SOUL_TEMPLATES_DIR.iterdir():
            if item.is_dir():
                teams.append(item.name)
    return sorted(teams)


def get_team(team_name: str) -> Optional[Dict]:
    """Get team data by parsing template files.
    
    Args:
        team_name: Name of the team (directory name)
        
    Returns:
        Dictionary with team data or None if team not found
    """
    team_dir = SOUL_TEMPLATES_DIR / team_name
    if not team_dir.exists():
        return None
    
    # Get description from leader or first available bot
    description = parse_team_description(team_name)
    
    # Build team data
    team_data = {
        "name": team_name,
        "description": description,
        "bots": {}
    }
    
    # Get metadata for each bot
    for bot_name in BOT_NAMES:
        metadata = get_bot_metadata(bot_name, team_name)
        if metadata:
            team_data["bots"][bot_name] = metadata
    
    return team_data


def list_teams() -> List[Dict]:
    """List all available teams with their metadata.
    
    Returns:
        List of team dictionaries with name, display_name, description, emoji
    """
    teams = []
    
    for team_name in discover_teams():
        team_data = get_team(team_name)
        if team_data:
            # Get emoji from leader bot
            leader_metadata = team_data["bots"].get("leader")
            emoji = leader_metadata.emoji if leader_metadata else "👤"
            
            # Create display name from team name
            display_name = team_name.replace("_", " ").title()
            
            teams.append({
                "name": team_name,
                "display_name": display_name,
                "description": team_data["description"],
                "emoji": emoji
            })
    
    return teams


def get_bot_team_profile(bot_name: str, team_name: str) -> Optional[Dict]:
    """Get team profile for a specific bot in a team.
    
    Args:
        bot_name: Bot role name (leader, researcher, coder, social, creative, auditor)
        team_name: Team name
        
    Returns:
        Dictionary with bot team profile info or None
    """
    metadata = get_bot_metadata(bot_name, team_name)
    if metadata:
        return metadata.to_dict()
    return None


def get_all_bot_team_profiles(team_name: str) -> Dict[str, Dict]:
    """Get team profiles for all bots in a team.
    
    Args:
        team_name: Team name
        
    Returns:
        Dictionary mapping bot names to their team profiles
    """
    all_profiles = {}
    for bot_name in BOT_NAMES:
        profile = get_bot_team_profile(bot_name, team_name)
        if profile:
            all_profiles[bot_name] = profile
    return all_profiles
