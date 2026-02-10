"""Interactive CLI configuration wizard for nanobot.

This module provides an interactive configuration interface using
typer and rich for a nice user experience.
"""

import asyncio
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from nanobot.config.loader import load_config, save_config, get_config_path
from nanobot.agent.tools.update_config import UpdateConfigTool


console = Console()


def configure_cli():
    """Main entry point for the configuration wizard."""
    # Show welcome
    console.print(Panel.fit(
        "[bold blue]🤖 nanobot Configuration Wizard[/bold blue]\n\n"
        "Configure your nanobot installation interactively.",
        title="Welcome",
        border_style="blue"
    ))
    
    # Check current config status with spinner
    with console.status("[cyan]Loading configuration...[/cyan]", spinner="dots"):
        tool = UpdateConfigTool()
        summary = tool.get_config_summary()
    
    # Show current status
    _show_status(summary)
    
    # Main menu loop
    while True:
        choice = _show_main_menu(summary)
        
        if choice == "exit":
            console.print("\n[green]✓[/green] Configuration complete!")
            console.print("\nYou can now start using nanobot:")
            console.print("  [cyan]nanobot agent[/cyan] - Start interactive chat")
            console.print("  [cyan]nanobot gateway[/cyan] - Start gateway server")
            break
        
        elif choice == "providers":
            _configure_providers(summary)
        
        elif choice == "channels":
            _configure_channels(summary)
        
        elif choice == "agents":
            _configure_agents()
        
        elif choice == "routing":
            _configure_routing()
        
        elif choice == "tools":
            _configure_tools()
        
        elif choice == "status":
            _show_detailed_status()
        
        # Refresh summary
        summary = tool.get_config_summary()


def _show_status(summary: dict):
    """Show current configuration status."""
    table = Table(title="Current Configuration", box=box.ROUNDED)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    # Providers
    configured_providers = [
        name for name, info in summary['providers'].items() 
        if info['has_key']
    ]
    if configured_providers:
        table.add_row(
            "LLM Providers",
            f"[green]✓[/green] {', '.join(configured_providers)}"
        )
    else:
        table.add_row(
            "LLM Providers",
            "[red]✗[/red] None configured [dim](Required)[/dim]"
        )
    
    # Channels
    enabled_channels = [
        name for name, info in summary['channels'].items()
        if info.get('enabled', False)
    ]
    if enabled_channels:
        table.add_row(
            "Channels",
            f"[green]✓[/green] {', '.join(enabled_channels)}"
        )
    else:
        table.add_row(
            "Channels",
            "[dim]○ None enabled (Optional)[/dim]"
        )
    
    console.print(table)
    console.print()


def _get_channels_status(summary: dict) -> str:
    """Get status indicator for channels."""
    enabled_channels = [
        name for name, info in summary.get('channels', {}).items()
        if info.get('enabled', False)
    ]
    return "[green]✓[/green]" if enabled_channels else "[dim]○[/dim]"


def _get_agents_status(summary: dict) -> str:
    """Get status indicator for agent settings."""
    # Use summary data to avoid reloading broken config
    # Show ✓ if model is set (done during provider setup)
    has_any_provider = any(
        p.get('has_key', False) for p in summary.get('providers', {}).values()
    )
    return "[green]✓[/green]" if has_any_provider else "[dim]○[/dim]"


def _get_routing_status(summary: dict) -> str:
    """Get status indicator for routing."""
    # This is passed in summary from get_config_summary
    # We need to check if routing was enabled
    # For now, check if any provider is configured (proxy for onboard completion)
    has_any_provider = any(
        p.get('has_key', False) for p in summary.get('providers', {}).values()
    )
    return "[green]✓[/green]" if has_any_provider else "[dim]○[/dim]"


def _get_tools_status(summary: dict) -> str:
    """Get status indicator for tools."""
    # Check if any channel is enabled (proxy for advanced setup)
    has_any_channel = any(
        info.get('enabled', False) 
        for info in summary.get('channels', {}).values()
    )
    return "[green]✓[/green]" if has_any_channel else "[dim]○[/dim]"


def _show_main_menu(summary: dict) -> str:
    """Show main menu and get user choice."""
    has_required = summary['has_required_config']
    
    console.print(Panel(
        "[bold]Main Menu[/bold]\n"
        "Select a category to configure:",
        border_style="blue"
    ))
    
    options = []
    
    # Check each section's status
    providers_status = "[green]✓[/green]" if has_required else "[dim]○[/dim]"
    channels_status = _get_channels_status(summary)
    agents_status = _get_agents_status(summary)
    routing_status = _get_routing_status(summary)
    tools_status = _get_tools_status(summary)
    
    if not has_required:
        console.print("[red]⚠ At least one LLM provider is required to start[/red]\n")
        options.append(("1", "providers", f"🤖 Model Providers {providers_status} [red](Required)[/red]"))
    else:
        options.append(("1", "providers", f"🤖 Model Providers {providers_status}"))
    
    options.extend([
        ("2", "channels", f"💬 Chat Channels {channels_status}"),
        ("3", "agents", f"⚙️ Agent Settings {agents_status}"),
        ("4", "routing", f"🧠 Smart Routing {routing_status}"),
        ("5", "tools", f"🛠️ Tool Settings {tools_status}"),
        ("6", "status", "📊 View Full Status"),
        ("7", "exit", "✓ Done" if has_required else "⏭ Skip for now"),
    ])
    
    for num, key, label in options:
        console.print(f"  [{num}] {label}")
    
    console.print()
    
    # Get choice
    choice_map = {num: key for num, key, _ in options}
    default = "1" if not has_required else "6"
    
    while True:
        choice = Prompt.ask(
            "Select option",
            choices=list(choice_map.keys()),
            default=default
        )
        if choice in choice_map:
            return choice_map[choice]


def _configure_providers(summary: dict):
    """Configure LLM providers."""
    tool = UpdateConfigTool()
    schema = tool.SCHEMA['providers']['providers']
    
    console.print(Panel(
        "[bold]Model Providers[/bold]\n"
        "Select a provider to configure:",
        border_style="blue"
    ))
    
    # Show provider options
    providers_list = list(schema.items())
    for i, (name, info) in enumerate(providers_list, 1):
        configured = summary['providers'].get(name, {}).get('has_key', False)
        status = "[green]✓[/green]" if configured else "[dim]○[/dim]"
        models = ", ".join(info.get('models', [])[:2])
        console.print(f"  [{i}] {status} {name.title()} - {models}...")
    
    console.print(f"  [0] Back to main menu")
    console.print()
    
    # Get choice
    choice = Prompt.ask(
        "Select provider",
        choices=[str(i) for i in range(len(providers_list) + 1)],
        default="1"
    )
    
    if choice == "0":
        return
    
    provider_name = providers_list[int(choice) - 1][0]
    provider_schema = schema[provider_name]
    
    # Show provider configuration
    _configure_single_provider(provider_name, provider_schema)


def _configure_single_provider(name: str, schema: dict):
    """Configure a single provider."""
    console.print(Panel(
        f"[bold]{name.title()} Configuration[/bold]",
        border_style="blue"
    ))
    
    tool = UpdateConfigTool()
    
    # Show help
    if 'models' in schema:
        console.print(f"\n[dim]Available models:[/dim]")
        for model in schema['models']:
            console.print(f"  • {model}")
    
    if 'fields' in schema:
        for field_name, field_info in schema['fields'].items():
            if field_info.get('help'):
                console.print(f"\n[dim]{field_info['help']}[/dim]")
    
    # Show options
    console.print()
    console.print("  [1] Enter API key")
    console.print("  [0] Back")
    console.print()
    
    choice = Prompt.ask("Select", choices=["0", "1"], default="1")
    
    if choice == "0":
        return
    
    # Get API key
    api_key = Prompt.ask(
        f"Enter {name} API key",
        password=False  # Show input so user can see what they're typing
    )
    
    if not api_key:
        console.print("[yellow]⚠ No API key provided, skipping[/yellow]")
        return
    
    # Show preview
    if len(api_key) > 8:
        preview = f"{api_key[:8]}...{api_key[-4:]}"
        console.print(f"Key preview: {preview}")
    
    # Confirm
    if not Confirm.ask("Save this API key?", default=True):
        console.print("[yellow]Cancelled[/yellow]")
        return
    
    # Update config with spinner
    with console.status(f"[cyan]Saving {name} configuration...[/cyan]", spinner="dots"):
        result = asyncio.run(tool.execute(
            path=f"providers.{name}.apiKey",
            value=api_key
        ))
    
    if "Error" in result:
        console.print(f"[red]{result}[/red]")
    else:
        console.print(f"[green]{result}[/green]")
        
        # Ask about default model
        if 'models' in schema and len(schema['models']) > 0:
            console.print("\n[dim]Available models:[/dim]")
            for i, model in enumerate(schema['models'], 1):
                console.print(f"  [{i}] {model}")
            
            model_choice = Prompt.ask(
                "Select default model (or press Enter to skip)",
                choices=[str(i) for i in range(len(schema['models']) + 1)],
                default="1"
            )
            
            if model_choice != "0":
                model = schema['models'][int(model_choice) - 1]
                result = asyncio.run(tool.execute(
                    path="agents.defaults.model",
                    value=model
                ))
                if "Error" not in result:
                    console.print(f"[green]✓ Set default model to {model}[/green]")


def _configure_channels(summary: dict):
    """Configure chat channels."""
    tool = UpdateConfigTool()
    schema = tool.SCHEMA['channels']['channels']
    
    console.print(Panel(
        "[bold]Chat Channels[/bold]\n"
        "Configure integrations with chat platforms:",
        border_style="blue"
    ))
    
    # Show channel options
    channels_list = list(schema.items())
    for i, (name, info) in enumerate(channels_list, 1):
        enabled = summary['channels'].get(name, {}).get('enabled', False)
        status = "[green]✓ Enabled[/green]" if enabled else "[dim]○ Disabled[/dim]"
        difficulty = info.get('difficulty', 'Medium')
        console.print(f"  [{i}] {status} {name.title()} ({difficulty})")
    
    console.print(f"  [0] Back to main menu")
    console.print()
    
    # Get choice
    choice = Prompt.ask(
        "Select channel to configure",
        choices=[str(i) for i in range(len(channels_list) + 1)],
        default="1"
    )
    
    if choice == "0":
        return
    
    channel_name = channels_list[int(choice) - 1][0]
    channel_schema = schema[channel_name]
    
    _configure_single_channel(channel_name, channel_schema)


def _configure_single_channel(name: str, schema: dict):
    """Configure a single channel."""
    console.print(Panel(
        f"[bold]{name.title()} Configuration[/bold]",
        border_style="blue"
    ))
    
    tool = UpdateConfigTool()
    
    # Show setup notes
    if 'setup_note' in schema:
        console.print(f"\n[yellow]⚠ {schema['setup_note']}[/yellow]")
    
    # Show current status
    current = tool.get_config_summary()['channels'].get(name, {})
    is_enabled = current.get('enabled', False)
    
    if is_enabled:
        console.print(f"\n[green]✓ Channel is currently enabled[/green]")
        if Confirm.ask("Disable this channel?", default=False):
            asyncio.run(tool.execute(path=f"channels.{name}.enabled", value=False))
            console.print("[green]✓ Channel disabled[/green]")
        return
    
    # Enable channel
    console.print("\nTo enable this channel, I need some information:")
    console.print("  [1] Continue with setup")
    console.print("  [0] Back")
    console.print()
    
    choice = Prompt.ask("Select", choices=["0", "1"], default="1")
    
    if choice == "0":
        return
    
    console.print()
    
    # Collect required fields
    if 'fields' in schema:
        for field_name, field_info in schema['fields'].items():
            if field_info.get('type') == 'boolean':
                continue  # Skip boolean fields for now
            
            help_text = field_info.get('help', '')
            if help_text:
                console.print(f"[dim]{help_text}[/dim]")
            
            value = Prompt.ask(f"Enter {field_name}")
            
            if value:
                result = asyncio.run(tool.execute(
                    path=f"channels.{name}.{field_name}",
                    value=value
                ))
                if "Error" in result:
                    console.print(f"[red]{result}[/red]")
    
    # Enable the channel
    if Confirm.ask("Enable this channel?", default=True):
        with console.status(f"[cyan]Enabling {name} channel...[/cyan]", spinner="dots"):
            result = asyncio.run(tool.execute(path=f"channels.{name}.enabled", value=True))
        if "Error" not in result:
            console.print(f"[green]✓ {name.title()} channel enabled![/green]")
        console.print(f"[dim]Start the gateway to activate: nanobot gateway[/dim]")


def _configure_agents():
    """Configure agent settings."""
    tool = UpdateConfigTool()
    
    console.print(Panel(
        "[bold]Agent Settings[/bold]",
        border_style="blue"
    ))
    
    # Show current settings
    config = load_config()
    
    console.print(f"\n[dim]Current settings:[/dim]")
    console.print(f"  Model: {config.agents.defaults.model}")
    console.print(f"  Max tokens: {config.agents.defaults.max_tokens}")
    console.print(f"  Temperature: {config.agents.defaults.temperature}")
    
    # Ask what to change
    console.print("\nWhat would you like to change?")
    console.print("  [1] Default model")
    console.print("  [2] Max tokens")
    console.print("  [3] Temperature")
    console.print("  [0] Back")
    
    choice = Prompt.ask("Select", choices=["0", "1", "2", "3"], default="0")
    
    if choice == "1":
        model = Prompt.ask("Enter model name (e.g., anthropic/claude-opus-4-5)")
        if model:
            result = asyncio.run(tool.execute(path="agents.defaults.model", value=model))
            console.print(f"[green]{result}[/green]")
    
    elif choice == "2":
        tokens = Prompt.ask("Enter max tokens", default="8192")
        result = asyncio.run(tool.execute(path="agents.defaults.max_tokens", value=int(tokens)))
        console.print(f"[green]{result}[/green]")
    
    elif choice == "3":
        temp = Prompt.ask("Enter temperature (0.0-2.0)", default="0.7")
        result = asyncio.run(tool.execute(path="agents.defaults.temperature", value=float(temp)))
        console.print(f"[green]{result}[/green]")


def _configure_routing():
    """Configure smart routing settings."""
    from nanobot.config.loader import load_config
    
    tool = UpdateConfigTool()
    config = load_config()
    
    console.print(Panel(
        "[bold]Smart Routing Configuration[/bold]\n"
        "Smart routing automatically selects the best model based on query complexity",
        border_style="blue"
    ))
    
    # Show current status
    is_enabled = config.routing.enabled
    console.print(f"\nSmart Routing: {'[green]Enabled[/green]' if is_enabled else '[dim]Disabled[/dim]'}")
    
    if not is_enabled:
        if Confirm.ask("Enable smart routing?", default=True):
            result = asyncio.run(tool.execute(path="routing.enabled", value=True))
            console.print(f"[green]{result}[/green]")
            is_enabled = True
    
    if is_enabled:
        console.print("\n[dim]Smart routing is active. The bot will automatically select models based on query complexity.[/dim]\n")
        
        # Show current tier configuration
        console.print("[bold]Current Model Tiers:[/bold]")
        tiers_table = Table(box=box.ROUNDED)
        tiers_table.add_column("Tier", style="cyan")
        tiers_table.add_column("Model", style="green")
        tiers_table.add_column("Cost/M tokens", style="yellow")
        tiers_table.add_column("Use Case", style="dim")
        
        tiers_info = [
            ("Simple", config.routing.tiers.simple, "Quick queries, greetings"),
            ("Medium", config.routing.tiers.medium, "General questions"),
            ("Complex", config.routing.tiers.complex, "Deep analysis"),
            ("Reasoning", config.routing.tiers.reasoning, "Multi-step logic"),
            ("Coding", config.routing.tiers.coding, "Code generation"),
        ]
        
        for tier_name, tier_config, use_case in tiers_info:
            tiers_table.add_row(
                tier_name,
                tier_config.model,
                f"${tier_config.cost_per_mtok:.2f}",
                use_case
            )
        
        console.print(tiers_table)
        
        # Ask if user wants to customize
        console.print("\n[1] Customize tier models")
        console.print("[2] Adjust confidence thresholds")
        console.print("[0] Back")
        
        choice = Prompt.ask("Select", choices=["0", "1", "2"], default="0")
        
        if choice == "1":
            console.print("\n[bold]Customize Model Tiers:[/bold]")
            console.print("Select a tier to customize:\n")
            
            for i, (tier_name, _, use_case) in enumerate(tiers_info, 1):
                console.print(f"  [{i}] {tier_name} - {use_case}")
            console.print("  [0] Back")
            
            tier_choice = Prompt.ask("Select tier", choices=["0", "1", "2", "3", "4", "5"], default="0")
            
            if tier_choice != "0":
                tier_names = ["simple", "medium", "complex", "reasoning", "coding"]
                selected_tier = tier_names[int(tier_choice) - 1]
                
                console.print(f"\n[bold]Configure {selected_tier.title()} Tier:[/bold]")
                
                new_model = Prompt.ask("Enter model name (or press Enter to keep current)", default="")
                if new_model:
                    result = asyncio.run(tool.execute(
                        path=f"routing.tiers.{selected_tier}.model",
                        value=new_model
                    ))
                    console.print(f"[green]{result}[/green]")
                
                secondary = Prompt.ask("Enter secondary/fallback model (optional)", default="")
                if secondary:
                    result = asyncio.run(tool.execute(
                        path=f"routing.tiers.{selected_tier}.secondaryModel",
                        value=secondary
                    ))
                    console.print(f"[green]{result}[/green]")
        
        elif choice == "2":
            console.print("\n[bold]Confidence Thresholds:[/bold]")
            console.print(f"Current client classifier confidence: {config.routing.client_classifier.min_confidence}")
            
            new_confidence = Prompt.ask(
                "Enter new confidence threshold (0.0-1.0, or press Enter to keep)",
                default=""
            )
            if new_confidence:
                result = asyncio.run(tool.execute(
                    path="routing.clientClassifier.minConfidence",
                    value=float(new_confidence)
                ))
                console.print(f"[green]{result}[/green]")


def _configure_tools():
    """Configure tool settings."""
    tool = UpdateConfigTool()
    
    console.print(Panel(
        "[bold]Tool Settings[/bold]",
        border_style="blue"
    ))
    
    # Show menu
    console.print("\n[dim]What would you like to configure?[/dim]")
    console.print("  [1] Security Settings (Evolutionary mode)")
    console.print("  [2] Web Search API Key")
    console.print("  [0] Back")
    console.print()
    
    choice = Prompt.ask("Select", choices=["0", "1", "2"], default="1")
    
    if choice == "0":
        return
    
    if choice == "1":
        console.print("\n[dim]Security Settings:[/dim]")
        
        # Evolutionary mode
        config = load_config()
        is_evolutionary = config.tools.evolutionary
        
        console.print(f"\nEvolutionary mode: {'[green]Enabled[/green]' if is_evolutionary else '[dim]Disabled[/dim]'}")
        console.print("[dim]Allows bot to modify its own source code[/dim]")
        
        if Confirm.ask(
            f"{'Disable' if is_evolutionary else 'Enable'} evolutionary mode?",
            default=False
        ):
            with console.status("[cyan]Updating security settings...[/cyan]", spinner="dots"):
                result = asyncio.run(tool.execute(
                    path="tools.evolutionary",
                    value=not is_evolutionary
                ))
            console.print(f"[green]{result}[/green]")
            
            if not is_evolutionary:  # Just enabled
                console.print("\n[yellow]⚠ Security Warning:[/yellow]")
                console.print("Evolutionary mode allows the bot to modify files outside")
                console.print("the workspace. Make sure allowedPaths is configured correctly.")
    
    elif choice == "2":
        # Web Search API Key
        console.print("\n[dim]Web Search Configuration:[/dim]")
        
        config = load_config()
        has_key = bool(config.tools.web.search.api_key)
        
        console.print(f"\nBrave Search API: {'[green]✓ Configured[/green]' if has_key else '[dim]○ Not configured[/dim]'}")
        console.print("[dim]Required for web search functionality[/dim]")
        console.print("[dim]Get API key from: https://api.search.brave.com/app/keys[/dim]")
        
        if Confirm.ask("\nConfigure Brave Search API key?", default=not has_key):
            api_key = Prompt.ask("Enter Brave Search API key", password=True)
            
            if api_key:
                with console.status("[cyan]Saving web search configuration...[/cyan]", spinner="dots"):
                    result = asyncio.run(tool.execute(
                        path="tools.web.search.apiKey",
                        value=api_key
                    ))
                if "Error" not in result:
                    console.print(f"[green]{result}[/green]")
                    console.print("[dim]Web search is now enabled[/dim]")
                else:
                    console.print(f"[red]{result}[/red]")
            else:
                console.print("[yellow]⚠ No API key provided, skipping[/yellow]")


def _show_detailed_status():
    """Show detailed configuration status."""
    config = load_config()
    config_path = get_config_path()
    
    console.print(Panel(
        "[bold]Detailed Configuration Status[/bold]",
        border_style="blue"
    ))
    
    # Config file location
    console.print(f"\n[dim]Config file:[/dim] {config_path}")
    console.print(f"[dim]Exists:[/dim] {'[green]Yes[/green]' if config_path.exists() else '[red]No[/red]'}\n")
    
    # Providers table
    table = Table(title="Providers", box=box.ROUNDED)
    table.add_column("Provider", style="cyan")
    table.add_column("API Key", style="green")
    table.add_column("Default", style="yellow")
    
    for provider_name in ['openrouter', 'anthropic', 'openai', 'groq', 'deepseek', 'moonshot']:
        provider = getattr(config.providers, provider_name, None)
        has_key = bool(provider and provider.api_key)
        is_default = provider_name in config.agents.defaults.model.lower()
        
        table.add_row(
            provider_name.title(),
            "[green]✓[/green]" if has_key else "[dim]✗[/dim]",
            "[bold]✓[/bold]" if is_default else ""
        )
    
    console.print(table)
    
    # Channels table
    console.print()
    table = Table(title="Channels", box=box.ROUNDED)
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    
    for channel_name in ['telegram', 'discord', 'whatsapp', 'slack', 'email']:
        channel = getattr(config.channels, channel_name, None)
        enabled = bool(channel and getattr(channel, 'enabled', False))
        
        table.add_row(
            channel_name.title(),
            "[green]✓[/green]" if enabled else "[dim]✗[/dim]"
        )
    
    console.print(table)
    
    console.print("\n[dim]Press Enter to continue...[/dim]")
    input()


# Typer app for CLI integration
app = typer.Typer(help="Configure nanobot interactively")


@app.callback(invoke_without_command=True)
def main():
    """Interactive configuration wizard."""
    configure_cli()


if __name__ == "__main__":
    app()
