"""Security-related CLI commands for keyring and key management."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table

from nanofolks.security.keyring_manager import KeyringManager, get_keyring_manager, is_keyring_available
from nanofolks.config.loader import load_config, save_config, KEYRING_MARKER

app = typer.Typer(help="Security commands for key management")
console = Console()


@app.command("status")
def keyring_status():
    """Check keyring availability and status."""
    console.print("\n[bold]Keyring Status[/bold]\n")
    
    available = is_keyring_available()
    
    if available:
        console.print("[green]✓[/green] OS Keyring is available")
    else:
        console.print("[red]✗[/red] OS Keyring is not available")
        console.print("[yellow]Keys will be stored in config file instead[/yellow]")
        return
    
    # Show stored keys
    keyring = get_keyring_manager()
    stored_keys = keyring.list_keys()
    
    if stored_keys:
        console.print(f"\n[green]Keys stored in keyring:[/green] {len(stored_keys)}")
        for key in stored_keys:
            console.print(f"  • {key}")
    else:
        console.print("\n[yellow]No keys stored in keyring yet[/yellow]")


@app.command("list")
def list_keys():
    """List all API keys (shows which are in keyring vs config)."""
    from nanofolks.config.loader import PROVIDERS_WITH_KEYS
    
    console.print("\n[bold]API Key Status[/bold]\n")
    
    config = load_config()
    keyring = get_keyring_manager()
    keyring_available = keyring.is_available()
    
    table = Table(show_header=True, header_style="bold")
    table.add_column("Provider")
    table.add_column("Location")
    table.add_column("Status")
    
    for provider_name in PROVIDERS_WITH_KEYS:
        provider = getattr(config.providers, provider_name, None)
        
        if not provider:
            continue
        
        api_key = provider.api_key
        
        if not api_key:
            table.add_row(provider_name, "-", "[dim]Not configured[/dim]")
        elif api_key == KEYRING_MARKER:
            if keyring_available and keyring.has_key(provider_name):
                table.add_row(provider_name, "Keyring", "[green]✓ Configured[/green]")
            else:
                table.add_row(provider_name, "Keyring", "[red]✗ Missing[/red]")
        else:
            table.add_row(provider_name, "Config File", "[yellow]⚠ Plain text[/yellow]")
    
    console.print(table)
    console.print("\n[dim]Run 'nanofolks security migrate-to-keyring' to move keys to secure storage[/dim]")


@app.command("migrate-to-keyring")
def migrate_to_keyring(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be migrated without actually migrating"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Specific provider to migrate"),
):
    """Migrate API keys from config file to OS keyring."""
    console.print("\n[bold]Migrating Keys to Keyring[/bold]\n")
    
    if not is_keyring_available():
        console.print("[red]Error: OS Keyring is not available[/red]")
        console.print("[yellow]Please install keyring package: pip install keyring[/yellow]")
        raise typer.Exit(1)
    
    config = load_config()
    keyring = get_keyring_manager()
    
    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be made[/yellow]\n")
    
    migrated = []
    
    from nanofolks.config.loader import PROVIDERS_WITH_KEYS
    
    # Migrate specific provider or all
    providers_to_migrate = [provider] if provider else PROVIDERS_WITH_KEYS
    
    for provider_name in providers_to_migrate:
        provider_obj = getattr(config.providers, provider_name, None)
        
        if not provider_obj or not provider_obj.api_key:
            continue
        
        if provider_obj.api_key == KEYRING_MARKER:
            console.print(f"[dim]• {provider_name}: Already in keyring[/dim]")
            continue
        
        if dry_run:
            console.print(f"[yellow]→ {provider_name}: Would migrate (key: {provider_obj.api_key[:10]}...)[/yellow]")
        else:
            keyring.store_key(provider_name, provider_obj.api_key)
            provider_obj.api_key = KEYRING_MARKER
            console.print(f"[green]✓ {provider_name}: Migrated to keyring[/green]")
            migrated.append(provider_name)
    
    # Also check brave search
    if config.tools and config.tools.web and config.tools.web.search:
        brave_key = config.tools.web.search.api_key
        if brave_key and brave_key != KEYRING_MARKER:
            if provider and provider != "brave":
                pass  # Skip if specific provider requested
            else:
                if dry_run:
                    console.print(f"[yellow]→ brave: Would migrate[/yellow]")
                else:
                    keyring.store_key("brave", brave_key)
                    config.tools.web.search.api_key = KEYRING_MARKER
                    console.print(f"[green]✓ brave: Migrated to keyring[/green]")
                    migrated.append("brave")
    
    if not dry_run and migrated:
        # Save config with keyring markers
        save_config(config)
        console.print(f"\n[green]Successfully migrated {len(migrated)} key(s) to keyring[/green]")
        console.print("[dim]Config file now references keyring instead of plain text keys[/dim]")
    elif dry_run and not migrated:
        console.print("\n[dim]No keys need to be migrated[/dim]")


@app.command("remove")
def remove_key(
    provider: str = typer.Argument(..., help="Provider name to remove key for"),
    force: bool = typer.Option(False, "--force", "-f", help="Don't ask for confirmation"),
):
    """Remove a key from the OS keyring."""
    console.print(f"\n[bold]Removing Key for {provider}[/bold]\n")
    
    keyring = get_keyring_manager()
    
    if not keyring.has_key(provider):
        console.print(f"[yellow]No key found for '{provider}' in keyring[/yellow]")
        raise typer.Exit(1)
    
    if not force:
        confirm = typer.confirm(f"Delete key for '{provider}' from keyring?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)
    
    keyring.delete_key(provider)
    console.print(f"[green]✓[/green] Deleted key for '{provider}' from keyring")


@app.command("add")
def add_key(
    provider: str = typer.Argument(..., help="Provider name (e.g., openrouter, anthropic)"),
    key: str = typer.Option(None, "--key", "-k", help="API key (will prompt if not provided)"),
):
    """Add an API key to the OS keyring."""
    from rich.prompt import Prompt
    
    console.print(f"\n[bold]Adding Key for {provider}[/bold]\n")
    
    if not is_keyring_available():
        console.print("[red]Error: OS Keyring is not available[/red]")
        raise typer.Exit(1)
    
    # Get key from option or prompt
    if not key:
        key = Prompt.ask(f"Enter API key for {provider}", password=True)
    
    if not key:
        console.print("[red]Error: No API key provided[/red]")
        raise typer.Exit(1)
    
    keyring = get_keyring_manager()
    keyring.store_key(provider, key)
    
    console.print(f"[green]✓[/green] Stored API key for '{provider}' in keyring")
    console.print(f"\n[dim]You can now remove the key from your config file and use '{KEYRING_MARKER}' instead[/dim]")


if __name__ == "__main__":
    app()
