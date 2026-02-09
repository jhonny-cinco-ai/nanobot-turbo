"""CLI commands for nanobot."""

import asyncio
import atexit
import os
import signal
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __version__, __logo__

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()

# ---------------------------------------------------------------------------
# Lightweight CLI input: readline for arrow keys / history, termios for flush
# ---------------------------------------------------------------------------

_READLINE = None
_HISTORY_FILE: Path | None = None
_HISTORY_HOOK_REGISTERED = False
_USING_LIBEDIT = False
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _save_history() -> None:
    if _READLINE is None or _HISTORY_FILE is None:
        return
    try:
        _READLINE.write_history_file(str(_HISTORY_FILE))
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _enable_line_editing() -> None:
    """Enable readline for arrow keys, line editing, and persistent history."""
    global _READLINE, _HISTORY_FILE, _HISTORY_HOOK_REGISTERED, _USING_LIBEDIT, _SAVED_TERM_ATTRS

    # Save terminal state before readline touches it
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE = history_file

    try:
        import readline
    except ImportError:
        return

    _READLINE = readline
    _USING_LIBEDIT = "libedit" in (readline.__doc__ or "").lower()

    try:
        if _USING_LIBEDIT:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode emacs")
    except Exception:
        pass

    try:
        readline.read_history_file(str(history_file))
    except Exception:
        pass

    if not _HISTORY_HOOK_REGISTERED:
        atexit.register(_save_history)
        _HISTORY_HOOK_REGISTERED = True


def _prompt_text() -> str:
    """Build a readline-friendly colored prompt."""
    if _READLINE is None:
        return "You: "
    # libedit on macOS does not honor GNU readline non-printing markers.
    if _USING_LIBEDIT:
        return "\033[1;34mYou:\033[0m "
    return "\001\033[1;34m\002You:\001\033[0m\002 "


async def _read_interactive_input_async() -> str:
    """Read user input with arrow keys and history (runs input() in a thread)."""
    try:
        return await asyncio.to_thread(input, _prompt_text())
    except EOFError as exc:
        raise KeyboardInterrupt from exc


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am nanobot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


def _make_provider(config):
    """Create LiteLLMProvider from config. Exits if no API key found."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=config.get_provider_name(),
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the nanobot gateway."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.session.manager import SessionManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} Starting nanobot gateway on port {port}...")
    
    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with cron service and smart routing
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        routing_config=config.routing,
    )
    
    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    
    config = load_config()
    
    bus = MessageBus()
    provider = _make_provider(config)
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        routing_config=config.routing,
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        _enable_line_editing()
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")

        # input() runs in a worker thread that can't be cancelled.
        # Without this handler, asyncio.run() would hang waiting for it.
        def _exit_on_sigint(signum, frame):
            _save_history()
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)
        
        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    _save_history()
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Routing Commands
# ============================================================================


routing_app = typer.Typer(help="Smart routing management")


@routing_app.command("status")
def routing_status():
    """Show smart routing status and configuration."""
    from nanobot.config.loader import load_config
    from nanobot.agent.stages import RoutingStage
    
    config = load_config()
    
    console.print(f"{__logo__} Smart Routing Status\n")
    
    if not config.routing.enabled:
        console.print("[yellow]Smart routing is disabled[/yellow]")
        console.print("Enable it in ~/.nanobot/config.json:")
        console.print('  "routing": {"enabled": true}')
        return
    
    console.print("[green]✓ Smart routing is enabled[/green]\n")
    
    # Create routing stage to get info
    try:
        routing_stage = RoutingStage(config.routing, workspace=config.workspace_path)
        info = routing_stage.get_routing_info()
        
        # Tiers table
        table = Table(title="Model Tiers")
        table.add_column("Tier", style="cyan")
        table.add_column("Model", style="green")
        table.add_column("Cost/M tokens", style="yellow")
        
        for tier_name, tier_config in info["tiers"].items():
            table.add_row(
                tier_name.upper(),
                tier_config["model"],
                f"${tier_config['cost_per_mtok']:.2f}"
            )
        
        console.print(table)
        console.print()
        
        # Configuration
        console.print("[bold]Configuration:[/bold]")
        console.print(f"  Client confidence threshold: {info['client_confidence_threshold']}")
        console.print(f"  LLM classifier: {info['llm_classifier']['model']} (timeout: {info['llm_classifier']['timeout_ms']}ms)")
        console.print(f"  Sticky context window: {info['sticky']['context_window']} messages")
        console.print(f"  Downgrade confidence: {info['sticky']['downgrade_confidence']}")
        console.print()
        
        # Calibration info
        if "calibration" in info:
            console.print("[bold]Calibration:[/bold]")
            console.print(f"  Enabled: {info['calibration']['enabled']}")
            console.print(f"  Interval: {info['calibration']['interval']}")
            if info['calibration']['last_run']:
                console.print(f"  Last run: {info['calibration']['last_run']}")
            console.print(f"  Total classifications: {info['calibration']['total_classifications']}")
        
    except Exception as e:
        console.print(f"[red]Error loading routing info: {e}[/red]")


@routing_app.command("calibrate")
def routing_calibrate(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes"),
):
    """Manually trigger routing calibration."""
    from nanobot.config.loader import load_config
    from nanobot.agent.router.calibration import CalibrationManager
    
    config = load_config()
    
    if not config.routing.enabled:
        console.print("[red]Error: Smart routing is disabled[/red]")
        raise typer.Exit(1)
    
    if not config.routing.auto_calibration.enabled:
        console.print("[yellow]Warning: Auto-calibration is disabled[/yellow]")
        console.print("Enable it in config or use --force to calibrate anyway")
        if not typer.confirm("Continue anyway?"):
            raise typer.Exit(0)
    
    console.print(f"{__logo__} Running calibration...\n")
    
    try:
        patterns_file = config.workspace_path / "memory" / "ROUTING_PATTERNS.json"
        analytics_file = config.workspace_path / "analytics" / "routing_stats.json"
        
        calibration = CalibrationManager(
            patterns_file=patterns_file,
            analytics_file=analytics_file,
            config=config.routing.auto_calibration.model_dump(),
        )
        
        if dry_run:
            console.print("[blue]Dry run mode - no changes will be made[/blue]")
            console.print(f"Would analyze {len(calibration._classifications)} classifications")
            if calibration.should_calibrate():
                console.print("[green]Calibration would run[/green]")
            else:
                console.print("[yellow]Calibration would be skipped (not enough data)[/yellow]")
        else:
            if not calibration.should_calibrate():
                console.print("[yellow]Not enough data for calibration yet[/yellow]")
                console.print(f"Need {config.routing.auto_calibration.min_classifications} classifications")
                console.print(f"Current: {len(calibration._classifications)}")
                raise typer.Exit(1)
            
            results = calibration.calibrate()
            
            console.print("[green]✓ Calibration complete[/green]\n")
            console.print(f"Classifications analyzed: {results['classifications_analyzed']}")
            console.print(f"Patterns added: {results['patterns_added']}")
            console.print(f"Patterns removed: {results['patterns_removed']}")
            console.print(f"Total patterns: {results['total_patterns']}")
    
    except Exception as e:
        console.print(f"[red]Calibration failed: {e}[/red]")
        raise typer.Exit(1)


@routing_app.command("patterns")
def routing_patterns(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum patterns to show"),
    tier: str = typer.Option(None, "--tier", "-t", help="Filter by tier (simple/medium/complex/reasoning)"),
):
    """Show learned routing patterns."""
    from nanobot.config.loader import load_config
    from nanobot.agent.router.models import RoutingPattern
    import json
    
    config = load_config()
    
    patterns_file = config.workspace_path / "memory" / "ROUTING_PATTERNS.json"
    
    if not patterns_file.exists():
        console.print("[yellow]No patterns file found[/yellow]")
        console.print(f"Expected at: {patterns_file}")
        console.print("\nPatterns are learned automatically over time.")
        return
    
    try:
        data = json.loads(patterns_file.read_text())
        patterns_data = data.get("patterns", [])
        
        # Filter by tier if specified
        if tier:
            tier = tier.lower()
            patterns_data = [p for p in patterns_data if p.get("tier") == tier]
        
        # Sort by success rate
        patterns_data.sort(key=lambda p: p.get("success_rate", 0), reverse=True)
        
        console.print(f"{__logo__} Learned Patterns ({len(patterns_data)} total)\n")
        
        table = Table()
        table.add_column("Tier", style="cyan")
        table.add_column("Pattern", style="green")
        table.add_column("Confidence", style="yellow")
        table.add_column("Success", style="blue")
        table.add_column("Uses", style="dim")
        
        for pattern_data in patterns_data[:limit]:
            table.add_row(
                pattern_data.get("tier", "unknown").upper(),
                pattern_data.get("regex", "")[:50],
                f"{pattern_data.get('confidence', 0):.2f}",
                f"{pattern_data.get('success_rate', 0):.1%}",
                str(pattern_data.get("usage_count", 0)),
            )
        
        console.print(table)
        
        if len(patterns_data) > limit:
            console.print(f"\n[dim]... and {len(patterns_data) - limit} more[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error reading patterns: {e}[/red]")


@routing_app.command("test")
def routing_test(
    message: str = typer.Argument(..., help="Message to test classification on"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed scores"),
):
    """Test classification on a message."""
    from nanobot.agent.router import classify_content
    
    console.print(f"{__logo__} Testing Classification\n")
    console.print(f"Message: [cyan]{message}[/cyan]\n")
    
    try:
        decision, scores = classify_content(message)
        
        # Results table
        table = Table(title="Classification Result")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Tier", decision.tier.value.upper())
        table.add_row("Confidence", f"{decision.confidence:.2f}")
        table.add_row("Layer", decision.layer)
        table.add_row("Estimated Tokens", str(decision.estimated_tokens))
        table.add_row("Needs Tools", "Yes" if decision.needs_tools else "No")
        
        console.print(table)
        
        if verbose:
            console.print("\n[bold]Dimension Scores:[/bold]")
            scores_table = Table()
            scores_table.add_column("Dimension", style="cyan")
            scores_table.add_column("Score", style="yellow")
            
            for dim, score in scores.to_dict().items():
                bar = "█" * int(score * 20)
                scores_table.add_row(dim, f"{score:.2f} {bar}")
            
            console.print(scores_table)
        
        console.print(f"\n[dim]{decision.reasoning}[/dim]")
    
    except Exception as e:
        console.print(f"[red]Classification failed: {e}[/red]")


@routing_app.command("analytics")
def routing_analytics():
    """Show routing analytics and cost savings."""
    from nanobot.config.loader import load_config
    import json
    
    config = load_config()
    
    if not config.routing.enabled:
        console.print("[red]Smart routing is disabled[/red]")
        return
    
    analytics_file = config.workspace_path / "analytics" / "routing_stats.json"
    
    console.print(f"{__logo__} Routing Analytics\n")
    
    # Load analytics data
    classifications = []
    if analytics_file.exists():
        try:
            data = json.loads(analytics_file.read_text())
            classifications = data.get("classifications", [])
        except:
            pass
    
    if not classifications:
        console.print("[yellow]No analytics data yet[/yellow]")
        console.print("Data is collected automatically as you use the system.")
        return
    
    # Calculate tier distribution
    tier_counts = {}
    layer_counts = {"client": 0, "llm": 0}
    
    for c in classifications:
        tier = c.get("final_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        layer_counts[c.get("layer", "client")] += 1
    
    # Cost calculation
    total = len(classifications)
    cost_table = Table(title="Cost Analysis")
    cost_table.add_column("Metric", style="cyan")
    cost_table.add_column("Value", style="green")
    
    # Calculate blended cost vs using most expensive model
    blended_cost = 0
    for tier_name, count in tier_counts.items():
        tier_config = config.routing.tiers.get(tier_name)
        if tier_config:
            pct = count / total
            blended_cost += pct * tier_config.cost_per_mtok
    
    most_expensive = max(
        (t.cost_per_mtok for t in config.routing.tiers.values()),
        default=75.0
    )
    
    savings_pct = ((most_expensive - blended_cost) / most_expensive * 100) if most_expensive > 0 else 0
    
    cost_table.add_row("Total Classifications", str(total))
    cost_table.add_row("Client-side Classifications", f"{layer_counts['client']} ({layer_counts['client']/total*100:.1f}%)")
    cost_table.add_row("LLM-assisted Classifications", f"{layer_counts['llm']} ({layer_counts['llm']/total*100:.1f}%)")
    cost_table.add_row("Blended Cost", f"${blended_cost:.2f}/M tokens")
    cost_table.add_row("Most Expensive Model", f"${most_expensive:.2f}/M tokens")
    cost_table.add_row("Estimated Savings", f"{savings_pct:.1f}%")
    
    console.print(cost_table)
    console.print()
    
    # Tier distribution
    tier_table = Table(title="Tier Distribution")
    tier_table.add_column("Tier", style="cyan")
    tier_table.add_column("Count", style="yellow")
    tier_table.add_column("Percentage", style="green")
    
    for tier_name in ["simple", "medium", "complex", "reasoning"]:
        count = tier_counts.get(tier_name, 0)
        pct = count / total * 100 if total > 0 else 0
        tier_table.add_row(
            tier_name.upper(),
            str(count),
            f"{pct:.1f}%"
        )
    
    console.print(tier_table)


# Add routing subcommand to main app
app.add_typer(routing_app, name="routing")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")
        
        # Smart routing status
        console.print()
        if config.routing.enabled:
            console.print(f"Smart Routing: [green]✓ enabled[/green]")
            console.print("  Run [cyan]nanobot routing status[/cyan] for details")
        else:
            console.print(f"Smart Routing: [dim]disabled[/dim]")


if __name__ == "__main__":
    app()
