"""Team manager for applying and switching teams using template-based discovery."""

from typing import Optional, Dict, List

from nanofolks.templates import (
    discover_teams,
    get_team,
    list_teams,
    get_bot_team_profile,
    get_all_bot_team_profiles,
)


class TeamManager:
    """Manage team selection and application using template-based discovery."""

    def __init__(self, default_team: str = "pirate_crew"):
        """Initialize team manager.

        Args:
            default_team: Default team name (pirate_crew, rock_band, swat_team, feral_clowder, executive_suite, space_crew)
        """
        self.current_team: Optional[str] = default_team
        self._team_data: Optional[Dict] = None

        # Load the default team
        self._load_team(default_team)

    def _load_team(self, team_name: str) -> bool:
        """Load team data from templates.

        Args:
            team_name: Name of the team to load

        Returns:
            True if team loaded successfully, False otherwise
        """
        team_data = get_team(team_name)
        if team_data:
            self._team_data = team_data
            self.current_team = team_name
            return True
        return False

    def list_teams(self) -> List[Dict]:
        """Get list of available teams.

        Returns:
            List of team dictionaries with name, display_name, description, emoji
        """
        return list_teams()

    def select_team(self, team_name: str) -> Optional[Dict]:
        """Select a team.

        Args:
            team_name: Team name (pirate_crew, rock_band, etc.)

        Returns:
            Selected team data or None if not found
        """
        if self._load_team(team_name):
            return self._team_data
        return None

    def get_current_team(self) -> Optional[Dict]:
        """Get currently active team.

        Returns:
            Current team data or None
        """
        return self._team_data

    def get_current_team_name(self) -> Optional[str]:
        """Get name of currently active team.

        Returns:
            Team name or None
        """
        return self.current_team

    def get_bot_team_profile(self, bot_role: str) -> Dict:
        """Get team profile for a specific bot in current team.

        Args:
            bot_role: Role identifier (leader, researcher, coder, social, creative, auditor)

        Returns:
            Dictionary with bot team profile info (bot_title, bot_name, personality, greeting, voice, emoji)
        """
        if not self.current_team:
            return {}

        return get_bot_team_profile(bot_role, self.current_team) or {}

    def get_all_bot_team_profiles(self) -> Dict[str, Dict]:
        """Get team profiles for all bots in current team.

        Returns:
            Dictionary mapping bot roles to their team profiles
        """
        if not self.current_team:
            return {}

        return get_all_bot_team_profiles(self.current_team)

    def to_dict(self) -> Dict:
        """Convert current team to dictionary.

        Returns:
            Team dictionary representation
        """
        if self._team_data:
            return {
                "name": self._team_data["name"],
                "description": self._team_data["description"],
                "bots": {
                    bot_name: bot_data.to_dict() if hasattr(bot_data, 'to_dict') else bot_data
                    for bot_name, bot_data in self._team_data.get("bots", {}).items()
                }
            }
        return {}
