"""Concrete bot implementations."""

from nanobot.bots.base import SpecialistBot
from nanobot.models.room import Room
from nanobot.models import get_role_card


class NanobotLeader(SpecialistBot):
    """nanobot - The Coordinator/Companion.

    Your personalized companion that coordinates the team.
    """

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize nanobot leader.

        Args:
            bus: InterBotBus for communication with team
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
            theme_manager: Optional theme manager for applying themed display names
            custom_name: Optional custom display name (overrides theme)
        """
        super().__init__(get_role_card("nanobot"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.authority_level = "high"
        self.can_create_workspaces = True
        self.can_recruit_bots = True

        # Auto-initialize heartbeat with coordinator-specific config (30min interval)
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import COORDINATOR_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=COORDINATOR_CONFIG, workspace=workspace, tool_registry=tool_registry)

    async def process_message(self, message: str, workspace: Room) -> str:
        """Process a message as the coordinator."""
        # TODO: Integrate with LLM
        return f"nanobot: I received your message in {workspace.id}"

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

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize researcher bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
            theme_manager: Optional theme manager for applying themed display names
            custom_name: Optional custom display name (overrides theme)
        """
        super().__init__(get_role_card("researcher"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.add_expertise("data_analysis")
        self.add_expertise("web_research")
        
        # Auto-initialize heartbeat with researcher-specific config
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import RESEARCHER_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=RESEARCHER_CONFIG, workspace=workspace, tool_registry=tool_registry)

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

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize coder bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
            theme_manager: Optional theme manager for applying themed display names
            custom_name: Optional custom display name (overrides theme)
        """
        super().__init__(get_role_card("coder"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.add_expertise("python")
        self.add_expertise("testing")
        self.add_expertise("refactoring")

        # Auto-initialize heartbeat with coder-specific config
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import CODER_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=CODER_CONFIG, workspace=workspace, tool_registry=tool_registry)

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

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize social bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
        """
        super().__init__(get_role_card("social"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.add_expertise("community_management")
        self.add_expertise("social_media")

        # Auto-initialize heartbeat with social-specific config
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import SOCIAL_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=SOCIAL_CONFIG, workspace=workspace, tool_registry=tool_registry)

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

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize creative bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
        """
        super().__init__(get_role_card("creative"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.add_expertise("visual_design")
        self.add_expertise("content_creation")

        # Auto-initialize heartbeat with creative-specific config
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import CREATIVE_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=CREATIVE_CONFIG, workspace=workspace, tool_registry=tool_registry)

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

    def __init__(self, bus=None, workspace_id=None, workspace=None, auto_init_heartbeat: bool = True, theme_manager=None, custom_name=None):
        """Initialize auditor bot.

        Args:
            bus: InterBotBus for communication with coordinator
            workspace_id: Room context ID
            workspace: Path to workspace (for HEARTBEAT.md)
            auto_init_heartbeat: Whether to auto-initialize heartbeat on creation
        """
        super().__init__(get_role_card("auditor"), bus, workspace_id, theme_manager=theme_manager, custom_name=custom_name)
        self.add_expertise("quality_assurance")
        self.add_expertise("compliance")

        # Auto-initialize heartbeat with auditor-specific config
        if auto_init_heartbeat:
            from nanobot.bots.heartbeat_configs import AUDITOR_CONFIG
            tool_registry = self._create_tool_registry(workspace) if workspace else None
            self.initialize_heartbeat(config=AUDITOR_CONFIG, workspace=workspace, tool_registry=tool_registry)

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
