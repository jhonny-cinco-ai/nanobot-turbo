"""Agent-browser tool wrapper for authenticated web actions."""

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

from nanofolks.agent.tools.base import Tool


WRITE_ACTIONS = {
    "click",
    "dblclick",
    "focus",
    "type",
    "fill",
    "press",
    "keyboard_type",
}


class AgentBrowserTool(Tool):
    """Run agent-browser for interactive web tasks (opt-in)."""

    name = "browser_action"
    description = (
        "Use agent-browser for interactive web tasks (login/posting). "
        "Requires explicit user confirmation for write actions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "open",
                    "snapshot",
                    "click",
                    "dblclick",
                    "focus",
                    "type",
                    "fill",
                    "press",
                    "keyboard_type",
                    "get_text",
                    "get_html",
                    "get_value",
                    "get_attr",
                    "screenshot",
                    "close",
                ],
            },
            "room_id": {"type": "string", "description": "Current room id"},
            "url": {"type": "string", "description": "URL for open"},
            "selector": {"type": "string", "description": "CSS selector or @ref from snapshot"},
            "text": {"type": "string", "description": "Text for type/fill/keyboard_type"},
            "key": {"type": "string", "description": "Key name for press"},
            "attr": {"type": "string", "description": "Attribute name for get_attr"},
            "confirm": {"type": "boolean", "description": "User explicitly confirmed action"},
            "note": {"type": "string", "description": "User confirmation note (what they approved)"},
            "full": {"type": "boolean", "description": "Full page screenshot"},
            "new_tab": {"type": "boolean", "description": "Open click in new tab"},
        },
        "required": ["action", "room_id"],
    }

    def __init__(self, binary: str = "agent-browser", allowlist: list[str] | None = None):
        self.binary = binary
        self.allowlist = allowlist or []

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action")
        room_id = kwargs.get("room_id")

        if not room_id:
            return "Error: room_id is required for browser session isolation"

        if self._requires_confirmation(action):
            if not kwargs.get("confirm"):
                return (
                    "Confirmation required. Ask the user to confirm this browser action, "
                    "then re-run with confirm=true."
                )

        url = kwargs.get("url")
        if url and not self._is_allowed(url):
            return f"Error: domain not allowed for browser automation: {url}"

        cmd = self._build_command(action, kwargs)
        if not cmd:
            return "Error: invalid parameters for browser action"

        session_name = f"room:{room_id}"
        cmd = [self.binary, "--session", session_name] + cmd

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
        except FileNotFoundError:
            return f"Error: '{self.binary}' not found. Install agent-browser first."
        except Exception as e:
            return f"Error: failed to run agent-browser: {e}"

        output = (stdout or b"").decode("utf-8", errors="replace").strip()
        err = (stderr or b"").decode("utf-8", errors="replace").strip()

        payload = {
            "action": action,
            "session": session_name,
            "exit_code": proc.returncode,
            "output": output,
            "error": err,
        }

        return json.dumps(payload)

    def _requires_confirmation(self, action: str | None) -> bool:
        return action in WRITE_ACTIONS

    def _is_allowed(self, url: str) -> bool:
        if not self.allowlist:
            return True
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            return False
        host = host.lower()
        for domain in self.allowlist:
            d = domain.lower().lstrip(".")
            if host == d or host.endswith(f".{d}"):
                return True
        return False

    def _build_command(self, action: str, params: dict[str, Any]) -> list[str] | None:
        selector = params.get("selector")
        text = params.get("text")
        key = params.get("key")
        url = params.get("url")
        attr = params.get("attr")
        full = params.get("full")
        new_tab = params.get("new_tab")

        if action == "open":
            if not url:
                return None
            return ["open", url]
        if action == "snapshot":
            return ["snapshot"]
        if action in {"click", "dblclick", "focus"}:
            if not selector:
                return None
            cmd = [action, selector]
            if new_tab:
                cmd.append("--new-tab")
            return cmd
        if action in {"type", "fill"}:
            if not selector or text is None:
                return None
            return [action, selector, text]
        if action == "press":
            if not key:
                return None
            return ["press", key]
        if action == "keyboard_type":
            if text is None:
                return None
            return ["keyboard", "type", text]
        if action == "get_text":
            if not selector:
                return None
            return ["get", "text", selector]
        if action == "get_html":
            if not selector:
                return None
            return ["get", "html", selector]
        if action == "get_value":
            if not selector:
                return None
            return ["get", "value", selector]
        if action == "get_attr":
            if not selector or not attr:
                return None
            return ["get", "attr", selector, attr]
        if action == "screenshot":
            cmd = ["screenshot"]
            if full:
                cmd.append("--full")
            return cmd
        if action == "close":
            return ["close"]
        return None
