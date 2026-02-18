"""Configuration schema using Pydantic."""

from pathlib import Path

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class WhatsAppConfig(Base):
    """WhatsApp channel configuration.

    For secure defaults (Tailscale IP + random port), leave bridge_url empty
    and it will be auto-configured on first run.
    """
    enabled: bool = False
    bridge_url: str = ""  # Auto-configured if empty: uses Tailscale/LAN IP + random port
    bridge_token: str = ""  # Shared token for bridge auth (optional, recommended)
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers
    _auto_configured: bool = False  # Track if URL was auto-configured

    def get_bridge_url(self) -> str:
        """Get effective bridge URL, auto-configuring if needed."""
        if self.bridge_url:
            return self.bridge_url

        # Auto-configure secure defaults
        try:
            from nanofolks.utils.network import get_secure_bind_address

            bind_addr = get_secure_bind_address("bridge")
            url = f"ws://{bind_addr.host}:{bind_addr.port}"

            # Save to config for future runs
            self._save_auto_configured_url(url)

            return url
        except Exception:
            # Fallback to legacy default
            return "ws://localhost:3001"

    def _save_auto_configured_url(self, url: str) -> None:
        """Save auto-configured URL to config file."""
        if self._auto_configured:
            return  # Already saved

        try:
            from nanofolks.config.loader import load_config, save_config

            config = load_config()
            config.channels.whatsapp.bridge_url = url
            save_config(config)
            self._auto_configured = True
            logger.info(f"Saved auto-configured WhatsApp bridge URL: {url}")
        except Exception as e:
            logger.warning(f"Could not save auto-configured bridge URL: {e}")


class TelegramConfig(Base):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"


class DiscordConfig(Base):
    """Discord channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT

class EmailConfig(Base):
    """Email channel configuration (IMAP inbound + SMTP outbound)."""
    enabled: bool = False
    consent_granted: bool = False  # Explicit owner permission to access mailbox data

    # IMAP (receive)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_mailbox: str = "INBOX"
    imap_use_ssl: bool = True

    # SMTP (send)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    from_address: str = ""

    # Behavior
    auto_reply_enabled: bool = True  # If false, inbound email is read but no automatic reply is sent
    poll_interval_seconds: int = 30
    mark_seen: bool = True
    max_body_chars: int = 12000
    subject_prefix: str = "Re: "
    allow_from: list[str] = Field(default_factory=list)  # Allowed sender email addresses


class SlackDMConfig(Base):
    """Slack DM policy configuration."""
    enabled: bool = True
    policy: str = "open"  # "open" or "allowlist"
    allow_from: list[str] = Field(default_factory=list)  # Allowed Slack user IDs


class SlackConfig(Base):
    """Slack channel configuration."""
    enabled: bool = False
    mode: str = "socket"  # "socket" supported
    webhook_path: str = "/slack/events"
    bot_token: str = ""  # xoxb-...
    app_token: str = ""  # xapp-...
    user_token_read_only: bool = True
    group_policy: str = "mention"  # "mention", "open", "allowlist"
    group_allow_from: list[str] = Field(default_factory=list)  # Allowed channel IDs if allowlist
    dm: SlackDMConfig = Field(default_factory=SlackDMConfig)


class ChannelsConfig(Base):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)


class AgentDefaults(Base):
    """Default agent configuration."""
    workspace: str = "~/.nanofolks/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20
    # system_timezone is read from workspace/USER.md (preferred) or defaults to UTC
    # This is here for backward compatibility and CLI defaults only


class AgentsConfig(Base):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None
    extra_headers: dict[str, str] | None = None  # Custom headers (e.g. APP-Code for AiHubMix)


class ProvidersConfig(Base):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)  # AiHubMix API gateway


class GatewayConfig(Base):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(Base):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(Base):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""
    timeout: int = 60


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""
    command: str = ""  # Stdio: command to run (e.g. "npx")
    args: list[str] = Field(default_factory=list)  # Stdio: command arguments
    env: dict[str, str] = Field(default_factory=dict)  # Stdio: extra env vars
    url: str = ""  # HTTP: streamable HTTP endpoint URL


class ToolsConfig(Base):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory
    evolutionary: bool = False  # If true, use allowed_paths whitelist instead of restrict_to_workspace
    allowed_paths: list[str] = Field(default_factory=list)  # Paths allowed when evolutionary mode is enabled (e.g., ["/projects/nanobot-turbo", "~/.nanofolks"])
    protected_paths: list[str] = Field(default_factory=lambda: ["~/.nanofolks/config.json"])  # Paths that are always blocked, even within allowed_paths (e.g., config files with secrets)
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)  # MCP server configurations


class RoutingTierConfig(Base):
    """Configuration for a routing tier."""
    model: str
    cost_per_mtok: float = 1.0
    secondary_model: str | None = None  # Fallback if primary fails


class RoutingTiersConfig(Base):
    """Configuration for all routing tiers."""
    simple: RoutingTierConfig = Field(default_factory=lambda: RoutingTierConfig(
        model="deepseek/deepseek-chat-v3-0324",
        cost_per_mtok=0.27,
        secondary_model="deepseek/deepseek-chat-v3.1"
    ))
    medium: RoutingTierConfig = Field(default_factory=lambda: RoutingTierConfig(
        model="openai/gpt-4.1-mini",
        cost_per_mtok=0.40,
        secondary_model="openai/gpt-4o-mini"
    ))
    complex: RoutingTierConfig = Field(default_factory=lambda: RoutingTierConfig(
        model="anthropic/claude-sonnet-4.5",
        cost_per_mtok=3.0,
        secondary_model="anthropic/claude-sonnet-4"
    ))
    reasoning: RoutingTierConfig = Field(default_factory=lambda: RoutingTierConfig(
        model="openai/o3",
        cost_per_mtok=2.0,
        secondary_model="openai/gpt-4o"
    ))
    coding: RoutingTierConfig = Field(default_factory=lambda: RoutingTierConfig(
        model="moonshotai/kimi-k2.5",
        cost_per_mtok=0.45,
        secondary_model="anthropic/claude-sonnet-4"
    ))


# Provider-specific routing tier mappings
# Maps each provider to equivalent models for each tier
# These are selected to match OpenRouter's tier capabilities as closely as possible
ROUTING_TIER_MAPPINGS: dict[str, dict[str, dict[str, str]]] = {
    # OpenRouter - gateway, can route anywhere (keep original defaults)
    "openrouter": {
        "simple": {"model": "deepseek/deepseek-chat-v3-0324", "secondary": "deepseek/deepseek-chat-v3.1"},
        "medium": {"model": "openai/gpt-4.1-mini", "secondary": "openai/gpt-4o-mini"},
        "complex": {"model": "anthropic/claude-sonnet-4.5", "secondary": "anthropic/claude-sonnet-4"},
        "reasoning": {"model": "openai/o3", "secondary": "openai/gpt-4o"},
        "coding": {"model": "moonshotai/kimi-k2.5", "secondary": "anthropic/claude-sonnet-4"},
    },
    # Anthropic - Claude models
    "anthropic": {
        "simple": {"model": "claude-3-haiku-20240307", "secondary": "claude-3-5-haiku-20241022"},
        "medium": {"model": "claude-3-5-sonnet-20241022", "secondary": "claude-3-opus-20240229"},
        "complex": {"model": "claude-3-opus-20240229", "secondary": "claude-3-5-sonnet-20241022"},
        "reasoning": {"model": "claude-sonnet-4-20250514", "secondary": "claude-3-opus-20240229"},
        "coding": {"model": "claude-sonnet-4-20250514", "secondary": "claude-3-5-sonnet-20241022"},
    },
    # OpenAI - GPT models
    "openai": {
        "simple": {"model": "gpt-4o-mini", "secondary": "gpt-4-turbo"},
        "medium": {"model": "gpt-4-turbo", "secondary": "gpt-4o"},
        "complex": {"model": "gpt-4o", "secondary": "gpt-4-turbo"},
        "reasoning": {"model": "o3", "secondary": "gpt-4o"},
        "coding": {"model": "o3", "secondary": "gpt-4o"},
    },
    # DeepSeek - DeepSeek models
    "deepseek": {
        "simple": {"model": "deepseek-chat", "secondary": "deepseek-chat"},
        "medium": {"model": "deepseek-chat", "secondary": "deepseek-coder"},
        "complex": {"model": "deepseek-chat", "secondary": "deepseek-coder"},
        "reasoning": {"model": "deepseek-reasoner", "secondary": "deepseek-chat"},
        "coding": {"model": "deepseek-coder", "secondary": "deepseek-chat"},
    },
    # Google Gemini models
    "gemini": {
        "simple": {"model": "gemini-2.0-flash", "secondary": "gemini-1.5-flash"},
        "medium": {"model": "gemini-1.5-flash", "secondary": "gemini-2.0-flash"},
        "complex": {"model": "gemini-2.0-pro", "secondary": "gemini-1.5-pro"},
        "reasoning": {"model": "gemini-2.0-pro", "secondary": "gemini-1.5-pro"},
        "coding": {"model": "gemini-2.0-flash", "secondary": "gemini-1.5-flash"},
    },
    # Moonshot - Kimi models
    "moonshot": {
        "simple": {"model": "kimi-k2.5", "secondary": "kimi-k2"},
        "medium": {"model": "kimi-k2.5", "secondary": "kimi-k2"},
        "complex": {"model": "kimi-k2", "secondary": "kimi-k2.5"},
        "reasoning": {"model": "kimi-k2", "secondary": "kimi-k2.5"},
        "coding": {"model": "kimi-k2.5", "secondary": "kimi-k2"},
    },
    # DashScope - Qwen models
    "dashscope": {
        "simple": {"model": "qwen-turbo", "secondary": "qwen-plus"},
        "medium": {"model": "qwen-plus", "secondary": "qwen-max"},
        "complex": {"model": "qwen-max", "secondary": "qwen-plus"},
        "reasoning": {"model": "qwen-max", "secondary": "qwen-plus"},
        "coding": {"model": "qwen-coder-turbo", "secondary": "qwen-plus"},
    },
    # Zhipu - GLM models
    "zhipu": {
        "simple": {"model": "glm-4-flash", "secondary": "glm-4"},
        "medium": {"model": "glm-4", "secondary": "glm-4-flash"},
        "complex": {"model": "glm-4", "secondary": "glm-4-plus"},
        "reasoning": {"model": "glm-4", "secondary": "glm-4-plus"},
        "coding": {"model": "glm-4", "secondary": "glm-4-flash"},
    },
    # MiniMax - MiniMax models
    "minimax": {
        "simple": {"model": "MiniMax-Text-01", "secondary": "abab6.5s-chat"},
        "medium": {"model": "abab6.5s-chat", "secondary": "MiniMax-Text-01"},
        "complex": {"model": "MiniMax-Text-01", "secondary": "abab6.5s-chat"},
        "reasoning": {"model": "MiniMax-Text-01", "secondary": "abab6.5s-chat"},
        "coding": {"model": "MiniMax-Text-01", "secondary": "abab6.5s-chat"},
    },
    # Groq - Fast inference models
    "groq": {
        "simple": {"model": "llama-3.1-8b-instant", "secondary": "mixtral-8x7b-32768"},
        "medium": {"model": "llama-3.1-70b-versatile", "secondary": "llama-3.1-8b-instant"},
        "complex": {"model": "llama-3.1-70b-versatile", "secondary": "mixtral-8x7b-32768"},
        "reasoning": {"model": "llama-3.1-70b-versatile", "secondary": "llama-3.1-8b-instant"},
        "coding": {"model": "llama-3.1-70b-versatile", "secondary": "mixtral-8x7b-32768"},
    },
    # AiHubMix - Gateway, can route to OpenAI-compatible models
    "aihubmix": {
        "simple": {"model": "gpt-4o-mini", "secondary": "claude-3-haiku"},
        "medium": {"model": "gpt-4o", "secondary": "claude-3-sonnet"},
        "complex": {"model": "claude-3-opus", "secondary": "gpt-4o"},
        "reasoning": {"model": "gpt-4o", "secondary": "claude-3-opus"},
        "coding": {"model": "claude-3-sonnet", "secondary": "gpt-4o"},
    },
}


def get_routing_tiers_for_provider(provider: str) -> RoutingTiersConfig:
    """Get routing tier configuration for a specific provider.

    Args:
        provider: Provider name (e.g., "openrouter", "anthropic", "openai")

    Returns:
        RoutingTiersConfig with provider-specific models
    """
    mapping = ROUTING_TIER_MAPPINGS.get(provider, ROUTING_TIER_MAPPINGS["openrouter"])

    return RoutingTiersConfig(
        simple=RoutingTierConfig(
            model=mapping["simple"]["model"],
            cost_per_mtok=0.3,
            secondary_model=mapping["simple"].get("secondary")
        ),
        medium=RoutingTierConfig(
            model=mapping["medium"]["model"],
            cost_per_mtok=0.5,
            secondary_model=mapping["medium"].get("secondary")
        ),
        complex=RoutingTierConfig(
            model=mapping["complex"]["model"],
            cost_per_mtok=2.0,
            secondary_model=mapping["complex"].get("secondary")
        ),
        reasoning=RoutingTierConfig(
            model=mapping["reasoning"]["model"],
            cost_per_mtok=2.0,
            secondary_model=mapping["reasoning"].get("secondary")
        ),
        coding=RoutingTierConfig(
            model=mapping["coding"]["model"],
            cost_per_mtok=1.0,
            secondary_model=mapping["coding"].get("secondary")
        ),
    )


class ClientClassifierConfig(Base):
    """Configuration for client-side classifier."""
    min_confidence: float = 0.85


class LLMClassifierConfig(Base):
    """Configuration for LLM-assisted classifier."""
    model: str = "gpt-4o-mini"
    timeout_ms: int = 500
    # Optional secondary model to use if the primary LLM classifier fails
    secondary_model: str | None = None


class StickyRoutingConfig(Base):
    """Configuration for sticky routing behavior."""
    context_window: int = 5
    downgrade_confidence: float = 0.9


class AutoCalibrationConfig(Base):
    """Configuration for auto-calibration."""
    enabled: bool = True
    interval: str = "24h"
    min_classifications: int = 50
    max_patterns: int = 100
    backup_before_calibration: bool = True


class RoutingConfig(Base):
    """Configuration for smart routing."""
    enabled: bool = False  # Disabled by default - user must explicitly enable
    tiers: RoutingTiersConfig = Field(default_factory=RoutingTiersConfig)
    client_classifier: ClientClassifierConfig = Field(default_factory=ClientClassifierConfig)
    llm_classifier: LLMClassifierConfig = Field(default_factory=LLMClassifierConfig)
    sticky: StickyRoutingConfig = Field(default_factory=StickyRoutingConfig)
    auto_calibration: AutoCalibrationConfig = Field(default_factory=AutoCalibrationConfig)
    streaming_enabled: bool = True  # Stream LLM responses to CLI in real-time
    stream_update_interval_ms: int = 100  # How often to update the streaming display (ms)


class BackgroundConfig(Base):
    """Background processing configuration for memory system."""
    enabled: bool = True
    interval_seconds: int = 60          # Check every 60s
    quiet_threshold_seconds: int = 30   # User inactive for 30s = safe to run


class EmbeddingConfig(Base):
    """Embedding provider configuration."""
    provider: str = "local"             # "local" or "api"
    local_model: str = "BAAI/bge-small-en-v1.5"
    api_model: str = "qwen/qwen3-embedding-0.6b"
    api_fallback: bool = True           # Fall back to API if local fails
    cache_embeddings: bool = True
    lazy_load: bool = True              # Download models on first use


class ExtractionConfig(Base):
    """Entity extraction configuration."""
    enabled: bool = True
    provider: str = "gliner2"           # "gliner2" (only option now)
    gliner2_model: str = "fastino/gliner2-base-v1"
    interval_seconds: int = 60
    batch_size: int = 20
    api_fallback: bool = False          # Use LLM for complex extractions
    api_model: str = ""                 # Uses LLM classifier model if empty


class SummaryConfig(Base):
    """Summary node configuration."""
    staleness_threshold: int = 10       # Events before refresh
    max_refresh_batch: int = 20         # Max nodes to refresh per cycle
    model: str = ""                     # Uses LLM classifier model if empty


class LearningConfig(Base):
    """Learning and preferences configuration."""
    enabled: bool = True
    decay_days: int = 14                # Half-life for learning relevance
    max_learnings: int = 200             # Max active learnings
    relevance_decay_rate: float = 0.05   # 5% per day


class ContextConfig(Base):
    """Context assembly configuration."""
    total_budget: int = 4000            # Total token budget for memory context
    always_include_preferences: bool = True


class SessionCompactionConfig(Base):
    """
    Session compaction configuration for long conversations.

    Inspired by OpenClaw's production-hardened compaction system.
    Prevents context overflow while preserving conversation coherence.

    Modes:
    - summary: Smart summarization of older messages (default)
    - token-limit: Hard truncation at safe boundaries (emergency)
    - off: Disable auto-compaction (manual only)
    """
    enabled: bool = True
    mode: str = "summary"               # summary | token-limit | off
    threshold_percent: float = 0.8      # Trigger at 80% (proactive, not reactive)
    target_tokens: int = 3000           # Target session history size
    min_messages: int = 10                # Always keep at least 10
    max_messages: int = 100             # Hard limit
    preserve_recent: int = 20           # Keep last N messages verbatim
    preserve_tool_chains: bool = True   # NEVER break tool_use → tool_result pairs
    summary_chunk_size: int = 10        # Summarize N messages at a time
    enable_memory_flush: bool = True    # Allow pre-compaction memory sync


class EnhancedContextConfig(Base):
    """
    Enhanced context assembly with real-time monitoring.

    Provides accurate token counting, budget allocation, and
    context percentage visibility (context=X%).
    """
    # Budget allocation
    max_context_tokens: int = 8000      # Total model context window
    response_buffer: int = 1000         # Reserve for model response
    memory_budget_percent: float = 0.35   # 35% for memory context
    history_budget_percent: float = 0.35  # 35% for session history
    system_budget_percent: float = 0.20   # 20% for system prompt

    # Real-time monitoring
    enable_real_time_tracking: bool = True
    show_context_percentage: bool = True  # Show context=65% in status
    warning_threshold: float = 0.70       # Warn at 70%
    compaction_threshold: float = 0.80    # Compact at 80%

    # Priority truncation
    enable_priority_truncation: bool = True
    min_history_messages: int = 10
    preserve_user_preferences: bool = True


class PrivacyConfig(Base):
    """Privacy and security configuration."""
    auto_redact_pii: bool = True
    auto_redact_credentials: bool = True
    excluded_patterns: list[str] = Field(default_factory=lambda: [
        "password", "api_key", "secret", "token", "credential"
    ])


class SecurityConfig(Base):
    """Security and skill scanning configuration."""
    enabled: bool = True  # Enable security scanning
    strict_mode: bool = False  # Block on MEDIUM severity (not just CRITICAL/HIGH)
    block_on_critical: bool = True  # Always block critical issues
    block_on_high: bool = True  # Always block high severity issues
    scan_on_install: bool = True  # Scan skills when installing
    scan_on_load: bool = False  # Scan skills when loading (performance impact)
    allowed_shell_commands: list[str] = Field(default_factory=lambda: [
        "git", "npm", "node", "python", "python3", "pip", "pnpm", "yarn"
    ])
    blocked_patterns: list[str] = Field(default_factory=lambda: [
        "curl.*\\|.*bash", "curl.*\\|.*sh", "wget.*\\|.*bash", "wget.*\\|.*sh",
        "sudo", "rm -rf /", "rm -rf /*", "> /etc/", "> ~/.ssh/"
    ])
    allow_network_installs: bool = False  # Allow curl/wget during skill install
    sandbox_skills: bool = False  # Run skills in sandbox (future feature)


class MemoryConfig(Base):
    """Memory system configuration."""
    enabled: bool = True
    db_path: str = "memory/memory.db"   # Relative to workspace

    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    summary: SummaryConfig = Field(default_factory=SummaryConfig)
    learning: LearningConfig = Field(default_factory=LearningConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)

    # Session compaction (Phase 8) - Long conversation support
    session_compaction: SessionCompactionConfig = Field(default_factory=SessionCompactionConfig)
    enhanced_context: EnhancedContextConfig = Field(default_factory=EnhancedContextConfig)


class WorkLogsConfig(Base):
    """Work logs configuration for transparency and debugging."""
    enabled: bool = True
    storage: str = "sqlite"  # "sqlite", "memory", "none"
    retention_days: int = 30
    show_in_response: bool = False  # Include in agent responses
    default_mode: str = "summary"  # "summary", "detailed", "debug"
    log_tool_calls: bool = True
    log_routing_decisions: bool = True
    min_confidence_to_log: float = 0.0  # Log all decisions (0.0 = all)

    # Feature flags for gradual rollout
    beta: bool = False  # Beta flag for gradual rollout


class Config(BaseSettings):
    """Root configuration for nanofolks."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    work_logs: WorkLogsConfig = Field(default_factory=WorkLogsConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    def _match_provider(self, model: str | None = None) -> tuple["ProviderConfig | None", str | None]:
        """Match provider config and its registry name. Returns (config, spec_name)."""
        from nanofolks.providers.registry import PROVIDERS
        model_lower = (model or self.agents.defaults.model).lower()

        # Match by keyword (order follows PROVIDERS registry)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and any(kw in model_lower for kw in spec.keywords) and p.api_key:
                return p, spec.name

        # Fallback: gateways first, then others (follows registry order)
        for spec in PROVIDERS:
            p = getattr(self.providers, spec.name, None)
            if p and p.api_key:
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> ProviderConfig | None:
        """Get matched provider config (api_key, api_base, extra_headers). Falls back to first available."""
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> str | None:
        """Get the registry name of the matched provider (e.g. "deepseek", "openrouter")."""
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model. Falls back to first available key."""
        p = self.get_provider(model)
        return p.api_key if p else None

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL for the given model. Applies default URLs for known gateways."""
        from nanofolks.providers.registry import find_by_name
        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        # Only gateways get a default api_base here. Standard providers
        # (like Moonshot) set their base URL via env vars in _setup_env
        # to avoid polluting the global litellm.api_base.
        if name:
            spec = find_by_name(name)
            if spec and spec.is_gateway and spec.default_api_base:
                return spec.default_api_base
        return None

    model_config = ConfigDict(
        env_prefix="NANOFOLKS_",
        env_nested_delimiter="__"
    )
