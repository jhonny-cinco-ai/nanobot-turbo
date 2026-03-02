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
    location: str = ""
    language: str = ""
    work: str = ""
    help: str = ""
    more_details: bool = False
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
            "field": "location",
            "key": "location",
            "question": "Where are you located? (City or country is fine — you can say 'skip')",
            "skip_if": lambda a: not a.name,
        },
        {
            "field": "language",
            "key": "language",
            "question": "What language do you prefer? (You can say 'skip')",
            "skip_if": lambda a: not a.name,
        },
        {
            "field": "work",
            "key": "work",
            "question": "What are you working on these days? (You can say 'skip')",
        },
        {
            "field": "help",
            "key": "help",
            "question": "How should we help you most right now? (You can say 'skip')",
            "skip_if": lambda a: not a.work,
        },
        {
            "field": "more_details",
            "key": "more_details",
            "question": "Want to add a few more details (tools, topics, team name)? (yes/no)",
            "skip_if": lambda a: not a.name,
        },
        {
            "field": "tools",
            "key": "tools",
            "question": "What tools do you use? (Optional)",
            "skip_if": lambda a: not a.more_details,
        },
        {
            "field": "topics",
            "key": "topics",
            "question": "Any topics you're into? (Optional)",
            "skip_if": lambda a: not a.more_details,
        },
        {
            "field": "team_name",
            "key": "team_name",
            "question": "Want to name your team? (Optional)",
            "skip_if": lambda a: not a.more_details,
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
        placeholders = ["(your name)", "(your location)", "(what you're working on)"]
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

        # Store the answer (support skip)
        field_name = question["key"]
        normalized = user_message.strip()
        skip_inputs = {"skip", "skip for now", "pass", "n/a"}
        if normalized.lower() in skip_inputs:
            if field_name == "more_details":
                setattr(self.answers, field_name, False)
            else:
                setattr(self.answers, field_name, "")
        elif field_name == "more_details":
            yes_inputs = {"y", "yes", "yeah", "yep", "sure", "ok", "okay"}
            setattr(self.answers, field_name, normalized.lower() in yes_inputs)
        else:
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
            responses.append("You’ve got a full team backing you — I’ll introduce everyone soon.")

        elif answered_q["key"] == "work":
            responses.append("Awesome — that gives us good context.")

        elif answered_q["key"] == "help":
            responses.append("Got it — we’ll focus on that.")

        elif answered_q["key"] == "tools":
            responses.append("Cool tools! I know some of those.")

        elif answered_q["key"] == "more_details":
            if self.answers.more_details:
                responses.append("Great — just a couple quick ones.")
            else:
                responses.append("No problem — we can add details later.")

        elif answered_q["key"] == "team_name":
            if self.answers.team_name:
                responses.append(f"Love it! '{self.answers.team_name}' it is!")
            else:
                responses.append("Got it, we'll keep the original name!")

        # Add next question
        responses.append(next_q["question"])

        return " ".join(responses)

    def _save_to_user_md(self) -> None:
        """Save collected answers to USER.md."""
        user_file = self.workspace_path / "USER.md"

        content = f"""# User Profile

Information about the user to help personalize interactions.

## Basic Information

- **Name**: {self.answers.name or "(your name)"}
- **Location**: {self.answers.location or "(your location)"}
- **Language**: {self.answers.language or "(preferred language)"}
- **Team Name**: {self.answers.team_name or "(default from team)"}

## Preferences

- **Communication Style**: {self.answers.communication_style or "Casual"}
- **Response Length**: {self.answers.response_length or "Adaptive based on question"}
- **Technical Level**: {self.answers.technical_level or "Intermediate"}

## Work Context

- **Current Focus**: {self.answers.work or "(what you're working on)"}
- **How We Should Help**: {self.answers.help or "(what you want help with)"}
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
        default_team_name = team["name"].replace("_", " ").title() if team else "Team"
        team_name = self.answers.team_name or default_team_name

        return f"""Great to know you better, {self.answers.name or "friend"}! 🎉

Now, let me introduce you to {team_name}!

{table}

That's your team! We're all here to help you with your {self.answers.work or "work"}.

Need more details on any particular team member? Just ask!"""

    def _build_team_table(self) -> Table:
        """Build a team-styled table of all bots."""
        table = Table(show_header=True, header_style="bold magenta")

        # Add columns: Name, Title, Role, Focus
        table.add_column("Name", style="cyan", width=20)
        table.add_column("Title", style="yellow", width=18)
        table.add_column("Role", style="magenta", width=12)
        table.add_column("Focus", style="green", width=45)

        # Ensure team is loaded
        self.team_manager.get_current_team()

        # Get all bots in order
        bot_order = ["leader", "researcher", "coder", "creative", "social", "auditor"]

        for bot_role in bot_order:
            # Get team profile info
            team_profile = self.team_manager.get_bot_team_profile(
                bot_role, workspace_path=self.workspace_path
            )

            if not team_profile:
                continue

            bot_name = team_profile.bot_name or team_profile.bot_title or bot_role
            bot_title = team_profile.bot_title or bot_role
            emoji = team_profile.emoji or ""

            # Get role description from domain
            role_card = BUILTIN_ROLES.get(bot_role)
            if role_card:
                domain = role_card.domain
                role_desc = DOMAIN_DESCRIPTIONS.get(domain, domain.value)
            else:
                role_desc = "Helping the team"

            # Add emoji to name
            display_name = f"{emoji} {bot_name}" if emoji else bot_name

            table.add_row(display_name, bot_title, f"@{bot_role}", role_desc)

        return table

    def get_team_intro_only(self) -> str:
        """Get just the team introduction (for later requests)."""
        self.state = OnboardingState.TEAM_INTRO
        return self._get_team_intro_message()

    def introduce_bot(self, bot_role: str) -> str:
        """Introduce a specific bot in detail."""
        # Get team profile info
        team_profile = self.team_manager.get_bot_team_profile(
            bot_role, workspace_path=self.workspace_path
        )

        if not team_profile:
            bot_name = bot_role
            bot_title = bot_role
            emoji = ""
            personality = ""
            greeting = ""
        else:
            bot_name = team_profile.bot_name or team_profile.bot_title or bot_role
            bot_title = team_profile.bot_title or bot_role
            emoji = team_profile.emoji or ""
            personality = team_profile.personality or ""
            greeting = team_profile.greeting or ""

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
            if role_card.capabilities.can_do_routines:
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
                "location": self.answers.location,
                "language": self.answers.language,
                "work": self.answers.work,
                "help": self.answers.help,
                "more_details": self.answers.more_details,
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

        answers = dict(data.get("answers", {}))
        valid_fields = set(UserProfileAnswers.__dataclass_fields__.keys())
        filtered = {k: v for k, v in answers.items() if k in valid_fields}
        onboarding.answers = UserProfileAnswers(**filtered)

        return onboarding

    def extract_info_from_message(self, message: str) -> None:
        """Extract user information from their message using simple heuristics."""
        message_lower = message.lower()

        # Extract name - look for patterns like "I'm Rick", "My name is Rick", "Call me Rick"
        if not self.answers.name:
            import re

            name_patterns = [
                r"i['\']?m\s+(\w+)",
                r"my name is\s+(\w+)",
                r"call me\s+(\w+)",
                r"name['\']?s?\s+(\w+)",
            ]
            for pattern in name_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    self.answers.name = match.group(1).capitalize()
                    break

        # Extract location - look for "from [place]" or "in [place]"
        if not self.answers.location:
            import re

            location_patterns = [
                r"from\s+([\w\s,]+?)(?:\.|,|$)",
                r"in\s+([\w\s,]+?)(?:\.|,|$)",
                r"located in\s+([\w\s,]+?)(?:\.|,|$)",
            ]
            for pattern in location_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    self.answers.location = match.group(1).strip().title()
                    break

        # Extract what they're working on
        if not self.answers.work:
            work_keywords = [
                "working on",
                "building",
                "creating",
                "project",
                "startup",
                "app",
                "website",
            ]
            for keyword in work_keywords:
                if keyword in message_lower:
                    # Take the sentence containing the keyword
                    sentences = message.split(".")
                    for sentence in sentences:
                        if keyword in sentence.lower():
                            self.answers.work = sentence.strip()
                            break
                    break

        # Extract help needed
        if not self.answers.help:
            help_keywords = ["help", "need", "want", "looking for", "trying to"]
            for keyword in help_keywords:
                if keyword in message_lower:
                    sentences = message.split(".")
                    for sentence in sentences:
                        if keyword in sentence.lower() and len(sentence.strip()) > 10:
                            self.answers.help = sentence.strip()
                            break
                    break

        # Save to USER.md if we got new info
        self._save_to_user_md()

    def has_all_required_info(self) -> bool:
        """Check if we have all the minimum required information."""
        # Required: name, location, work, help
        return bool(
            self.answers.name and self.answers.location and self.answers.work and self.answers.help
        )
