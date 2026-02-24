"""Role parser for extracting role card data from ROLE.md files.

This module parses ROLE.md markdown files and converts them back to RoleCard objects,
enabling users to edit role configuration in visible markdown files.
"""

import re
from pathlib import Path
from typing import List, Optional

from loguru import logger

from nanofolks.models.role_card import BotCapabilities, RoleCard, RoleCardDomain


class RoleParser:
    """Parse ROLE.md files into RoleCard objects."""

    def __init__(self, workspace: Path):
        """Initialize RoleParser.

        Args:
            workspace: Workspace path for loading ROLE.md files
        """
        self.workspace = Path(workspace)

    def parse_role_file(self, bot_name: str) -> Optional[RoleCard]:
        """Parse a ROLE.md file for a bot.

        Args:
            bot_name: Name of the bot

        Returns:
            RoleCard object or None if file doesn't exist or is invalid
        """
        role_path = self.workspace / "bots" / bot_name / "ROLE.md"

        if not role_path.exists():
            return None

        try:
            with open(role_path, 'r', encoding='utf-8') as f:
                content = f.read()

            return self.parse_role_content(content, bot_name)
        except Exception as e:
            logger.warning(f"Failed to parse ROLE.md for {bot_name}: {e}")
            return None

    def parse_role_content(self, content: str, bot_name: str) -> Optional[RoleCard]:
        """Parse ROLE.md content into a RoleCard.

        Args:
            content: ROLE.md content
            bot_name: Name of the bot

        Returns:
            RoleCard object or None if invalid
        """
        try:
            # Extract domain
            domain = self._extract_domain(content)
            domain_desc = self._extract_section(content, "## Domain", "Description:")

            # Extract inputs and outputs
            inputs = self._extract_list_items(content, "## Inputs")
            outputs = self._extract_list_items(content, "## Outputs")

            # Extract definition of done
            definition_of_done = self._extract_list_items(content, "## Definition of Done")

            # Extract hard bans
            hard_bans = self._extract_hard_bans(content)

            # Extract escalation triggers
            escalation_triggers = self._extract_list_items(content, "## Escalation Triggers")

            # Extract metrics/KPIs
            metrics = self._extract_list_items(content, "## Your KPIs")

            # Extract capabilities
            capabilities = self._extract_capabilities(content)

            # Extract version
            version = self._extract_version(content) or "1.0"

            return RoleCard(
                bot_name=bot_name,
                domain=domain,
                domain_description=domain_desc,
                inputs=inputs,
                outputs=outputs,
                definition_of_done=definition_of_done,
                hard_bans=hard_bans,
                escalation_triggers=escalation_triggers,
                metrics=metrics,
                capabilities=capabilities,
                version=version,
            )

        except Exception as e:
            logger.error(f"Failed to parse role content for {bot_name}: {e}")
            return None

    def _extract_domain(self, content: str) -> RoleCardDomain:
        """Extract domain from ROLE.md content."""
        # Try to find domain line
        domain_match = re.search(r'\*\*Primary:\*\*\s*(\w+)', content)
        if domain_match:
            domain_str = domain_match.group(1).upper()
            domain_map = {
                'COORDINATION': RoleCardDomain.COORDINATION,
                'RESEARCH': RoleCardDomain.RESEARCH,
                'DEVELOPMENT': RoleCardDomain.DEVELOPMENT,
                'COMMUNITY': RoleCardDomain.COMMUNITY,
                'DESIGN': RoleCardDomain.DESIGN,
                'QUALITY': RoleCardDomain.QUALITY,
            }
            return domain_map.get(domain_str, RoleCardDomain.COORDINATION)

        return RoleCardDomain.COORDINATION

    def _extract_section(self, content: str, section_header: str, prefix: str = "") -> str:
        """Extract text from a section."""
        pattern = rf'{re.escape(section_header)}.*?\n(.*?)(?=\n## |\n---|$)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            section_text = match.group(1).strip()
            if prefix:
                # Look for specific prefix
                prefix_pattern = rf'{re.escape(prefix)}\s*(.*?)(?=\n\n|\n- |$)'
                prefix_match = re.search(prefix_pattern, section_text)
                if prefix_match:
                    return prefix_match.group(1).strip()
            return section_text

        return ""

    def _extract_list_items(self, content: str, section_header: str) -> List[str]:
        """Extract list items from a section."""
        pattern = rf'{re.escape(section_header)}.*?\n(.*?)(?=\n## |\n---|$)'
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            return []

        section_text = match.group(1)

        # Find all list items (lines starting with - or checkboxes)
        items = []
        for line in section_text.split('\n'):
            line = line.strip()
            # Match - [ ] or - item or just -
            item_match = re.match(r'^[-*]\s*(?:\[.)?\s*(.+)$', line)
            if item_match:
                item = item_match.group(1).strip()
                if item:
                    items.append(item)

        return items

    def _extract_hard_bans(self, content: str) -> List[str]:
        """Extract hard bans from content."""
        bans = []

        # Find the HARD BANS section
        pattern = r'## HARD BANS.*?\n(.*?)(?=\n## |\n---|$)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            section_text = match.group(1)
            # Find lines starting with 🚫
            for line in section_text.split('\n'):
                if '🚫' in line:
                    # Extract text after emoji
                    ban_text = line.split('🚫', 1)[1].strip()
                    if ban_text:
                        bans.append(ban_text)

        return bans

    def _extract_capabilities(self, content: str) -> BotCapabilities:
        """Extract capabilities from content."""
        caps = BotCapabilities()

        # Find the Capabilities section
        pattern = r'## Capabilities.*?\n(.*?)(?=\n## |\n---|$)'
        match = re.search(pattern, content, re.DOTALL)

        if match:
            section_text = match.group(1)

            # Parse each capability line
            caps.can_invoke_bots = self._parse_capability(section_text, "Can invoke other bots")
            caps.can_do_routines = self._parse_capability(section_text, "Can do routines")
            caps.can_access_web = self._parse_capability(section_text, "Can access web")
            caps.can_exec_commands = self._parse_capability(section_text, "Can execute commands")
            caps.can_send_messages = self._parse_capability(section_text, "Can send messages")

            # Extract max concurrent tasks
            max_tasks_match = re.search(r'Max concurrent tasks:\s*\*\*(\d+)\*\*', section_text)
            if max_tasks_match:
                caps.max_concurrent_tasks = int(max_tasks_match.group(1))

        return caps

    def _parse_capability(self, text: str, capability_name: str) -> bool:
        """Parse a yes/no capability."""
        pattern = rf'{re.escape(capability_name)}:\s*\*\*(\w+)\*\*'
        match = re.search(pattern, text)
        if match:
            return match.group(1).upper() == "YES"
        return False

    def _extract_version(self, content: str) -> Optional[str]:
        """Extract version from content."""
        version_match = re.search(r'Version:\s*(\d+\.\d+)', content)
        if version_match:
            return version_match.group(1)
        return None
