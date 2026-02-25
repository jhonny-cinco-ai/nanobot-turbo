"""Interactive CLI configuration wizard for nanofolks.

This module provides an interactive configuration interface using
typer and rich for a nice user experience.
"""

import asyncio

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from nanofolks.agent.tools.update_config import UpdateConfigTool
from nanofolks.config.loader import get_config_path, load_config

console = Console()


def configure_cli():
    """Main entry point for the configuration wizard."""
    # Show welcome
    console.print(Panel.fit(
        "[bold bright_magenta]🐱 nanofolks Setup[/bold bright_magenta]\n\n"
        "Configure your nanofolks installation interactively.",
        title="Welcome",
        border_style="bright_magenta"
    ))

    # Check current config status with spinner
    with console.status("[bright_magenta]Loading configuration...[/bright_magenta]", spinner="dots"):
        tool = UpdateConfigTool()
        summary = tool.get_config_summary()

    # Show current status
    _show_status(summary)

    # Main menu loop
    while True:
        choice = _show_main_menu(summary)

        if choice == "exit":
            console.print("\n[green]✓[/green] Configuration complete!")
            console.print("\nYou can now start using nanofolks:")
            console.print("  [bright_magenta]nanofolks chat[/bright_magenta] - Start interactive chat")
            console.print("  [bright_magenta]nanofolks gateway[/bright_magenta] - Start gateway server")
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

        elif choice == "gateway":
            _configure_gateway()

        elif choice == "storage":
            _configure_storage()

        elif choice == "status":
            _show_detailed_status()

        # Refresh summary
        summary = tool.get_config_summary()


def _show_status(summary: dict):
    """Show current configuration status."""
    table = Table(title="Current Configuration", box=box.ROUNDED)
    table.add_column("Component", style="bright_magenta")
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
    from nanofolks.config.loader import load_config
    config = load_config()

    # Check if any tool settings are customized
    has_evolutionary = config.tools.evolutionary
    has_web_search = bool(config.tools.web.search.api_key)
    has_custom_paths = bool(config.tools.allowed_paths)
    has_mcp_servers = bool(config.tools.mcp_servers)

    is_configured = has_evolutionary or has_web_search or has_custom_paths or has_mcp_servers
    return "[green]✓[/green]" if is_configured else "[dim]○[/dim]"


def _get_gateway_status(summary: dict) -> str:
    """Get status indicator for gateway."""
    from nanofolks.config.loader import load_config
    config = load_config()

    # Check if gateway settings differ from defaults
    is_custom_host = config.gateway.host != "0.0.0.0"
    is_custom_port = config.gateway.port != 18790

    is_configured = is_custom_host or is_custom_port
    return "[green]✓[/green]" if is_configured else "[dim]○[/dim]"


def _show_main_menu(summary: dict) -> str:
    """Show main menu and get user choice."""
    has_required = summary['has_required_config']

    console.print(Panel(
        "[bold]Main Menu[/bold]\n"
        "Select a category to configure:",
        border_style="bright_magenta"
    ))

    options = []

    # Check each section's status
    providers_status = "[green]✓[/green]" if has_required else "[dim]○[/dim]"
    channels_status = _get_channels_status(summary)
    agents_status = _get_agents_status(summary)
    routing_status = _get_routing_status(summary)
    tools_status = _get_tools_status(summary)
    gateway_status = _get_gateway_status(summary)

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
        ("6", "gateway", f"🌐 Gateway {gateway_status}"),
        ("7", "storage", "💾 Storage"),
        ("8", "status", "📊 View Full Status"),
        ("9", "exit", "✓ Done" if has_required else "⏭ Skip for now"),
    ])

    for num, key, label in options:
        console.print(f"  [{num}] {label}")

    console.print()

    # Get choice
    choice_map = {num: key for num, key, _ in options}

    while True:
        choice = Prompt.ask(
            "Select option",
            choices=list(choice_map.keys())
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
        border_style="bright_magenta"
    ))

    # Show provider options
    providers_list = list(schema.items())
    for i, (name, info) in enumerate(providers_list, 1):
        configured = summary['providers'].get(name, {}).get('has_key', False)
        status = "[green]✓[/green]" if configured else "[dim]○[/dim]"
        models = ", ".join(info.get('models', [])[:2])
        console.print(f"  [{i}] {status} {name.title()} - {models}...")

    console.print("  [0] Back to main menu")
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
        border_style="bright_magenta"
    ))

    tool = UpdateConfigTool()

    # Show help
    if 'models' in schema:
        console.print("\n[dim]Available models:[/dim]")
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

    # Store API key in OS keyring (secure by default)
    from nanofolks.security.keyring_manager import is_keyring_available
    from nanofolks.security.secret_manager import get_secret_manager

    keyring_available = is_keyring_available()

    if keyring_available:
        # Store in keyring (secure default)
        manager = get_secret_manager()

        with console.status(f"[bright_magenta]Saving {name} API key to OS keyring...[/bright_magenta]", spinner="dots"):
            manager.store_key(name, api_key)

        console.print("[green]✓[/green] API key saved securely to OS keyring")

        # Save marker to config (empty - key loaded from keyring)
        with console.status("[bright_magenta]Updating configuration...[/bright_magenta]", spinner="dots"):
            result = asyncio.run(tool.execute(
                path=f"providers.{name}.apiKey",
                value=""  # Empty - key loaded from keyring
            ))

        console.print("[dim]API key stored in OS Keychain/Keyring (not in config file)[/dim]")
    else:
        # Fallback: store in config file if keyring not available (less secure!)
        console.print("[yellow]⚠ WARNING: OS Keyring not available![/yellow]")
        console.print("[yellow]⚠ API key stored in config file (less secure)[/yellow]")
        console.print("[dim]Recommendation: Set up your OS keyring for better security[/dim]")

        with console.status(f"[bright_magenta]Saving {name} configuration...[/bright_magenta]", spinner="dots"):
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
        border_style="bright_magenta"
    ))

    # Show channel options
    channels_list = list(schema.items())
    for i, (name, info) in enumerate(channels_list, 1):
        enabled = summary['channels'].get(name, {}).get('enabled', False)
        status = "[green]✓ Enabled[/green]" if enabled else "[dim]○ Disabled[/dim]"
        difficulty = info.get('difficulty', 'Medium')
        console.print(f"  [{i}] {status} {name.title()} ({difficulty})")

    console.print("  [0] Back to main menu")
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
    """Configure a single channel with submenu."""
    tool = UpdateConfigTool()

    while True:
        config = load_config()
        channel = getattr(config.channels, name, None)
        is_enabled = getattr(channel, 'enabled', False) if channel else False

        console.print(Panel(
            f"[bold]{name.title()} Configuration[/bold]",
            border_style="bright_magenta"
        ))

        # Show setup notes
        if 'setup_note' in schema:
            console.print(f"\n[yellow]⚠ {schema['setup_note']}[/yellow]")

        # Show current status
        console.print(f"\nStatus: {'[green]Enabled[/green]' if is_enabled else '[dim]Disabled[/dim]'}")

        # Show current configuration values
        if 'fields' in schema and channel:
            console.print("\n[bold]Current Configuration:[/bold]")
            for field_name, field_info in schema['fields'].items():
                if field_info.get('type') == 'boolean':
                    continue
                field_value = getattr(channel, field_name, '')
                if field_value:
                    # Mask sensitive values
                    if 'password' in field_name.lower() or 'secret' in field_name.lower() or 'token' in field_name.lower():
                        display_value = field_value[:4] + '****' if len(field_value) > 4 else '****'
                    else:
                        display_value = field_value
                    console.print(f"  {field_name}: [bright_magenta]{display_value}[/bright_magenta]")

        # Build menu options
        console.print("\n[dim]What would you like to do?[/dim]")

        menu_options = []
        option_num = 1

        # Toggle enable/disable
        toggle_text = "Disable" if is_enabled else "Enable"
        console.print(f"  [{option_num}] {toggle_text} channel")
        menu_options.append(('toggle', None))
        option_num += 1

        # Field configuration options (only show if not enabled, or always show for editing)
        if 'fields' in schema:
            for field_name, field_info in schema['fields'].items():
                if field_info.get('type') == 'boolean':
                    continue
                # Create descriptive label based on field name
                if field_name == 'token':
                    field_label = "bot token"
                elif field_name == 'botToken':
                    field_label = "bot token"
                elif field_name == 'appToken':
                    field_label = "app token"
                elif field_name == 'allowFrom':
                    field_label = "allowed users (allowFrom)"
                elif field_name == 'bridgeUrl':
                    field_label = "bridge URL"
                else:
                    field_label = field_name.replace('_', ' ').title()
                console.print(f"  [{option_num}] Configure {field_label}")
                menu_options.append(('field', field_name, field_info))
                option_num += 1

        # Back option
        console.print("  [0] Back")
        console.print()

        # Get user choice
        choices = [str(i) for i in range(option_num)]
        choice = Prompt.ask("Select", choices=choices, default="0")

        if choice == "0":
            break

        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(menu_options):
            continue

        action = menu_options[choice_idx]

        if action[0] == 'toggle':
            # Toggle channel enabled state
            new_value = not is_enabled
            if new_value:
                # Enabling - check if required fields are set
                missing_fields = []
                if 'fields' in schema and channel:
                    for field_name, field_info in schema['fields'].items():
                        if field_info.get('type') == 'boolean':
                            continue
                        if field_info.get('required', False):
                            field_value = getattr(channel, field_name, '')
                            if not field_value:
                                missing_fields.append(field_name)

                if missing_fields:
                    console.print(f"\n[yellow]⚠ Cannot enable: Missing required fields: {', '.join(missing_fields)}[/yellow]")
                    console.print("[dim]Please configure all required fields first.[/dim]")
                    continue

                # Enable the channel
                with console.status(f"[bright_magenta]Enabling {name} channel...[/bright_magenta]", spinner="dots"):
                    result = asyncio.run(tool.execute(path=f"channels.{name}.enabled", value=True))
                if "Error" not in result:
                    console.print(f"[green]✓ {name.title()} channel enabled![/green]")
                    console.print("[dim]Start the gateway to activate: nanofolks gateway[/dim]")

                    # Check if voice transcription should be enabled (for Telegram/WhatsApp)
                    if name in ['telegram', 'whatsapp']:
                        _check_and_offer_groq_setup()
            else:
                # Disable the channel
                with console.status(f"[bright_magenta]Disabling {name} channel...[/bright_magenta]", spinner="dots"):
                    result = asyncio.run(tool.execute(path=f"channels.{name}.enabled", value=False))
                if "Error" not in result:
                    console.print(f"[green]✓ {name.title()} channel disabled![/green]")

        elif action[0] == 'field':
            # Configure a specific field
            field_name = action[1]
            field_info = action[2]

            help_text = field_info.get('help', '')
            if help_text:
                console.print(f"\n[dim]{help_text}[/dim]")

            # Show current value
            current_value = getattr(channel, field_name, '') if channel else ''
            if current_value:
                console.print(f"[dim]Current value: {current_value}[/dim]")

            # Create descriptive prompt based on field name
            if field_name == 'token':
                prompt_text = "Enter bot token"
            elif field_name == 'botToken':
                prompt_text = "Enter bot token"
            elif field_name == 'appToken':
                prompt_text = "Enter app token"
            elif field_name == 'allowFrom':
                prompt_text = "Enter allowed user IDs/usernames (comma-separated, leave empty for all users)"
            elif field_name == 'bridgeUrl':
                prompt_text = "Enter bridge URL"
            else:
                prompt_text = f"Enter {field_name.replace('_', ' ')}"

            value = Prompt.ask(prompt_text, default=current_value if current_value else '')

            if value:
                result = asyncio.run(tool.execute(
                    path=f"channels.{name}.{field_name}",
                    value=value
                ))
                if "Error" in result:
                    console.print(f"[red]{result}[/red]")
                else:
                    console.print(f"[green]✓ Updated {field_name}[/green]")


def _check_and_offer_groq_setup():
    """Check if Groq is configured and offer to set it up for voice transcription."""
    tool = UpdateConfigTool()
    summary = tool.get_config_summary()

    # Check if Groq is already configured
    groq_configured = summary['providers'].get('groq', {}).get('has_key', False)

    if groq_configured:
        console.print("\n[dim]✓ Voice transcription ready (Groq configured)[/dim]")
        return

    # Offer to set up Groq for voice transcription
    console.print("\n[bold bright_magenta]🎤 Voice Message Support[/bold bright_magenta]")
    console.print("""
[dim]Telegram/WhatsApp users can send voice messages.
To transcribe them, you need Groq's Whisper API (free tier available).[/dim]
    """)

    if Confirm.ask("Enable voice transcription?", default=True):
        console.print("\n[dim]Get your API key from: https://console.groq.com/keys[/dim]")
        api_key = Prompt.ask("Enter Groq API key", password=False)

        if api_key:
            with console.status("[bright_magenta]Saving Groq configuration...[/bright_magenta]", spinner="dots"):
                result = asyncio.run(tool.execute(
                    path="providers.groq.apiKey",
                    value=api_key
                ))
            if "Error" not in result:
                console.print("[green]✓ Voice transcription enabled![/green]")
                console.print("[dim]Your bot will now transcribe voice messages.[/dim]")
            else:
                console.print(f"[red]{result}[/red]")
        else:
            console.print("[yellow]⚠ No API key provided. Voice messages won't be transcribed.[/yellow]")
            console.print("[dim]You can configure this later with: nanofolks configure[/dim]")


def _configure_agents():
    """Configure agent settings."""
    tool = UpdateConfigTool()

    console.print(Panel(
        "[bold]Agent Settings[/bold]",
        border_style="bright_magenta"
    ))

    # Show current settings
    config = load_config()

    console.print("\n[dim]Current settings:[/dim]")
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
    from nanofolks.config.loader import load_config

    tool = UpdateConfigTool()
    config = load_config()

    console.print(Panel(
        "[bold]Smart Routing Configuration[/bold]\n"
        "Smart routing automatically selects the best model based on query complexity",
        border_style="bright_magenta"
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
        tiers_table.add_column("Tier", style="bright_magenta")
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

        # Show classifier model info
        console.print(f"\n[dim]LLM Classifier Model: {config.routing.llm_classifier.model}[/dim]")
        console.print("[dim]Used for ambiguous queries when client classifier is unsure[/dim]")

        # Ask if user wants to customize
        console.print("\n[1] Customize tier models")
        console.print("[2] Adjust confidence thresholds")
        console.print("[3] Change classifier model")
        console.print("[0] Back")

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3"], default="0")

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
                    # Validate the model
                    validation = tool.validate_model_for_routing(new_model)
                    proceed = True
                    if validation['warning']:
                        console.print(f"[yellow]⚠ {validation['warning']}[/yellow]")
                        if validation['suggestion']:
                            console.print(f"[dim]{validation['suggestion']}[/dim]")
                        proceed = Confirm.ask("Continue anyway?", default=False)

                    if proceed:
                        result = asyncio.run(tool.execute(
                            path=f"routing.tiers.{selected_tier}.model",
                            value=new_model
                        ))
                        console.print(f"[green]{result}[/green]")
                    else:
                        console.print("[dim]Cancelled.[/dim]")

                secondary = Prompt.ask("Enter secondary/fallback model (optional)", default="")
                if secondary:
                    # Validate secondary model too
                    validation = tool.validate_model_for_routing(secondary)
                    if validation['warning']:
                        console.print(f"[yellow]⚠ {validation['warning']}[/yellow]")
                        if not Confirm.ask("Continue with this fallback model?", default=True):
                            console.print("[dim]Skipping secondary model.[/dim]")
                        else:
                            result = asyncio.run(tool.execute(
                                path=f"routing.tiers.{selected_tier}.secondaryModel",
                                value=secondary
                            ))
                            console.print(f"[green]{result}[/green]")
                    else:
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

        elif choice == "3":
            # Change LLM classifier model
            console.print("\n[bold]LLM Classifier Model:[/bold]")
            console.print("This model is used to classify ambiguous queries when the client-side classifier is unsure.")
            console.print(f"Current: [bright_magenta]{config.routing.llm_classifier.model}[/bright_magenta]")

            new_model = Prompt.ask("Enter new classifier model (or press Enter to keep)", default="")
            if new_model:
                # Validate the model
                validation = tool.validate_model_for_routing(new_model)
                proceed = True
                if validation['warning']:
                    console.print(f"[yellow]⚠ {validation['warning']}[/yellow]")
                    if validation['suggestion']:
                        console.print(f"[dim]{validation['suggestion']}[/dim]")
                    proceed = Confirm.ask("Continue anyway?", default=False)

                if proceed:
                    result = asyncio.run(tool.execute(
                        path="routing.llmClassifier.model",
                        value=new_model
                    ))
                    console.print(f"[green]{result}[/green]")
                else:
                    console.print("[dim]Cancelled.[/dim]")


def _configure_tools():
    """Configure tool settings."""
    tool = UpdateConfigTool()

    while True:
        console.print(Panel(
            "[bold]Tool Settings[/bold]",
            border_style="bright_magenta"
        ))

        # Show menu
        console.print("\n[dim]What would you like to configure?[/dim]")
        console.print("  [1] Security Settings (Evolutionary mode)")
        console.print("  [2] Web Search API Key")
        console.print("  [3] MCP Servers")
        console.print("  [0] Back")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2", "3"], default="1")

        if choice == "3":
            _configure_mcp_servers()
            return

        if choice == "0":
            return

        if choice == "1":
            # Security Settings submenu loop
            while True:
                config = load_config()
                is_evolutionary = config.tools.evolutionary

                console.print(Panel(
                    "[bold]Security Settings[/bold]",
                    border_style="bright_magenta"
                ))

                # Show current status
                console.print(f"\nEvolutionary mode: {'[green]Enabled[/green]' if is_evolutionary else '[dim]Disabled[/dim]'}")
                console.print("[dim]Allows bot to modify files outside the workspace[/dim]")

                if is_evolutionary:
                    console.print("\n[bold]Path Configuration:[/bold]")
                    console.print("[dim]Allowed Paths (whitelist):[/dim]")
                    for path in config.tools.allowed_paths:
                        console.print(f"  • {path}")
                    if not config.tools.allowed_paths:
                        console.print("  [dim](None - restricted to workspace)[/dim]")

                    console.print("\n[dim]Protected Paths (blacklist):[/dim]")
                    for path in config.tools.protected_paths:
                        console.print(f"  • {path}")

                # Show menu options
                console.print("\n[dim]What would you like to do?[/dim]")
                toggle_text = "Disable" if is_evolutionary else "Enable"
                console.print(f"  [1] {toggle_text} evolutionary mode")
                if is_evolutionary:
                    console.print("  [2] Add allowed path")
                    console.print("  [3] Remove allowed path")
                    console.print("  [4] Add protected path")
                    console.print("  [5] Remove protected path")
                console.print("  [0] Back")
                console.print()

                # Determine available choices based on state
                available_choices = ["0", "1"]
                if is_evolutionary:
                    available_choices.extend(["2", "3", "4", "5"])

                menu_choice = Prompt.ask("Select", choices=available_choices, default="0")

                if menu_choice == "0":
                    break

                if menu_choice == "1":
                    # Toggle evolutionary mode
                    new_value = not is_evolutionary

                    if new_value:
                        # About to enable - show warning first
                        console.print("\n[yellow]⚠ Security Warning:[/yellow]")
                        console.print("Evolutionary mode allows the bot to modify files outside")
                        console.print("the workspace. Only enable if you understand the risks.")
                        console.print("\nDefault allowed paths will be set:")
                        console.print("  • /projects/nanobot-turbo")
                        console.print("  • ~/.nanofolks")

                    if Confirm.ask(
                        f"{'Disable' if is_evolutionary else 'Enable'} evolutionary mode?",
                        default=False
                    ):
                        with console.status("[bright_magenta]Updating security settings...[/bright_magenta]", spinner="dots"):
                            result = asyncio.run(tool.execute(
                                path="tools.evolutionary",
                                value=new_value
                            ))

                            # If enabling, also set default allowed paths
                            if new_value:
                                asyncio.run(tool.execute(
                                    path="tools.allowedPaths",
                                    value=["/projects/nanobot-turbo", "~/.nanofolks"]
                                ))

                        console.print(f"[green]{result}[/green]")
                        if new_value:
                            console.print("[green]✓ Default allowed paths configured[/green]")

                elif menu_choice == "2" and is_evolutionary:
                    # Add allowed path
                    console.print("\n  [1] Enter path to allow")
                    console.print("  [0] Cancel")

                    add_choice = Prompt.ask("Select", choices=["0", "1"], default="0")
                    if add_choice == "0":
                        continue

                    new_path = Prompt.ask("Enter absolute path to allow")
                    if new_path:
                        current_paths = config.tools.allowed_paths
                        if new_path not in current_paths:
                            updated_paths = current_paths + [new_path]
                            with console.status("[bright_magenta]Adding path...[/bright_magenta]", spinner="dots"):
                                asyncio.run(tool.execute(
                                    path="tools.allowedPaths",
                                    value=updated_paths
                                ))
                            console.print(f"[green]✓ Added {new_path}[/green]")
                        else:
                            console.print("[yellow]Path already allowed[/yellow]")

                elif menu_choice == "3" and is_evolutionary:
                    # Remove allowed path
                    if not config.tools.allowed_paths:
                        console.print("[yellow]No paths to remove[/yellow]")
                        continue

                    console.print("\nSelect path to remove:")
                    for i, path in enumerate(config.tools.allowed_paths, 1):
                        console.print(f"  [{i}] {path}")
                    console.print("  [0] Cancel")

                    rm_idx = Prompt.ask("Select number", choices=["0"] + [str(i) for i in range(1, len(config.tools.allowed_paths)+1)], default="0")
                    if rm_idx == "0":
                        continue

                    path_to_remove = config.tools.allowed_paths[int(rm_idx)-1]

                    updated_paths = [p for p in config.tools.allowed_paths if p != path_to_remove]
                    with console.status("[bright_magenta]Removing path...[/bright_magenta]", spinner="dots"):
                        asyncio.run(tool.execute(
                            path="tools.allowedPaths",
                            value=updated_paths
                        ))
                    console.print(f"[green]✓ Removed {path_to_remove}[/green]")

                elif menu_choice == "4" and is_evolutionary:
                    # Add protected path
                    console.print("\n  [1] Enter path to protect (blacklist)")
                    console.print("  [0] Cancel")

                    add_choice = Prompt.ask("Select", choices=["0", "1"], default="0")
                    if add_choice == "0":
                        continue

                    new_path = Prompt.ask("Enter absolute path to protect (blacklist)")
                    if new_path:
                        current_paths = config.tools.protected_paths
                        if new_path not in current_paths:
                            updated_paths = current_paths + [new_path]
                            with console.status("[bright_magenta]Adding protected path...[/bright_magenta]", spinner="dots"):
                                asyncio.run(tool.execute(
                                    path="tools.protectedPaths",
                                    value=updated_paths
                                ))
                            console.print(f"[green]✓ Added {new_path} to protected paths[/green]")
                        else:
                            console.print("[yellow]Path already protected[/yellow]")

                elif menu_choice == "5" and is_evolutionary:
                    # Remove protected path
                    if not config.tools.protected_paths:
                        console.print("[yellow]No protected paths to remove[/yellow]")
                        continue

                    console.print("\nSelect protected path to remove:")
                    for i, path in enumerate(config.tools.protected_paths, 1):
                        console.print(f"  [{i}] {path}")
                    console.print("  [0] Cancel")

                    rm_idx = Prompt.ask("Select number", choices=["0"] + [str(i) for i in range(1, len(config.tools.protected_paths)+1)], default="0")
                    if rm_idx == "0":
                        continue
                    path_to_remove = config.tools.protected_paths[int(rm_idx)-1]

                    updated_paths = [p for p in config.tools.protected_paths if p != path_to_remove]
                    with console.status("[bright_magenta]Removing protected path...[/bright_magenta]", spinner="dots"):
                        asyncio.run(tool.execute(
                            path="tools.protectedPaths",
                            value=updated_paths
                        ))
                    console.print(f"[green]✓ Removed {path_to_remove} from protected paths[/green]")

        elif choice == "2":
            # Web Search API Key
            console.print("\n[dim]Web Search Configuration:[/dim]")

            config = load_config()
            has_key = bool(config.tools.web.search.api_key)

            console.print(f"\nBrave Search API: {'[green]✓ Configured[/green]' if has_key else '[dim]○ Not configured[/dim]'}")
            console.print("[dim]Required for web search functionality[/dim]")
            console.print("[dim]Get API key from: https://api.search.brave.com/app/keys[/dim]")

            console.print("\n  [1] Enter API key")
            console.print("  [0] Back")
            console.print()

            choice = Prompt.ask("Select", choices=["0", "1"], default="1")

            if choice == "1":
                api_key = Prompt.ask("Enter Brave Search API key", password=False)

                if api_key:
                    # Store in OS keyring (secure by default)
                    from nanofolks.security.keyring_manager import (
                        get_keyring_manager,
                        is_keyring_available,
                    )

                    keyring_available = is_keyring_available()

                    if keyring_available:
                        keyring = get_keyring_manager()
                        with console.status("[bright_magenta]Saving Brave Search API key to OS keyring...[/bright_magenta]", spinner="dots"):
                            keyring.store_key("brave", api_key)

                        # Save marker to config
                        result = asyncio.run(tool.execute(
                            path="tools.web.search.apiKey",
                            value="__KEYRING__"  # Marker for keyring
                        ))
                        console.print("[green]✓[/green] API key saved securely to OS keyring")
                    else:
                        # Fallback to config file
                        with console.status("[bright_magenta]Saving web search configuration...[/bright_magenta]", spinner="dots"):
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


def _configure_gateway():
    """Configure gateway server settings."""
    tool = UpdateConfigTool()

    while True:
        config = load_config()

        console.print(Panel(
            "[bold]Gateway Configuration[/bold]",
            border_style="bright_magenta"
        ))

        # Show current settings
        console.print("\n[bold]Current Settings:[/bold]")
        console.print(f"  Host: [bright_magenta]{config.gateway.host}[/bright_magenta]")
        console.print(f"  Port: [bright_magenta]{config.gateway.port}[/bright_magenta]")
        console.print("\n[dim]The gateway server listens for incoming requests from chat channels.[/dim]")

        # Show menu
        console.print("\n[dim]What would you like to do?[/dim]")
        console.print("  [1] Change host")
        console.print("  [2] Change port")
        console.print("  [0] Back")
        console.print()

        choice = Prompt.ask("Select", choices=["0", "1", "2"], default="0")

        if choice == "0":
            break

        elif choice == "1":
            new_host = Prompt.ask("Enter new host (e.g., 0.0.0.0, 127.0.0.1, localhost)", default=config.gateway.host)
            if new_host and new_host != config.gateway.host:
                with console.status("[bright_magenta]Updating host...[/bright_magenta]", spinner="dots"):
                    result = asyncio.run(tool.execute(
                        path="gateway.host",
                        value=new_host
                    ))
                console.print(f"[green]{result}[/green]")

        elif choice == "2":
            new_port = Prompt.ask("Enter new port", default=str(config.gateway.port))
            if new_port:
                try:
                    port_int = int(new_port)
                    if port_int != config.gateway.port:
                        with console.status("[bright_magenta]Updating port...[/bright_magenta]", spinner="dots"):
                            result = asyncio.run(tool.execute(
                                path="gateway.port",
                                value=port_int
                            ))
                        console.print(f"[green]{result}[/green]")
                except ValueError:
                    console.print("[red]Invalid port number[/red]")


def _configure_storage():
    """Configure storage settings."""
    tool = UpdateConfigTool()

    console.print(Panel(
        "[bold]Storage Configuration[/bold]\n\n"
        "Configure storage behavior for session data.",
        border_style="bright_magenta"
    ))

    config = load_config()
    use_cas = getattr(config.storage, 'use_cas_storage', True)

    console.print(f"\nCAS Storage: {'[green]Enabled[/green]' if use_cas else '[dim]Disabled[/dim]'}")
    console.print("[dim]CAS (Compare-And-Set) provides conflict-free concurrent writes.[/dim]")
    console.print("[dim]Enable this for multi-channel setups to prevent file corruption.[/dim]")

    console.print("\n  [1] Toggle CAS Storage")
    console.print("  [0] Back")
    console.print()

    choice = Prompt.ask("Select", choices=["0", "1"], default="0")

    if choice == "1":
        new_value = not use_cas
        with console.status("[bright_magenta]Updating storage settings...[/bright_magenta]", spinner="dots"):
            result = asyncio.run(tool.execute(
                path="storage.use_cas_storage",
                value=new_value
            ))
        if "Error" not in result:
            status = "enabled" if new_value else "disabled"
            console.print(f"[green]✓ CAS Storage {status}[/green]")
        else:
            console.print(f"[red]{result}[/red]")


def _configure_mcp_servers():
    """Configure MCP (Model Context Protocol) servers."""
    tool = UpdateConfigTool()

    while True:
        config = load_config()
        mcp_servers = config.tools.mcp_servers or {}

        console.print(Panel(
            "[bold]MCP Servers Configuration[/bold]\n\n"
            "MCP servers provide additional tools to nanofolks.\n"
            "Configure stdio servers (npx, uvx) or HTTP endpoints.",
            border_style="bright_magenta"
        ))

        # Show current servers
        if mcp_servers:
            console.print("\n[bold]Configured Servers:[/bold]")
            for name, server_config in mcp_servers.items():
                if server_config.url:
                    console.print(f"  • {name}: [bright_magenta]{server_config.url}[/bright_magenta] (HTTP)")
                else:
                    cmd = server_config.command or "?"
                    args = " ".join(server_config.args or [])
                    console.print(f"  • {name}: [bright_magenta]{cmd} {args}[/bright_magenta] (stdio)")
        else:
            console.print("\n[dim]No MCP servers configured[/dim]")

        # Menu
        console.print("\n[dim]What would you like to do?[/dim]")
        console.print("  [1] Add MCP server")
        if mcp_servers:
            console.print("  [2] Remove MCP server")
            console.print("  [3] Test connection")
        console.print("  [0] Back")
        console.print()

        choices = ["0", "1"]
        if mcp_servers:
            choices.extend(["2", "3"])

        choice = Prompt.ask("Select", choices=choices, default="0")

        if choice == "0":
            return

        elif choice == "1":
            _add_mcp_server(tool)

        elif choice == "2" and mcp_servers:
            _remove_mcp_server(tool, mcp_servers)

        elif choice == "3" and mcp_servers:
            _test_mcp_server(mcp_servers)


def _add_mcp_server(tool: UpdateConfigTool):
    """Add a new MCP server."""
    console.print(Panel(
        "[bold]Add MCP Server[/bold]\n\n"
        "Choose connection type:",
        border_style="bright_magenta"
    ))

    console.print("  [1] Stdio (local command like npx, uvx)")
    console.print("  [2] HTTP (remote server)")
    console.print("  [0] Cancel")
    console.print()

    conn_type = Prompt.ask("Select", choices=["0", "1", "2"], default="0")

    if conn_type == "0":
        return

    # Get server name
    server_name = Prompt.ask("Enter server name (e.g., filesystem, github, brave)")
    if not server_name:
        console.print("[red]Server name required[/red]")
        return

    # Clean name for config key
    config_key = server_name.lower().replace(" ", "_")

    if conn_type == "1":
        # Stdio configuration
        command = Prompt.ask("Enter command (e.g., npx, uvx, python)")
        if not command:
            console.print("[red]Command required[/red]")
            return

        args_input = Prompt.ask(
            "Enter arguments (e.g., -y @modelcontextprotocol/server-filesystem /path)",
            default=""
        )
        args = args_input.split() if args_input else []

        # Build config
        server_config = {
            "command": command,
            "args": args,
            "env": {},
            "url": ""
        }

    elif conn_type == "2":
        # HTTP configuration
        url = Prompt.ask("Enter HTTP endpoint URL (e.g., http://localhost:3000/mcp)")
        if not url:
            console.print("[red]URL required[/red]")
            return

        server_config = {
            "command": "",
            "args": [],
            "env": {},
            "url": url
        }

    else:
        return

    # Save to config
    with console.status("[bright_magenta]Saving MCP server...[/bright_magenta]", spinner="dots"):
        try:
            # Get current MCP servers config
            config = load_config()
            mcp_servers = config.tools.mcp_servers or {}
            mcp_servers[config_key] = server_config

            asyncio.run(tool.execute(
                path="tools.mcp_servers",
                value=mcp_servers
            ))
            console.print(f"[green]✓ MCP server '{server_name}' added[/green]")
            console.print("\n[dim]Restart nanofolks for changes to take effect.[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to add MCP server: {e}[/red]")


def _remove_mcp_server(tool: UpdateConfigTool, mcp_servers: dict):
    """Remove an MCP server."""
    console.print("\n[bold]Select server to remove:[/bold]")

    servers = list(mcp_servers.keys())
    for i, name in enumerate(servers, 1):
        console.print(f"  [{i}] {name}")
    console.print("  [0] Cancel")
    console.print()

    choice = Prompt.ask(
        "Select",
        choices=["0"] + [str(i) for i in range(1, len(servers) + 1)],
        default="0"
    )

    if choice == "0":
        return

    server_to_remove = servers[int(choice) - 1]

    if Confirm.ask(f"Remove MCP server '{server_to_remove}'?", default=False):
        with console.status("[bright_magenta]Removing MCP server...[/bright_magenta]", spinner="dots"):
            try:
                del mcp_servers[server_to_remove]
                asyncio.run(tool.execute(
                    path="tools.mcp_servers",
                    value=mcp_servers
                ))
                console.print(f"[green]✓ MCP server '{server_to_remove}' removed[/green]")
                console.print("\n[dim]Restart nanofolks for changes to take effect.[/dim]")
            except Exception as e:
                console.print(f"[red]Failed to remove MCP server: {e}[/red]")


def _test_mcp_server(mcp_servers: dict):
    """Test connection to an MCP server."""
    console.print("\n[bold]Select server to test:[/bold]")

    servers = list(mcp_servers.keys())
    for i, name in enumerate(servers, 1):
        console.print(f"  [{i}] {name}")
    console.print("  [0] Cancel")
    console.print()

    choice = Prompt.ask(
        "Select",
        choices=["0"] + [str(i) for i in range(1, len(servers) + 1)],
        default="0"
    )

    if choice == "0":
        return

    server_name = servers[int(choice) - 1]
    server_config = mcp_servers[server_name]

    console.print(f"\n[bright_magenta]Testing connection to '{server_name}'...[/bright_magenta]")

    # This is a simplified test - just check if we can list tools
    # In practice, you'd want to actually connect and list tools
    if server_config.get("url"):
        console.print(f"  URL: {server_config['url']}")
    else:
        cmd = server_config.get("command", "?")
        args = " ".join(server_config.get("args", []))
        console.print(f"  Command: {cmd} {args}")

    console.print("\n[yellow]Note: Full connection test requires restarting nanofolks.[/dim]")
    console.print("[dim]The server will be available after restart if configured correctly.[/dim]")


def _show_detailed_status():
    """Show detailed configuration status."""
    config = load_config()
    config_path = get_config_path()

    console.print(Panel(
        "[bold]Detailed Configuration Status[/bold]",
        border_style="bright_magenta"
    ))

    # Config file location
    console.print(f"\n[dim]Config file:[/dim] {config_path}")
    console.print(f"[dim]Exists:[/dim] {'[green]Yes[/green]' if config_path.exists() else '[red]No[/red]'}\n")

    # ═══════════════════════════════════════════════════════════
    # AGENT SETTINGS
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Agent Settings[/bold bright_magenta]")
    if config.routing.enabled:
        console.print(f"  Default Model: [dim]{config.agents.defaults.model}[/dim] [yellow](overridden by Smart Routing)[/yellow]")
    else:
        console.print(f"  Default Model: [green]{config.agents.defaults.model}[/green]")
    console.print(f"  Temperature: {config.agents.defaults.temperature}")
    console.print(f"  Max Tokens: {config.agents.defaults.max_tokens}")
    console.print(f"  Max Tool Iterations: {config.agents.defaults.max_tool_iterations}")
    console.print(f"  Workspace: {config.agents.defaults.workspace}\n")

    # ═══════════════════════════════════════════════════════════
    # MODEL PROVIDERS
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Model Providers[/bold bright_magenta]")
    default_model = config.agents.defaults.model

    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Provider", style="bright_magenta")
    table.add_column("API Key", style="green", justify="center")
    table.add_column("Status", style="yellow")

    all_providers = [
        'openrouter', 'anthropic', 'openai', 'groq', 'deepseek',
        'moonshot', 'gemini', 'zhipu', 'dashscope', 'aihubmix', 'vllm'
    ]

    # Determine active provider
    active_provider = None
    if '/' in default_model:
        # Gateway usage
        model_parts = default_model.split('/')
        if len(model_parts) >= 2:
            active_provider = model_parts[0].lower()
    else:
        # Direct provider usage
        model_lower = default_model.lower()
        for provider_name in all_providers:
            if provider_name in model_lower:
                active_provider = provider_name
                break

    for provider_name in all_providers:
        provider = getattr(config.providers, provider_name, None)
        has_key = bool(provider and provider.api_key)

        if has_key and provider_name == active_provider:
            status = "[bold green]← Active[/bold green]"
        elif has_key:
            status = "[dim]Available[/dim]"
        else:
            status = ""

        table.add_row(
            provider_name.title(),
            "[green]✓[/green]" if has_key else "[dim]✗[/dim]",
            status
        )

    console.print(table)
    console.print()

    # ═══════════════════════════════════════════════════════════
    # SMART ROUTING
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Smart Routing[/bold bright_magenta]")
    if config.routing.enabled:
        console.print("  Status: [green]Enabled[/green]")
        console.print("\n  [dim]Tier Configuration:[/dim]")

        tiers_table = Table(box=box.SIMPLE)
        tiers_table.add_column("Tier", style="bright_magenta")
        tiers_table.add_column("Model", style="green")
        tiers_table.add_column("Cost/Mtok", style="yellow")

        tiers = [
            ("Simple", config.routing.tiers.simple),
            ("Medium", config.routing.tiers.medium),
            ("Complex", config.routing.tiers.complex),
            ("Reasoning", config.routing.tiers.reasoning),
            ("Coding", config.routing.tiers.coding),
        ]

        for tier_name, tier_config in tiers:
            tiers_table.add_row(
                tier_name,
                tier_config.model,
                f"${tier_config.cost_per_mtok:.2f}"
            )

        console.print(tiers_table)
        console.print(f"\n  Client Classifier Confidence: {config.routing.client_classifier.min_confidence}")
    else:
        console.print("  Status: [dim]Disabled[/dim]")
    console.print()

    # ═══════════════════════════════════════════════════════════
    # GATEWAY SERVER
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Gateway Server[/bold bright_magenta]")
    console.print(f"  Host: [bright_magenta]{config.gateway.host}[/bright_magenta]")
    console.print(f"  Port: [bright_magenta]{config.gateway.port}[/bright_magenta]")
    console.print(f"  URL: http://{config.gateway.host}:{config.gateway.port}\n")

    # ═══════════════════════════════════════════════════════════
    # CHAT CHANNELS
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Chat Channels[/bold bright_magenta]")

    channels_table = Table(box=box.SIMPLE_HEAD)
    channels_table.add_column("Channel", style="bright_magenta")
    channels_table.add_column("Status", style="green")
    channels_table.add_column("Details", style="dim")

    for channel_name in ['telegram', 'discord', 'whatsapp', 'slack', 'email']:
        channel = getattr(config.channels, channel_name, None)
        enabled = bool(channel and getattr(channel, 'enabled', False))

        # Build details string
        details = ""
        if channel and enabled:
            detail_parts = []

            # Check for key/token fields
            token_fields = ['token', 'bot_token', 'botToken', 'app_token', 'appToken']
            for field in token_fields:
                if hasattr(channel, field):
                    value = getattr(channel, field)
                    if value:
                        detail_parts.append("Auth configured")
                        break

            # Check for allow list
            if hasattr(channel, 'allow_from') and channel.allow_from:
                detail_parts.append(f"{len(channel.allow_from)} allowed")

            details = ", ".join(detail_parts) if detail_parts else ""

        channels_table.add_row(
            channel_name.title(),
            "[green]Enabled[/green]" if enabled else "[dim]Disabled[/dim]",
            details
        )

    console.print(channels_table)
    console.print()

    # ═══════════════════════════════════════════════════════════
    # TOOL SETTINGS
    # ═══════════════════════════════════════════════════════════
    console.print("[bold bright_magenta]Tool Settings[/bold bright_magenta]")

    # Web Search
    has_web_search = bool(config.tools.web.search.api_key)
    console.print(f"  Web Search: {'[green]Configured[/green]' if has_web_search else '[dim]Not configured[/dim]'}")
    if has_web_search:
        console.print(f"    Max Results: {config.tools.web.search.max_results}")

    # Evolutionary Mode
    console.print(f"\n  Evolutionary Mode: {'[green]Enabled[/green]' if config.tools.evolutionary else '[dim]Disabled[/dim]'}")
    if config.tools.evolutionary:
        console.print(f"    Allowed Paths: {len(config.tools.allowed_paths)} paths")
        for path in config.tools.allowed_paths[:3]:  # Show first 3
            console.print(f"      • {path}")
        if len(config.tools.allowed_paths) > 3:
            console.print(f"      ... and {len(config.tools.allowed_paths) - 3} more")

        console.print(f"\n    Protected Paths: {len(config.tools.protected_paths)} paths")
        for path in config.tools.protected_paths[:3]:  # Show first 3
            console.print(f"      • {path}")
        if len(config.tools.protected_paths) > 3:
            console.print(f"      ... and {len(config.tools.protected_paths) - 3} more")

    console.print(f"\n  Restrict to Workspace: {'[green]Yes[/green]' if config.tools.restrict_to_workspace else '[dim]No[/dim]'}")

    # Exit with consistent UX
    console.print("\n[dim]Press Enter or select:[/dim]")
    console.print("  [0] Back")
    Prompt.ask("Select", choices=["0"], default="0")
    return


# Typer app for CLI integration
app = typer.Typer(help="Configure nanofolks interactively")


@app.callback(invoke_without_command=True)
def main():
    """Interactive configuration wizard."""
    configure_cli()


if __name__ == "__main__":
    app()
