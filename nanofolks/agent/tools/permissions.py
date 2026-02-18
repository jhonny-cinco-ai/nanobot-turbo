"""Tool permissions system for per-bot tool access control.

This module provides:
- Parsing tool permissions from markdown (SOUL.md, AGENTS.md, or custom)
- Filtering tool registries based on permissions
- Creating restricted tool sets per bot
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from nanofolks.agent.tools.registry import ToolRegistry

if TYPE_CHECKING:
    pass
from typing import Optional


@dataclass
class ToolPermissions:
    """Represents tool permissions for a bot."""

    allowed_tools: set[str] = field(default_factory=set)
    denied_tools: set[str] = field(default_factory=set)
    custom_tools: dict[str, str] = field(default_factory=dict)

    def is_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed.

        If allowed_tools is empty, all tools are allowed except denied ones.
        If allowed_tools is not empty, only those tools are allowed.
        """
        if tool_name in self.denied_tools:
            return False

        if self.allowed_tools:
            return tool_name in self.allowed_tools

        return True

    def get_custom_description(self, tool_name: str) -> Optional[str]:
        """Get custom description for a tool if defined."""
        return self.custom_tools.get(tool_name)


def parse_tool_permissions(markdown: str) -> ToolPermissions:
    """Parse tool permissions from markdown content.

    Supports:
    - ## Allowed Tools / ## Allowed
    - ## Denied Tools / ## Denied
    - ## Custom Tools / ## Custom

    Format:
    ## Allowed Tools
    - read_file
    - write_file
    - web_search

    ## Denied Tools
    - exec
    - spawn

    ## Custom Tools
    - shopify_api: Custom Shopify integration
    - custom_api: My custom tool description

    Args:
        markdown: Raw markdown content from SOUL.md or AGENTS.md

    Returns:
        ToolPermissions object with parsed rules
    """
    permissions = ToolPermissions()

    if not markdown:
        return permissions

    lines = markdown.split('\n')
    current_section = None

    for line in lines:
        line = line.strip()

        # Detect section headers
        section_match = re.match(r'^#{1,3}\s*(Allowed|Denied|Custom)\s*(Tools?)?', line, re.IGNORECASE)
        if section_match:
            section_type = section_match.group(1).lower()
            if 'allow' in section_type:
                current_section = 'allowed'
            elif 'deny' in section_type or 'ban' in section_type:
                current_section = 'denied'
            elif 'custom' in section_type:
                current_section = 'custom'
            continue

        # Parse list items
        if line.startswith(('- ', '* ', '+ ')) and current_section:
            content = line[2:].strip()

            # Check for custom description (tool: description)
            if ':' in content and current_section == 'custom':
                tool_name, description = content.split(':', 1)
                permissions.custom_tools[tool_name.strip()] = description.strip()
            elif content:
                if current_section == 'allowed':
                    permissions.allowed_tools.add(content)
                elif current_section == 'denied':
                    permissions.denied_tools.add(content)

    return permissions


def filter_registry(
    registry: "ToolRegistry",
    permissions: ToolPermissions
) -> "ToolRegistry":
    """Filter a tool registry based on permissions.

    Creates a new registry containing only allowed tools.

    Args:
        registry: Source tool registry
        permissions: Permissions to apply

    Returns:
        New ToolRegistry with filtered tools
    """
    from nanofolks.agent.tools import ToolRegistry

    filtered = ToolRegistry()

    for tool in registry._tools.values():
        if permissions.is_allowed(tool.name):
            filtered.register(tool)

    return filtered


def get_permissions_from_soul(bot_name: str, workspace: "Path") -> ToolPermissions:
    """Get tool permissions from bot's SOUL.md file.

    Args:
        bot_name: Name of the bot
        workspace: Path to workspace

    Returns:
        ToolPermissions parsed from SOUL.md
    """

    # Check bot-specific SOUL
    bot_soul = workspace / "bots" / bot_name / "SOUL.md"
    if bot_soul.exists():
        content = bot_soul.read_text(encoding="utf-8")
        return parse_tool_permissions(content)

    return ToolPermissions()


def get_permissions_from_agents(bot_name: str, workspace: "Path") -> ToolPermissions:
    """Get tool permissions from bot's AGENTS.md file.

    Args:
        bot_name: Name of the bot
        workspace: Path to workspace

    Returns:
        ToolPermissions parsed from AGENTS.md
    """

    # Check bot-specific AGENTS.md
    bot_agents = workspace / "bots" / bot_name / "AGENTS.md"
    if bot_agents.exists():
        content = bot_agents.read_text(encoding="utf-8")
        return parse_tool_permissions(content)

    return ToolPermissions()


def merge_permissions(*permissions: ToolPermissions) -> ToolPermissions:
    """Merge multiple ToolPermissions together.

    Later permissions override earlier ones.

    Args:
        *permissions: Variable number of ToolPermissions

    Returns:
        Merged ToolPermissions
    """
    merged = ToolPermissions()

    for perms in permissions:
        # Union of allowed tools (empty means all)
        if perms.allowed_tools:
            if merged.allowed_tools:
                merged.allowed_tools |= perms.allowed_tools
            else:
                merged.allowed_tools = perms.allowed_tools.copy()

        # Union of denied tools
        merged.denied_tools |= perms.denied_tools

        # Later custom tools override earlier
        merged.custom_tools.update(perms.custom_tools)

    return merged
