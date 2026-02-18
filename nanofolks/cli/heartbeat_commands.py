"""CLI commands for managing bot heartbeats.

Provides commands for controlling the multi-heartbeat system:
- nanofolks heartbeat start [--bot BOT_NAME]
- nanofolks heartbeat stop [--bot BOT_NAME]
- nanofolks heartbeat status [--bot BOT_NAME]
- nanofolks heartbeat trigger [--bot BOT_NAME] [--reason REASON]
- nanofolks heartbeat logs [--bot BOT_NAME] [--limit N]
"""

import asyncio
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

heartbeat_app = typer.Typer(help="Manage bot heartbeats")
console = Console()

# Global manager instance (will be set by main CLI)
_manager = None


def set_heartbeat_manager(manager):
    """Set the global heartbeat manager instance."""
    global _manager
    _manager = manager


def _get_manager():
    """Get the heartbeat manager, with error handling."""
    global _manager
    if _manager is None:
        console.print("[red]❌ Error: Heartbeat manager not initialized[/red]")
        console.print("[dim]This command requires the bot agent to be running[/dim]")
        raise typer.Exit(1)
    return _manager


@heartbeat_app.command("start")
def heartbeat_start(
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Start specific bot (default: all)"),
):
    """Start heartbeat(s) for bot(s)."""
    manager = _get_manager()

    try:
        if bot:
            # Start specific bot
            found_bot = None
            for b in manager.bots.values():
                if b.name.lower() == bot.lower():
                    found_bot = b
                    break

            if not found_bot:
                console.print(f"[red]❌ Bot '{bot}' not found[/red]")
                console.print(f"[dim]Available bots: {', '.join(b.name for b in manager.bots.values())}[/dim]")
                raise typer.Exit(1)

            if found_bot.is_heartbeat_running:
                console.print(f"[yellow]⚠️ Heartbeat for '{found_bot.name}' is already running[/yellow]")
                return

            asyncio.run(found_bot.start_heartbeat())
            console.print(f"[green]✅ Started heartbeat for '{found_bot.name}'[/green]")
        else:
            # Start all bots
            asyncio.run(manager.start_all())
            console.print("[green]✅ Started heartbeats for all bots[/green]")

            # Show status
            _print_team_status(manager)

    except Exception as e:
        console.print(f"[red]❌ Error starting heartbeat: {e}[/red]")
        logger.exception("Heartbeat start failed")
        raise typer.Exit(1)


@heartbeat_app.command("stop")
def heartbeat_stop(
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Stop specific bot (default: all)"),
):
    """Stop heartbeat(s) for bot(s)."""
    manager = _get_manager()

    try:
        if bot:
            # Stop specific bot
            found_bot = None
            for b in manager.bots.values():
                if b.name.lower() == bot.lower():
                    found_bot = b
                    break

            if not found_bot:
                console.print(f"[red]❌ Bot '{bot}' not found[/red]")
                console.print(f"[dim]Available bots: {', '.join(b.name for b in manager.bots.values())}[/dim]")
                raise typer.Exit(1)

            if not found_bot.is_heartbeat_running:
                console.print(f"[yellow]⚠️ Heartbeat for '{found_bot.name}' is not running[/yellow]")
                return

            asyncio.run(found_bot.stop_heartbeat())
            console.print(f"[green]✅ Stopped heartbeat for '{found_bot.name}'[/green]")
        else:
            # Stop all bots
            asyncio.run(manager.stop_all())
            console.print("[green]✅ Stopped heartbeats for all bots[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error stopping heartbeat: {e}[/red]")
        logger.exception("Heartbeat stop failed")
        raise typer.Exit(1)


@heartbeat_app.command("status")
def heartbeat_status(
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Show status of specific bot (default: all)"),
):
    """Show heartbeat status for bot(s)."""
    manager = _get_manager()

    try:
        if bot:
            # Show specific bot status
            found_bot = None
            for b in manager.bots.values():
                if b.name.lower() == bot.lower():
                    found_bot = b
                    break

            if not found_bot:
                console.print(f"[red]❌ Bot '{bot}' not found[/red]")
                console.print(f"[dim]Available bots: {', '.join(b.name for b in manager.bots.values())}[/dim]")
                raise typer.Exit(1)

            status = asyncio.run(found_bot.get_heartbeat_status())
            _print_bot_status(found_bot, status)
        else:
            # Show all bots status
            _print_team_status(manager)

    except Exception as e:
        console.print(f"[red]❌ Error getting heartbeat status: {e}[/red]")
        logger.exception("Heartbeat status failed")
        raise typer.Exit(1)


@heartbeat_app.command("trigger")
def heartbeat_trigger(
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Trigger specific bot (default: all)"),
    reason: str = typer.Option("Manual trigger", "--reason", "-r", help="Reason for trigger"),
):
    """Manually trigger heartbeat(s) for bot(s)."""
    manager = _get_manager()

    try:
        if bot:
            # Trigger specific bot
            found_bot = None
            for b in manager.bots.values():
                if b.name.lower() == bot.lower():
                    found_bot = b
                    break

            if not found_bot:
                console.print(f"[red]❌ Bot '{bot}' not found[/red]")
                console.print(f"[dim]Available bots: {', '.join(b.name for b in manager.bots.values())}[/dim]")
                raise typer.Exit(1)

            asyncio.run(found_bot.trigger_heartbeat_now(reason))
            console.print(f"[green]✅ Triggered heartbeat for '{found_bot.name}'[/green]")
            console.print(f"[dim]Reason: {reason}[/dim]")
        else:
            # Trigger all bots
            asyncio.run(manager.trigger_team_heartbeat(reason))
            console.print("[green]✅ Triggered heartbeats for all bots[/green]")
            console.print(f"[dim]Reason: {reason}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error triggering heartbeat: {e}[/red]")
        logger.exception("Heartbeat trigger failed")
        raise typer.Exit(1)


@heartbeat_app.command("team-health")
def heartbeat_team_health():
    """Show team health report."""
    manager = _get_manager()

    try:
        health = asyncio.run(manager.get_team_health())

        # Overall status
        overall_pct = health.overall_success_rate * 100
        if overall_pct >= 80:
            overall_color = "green"
            overall_icon = "🟢"
        elif overall_pct >= 50:
            overall_color = "yellow"
            overall_icon = "🟡"
        else:
            overall_color = "red"
            overall_icon = "🔴"

        console.print(Panel(
            f"[{overall_color}]{overall_icon} Team Health: {overall_pct:.1f}%[/{overall_color}]",
            title="[bold]Team Status[/bold]",
            expand=False
        ))

        # Per-bot metrics
        table = Table(title="Bot Metrics")
        table.add_column("Bot", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Ticks", style="blue")
        table.add_column("Success Rate", style="yellow")
        table.add_column("Checks", style="magenta")

        for bot_name, bot_data in health.bots.items():
            running = "✅ Running" if bot_data.get("running") else "⏸️ Stopped"
            success_rate = bot_data.get("success_rate", 0.0) * 100
            passed = bot_data.get("passed_checks", 0)
            total = bot_data.get("total_checks", 0)
            checks = f"{passed}/{total}"
            ticks = bot_data.get("total_ticks", 0)

            table.add_row(
                bot_name,
                running,
                str(ticks),
                f"{success_rate:.1f}%",
                checks
            )

        console.print(table)

        # Alerts
        if health.alerts:
            console.print("\n[bold]⚠️  Alerts:[/bold]")
            for alert in health.alerts:
                console.print(f"  [red]•[/red] {alert}")

        # Timestamp
        console.print(f"\n[dim]Report timestamp: {health.timestamp}[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error getting team health: {e}[/red]")
        logger.exception("Team health failed")
        raise typer.Exit(1)


@heartbeat_app.command("logs")
def heartbeat_logs(
    bot: Optional[str] = typer.Option(None, "--bot", "-b", help="Show logs for specific bot (default: recent)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of log entries to show"),
):
    """Show heartbeat logs."""
    manager = _get_manager()

    try:
        table = Table(title="Recent Heartbeat Logs")
        table.add_column("Timestamp", style="dim")
        table.add_column("Bot", style="cyan")
        table.add_column("Event", style="yellow")
        table.add_column("Details", style="white")

        # Collect logs from all or specific bot
        logs = []

        if bot:
            found_bot = None
            for b in manager.bots.values():
                if b.name.lower() == bot.lower():
                    found_bot = b
                    break

            if not found_bot:
                console.print(f"[red]❌ Bot '{bot}' not found[/red]")
                raise typer.Exit(1)

            # Get heartbeat history from private memory
            history = found_bot.private_memory.get("heartbeat_history", [])
            for entry in history[-limit:]:
                logs.append((entry.get("timestamp", ""), found_bot.name, entry))
        else:
            # Get logs from all bots
            for found_bot in manager.bots.values():
                history = found_bot.private_memory.get("heartbeat_history", [])
                for entry in history[-limit:]:
                    logs.append((entry.get("timestamp", ""), found_bot.name, entry))

        # Sort by timestamp
        logs.sort(key=lambda x: x[0], reverse=True)

        # Display
        for ts, bot_name, entry in logs[:limit]:
            event = entry.get("event", "unknown")
            details = entry.get("details", {})

            event_type = details.get("type", "check")
            if event_type == "check":
                status = "✅" if details.get("success") else "❌"
                detail_str = f"{status} {details.get('check_name', 'unknown')}"
            elif event_type == "tick":
                status = "✅" if details.get("success") else "❌"
                detail_str = f"{status} {details.get('checks_run', 0)} checks"
            else:
                detail_str = str(details)[:50]

            table.add_row(ts, bot_name, event, detail_str)

        console.print(table)

    except Exception as e:
        console.print(f"[red]❌ Error getting logs: {e}[/red]")
        logger.exception("Heartbeat logs failed")
        raise typer.Exit(1)


def _print_team_status(manager):
    """Print team status table."""
    table = Table(title="Bot Heartbeat Status")
    table.add_column("Bot", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Ticks", style="blue")
    table.add_column("Interval", style="yellow")
    table.add_column("Next Run", style="magenta")

    for bot in manager.bots.values():
        status = "✅ Running" if bot.is_heartbeat_running else "⏸️ Stopped"

        # Get heartbeat config
        try:
            from nanofolks.bots.heartbeat_configs import get_bot_heartbeat_config
            config = get_bot_heartbeat_config(bot.name)
            interval_min = config.default_interval // 60
        except Exception:
            interval_min = "?"

        # Get history count
        history = bot.private_memory.get("heartbeat_history", [])
        ticks = len([h for h in history if h.get("event") == "tick"])

        table.add_row(
            bot.name,
            status,
            str(ticks),
            f"{interval_min}m",
            "TBD"  # Would need heartbeat service state to show
        )

    console.print(table)


def _print_bot_status(bot, status):
    """Print detailed status for a single bot."""
    running = status.get("running", False)
    state_text = "🟢 Running" if running else "🔴 Stopped"

    panel = Panel(
        f"{state_text}",
        title=f"[bold]{bot.name} Status[/bold]",
        expand=False
    )
    console.print(panel)

    # Show config details
    try:
        from nanofolks.bots.heartbeat_configs import get_bot_heartbeat_config
        config = get_bot_heartbeat_config(bot.name)

        table = Table(title="Configuration")
        table.add_column("Setting", style="dim")
        table.add_column("Value", style="white")

        table.add_row("Default Interval", f"{config.default_interval // 60}m")
        table.add_row("Max Concurrent", str(config.max_concurrent_checks))
        table.add_row("Parallel Execution", str(config.parallel_checks))

        console.print(table)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")

    # Show history
    history = bot.private_memory.get("heartbeat_history", [])
    if history:
        console.print(f"\n[bold]Recent History ({len(history)} total):[/bold]")

        table = Table()
        table.add_column("Timestamp", style="dim")
        table.add_column("Event", style="cyan")
        table.add_column("Result", style="green")

        for entry in history[-5:]:
            ts = entry.get("timestamp", "")
            event = entry.get("event", "")
            details = entry.get("details", {})

            if event == "tick":
                result = f"✅ {details.get('checks_run', 0)} checks" if details.get("success") else "❌ Failed"
            elif event == "check":
                result = f"✅ {details.get('check_name')}" if details.get("success") else f"❌ {details.get('check_name')}"
            else:
                result = str(details)[:30]

            table.add_row(ts, event, result)

        console.print(table)
    else:
        console.print("[dim]No heartbeat history yet[/dim]")
