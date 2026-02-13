"""Interactive onboarding wizard for multi-agent orchestration setup.

This module provides an interactive CLI wizard that guides new users through:
1. Theme selection
2. Capability selection
3. Team composition recommendation
4. #general workspace creation

Uses typer and rich for interactive prompts and rich terminal output.
"""

from typing import List, Set, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from nanobot.themes import ThemeManager, list_themes, get_theme
from nanobot.models import Workspace, WorkspaceType

console = Console()


class OnboardingWizard:
    """Interactive onboarding wizard for multi-agent team setup."""
    
    DOMAIN_DESCRIPTIONS = {
        "coordination": "Team leadership, task delegation, decision making",
        "research": "Information gathering, analysis, pattern recognition",
        "development": "Code implementation, architecture, technical solutions",
        "community": "User engagement, communication, relationship building",
        "design": "Creative solutions, visual thinking, innovation",
        "quality": "Testing, validation, error checking, compliance",
    }
    
    BOT_DESCRIPTIONS = {
        "researcher": "📚 Researcher Bot - Gathers and analyzes information",
        "coder": "💻 Coder Bot - Implements technical solutions",
        "social": "🤝 Social Bot - Handles communication and engagement",
        "creative": "🎨 Creative Bot - Generates novel ideas and solutions",
        "auditor": "✓ Auditor Bot - Validates and ensures quality",
    }
    
    def __init__(self):
        """Initialize the onboarding wizard."""
        self.theme_manager = ThemeManager()
        self.selected_theme: Optional[str] = None
        self.selected_domains: Set[str] = set()
        self.recommended_team: List[str] = []
    
    def run(self) -> Dict:
        """Run the complete onboarding wizard.
        
        Returns:
            Dictionary containing:
                - theme: selected theme name
                - domains: set of selected domains
                - team: list of recommended bot names
                - general_workspace: created workspace object
        """
        self._show_welcome()
        self._select_theme()
        self._select_domains()
        self._recommend_team()
        self._confirm_and_create()
        
        return {
            "theme": self.selected_theme,
            "domains": self.selected_domains,
            "team": self.recommended_team,
        }
    
    def _show_welcome(self) -> None:
        """Display welcome panel."""
        console.print(Panel.fit(
            "[bold cyan]🤖 Multi-Agent Team Onboarding[/bold cyan]\n\n"
            "Welcome! Let's set up your personalized team of AI bots.\n"
            "This wizard will help you:\n"
            "  1. Select a team personality theme\n"
            "  2. Choose your focus areas (domains)\n"
            "  3. Build your custom team\n"
            "  4. Create your #general workspace",
            title="Welcome",
            border_style="cyan"
        ))
        console.print()
    
    def _select_theme(self) -> None:
        """Interactive theme selection."""
        console.print("[bold]Step 1: Select Team Theme[/bold]")
        console.print("Choose how your team will present itself:\n")
        
        themes = list_themes()
        theme_names = [t["name"] for t in themes]
        
        # Display themes with descriptions
        for i, theme in enumerate(themes, 1):
            console.print(f"{i}. [bold cyan]{theme['display_name']}[/bold cyan]")
            console.print(f"   {theme['description']}\n")
        
        # Prompt for selection
        while True:
            choice = Prompt.ask(
                "Select theme (number or name)",
                choices=[str(i) for i in range(1, len(themes) + 1)] + theme_names,
            )
            
            # Convert number to theme name
            if choice.isdigit():
                self.selected_theme = theme_names[int(choice) - 1]
            else:
                self.selected_theme = choice
            
            # Validate and confirm
            theme_obj = get_theme(self.selected_theme)
            if theme_obj:
                if Confirm.ask(
                    f"\n✓ Confirmed: [cyan]{theme_obj.description}[/cyan]?",
                    default=True
                ):
                    self.theme_manager.select_theme(self.selected_theme)
                    console.print()
                    break
                console.print()
    
    def _select_domains(self) -> None:
        """Interactive domain/capability selection."""
        console.print("[bold]Step 2: Select Focus Areas (Domains)[/bold]")
        console.print("Choose the areas your team will focus on:\n")
        
        domains = list(self.DOMAIN_DESCRIPTIONS.keys())
        
        # Display domains
        for i, domain in enumerate(domains, 1):
            console.print(f"{i}. [bold cyan]{domain.upper()}[/bold cyan]")
            console.print(f"   {self.DOMAIN_DESCRIPTIONS[domain]}\n")
        
        # Multi-select with checkmarks
        selected = set()
        console.print("[cyan]Enter domain numbers separated by spaces (e.g., '1 2 3')[/cyan]")
        console.print("[cyan]Or press Enter to select all[/cyan]\n")
        
        while True:
            choice = Prompt.ask("Select domains").strip()
            
            if not choice:
                # Select all domains
                selected = set(domains)
                break
            
            # Parse numbers
            try:
                numbers = [int(x.strip()) for x in choice.split()]
                if all(1 <= n <= len(domains) for n in numbers):
                    selected = {domains[n - 1] for n in numbers}
                    break
                console.print("[red]✗ Invalid selection. Please enter valid numbers.[/red]\n")
            except ValueError:
                console.print("[red]✗ Invalid input. Please enter numbers separated by spaces.[/red]\n")
        
        self.selected_domains = selected
        
        # Show confirmation
        console.print("\n[green]✓ Selected domains:[/green]")
        for domain in sorted(self.selected_domains):
            console.print(f"  • {domain.upper()}")
        console.print()
    
    def compute_recommended_team(self) -> List[str]:
        """Compute team composition based on selected domains.
        
        Returns:
            List of recommended bot names
        """
        # Always include nanobot leader
        domain_to_bots = {
            "coordination": ["nanobot"],
            "research": ["researcher"],
            "development": ["coder"],
            "community": ["social"],
            "design": ["creative"],
            "quality": ["auditor"],
        }
        
        # Collect recommended bots
        recommended = {"nanobot"}
        for domain in self.selected_domains:
            for bot in domain_to_bots.get(domain, []):
                recommended.add(bot)
        
        return sorted(list(recommended))
    
    def _recommend_team(self, interactive: bool = True) -> None:
        """Recommend team composition based on selected domains.
        
        Args:
            interactive: If True, show prompts and allow customization
        """
        if interactive:
            console.print("[bold]Step 3: Build Your Team[/bold]")
            console.print("Based on your selected domains, here are recommended team members:\n")
        
        self.recommended_team = self.compute_recommended_team()
        
        if interactive:
            # Display with descriptions
            for bot_name in self.recommended_team:
                if bot_name in self.BOT_DESCRIPTIONS:
                    console.print(self.BOT_DESCRIPTIONS[bot_name])
            
            # Allow customization
            console.print()
            if Confirm.ask("Would you like to customize the team?"):
                self._customize_team()
            else:
                console.print("[green]✓ Team composition confirmed[/green]\n")
    
    def _customize_team(self) -> None:
        """Allow user to customize team composition."""
        console.print("\n[bold]Team Customization[/bold]\n")
        
        all_bots = ["researcher", "coder", "social", "creative", "auditor"]
        current_team = set(self.recommended_team)
        
        # Show available bots to add/remove
        console.print("[cyan]Current team:[/cyan]")
        for bot in self.recommended_team:
            console.print(f"  ✓ {bot}")
        
        console.print("\n[cyan]Available to add:[/cyan]")
        available = [b for b in all_bots if b not in current_team]
        for i, bot in enumerate(available, 1):
            console.print(f"  {i}. {self.BOT_DESCRIPTIONS[bot]}")
        
        # Prompt for additions
        if available:
            console.print()
            to_add = Prompt.ask(
                "Add bots (numbers separated by spaces, or press Enter to skip)",
                default=""
            )
            
            if to_add:
                try:
                    numbers = [int(x.strip()) for x in to_add.split()]
                    for num in numbers:
                        if 1 <= num <= len(available):
                            self.recommended_team.append(available[num - 1])
                except ValueError:
                    console.print("[yellow]⚠ Skipping additions due to invalid input[/yellow]")
        
        # Prompt for removals (except nanobot)
        removable = [b for b in self.recommended_team if b != "nanobot"]
        if removable:
            console.print("\n[cyan]Remove from team:[/cyan]")
            for i, bot in enumerate(removable, 1):
                console.print(f"  {i}. {bot}")
            
            to_remove = Prompt.ask(
                "Remove bots (numbers separated by spaces, or press Enter to skip)",
                default=""
            )
            
            if to_remove:
                try:
                    numbers = sorted([int(x.strip()) for x in to_remove.split()], reverse=True)
                    for num in numbers:
                        if 1 <= num <= len(removable):
                            self.recommended_team.remove(removable[num - 1])
                except ValueError:
                    console.print("[yellow]⚠ Skipping removals due to invalid input[/yellow]")
        
        self.recommended_team = sorted(list(set(self.recommended_team)))
        console.print("\n[green]✓ Team customization complete[/green]\n")
    
    def _confirm_and_create(self) -> None:
        """Final confirmation and workspace creation."""
        console.print("[bold]Step 4: Summary[/bold]\n")
        
        # Show summary table
        summary_table = Table(title="Team Setup Summary", box=box.ROUNDED)
        summary_table.add_column("Setting", style="cyan")
        summary_table.add_column("Value", style="green")
        
        theme_obj = self.theme_manager.get_current_theme()
        summary_table.add_row("Theme", theme_obj.name)
        summary_table.add_row("Domains", ", ".join(sorted(self.selected_domains)))
        summary_table.add_row("Team Members", ", ".join(self.recommended_team))
        
        console.print(summary_table)
        console.print()
        
        if Confirm.ask("Create team and #general workspace?", default=True):
            console.print("[green]✓ Setup complete![/green]")
            console.print("\nYour team is ready. Start using it with:")
            console.print("  [cyan]@researcher analyze <topic>[/cyan]")
            console.print("  [cyan]@coder implement <feature>[/cyan]")
            console.print("  [cyan]#general <message>[/cyan]")
            console.print()
        else:
            console.print("[yellow]Setup cancelled[/yellow]\n")
    
    def create_general_workspace(self) -> Workspace:
        """Create #general workspace with recommended team.
        
        Returns:
            Created Workspace object
        """
        general_ws = Workspace(
            id="general",
            type=WorkspaceType.OPEN,
            participants=self.recommended_team,
            owner="system",
            metadata={
                "name": "General",
                "description": "General discussion and coordination workspace",
            }
        )
        return general_ws


def run_onboarding():
    """Entry point for the onboarding wizard."""
    wizard = OnboardingWizard()
    result = wizard.run()
    return result
