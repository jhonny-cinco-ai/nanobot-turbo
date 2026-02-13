"""Bot system for multi-agent orchestration."""

from .base import SpecialistBot
from .definitions import (
    NANOBOT_ROLE,
    RESEARCHER_ROLE,
    CODER_ROLE,
    SOCIAL_ROLE,
    CREATIVE_ROLE,
    AUDITOR_ROLE,
)
from .implementations import (
    NanobotLeader,
    ResearcherBot,
    CoderBot,
    SocialBot,
    CreativeBot,
    AuditorBot,
)

__all__ = [
    "SpecialistBot",
    "NANOBOT_ROLE",
    "RESEARCHER_ROLE",
    "CODER_ROLE",
    "SOCIAL_ROLE",
    "CREATIVE_ROLE",
    "AUDITOR_ROLE",
    "NanobotLeader",
    "ResearcherBot",
    "CoderBot",
    "SocialBot",
    "CreativeBot",
    "AuditorBot",
]
