"""Response formatting with progressive disclosure of work logs.

This module handles formatting agent responses with optional work log
transparency, using HTML details tags for collapsible sections.
"""

from typing import Optional

from nanobot.agent.work_log import WorkLog
from nanobot.agent.work_log_manager import WorkLogManager


class ResponseFormatter:
    """Formats responses with progressive disclosure of work logs."""
    
    def __init__(self, work_log_manager: Optional[WorkLogManager] = None):
        """Initialize formatter with optional work log manager."""
        self.work_log_manager = work_log_manager
    
    def format_response(
        self,
        result: str,
        include_log: bool = False,
        log_mode: str = "summary",
        show_summary: bool = True
    ) -> str:
        """Format response with optional work log.
        
        Args:
            result: The main response content
            include_log: Whether to include work log
            log_mode: Format mode for work log (summary, detailed, debug)
            show_summary: Whether to show insight summary before log
            
        Returns:
            Formatted response string
        """
        if not include_log or not self.work_log_manager:
            return result
        
        log = self.work_log_manager.get_last_log()
        if not log:
            return result
        
        # Build response with collapsible work log
        lines = [result]
        lines.append("")
        
        # Add summary if requested
        if show_summary:
            summary = self._extract_summary(log)
            if summary:
                lines.append(summary)
                lines.append("")
        
        # Add collapsible work log
        formatted_log = self.work_log_manager.get_formatted_log(log_mode)
        lines.append(self._create_collapsible_section(formatted_log))
        
        return "\n".join(lines)
    
    def format_response_html(
        self,
        result: str,
        include_log: bool = False,
        log_mode: str = "summary",
        show_summary: bool = True
    ) -> str:
        """Format response as HTML with collapsible work log.
        
        Args:
            result: The main response content
            include_log: Whether to include work log
            log_mode: Format mode for work log
            show_summary: Whether to show insight summary
            
        Returns:
            HTML formatted response string
        """
        if not include_log or not self.work_log_manager:
            return self._escape_html(result)
        
        log = self.work_log_manager.get_last_log()
        if not log:
            return self._escape_html(result)
        
        html_parts = [
            f"<div class='response'>{self._escape_html(result)}</div>"
        ]
        
        # Add summary
        if show_summary:
            summary = self._extract_summary(log)
            if summary:
                html_parts.append(
                    f"<div class='summary'>{self._escape_html(summary)}</div>"
                )
        
        # Add collapsible work log
        formatted_log = self.work_log_manager.get_formatted_log(log_mode)
        html_parts.append(self._create_collapsible_html(formatted_log))
        
        return "\n".join(html_parts)
    
    def _extract_summary(self, log: WorkLog) -> str:
        """Extract key insights from work log.
        
        Args:
            log: The work log to summarize
            
        Returns:
            Summary string with key insights
        """
        lines = ["**How I decided this:**"]
        
        # Count key activities
        decisions = [e for e in log.entries if e.level.value == "decision"]
        tools = [e for e in log.entries if e.tool_name]
        errors = [e for e in log.entries if e.level.value == "error"]
        
        if decisions:
            avg_conf = sum(e.confidence or 0.0 for e in decisions) / len(decisions)
            lines.append(f"- Made {len(decisions)} decisions (avg confidence: {avg_conf:.0%})")
        
        if tools:
            lines.append(f"- Used {len(tools)} tools")
        
        if errors:
            lines.append(f"⚠️ Encountered {len(errors)} issues")
        
        # Show coordinator mode if active
        if any(e.coordinator_mode for e in log.entries):
            lines.append("- Operating in coordinator mode")
        
        # Show escalations
        escalations = [e for e in log.entries if e.escalation]
        if escalations:
            lines.append(f"⚠️ {len(escalations)} issues escalated to user")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _create_collapsible_section(self, content: str) -> str:
        """Create a collapsible markdown section.
        
        Args:
            content: The content to make collapsible
            
        Returns:
            Markdown with collapsible details tag
        """
        return f"""<details>
<summary>🔍 How I decided this (work log)</summary>

```
{content}
```

</details>"""
    
    def _create_collapsible_html(self, content: str) -> str:
        """Create a collapsible HTML section.
        
        Args:
            content: The content to make collapsible
            
        Returns:
            HTML with collapsible details tag
        """
        return f"""<details>
<summary>🔍 How I decided this (work log)</summary>
<pre>{self._escape_html(content)}</pre>
</details>"""
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters.
        
        Args:
            text: Text to escape
            
        Returns:
            HTML-escaped text
        """
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))
    
    def format_interactive_response(
        self,
        result: str,
        show_actions: bool = True
    ) -> str:
        """Format response for interactive CLI with action buttons.
        
        Args:
            result: The main response
            show_actions: Whether to show action suggestions
            
        Returns:
            Formatted response with interactive prompts
        """
        lines = [result]
        
        if show_actions:
            lines.append("")
            lines.append("**What would you like to do?**")
            lines.append("- `nanobot explain` - See how I made this decision")
            lines.append("- `nanobot how \"<query>\"` - Search my reasoning")
            lines.append("- Ask me a follow-up question")
        
        return "\n".join(lines)
