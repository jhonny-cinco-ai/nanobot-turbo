"""Unified onboarding wizard for multi-agent orchestration setup.

This module provides a unified CLI wizard that guides new users through:
1. Keyring security check (optional setup)
2. Provider selection + model selection
3. Network & security info (ports, Tailscale)
4. Team selection (with team description)
5. #general room creation + SOUL/IDENTITY/ROLE generation

Uses typer and rich for interactive prompts and rich terminal output.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from nanofolks.models import Room, RoomType
from nanofolks.security.keyring_manager import (
    get_keyring_info,
    init_gnome_keyring,
    is_keyring_available,
)
from nanofolks.soul import SoulManager
from nanofolks.teams import TeamManager
from nanofolks.templates import get_team, list_teams

console = Console()


class OnboardingWizard:
    """Unified onboarding wizard for multi-agent team setup.

    Complete wizard that guides users through:
    1. Keyring security check (optional setup)
    2. Provider selection + model selection
    3. Network & security info
    4. Team selection with full team description
    5. Room creation + SOUL/IDENTITY/ROLE generation
    """

    PROVIDERS = {
        "1": ("openrouter", "OpenRouter - Access multiple AI models (recommended)"),
        "2": ("anthropic", "Anthropic - Claude models"),
        "3": ("openai", "OpenAI - GPT models"),
        "4": ("groq", "Groq - Fast inference"),
        "5": ("deepseek", "DeepSeek - Chinese models"),
        "6": ("moonshot", "Moonshot - Kimi models"),
        "7": ("gemini", "Gemini - Google AI models"),
    }

    def __init__(self, non_interactive: bool = False):
        """Initialize the onboarding wizard."""
        self.team_manager = TeamManager()
        self.selected_team: Optional[str] = None
        self.soul_manager: Optional[SoulManager] = None
        self.config_result: Dict = {}
        self._non_interactive = non_interactive

    def _is_non_interactive(self) -> bool:
        env_flag = os.getenv("NANOFOLKS_ONBOARD_NONINTERACTIVE")
        if env_flag:
            return env_flag.lower() in {"1", "true", "yes", "on"}
        if self._non_interactive:
            return True
        return not sys.stdin.isatty()

    def _prompt(self, text: str, **kwargs) -> str:
        if self._is_non_interactive():
            default = kwargs.get("default")
            if default is not None:
                return str(default)
            choices = kwargs.get("choices")
            if choices:
                return str(choices[0])
            return ""
        return Prompt.ask(text, **kwargs)

    def _confirm(self, text: str, **kwargs) -> bool:
        if self._is_non_interactive():
            return bool(kwargs.get("default", False))
        return Confirm.ask(text, **kwargs)

    def run(self, workspace_path: Optional[Path] = None) -> Dict:
        """Run the complete onboarding wizard.

        Args:
            workspace_path: Optional workspace path for SOUL file generation and room storage

        Returns:
            Dictionary containing:
                - provider: selected provider name
                - model: selected model
                - team: selected team name
                - workspace_path: workspace path used
                - general_room: created Room object for #general
        """
        self._show_welcome()

        steps = [
            self._check_keyring_status,
            self._configure_provider,
            self._select_team,
            self._confirm_and_create
        ]
        
        step_idx = 0
        while step_idx < len(steps):
            result = steps[step_idx]()
            
            if result == "back":
                # Go back one step, but don't go below 0
                step_idx = max(0, step_idx - 1)
                # If we went back to the very beginning, show welcome again
                if step_idx == 0:
                    self._show_welcome()
            else:
                step_idx += 1

        # Create the #general room
        general_room = self.create_general_room()

        # Apply team selection to workspace if path provided
        if workspace_path:
            self._apply_team_to_workspace(workspace_path)
            # Save the general room to disk
            self._save_room(general_room, workspace_path)

        return {
            "provider": self.config_result.get("provider"),
            "model": self.config_result.get("model"),
            "team": self.selected_team,
            "workspace_path": str(workspace_path) if workspace_path else None,
            "general_room": general_room,
        }

    def _show_welcome(self) -> None:
        """Display welcome panel."""
        console.print(
            Panel.fit(
                "[bold bright_magenta]🚀 Welcome to nanofolks![/bold bright_magenta]\n\n"
                "Let's set up your multi-agent team in just a few steps.\n"
                "This wizard will guide you through:\n"
                "  1. [bold]Security[/bold] - Keyring setup for secure API key storage\n"
                "  2. [bold]AI Provider[/bold] + Model\n"
                "  3. [bold]Network Security[/bold] (Tailscale + secure ports)\n"
                "  4. [bold]Team[/bold] - Choose your crew's personality\n"
                "  5. [bold]Launch[/bold] - Create your workspace and crew",
                title="🎉",
                border_style="bright_magenta",
            )
        )
        console.print()

    def _check_keyring_status(self) -> None:
        """Check and display keyring status."""
        from rich import box

        console.print("[dim]Initializing security checks...[/dim]")

        loading_messages = [
            "Analyzing operative system...",
            "Checking keyring configuration...",
            "This could take a few moments...",
            "Don't worry, our bots are getting ready...",
            "Just a tiny bit more...",
        ]

        # Start with first message
        current_msg = loading_messages[0]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(current_msg, total=None)

            # Rotate messages every 0.8 seconds
            import time
            start_time = time.time()
            msg_index = 0
            min_duration = 2.5  # Minimum time to show spinner

            while True:
                elapsed = time.time() - start_time
                # Cycle through messages using modulo
                new_index = int(elapsed / 0.8) % len(loading_messages)

                if new_index != msg_index:
                    msg_index = new_index
                    progress.update(task, description=loading_messages[msg_index])

                # Run for minimum duration
                if elapsed > min_duration:
                    break

                time.sleep(0.1)

            info = get_keyring_info()
            progress.update(task, description="Done!", completed=True)

        status_table = Table(title="Keyring Status", box=box.ROUNDED, show_header=False)
        status_table.add_column("Property", style="bright_magenta")
        status_table.add_column("Value", style="white")

        status_table.add_row("OS", f"{info.os_name} ({info.os_detail})")
        status_table.add_row("Backend", info.keyring_backend)

        if info.keyring_available:
            status_table.add_row("Status", "[green]✓ Available[/green]")
        else:
            status_table.add_row("Status", "[yellow]⚠ Not available[/yellow]")
            if info.setup_instructions:
                status_table.add_row("Fix", info.setup_instructions)

        console.print(status_table)
        console.print()

        if info.needs_setup:
            console.print("[yellow]⚠ Headless Linux server detected[/yellow]")
            init_default = False if self._is_non_interactive() else True
            init_keyring = self._confirm(
                "Initialize GNOME keyring now? (required for secure API key storage)",
                default=init_default,
            )

            if init_keyring:
                password = self._prompt("Enter a password to unlock the keyring", password=True)
                if password:
                    console.print("\n[bright_magenta]Initializing GNOME keyring...[/bright_magenta]")
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=console,
                        transient=True,
                    ) as progress:
                        task = progress.add_task("Initializing keyring...", total=None)
                        success = init_gnome_keyring(password)
                        progress.update(task, completed=True)
                    
                    if success:
                        console.print("[green]✓ GNOME keyring initialized successfully![/green]\n")
                    else:
                        console.print("[red]✗ Failed to initialize keyring[/red]")
                        console.print(
                            "[dim]You can run 'nanofolks security init-keyring' later[/dim]\n"
                        )

    def _configure_provider(self) -> None:
        """Step 1: Configure AI provider and API key."""
        console.print("[bold bright_magenta]Step 2: AI Provider Setup[/bold bright_magenta]\n")
        console.print("Choose the AI provider for your crew:\n")

        for key, (name, desc) in self.PROVIDERS.items():
            console.print(f"  [{key}] {desc}")
        console.print("  [b] Back to welcome")

        provider_choice = self._prompt(
            "\nSelect provider", choices=list(self.PROVIDERS.keys()) + ["b"], default="1"
        )
        
        if provider_choice == "b":
            return "back"
            
        provider_name, provider_desc = self.PROVIDERS[provider_choice]

        # Get API key - allow pasting by default
        console.print(f"\n[dim]{provider_desc}[/dim]")
        console.print("[dim]Tip: You can paste your API key (Ctrl+V or Cmd+V)[/dim]")
        api_key = self._prompt(f"Enter your {provider_name.title()} API key", password=False)

        if api_key:
            key_preview = api_key[:12] + "..." if len(api_key) > 12 else api_key
            console.print(f"[dim]Received: {key_preview}[/dim]\n")

        if not api_key:
            console.print(
                "[yellow]⚠ No API key provided. You can configure this later with: nanofolks configure[/yellow]\n"
            )
            self.config_result["provider"] = None
            self.config_result["api_key"] = None
        else:
            # Save API key
            console.print(f"\n[bright_magenta]Saving API key for {provider_name}...[/bright_magenta]")
            self.config_result["provider"] = provider_name
            self.config_result["api_key"] = api_key

            # Configure using UpdateConfigTool
            asyncio.run(self._save_provider_config(provider_name, api_key))
            console.print(f"[green]✓ {provider_name.title()} configured![/green]\n")

        # Model selection
        console.print("[bold]Select Model[/bold]")
        console.print("Choose the default model for your crew:\n")

        models = self._get_available_models(provider_name)
        for i, model in enumerate(models[:5], 1):
            console.print(f"  [{i}] {model}")
        console.print("  [c] Custom model")
        console.print("  [b] Back")

        model_choice = self._prompt(
            "\nSelect model",
            choices=[str(i) for i in range(1, min(6, len(models) + 1))] + ["c", "b"],
            default="1",
        )

        if model_choice == "b":
            return self._configure_provider()
        
        if model_choice == "c":
            primary_model = self._prompt("Enter custom model name")
        else:
            primary_model = models[int(model_choice) - 1]

        self.config_result["model"] = primary_model

        # Save model selection
        if primary_model and api_key:
            asyncio.run(self._save_model_config(primary_model))
            console.print(f"[green]✓ Primary model set to {primary_model}[/green]\n")

        # Smart routing is enabled by default; apply provider-specific tiers.
        if provider_name:
            asyncio.run(self._save_routing_config(True, provider_name))
            console.print(
                "[dim]Smart routing enabled by default (edit anytime: nanofolks configure)[/dim]\n"
            )

        # Network & Security configuration
        self._configure_network_security()

    def _configure_network_security(self) -> None:
        """Step 3: Configure Network & Security."""
        console.print("[bold bright_magenta]Step 3: Network & Security[/bold bright_magenta]\n")
        console.print("""
[dim]Configure how nanofolks services are accessed:[/dim]
  • Dashboard & bridge will use secure defaults
  • Random ports (8000-9000) to avoid detection
  • Tailscale IP if available for private access
        """)

        # Detect current network status
        try:
            from nanofolks.utils.network import find_free_port, get_best_ip, get_tailscale_ip

            tailscale_ip = get_tailscale_ip()
            best_ip = get_best_ip()

            if tailscale_ip:
                console.print(f"\n[green]✓ Tailscale detected: {tailscale_ip}[/green]")
                console.print("[dim]Services will be accessible via your Tailscale network[/dim]")
            else:
                console.print(f"\n[dim]Using private IP: {best_ip}[/dim]")
                console.print("[dim]For better security, consider installing Tailscale[/dim]")

            # Show what ports will be used
            dashboard_port = find_free_port()
            bridge_port = find_free_port()

            console.print("\n[dim]Secure defaults configured:[/dim]")
            console.print(f"  • Dashboard: http://{tailscale_ip or best_ip}:{dashboard_port}")
            console.print(f"  • WhatsApp bridge: ws://{tailscale_ip or best_ip}:{bridge_port}")

        except Exception as e:
            console.print(f"[yellow]⚠ Could not detect network: {e}[/yellow]")

        console.print("\n[dim]Network auto-configured on first run.[/dim]")

        # Ask about Tailscale installation
        console.print()
        if not tailscale_ip:
            install_tailscale = self._confirm(
                "Install Tailscale for private network access?", default=False
            )
            if install_tailscale:
                self._install_tailscale_guide()

    def _install_tailscale_guide(self) -> None:
        """Show guide for installing Tailscale."""
        console.print(
            Panel.fit(
                """
[bold bright_magenta]Install Tailscale:[/bold bright_magenta]

[bold]macOS:[/bold]
  brew install tailscale
  tailscale up

[bold]Linux:[/bold]
  curl -fsSL https://tailscale.com/install.sh | sh
  tailscale up

[bold]Windows:[/bold]
  Download from https://tailscale.com/download

After install, run: [bold]tailscale up[/bold]
Then restart nanofolks for secure access.
            """,
                title="Tailscale Setup Guide",
                border_style="bright_magenta",
            )
        )

    async def _save_routing_config(self, enabled: bool, provider: str = "openrouter") -> None:
        """Save routing configuration with provider-specific tiers.

        Args:
            enabled: Whether to enable routing
            provider: Provider name for selecting appropriate models
        """
        try:
            from nanofolks.agent.tools.update_config import UpdateConfigTool
            from nanofolks.config.schema import get_routing_tiers_for_provider

            tool = UpdateConfigTool()

            # Enable routing
            await tool.execute(path="routing.enabled", value=enabled)

            # Get provider-specific tiers
            tiers = get_routing_tiers_for_provider(provider)

            # Save each tier's model
            await tool.execute(path="routing.tiers.simple.model", value=tiers.simple.model)
            await tool.execute(
                path="routing.tiers.simple.secondary_model", value=tiers.simple.secondary_model
            )

            await tool.execute(path="routing.tiers.medium.model", value=tiers.medium.model)
            await tool.execute(
                path="routing.tiers.medium.secondary_model", value=tiers.medium.secondary_model
            )

            await tool.execute(path="routing.tiers.complex.model", value=tiers.complex.model)
            await tool.execute(
                path="routing.tiers.complex.secondary_model", value=tiers.complex.secondary_model
            )

            await tool.execute(path="routing.tiers.reasoning.model", value=tiers.reasoning.model)
            await tool.execute(
                path="routing.tiers.reasoning.secondary_model",
                value=tiers.reasoning.secondary_model,
            )

            await tool.execute(path="routing.tiers.coding.model", value=tiers.coding.model)
            await tool.execute(
                path="routing.tiers.coding.secondary_model", value=tiers.coding.secondary_model
            )

        except Exception as e:
            console.print(f"[yellow]⚠ Could not save routing config: {e}[/yellow]")

    async def _save_provider_config(self, provider: str, api_key: str) -> None:
        """Save provider API key to config using the secret store (OS keyring)."""
        try:
            from nanofolks.security.keyring_manager import is_keyring_available
            from nanofolks.security.secret_store import get_secret_store

            # Try to store in OS keyring (secure by default)
            keyring_available = is_keyring_available()

            if keyring_available:
                store = get_secret_store()
                store.set(provider, api_key)

                # Save empty marker to config (key loaded from keyring)
                from nanofolks.agent.tools.update_config import UpdateConfigTool

                tool = UpdateConfigTool()
                await tool.execute(path=f"providers.{provider}.apiKey", value="")

                console.print(
                    "[dim]API key saved to OS Keychain/Keyring (not in config file)[/dim]"
                )
            else:
                # Fallback: store in config file (less secure!)
                from nanofolks.agent.tools.update_config import UpdateConfigTool

                tool = UpdateConfigTool()
                await tool.execute(path=f"providers.{provider}.apiKey", value=api_key)
                console.print("[yellow]⚠ WARNING: OS Keyring unavailable![/yellow]")
                console.print("[yellow]⚠ API key stored in config file (less secure)[/yellow]")
                console.print(
                    "[dim]Recommendation: Set up your OS keyring for better security[/dim]"
                )
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save API key: {e}[/yellow]")

    async def _save_model_config(self, model: str) -> None:
        """Save default model to config."""
        try:
            from nanofolks.agent.tools.update_config import UpdateConfigTool

            tool = UpdateConfigTool()
            await tool.execute(path="agents.defaults.model", value=model)
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save model: {e}[/yellow]")

    def _get_available_models(self, provider: str) -> list:
        """Get available models for a provider."""
        # Simplified - in production would query provider schema
        defaults = {
            "openrouter": [
                # Anthropic
                "openrouter/anthropic/claude-3.5-haiku",
                "openrouter/anthropic/claude-3.5-sonnet",
                "openrouter/anthropic/claude-opus-4-5",
                # OpenAI
                "openrouter/openai/gpt-4o",
                "openrouter/openai/gpt-4o-mini",
                "openrouter/openai/o1",
                "openrouter/openai/o1-mini",
                # DeepSeek
                "openrouter/deepseek/deepseek-chat",
                "openrouter/deepseek/deepseek-chat-v3-0324",
                # Google
                "openrouter/google/gemini-pro-1.5",
                "openrouter/google/gemini-flash-1.5",
                # Meta
                "openrouter/meta-llama/llama-3.3-70b-instruct",
                "openrouter/meta-llama/llama-3.1-8b-instruct",
                # Qwen
                "openrouter/qwen/qwen-2.5-72b-instruct",
                "openrouter/qwen/qwen-2.5-32b-instruct",
                # Mistral
                "openrouter/mistralai/mistral-small-3.1",
                # Cohere
                "openrouter/cohere/command-a",
            ],
            "anthropic": [
                "anthropic/claude-3.5-sonnet-20241022",
                "anthropic/claude-3-opus-20240229",
                "anthropic/claude-3-haiku-20240307",
            ],
            "openai": ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/o1", "openai/o1-mini"],
            "groq": ["groq/llama-3.3-70b", "groq/mixtral-8x7b-32768"],
            "deepseek": ["deepseek/deepseek-chat", "deepseek/deepseek-chat-v3-0324"],
            "moonshot": ["moonshot/kimi-k2.5"],
            "gemini": ["gemini-2.0-flash-exp", "gemini-1.5-pro"],
        }
        return defaults.get(provider, ["default-model"])

    def _select_team(self) -> None:
        """Interactive team selection."""
        console.print("[bold bright_magenta]Step 4: Choose Your Crew Team[/bold bright_magenta]\n")

        teams = list_teams()
        [t["name"] for t in teams]

        # First show just the crew team options
        console.print("Choose your crew's personality:\n")
        for i, team in enumerate(teams, 1):
            console.print(f"  [{i}] {team['display_name']} - {team['description']}")
        console.print("  [b] Back to previous step")

        console.print()

        # Let user select
        choice = self._prompt(
            "Select crew team",
            choices=[str(i) for i in range(1, len(teams) + 1)] + ["b"],
            default="1",
        )

        if choice == "b":
            return "back"

        selected_team = teams[int(choice) - 1]
        self.selected_team = selected_team["name"]

        # Now show the full team composition for the selected team
        self._show_team_details(selected_team["name"])

        # Confirm with option to go back
        console.print()
        confirm = self._confirm(f"✓ Confirm {selected_team['display_name']} crew?", default=True)

        if confirm:
            self.team_manager.select_team(self.selected_team)
            console.print()
        else:
            # Let them choose again
            return self._select_team()

    def _show_team_details(self, team_name: str) -> None:
        """Show the full team composition for a team."""
        from nanofolks.templates import get_team
        from nanofolks.teams import get_bot_team_profile

        team = get_team(team_name)
        if not team:
            return

        console.print(f"\n[bold]Crew: {team_name}[/bold]\n")
        console.print(f"[dim]{team['description']}[/dim]\n")

        # Create a table showing each team member
        team_table = Table(title="Your Crew Members", box=box.ROUNDED, show_lines=True)
        team_table.add_column("Name", style="green", width=12)
        team_table.add_column("Title", style="bright_magenta", width=15)
        team_table.add_column("Role", style="magenta", width=12)
        team_table.add_column("Description", style="white")

        # Add each bot
        bot_roles = ["leader", "researcher", "coder", "social", "creative", "auditor"]

        for bot_name in bot_roles:
            bot_profile = get_bot_team_profile(bot_name, team_name)
            if bot_profile:
                team_table.add_row(
                    bot_profile.bot_name,
                    f"{bot_profile.emoji} {bot_profile.bot_title}",
                    f"@{bot_name}",
                    bot_profile.personality,
                )

        console.print(team_table)
        console.print()
        console.print("[dim]All 6 bots will be created and ready to use.[/dim]\n")

    def _confirm_and_create(self) -> None:
        """Final confirmation and room creation."""
        console.print("[bold bright_magenta]Step 5: Ready to Launch![/bold bright_magenta]\n")

        # Show summary table
        summary_table = Table(title="Your Setup Summary", box=box.ROUNDED)
        summary_table.add_column("Setting", style="bright_magenta")
        summary_table.add_column("Value", style="green")

        # Provider info
        provider = self.config_result.get("provider", "Not configured")
        model = self.config_result.get("model", "default")
        summary_table.add_row("AI Provider", provider)
        summary_table.add_row("Model", model)

        # Team info
        team_obj = self.team_manager.get_current_team()
        team_name = team_obj["name"] if team_obj else self.selected_team or "Unknown"
        summary_table.add_row("Team", team_name)
        summary_table.add_row("Bots", "6 (all ready)")
        summary_table.add_row("Room", "#general")

        console.print(summary_table)
        console.print()

        if self._confirm("🚀 Launch your crew?", default=True):
            console.print("\n[green]✓ Setup complete![/green]\n")
            console.print("Your AI crew is ready!")
            console.print("\n[bold]Get started:[/bold]")
            console.print("  [bright_magenta]nanofolks chat[/bright_magenta]        - Start chatting")
            console.print("  [bright_magenta]#general[/bright_magenta]            - Crew chat room")
            console.print("  [bright_magenta]@researcher[/bright_magenta]        - DM a bot directly")
            console.print("  [bright_magenta]nanofolks configure[/bright_magenta]  - Add more providers/models\n")
        else:
            console.print("[yellow]Setup cancelled[/yellow]\n")

    def create_general_room(self) -> Room:
        """Create #general room with leader (Leader).

        Returns:
            Created Room object
        """
        general_room = Room(
            id="general",
            type=RoomType.OPEN,
            participants=["leader"],  # Only Leader in general room by default
            owner="system",
            metadata={
                "name": "General",
                "description": "General discussion and coordination room",
            },
        )
        return general_room

    def _save_room(self, room: Room, workspace_path: Path) -> None:
        """Save room to disk.

        Args:
            room: Room object to save
            workspace_path: Path to workspace root directory
        """
        import json

        try:
            # Create rooms directory if it doesn't exist
            rooms_dir = workspace_path / "rooms"
            rooms_dir.mkdir(parents=True, exist_ok=True)

            # Convert room to JSON-serializable format
            room_data = {
                "id": room.id,
                "type": room.type.value,
                "participants": room.participants,
                "owner": room.owner,
                "created_at": room.created_at.isoformat(),
                "auto_archive": room.auto_archive,
                "archive_after_days": room.archive_after_days,
                "coordinator_mode": room.coordinator_mode,
                "escalation_threshold": room.escalation_threshold,
                "deadline": room.deadline,
                "metadata": room.metadata,
                "summary": room.summary,
            }

            # Save to room-specific JSON file
            room_file = rooms_dir / f"{room.id}.json"
            with open(room_file, "w") as f:
                json.dump(room_data, f, indent=2, default=str)

            console.print(f"[green]✓ Saved room to {room_file}[/green]")

        except Exception as e:
            console.print(f"[yellow]⚠ Could not save room: {e}[/yellow]")

    def _apply_team_to_workspace(self, workspace_path: Path) -> None:
        """Apply selected team to all crew members in workspace.

        Creates SOUL.md, IDENTITY.md, and ROLE.md personality files for the entire crew.

        Args:
            workspace_path: Path to workspace
        """
        try:
            # Initialize SoulManager for workspace
            soul_manager = SoulManager(workspace_path)

            if self.selected_team:
                console.print("\n[bright_magenta]Initializing crew personalities...[/bright_magenta]")

                # Apply team to entire crew
                crew = ["leader", "researcher", "coder", "social", "creative", "auditor"]

                # Apply SOUL.md, IDENTITY.md, and ROLE.md team styles
                soul_results = soul_manager.apply_team_to_crew(
                    self.selected_team, crew, force=True
                )

                # Show results
                soul_successful = sum(1 for v in soul_results.values() if v)

                if soul_successful > 0:
                    console.print(
                        f"[green]✓ Initialized {soul_successful}/{len(crew)} bot personality files[/green]"
                    )
                    console.print("[dim]  (SOUL.md, IDENTITY.md, ROLE.md, AGENTS.md)[/dim]")

                # Show team personalities
                from nanofolks.teams import get_bot_team_profile

                console.print("\n[bold]Crew personalities configured:[/bold]")
                for bot_name in crew:
                    profile = get_bot_team_profile(
                        bot_name, self.selected_team, workspace_path=workspace_path
                    )
                    if profile:
                        console.print(f"  {profile.emoji} {profile.bot_title} ({bot_name})")

            # Create per-bot files (AGENTS.md, IDENTITY.md if not already created)
            self._create_bot_files(workspace_path)

        except Exception as e:
            console.print(f"[yellow]⚠ Could not apply team selection: {e}[/yellow]")

    def _create_bot_files(self, workspace_path: Path) -> None:
        """Create per-bot AGENTS.md and IDENTITY.md files.

        Args:
            workspace_path: Path to workspace
        """
        try:
            from nanofolks.soul import SoulManager

            soul_manager = SoulManager(workspace_path)
            team = ["leader", "researcher", "coder", "social", "creative", "auditor"]

            console.print("\n[bright_magenta]Creating bot configuration files...[/bright_magenta]")

            # Create AGENTS.md for each bot
            agents_results = soul_manager.apply_agents_to_team(team)
            agents_count = sum(1 for v in agents_results.values() if v)

            if agents_count > 0:
                console.print(f"  [green]✓[/green] Created AGENTS.md for {agents_count} bots")

            # Create IDENTITY.md for each bot from selected team
            identity_results = soul_manager.apply_identity_to_team(
                team, team_name=self.selected_team, force=True
            )
            identity_count = sum(1 for v in identity_results.values() if v)

            if identity_count > 0:
                console.print(f"  [green]✓[/green] Created IDENTITY.md for {identity_count} bots")

            console.print("\n[green]✓ Bot configuration files ready![/green]")
            console.print("[dim]  - AGENTS.md: Role-specific instructions for each bot[/dim]")
            console.print(
                "[dim]  - IDENTITY.md: Character definition and relationships (from team style)[/dim]"
            )

        except Exception as e:
            console.print(f"[yellow]⚠ Could not create bot files: {e}[/yellow]")


def run_onboarding():
    """Entry point for the onboarding wizard."""
    wizard = OnboardingWizard()
    result = wizard.run()
    return result
