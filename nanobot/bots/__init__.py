"""Bot system for multi-agent orchestration."""

from .base import SpecialistBot
from .definitions import (
    RoleCard,
    RoleCardDomain,
    BotCapabilities,
    BUILTIN_BOTS,
    get_role_card,
    list_bots,
    is_valid_bot,
    BotRegistry,
    get_bot_registry,
    list_available_bots,
)
from .room_manager import RoomManager, get_room_manager
from .workspace_manager import WorkspaceManager, get_workspace_manager  # Legacy aliases
from .implementations import (
    NanobotLeader,
    ResearcherBot,
    CoderBot,
    SocialBot,
    CreativeBot,
    AuditorBot,
)

# Heartbeat configurations and checks
from .heartbeat_configs import (
    RESEARCHER_CONFIG,
    CODER_CONFIG,
    SOCIAL_CONFIG,
    AUDITOR_CONFIG,
    CREATIVE_CONFIG,
    COORDINATOR_CONFIG,
    DEFAULT_CONFIGS,
    get_bot_heartbeat_config,
    get_all_heartbeat_configs,
    load_config_from_file,
    save_heartbeat_config,
    merge_config,
)

# Import check modules to ensure registration
from .checks import (
    researcher_checks,
    coder_checks,
    social_checks,
    auditor_checks,
    creative_checks,
    coordinator_checks,
)

__all__ = [
    # Base classes
    "SpecialistBot",
    # Room management (new)
    "RoomManager",
    "get_room_manager",
    # Room management (legacy aliases)
    "WorkspaceManager",
    "get_workspace_manager",
    # Role definitions
    "RoleCard",
    "RoleCardDomain",
    "BotCapabilities",
    "BUILTIN_BOTS",
    "get_role_card",
    "list_bots",
    "is_valid_bot",
    "BotRegistry",
    "get_bot_registry",
    "list_available_bots",
    # Bot implementations
    "NanobotLeader",
    "ResearcherBot",
    "CoderBot",
    "SocialBot",
    "CreativeBot",
    "AuditorBot",
    # Heartbeat configs
    "RESEARCHER_CONFIG",
    "CODER_CONFIG",
    "SOCIAL_CONFIG",
    "AUDITOR_CONFIG",
    "CREATIVE_CONFIG",
    "COORDINATOR_CONFIG",
    "DEFAULT_CONFIGS",
    # Config functions
    "get_bot_heartbeat_config",
    "get_all_heartbeat_configs",
    "load_config_from_file",
    "save_heartbeat_config",
    "merge_config",
    # Check modules (imported for side effects)
    "researcher_checks",
    "coder_checks",
    "social_checks",
    "auditor_checks",
    "creative_checks",
    "coordinator_checks",
]
