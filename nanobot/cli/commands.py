"""CLI commands for nanobot."""

import asyncio
import os
import signal
from pathlib import Path
import select
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from loguru import logger

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from nanobot import __logo__
from nanobot.config.loader import load_config, get_data_dir
from nanobot.config.schema import MemoryConfig

# Initialize Rich console
console = Console()

# Main CLI app
app = typer.Typer(name="nanobot", help="nanobot CLI")

# Import memory commands
try:
    from nanobot.cli.memory_commands import (
        memory_app, session_app,
        memory_init, memory_status, memory_search, memory_entities,
        memory_entity, memory_forget, memory_doctor,
        session_compact, session_status, session_reset
    )
except ImportError:
    memory_app = None
    session_app = None


# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# 
# MIGRATION NOTE (2026-02-12):
# Replaced basic input() with prompt_toolkit.PromptSession for:
#   ✓ Multiline paste support (bracketed paste mode)
#   ✓ Persistent command history (FileHistory)
#   ✓ Clean display without ghost characters (patch_stdout)
#   ✓ Animated spinner during processing (safe with prompt_toolkit)
#   ✓ Easy copy-paste of output (clean formatting)
#
# Migration phases completed:
#   Phase 1: Dependencies & basic setup ✓
#   Phase 2: Input handling & core functions ✓
#   Phase 3-4: UI polish & code cleanup ✓
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


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


# Exit commands for interactive mode
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with clean, copy-friendly header."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    # Use a simple header instead of a Panel box, making it easier to copy text
    console.print(f"{__logo__} [bold cyan]nanobot[/bold cyan]")
    console.print(body)
    console.print()


def _run_onboard_wizard():
    """Run the step-by-step onboarding wizard."""
    # Show spinner immediately while imports load
    with console.status("[cyan]Preparing setup wizard...[/cyan]", spinner="dots"):
        import asyncio
        from rich.prompt import Prompt, Confirm
        from nanobot.agent.tools.update_config import UpdateConfigTool
        
        tool = UpdateConfigTool()
    
    console.print("\n[bold cyan]Let's get you set up![/bold cyan]")
    console.print("[dim]I'll guide you through the essential configuration.[/dim]\n")
    
    # Step 1: Model Provider
    console.print("[bold]Step 1: Select Model Provider[/bold]")
    console.print("Choose the AI provider for your bot:\n")
    
    providers = {
        "1": ("openrouter", "OpenRouter - Access multiple AI models (recommended)"),
        "2": ("anthropic", "Anthropic - Claude models"),
        "3": ("openai", "OpenAI - GPT models"),
        "4": ("groq", "Groq - Fast inference + Voice transcription (Whisper)"),
        "5": ("deepseek", "DeepSeek - Chinese models"),
        "6": ("moonshot", "Moonshot - Kimi models (Chinese)"),
        "7": ("gemini", "Gemini - Google AI models"),
        "8": ("zhipu", "Zhipu - ChatGLM models (Chinese)"),
        "9": ("dashscope", "DashScope - Qwen models (Alibaba/Chinese)"),
        "10": ("aihubmix", "AiHubMix - API Gateway"),
        "11": ("vllm", "vLLM - Local models"),
    }
    
    for key, (name, desc) in providers.items():
        console.print(f"  [{key}] {desc}")
    
    provider_choice = Prompt.ask("\nSelect provider", choices=list(providers.keys()), default="1")
    provider_name, provider_desc = providers[provider_choice]
    
    # Get API key
    console.print(f"\n[dim]{provider_desc}[/dim]")
    api_key = Prompt.ask(f"Enter your {provider_name.title()} API key", password=False)
    
    if not api_key:
        console.print("[yellow]⚠ No API key provided. You can configure this later with: nanobot configure[/yellow]")
    else:
        with console.status(f"[cyan]Saving {provider_name} API key...[/cyan]", spinner="dots"):
            result = asyncio.run(tool.execute(
                path=f"providers.{provider_name}.apiKey",
                value=api_key
            ))
        if "Error" not in result:
            console.print(f"[green]✓ {provider_name.title()} configured[/green]\n")
    
    # Step 2: Primary Model
    console.print("[bold]Step 2: Select Primary Model[/bold]")
    console.print("This is the default model your bot will use:\n")
    
    # Show available models for the provider
    schema = tool.SCHEMA['providers']['providers']
    provider_schema = schema.get(provider_name, {})
    available_models = provider_schema.get('models', ['anthropic/claude-opus-4-5'])
    
    for i, model in enumerate(available_models[:5], 1):
        console.print(f"  [{i}] {model}")
    console.print("  [c] Custom model")
    
    model_choice = Prompt.ask("\nSelect model", choices=[str(i) for i in range(1, min(6, len(available_models)+1))] + ["c"], default="1")
    
    if model_choice == "c":
        primary_model = Prompt.ask("Enter custom model name")
    else:
        primary_model = available_models[int(model_choice) - 1]
    
    if primary_model:
        with console.status("[cyan]Setting primary model...[/cyan]", spinner="dots"):
            result = asyncio.run(tool.execute(
                path="agents.defaults.model",
                value=primary_model
            ))
        if "Error" not in result:
            console.print(f"[green]✓ Primary model set to {primary_model}[/green]\n")
    
    # Step 3: Smart Routing
    console.print("[bold]Step 3: Smart Routing[/bold]")
    console.print("""
[dim]Smart routing automatically selects the best model based on query complexity:[/dim]
  • Simple queries → Cheaper models
  • Complex tasks → Stronger models
  • Coding → Specialized coding models
  • Reasoning → Advanced reasoning models

This saves costs while maintaining quality.

[yellow]Note:[/yellow] Smart routing is experimental and continuously improving.
If disabled, your bot will use [bold]{}[/bold] for all queries.
    """.format(primary_model))
    
    enable_routing = Confirm.ask("Enable smart routing?", default=True)
    
    if enable_routing:
        with console.status("[cyan]Enabling smart routing...[/cyan]", spinner="dots"):
            result = asyncio.run(tool.execute(path="routing.enabled", value=True))
        if "Error" not in result:
            console.print("[green]✓ Smart routing enabled[/green]")
            
            # Show suggested tier configuration with validation
            console.print("\n[dim]Suggested tier configuration:[/dim]")
            
            # Define suggested models based on selected provider
            # For gateway providers like OpenRouter, use their model format
            if provider_name == 'openrouter':
                # OpenRouter supports all models through their gateway
                suggested_models = {
                    'simple': 'openrouter/deepseek/deepseek-chat-v3-0324',
                    'medium': 'openrouter/openai/gpt-4.1-mini',
                    'complex': 'openrouter/anthropic/claude-3-5-sonnet',
                    'reasoning': 'openrouter/openai/o3-mini',
                    'coding': 'openrouter/moonshotai/kimi-k2.5',
                }
            elif provider_name == 'aihubmix':
                # AiHubMix uses OpenAI-compatible format
                suggested_models = {
                    'simple': 'deepseek/deepseek-chat-v3-0324',
                    'medium': 'gpt-4.1-mini',
                    'complex': 'claude-3-5-sonnet-20241022',
                    'reasoning': 'o3-mini',
                    'coding': 'kimi-k2.5',
                }
            else:
                # For direct providers, use models from their schema or defaults
                default_simple = provider_schema.get('models', [f'{provider_name}/default'])[0] if provider_schema.get('models') else f'{provider_name}/default'
                suggested_models = {
                    'simple': default_simple,
                    'medium': f'{provider_name}/medium-model',
                    'complex': f'{provider_name}/complex-model',
                    'reasoning': f'{provider_name}/reasoning-model',
                    'coding': f'{provider_name}/coding-model',
                }
            
            # Validate each suggested model
            validation_warnings = []
            for tier, model in suggested_models.items():
                validation = tool.validate_model_for_routing(model)
                status = "✓" if validation['provider_configured'] else "○"
                console.print(f"  {status} {tier.capitalize():9} {model}")
                if validation['warning']:
                    validation_warnings.append(f"  • {validation['warning']}")
            
            if validation_warnings:
                console.print("\n[yellow]⚠ Provider Configuration Needed:[/yellow]")
                for warning in validation_warnings:
                    console.print(warning)
                console.print("\n[dim]These models will only work once you add the required API keys.[/dim]")
                console.print("[dim]Run 'nanobot configure' to add more providers.[/dim]")
            
            console.print("\n[dim]You can customize these later in: nanobot configure[/dim]\n")
    else:
        console.print("[dim]Smart routing disabled. Your bot will use the primary model for all queries.[/dim]\n")
    
    # Step 4: Evolutionary Mode
    console.print("[bold]Step 4: Evolutionary Mode[/bold]")
    console.print("""
[dim]Evolutionary mode allows the bot to:[/dim]
  • Modify its own source code
  • Access paths outside the workspace
  • Self-improve and adapt

[yellow]⚠ Security Note:[/yellow] Only enable if you understand the risks.
    """)
    
    enable_evo = Confirm.ask("Enable evolutionary mode?", default=False)
    
    if enable_evo:
        with console.status("[cyan]Enabling evolutionary mode...[/cyan]", spinner="dots"):
            result = asyncio.run(tool.execute(path="tools.evolutionary", value=True))
            # Set default allowed paths
            asyncio.run(tool.execute(
                path="tools.allowedPaths", 
                value=["/projects/nanobot-turbo", "~/.nanobot"]
            ))
        if "Error" not in result:
            console.print("[green]✓ Evolutionary mode enabled[/green]")
            console.print("[dim]Allowed paths: /projects/nanobot-turbo, ~/.nanobot[/dim]")
            console.print("[dim]Configure additional paths later with: nanobot configure[/dim]\n")
    else:
        console.print("[dim]Evolutionary mode disabled. Bot restricted to workspace only.[/dim]\n")
    
    # Completion
    console.print(Panel.fit(
        "[bold green]🎉 Setup Complete![/bold green]\n\n"
        "Your nanobot is ready to use.",
        border_style="green"
    ))
    
    console.print("\n[bold]Get started:[/bold]")
    console.print("  [cyan]nanobot agent[/cyan]     - Start interactive chat")
    console.print("  [cyan]nanobot gateway[/cyan]   - Start gateway server")
    console.print("  [cyan]nanobot configure[/cyan] - Advanced settings")


@app.command("onboard")
def onboard():
    """Set up your multi-agent team from scratch.
    
    This wizard will guide you through:
    1. AI Provider & API key configuration
    2. Model selection  
    3. Team theme selection with full team preview
    4. Workspace creation with all bots ready
    """
    from nanobot.cli.onboarding import OnboardingWizard
    
    wizard = OnboardingWizard()
    result = wizard.run()


@app.command()
def configure():
    """Interactive configuration wizard."""
    with console.status("[cyan]Loading configuration interface...[/cyan]", spinner="dots"):
        from nanobot.cli.configure import configure_cli
    configure_cli()




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files.
    
    Note: AGENTS.md and SOUL.md are now per-bot, created in bots/{bot}/ directory.
    Only shared files (USER.md, TOOLS.md) are created at workspace level.
    """
    templates = {
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
        "TOOLS.md": """# Available Tools

This document describes the tools available to nanobot.

## File Operations

### read_file
Read the contents of a file.

### write_file
Write content to a file (creates parent directories if needed).

### edit_file
Edit a file by replacing specific text.

### list_dir
List contents of a directory.

## Shell Execution

### exec
Execute a shell command and return output.

**Safety Notes:**
- Commands have a configurable timeout (default 60s)
- Dangerous commands are blocked (rm -rf, format, dd, shutdown, etc.)
- Output is truncated at 10,000 characters

## Web Access

### web_search
Search the web using Brave Search API.

### web_fetch
Fetch and extract main content from a URL.

## Communication

### message
Send a message to the user on chat channels.

## Background Tasks

### invoke
Invoke a specialist bot to handle a task in the background.
```
invoke(bot_name: str, task: str, context: str = None)
```

Use for complex tasks that need specialist expertise. The bot will complete the task and report back.

## Cron Reminders

Use the `exec` tool to create scheduled reminders with `nanobot cron add`.

---

## Per-Bot Tool Permissions

You can customize which tools each bot has access to by adding tool permissions to their SOUL.md or AGENTS.md files:

```markdown
## Allowed Tools
- read_file
- write_file
- web_search

## Denied Tools
- exec
- spawn

## Custom Tools
- shopify_api: Custom Shopify integration
```

If no permissions are specified, bots get access to all standard tools.
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

    # Create skills directory for custom user skills
    skills_dir = workspace / "skills"
    skills_dir.mkdir(exist_ok=True)


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
    from nanobot.heartbeat.multi_manager import MultiHeartbeatManager
    from nanobot.heartbeat.dashboard import DashboardService
    from nanobot.heartbeat.dashboard_server import DashboardHTTPServer
    
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
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        routing_config=config.routing,
        evolutionary=config.tools.evolutionary,
        allowed_paths=config.tools.allowed_paths,
        protected_paths=config.tools.protected_paths,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent or handle system jobs."""
        # Handle calibration jobs (system jobs, not user messages)
        if job.payload.message == "CALIBRATE_ROUTING":
            try:
                from nanobot.agent.router.calibration import CalibrationManager
                calibration = CalibrationManager(
                    patterns_file=config.workspace_path / "routing_patterns.json",
                    analytics_file=config.workspace_path / "routing_stats.json",
                    config=config.routing.auto_calibration.model_dump() if config.routing.auto_calibration else None,
                )
                if calibration.should_calibrate():
                    results = calibration.calibrate()
                    logger.info(f"Scheduled calibration completed: {results}")
                    return f"Calibration completed: {results.get('patterns_added', 0)} patterns added, {results.get('patterns_removed', 0)} removed"
                else:
                    return "Calibration not needed yet (insufficient data or too soon)"
            except Exception as e:
                logger.error(f"Calibration job failed: {e}")
                return f"Calibration failed: {e}"
        
        # Regular user job - process through agent
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
    
    # Create heartbeat service (legacy)
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create multi-heartbeat manager with all 6 bots
    try:
        from nanobot.bots.implementations import (
            ResearcherBot, CoderBot, SocialBot, AuditorBot, CreativeBot, NanobotLeader
        )
        
        # Load appearance configuration (themes and custom names)
        from nanobot.bots.appearance_config import get_appearance_config
        appearance_config = get_appearance_config()
        theme_manager = appearance_config.theme_manager
        
        # Create bot instances with auto-initialization and appearance config
        researcher = ResearcherBot(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("researcher")
        )
        coder = CoderBot(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("coder")
        )
        social = SocialBot(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("social")
        )
        auditor = AuditorBot(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("auditor")
        )
        creative = CreativeBot(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("creative")
        )
        nanobot = NanobotLeader(
            bus=bus,
            workspace_id=str(config.workspace_path),
            workspace=config.workspace_path,
            theme_manager=theme_manager,
            custom_name=appearance_config.get_custom_name("nanobot")
        )
        
        # Initialize multi-heartbeat manager
        multi_manager = MultiHeartbeatManager()
        multi_manager.register_bot(researcher)
        multi_manager.register_bot(coder)
        multi_manager.register_bot(social)
        multi_manager.register_bot(auditor)
        multi_manager.register_bot(creative)
        multi_manager.register_bot(nanobot)
        
        # Re-initialize heartbeats with provider, routing, and reasoning config
        # This enables HEARTBEAT.md execution with smart model selection
        from nanobot.reasoning.config import get_reasoning_config
        from nanobot.agent.work_log_manager import get_work_log_manager
        
        # Get work log manager for heartbeat logging
        work_log_manager = get_work_log_manager()
        
        # Create tool registry for bots
        from nanobot.agent.tools.factory import create_bot_registry
        
        bots_list = [researcher, coder, social, auditor, creative, nanobot]
        for bot in bots_list:
            bot_reasoning_config = get_reasoning_config(bot.name)
            tool_registry = create_bot_registry(
                workspace=config.workspace_path,
                bot_name=bot.name,
            )
            bot.initialize_heartbeat(
                workspace=config.workspace_path,
                provider=provider,
                routing_config=config.routing,
                reasoning_config=bot_reasoning_config,
                work_log_manager=work_log_manager,
                tool_registry=tool_registry,
            )
        
        # Wire manager into CLI commands
        from nanobot.cli.heartbeat_commands import set_heartbeat_manager
        set_heartbeat_manager(multi_manager)
        
        console.print("[green]✓[/green] Multi-heartbeat manager initialized with 6 bots")
    except Exception as e:
        logger.warning(f"Failed to initialize multi-heartbeat manager: {e}")
        multi_manager = None
    
        # Create dashboard service for real-time monitoring
        try:
            dashboard_service = DashboardService(
                manager=multi_manager,
                port=9090,
                update_interval=5.0,  # Update every 5 seconds
            )
            dashboard_server = DashboardHTTPServer(
                dashboard_service,
                host="localhost",
                port=9090
            )
            console.print("[green]✓[/green] Dashboard initialized on http://localhost:9090")
        except Exception as e:
            logger.warning(f"Failed to initialize dashboard: {e}")
            dashboard_service = None
            dashboard_server = None
        
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
            
            # Start multi-heartbeat manager if initialized
            if multi_manager:
                await multi_manager.start_all()
            
            # Start dashboard service if initialized
            if dashboard_service:
                await dashboard_service.start()
                if dashboard_server:
                    await dashboard_server.start()
            
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            
            # Stop dashboard service if initialized
            if dashboard_service:
                await dashboard_service.stop()
            if dashboard_server:
                await dashboard_server.stop()
            
            # Stop multi-heartbeat manager if initialized
            if multi_manager:
                await multi_manager.stop_all()
            
            heartbeat.stop()
            cron.stop()
            await agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from loguru import logger
    
    config = load_config()
    
    bus = MessageBus()
    provider = _make_provider(config)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        routing_config=config.routing,
        evolutionary=config.tools.evolutionary,
        allowed_paths=config.tools.allowed_paths,
        protected_paths=config.tools.protected_paths,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

    if message:
        # Single message mode
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id)
            _print_agent_response(response, render_markdown=markdown)
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)
        
        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    command = user_input.strip()
                    if not command:
                        continue

                    if _is_exit_command(command):
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break
                    
                    # Handle work log commands in interactive mode
                    if command == "/explain":
                        from nanobot.agent.work_log_manager import get_work_log_manager
                        manager = get_work_log_manager()
                        formatted = manager.get_formatted_log("detailed")
                        console.print("\n[cyan]Last Work Log:[/cyan]")
                        console.print(formatted)
                        console.print()
                        continue
                    
                    if command == "/logs":
                        from nanobot.agent.work_log_manager import get_work_log_manager
                        manager = get_work_log_manager()
                        formatted = manager.get_formatted_log("summary")
                        console.print("\n[cyan]Work Log Summary:[/cyan]")
                        console.print(formatted)
                        console.print()
                        continue
                    
                    if command.startswith("/how "):
                        from nanobot.agent.work_log_manager import get_work_log_manager
                        from nanobot.agent.work_log import LogLevel
                        
                        manager = get_work_log_manager()
                        log = manager.get_last_log()
                        
                        if log:
                            search_query = command[5:]  # Remove "/how " prefix
                            query_lower = search_query.lower()
                            matches = []
                            
                            for entry in log.entries:
                                if (query_lower in entry.message.lower() or
                                    query_lower in entry.category.lower() or
                                    (entry.tool_name and query_lower in entry.tool_name.lower())):
                                    matches.append(entry)
                            
                            if matches:
                                console.print(f"\n[cyan]Found {len(matches)} entries matching '{search_query}':[/cyan]\n")
                                for entry in matches[:5]:
                                    icon = _get_work_log_icon(entry.level)
                                    console.print(f"{icon} Step {entry.step}: {entry.message}")
                            else:
                                console.print(f"\n[yellow]No entries found matching '{search_query}'[/yellow]\n")
                        else:
                            console.print("\n[yellow]No work log found.[/yellow]\n")
                        continue
                    
                    with _thinking_ctx():
                        response = await agent_loop.process_direct(user_input, session_id)
                    _print_agent_response(response, render_markdown=markdown)
                except KeyboardInterrupt:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
                except EOFError:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Work Log Commands (Transparency & Debugging)
# ============================================================================

@app.command("explain")
def explain_last_decision(
    mode: str = typer.Option("detailed", "--mode", "-m",
                            help="Display mode: summary, detailed, debug, coordination, conversations"),
    session: Optional[str] = typer.Option(None, "--session", "-s",
                                         help="Specific session ID to explain"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w",
                                           help="Workspace to explain (#general, #project-alpha)"),
    bot: Optional[str] = typer.Option(None, "--bot", "-b",
                                     help="Filter by bot (@researcher, @coder)"),
):
    """
    Show how nanobot made its last decision.
    
    Provides transparency into the agent's reasoning process, including:
    - Routing decisions (why a specific model was chosen)
    - Tool executions (what tools were called and their results)
    - Memory retrieval (what context was used)
    - Confidence scores and timing information
    
    Examples:
        nanobot explain                              # Explain the last interaction
        nanobot explain --mode summary               # Brief summary only
        nanobot explain --mode debug                 # Full technical details
        nanobot explain --session abc123             # Explain a specific session
        nanobot explain -w #project-refactor         # Explain project workspace
        nanobot explain -w #coordination-website     # See overnight coordination
        nanobot explain --mode coordination          # Focus on coordinator decisions
        nanobot explain -b @researcher               # See what researcher did
    """
    from nanobot.agent.work_log_manager import get_work_log_manager
    from nanobot.agent.work_log import LogLevel
    
    manager = get_work_log_manager()
    
    # Get the appropriate log
    if workspace:
        logs = manager.get_logs_by_workspace(workspace, limit=1)
        log = logs[0] if logs else None
        if not log:
            console.print(f"[yellow]No work log found for workspace: {workspace}[/yellow]")
            console.print("[dim]Tip: Use 'nanobot agent' first to generate a work log.[/dim]")
            raise typer.Exit(1)
    elif session:
        log = manager.get_log_by_session(session)
        if not log:
            console.print(f"[yellow]No work log found for session: {session}[/yellow]")
            console.print("[dim]Tip: Use 'nanobot agent' first to generate a work log.[/dim]")
            raise typer.Exit(1)
    else:
        log = manager.get_last_log()
        if not log:
            console.print("[yellow]No work log found.[/yellow]")
            console.print("[dim]Tip: Use 'nanobot agent' first to generate a work log.[/dim]")
            raise typer.Exit(1)
    
    # Filter by bot if specified
    if bot:
        entries = [e for e in log.entries if e.bot_name == bot.lstrip("@")]
        if not entries:
            console.print(f"[yellow]No entries found for bot: {bot}[/yellow]")
            raise typer.Exit(1)
        console.print(f"[cyan]Work log for {log.workspace_id} - showing entries from {bot}[/cyan]\n")
    else:
        entries = log.entries
        if log.workspace_id != "default":
            console.print(f"[cyan]Work log for {log.workspace_id} ({log.workspace_type.value})[/cyan]\n")
    
    # Handle special display modes
    if mode == "coordination":
        coord_entries = [e for e in entries if e.coordinator_mode]
        if not coord_entries:
            console.print("[yellow]No coordinator mode entries found.[/yellow]")
            raise typer.Exit(1)
        _print_coordination_summary(log, coord_entries)
        return
    
    if mode == "conversations":
        convo_entries = [e for e in entries if e.category == "bot_conversation"]
        if not convo_entries:
            console.print("[yellow]No bot conversations found.[/yellow]")
            raise typer.Exit(1)
        _print_bot_conversations(log, convo_entries)
        return
    
    # Display the formatted log
    formatted = manager.get_formatted_log(mode)
    console.print(formatted)


@app.command("how")
def how_did_you_decide(
    query: str = typer.Argument(..., help="What to search for (e.g., 'routing', 'memory', 'web_search')"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results to show"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w",
                                           help="Search in specific workspace"),
):
    """
    Search work logs for specific decisions or events.
    
    Helps you understand:
    - Why a specific model was chosen
    - What tools were executed
    - What memories were retrieved
    - Any errors or warnings
    
    Examples:
        nanobot how "routing"                  # Find routing decisions
        nanobot how "web_search"               # Find web search tool calls
        nanobot how "memory"                   # Find memory retrievals
        nanobot how "error"                    # Find errors
        nanobot how "claude"                   # Find mentions of Claude model
        nanobot how "why did you escalate" -w #coordination-website
        nanobot how "what did @researcher find"
    """
    from nanobot.agent.work_log_manager import get_work_log_manager
    
    manager = get_work_log_manager()
    
    # Get logs to search
    if workspace:
        logs = manager.get_logs_by_workspace(workspace, limit=10)
        if not logs:
            console.print(f"[yellow]No work logs found for workspace: {workspace}[/yellow]")
            raise typer.Exit(1)
    else:
        log = manager.get_last_log()
        if not log:
            console.print("[yellow]No work log found.[/yellow]")
            console.print("[dim]Tip: Use 'nanobot agent' first to generate a work log.[/dim]")
            raise typer.Exit(1)
        logs = [log]
    
    # Search for matching entries across all logs
    query_lower = query.lower()
    matches = []
    
    for log in logs:
        for entry in log.entries:
            # Search in message, category, tool name, and details
            if (query_lower in entry.message.lower() or
                query_lower in entry.category.lower() or
                (entry.tool_name and query_lower in entry.tool_name.lower()) or
                query_lower in str(entry.details).lower()):
                matches.append((log.workspace_id, entry))
    
    if not matches:
        console.print(f"[yellow]No entries found matching '{query}'[/yellow]")
        console.print(f"[dim]Try searching for: routing, memory, web_search, read_file, error[/dim]")
        raise typer.Exit(1)
    
    # Display results
    console.print(f"[cyan]Found {len(matches)} entries matching '{query}':[/cyan]\n")
    
    for i, (workspace_id, entry) in enumerate(matches[:limit], 1):
        icon = _get_work_log_icon(entry.level)
        
        # Show workspace for multi-workspace searches
        if len(logs) > 1:
            console.print(f"[dim]{workspace_id}[/dim] - Step {entry.step} - {entry.category}")
        else:
            console.print(f"{icon} [bold]Step {entry.step}[/bold] - {entry.category}")
        
        if entry.bot_name != "nanobot":
            console.print(f"   [cyan]@{entry.bot_name}:[/cyan] {entry.message}")
        else:
            console.print(f"   {entry.message}")
        
        if entry.confidence is not None:
            confidence_color = "green" if entry.confidence >= 0.8 else "yellow" if entry.confidence >= 0.5 else "red"
            console.print(f"   [dim]Confidence: [{confidence_color}]{entry.confidence:.0%}[/{confidence_color}][/dim]")
        
        if entry.duration_ms:
            console.print(f"   [dim]Duration: {entry.duration_ms}ms[/dim]")
        
        if entry.tool_name:
            status_icon = "✓" if entry.tool_status == "success" else "✗"
            console.print(f"   [dim]Tool: {entry.tool_name} [{status_icon} {entry.tool_status}][/dim]")
        
        console.print()
    
    if len(matches) > limit:
        console.print(f"[dim]... and {len(matches) - limit} more entries (use --limit to show more)[/dim]")


@app.command("workspace-logs")
def list_workspace_logs(
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w",
                                           help="Filter by workspace"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of logs to show"),
):
    """
    List recent work logs across workspaces.
    
    Examples:
        nanobot workspace-logs              # Show all recent logs
        nanobot workspace-logs -w #general  # Show only #general logs
        nanobot workspace-logs -n 20        # Show last 20 logs
    """
    from nanobot.agent.work_log_manager import get_work_log_manager
    
    manager = get_work_log_manager()
    logs = manager.get_all_logs(limit=limit, workspace=workspace)
    
    if not logs:
        workspace_msg = f" for workspace {workspace}" if workspace else ""
        console.print(f"[yellow]No work logs found{workspace_msg}.[/yellow]")
        console.print("[dim]Tip: Use 'nanobot agent' first to generate work logs.[/dim]")
        raise typer.Exit(1)
    
    table = Table(title="Recent Work Logs")
    table.add_column("Workspace", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Bots", style="yellow")
    table.add_column("Duration", style="dim")
    table.add_column("Status", style="blue")
    
    for log in logs:
        duration = "In Progress" if not log.end_time else f"{(log.end_time - log.start_time).seconds}s"
        status = "🟢 Complete" if log.end_time else "🟡 Active"
        
        table.add_row(
            log.workspace_id,
            log.workspace_type.value,
            ", ".join(log.participants[:3]),  # Show first 3 bots
            duration,
            status
        )
    
    console.print(table)


def _get_work_log_icon(level) -> str:
    """Get emoji icon for work log level."""
    from nanobot.agent.work_log import LogLevel
    
    icons = {
        LogLevel.INFO: "ℹ️",
        LogLevel.THINKING: "🧠",
        LogLevel.DECISION: "🎯",
        LogLevel.CORRECTION: "🔄",
        LogLevel.UNCERTAINTY: "❓",
        LogLevel.WARNING: "⚠️",
        LogLevel.ERROR: "❌",
        LogLevel.TOOL: "🔧"
    }
    return icons.get(level, "•")


def _print_coordination_summary(log, entries):
    """Print a rich summary of coordinator mode decisions."""
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    
    # Header with workspace context
    header = Text()
    header.append("🤖 Coordinator Mode Summary", style="bold cyan")
    header.append(f" - {log.workspace_id}", style="bold")
    console.print(header)
    console.print()
    
    # Workspace Info Panel
    info_lines = [
        f"[cyan]Workspace:[/cyan] {log.workspace_id} ({log.workspace_type.value})",
        f"[cyan]Coordinator:[/cyan] {log.coordinator}",
        f"[cyan]Participants:[/cyan] {', '.join(log.participants)}",
        f"[cyan]Total Coordinator Entries:[/cyan] {len(entries)}"
    ]
    console.print(Panel("\n".join(info_lines), title="[bold]Context[/bold]", border_style="blue"))
    console.print()
    
    # Separate by category
    bot_delegations = [e for e in entries if e.category == "bot_conversation"]
    decisions = [e for e in entries if e.level.value == "decision"]
    escalations = [e for e in entries if e.escalation]
    
    # Bot Delegations Table
    if bot_delegations:
        delegation_table = Table(title="Bot Delegations & Handoffs", box=None)
        delegation_table.add_column("Step", style="dim", width=5)
        delegation_table.add_column("From", style="yellow", width=12)
        delegation_table.add_column("To", style="cyan", width=12)
        delegation_table.add_column("Task", style="white")
        
        for entry in bot_delegations:
            mentions = ", ".join([m.lstrip("@") for m in entry.mentions]) if entry.mentions else "-"
            delegation_table.add_row(
                str(entry.step),
                entry.bot_name,
                mentions,
                entry.message[:50] + "..." if len(entry.message) > 50 else entry.message,
            )
        
        console.print(delegation_table)
        console.print()
    
    # Decisions Table
    if decisions:
        decision_table = Table(title="Autonomous Decisions", box=None)
        decision_table.add_column("Step", style="dim", width=5)
        decision_table.add_column("Bot", style="cyan", width=12)
        decision_table.add_column("Decision", style="white")
        decision_table.add_column("Confidence", style="green", width=12)
        
        for entry in decisions:
            conf_color = "green" if entry.confidence and entry.confidence >= 0.8 else "yellow" if entry.confidence and entry.confidence >= 0.5 else "red"
            confidence_str = f"[{conf_color}]{entry.confidence:.0%}[/{conf_color}]" if entry.confidence else "-"
            decision_table.add_row(
                str(entry.step),
                entry.bot_name,
                entry.message[:50] + "..." if len(entry.message) > 50 else entry.message,
                confidence_str
            )
        
        console.print(decision_table)
        console.print()
    
    # Escalations Alert
    if escalations:
        esc_panel_lines = []
        for esc in escalations:
            esc_panel_lines.append(f"[red]Step {esc.step}:[/red] {esc.message}")
        
        console.print(Panel(
            "\n".join(esc_panel_lines),
            title="[bold red]⚠️  Escalations Requiring User Input[/bold red]",
            border_style="red"
        ))
        console.print()
    
    # Summary Stats
    stats_text = Text()
    stats_text.append(f"Total Actions: {len(entries)}", style="dim")
    stats_text.append(f" | Delegations: {len(bot_delegations)}", style="yellow")
    stats_text.append(f" | Decisions: {len(decisions)}", style="cyan")
    stats_text.append(f" | Escalations: {len(escalations)}", style="red" if escalations else "green")
    console.print(stats_text)


def _print_bot_conversations(log, entries):
    """Print bot-to-bot conversation threading visualization."""
    from rich.text import Text
    
    console.print(f"[bold cyan]💬 Bot Conversation Threads - {log.workspace_id}[/bold cyan]\n")
    
    # Build conversation threads (response_to chains)
    threads = {}
    standalone = []
    
    for entry in entries:
        if entry.category == "bot_conversation":
            if entry.response_to:
                # Part of a thread
                if entry.response_to not in threads:
                    threads[entry.response_to] = []
                threads[entry.response_to].append(entry)
            else:
                # Standalone message or thread start
                if entry.step not in threads:
                    standalone.append(entry)
    
    # Display threads
    thread_num = 1
    for root_step in sorted(threads.keys()):
        root_msg = next((e for e in entries if e.step == root_step), None)
        if not root_msg:
            continue
        
        console.print(f"[bold yellow]Thread {thread_num}:[/bold yellow]")
        
        # Initial message
        console.print(f"  [{root_step}] [cyan]@{root_msg.bot_name}[/cyan]: {root_msg.message[:70]}")
        
        # Responses
        for response in threads[root_step]:
            indent = "      " if response.response_to == root_step else "    "
            mentions_str = f" (→ {', '.join([m.lstrip('@') for m in response.mentions])})" if response.mentions else ""
            console.print(f"{indent}↳ [{response.step}] [cyan]@{response.bot_name}[/cyan]: {response.message[:65]}{mentions_str}")
        
        console.print()
        thread_num += 1
    
    # Standalone messages
    if standalone:
        console.print(f"[bold yellow]Standalone Messages:[/bold yellow]")
        for entry in standalone:
            mentions_str = f" → {', '.join([m.lstrip('@') for m in entry.mentions])}" if entry.mentions else ""
            console.print(f"  [{entry.step}] [cyan]@{entry.bot_name}[/cyan]: {entry.message[:70]}{mentions_str}")
        console.print()


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

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
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
    from nanobot.config.loader import load_config
    
    config = load_config()
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
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
    tiers_dict = config.routing.tiers.model_dump()
    for tier_name, count in tier_counts.items():
        tier_config = tiers_dict.get(tier_name)
        if tier_config:
            pct = count / total
            blended_cost += pct * tier_config.get('cost_per_mtok', 0)
    
    most_expensive = max(
        (tier.get('cost_per_mtok', 0) for tier in tiers_dict.values()),
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


# Add memory and session subcommands if available
if memory_app is not None:
    app.add_typer(memory_app, name="memory")

if session_app is not None:
    app.add_typer(session_app, name="session")


# Skills Security Commands
# ============================================================================

skills_app = typer.Typer(name="skills", help="Skills management and security")

@skills_app.command("scan")
def scan_skill_command(
    skill_path: str = typer.Argument(..., help="Path to skill directory or file"),
    strict: bool = typer.Option(False, "--strict", help="Enable strict mode (block on medium severity)"),
    ignore_security: bool = typer.Option(False, "--ignore-security", help="Ignore security issues (not recommended)"),
):
    """
    Scan a skill for security vulnerabilities.
    
    Examples:
        nanobot skills scan ./my-skill
        nanobot skills scan ./my-skill --strict
        nanobot skills scan ./my-skill --ignore-security
    """
    from pathlib import Path
    from nanobot.security.skill_scanner import scan_skill, format_report_for_cli
    from rich.console import Console
    
    console = Console()
    path = Path(skill_path)
    
    if not path.exists():
        console.print(f"[red]Error: Path not found: {skill_path}[/red]")
        raise typer.Exit(1)
    
    console.print(f"[cyan]🔍 Scanning skill: {path.name}...[/cyan]\n")
    
    report = scan_skill(path, strict=strict)
    
    # Display report
    console.print(format_report_for_cli(report))
    
    # Exit with error if failed and not ignoring
    if not report.passed and not ignore_security:
        console.print("\n[red]❌ Security scan failed. Use --ignore-security to force (not recommended).[/red]")
        raise typer.Exit(1)
    elif ignore_security and not report.passed:
        console.print("\n[yellow]⚠️  Security issues ignored by user request.[/yellow]")
    elif report.passed:
        console.print("\n[green]✅ Skill passed security scan![/green]")


@skills_app.command("security")
def skills_security_status():
    """Show security configuration status."""
    from nanobot.config.loader import load_config
    from rich.table import Table
    
    config = load_config()
    security = config.security
    
    table = Table(title="Security Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")
    
    table.add_row("Security Enabled", str(security.enabled), "✅" if security.enabled else "❌")
    table.add_row("Strict Mode", str(security.strict_mode), "🟡 Active" if security.strict_mode else "🟢 Normal")
    table.add_row("Scan on Install", str(security.scan_on_install), "✅" if security.scan_on_install else "❌")
    table.add_row("Block Critical", str(security.block_on_critical), "🚫" if security.block_on_critical else "⚠️")
    table.add_row("Block High", str(security.block_on_high), "🚫" if security.block_on_high else "⚠️")
    table.add_row("Network Installs", str(security.allow_network_installs), "⚠️ Allowed" if security.allow_network_installs else "🚫 Blocked")
    
    console.print(table)


@skills_app.command("approve")
def skills_approve(
    skill_name: str = typer.Argument(..., help="Name of skill to approve"),
    force: bool = typer.Option(False, "--force", help="Force approval even if dangerous"),
):
    """
    Approve a skill for use (overrides security warnings).
    
    Examples:
        nanobot skills approve x-bookmarks
        nanobot skills approve my-skill --force
    """
    from nanobot.agent.skills import SkillsLoader
    from nanobot.config.loader import load_config
    from nanobot.security.skill_scanner import scan_skill, format_report_for_cli
    
    config = load_config()
    workspace = config.workspace_path
    loader = SkillsLoader(workspace)
    
    # Check if skill exists
    skill_path = workspace / "skills" / skill_name
    if not skill_path.exists():
        console.print(f"[red]❌ Skill not found: {skill_name}[/red]")
        console.print("[dim]Make sure the skill is in your workspace/skills/ directory[/dim]")
        raise typer.Exit(1)
    
    # Show current status
    status = loader.get_verification_status(skill_name)
    console.print(f"[dim]Current status: {status}[/dim]\n")
    
    # If rejected or pending, show scan results
    if status in ["rejected", "pending"]:
        console.print("[yellow]⚠️  Security scan detected issues. Review below:[/yellow]\n")
        report = scan_skill(skill_path)
        console.print(format_report_for_cli(report))
        
        if not report.passed and not force:
            console.print("\n[red]🚫 This skill has security concerns![/red]")
            console.print("[yellow]Use --force to approve anyway (not recommended)[/yellow]")
            raise typer.Exit(1)
        
        if force:
            console.print("\n[orange]⚠️  FORCE APPROVAL - Bypassing security warnings[/orange]")
    
    # Approve the skill
    if loader.approve_skill(skill_name):
        console.print(f"\n[green]✅ Skill '{skill_name}' has been approved![/green]")
        console.print("[dim]The skill is now available for use by the agent.[/dim]")
    else:
        console.print(f"[red]❌ Failed to approve skill[/red]")


@skills_app.command("reject")
def skills_reject(
    skill_name: str = typer.Argument(..., help="Name of skill to mark as dangerous"),
):
    """Mark a skill as rejected/dangerous (blocks usage)."""
    from nanobot.agent.skills import SkillsLoader
    from nanobot.config.loader import load_config
    
    config = load_config()
    workspace = config.workspace_path
    loader = SkillsLoader(workspace)
    
    skill_path = workspace / "skills" / skill_name
    if not skill_path.exists():
        console.print(f"[red]❌ Skill not found: {skill_name}[/red]")
        raise typer.Exit(1)
    
    if loader.reject_skill(skill_name):
        console.print(f"[red]🚫 Skill '{skill_name}' has been marked as REJECTED[/red]")
        console.print("[dim]The skill will not be available for use.[/dim]")
        console.print("[dim]To remove the skill completely, delete the folder: {skill_path}[/dim]")
    else:
        console.print(f"[red]❌ Failed to reject skill[/red]")


@skills_app.command("list")
def skills_list(
    all: bool = typer.Option(False, "--all", help="Show all skills including pending/rejected"),
):
    """List all skills and their verification status."""
    from nanobot.agent.skills import SkillsLoader, SkillVerificationStatus
    from nanobot.config.loader import load_config
    from rich.table import Table
    
    config = load_config()
    workspace = config.workspace_path
    loader = SkillsLoader(workspace)
    
    skills = loader.list_skills(filter_unavailable=False, include_verification=True)
    
    if not skills:
        console.print("[dim]No skills found[/dim]")
        return
    
    table = Table(title="Installed Skills")
    table.add_column("Skill", style="cyan")
    table.add_column("Source", style="blue")
    table.add_column("Status", style="green")
    table.add_column("Risk", style="yellow")
    
    for s in skills:
        name = s["name"]
        source = s.get("source", "unknown")
        verified = s.get("verified", "unknown")
        risk = s.get("risk_score", "0")
        
        # Status formatting
        if verified == SkillVerificationStatus.APPROVED:
            status_str = "✅ Approved"
            status_color = "green"
        elif verified == SkillVerificationStatus.MANUAL_APPROVAL:
            status_str = "✅ Manually Approved"
            status_color = "blue"
        elif verified == SkillVerificationStatus.REJECTED:
            status_str = "🚫 Rejected"
            status_color = "red"
        elif verified == SkillVerificationStatus.PENDING:
            status_str = "⏳ Pending"
            status_color = "yellow"
        else:
            status_str = "❓ Unknown"
            status_color = "dim"
        
        # Risk color
        if risk == "0" or risk == 0:
            risk_str = "🟢 None"
        elif int(str(risk)) < 25:
            risk_str = f"🟡 {risk}"
        elif int(str(risk)) < 50:
            risk_str = f"🟠 {risk}"
        else:
            risk_str = f"🔴 {risk}"
        
        table.add_row(name, source, f"[{status_color}]{status_str}[/{status_color}]", risk_str)
    
    console.print(table)
    console.print("\n[dim]Use 'nanobot skills approve <name>' to approve pending skills[/dim]")


app.add_typer(skills_app, name="skills")

# ============================================================================
# Theme Commands
# ============================================================================

theme_app = typer.Typer(help="Manage crew themes and bot personalities")


@theme_app.command("list")
def theme_list():
    """List available crew themes."""
    from nanobot.themes import list_themes
    
    themes = list_themes()
    
    if not themes:
        console.print("[yellow]No themes available.[/yellow]")
        return
    
    table = Table(title="Available Crew Themes")
    table.add_column("Theme", style="cyan")
    table.add_column("Description")
    table.add_column("Emoji", justify="center")
    
    for theme in themes:
        table.add_row(
            theme["display_name"],
            theme["description"],
            theme["emoji"]
        )
    
    console.print(table)
    console.print("\n[dim]Use 'nanobot theme set <theme_name>' to change your crew's theme[/dim]")


@theme_app.command("set")
def theme_set(
    theme_name: str = typer.Argument(..., help="Theme name (pirate_crew, rock_band, swat_team, feral_clowder, executive_suite, space_crew)"),
):
    """Set the crew theme."""
    from nanobot.themes import get_theme, ThemeManager
    from nanobot.config.loader import get_data_dir
    import json
    
    # Validate theme
    theme = get_theme(theme_name)
    if not theme:
        console.print(f"[red]❌ Unknown theme: {theme_name}[/red]")
        console.print("\n[dim]Available themes:[/dim]")
        theme_list()
        raise typer.Exit(1)
    
    # Save theme preference
    config_dir = get_data_dir()
    theme_config_file = config_dir / "theme_config.json"
    
    theme_config = {
        "current_theme": theme_name,
        "theme_display_name": theme.name.value.replace("_", " ").title(),
        "emoji": theme.nanobot.emoji,
    }
    
    theme_config_file.write_text(json.dumps(theme_config, indent=2))
    
    console.print(f"\n{theme.nanobot.emoji} [green]✓ Theme set to:[/green] {theme.name.value.replace('_', ' ').title()}")
    console.print(f"[dim]{theme.description}[/dim]\n")
    
    # Show bot personalities in this theme
    table = Table(title="Your Crew")
    table.add_column("Bot", style="cyan")
    table.add_column("Role")
    table.add_column("Personality")
    table.add_column("Emoji", justify="center")
    
    bot_mappings = [
        ("nanobot", "Leader"),
        ("researcher", "Researcher"),
        ("coder", "Coder"),
        ("social", "Social"),
        ("creative", "Creative"),
        ("auditor", "Auditor"),
    ]
    
    for bot_name, role in bot_mappings:
        theming = theme.get_bot_theming(bot_name)
        if theming:
            table.add_row(
                role,
                theming.title,
                theming.personality[:40] + "..." if len(theming.personality) > 40 else theming.personality,
                theming.emoji
            )
    
    console.print(table)
    console.print("\n[dim]Restart nanobot to apply the new theme to your crew.[/dim]")


@theme_app.command("show")
def theme_show():
    """Show current theme settings."""
    from nanobot.themes import ThemeManager
    from nanobot.config.loader import get_data_dir
    import json
    
    # Load saved theme
    config_dir = get_data_dir()
    theme_config_file = config_dir / "theme_config.json"
    
    if theme_config_file.exists():
        theme_config = json.loads(theme_config_file.read_text())
        current_theme_name = theme_config.get("current_theme", "pirate_crew")
    else:
        current_theme_name = "pirate_crew"
    
    # Get theme
    theme_manager = ThemeManager(current_theme_name)
    theme = theme_manager.get_current_theme()
    
    if not theme:
        console.print("[yellow]No theme currently set.[/yellow]")
        return
    
    console.print(f"\n{theme.nanobot.emoji} [bold]{theme.name.value.replace('_', ' ').title()}[/bold]")
    console.print(f"[dim]{theme.description}[/dim]\n")
    
    table = Table(title="Current Crew")
    table.add_column("Bot", style="cyan")
    table.add_column("Display Name")
    table.add_column("Greeting")
    
    bot_roles = [
        ("nanobot", "Leader"),
        ("researcher", "Researcher"),
        ("coder", "Coder"),
        ("social", "Social"),
        ("creative", "Creative"),
        ("auditor", "Auditor"),
    ]
    
    for bot_name, role in bot_roles:
        theming = theme.get_bot_theming(bot_name)
        if theming:
            greeting = theming.greeting[:50] + "..." if len(theming.greeting) > 50 else theming.greeting
            table.add_row(
                f"{theming.emoji} {role}",
                theming.title,
                f"[dim]'{greeting}'[/dim]"
            )
    
    console.print(table)


app.add_typer(theme_app, name="theme")

# ============================================================================
# Bot Management Commands
# ============================================================================

bot_app = typer.Typer(help="Manage your AI crew members")


@bot_app.command("list")
def bot_list():
    """List all crew members."""
    from nanobot.bots.definitions import (
        NANOBOT_ROLE,
        RESEARCHER_ROLE,
        CODER_ROLE,
        SOCIAL_ROLE,
        CREATIVE_ROLE,
        AUDITOR_ROLE,
    )
    from nanobot.config.loader import get_data_dir
    import json
    
    # Load custom names
    config_dir = get_data_dir()
    bot_names_file = config_dir / "bot_custom_names.json"
    custom_names = {}
    if bot_names_file.exists():
        custom_names = json.loads(bot_names_file.read_text())
    
    from nanobot.models import get_bot_registry
    registry = get_bot_registry()
    bot_names = registry.get_bot_names()
    
    table = Table(title="Your AI Crew")
    table.add_column("Bot", style="cyan")
    table.add_column("Display Name")
    table.add_column("Domain")
    table.add_column("Status")
    
    for bot_id in bot_names:
        role_card = registry.get_role_card(bot_id)
        custom_name = custom_names.get(bot_id)
        display = custom_name if custom_name else bot_id.title()
        status = "🟢 Active" if custom_name else "⚪ Default"
        
        domain = role_card.domain.value if role_card else "unknown"
        emoji = "🤖"
        
        table.add_row(
            f"{emoji} {bot_id}",
            display,
            domain,
            status
        )
    
    console.print(table)
    console.print("\n[dim]Use 'nanobot bot rename <bot> <name>' to customize names[/dim]")


@bot_app.command("rename")
def bot_rename(
    bot_name: str = typer.Argument(..., help="Bot to rename (nanobot, researcher, coder, social, creative, auditor)"),
    new_name: str = typer.Argument(..., help="New display name"),
):
    """Rename a crew member."""
    from nanobot.config.loader import get_data_dir
    import json
    
    # Validate bot name
    valid_bots = ["nanobot", "researcher", "coder", "social", "creative", "auditor"]
    if bot_name.lower() not in valid_bots:
        console.print(f"[red]❌ Unknown bot: {bot_name}[/red]")
        console.print(f"[dim]Valid bots: {', '.join(valid_bots)}[/dim]")
        raise typer.Exit(1)
    
    # Load existing custom names
    config_dir = get_data_dir()
    bot_names_file = config_dir / "bot_custom_names.json"
    custom_names = {}
    if bot_names_file.exists():
        custom_names = json.loads(bot_names_file.read_text())
    
    # Update name
    old_name = custom_names.get(bot_name.lower(), "(default)")
    custom_names[bot_name.lower()] = new_name
    
    # Save
    bot_names_file.write_text(json.dumps(custom_names, indent=2))
    
    console.print(f"\n📝 [green]✓ Renamed {bot_name}:[/green]")
    console.print(f"   From: [dim]{old_name}[/dim]")
    console.print(f"   To:   [bold]{new_name}[/bold]")
    console.print("\n[dim]Restart nanobot to see the change.[/dim]")


@bot_app.command("reset")
def bot_reset(
    bot_name: str = typer.Argument(..., help="Bot to reset (or 'all' for all bots)"),
):
    """Reset a crew member's name to default."""
    from nanobot.config.loader import get_data_dir
    import json
    
    config_dir = get_data_dir()
    bot_names_file = config_dir / "bot_custom_names.json"
    
    if not bot_names_file.exists():
        console.print("[yellow]No custom names to reset.[/yellow]")
        return
    
    custom_names = json.loads(bot_names_file.read_text())
    
    if bot_name.lower() == "all":
        # Reset all
        count = len(custom_names)
        custom_names = {}
        bot_names_file.write_text(json.dumps(custom_names, indent=2))
        console.print(f"\n🔄 [green]✓ Reset {count} crew members to default names[/green]")
    else:
        # Reset specific bot
        if bot_name.lower() in custom_names:
            old_name = custom_names.pop(bot_name.lower())
            bot_names_file.write_text(json.dumps(custom_names, indent=2))
            console.print(f"\n🔄 [green]✓ Reset {bot_name}[/green] (was: {old_name})")
        else:
            console.print(f"[yellow]{bot_name} already uses default name[/yellow]")
    
    console.print("\n[dim]Restart nanobot to see the changes.[/dim]")


app.add_typer(bot_app, name="bot")

# ============================================================================
# Room Commands
# ============================================================================

room_app = typer.Typer(help="Manage rooms and bot invitations")


@room_app.command("list")
def room_list():
    """List all rooms."""
    from nanobot.bots.room_manager import get_room_manager
    
    manager = get_room_manager()
    rooms = manager.list_rooms()
    
    if not rooms:
        console.print("[yellow]No rooms found.[/yellow]")
        return
    
    table = Table(title="Rooms")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="blue")
    table.add_column("Bots", style="green")
    table.add_column("Default", style="yellow")
    
    for room in rooms:
        is_default = "★" if room["is_default"] else ""
        bots = ", ".join(room["participants"])
        table.add_row(
            room["id"],
            room["type"],
            bots,
            is_default
        )
    
    console.print(table)
    console.print("\n[dim]Use 'nanobot room create <name>' to create new room[/dim]")


@room_app.command("create")
def room_create(
    name: str = typer.Argument(..., help="Room name"),
    bots: Optional[str] = typer.Option(None, "--bots", "-b", help="Comma-separated bot names (default: nanobot only)"),
):
    """Create a new room."""
    from nanobot.bots.room_manager import get_room_manager
    from nanobot.models.room import RoomType
    
    manager = get_room_manager()
    
    # Parse bot list
    if bots:
        participant_list = [b.strip() for b in bots.split(",")]
    else:
        participant_list = ["nanobot"]  # Default to just Leader
    
    try:
        room = manager.create_room(
            name=name,
            room_type=RoomType.PROJECT,
            participants=participant_list
        )
        console.print(f"\n✅ [green]Created room:[/green] {room.id}")
        console.print(f"   Participants: {', '.join(room.participants)}")
        console.print(f"\n[dim]Use 'nanobot room invite {room.id} <bot>' to add more bots[/dim]")
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)


@room_app.command("invite")
def room_invite(
    room_id: str = typer.Argument(..., help="Room ID"),
    bot_name: str = typer.Argument(..., help="Bot to invite (nanobot, researcher, coder, social, creative, auditor)"),
):
    """Invite a bot to a room."""
    from nanobot.bots.room_manager import get_room_manager
    
    manager = get_room_manager()
    
    # Validate bot name
    valid_bots = ["nanobot", "researcher", "coder", "social", "creative", "auditor"]
    if bot_name.lower() not in valid_bots:
        console.print(f"[red]❌ Invalid bot name: {bot_name}[/red]")
        console.print(f"[dim]Valid bots: {', '.join(valid_bots)}[/dim]")
        raise typer.Exit(1)
    
    success = manager.invite_bot(room_id, bot_name.lower())
    
    if success:
        console.print(f"\n✅ [green]Invited {bot_name} to {room_id}[/green]")
    else:
        console.print(f"[yellow]⚠ {bot_name} is already in {room_id} or room not found[/yellow]")


@room_app.command("remove")
def room_remove(
    room_id: str = typer.Argument(..., help="Room ID"),
    bot_name: str = typer.Argument(..., help="Bot to remove"),
):
    """Remove a bot from a room."""
    from nanobot.bots.room_manager import get_room_manager
    
    manager = get_room_manager()
    
    success = manager.remove_bot(room_id, bot_name.lower())
    
    if success:
        console.print(f"\n✅ [green]Removed {bot_name} from {room_id}[/green]")
    else:
        console.print(f"[yellow]⚠ Could not remove {bot_name} (not in room, or room not found)[/yellow]")


@room_app.command("show")
def room_show(
    room_id: str = typer.Argument(..., help="Room ID (or 'general' for default)"),
):
    """Show room details."""
    from nanobot.bots.room_manager import get_room_manager
    
    manager = get_room_manager()
    room = manager.get_room(room_id)
    
    if not room:
        console.print(f"[red]❌ Room '{room_id}' not found[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n📁 [bold]{room.id}[/bold]")
    console.print(f"   Type: {room.type.value}")
    console.print(f"   Created: {room.created_at}")
    console.print(f"\n   Participants ({len(room.participants)}):")
    
    for bot in room.participants:
        console.print(f"   • {bot}")
    
    console.print(f"\n[dim]Use 'nanobot room invite {room_id} <bot>' to add bots[/dim]")


app.add_typer(room_app, name="room")

# Import and wire heartbeat commands
try:
    from nanobot.cli.heartbeat_commands import heartbeat_app
    app.add_typer(heartbeat_app, name="heartbeat")
except ImportError:
    logger.warning("Could not import heartbeat commands")


if __name__ == "__main__":
    app()
