"""Security tool for the agent to scan skills.

This tool allows the agent to validate skills for security issues
before installing or using them.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from nanofolks.agent.tools.base import Tool
from nanofolks.security.skill_scanner import scan_skill


class ScanSkillTool(Tool):
    """
    Tool to scan a skill for security vulnerabilities.

    This tool allows the agent to validate skills before installation,
    ensuring they don't contain malicious code or dangerous operations.

    Usage:
        Agent: "I'll scan this skill before we install it..."
        → Calls scan_skill with the skill path
        → Reports findings to user
    """

    @property
    def name(self) -> str:
        return "scan_skill"

    @property
    def description(self) -> str:
        return (
            "Scan a skill for security vulnerabilities before installation. "
            "Use this tool whenever you're about to install a new skill or "
            "when a user asks you to validate a skill's safety. "
            "This protects against malicious skills that could compromise security."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_path": {
                    "type": "string",
                    "description": "Path to the skill directory or SKILL.md file to scan (e.g., './skills/my-skill' or './skills/my-skill/SKILL.md')"
                },
                "strict_mode": {
                    "type": "boolean",
                    "description": "If true, blocks on medium severity issues as well as critical/high. Use for extra safety.",
                    "default": False
                }
            },
            "required": ["skill_path"]
        }

    async def execute(self, skill_path: str, strict_mode: bool = False, **kwargs) -> str:
        """
        Execute skill security scan.

        Args:
            skill_path: Path to skill directory or file
            strict_mode: Enable strict scanning (blocks on medium severity)

        Returns:
            Formatted security report
        """
        try:
            path = Path(skill_path)

            if not path.exists():
                return f"❌ Error: Skill path not found: {skill_path}"

            logger.info(f"Agent scanning skill for security: {path}")

            # Perform the scan
            report = scan_skill(path, strict=strict_mode)

            # Generate report
            if report.passed:
                result = f"""
✅ **Security Scan Passed**

Skill: {path.name}
Risk Score: {report.total_risk_score}/100
Findings: {len(report.findings)}

The skill appears safe for installation.
"""
                if report.findings:
                    result += "\n⚠️  Minor issues found (informational only):\n"
                    for finding in report.findings:
                        if finding.severity.value in ['medium', 'low']:
                            result += f"\n• [{finding.severity.value.upper()}] {finding.category}:\n"
                            result += f"  {finding.description}\n"

                return result

            else:
                # Security issues found
                result = f"""
🚫 **Security Scan FAILED - Do Not Install!**

Skill: {path.name}
Risk Score: {report.total_risk_score}/100
Critical Issues: {report.critical_count}
High Issues: {report.high_count}

**This skill contains dangerous patterns that could compromise your system.**

**Critical Findings (Blockers):**
"""
                # List critical and high findings first
                for finding in report.findings:
                    if finding.severity.value in ['critical', 'high']:
                        result += f"""
🚫 **{finding.category.replace('_', ' ').title()}**
- Severity: {finding.severity.value.upper()}
- Description: {finding.description}
"""
                        if finding.line_content:
                            result += f"- Code: `{finding.line_content[:80]}`\n"
                        if finding.remediation:
                            result += f"- Why it's dangerous: {finding.remediation}\n"

                # Add medium findings if any
                medium_count = sum(1 for f in report.findings if f.severity.value == 'medium')
                if medium_count > 0:
                    result += f"\n⚠️  Additionally found {medium_count} medium-risk issues.\n"

                result += """
**Recommendation:**
❌ DO NOT install this skill. It contains patterns associated with malware:
- Stealing SSH keys or credentials
- Executing unverified code from the internet
- Disabling security protections
- Installing persistence mechanisms

**If you trust this skill:**
1. Ask the skill developer to remove the dangerous patterns
2. Review the code manually with security expertise
3. Run in an isolated environment (not recommended)
"""

                return result

        except Exception as e:
            logger.error(f"Skill scan failed: {e}")
            return f"❌ Error scanning skill: {str(e)}"


class ValidateSkillSafetyTool(Tool):
    """
    Quick validation tool to check if a skill is safe.

    This is a lighter-weight version that just returns safe/unsafe status
    without detailed reporting. Good for automatic checks.
    """

    @property
    def name(self) -> str:
        return "validate_skill_safety"

    @property
    def description(self) -> str:
        return (
            "Quickly check if a skill is safe to use (returns true/false). "
            "Use this for automatic validation when speed is important. "
            "For detailed security analysis, use the scan_skill tool instead."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_path": {
                    "type": "string",
                    "description": "Path to skill directory or SKILL.md file"
                }
            },
            "required": ["skill_path"]
        }

    async def execute(self, skill_path: str, **kwargs) -> str:
        """Quick safety check."""
        try:
            path = Path(skill_path)

            if not path.exists():
                return "false"

            report = scan_skill(path, strict=False)

            # Just return true/false as string for easy parsing
            if report.passed:
                return f"true (Risk score: {report.total_risk_score}/100)"
            else:
                return f"false (Risk score: {report.total_risk_score}/100 - Critical: {report.critical_count}, High: {report.high_count})"

        except Exception as e:
            logger.error(f"Safety validation failed: {e}")
            return "false (error)"


class SecureRemediateTool(Tool):
    """
    Tool to help users fix security issues in routine files or skills.

    This tool can:
    - Scan files for exposed credentials
    - Store credentials in OS Keyring
    - Update files to use {{symbolic_ref}} instead of actual keys

    Use this when users ask about security warnings or want to secure their files.
    """

    @property
    def name(self) -> str:
        return "secure_remediate"

    @property
    def description(self) -> str:
        return (
            "Fix security issues in routine files or skill files. "
            "This tool scans for exposed API keys/tokens, offers to store them "
            "securely in OS Keyring, and updates files to use {{symbolic_ref}} instead. "
            "Use this when you notice security warnings or users ask to secure their files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to file to scan and remediate (e.g., 'routines/jobs.json', 'skills/my-skill/SKILL.md')"
                },
                "action": {
                    "type": "string",
                    "description": "Action to take: 'scan' (default), 'store_and_fix', or 'show_instructions'",
                    "enum": ["scan", "store_and_fix", "show_instructions"]
                },
                "key_type": {
                    "type": "string",
                    "description": "The type of key to store (e.g., 'github_token', 'openai_api_key'). Required for 'store_and_fix' action."
                },
                "api_key": {
                    "type": "string",
                    "description": "The actual API key to store securely. Required for 'store_and_fix' action."
                }
            },
            "required": ["file_path", "action"]
        }

    async def execute(self, file_path: str = "", action: str = "scan", key_type: str = "", api_key: str = "", **kwargs) -> str:
        """Remediate security issues in a file."""

        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if action == "show_instructions":
            return self._show_instructions()

        if action == "scan":
            return await self._scan_and_report(path)

        if action == "store_and_fix":
            if not key_type or not api_key:
                return "Error: key_type and api_key are required for 'store_and_fix' action"
            return await self._store_and_fix(path, key_type, api_key)

        return "Error: Unknown action. Use 'scan', 'store_and_fix', or 'show_instructions'."

    def _show_instructions(self) -> str:
        return """## How to Secure Your Files

### Option 1: Store Key in OS Keyring
```bash
nanofolks security add <key_type>
# Example: nanofolks security add github_token
```

### Option 2: Use Symbolic References
Instead of:
```
Use token ghp_abc123xyz for GitHub
```

Use:
```
Use token {{github_token}} for GitHub
```

### Available Key Types
- github_token / github_pat
- openai_api_key
- anthropic_api_key
- brave_key
- And more...

### Benefits
- Keys are stored securely in OS Keyring (never in config files)
- LLM only sees {{symbolic_ref}}, never actual keys
- Automatic resolution at tool execution time"""

    async def _scan_and_report(self, path: Path) -> str:
        """Scan file and report found credentials."""
        from nanofolks.security.credential_detector import CredentialDetector

        try:
            content = path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"

        detector = CredentialDetector()
        matches = detector.detect(content)

        if not matches:
            return f"✅ No credentials detected in {path.name}"

        list(set(m.credential_type for m in matches))

        report = [f"⚠️ Found {len(matches)} credential(s) in {path.name}:"]
        for m in matches:
            masked = m.value[:4] + "..." + m.value[-4:] if len(m.value) > 8 else "***"
            report.append(f"  - {m.credential_type}: ...{masked}")

        report.append("")
        report.append("To fix this, I can help you:")
        report.append("1. Store the key(s) in OS Keyring securely")
        report.append("2. Update the file to use {{symbolic_ref}} instead")
        report.append("")
        report.append("Say something like: 'Please secure the keys in this file' and I'll help you fix it.")

        return "\n".join(report)

    async def _store_and_fix(self, path: Path, key_type: str, api_key: str) -> str:
        """Store key in keyring and update file with symbolic ref."""
        from nanofolks.security.secret_manager import get_secret_manager

        try:
            manager = get_secret_manager()
            manager.store_key(key_type, api_key)
        except Exception as e:
            return f"Error storing key in keyring: {e}"

        try:
            content = path.read_text()

            from nanofolks.security.secret_manager import get_secret_manager
            manager = get_secret_manager()
            result = manager.convert_to_symbolic(content, f"remediate:{path.name}")

            path.write_text(result.text)
        except Exception as e:
            return f"Error updating file: {e}"

        return f"""✅ Security issues fixed in {path.name}!

1. ✅ Stored {key_type} in OS Keyring securely
2. ✅ Replaced actual key with {{symbolic_ref}} in {path.name}

The file now uses {{symbolic_ref}} syntax which will be resolved to the actual key only at execution time. The LLM will never see your actual API key."""


def create_security_tools() -> list[Tool]:
    """
    Create all security-related tools for the agent.

    Returns:
        List of security tools
    """
    return [
        ScanSkillTool(),
        ValidateSkillSafetyTool(),
        SecureRemediateTool(),
    ]
