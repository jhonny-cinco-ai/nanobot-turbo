# Multi-Agent Orchestration v2.0 Implementation Plan

**Status:** Active Implementation Plan  
**Created:** February 12, 2026  
**Based On:** MULTI_AGENT_ORCHESTRATION_ANALYSIS.md  
**Estimated Duration:** 6 weeks (phased approach)

> ⭐ **THIS IS THE MAIN FILE TO FOLLOW** - Contains all phases, deliverables, and code templates

---

## Quick Navigation

- **Want overview?** → Read "Executive Summary" below
- **Ready to code?** → Jump to Phase 1 section
- **Need specific details?** → Use Ctrl+F to search

---

## Executive Summary

This document outlines the concrete implementation steps to bring the Workspace & Contextual Team Model (v2.0) to life. The plan is organized into 5 phases with specific, actionable tasks.

**Key Timeline:**
- **Phase 1 (Week 1-2):** Foundation - Workspace model, tagging, role cards, leader + 5 specialist bots
- **Phase 2 (Week 3):** Personalization - 5 personality themes, onboarding wizard
- **Phase 3 (Week 4):** Memory - Hybrid architecture with cross-pollination
- **Phase 4 (Week 5):** Coordination - Autonomous collaboration, escalations
- **Phase 5 (Week 6):** Polish - Archival, summaries, docs, performance tuning

---

## Phase 1: Foundation (Week 1-2)

### Objectives
- Implement core Workspace data model
- Build tag parsing system
- Create role card structure
- Deploy 1 leader bot (nanobot) + 5 specialist bots

### Bot Team Structure (Important Clarification)

The system has **6 bots total**: 1 Leader + 5 Specialists

1. **nanobot** (The Leader/Coordinator)
   - Domain: Coordination, user interface, team management
   - Role: Your personalized companion, always present
   - Responsibilities: Route messages, manage escalations, create workspaces
   - Authority: High (can make decisions when coordinator mode enabled)

2. **@researcher** (Specialist Domain: Research & Analysis)
3. **@coder** (Specialist Domain: Development & Implementation)
4. **@social** (Specialist Domain: Community & Engagement)
5. **@creative** (Specialist Domain: Design & Content Creation)
6. **@auditor** (Specialist Domain: Quality & Compliance)

**Key distinction:**
- nanobot has a **Coordinator role card** (not a specialist domain)
- The 5 specialists have **Domain role cards** (research, development, community, design, quality)
- All 6 follow the same role card structure with hard bans and affinities

### Deliverables

#### 1.1: Workspace Data Model
**File:** `nanobot/models/workspace.py`

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any
from datetime import datetime

class WorkspaceType(Enum):
    OPEN = "open"          # #general - all bots, casual
    PROJECT = "project"    # #project-x - specific team, deadline
    DIRECT = "direct"      # DM @bot - 1-on-1 focused
    COORDINATION = "coordination"  # nanobot manages

@dataclass
class Message:
    sender: str
    content: str
    timestamp: datetime
    workspace_id: str
    attachments: List[str] = field(default_factory=list)

@dataclass
class SharedContext:
    events: List[Dict[str, Any]] = field(default_factory=list)
    entities: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    facts: List[Dict[str, Any]] = field(default_factory=list)
    artifact_chain: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Workspace:
    id: str
    type: WorkspaceType
    participants: List[str]  # ["nanobot", "researcher", "coder"]
    owner: str  # "user" or bot name if coordination mode
    created_at: datetime
    
    # Memory
    shared_context: SharedContext = field(default_factory=SharedContext)
    history: List[Message] = field(default_factory=list)
    summary: str = ""
    
    # Behavior
    auto_archive: bool = False
    archive_after_days: int = 30
    coordinator_mode: bool = False
    escalation_threshold: str = "medium"  # "low", "medium", "high"
    
    # Metadata
    deadline: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, sender: str, content: str):
        """Add message to workspace history."""
        msg = Message(
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            workspace_id=self.id
        )
        self.history.append(msg)
    
    def add_participant(self, bot_name: str):
        """Add bot to workspace."""
        if bot_name not in self.participants:
            self.participants.append(bot_name)
    
    def is_active(self) -> bool:
        """Check if workspace should be archived."""
        if not self.history:
            return False
        last_activity = self.history[-1].timestamp
        days_inactive = (datetime.now() - last_activity).days
        return days_inactive < self.archive_after_days
```

**Testing:** Create `tests/test_workspace_model.py`
- Test workspace creation with different types
- Test message addition and history
- Test participant management
- Test archive eligibility

**Acceptance Criteria:**
- Workspace model fully functional
- All workspace types create correctly
- Message history maintained with timestamps
- Participant tracking works

---

#### 1.2: Tag Parsing System
**File:** `nanobot/systems/tag_handler.py`

```python
import re
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class ParsedTags:
    bots: List[str]  # ["researcher", "coder"]
    workspaces: List[str]  # ["project-refactor"]
    actions: List[str]  # ["create", "analyze"]
    raw_message: str
    mentions: Dict[str, str]  # "@researcher" -> full mention context

class TagHandler:
    """Parse Discord/Slack style tags from messages."""
    
    BOT_PATTERN = r'@([\w\-]+)'
    WORKSPACE_PATTERN = r'#([\w\-]+)'
    ACTION_PATTERN = r'^(create|join|leave|analyze|research|coordinate)\s'
    
    def parse_tags(self, message: str) -> ParsedTags:
        """
        Extract all tags from message.
        
        Examples:
            "@researcher analyze #project-alpha market data"
            -> bots=["researcher"], workspaces=["project-alpha"], actions=["analyze"]
        
            "create #new-workspace for Q2 planning"
            -> workspaces=["new-workspace"], actions=["create"]
            
            "#general what's the status?"
            -> workspaces=["general"]
        """
        bots = [m.group(1) for m in re.finditer(self.BOT_PATTERN, message)]
        workspaces = [m.group(1) for m in re.finditer(self.WORKSPACE_PATTERN, message)]
        actions = []
        
        action_match = re.match(self.ACTION_PATTERN, message, re.IGNORECASE)
        if action_match:
            actions.append(action_match.group(1).lower())
        
        return ParsedTags(
            bots=list(set(bots)),
            workspaces=list(set(workspaces)),
            actions=actions,
            raw_message=message,
            mentions=self._extract_mentions(message)
        )
    
    def _extract_mentions(self, message: str) -> Dict[str, str]:
        """Extract full context of each mention."""
        mentions = {}
        for bot in re.findall(self.BOT_PATTERN, message):
            # Get surrounding words for context
            mentions[f"@{bot}"] = message
        return mentions
    
    def validate_tags(self, parsed: ParsedTags, valid_bots: List[str], 
                      valid_workspaces: List[str]) -> tuple[bool, List[str]]:
        """Validate parsed tags against available bots and workspaces."""
        errors = []
        
        for bot in parsed.bots:
            if bot not in valid_bots:
                errors.append(f"Unknown bot: @{bot}")
        
        for ws in parsed.workspaces:
            if ws not in valid_workspaces:
                errors.append(f"Unknown workspace: #{ws}")
        
        return len(errors) == 0, errors
```

**Testing:** Create `tests/test_tag_handler.py`
- Test @bot tag parsing
- Test #workspace tag parsing
- Test action detection
- Test validation with valid/invalid tags
- Test multiple tags in one message
- Test edge cases (nested tags, special chars)

**Acceptance Criteria:**
- Tag parser identifies all @bots and #workspaces correctly
- Actions detected reliably
- Validation catches invalid tags
- Handles edge cases gracefully

---

#### 1.3: Role Card Structure
**File:** `nanobot/models/role_card.py`

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum

class BotDomain(Enum):
    RESEARCH = "research"
    DEVELOPMENT = "development"
    COMMUNITY = "community"
    DESIGN = "design"
    QUALITY = "quality"
    COORDINATION = "coordination"

@dataclass
class HardBan:
    """Rules that bot MUST follow (never override)."""
    rule: str
    consequence: str  # What happens if violated
    severity: str  # "critical", "high", "medium"

@dataclass
class Affinity:
    """How well this bot works with others."""
    bot_name: str
    score: float  # 0.0 to 1.0
    reason: str
    can_produce_creative_tension: bool = False

@dataclass
class RoleCard:
    """Complete bot personality and constraints."""
    bot_name: str
    domain: BotDomain
    title: str  # "Navigator", "Gunner", "Lookout", etc.
    description: str
    
    # Inputs/Outputs
    inputs: List[str]  # What this bot accepts
    outputs: List[str]  # What this bot produces
    
    # Constraints
    hard_bans: List[HardBan] = field(default_factory=list)
    capabilities: Dict[str, bool] = field(default_factory=dict)
    
    # Personality
    voice: str  # Communication style
    greeting: str  # How it introduces itself
    emoji: str = ""
    
    # Relationships
    affinities: List[Affinity] = field(default_factory=list)
    
    # Metadata
    version: str = "1.0"
    author: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_affinity_with(self, bot_name: str) -> float:
        """Get affinity score with another bot."""
        for aff in self.affinities:
            if aff.bot_name == bot_name:
                return aff.score
        return 0.5  # neutral default
    
    def has_capability(self, capability: str) -> bool:
        """Check if bot has a capability."""
        return self.capabilities.get(capability, False)
    
    def validate_action(self, action: str) -> tuple[bool, str]:
        """Check if action violates hard bans."""
        for ban in self.hard_bans:
            if self._matches_rule(action, ban.rule):
                return False, f"Hard ban: {ban.rule}. Consequence: {ban.consequence}"
        return True, ""
    
    def _matches_rule(self, action: str, rule: str) -> bool:
        """Simple rule matching (can be enhanced with regex)."""
        return rule.lower() in action.lower()
```

**File:** `nanobot/bots/specialist_definitions.py`

Contains role cards for all 5 bots (1 coordinator + 4 specialists):

```python
# THE LEADER/COORDINATOR
NANOBOT_ROLE = RoleCard(
    bot_name="nanobot",
    domain=BotDomain.COORDINATION,
    title="Your Companion",  # Themed: "Captain", "Lead Singer", "Commander", etc.
    description="Team coordinator, user interface, relationship builder",
    inputs=["User messages", "Team requests", "Workspace management", "Escalations"],
    outputs=["Routed messages", "Team summaries", "Decisions", "Notifications"],
    hard_bans=[
        HardBan(
            rule="override user decisions without escalation",
            consequence="user loses control, trust destroyed",
            severity="critical"
        ),
        HardBan(
            rule="make commitments user wouldn't approve",
            consequence="user left with broken promises",
            severity="critical"
        ),
        HardBan(
            rule="forget what user taught you",
            consequence="lost relationship building, frustration",
            severity="high"
        ),
    ],
    voice="Warm, supportive, decisive. Represents user to the team.",
    greeting="I'm here for you. What shall we tackle today?",
    emoji="🤖",
    affinities=[
        Affinity("researcher", 0.8, "Strong partnership, values evidence"),
        Affinity("coder", 0.7, "Trusts technical judgment"),
        Affinity("social", 0.8, "Strong partnership, community voice"),
        Affinity("auditor", 0.9, "Excellent relationship, quality focused"),
    ],
)
```

Now the 4 specialists:

```python
RESEARCHER_ROLE = RoleCard(
    bot_name="researcher",
    domain=BotDomain.RESEARCH,
    title="Navigator",
    description="Scout, analysis, knowledge synthesis",
    inputs=["Research queries", "Web data", "Documents", "Market analysis requests"],
    outputs=["Synthesized reports", "Knowledge updates", "Gap analysis", "Data insights"],
    hard_bans=[
        HardBan(
            rule="make up citations",
            consequence="credibility destroyed, user misled",
            severity="critical"
        ),
        HardBan(
            rule="state opinions as facts",
            consequence="misinformation, lost trust",
            severity="critical"
        ),
        HardBan(
            rule="exceed API cost per query",
            consequence="unexpected expenses, user frustrated",
            severity="high"
        ),
    ],
    voice="Measured, analytical, skeptical. Asks for data before conclusions.",
    greeting="Navigator here. What waters shall we explore?",
    emoji="🧭",
    affinities=[
        Affinity("nanobot", 0.8, "Works well with coordinator"),
        Affinity("coder", 0.3, "Tension: caution vs speed (productive)", True),
        Affinity("social", 0.4, "Some friction: depth vs breadth"),
    ],
)

CODER_ROLE = RoleCard(
    bot_name="coder",
    domain=BotDomain.DEVELOPMENT,
    title="Gunner",
    description="Code implementation, technical solutions",
    inputs=["Technical requirements", "Codebases", "Bug reports", "Architecture questions"],
    outputs=["Working code", "Technical analysis", "Refactoring plans", "Bug fixes"],
    hard_bans=[
        HardBan(
            rule="ship without basic tests",
            consequence="production bugs, user trust lost",
            severity="critical"
        ),
        HardBan(
            rule="modify production without backup",
            consequence="data loss, catastrophic failure",
            severity="critical"
        ),
        HardBan(
            rule="ignore security vulnerabilities",
            consequence="system compromise, breach risk",
            severity="critical"
        ),
    ],
    voice="Pragmatic, direct, hates unnecessary complexity.",
    greeting="Gunner ready. What needs fixing?",
    emoji="🔧",
    affinities=[
        Affinity("nanobot", 0.7, "Strong working relationship"),
        Affinity("researcher", 0.3, "Tension: speed vs caution (productive)", True),
        Affinity("auditor", 0.9, "Great collaboration"),
    ],
)

SOCIAL_ROLE = RoleCard(
    bot_name="social",
    domain=BotDomain.COMMUNITY,
    title="Lookout",
    description="Community engagement, social media",
    inputs=["Content drafts", "Channel data", "Engagement metrics", "Community feedback"],
    outputs=["Scheduled posts", "Community responses", "Trend reports", "Engagement summaries"],
    hard_bans=[
        HardBan(
            rule="post without user approval",
            consequence="unauthorized communication, brand damage",
            severity="critical"
        ),
        HardBan(
            rule="engage with trolls or harassment",
            consequence="amplify negativity, feed bad behavior",
            severity="high"
        ),
        HardBan(
            rule="share sensitive internal data",
            consequence="privacy breach, data leak",
            severity="critical"
        ),
    ],
    voice="Responsive, engaging, careful with public voice.",
    greeting="Lookout on duty. What's the vibe?",
    emoji="📢",
    affinities=[
        Affinity("nanobot", 0.8, "Strong partnership"),
        Affinity("researcher", 0.4, "Some friction: impulse vs caution"),
        Affinity("creative", 0.95, "Exceptional collaboration"),
    ],
)

CREATIVE_ROLE = RoleCard(
    bot_name="creative",
    domain=BotDomain.DESIGN,
    title="Artist",
    description="Design, content creation, visual storytelling",
    inputs=["Design briefs", "Content requests", "Brand guidelines", "Feedback on designs"],
    outputs=["Designs", "Content", "Visual assets", "Creative direction", "Brand materials"],
    hard_bans=[
        HardBan(
            rule="ignore brand guidelines or user direction",
            consequence="inconsistent brand, user frustration",
            severity="high"
        ),
        HardBan(
            rule="create without considering accessibility",
            consequence="excludes users, brand damage",
            severity="high"
        ),
        HardBan(
            rule="proceed without stakeholder feedback",
            consequence="wasted effort, wrong direction",
            severity="medium"
        ),
    ],
    voice="Imaginative, collaborative, asks clarifying questions. Translates ideas to visuals.",
    greeting="Let's create something amazing! What's the vision?",
    emoji="🎨",
    affinities=[
        Affinity("nanobot", 0.7, "Good partnership on vision"),
        Affinity("social", 0.95, "Exceptional collaboration - content & community"),
        Affinity("researcher", 0.5, "Some friction: inspiration vs data"),
        Affinity("coder", 0.6, "Good collaboration - design meets tech"),
        Affinity("auditor", 0.5, "Some friction: creative freedom vs constraints"),
    ],
)

AUDITOR_ROLE = RoleCard(
    bot_name="auditor",
    domain=BotDomain.QUALITY,
    title="Quartermaster",
    description="Quality review, budget, compliance",
    inputs=["Completed work", "Budget data", "Process logs", "Quality reviews"],
    outputs=["Review reports", "Budget alerts", "Improvement suggestions", "Compliance checks"],
    hard_bans=[
        HardBan(
            rule="blame individuals, critique processes",
            consequence="team morale destroyed, defensive behavior",
            severity="high"
        ),
        HardBan(
            rule="modify others' work directly",
            consequence="ownership confusion, learning prevented",
            severity="high"
        ),
        HardBan(
            rule="ignore safety or security concerns",
            consequence="risk exposure, potential breach",
            severity="critical"
        ),
    ],
    voice="Evidence-based, process-focused, constructive.",
    greeting="Quartermaster reporting. Status check?",
    emoji="✅",
    affinities=[
        Affinity("nanobot", 0.9, "Excellent coordination"),
        Affinity("coder", 0.9, "Great partnership"),
        Affinity("social", 0.4, "Some friction: caution vs action"),
        Affinity("creative", 0.5, "Some friction: creative freedom vs quality standards"),
    ],
)
```

**Acceptance Criteria:**
- All 5 specialist role cards defined (researcher, coder, social, creative, auditor)
- Hard bans are clear and enforceable
- Affinities create realistic team dynamics
- Voice/personality distinct for each bot

---

#### 1.4: Implement Leader + 5 Specialist Bots
**File:** `nanobot/bots/specialist_bot.py`

```python
from abc import ABC, abstractmethod
from typing import Optional
from nanobot.models.role_card import RoleCard
from nanobot.models.workspace import Workspace

class SpecialistBot(ABC):
    """Base class for all specialist bots."""
    
    def __init__(self, role_card: RoleCard):
        self.role_card = role_card
        self.private_memory = {
            "learnings": [],
            "expertise_domains": [],
            "mistakes": [],
            "confidence": 0.7,
        }
    
    def can_perform_action(self, action: str) -> tuple[bool, Optional[str]]:
        """Validate action against hard bans."""
        return self.role_card.validate_action(action)
    
    def get_greeting(self, workspace: Workspace) -> str:
        """Get bot's greeting for workspace."""
        return self.role_card.greeting
    
    def record_learning(self, lesson: str, confidence: float):
        """Record a private learning."""
        self.private_memory["learnings"].append({
            "lesson": lesson,
            "confidence": confidence,
            "timestamp": datetime.now()
        })
    
    def record_mistake(self, error: str, recovery: str):
        """Record mistake and how it was fixed."""
        self.private_memory["mistakes"].append({
            "error": error,
            "recovery": recovery,
            "timestamp": datetime.now()
        })
    
    @abstractmethod
    async def process_message(self, message: str, workspace: Workspace) -> str:
        """Process message and generate response."""
        pass
    
    @abstractmethod
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        """Execute a specific task."""
        pass

# Concrete implementations

class NanobotLeader(SpecialistBot):
    """The Coordinator - your main companion."""
    
    def __init__(self):
        super().__init__(NANOBOT_ROLE)
        self.authority_level = "high"  # Can make decisions
        self.can_create_workspaces = True
        self.can_recruit_bots = True
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        # Implementation will integrate with LLM
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        # Execute coordination tasks (route messages, escalate, summarize)
        pass
    
    async def coordinate_workspace(self, workspace: Workspace) -> dict:
        """Run coordination mode while user is away."""
        # Coordinate bot-to-bot conversations
        # Make routine decisions
        # Escalate when needed
        pass

class ResearcherBot(SpecialistBot):
    """Navigator - deep research and analysis."""
    
    def __init__(self):
        super().__init__(RESEARCHER_ROLE)
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        # Implementation will integrate with LLM
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        # Execute research tasks
        pass

class CoderBot(SpecialistBot):
    """Gunner - code implementation."""
    
    def __init__(self):
        super().__init__(CODER_ROLE)
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        pass

class SocialBot(SpecialistBot):
    """Lookout - community engagement."""
    
    def __init__(self):
        super().__init__(SOCIAL_ROLE)
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        pass

class CreativeBot(SpecialistBot):
    """Artist - design and content creation."""
    
    def __init__(self):
        super().__init__(CREATIVE_ROLE)
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        pass

class AuditorBot(SpecialistBot):
    """Quartermaster - quality review."""
    
    def __init__(self):
        super().__init__(AUDITOR_ROLE)
    
    async def process_message(self, message: str, workspace: Workspace) -> str:
        pass
    
    async def execute_task(self, task: str, workspace: Workspace) -> dict:
        pass
```

**Acceptance Criteria:**
- All 4 bots instantiate correctly
- Role cards loaded properly
- Private memory tracking works
- Bot hierarchy/inheritance functional

---

### Phase 1 Success Metrics
- ✅ Workspace model tested and working
- ✅ Tag handler parses all tag types correctly
- ✅ Role cards defined for all 4 specialists
- ✅ Specialist bot base classes implemented
- ✅ Unit tests at 80%+ coverage for Phase 1 code

---

## Phase 2: Personalization (Week 3)

### Objectives
- Implement 5 personality themes
- Build interactive onboarding
- Integrate themes with SOUL.md
- Enable theme switching

### Deliverables

#### 2.1: Theme System
**File:** `nanobot/themes/theme_system.py`

```python
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any

class ThemeName(Enum):
    PIRATE_CREW = "pirate_crew"
    ROCK_BAND = "rock_band"
    SWAT_TEAM = "swat_team"
    PROFESSIONAL = "professional"
    SPACE_CREW = "space_crew"

@dataclass
class BotTheming:
    """Bot personality within a theme."""
    title: str  # "Captain", "Lead Singer", "Commander"
    personality: str  # Brief description
    greeting: str
    voice_directive: str
    emoji: str = ""

@dataclass
class Theme:
    """Complete personality theme for team."""
    name: ThemeName
    description: str
    nanobot: BotTheming
    researcher: BotTheming
    coder: BotTheming
    social: BotTheming
    auditor: BotTheming
    affinity_modifiers: Dict[str, float] = None
    
    def get_bot_theming(self, bot_name: str) -> BotTheming:
        """Get theming for a specific bot."""
        return getattr(self, bot_name)
```

**File:** `nanobot/themes/presets.py`

```python
PIRATE_CREW = Theme(
    name=ThemeName.PIRATE_CREW,
    description="Bold adventurers exploring uncharted territories",
    nanobot=BotTheming(
        title="Captain",
        personality="Commanding, bold, decisive",
        greeting="Ahoy! What treasure we seeking today?",
        voice_directive="Speak with authority and adventure spirit",
        emoji="🏴‍☠️"
    ),
    researcher=BotTheming(
        title="Navigator",
        personality="Explores unknown waters, maps territories",
        greeting="Charted these waters before, Captain. Beware the reef of misinformation.",
        voice_directive="Measured but adventurous, warns of dangers",
        emoji="🧭"
    ),
    # ... more bots
)

ROCK_BAND = Theme(
    name=ThemeName.ROCK_BAND,
    description="Creative team making hits together",
    nanobot=BotTheming(
        title="Lead Singer",
        personality="Charismatic frontman, sets the vibe",
        greeting="Hey! Ready to make some hits?",
        voice_directive="Charismatic and energetic",
        emoji="🎤"
    ),
    # ... more bots
)

SWAT_TEAM = Theme(
    name=ThemeName.SWAT_TEAM,
    description="Elite tactical unit handling critical operations",
    # ... all bots with tactical theming
)

PROFESSIONAL = Theme(
    name=ThemeName.PROFESSIONAL,
    description="Formal, structured, business-focused team",
    # ... all bots with professional theming
)

SPACE_CREW = Theme(
    name=ThemeName.SPACE_CREW,
    description="Exploratory team discovering new frontiers",
    # ... all bots with space exploration theming
)

AVAILABLE_THEMES = [PIRATE_CREW, ROCK_BAND, SWAT_TEAM, PROFESSIONAL, SPACE_CREW]
```

**File:** `nanobot/themes/theme_manager.py`

```python
class ThemeManager:
    """Manage theme selection and application."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.current_theme: Optional[Theme] = None
    
    def list_themes(self) -> List[Dict[str, str]]:
        """Return list of available themes with descriptions."""
        return [
            {
                "id": theme.name.value,
                "name": theme.name.value.replace("_", " ").title(),
                "description": theme.description,
            }
            for theme in AVAILABLE_THEMES
        ]
    
    def select_theme(self, theme_name: str) -> Theme:
        """Select a theme and apply it."""
        for theme in AVAILABLE_THEMES:
            if theme.name.value == theme_name:
                self.current_theme = theme
                self._apply_theme(theme)
                return theme
        raise ValueError(f"Unknown theme: {theme_name}")
    
    def _apply_theme(self, theme: Theme):
        """Apply theme to SOUL.md and bot configs."""
        # Update SOUL.md with new personality
        # Update role cards with new greetings/voice
        # Save to user config
        pass
    
    def get_current_theme(self) -> Optional[Theme]:
        """Get currently active theme."""
        return self.current_theme
```

**Acceptance Criteria:**
- 5 themes fully defined with all bots
- Theme manager loads and applies themes
- Themes can be switched without data loss
- Affinity modifiers work correctly

---

#### 2.2: Onboarding Wizard
**File:** `nanobot/cli/onboarding.py`

```python
import inquirer
from typing import Dict, List

class OnboardingWizard:
    """Interactive setup wizard for new users."""
    
    def run(self) -> Dict[str, Any]:
        """Run complete onboarding flow."""
        print("\n🤖 Welcome to nanobot! Let's set up your AI team.\n")
        
        # Step 1: Theme selection
        theme_choice = self._select_theme()
        
        # Step 2: Capability selection
        capabilities = self._select_capabilities()
        
        # Step 3: Team composition
        team = self._recommend_team(capabilities, theme_choice)
        
        # Step 4: Workspace setup
        self._create_general_workspace(team)
        
        return {
            "theme": theme_choice,
            "capabilities": capabilities,
            "team": team,
        }
    
    def _select_theme(self) -> str:
        """Guide user to choose personality theme."""
        themes = [
            ("🏴‍☠️ Pirate Crew (Bold, adventurous)", "pirate_crew"),
            ("🎸 Rock Band (Creative, collaborative)", "rock_band"),
            ("🎯 SWAT Team (Tactical, precise)", "swat_team"),
            ("💼 Professional Office (Formal, structured)", "professional"),
            ("🚀 Space Crew (Exploratory, technical)", "space_crew"),
        ]
        
        questions = [
            inquirer.List(
                'theme',
                message="Choose your team's personality theme:",
                choices=themes,
            ),
        ]
        
        answers = inquirer.prompt(questions)
        return answers['theme']
    
    def _select_capabilities(self) -> List[str]:
        """Let user choose what they need help with."""
        questions = [
            inquirer.Checkbox(
                'capabilities',
                message="What do you need help with?",
                choices=[
                    "Research and analysis",
                    "Coding and development",
                    "Social media management",
                    "Content creation",
                    "Project management",
                    "Quality review",
                ],
            ),
        ]
        
        answers = inquirer.prompt(questions)
        return answers['capabilities']
    
    def _recommend_team(self, capabilities: List[str], theme: str) -> Dict[str, Any]:
        """Recommend which specialists based on capabilities."""
        team = {"nanobot": {"role": "Coordinator"}}
        
        if any(c in capabilities for c in ["Research", "analysis"]):
            team["researcher"] = {"role": "Research and Analysis"}
        
        if any(c in capabilities for c in ["Coding", "development"]):
            team["coder"] = {"role": "Technical Implementation"}
        
        if any(c in capabilities for c in ["Social media", "Community"]):
            team["social"] = {"role": "Community Engagement"}
        
        if any(c in capabilities for c in ["Content", "Quality"]):
            team["auditor"] = {"role": "Quality and Review"}
        
        # Print recommendation
        print(f"\n✨ Recommended team for {theme.replace('_', ' ').title()}:")
        for bot, info in team.items():
            print(f"  - @{bot} ({info['role']})")
        
        # Ask for confirmation
        confirmed = inquirer.prompt([
            inquirer.Confirm('confirm', message="Create this team?", default=True)
        ])
        
        return team if confirmed['confirm'] else self._manual_team_selection()
    
    def _create_general_workspace(self, team: Dict[str, Any]):
        """Create #general workspace with selected team."""
        # Create workspace in system
        # Add all team members
        # Send greeting from nanobot
        pass
    
    def _manual_team_selection(self) -> Dict[str, Any]:
        """Allow manual selection if auto recommendation declined."""
        # Let user pick individual bots
        pass
```

**Acceptance Criteria:**
- Onboarding wizard guides through all steps
- Theme selection works
- Capability matching suggests appropriate bots
- Workspace created after onboarding
- User can see recommended team before confirming

---

#### 2.3: SOUL.md Integration
**File:** `nanobot/soul/soul_manager.py`

Integrate theme system with SOUL.md personality definition:

```python
class SoulManager:
    """Manage nanobot's personality in SOUL.md."""
    
    def __init__(self, soul_path: str):
        self.soul_path = soul_path
        self.soul_data = self._load_soul()
    
    def apply_theme(self, theme: Theme):
        """Update SOUL.md with theme personality."""
        # Get nanobot theming from theme
        bot_theming = theme.nanobot
        
        # Update soul content
        self.soul_data['title'] = bot_theming.title
        self.soul_data['personality'] = bot_theming.personality
        self.soul_data['greeting'] = bot_theming.greeting
        self.soul_data['voice_directive'] = bot_theming.voice_directive
        self.soul_data['theme'] = theme.name.value
        
        # Save updated SOUL.md
        self._save_soul()
    
    def get_current_personality(self) -> Dict[str, str]:
        """Get current personality settings."""
        return {
            "title": self.soul_data.get('title', 'nanobot'),
            "personality": self.soul_data.get('personality', ''),
            "voice": self.soul_data.get('voice_directive', ''),
            "theme": self.soul_data.get('theme', 'custom'),
        }
    
    def customize_personality(self, **kwargs):
        """Allow manual customization of personality."""
        for key, value in kwargs.items():
            if key in self.soul_data:
                self.soul_data[key] = value
        self._save_soul()
    
    def _load_soul(self) -> Dict:
        """Load SOUL.md and parse."""
        # Read SOUL.md file
        # Parse YAML frontmatter
        pass
    
    def _save_soul(self):
        """Save updated SOUL.md."""
        # Write changes back to file
        pass
```

**Acceptance Criteria:**
- Theme application updates SOUL.md
- SOUL.md maintains backward compatibility
- Users can see current theme
- Manual customization possible
- Theme switching preserves other user settings

---

### Phase 2 Success Metrics
- ✅ 5 themes fully defined and working
- ✅ Onboarding wizard completes successfully
- ✅ SOUL.md integration functional
- ✅ Theme switching works without data loss
- ✅ User can select theme or manually customize

---

## Phase 3: Memory (Week 4)

### Objectives
- Implement hybrid memory architecture
- Build shared memory layer
- Create private memory per bot
- Enable cross-pollination of learnings

### Key Files
- `nanobot/memory/shared_memory.py` - Shared facts, events, entities
- `nanobot/memory/private_memory.py` - Per-bot learnings
- `nanobot/memory/cross_pollination.py` - Promotion mechanism

### Implementation Notes

**Shared Memory Structure:**
- Events: "User prefers data-driven decisions" (with timestamp, confidence)
- Entities: Knowledge graph of people, organizations, concepts
- Facts: Verified truths with confidence scores
- Artifact chain: Structured handoffs between bots

**Private Memory Structure:**
- Learnings: Patterns discovered by individual bot
- Expertise: Domains where bot has proven competence
- Mistakes: Errors and how they were recovered from
- Confidence: Self-assessed competence level

**Cross-Pollination Logic:**
- When a bot accumulates 5+ lessons in a domain
- Synthesize into high-confidence fact
- Add to shared memory
- All other bots inherit learning without repeating mistake

---

## Phase 4: Coordination (Week 5)

### Objectives
- Implement coordinator mode
- Build escalation system
- Enable autonomous bot-to-bot conversations
- User notification preferences

### Key Components
- Coordinator role for nanobot
- Decision routing (escalate vs decide)
- Async message queuing
- Notification dispatch

---

## Phase 5: Polish (Week 6)

### Objectives
- Workspace archival
- Conversation summaries
- Performance optimization
- Complete documentation

### Tasks
- Auto-archive workspaces after 30 days inactivity
- AI-generated summaries for quick catch-up
- Database indexing and query optimization
- User guides, API docs, examples

---

## Cross-Phase Considerations

### Testing Strategy
- Unit tests for each component (80%+ coverage)
- Integration tests for multi-component workflows
- User acceptance testing with 10-15 beta users
- Performance testing with 100+ workspaces

### Documentation
- API documentation
- User guides per feature
- Architecture decision records (ADRs)
- Troubleshooting guides

### Rollout Strategy
1. **Alpha:** Internal team (Week 6)
2. **Beta:** 20-30 early adopters (Week 7-8)
3. **General availability:** Full release (Week 9+)

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Team dynamics too complex | Medium | High | Simplify affinities, test extensively |
| Memory conflicts | Medium | Medium | Clear conflict resolution rules |
| Autonomous decisions wrong | Medium | High | Conservative escalation thresholds |
| UX too complex | Low | High | Onboarding wizard, themes |
| Performance degradation | Low | Medium | Query optimization, caching |

---

## Success Criteria (Overall)

✅ Users can create workspaces with theme-based bots  
✅ Bots respect hard bans and constraints  
✅ Memory system shares learnings across team  
✅ Coordinator mode handles routine tasks  
✅ Average user setup time < 5 minutes  
✅ 80%+ user satisfaction in beta  
✅ Production-ready code quality  

---

## Next Steps (Immediate)

1. **Create GitHub issues** for each Phase 1 task
2. **Review and refine** data models with team
3. **Set up test infrastructure** (pytest, coverage, CI/CD)
4. **Begin Phase 1 implementation** with workspace model
5. **Schedule weekly reviews** to track progress

---

**Created:** February 12, 2026  
**Next Review:** February 19, 2026 (End of Week 1)  
**Plan Owner:** Rick Ovelar  

