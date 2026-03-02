"""Enhanced role card system with 6-layer structure.

Based on the multi-agent architecture pattern, each role card defines:
1. Domain - What the bot owns
2. Inputs/Outputs - What it receives and delivers
3. Definition of Done - When "done" is actually done
4. Hard Bans - What it must never do
5. Escalation - When to stop and ask for help
6. Metrics - KPIs for performance tracking

Role cards complement (not compete with):
- SOUL.md: Voice, tone, speaking style
- IDENTITY.md: Personality, relationships, quirks
- AGENTS.md: Specific task instructions

Storage:
- Default role cards are defined in code (BUILTIN_ROLES)
- User/bot edits are stored in workspace/role_cards/{bot_name}.yaml
- Bots can propose role card updates through the learning system
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from loguru import logger


class RoleCardDomain(Enum):
    """Domain/specialty of a bot."""

    COORDINATION = "coordination"
    RESEARCH = "research"
    DEVELOPMENT = "development"
    COMMUNITY = "community"
    DESIGN = "design"
    QUALITY = "quality"


@dataclass
class BotCapabilities:
    """What features/tools are enabled for a bot."""

    can_invoke_bots: bool = False
    can_do_routines: bool = False
    can_access_web: bool = True
    can_exec_commands: bool = True
    can_send_messages: bool = True
    max_concurrent_tasks: int = 1


@dataclass
class RoleCard:
    """Complete bot role card with 6-layer structure.

    This is the discipline manual + job description + escalation protocol.
    It defines what the bot CAN and CANNOT do, its responsibilities,
    and when to escalate.

    Complementary files:
    - SOUL.md: How the bot speaks (voice, tone, style)
    - IDENTITY.md: Who the bot is (personality, relationships, quirks)
    - AGENTS.md: Specific task instructions

    The role card SHRINKS the behavior space by defining constraints.
    """

    # Core identification
    bot_name: str  # System identifier (e.g., "researcher", "coder")
    domain: RoleCardDomain  # What the bot specializes in

    # Layer 1: Domain ownership
    domain_description: str = ""  # Detailed description of domain ownership

    # Layer 2: Inputs/Outputs
    inputs: List[str] = field(default_factory=list)  # What the bot receives
    outputs: List[str] = field(default_factory=list)  # What the bot delivers

    # Layer 3: Definition of Done
    definition_of_done: List[str] = field(default_factory=list)  # Completion criteria

    # Layer 4: Hard Bans (what must never be done)
    hard_bans: List[str] = field(default_factory=list)  # Absolute prohibitions

    # Layer 5: Escalation triggers
    escalation_triggers: List[str] = field(default_factory=list)  # When to escalate

    # Layer 6: Metrics/KPIs
    metrics: List[str] = field(default_factory=list)  # Performance indicators

    # Functional capabilities
    capabilities: BotCapabilities = field(default_factory=BotCapabilities)

    # Display/identity attributes (typically set by team styling, not user-editable in role card)
    # Kept here for display customization driven by team profiles
    title: str = ""  # Display title (e.g., "Research Director")
    _display_name: str = ""  # Custom display name (private, use getter/setter)
    greeting: str = ""  # Default greeting message
    voice: str = ""  # Voice description (should match SOUL.md)

    # Metadata
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    editable_by_user: bool = True  # Can users edit this role card?
    editable_by_bots: bool = True  # Can bots propose updates?

    def get_display_name(self) -> str:
        """Get the display name for this bot.

        Returns:
            Display name (falls back to title if not set, then bot_name)
        """
        if self._display_name:
            return self._display_name
        if self.title:
            return self.title
        return self.bot_name

    def set_display_name(self, name: str) -> None:
        """Set a custom display name.

        Args:
            name: Custom display name (empty string resets to default)
        """
        self._display_name = name

    def has_capability(self, cap: str) -> bool:
        """Check if bot has a capability."""
        return getattr(self.capabilities, cap, False)

    def check_hard_bans(
        self, action: str, context: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if an action violates any hard bans.

        Args:
            action: Description of the action being attempted
            context: Additional context (tool name, parameters, etc.)

        Returns:
            Tuple of (is_allowed, violation_message)
            If allowed: (True, None)
            If banned: (False, "Violates ban: {ban_description}")
        """
        action_lower = action.lower()

        # Check each hard ban
        for ban in self.hard_bans:
            ban_lower = ban.lower()
            # Simple keyword matching (can be enhanced with more sophisticated logic)
            if any(keyword in action_lower for keyword in self._extract_keywords(ban_lower)):
                return False, f"Action violates hard ban: '{ban}'"

        return True, None

    def _extract_keywords(self, ban_text: str) -> List[str]:
        """Extract key action keywords from ban text for matching."""
        # Common action keywords to match against
        keywords = []
        action_patterns = [
            "direct",
            "post",
            "deploy",
            "execute",
            "modify",
            "delete",
            "bypass",
            "skip",
            "ignore",
            "fabricate",
            "invent",
            "make up",
            "without approval",
            "without verification",
            "internal format",
            "tool trace",
            "path",
            "credential",
            "secret",
        ]

        for pattern in action_patterns:
            if pattern in ban_text:
                keywords.append(pattern)

        return keywords if keywords else [ban_text]  # Fallback to full ban text

    def should_escalate(self, situation: str, confidence: float = 1.0) -> Tuple[bool, str]:
        """Determine if a situation requires escalation.

        Args:
            situation: Description of the current situation
            confidence: Confidence level (0.0-1.0)

        Returns:
            Tuple of (should_escalate, reason)
        """
        situation_lower = situation.lower()

        # Check escalation triggers
        for trigger in self.escalation_triggers:
            trigger_lower = trigger.lower()
            # Check if situation matches trigger
            if any(keyword in situation_lower for keyword in self._extract_keywords(trigger_lower)):
                return True, f"Escalation trigger matched: '{trigger}'"

        # Low confidence escalation
        if confidence < 0.5:
            return True, f"Low confidence ({confidence:.0%}) - requires human review"

        return False, ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert role card to dictionary."""
        return {
            "bot_name": self.bot_name,
            "domain": self.domain.value,
            "domain_description": self.domain_description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "definition_of_done": self.definition_of_done,
            "hard_bans": self.hard_bans,
            "escalation_triggers": self.escalation_triggers,
            "metrics": self.metrics,
            "capabilities": {
                "can_invoke_bots": self.capabilities.can_invoke_bots,
                "can_do_routines": self.capabilities.can_do_routines,
                "can_access_web": self.capabilities.can_access_web,
                "can_exec_commands": self.capabilities.can_exec_commands,
                "can_send_messages": self.capabilities.can_send_messages,
                "max_concurrent_tasks": self.capabilities.max_concurrent_tasks,
            },
            "title": self.title,
            "display_name": self._display_name,
            "greeting": self.greeting,
            "voice": self.voice,
            "version": self.version,
            "metadata": self.metadata,
            "editable_by_user": self.editable_by_user,
            "editable_by_bots": self.editable_by_bots,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoleCard":
        """Create role card from dictionary."""
        capabilities_data = data.get("capabilities", {})
        capabilities = BotCapabilities(
            can_invoke_bots=capabilities_data.get("can_invoke_bots", False),
            can_do_routines=capabilities_data.get("can_do_routines", False),
            can_access_web=capabilities_data.get("can_access_web", True),
            can_exec_commands=capabilities_data.get("can_exec_commands", True),
            can_send_messages=capabilities_data.get("can_send_messages", True),
            max_concurrent_tasks=capabilities_data.get("max_concurrent_tasks", 1),
        )

        # Create instance with core data
        instance = cls(
            bot_name=data["bot_name"],
            domain=RoleCardDomain(data["domain"]),
            domain_description=data.get("domain_description", ""),
            inputs=data.get("inputs", []),
            outputs=data.get("outputs", []),
            definition_of_done=data.get("definition_of_done", []),
            hard_bans=data.get("hard_bans", []),
            escalation_triggers=data.get("escalation_triggers", []),
            metrics=data.get("metrics", []),
            capabilities=capabilities,
            version=data.get("version", "1.0"),
            metadata=data.get("metadata", {}),
            editable_by_user=data.get("editable_by_user", True),
            editable_by_bots=data.get("editable_by_bots", True),
        )

        # Set display attributes if present
        instance.title = data.get("title", "")
        instance._display_name = data.get("display_name", "")
        instance.greeting = data.get("greeting", "")
        instance.voice = data.get("voice", "")

        return instance

    def format_for_prompt(self) -> str:
        """Format role card as a prompt-friendly string."""
        lines = [
            f"## Role Card: @{self.bot_name}",
            "",
            "**CRITICAL: How You Must Speak**",
            '- You must NEVER use stage directions in your responses. Never write things like "*adjusts hat*" or "*leans forward*" or "*smiles*". Write as if you\'re speaking naturally in conversation.',
            "",
            f"**Domain:** {self.domain.value}",
            f"{self.domain_description}",
            "",
        ]

        if self.inputs:
            lines.append("**Inputs (what you receive):**")
            for inp in self.inputs:
                lines.append(f"  - {inp}")
            lines.append("")

        if self.outputs:
            lines.append("**Outputs (what you deliver):**")
            for out in self.outputs:
                lines.append(f"  - {out}")
            lines.append("")

        if self.definition_of_done:
            lines.append("**Definition of Done (completion criteria):**")
            for criteria in self.definition_of_done:
                lines.append(f"  - {criteria}")
            lines.append("")

        if self.hard_bans:
            lines.append("**HARD BANS (what you must NEVER do):**")
            for ban in self.hard_bans:
                lines.append(f"  - {ban}")
            lines.append("")

        if self.escalation_triggers:
            lines.append("**Escalation triggers (when to ask for help):**")
            for trigger in self.escalation_triggers:
                lines.append(f"  - {trigger}")
            lines.append("")

        if self.metrics:
            lines.append("**Your KPIs:**")
            for metric in self.metrics:
                lines.append(f"  - {metric}")
            lines.append("")

        lines.append("**Capabilities:**")
        lines.append(f"  - Can invoke other bots: {self.capabilities.can_invoke_bots}")
        lines.append(f"  - Can do routines: {self.capabilities.can_do_routines}")
        lines.append(f"  - Can access web: {self.capabilities.can_access_web}")
        lines.append(f"  - Can execute commands: {self.capabilities.can_exec_commands}")
        lines.append(f"  - Can send messages: {self.capabilities.can_send_messages}")
        lines.append(f"  - Max concurrent tasks: {self.capabilities.max_concurrent_tasks}")

        return "\n".join(lines)


# =============================================================================
# Complete Role Cards for Each Bot
# =============================================================================

LEADER_ROLE = RoleCard(
    bot_name="leader",
    domain=RoleCardDomain.COORDINATION,
    domain_description="Team coordination, task delegation, and final decision making. You are the Chief of Staff who ensures all bots work together effectively.",
    inputs=[
        "User requests and requirements",
        "Bot outputs and deliverables",
        "Status reports from specialists",
        "Escalations requiring decisions",
        "System health metrics",
    ],
    outputs=[
        "Task assignments to specialist bots",
        "Coordinated responses to users",
        "Final decisions on escalations",
        "Strategic direction and priorities",
        "Team health summaries",
    ],
    definition_of_done=[
        "All tasks are assigned to appropriate bots",
        "Escalations have been resolved or forwarded to user",
        "Team coordination is documented",
        "Next steps and owners are clearly defined",
    ],
    hard_bans=[
        "No deploying to production without approval",
        "No making final decisions on legal/compliance issues without user confirmation",
        "No overriding specialist bot expertise without good reason",
        "No ignoring escalation requests from bots",
        "No keeping critical information from the user",
    ],
    escalation_triggers=[
        "Legal or compliance risks",
        "High-stakes decisions with unclear outcomes",
        "Bot conflicts that cannot be resolved",
        "Security incidents or vulnerabilities",
        "Tasks outside all bot domains",
    ],
    metrics=[
        "Task completion rate",
        "Average resolution time",
        "Escalation handling speed",
        "Bot team utilization",
        "User satisfaction with coordination",
    ],
    capabilities=BotCapabilities(
        can_invoke_bots=True,
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=True,
        can_send_messages=True,
        max_concurrent_tasks=3,
    ),
    version="1.0",
)

RESEARCHER_ROLE = RoleCard(
    bot_name="researcher",
    domain=RoleCardDomain.RESEARCH,
    domain_description="Information gathering, data analysis, and knowledge synthesis. You find facts, verify claims, and provide evidence-based insights.",
    inputs=[
        "Research questions and topics",
        "Data sources and references",
        "Claims requiring verification",
        "Market trends and signals",
        "Competitor information",
    ],
    outputs=[
        "Research summaries with sources",
        "Fact-checked information",
        "Data analysis and insights",
        "Verified citations and references",
        "Risk flags for unverified claims",
    ],
    definition_of_done=[
        "Information is sourced and citations provided",
        "Claims have been verified or flagged as unverified",
        "Analysis includes methodology and confidence level",
        "Deliverable is review-ready with clear findings",
    ],
    hard_bans=[
        "No making up citations or fabricating data",
        "No presenting unverified information as fact",
        "No using outdated sources without noting the date",
        "No internal tool traces or paths in outputs",
        "No ignoring conflicting evidence",
    ],
    escalation_triggers=[
        "Conflicting or contradictory data",
        "Insufficient reliable sources",
        "Claims requiring domain expertise beyond research",
        "Sensitive or controversial topics",
        "Data quality concerns",
    ],
    metrics=[
        "Research accuracy rate",
        "Source quality score",
        "Time to complete research",
        "Citation completeness",
        "User satisfaction with findings",
    ],
    capabilities=BotCapabilities(
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=False,
        can_send_messages=False,
        max_concurrent_tasks=2,
    ),
    version="1.0",
)

CODER_ROLE = RoleCard(
    bot_name="coder",
    domain=RoleCardDomain.DEVELOPMENT,
    domain_description="Code implementation, debugging, and technical solutions. You write clean, maintainable code and ensure technical quality.",
    inputs=[
        "Technical requirements and specs",
        "Bug reports and issues",
        "Code review requests",
        "Architecture decisions to implement",
        "Security vulnerabilities to fix",
    ],
    outputs=[
        "Clean, documented code",
        "Bug fixes with tests",
        "Code review feedback",
        "Technical implementation plans",
        "Security patches",
    ],
    definition_of_done=[
        "Code compiles/parses without errors",
        "Tests pass (unit, integration, lint)",
        "Documentation is updated",
        "Security scan passes",
        "Implementation matches requirements",
    ],
    hard_bans=[
        "No committing directly to main/production without PR",
        "No skipping tests or code review",
        "No introducing security vulnerabilities",
        "No breaking existing functionality without migration plan",
        "No leaving hardcoded credentials or secrets",
        "No internal file paths or tool traces in code comments",
    ],
    escalation_triggers=[
        "Architectural decisions affecting multiple systems",
        "Security vulnerabilities requiring immediate attention",
        "Breaking changes to public APIs",
        "Unclear requirements or conflicting specifications",
        "Performance concerns requiring optimization",
    ],
    metrics=[
        "Code quality score",
        "Bug fix success rate",
        "Test coverage",
        "Security scan results",
        "Implementation time vs estimate",
    ],
    capabilities=BotCapabilities(
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=True,
        can_send_messages=False,
        max_concurrent_tasks=2,
    ),
    version="1.0",
)

SOCIAL_ROLE = RoleCard(
    bot_name="social",
    domain=RoleCardDomain.COMMUNITY,
    domain_description="Community engagement, social media management, and public communication. You manage the public face and community interactions.",
    inputs=[
        "Content drafts and variants",
        "Community mentions and feedback",
        "Trending topics and signals",
        "Brand guidelines and constraints",
        "Engagement metrics and analytics",
    ],
    outputs=[
        "Social media drafts (NOT direct posts)",
        "Community response suggestions",
        "Engagement reports",
        "Risk flags for public content",
        "Posting plans and schedules",
    ],
    definition_of_done=[
        "Draft is review-ready with 1-2 variants",
        "Any risky claims are flagged explicitly",
        "Content aligns with brand guidelines",
        "Plan includes next step and owner",
        "Drafts are saved for approval, NOT posted",
    ],
    hard_bans=[
        "No direct posting to social media (drafts only)",
        "No making up statistics or numbers",
        "No internal formats or tool traces in public content",
        "No ignoring negative sentiment or crises",
        "No engaging with trolls or inflammatory content",
        "No posting without brand approval on sensitive topics",
    ],
    escalation_triggers=[
        "Numeric claims or comparisons requiring verification",
        "Controversial or sensitive topics",
        "Negative sentiment or PR risks",
        "Community crisis or backlash",
        "Unclear brand alignment",
    ],
    metrics=[
        "Engagement rate per post",
        "Drafts-to-publish ratio",
        "Community interaction quality",
        "Response time to mentions",
        "Brand sentiment tracking",
    ],
    capabilities=BotCapabilities(
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=False,
        can_send_messages=True,
        max_concurrent_tasks=2,
    ),
    version="1.0",
)

CREATIVE_ROLE = RoleCard(
    bot_name="creative",
    domain=RoleCardDomain.DESIGN,
    domain_description="Content creation, design assets, and creative strategy. You craft compelling content while maintaining brand consistency.",
    inputs=[
        "Creative briefs and requirements",
        "Brand guidelines and assets",
        "Content calendars and deadlines",
        "Feedback on creative work",
        "Design references and inspiration",
    ],
    outputs=[
        "Creative content and copy",
        "Design assets and mockups",
        "Content variants for testing",
        "Creative strategy recommendations",
        "Asset organization and documentation",
    ],
    definition_of_done=[
        "Content meets creative brief requirements",
        "Brand guidelines are followed",
        "Assets are organized and named correctly",
        "Deliverables are in requested formats",
        "Creative is review-ready with rationale",
    ],
    hard_bans=[
        "No inventing facts for creative content",
        "No using copyrighted material without permission",
        "No deviating from brand guidelines without approval",
        "No internal tool paths or references in public assets",
        "No missing deadlines without communication",
    ],
    escalation_triggers=[
        "Conflicts between creative vision and brand guidelines",
        "Requests requiring copyrighted or licensed material",
        "Extremely tight deadlines affecting quality",
        "Vague creative briefs requiring clarification",
        "Multiple rounds of conflicting feedback",
    ],
    metrics=[
        "Creative output volume",
        "Content approval rate",
        "Brand consistency score",
        "Deadline adherence",
        "User satisfaction with creative work",
    ],
    capabilities=BotCapabilities(
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=False,
        can_send_messages=False,
        max_concurrent_tasks=2,
    ),
    version="1.0",
)

AUDITOR_ROLE = RoleCard(
    bot_name="auditor",
    domain=RoleCardDomain.QUALITY,
    domain_description="Cross-domain quality assurance and compliance guardian. You audit outputs from ALL bots (research, creative, code, social) ensuring they meet standards, are complete, accurate, and compliant before approval or handoff.",
    inputs=[
        "Code for technical review (security, quality, standards)",
        "Research outputs for fact-checking and methodology review",
        "Creative assets for brand compliance and completeness",
        "Social content for risk assessment and approval readiness",
        "Cross-bot handoffs for workflow compliance",
        "Documentation for accuracy and completeness",
        "Definition-of-Done criteria for deliverables",
        "Compliance requirements and quality standards",
        "Audit logs and bot activity trails",
    ],
    outputs=[
        "Comprehensive audit reports with domain-specific findings",
        "Quality gate decisions (pass/block/request changes)",
        "Fact-checking reports with verification status",
        "Brand compliance assessments for creative work",
        "Risk assessments for public-facing content",
        "Cross-bot workflow compliance reports",
        "Definition-of-Done verification results",
        "Process improvement recommendations",
        "Audit trail integrity reports",
    ],
    definition_of_done=[
        "All applicable quality checks completed for the domain",
        "Critical issues flagged and rated by severity",
        "Verification evidence documented (sources, screenshots, references)",
        "Recommendations are specific and actionable",
        "Audit trail entry created with timestamps and decisions",
        "Handoff readiness status clearly stated",
    ],
    hard_bans=[
        "No approving work with critical security, legal, or safety issues",
        "No ignoring compliance violations (GDPR, copyright, accessibility)",
        "No approving public content with unverified factual claims",
        "No approving creative work that violates brand guidelines",
        "No approving incomplete deliverables missing required components",
        "No approving research without verifiable sources",
        "No personal attacks or blame in feedback - focus on issues not people",
        "No missing critical audit trail entries",
        "No overriding quality gates without explicit escalation and approval",
        "No fabricating or exaggerating audit findings",
        "No approving cross-bot handoffs with incomplete context or missing deliverables",
        "No ignoring conflicting information between bot outputs",
    ],
    escalation_triggers=[
        "Critical security vulnerabilities in code",
        "Legal or compliance violations (copyright, privacy, accessibility)",
        "Public content with unverified claims or potential misinformation",
        "Creative assets violating brand guidelines or legal requirements",
        "Research with fabricated or unsupportable conclusions",
        "Missing audit trails or tampering evidence",
        "Significant quality degradation across multiple domains",
        "Cross-bot workflow failures or communication breakdowns",
        "Conflicts between speed requirements and quality standards",
        "Unclear quality criteria or missing acceptance standards",
        "Audit findings that challenge fundamental assumptions",
    ],
    metrics=[
        "Quality gate pass rate by domain (code, research, creative, social)",
        "Critical issue detection rate",
        "Fact-checking accuracy (verified claims / total claims)",
        "Brand compliance score for creative assets",
        "Risk identification rate before publication",
        "Cross-bot handoff success rate",
        "Definition-of-Done fulfillment rate",
        "Audit completion time by deliverable type",
        "False positive rate (incorrectly flagged issues)",
        "Process improvement recommendations implemented",
    ],
    capabilities=BotCapabilities(
        can_do_routines=True,
        can_access_web=True,
        can_exec_commands=True,
        can_send_messages=False,
        max_concurrent_tasks=3,
    ),
    version="2.0",
)


# =============================================================================
# Role Card Storage and Management
# =============================================================================

BUILTIN_ROLES: Dict[str, RoleCard] = {
    "leader": LEADER_ROLE,
    "researcher": RESEARCHER_ROLE,
    "coder": CODER_ROLE,
    "social": SOCIAL_ROLE,
    "creative": CREATIVE_ROLE,
    "auditor": AUDITOR_ROLE,
}


class RoleCardStorage:
    """Storage manager for user-editable role cards.

    Role cards can be stored at:
    - {workspace}/.nanofolks/role_cards/{bot_name}.yaml (user overrides)
    - ~/.config/nanofolks/role_cards/{bot_name}.yaml (global overrides)

    Bots can propose updates which are saved as drafts for user approval.
    """

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace = workspace_path or Path.cwd()
        self.role_cards_dir = self.workspace / ".nanofolks" / "role_cards"
        self.global_dir = Path.home() / ".config" / "nanofolks" / "role_cards"

        # Ensure directories exist
        self.role_cards_dir.mkdir(parents=True, exist_ok=True)
        self.global_dir.mkdir(parents=True, exist_ok=True)

    def get_role_card(self, bot_name: str, use_cache: bool = True) -> Optional[RoleCard]:
        """Get role card for a bot.

        Priority:
        1. ROLE.md in workspace (user-editable markdown)
        2. YAML workspace override (legacy)
        3. YAML global override (legacy)
        4. Built-in default

        Args:
            bot_name: Name of the bot
            use_cache: Whether to use cached version

        Returns:
            RoleCard or None if not found
        """
        # 1. Check for ROLE.md (new markdown-based approach)
        from nanofolks.identity.role_parser import RoleParser

        role_parser = RoleParser(self.workspace)
        role_from_md = role_parser.parse_role_file(bot_name)
        if role_from_md:
            return role_from_md

        # 2. Check YAML workspace override (legacy)
        workspace_path = self.role_cards_dir / f"{bot_name}.yaml"
        if workspace_path.exists():
            return self._load_from_file(workspace_path)

        # 3. Check YAML global override (legacy)
        global_path = self.global_dir / f"{bot_name}.yaml"
        if global_path.exists():
            return self._load_from_file(global_path)

        # 4. Return built-in default
        return BUILTIN_ROLES.get(bot_name)

    def _load_from_file(self, path: Path) -> Optional[RoleCard]:
        """Load role card from YAML file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            return RoleCard.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load role card from {path}: {e}")
            return None

    def save_role_card(self, role_card: RoleCard, scope: str = "workspace") -> bool:
        """Save a role card override.

        Args:
            role_card: The role card to save
            scope: "workspace" or "global"

        Returns:
            True if saved successfully
        """
        if scope == "workspace":
            path = self.role_cards_dir / f"{role_card.bot_name}.yaml"
        else:
            path = self.global_dir / f"{role_card.bot_name}.yaml"

        try:
            with open(path, "w") as f:
                yaml.dump(role_card.to_dict(), f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved role card for {role_card.bot_name} to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save role card: {e}")
            return False

    def save_bot_proposal(
        self, bot_name: str, proposed_changes: Dict[str, Any], reason: str
    ) -> bool:
        """Save a bot-proposed role card update as a draft.

        These proposals require user approval before becoming active.

        Args:
            bot_name: Name of the bot proposing changes
            proposed_changes: Dictionary of proposed changes
            reason: Explanation for the changes

        Returns:
            True if proposal was saved
        """
        proposal_path = self.role_cards_dir / f"{bot_name}_proposal.yaml"

        proposal = {
            "status": "pending",
            "proposed_by": bot_name,
            "reason": reason,
            "timestamp": str(datetime.now()),
            "changes": proposed_changes,
        }

        try:
            with open(proposal_path, "w") as f:
                yaml.dump(proposal, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Saved role card proposal from {bot_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")
            return False

    def list_available_roles(self) -> List[str]:
        """List all available role names."""
        builtin = set(BUILTIN_ROLES.keys())

        # Check for workspace overrides
        workspace_roles = set()
        if self.role_cards_dir.exists():
            for f in self.role_cards_dir.glob("*.yaml"):
                if not f.name.endswith("_proposal.yaml"):
                    workspace_roles.add(f.stem)

        # Check for global overrides
        global_roles = set()
        if self.global_dir.exists():
            for f in self.global_dir.glob("*.yaml"):
                if not f.name.endswith("_proposal.yaml"):
                    global_roles.add(f.stem)

        return sorted(builtin | workspace_roles | global_roles)

    def reset_to_default(self, bot_name: str) -> bool:
        """Remove user overrides and reset to built-in default.

        Args:
            bot_name: Name of the bot

        Returns:
            True if reset (or was already at default)
        """
        workspace_path = self.role_cards_dir / f"{bot_name}.yaml"
        global_path = self.global_dir / f"{bot_name}.yaml"

        removed = False
        if workspace_path.exists():
            workspace_path.unlink()
            removed = True
        if global_path.exists():
            global_path.unlink()
            removed = True

        if removed:
            logger.info(f"Reset role card for {bot_name} to default")

        return True


# =============================================================================
# Global Functions
# =============================================================================

_storage_instance: Optional[RoleCardStorage] = None


def get_role_card_storage(workspace_path: Optional[Path] = None) -> RoleCardStorage:
    """Get or create the global role card storage instance."""
    global _storage_instance
    if _storage_instance is None or workspace_path:
        _storage_instance = RoleCardStorage(workspace_path)
    return _storage_instance


def get_role_card(bot_name: str, workspace_path: Optional[Path] = None) -> Optional[RoleCard]:
    """Get role card for a bot.

    Args:
        bot_name: Name of the bot
        workspace_path: Optional workspace path for user overrides

    Returns:
        RoleCard or None if not found
    """
    storage = get_role_card_storage(workspace_path)
    return storage.get_role_card(bot_name)


def list_roles(workspace_path: Optional[Path] = None) -> List[str]:
    """List all available role names."""
    storage = get_role_card_storage(workspace_path)
    return storage.list_available_roles()


def is_valid_role(bot_name: str) -> bool:
    """Check if a bot name is valid."""
    return bot_name in BUILTIN_ROLES


def save_role_card(
    role_card: RoleCard, scope: str = "workspace", workspace_path: Optional[Path] = None
) -> bool:
    """Save a role card override."""
    storage = get_role_card_storage(workspace_path)
    return storage.save_role_card(role_card, scope)


# Legacy compatibility
list_bots = list_roles
is_valid_bot = is_valid_role


# Import datetime at end to avoid circular import issues
from datetime import datetime

__all__ = [
    "RoleCard",
    "RoleCardDomain",
    "BotCapabilities",
    "RoleCardStorage",
    "get_role_card",
    "get_role_card_storage",
    "list_roles",
    "list_bots",
    "is_valid_role",
    "is_valid_bot",
    "save_role_card",
    "BUILTIN_ROLES",
    "LEADER_ROLE",
    "RESEARCHER_ROLE",
    "CODER_ROLE",
    "SOCIAL_ROLE",
    "CREATIVE_ROLE",
    "AUDITOR_ROLE",
]
