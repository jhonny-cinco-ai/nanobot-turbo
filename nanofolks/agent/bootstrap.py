"""Workspace bootstrapping and template management."""

from pathlib import Path
from loguru import logger

# Shared templates for workspace root
TEMPLATES = {
    "USER.md": """# User Profile

Information about the user to help personalize interactions.

## Basic Information

- **Name**: (your name)
- **Location**: (your location)
- **Language**: (preferred language)
- **Team Name**: (default from team)

## Preferences

- **Communication Style**: Casual
- **Response Length**: Adaptive based on question
- **Technical Level**: Intermediate

## Work Context

- **Current Focus**: (what you're working on)
- **How We Should Help**: (what you want help with)
- **Tools You Use**: (tools and software)

## Topics of Interest

-
-
-

## Special Instructions

(Any specific instructions for how the bot should behave)

---

*Auto-filled during onboarding.*
""",
    "TOOLS.md": """# Available Tools

This document describes the tools available to nanofolks.

## File Operations

### read_file
Read the contents of a file.

### write_file
Write content to a file (creates parent directories if needed).

### edit_file
Edit a file by replacing specific text.

### list_dir
List contents of a directory.

## Shell Execution

### exec
Execute a shell command and return output.

**Safety Notes:**
- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters

## Web Access

### web_search
Search the web using Brave Search API.

### web_fetch
Fetch and extract main content from a URL.

## Communication

### message
Send a message to the user on chat channels.

## Background Tasks

### invoke
Invoke a specialist bot to handle a task in the background.
```
invoke(bot_name: str, task: str, context: str = None)
```

Use for complex tasks that need specialist expertise. The bot will complete the task and report back.

## Cron Reminders

Use the `exec` tool to create scheduled reminders with `nanofolks routines add`.

---

## Per-Bot Tool Permissions

You can customize which tools each bot has access to by adding tool permissions to their SOUL.md or AGENTS.md files:

```markdown
## Allowed Tools
- read_file
- write_file
- web_search

## Denied Tools
- exec
- spawn

## Custom Tools
- shopify_api: Custom Shopify integration
```

If no permissions are specified, bots get access to all standard tools.
""",
}


def bootstrap_workspace(workspace_path: Path) -> None:
    """Ensure required shared files exist in the workspace root.

    Args:
        workspace_path: Path to the workspace directory.
    """
    if not workspace_path.exists():
        logger.info(f"Creating workspace directory: {workspace_path}")
        workspace_path.mkdir(parents=True, exist_ok=True)

    for filename, content in TEMPLATES.items():
        file_path = workspace_path / filename
        if not file_path.exists():
            logger.info(f"Creating missing workspace template: {filename}")
            try:
                # Ensure no leading whitespace in template lines
                cleaned_content = "\n".join(line.lstrip() for line in content.strip().split("\n"))
                file_path.write_text(cleaned_content, encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to create {filename}: {e}")
