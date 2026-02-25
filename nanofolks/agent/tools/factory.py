"""Factory for creating bot-specific tool registries.

This module provides utilities to create tool registries for specialist bots
with appropriate permissions based on their SOUL.md/AGENTS.md configuration.
"""

from pathlib import Path
from typing import Any, Optional

from nanofolks.agent.tools import ToolRegistry
from nanofolks.agent.tools.permissions import (
    filter_registry,
    get_permissions_from_agents,
    get_permissions_from_soul,
    merge_permissions,
)
from nanofolks.config.schema import ExecToolConfig


def create_bot_registry(
    workspace: Path,
    bot_name: str,
    provider: Optional[Any] = None,
    brave_api_key: Optional[str] = None,
    web_config: Optional[Any] = None,
    browser_config: Optional[Any] = None,
    exec_config: Optional[ExecToolConfig] = None,
    restrict_to_workspace: bool = False,
    base_registry: Optional[ToolRegistry] = None,
) -> ToolRegistry:
    """Create a tool registry for a specialist bot.

    This function:
    1. Loads tool permissions from bot's SOUL.md/AGENTS.md
    2. Creates a base tool registry with standard tools
    3. Filters tools based on permissions

    Args:
        workspace: Path to workspace
        bot_name: Name of the bot
        provider: LLM provider (for message tool)
        brave_api_key: API key for web search
        exec_config: Execution config for shell tool
        restrict_to_workspace: Whether to restrict file ops to workspace
        base_registry: Optional pre-created registry to filter

    Returns:
        Filtered ToolRegistry for the bot
    """
    # Get permissions
    soul_perms = get_permissions_from_soul(bot_name, workspace)
    agents_perms = get_permissions_from_agents(bot_name, workspace)
    permissions = merge_permissions(soul_perms, agents_perms)

    # If no special permissions, create default registry
    if not permissions.allowed_tools and not permissions.denied_tools:
        if base_registry:
            return base_registry
        return create_default_registry(
            workspace=workspace,
            provider=provider,
            brave_api_key=brave_api_key,
            web_config=web_config,
            browser_config=browser_config,
            exec_config=exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

    # Create base registry and filter
    base = base_registry or create_default_registry(
        workspace=workspace,
        provider=provider,
        brave_api_key=brave_api_key,
        web_config=web_config,
        browser_config=browser_config,
        exec_config=exec_config,
        restrict_to_workspace=restrict_to_workspace,
    )

    return filter_registry(base, permissions)


def create_default_registry(
    workspace: Path,
    provider: Optional[Any] = None,
    brave_api_key: Optional[str] = None,
    web_config: Optional[Any] = None,
    browser_config: Optional[Any] = None,
    exec_config: Optional[ExecToolConfig] = None,
    restrict_to_workspace: bool = False,
    evolutionary: bool = False,
    allowed_paths: Optional[list[str]] = None,
    protected_paths: Optional[list[str]] = None,
) -> ToolRegistry:
    """Create a default tool registry with all standard tools.

    Args:
        workspace: Path to workspace
        provider: LLM provider (for message tool)
        brave_api_key: API key for web search
        exec_config: Execution config for shell tool
        restrict_to_workspace: Whether to restrict file ops to workspace
        evolutionary: Whether evolutionary mode is enabled
        allowed_paths: Allowed paths for evolutionary mode
        protected_paths: Protected paths for evolutionary mode

    Returns:
        ToolRegistry with default tools
    """
    registry = ToolRegistry()

    # Import tools
    from nanofolks.agent.tools.filesystem import (
        EditFileTool,
        ListDirTool,
        ReadFileTool,
        WriteFileTool,
    )
    from nanofolks.agent.tools.shell import ExecTool
    from nanofolks.agent.tools.room_tasks import RoomTaskTool
    from nanofolks.agent.tools.web import WebFetchTool, WebSearchTool
    from nanofolks.agent.tools.browser import AgentBrowserTool

    # File tools
    allowed_dir = workspace if restrict_to_workspace else None

    if evolutionary and allowed_paths:
        allowed_dirs = [Path(p).expanduser().resolve() for p in allowed_paths]
        protected_dirs = [Path(p).expanduser().resolve() for p in (protected_paths or [])]

        registry.register(ReadFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
        registry.register(WriteFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
        registry.register(EditFileTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))
        registry.register(ListDirTool(allowed_paths=allowed_dirs, protected_paths=protected_dirs))

        registry.register(ExecTool(
            working_dir=str(workspace),
            timeout=exec_config.timeout if exec_config else 60,
            allowed_paths=allowed_paths,
        ))
    else:
        registry.register(ReadFileTool(allowed_dir=allowed_dir))
        registry.register(WriteFileTool(allowed_dir=allowed_dir))
        registry.register(EditFileTool(allowed_dir=allowed_dir))
        registry.register(ListDirTool(allowed_dir=allowed_dir))

        registry.register(ExecTool(
            working_dir=str(workspace),
            timeout=exec_config.timeout if exec_config else 60,
            restrict_to_workspace=restrict_to_workspace,
        ))

    # Web tools
    if brave_api_key:
        registry.register(WebSearchTool(api_key=brave_api_key))
    registry.register(WebFetchTool(
        scrapling_enabled=bool(getattr(web_config, "scrapling_enabled", False)),
        scrapling_min_chars=int(getattr(web_config, "scrapling_min_chars", 800)),
        scrapling_mode=str(getattr(web_config, "scrapling_mode", "auto")),
    ))

    if getattr(browser_config, "enabled", False):
        registry.register(AgentBrowserTool(
            binary=getattr(browser_config, "binary", "agent-browser"),
            allowlist=getattr(browser_config, "allowlist", []),
        ))

    # Room task tool (task ownership & handoffs)
    registry.register(RoomTaskTool())

    # Message tool (if provider/bus available)
    if provider:
        # We'll handle this differently - message tool needs bus
        pass

    # Invoke tool (for invoking other bots)
    # Note: invoker will be set later

    return registry


def get_tool_definitions_for_bot(
    workspace: Path,
    bot_name: str,
    base_definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Get filtered tool definitions for a bot based on permissions.

    Args:
        workspace: Path to workspace
        bot_name: Name of the bot
        base_definitions: Full list of tool definitions

    Returns:
        Filtered list of tool definitions
    """
    soul_perms = get_permissions_from_soul(bot_name, workspace)
    agents_perms = get_permissions_from_agents(bot_name, workspace)
    permissions = merge_permissions(soul_perms, agents_perms)

    if not permissions.allowed_tools and not permissions.denied_tools:
        return base_definitions

    filtered = []
    for tool_def in base_definitions:
        tool_name = tool_def.get("function", {}).get("name", "")
        if permissions.is_allowed(tool_name):
            # Apply custom description if present
            custom_desc = permissions.get_custom_description(tool_name)
            if custom_desc:
                tool_def = {
                    "type": "function",
                    "function": {
                        **tool_def.get("function", {}),
                        "description": custom_desc,
                    }
                }
            filtered.append(tool_def)

    return filtered
