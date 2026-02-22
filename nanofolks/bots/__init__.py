"""Bot system for multi-agent orchestration."""

from .base import SpecialistBot

# Import check modules to ensure registration
from .checks import (
    auditor_checks,
    coder_checks,
    coordinator_checks,
    creative_checks,
    researcher_checks,
    social_checks,
)
from .definitions import (
    BUILTIN_ROLES,
    BotCapabilities,
    BotRegistry,
    RoleCard,
    RoleCardDomain,
    get_bot_registry,
    get_role_card,
    is_valid_bot,
    list_available_bots,
    list_bots,
)

# Heartbeat configurations and checks
from .heartbeat_configs import (
    AUDITOR_CONFIG,
    CODER_CONFIG,
    COORDINATOR_CONFIG,
    CREATIVE_CONFIG,
    DEFAULT_CONFIGS,
    RESEARCHER_CONFIG,
    SOCIAL_CONFIG,
    get_all_heartbeat_configs,
    get_bot_heartbeat_config,
    load_config_from_file,
    merge_config,
    save_heartbeat_config,
)
from .implementations import (
    AuditorBot,
    BotLeader,
    CoderBot,
    CreativeBot,
    ResearcherBot,
    SocialBot,
)
from .room_manager import RoomManager, get_room_manager

__all__ = [
    # Base classes
    "SpecialistBot",
    # Room management
    "RoomManager",
    "get_room_manager",
    # Role definitions
    "RoleCard",
    "RoleCardDomain",
    "BotCapabilities",
    "BUILTIN_ROLES",
    "get_role_card",
    "list_bots",
    "is_valid_bot",
    "BotRegistry",
    "get_bot_registry",
    "list_available_bots",
    # Bot implementations
    "BotLeader",
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
