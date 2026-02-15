"""Unified onboarding wizard for multi-agent orchestration setup.

This module provides a unified CLI wizard that guides new users through:
1. Provider selection (API key)
2. Model selection
3. Theme/Team selection (with team description)
4. #general room creation with all bots
5. SOUL.md personality file generation

Uses typer and rich for interactive prompts and rich terminal output.
"""

import asyncio
from pathlib import Path
from typing import Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from nanobot.themes import ThemeManager, list_themes, get_theme
from nanobot.models import Room, RoomType
from nanobot.soul import SoulManager

console = Console()


class OnboardingWizard:
    """Unified onboarding wizard for multi-agent team setup.
    
    Complete wizard that guides users through:
    1. Provider selection and API key
    2. Model selection
    3. Theme/Team selection with full team description
    4. Room creation
    5. SOUL.md personality file generation
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
    
    def __init__(self):
        """Initialize the onboarding wizard."""
        self.theme_manager = ThemeManager()
        self.selected_theme: Optional[str] = None
        self.soul_manager: Optional[SoulManager] = None
        self.config_result: Dict = {}
    
    def run(self, workspace_path: Optional[Path] = None) -> Dict:
        """Run the complete onboarding wizard.
        
        Args:
            workspace_path: Optional workspace path for SOUL file generation and room storage
        
        Returns:
            Dictionary containing:
                - provider: selected provider name
                - model: selected model
                - theme: selected theme name
                - workspace_path: workspace path used
                - general_room: created Room object for #general
        """
        self._show_welcome()
        
        # Step 1: Provider & API Key
        self._configure_provider()
        
        # Step 2: Theme/Team Selection
        self._select_theme()
        
        # Step 3: Summary & Create
        self._confirm_and_create()
        
        # Create the #general room
        general_room = self.create_general_room()
        
        # Apply theme to workspace if path provided
        if workspace_path:
            self._apply_theme_to_workspace(workspace_path)
            # Save the general room to disk
            self._save_room(general_room, workspace_path)
        
        return {
            "provider": self.config_result.get("provider"),
            "model": self.config_result.get("model"),
            "theme": self.selected_theme,
            "workspace_path": str(workspace_path) if workspace_path else None,
            "general_room": general_room,
        }
    
    def _show_welcome(self) -> None:
        """Display welcome panel."""
        console.print(Panel.fit(
            "[bold cyan]🚀 Welcome to Nanobot![/bold cyan]\n\n"
            "Let's set up your multi-agent team in just a few steps.\n"
            "This wizard will guide you through:\n"
            "  1. [bold]AI Provider[/bold] + Model (with Smart Routing)\n"
            "  2. [bold]Evolutionary Mode[/bold] (optional)\n"
            "  3. [bold]Team Theme[/bold] - Choose your crew's personality\n"
            "  4. [bold]Launch[/bold] - Create your workspace and crew",
            title="🎉",
            border_style="cyan"
        ))
        console.print()
    
    def _configure_provider(self) -> None:
        """Step 1: Configure AI provider and API key."""
        console.print("[bold cyan]Step 1: AI Provider Setup[/bold cyan]\n")
        console.print("Choose the AI provider for your crew:\n")
        
        for key, (name, desc) in self.PROVIDERS.items():
            console.print(f"  [{key}] {desc}")
        
        provider_choice = Prompt.ask(
            "\nSelect provider",
            choices=list(self.PROVIDERS.keys()),
            default="1"
        )
        provider_name, provider_desc = self.PROVIDERS[provider_choice]
        
        # Get API key
        console.print(f"\n[dim]{provider_desc}[/dim]")
        api_key = Prompt.ask(f"Enter your {provider_name.title()} API key", password=True)
        
        if not api_key:
            console.print("[yellow]⚠ No API key provided. You can configure this later with: nanobot configure[/yellow]\n")
            self.config_result["provider"] = None
            self.config_result["api_key"] = None
        else:
            # Save API key
            console.print(f"\n[cyan]Saving API key for {provider_name}...[/cyan]")
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
        
        model_choice = Prompt.ask(
            "\nSelect model",
            choices=[str(i) for i in range(1, min(6, len(models)+1))] + ["c"],
            default="1"
        )
        
        if model_choice == "c":
            primary_model = Prompt.ask("Enter custom model name")
        else:
            primary_model = models[int(model_choice) - 1]
        
        self.config_result["model"] = primary_model
        
        # Save model selection
        if primary_model and api_key:
            asyncio.run(self._save_model_config(primary_model))
            console.print(f"[green]✓ Primary model set to {primary_model}[/green]\n")
        
        # Smart Routing configuration
        self._configure_smart_routing(provider_name, primary_model)
        
        # Evolutionary Mode configuration
        self._configure_evolutionary_mode()
    
    def _configure_smart_routing(self, provider: str, primary_model: str) -> None:
        """Step 1b: Configure Smart Routing."""
        console.print("[bold cyan]Step 1b: Smart Routing[/bold cyan]\n")
        console.print("""
[dim]Smart routing automatically selects the best model based on query complexity:[/dim]
  • Simple queries → Cheaper, faster models
  • Complex tasks → Stronger, more capable models
  • Coding → Specialized coding models
  • Reasoning → Advanced reasoning models

[dim]This saves costs while maintaining quality.[/dim]
        """)
        
        enable_routing = Confirm.ask("Enable smart routing?", default=True)
        
        if enable_routing:
            provider = self.config_result.get("provider", "openrouter")
            asyncio.run(self._save_routing_config(True, provider))
            console.print("[green]✓ Smart routing enabled![/green]\n")
            console.print("[dim]Models auto-configured for your provider.[/dim]")
            console.print("[dim]Customize later: nanobot configure[/dim]\n")
        else:
            console.print("[dim]Smart routing disabled. Will use primary model for all queries.[/dim]\n")
    
    def _configure_evolutionary_mode(self) -> None:
        """Step 1c: Configure Evolutionary Mode."""
        console.print("[bold cyan]Step 1c: Evolutionary Mode (Optional)[/bold cyan]\n")
        console.print("""
[dim]Evolutionary mode allows bots to:[/dim]
  • Modify their own source code
  • Access paths outside the workspace
  • Self-improve and adapt

[yellow]⚠ Security Warning:[/yellow] Only enable if you understand the risks.
        """)
        
        enable_evo = Confirm.ask("Enable evolutionary mode?", default=False)
        
        if enable_evo:
            asyncio.run(self._save_evolutionary_config(True))
            console.print("[green]✓ Evolutionary mode enabled![/green]\n")
        else:
            console.print("[dim]Evolutionary mode disabled. Bots restricted to workspace only.[/dim]\n")
    
    async def _save_routing_config(self, enabled: bool, provider: str = "openrouter") -> None:
        """Save routing configuration with provider-specific tiers.
        
        Args:
            enabled: Whether to enable routing
            provider: Provider name for selecting appropriate models
        """
        try:
            from nanobot.agent.tools.update_config import UpdateConfigTool
            from nanobot.config.schema import get_routing_tiers_for_provider
            
            tool = UpdateConfigTool()
            
            # Enable routing
            await tool.execute(path="routing.enabled", value=enabled)
            
            # Get provider-specific tiers
            tiers = get_routing_tiers_for_provider(provider)
            
            # Save each tier's model
            await tool.execute(path="routing.tiers.simple.model", value=tiers.simple.model)
            await tool.execute(path="routing.tiers.simple.secondary_model", value=tiers.simple.secondary_model)
            
            await tool.execute(path="routing.tiers.medium.model", value=tiers.medium.model)
            await tool.execute(path="routing.tiers.medium.secondary_model", value=tiers.medium.secondary_model)
            
            await tool.execute(path="routing.tiers.complex.model", value=tiers.complex.model)
            await tool.execute(path="routing.tiers.complex.secondary_model", value=tiers.complex.secondary_model)
            
            await tool.execute(path="routing.tiers.reasoning.model", value=tiers.reasoning.model)
            await tool.execute(path="routing.tiers.reasoning.secondary_model", value=tiers.reasoning.secondary_model)
            
            await tool.execute(path="routing.tiers.coding.model", value=tiers.coding.model)
            await tool.execute(path="routing.tiers.coding.secondary_model", value=tiers.coding.secondary_model)
            
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save routing config: {e}[/yellow]")
    
    async def _save_evolutionary_config(self, enabled: bool) -> None:
        """Save evolutionary mode configuration."""
        try:
            from nanobot.agent.tools.update_config import UpdateConfigTool
            tool = UpdateConfigTool()
            await tool.execute(path="tools.evolutionary", value=enabled)
            if enabled:
                await tool.execute(path="tools.allowedPaths", value=["/projects/nanobot-turbo", "~/.nanobot"])
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save evolutionary config: {e}[/yellow]")
    
    async def _save_provider_config(self, provider: str, api_key: str) -> None:
        """Save provider API key to config."""
        try:
            from nanobot.agent.tools.update_config import UpdateConfigTool
            tool = UpdateConfigTool()
            await tool.execute(path=f"providers.{provider}.apiKey", value=api_key)
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save API key: {e}[/yellow]")
    
    async def _save_model_config(self, model: str) -> None:
        """Save default model to config."""
        try:
            from nanobot.agent.tools.update_config import UpdateConfigTool
            tool = UpdateConfigTool()
            await tool.execute(path="agents.defaults.model", value=model)
        except Exception as e:
            console.print(f"[yellow]⚠ Could not save model: {e}[/yellow]")
    
    def _get_available_models(self, provider: str) -> list:
        """Get available models for a provider."""
        # Simplified - in production would query provider schema
        defaults = {
            "openrouter": ["openrouter/anthropic/claude-3-5-sonnet", "openrouter/openai/gpt-4o"],
            "anthropic": ["anthropic/claude-3-5-sonnet-20241022"],
            "openai": ["openai/gpt-4o"],
            "groq": ["groq/llama-3.3-70b"],
            "deepseek": ["deepseek/deepseek-chat"],
            "moonshot": ["moonshot/kimi-k2.5"],
            "gemini": ["gemini-2.0-flash-exp"],
        }
        return defaults.get(provider, ["default-model"])
    
    def _select_theme(self) -> None:
        """Interactive team/theme selection."""
        console.print("[bold cyan]Step 2: Choose Your Crew Theme[/bold cyan]\n")
        
        themes = list_themes()
        theme_names = [t["name"] for t in themes]
        
        # First show just the team theme options
        console.print("Choose your crew's personality:\n")
        for i, theme in enumerate(themes, 1):
            console.print(f"  [{i}] {theme['display_name']} - {theme['description']}")
        console.print("  [b] Back to previous step")
        
        console.print()
        
        # Let user select
        choice = Prompt.ask(
            "Select crew theme",
            choices=[str(i) for i in range(1, len(themes) + 1)] + ["b"],
        )
        
        if choice == "b":
            # Go back to provider configuration
            self._configure_provider()
            return
        
        selected_theme = themes[int(choice) - 1]
        self.selected_theme = selected_theme["name"]
        
        # Now show the full team composition for the selected theme
        self._show_team_for_theme(selected_theme["name"])
        
        # Confirm with option to go back
        console.print()
        confirm = Confirm.ask(f"✓ Confirm {selected_theme['display_name']} crew?", default=True)
        
        if confirm:
            self.theme_manager.select_theme(self.selected_theme)
            console.print()
        else:
            # Let them choose again
            self._select_theme()
    
    def _show_team_for_theme(self, theme_name: str) -> None:
        """Show the full team composition for a theme."""
        theme = get_theme(theme_name)
        if not theme:
            return
        
        console.print(f"\n[bold]Crew: {theme.name.value}[/bold]\n")
        console.print(f"[dim]{theme.description}[/dim]\n")
        
        # Create a table showing each team member
        team_table = Table(title="Your Crew Members", box=box.ROUNDED)
        team_table.add_column("Role", style="cyan", width=15)
        team_table.add_column("Bot", style="green", width=12)
        team_table.add_column("Description", style="white")
        
        # Add each bot
        bots = [
            ("Leader", theme.nanobot, "nanobot"),
            ("Researcher", theme.researcher, "researcher"),
            ("Coder", theme.coder, "coder"),
            ("Social", theme.social, "social"),
            ("Creative", theme.creative, "creative"),
            ("Auditor", theme.auditor, "auditor"),
        ]
        
        for role, bot_theming, bot_name in bots:
            if bot_theming:
                team_table.add_row(
                    f"{bot_theming.emoji} {bot_theming.title}",
                    f"@{bot_name}",
                    bot_theming.personality
                )
        
        console.print(team_table)
        console.print()
        console.print("[dim]All 6 bots will be created and ready to use.[/dim]\n")
    
    def _confirm_and_create(self) -> None:
        """Final confirmation and room creation."""
        console.print("[bold cyan]Step 3: Ready to Launch![/bold cyan]\n")
        
        # Show summary table
        summary_table = Table(title="Your Setup Summary", box=box.ROUNDED)
        summary_table.add_column("Setting", style="cyan")
        summary_table.add_column("Value", style="green")
        
        # Provider info
        provider = self.config_result.get("provider", "Not configured")
        model = self.config_result.get("model", "default")
        summary_table.add_row("AI Provider", provider)
        summary_table.add_row("Model", model)
        
        # Theme info
        theme_obj = self.theme_manager.get_current_theme()
        theme_name = theme_obj.name.value if theme_obj else self.selected_theme or "Unknown"
        summary_table.add_row("Crew Theme", theme_name)
        summary_table.add_row("Bots", "6 (all ready)")
        summary_table.add_row("Room", "#general")
        
        console.print(summary_table)
        console.print()
        
        if Confirm.ask("🚀 Launch your crew?", default=True):
            console.print("\n[green]✓ Setup complete![/green]\n")
            console.print("Your AI crew is ready!")
            console.print("\n[bold]Get started:[/bold]")
            console.print("  [cyan]nanobot agent[/cyan]        - Start chatting")
            console.print("  [cyan]#general[/cyan]            - Crew chat room")
            console.print("  [cyan]@researcher[/cyan]        - DM a bot directly")
            console.print("  [cyan]nanobot configure[/cyan]  - Add more providers/models\n")
        else:
            console.print("[yellow]Setup cancelled[/yellow]\n")
    
    def create_general_room(self) -> Room:
        """Create #general room with nanobot (Leader).
        
        Returns:
            Created Room object
        """
        general_room = Room(
            id="general",
            type=RoomType.OPEN,
            participants=["nanobot"],  # Only Leader in general room by default
            owner="system",
            metadata={
                "name": "General",
                "description": "General discussion and coordination room",
            }
        )
        return general_room
    
    def _save_room(self, room: Room, workspace_path: Path) -> None:
        """Save room to disk.
        
        Args:
            room: Room object to save
            workspace_path: Path to workspace root directory
        """
        import json
        from datetime import datetime
        
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
    
    def _apply_theme_to_workspace(self, workspace_path: Path) -> None:
        """Apply selected theme to all crew members in workspace.
        
        Creates SOUL.md and IDENTITY.md personality files for the entire crew.
        
        Args:
            workspace_path: Path to workspace
        """
        try:
            # Initialize SoulManager for workspace
            soul_manager = SoulManager(workspace_path)
            theme = get_theme(self.selected_theme) if self.selected_theme else None
            
            if theme and self.selected_theme:
                console.print("\n[cyan]Initializing crew personalities...[/cyan]")
                
                # Apply theme to entire crew
                team = ["nanobot", "researcher", "coder", "social", "creative", "auditor"]
                
                # Apply SOUL.md theme
                soul_results = soul_manager.apply_theme_to_team(
                    theme,
                    team,
                    force=True
                )
                
                # Apply IDENTITY.md theme
                identity_results = soul_manager.apply_identity_to_team(
                    team,
                    theme=self.selected_theme,
                    force=True
                )
                
                # Show results
                soul_successful = sum(1 for v in soul_results.values() if v)
                identity_successful = sum(1 for v in identity_results.values() if v)
                
                if soul_successful > 0 or identity_successful > 0:
                    console.print(
                        f"[green]✓ Initialized {soul_successful}/{len(team)} SOUL files[/green]"
                    )
                    console.print(
                        f"[green]✓ Initialized {identity_successful}/{len(team)} IDENTITY files[/green]"
                    )
                
                # Show team personalities
                console.print("\n[bold]Crew personalities configured:[/bold]")
                for bot_name in team:
                    theming = theme.get_bot_theming(bot_name)
                    if theming:
                        console.print(f"  {theming.emoji} {theming.title} ({bot_name})")
            
            # Create per-bot files (AGENTS.md, IDENTITY.md if not already created, and HEARTBEAT.md)
            self._create_bot_files(workspace_path)
            
        except Exception as e:
            console.print(f"[yellow]⚠ Could not apply theme: {e}[/yellow]")
    
    def _create_bot_files(self, workspace_path: Path) -> None:
        """Create per-bot AGENTS.md, IDENTITY.md, and HEARTBEAT.md files.
        
        Args:
            workspace_path: Path to workspace
        """
        try:
            from nanobot.soul import SoulManager
            
            soul_manager = SoulManager(workspace_path)
            team = ["nanobot", "researcher", "coder", "social", "creative", "auditor"]
            
            console.print("\n[cyan]Creating bot configuration files...[/cyan]")
            
            # Create AGENTS.md for each bot
            agents_results = soul_manager.apply_agents_to_team(team)
            agents_count = sum(1 for v in agents_results.values() if v)
            
            if agents_count > 0:
                console.print(f"  [green]✓[/green] Created AGENTS.md for {agents_count} bots")
            
            # Create IDENTITY.md for each bot from selected theme
            identity_results = soul_manager.apply_identity_to_team(
                team, 
                theme=self.selected_theme,
                force=True
            )
            identity_count = sum(1 for v in identity_results.values() if v)
            
            if identity_count > 0:
                console.print(f"  [green]✓[/green] Created IDENTITY.md for {identity_count} bots")
            
            # Create HEARTBEAT.md for each bot
            bots_dir = workspace_path / "bots"
            bots_dir.mkdir(parents=True, exist_ok=True)
            
            heartbeat_count = 0
            for bot_name in team:
                bot_dir = bots_dir / bot_name
                bot_dir.mkdir(parents=True, exist_ok=True)
                
                heartbeat_file = bot_dir / "HEARTBEAT.md"
                
                if not heartbeat_file.exists():
                    template = f"""# Heartbeat for @{bot_name}

This file defines periodic tasks for @{bot_name}.

## Format
Use markdown with checkboxes:
- [ ] Task description

## Examples

### Every 30 minutes
- [ ] Check for new updates

### Every hour
- [ ] Monitor system status

### Daily
- [ ] Generate daily summary
"""
                    heartbeat_file.write_text(template)
                    heartbeat_count += 1
            
            if heartbeat_count > 0:
                console.print(f"  [green]✓[/green] Created HEARTBEAT.md for {heartbeat_count} bots")
            
            console.print(f"\n[green]✓ Bot configuration files ready![/green]")
            console.print("[dim]  - AGENTS.md: Role-specific instructions for each bot[/dim]")
            console.print("[dim]  - IDENTITY.md: Character definition and relationships (from theme)[/dim]")
            console.print("[dim]  - HEARTBEAT.md: Periodic tasks (leave empty if not needed)[/dim]")
            
        except Exception as e:
            console.print(f"[yellow]⚠ Could not create bot files: {e}[/yellow]")


def run_onboarding():
    """Entry point for the onboarding wizard."""
    wizard = OnboardingWizard()
    result = wizard.run()
    return result
