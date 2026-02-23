"""Conversational user onboarding - fills USER.md naturally and introduces the team.

This module provides a conversational onboarding experience where the leader bot
gets to know the user while filling in their profile (USER.md).

Unlike CLI `nanofolks onboard` (initial setup), this is the IN-CHAT onboarding
that happens when the user first talks to the agent.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.table import Table

from nanofolks.models.role_card import BUILTIN_ROLES, RoleCardDomain
from nanofolks.teams import TeamManager

console = Console()


class OnboardingState(Enum):
    """States in the onboarding conversation."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    TEAM_INTRO = "team_intro"
    COMPLETED = "completed"


# Mapping domain to human-readable role descriptions
DOMAIN_DESCRIPTIONS = {
    RoleCardDomain.COORDINATION: "Coordinates the team, manages tasks, and delegates work",
    RoleCardDomain.RESEARCH: "Investigates topics, finds information, and analyzes data",
    RoleCardDomain.DEVELOPMENT: "Writes code, builds applications, and solves technical problems",
    RoleCardDomain.COMMUNITY: "Manages social media, engages with people, and handles communications",
    RoleCardDomain.DESIGN: "Creates designs, writes content, and produces creative assets",
    RoleCardDomain.QUALITY: "Reviews work, finds issues, and ensures quality standards",
}


@dataclass
class UserProfileAnswers:
    """Collected answers from the user during onboarding."""

    name: str = ""
    timezone: str = ""
    language: str = ""
    role: str = ""
    projects: str = ""
    tools: str = ""
    topics: str = ""
    team_name: str = ""
    communication_style: str = ""
    response_length: str = ""
    technical_level: str = ""


@dataclass
class ChatOnboarding:
    """Handles conversational user onboarding."""

    workspace_path: Path
    team_manager: TeamManager
    state: OnboardingState = OnboardingState.NOT_STARTED
    answers: UserProfileAnswers = field(default_factory=UserProfileAnswers)
    current_question: int = 0

    # Questions flow (maps to USER.md fields)
    QUESTIONS = [
        {
            "field": "name",
            "key": "name",
            "question": "What should I call you?",
            "follow_up": "Got it! And what's your {field}?",
        },
        {
            "field": "timezone",
            "key": "timezone",
            "question": "What timezone are you in? (e.g., UTC-5, America/New_York)",
            "skip_if": lambda a: not a.name,
        },
        {
            "field": "language",
            "key": "language",
            "question": "What language do you prefer? (e.g., English, Spanish)",
            "skip_if": lambda a: not a.name,
        },
        {
            "field": "role",
            "key": "role",
            "question": "So what do you do for a living?",
            "follow_up": "Nice! And what kind of {field} work do you do?",
        },
        {
            "field": "projects",
            "key": "projects",
            "question": "What kind of projects are you working on?",
            "skip_if": lambda a: not a.role,
        },
        {
            "field": "tools",
            "key": "tools",
            "question": "What tools do you use? (e.g., VS Code, Figma, Photoshop)",
            "skip_if": lambda a: not a.projects,
        },
        {
            "field": "topics",
            "key": "topics",
            "question": "What topics are you interested in?",
            "skip_if": lambda a: not a.tools,
        },
        {
            "field": "team_name",
            "key": "team_name",
            "question": "One more thing — would you like to call your team something cool? (e.g., 'The Ravagers', 'Dream Team') or just keep the default?",
            "skip_if": lambda a: not a.name,
        },
    ]

    def is_needed(self) -> bool:
        """Check if onboarding is needed."""
        return self.state in [OnboardingState.NOT_STARTED, OnboardingState.IN_PROGRESS]

    def check_if_needed(self) -> bool:
        """Check if USER.md needs onboarding (is empty or has defaults)."""
        user_file = self.workspace_path / "USER.md"

        if not user_file.exists():
            return True

        content = user_file.read_text()

        # Check if user has filled in real info (not placeholders)
        placeholders = ["(your name)", "(your timezone)", "(your role)"]
        has_real_data = not any(p in content for p in placeholders)

        return not has_real_data

    def get_next_question(self) -> dict | None:
        """Get the next question in the flow."""
        while self.current_question < len(self.QUESTIONS):
            q = self.QUESTIONS[self.current_question]

            # Check skip condition
            skip_fn = q.get("skip_if")
            if skip_fn and skip_fn(self.answers):
                self.current_question += 1
                continue

            return q

        return None

    def process_answer(self, user_message: str) -> str:
        """Process user's answer and return leader's response."""
        question = self.get_next_question()

        if not question:
            # No more questions, move to team intro
            self.state = OnboardingState.TEAM_INTRO
            return self._get_team_intro_message()

        # Store the answer
        field_name = question["key"]
        setattr(self.answers, field_name, user_message)

        # Save to USER.md
        self._save_to_user_md()

        # Move to next question
        self.current_question += 1

        # Get next question for response
        next_q = self.get_next_question()

        if next_q:
            # Build natural response
            response = self._build_natural_response(question, next_q)
        else:
            # All questions done, move to team intro
            self.state = OnboardingState.TEAM_INTRO
            response = self._get_team_intro_message()

        return response

    def _build_natural_response(self, answered_q: dict, next_q: dict) -> str:
        """Build a natural leader response after user's answer."""
        # Simple responses based on question type
        responses = []

        if answered_q["key"] == "name":
            responses.append(f"Gotcha, {self.answers.name}!")
            responses.append(f"Alright {self.answers.name}, nice to meet you!")

        elif answered_q["key"] == "role":
            responses.append(f"Interesting! So you're a {self.answers.role}.")

        elif answered_q["key"] == "projects":
            responses.append("Awesome! Sounds like interesting work.")

        elif answered_q["key"] == "tools":
            responses.append("Cool tools! I know some of those.")

        elif answered_q["key"] == "team_name":
            if self.answers.team_name:
                responses.append(f"Love it! '{self.answers.team_name}' it is!")
            else:
                responses.append("Got it, we'll keep the original name!")

        # Add next question
        responses.append(f"\n{next_q['question']}")

        return " ".join(responses)

    def _save_to_user_md(self) -> None:
        """Save collected answers to USER.md."""
        user_file = self.workspace_path / "USER.md"

        content = f"""# User Profile

Information about the user to help personalize interactions.

## Basic Information

- **Name**: {self.answers.name or "(your name)"}
- **Timezone**: {self.answers.timezone or "(your timezone)"}
- **Language**: {self.answers.language or "(preferred language)"}
- **Team Name**: {self.answers.team_name or "(default from team)"}

## Preferences

### Communication Style

- [x] {self.answers.communication_style or "Casual"}
- [ ] Professional
- [ ] Technical

### Response Length

- [x] {self.answers.response_length or "Adaptive based on question"}
- [ ] Brief and concise
- [ ] Detailed explanations

### Technical Level

- [x] {self.answers.technical_level or "Intermediate"}
- [ ] Beginner
- [ ] Expert

## Work Context

- **Primary Role**: {self.answers.role or "(your role)"}
- **Main Projects**: {self.answers.projects or "(what you're working on)"}
- **Tools You Use**: {self.answers.tools or "(tools and software)"}

## Topics of Interest

{self._format_topics()}

## Special Instructions

{self._format_special_instructions()}

---

*Auto-filled during onboarding.*
"""

        user_file.write_text(content)

    def _format_topics(self) -> str:
        """Format topics as bullet points."""
        if self.answers.topics:
            lines = self.answers.topics.split(",")
            return "\n".join(f"- {line.strip()}" for line in lines if line.strip())
        return "-\n-\n-"

    def _format_special_instructions(self) -> str:
        """Format special instructions."""
        # Could add more context later
        return "(Any specific instructions for how the assistant should behave)"

    def _get_team_intro_message(self) -> str:
        """Get the team introduction message."""
        table = self._build_team_table()

        # Get the team's name (custom or default from team)
        team = self.team_manager.get_current_team()
        default_team_name = team["name"].replace("_", " ").title() if team else "Crew"
        team_name = self.answers.team_name or default_team_name

        return f"""Great to know you better, {self.answers.name or "friend"}! 🎉

Now, let me introduce you to {team_name}!

{table}

That's your team! We're all here to help you with your {self.answers.projects or "work"}.

Need more details on any particular crew member? Just ask!"""

    def _build_team_table(self) -> Table:
        """Build a team-styled table of all bots."""
        table = Table(show_header=True, header_style="bold magenta")

        # Add columns: Name, Title, Role
        table.add_column("Name", style="cyan", width=20)
        table.add_column("Title", style="yellow", width=15)
        table.add_column("Role", style="green", width=50)

        # Ensure team is loaded
        self.team_manager.get_current_team()

        # Get all bots in order
        bot_order = ["leader", "researcher", "coder", "creative", "social", "auditor"]

        for bot_role in bot_order:
            # Get team profile info
            team_profile = self.team_manager.get_bot_team_profile(bot_role)

            bot_name = team_profile.get("bot_name", team_profile.get("bot_title", bot_role))
            bot_title = team_profile.get("bot_title", bot_role)
            emoji = team_profile.get("emoji", "")

            # Get role description from domain
            role_card = BUILTIN_ROLES.get(bot_role)
            if role_card:
                domain = role_card.domain
                role_desc = DOMAIN_DESCRIPTIONS.get(domain, domain.value)
            else:
                role_desc = "Helping the team"

            # Add emoji to name
            display_name = f"{emoji} {bot_name}" if emoji else bot_name

            table.add_row(display_name, bot_title, role_desc)

        return table

    def get_team_intro_only(self) -> str:
        """Get just the team introduction (for later requests)."""
        self.state = OnboardingState.TEAM_INTRO
        return self._get_team_intro_message()

    def introduce_bot(self, bot_role: str) -> str:
        """Introduce a specific bot in detail."""
        # Get team profile info
        team_profile = self.team_manager.get_bot_team_profile(bot_role)

        bot_name = team_profile.get("bot_name", team_profile.get("bot_title", bot_role))
        bot_title = team_profile.get("bot_title", bot_role)
        emoji = team_profile.get("emoji", "")
        personality = team_profile.get("personality", "")
        greeting = team_profile.get("greeting", "")

        # Get role description
        role_card = BUILTIN_ROLES.get(bot_role)
        if role_card:
            domain = role_card.domain
            role_desc = DOMAIN_DESCRIPTIONS.get(domain, domain.value)

            # Get capabilities
            caps = []
            if role_card.capabilities.can_access_web:
                caps.append("web search")
            if role_card.capabilities.can_exec_commands:
                caps.append("run commands")
            if role_card.capabilities.can_send_messages:
                caps.append("send messages")
            if role_card.capabilities.can_do_heartbeat:
                caps.append("scheduled tasks")

            capabilities = ", ".join(caps) if caps else "various tools"
        else:
            role_desc = "Helping the team"
            capabilities = "various tools"

        intro = f"""
**{emoji} {bot_name} - {bot_title}**

_{role_desc}_

{personality}

They can: {capabilities}

{greeting}
"""
        return intro.strip()

    def complete(self) -> None:
        """Mark onboarding as complete."""
        self.state = OnboardingState.COMPLETED

    def to_dict(self) -> dict:
        """Serialize state for saving."""
        return {
            "state": self.state.value,
            "answers": {
                "name": self.answers.name,
                "timezone": self.answers.timezone,
                "language": self.answers.language,
                "role": self.answers.role,
                "projects": self.answers.projects,
                "tools": self.answers.tools,
                "topics": self.answers.topics,
                "team_name": self.answers.team_name,
            },
            "current_question": self.current_question,
        }

    @classmethod
    def from_dict(
        cls, data: dict, workspace_path: Path, team_manager: TeamManager
    ) -> "ChatOnboarding":
        """Deserialize from saved state."""
        onboarding = cls(workspace_path, team_manager)
        onboarding.state = OnboardingState(data.get("state", "not_started"))
        onboarding.current_question = data.get("current_question", 0)

        answers = data.get("answers", {})
        onboarding.answers = UserProfileAnswers(**answers)

        return onboarding
