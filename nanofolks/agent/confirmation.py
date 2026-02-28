"""Confirmation flow for actions suggested by external web content."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConfirmationType(Enum):
    """Types of confirmations needed."""
    FILE_MODIFICATION = "file_modification"
    COMMAND_EXECUTION = "command_execution"
    INFORMATION_DISCLOSURE = "information_disclosure"
    EXTERNAL_ACTION = "external_action"


@dataclass
class ActionSuggestion:
    """Represents an action suggested from external content."""
    action_type: ConfirmationType
    description: str
    source_url: str | None
    content_id: str | None
    details: dict[str, Any]


class ConfirmationDetector:
    """
    Detects when LLM responses suggest actions that came from web content.
    
    This runs after LLM response to detect if the response wants to:
    - Modify files
    - Execute commands  
    - Disclose sensitive information
    - Take other actions that might have been influenced by web content
    """
    
    # Patterns that indicate the LLM is about to take an action
    ACTION_PATTERNS = {
        # File modifications
        ConfirmationType.FILE_MODIFICATION: [
            (r"(?:I'll|I will|I am going to|Let me)\s+(?:create|write|make|add|update|modify|edit)\s+(?:a |the )?(?:file|config|directory)", "file_creation"),
            (r"(?:I'll|I will|I am going to|Let me)\s+(?:create|write|make|add|update|modify|edit)\s+", "file_modification"),
            (r"(?:Here's|This is|The).*config(?:uration)?.*:", "config_provided"),
            (r"```\s*(?:yaml|json|toml|ini|conf|config)", "config_code"),
        ],
        
        # Command execution
        ConfirmationType.COMMAND_EXECUTION: [
            (r"(?:I'll|I will|I am going to|Let me)\s+run\s+(?:the |this )?(?:command|script)", "command_run"),
            (r"(?:Here's|This is|The).*(?:command|script):", "command_provided"),
            (r"```\s*(?:bash|sh|shell|zsh|powershell|cmd)", "shell_code"),
            (r"(?:npm|pip|apt|brew|docker|cargo)\s+(?:install|run|build|start)", "package_command"),
        ],
        
        # Information disclosure
        ConfirmationType.INFORMATION_DISCLOSURE: [
            (r"(?:I'll|I will|I am going to|Let me)\s+(?:give|show|tell|reveal|share)\s+(?:you|them|us)", "info_disclose"),
            (r"(?:Here's|This is|The).*(?:API|key|token|secret|password|credential):", "secret_provided"),
        ],
    }
    
    # Web content indicators in context
    WEB_CONTENT_INDICATORS = [
        r"fetch_[a-f0-9]+",
        r"web_fetch",
        r"web_search",
        r"content from https?://",
        r"according to the (?:article|blog|doc|tutorial|guide)",
        r"(?:I found|found) (?:this|that|some) (?:information|content|tutorial|guide)",
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile patterns for performance."""
        self._action_patterns: dict[ConfirmationType, list[tuple[re.Pattern, str]]] = {}
        for conf_type, patterns in self.ACTION_PATTERNS.items():
            self._action_patterns[conf_type] = [
                (re.compile(p, re.IGNORECASE), name) 
                for p, name in patterns
            ]
        
        self._web_indicators = [
            re.compile(p, re.IGNORECASE) 
            for p in self.WEB_CONTENT_INDICATORS
        ]
    
    def needs_confirmation(
        self,
        response: str,
        tool_calls: list[dict] | None = None,
        message_history: list[dict] | None = None,
    ) -> ActionSuggestion | None:
        """
        Check if the response suggests actions that need confirmation.
        
        Args:
            response: The LLM's text response
            tool_calls: Any tool calls the LLM made
            message_history: Recent message history to check for web content
            
        Returns:
            ActionSuggestion if confirmation needed, None otherwise
        """
        # Check if web content was referenced recently
        has_web_content = self._has_web_content_context(message_history or [])
        
        if not has_web_content:
            return None
        
        # Check for action patterns in response
        for conf_type, patterns in self._action_patterns.items():
            for pattern, name in patterns:
                if pattern.search(response):
                    return ActionSuggestion(
                        action_type=conf_type,
                        description=f"Action detected: {name}",
                        source_url=None,
                        content_id=self._extract_content_id(message_history or []),
                        details={"pattern": name, "matched_text": pattern.pattern}
                    )
        
        # Also check tool calls
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                if tool_name in ("write_file", "edit_file", "exec", "bash"):
                    return ActionSuggestion(
                        action_type=ConfirmationType.COMMAND_EXECUTION 
                        if tool_name == "exec" else ConfirmationType.FILE_MODIFICATION,
                        description=f"Tool call: {tool_name}",
                        source_url=None,
                        content_id=self._extract_content_id(message_history or []),
                        details={"tool": tool_name}
                    )
        
        return None
    
    def _has_web_content_context(self, history: list[dict]) -> bool:
        """Check if recent history contains web content."""
        for msg in history[-5:]:  # Check last 5 messages
            content = msg.get("content", "")
            if isinstance(content, str):
                for indicator in self._web_indicators:
                    if indicator.search(content):
                        return True
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text", "")
                        for indicator in self._web_indicators:
                            if indicator.search(text):
                                return True
        return False
    
    def _extract_content_id(self, history: list[dict]) -> str | None:
        """Extract content ID from recent web content."""
        for msg in history[-5:]:
            content = msg.get("content", "")
            if isinstance(content, str):
                match = re.search(r"fetch_[a-f0-9]+", content)
                if match:
                    return match.group()
        return None


def create_confirmation_prompt(suggestion: ActionSuggestion) -> str:
    """Create a user confirmation prompt based on the action type."""
    
    prompts = {
        ConfirmationType.FILE_MODIFICATION: f"""I noticed you're about to create or modify a file based on content from the web.

{suggestion.description}

This could be a configuration file, code, or other file. Should I proceed with creating this file?

Would you like to:
- Review the content first
- Proceed with creating the file
- Skip this step""",
        
        ConfirmationType.COMMAND_EXECUTION: f"""I notice you're suggesting to run a command that appears to come from web content.

{suggestion.description}

Running commands from external sources can be risky. Should I proceed?

Would you like to:
- Review the command before execution
- Execute the command as suggested
- Skip this step""",
        
        ConfirmationType.INFORMATION_DISCLOSURE: f"""I notice you're about to share information that may have come from web content.

{suggestion.description}

Should I proceed with sharing this information?

Would you like to:
- Share the information
- Review it first
- Skip this step""",
        
        ConfirmationType.EXTERNAL_ACTION: f"""I notice you're suggesting an action based on web content.

{suggestion.description}

Should I proceed with this action?

Would you like to:
- Proceed with the action
- Review more details first
- Skip this step""",
    }
    
    return prompts.get(suggestion.action_type, prompts[ConfirmationType.EXTERNAL_ACTION])
