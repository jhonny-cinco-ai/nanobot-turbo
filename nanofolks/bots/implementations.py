"""Concrete bot implementations."""

from nanofolks.bots.base import SpecialistBot
from nanofolks.models import get_role_card
from nanofolks.models.room import Room


class BotLeader(SpecialistBot):
    """nanofolks Leader - The Coordinator/Companion.

    Your personalized companion that coordinates the team.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize nanofolks leader.

        Args:
            bus: InterBotBus for communication with team
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
            team_manager: Optional team manager for applying team-styled display names
            custom_name: Optional custom display name (overrides team style)
        """
        super().__init__(get_role_card("leader"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.authority_level = "high"
        self.can_create_workspaces = True
        self.can_recruit_bots = True

        # Auto-initialize crew routines with coordinator-specific config (30min interval)
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import COORDINATOR_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=COORDINATOR_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process a message as the coordinator."""
        # TODO: Integrate with LLM
        return f"nanofolks: I received your message in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute coordination tasks."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
        }


class ResearcherBot(SpecialistBot):
    """@researcher - The Navigator/Scout.

    Deep analysis and knowledge synthesis specialist.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize researcher bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
            team_manager: Optional team manager for applying team-styled display names
            custom_name: Optional custom display name (overrides team style)
        """
        super().__init__(get_role_card("researcher"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.add_expertise("data_analysis")
        self.add_expertise("web_research")

        # Auto-initialize crew routines with researcher-specific config
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import RESEARCHER_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=RESEARCHER_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process research request."""
        # TODO: Integrate with LLM
        return f"researcher: Analyzing request in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute research task."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
            "result": None,
        }


class CoderBot(SpecialistBot):
    """@coder - The Gunner/Tech.

    Code implementation and technical solutions.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize coder bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
            team_manager: Optional team manager for applying team-styled display names
            custom_name: Optional custom display name (overrides team style)
        """
        super().__init__(get_role_card("coder"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.add_expertise("python")
        self.add_expertise("testing")
        self.add_expertise("refactoring")

        # Auto-initialize crew routines with coder-specific config
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import CODER_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=CODER_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process code request."""
        # TODO: Integrate with LLM
        return f"coder: Ready to implement in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute code task."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
            "code": None,
        }


class SocialBot(SpecialistBot):
    """@social - The Lookout/Manager.

    Community engagement and social media specialist.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize social bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
        """
        super().__init__(get_role_card("social"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.add_expertise("community_management")
        self.add_expertise("social_media")

        # Auto-initialize crew routines with social-specific config
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import SOCIAL_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=SOCIAL_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process community request."""
        # TODO: Integrate with LLM
        return f"social: Engaging community in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute social task."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
            "content": None,
        }


class CreativeBot(SpecialistBot):
    """@creative - The Artist/Designer.

    Design and content creation specialist.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize creative bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
        """
        super().__init__(get_role_card("creative"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.add_expertise("visual_design")
        self.add_expertise("content_creation")

        # Auto-initialize crew routines with creative-specific config
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import CREATIVE_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=CREATIVE_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process creative request."""
        # TODO: Integrate with LLM
        return f"creative: Creating content in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute creative task."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
            "assets": [],
        }


class AuditorBot(SpecialistBot):
    """@auditor - The Quartermaster/Medic.

    Quality review and compliance specialist.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_crew_routines: bool = True, team_manager=None, custom_name=None):
        """Initialize auditor bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for CREW_ROUTINES.md)
            auto_init_crew_routines: Whether to auto-initialize crew routines on creation
        """
        super().__init__(get_role_card("auditor"), bus, workspace_id, team_manager=team_manager, custom_name=custom_name)
        self.add_expertise("quality_assurance")
        self.add_expertise("compliance")

        # Auto-initialize crew routines with auditor-specific config
        if auto_init_crew_routines:
            from nanofolks.bots.crew_routines_configs import AUDITOR_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_crew_routines(config=AUDITOR_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process audit request."""
        # TODO: Integrate with LLM
        return f"auditor: Reviewing work in {workspace.id}"

    async def execute_task(self, task: str, workspace: Room) -> dict:
        """Execute audit task."""
        return {
            "status": "pending",
            "task": task,
            "workspace": workspace.id,
            "executor": self.name,
            "findings": [],
        }
