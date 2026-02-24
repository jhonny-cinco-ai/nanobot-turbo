"""Crew routines configurations for all bot types.

This module provides default crew routines configurations for each bot type
and utilities for loading custom configurations. Users can override
defaults by providing a crew_routines.yaml or crew_routines.json file.

Usage:
    from nanofolks.bots.crew_routines_configs import get_bot_crew_routines_config

    config = get_bot_crew_routines_config("researcher")
    service = BotCrewRoutinesService(bot, config)
    await service.start()
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from loguru import logger

from nanofolks.routines.crew.crew_routines_models import CheckDefinition, CheckPriority, CrewRoutinesConfig

# Default interval: 60 minutes for specialists, 30 minutes for coordinator
DEFAULT_SPECIALIST_INTERVAL_S = 3600  # 60 minutes
DEFAULT_COORDINATOR_INTERVAL_S = 1800  # 30 minutes


def _create_check(name: str, description: str, priority: str = "normal",
                  max_duration_s: float = 60.0, config: Optional[Dict] = None) -> CheckDefinition:
    """Helper to create a CheckDefinition."""
    priority_map = {
        "critical": CheckPriority.CRITICAL,
        "high": CheckPriority.HIGH,
        "normal": CheckPriority.NORMAL,
        "low": CheckPriority.LOW
    }

    return CheckDefinition(
        name=name,
        description=description,
        priority=priority_map.get(priority, CheckPriority.NORMAL),
        max_duration_s=max_duration_s,
        config=config or {}
    )


# =============================================================================
# Default Configurations by Bot Type
# =============================================================================

RESEARCHER_CONFIG = CrewRoutinesConfig(
    bot_name="researcher",
    interval_s=DEFAULT_SPECIALIST_INTERVAL_S,
    max_execution_time_s=300,
    enabled=False,  # Disabled by default - user must explicitly activate
    checks=[
        _create_check(
            "monitor_data_sources",
            "Check data feeds for updates and availability",
            priority="high",
            max_duration_s=120.0,
            config={
                "sources": [],  # Auto-detect from bot config
                "timeout_s": 30
            }
        ),
        _create_check(
            "track_market_trends",
            "Analyze market changes and detect anomalies",
            priority="normal",
            max_duration_s=180.0,
            config={
                "symbols": [],  # Configurable list of symbols
                "alert_threshold_pct": 5.0
            }
        ),
        _create_check(
            "monitor_research_deadlines",
            "Alert on approaching research deadlines",
            priority="critical",
            max_duration_s=30.0,
            config={
                "alert_days": [7, 3, 1]
            }
        ),
        _create_check(
            "update_competitor_tracking",
            "Track competitor activities and updates",
            priority="normal",
            max_duration_s=90.0,
            config={
                "competitors": [],  # Configurable list
                "track_changes": True
            }
        ),
    ],
    parallel_checks=True,
    max_concurrent_checks=2,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["coordinator"],
    retain_history_count=50
)


CODER_CONFIG = CrewRoutinesConfig(
    bot_name="coder",
    interval_s=DEFAULT_SPECIALIST_INTERVAL_S,
    max_execution_time_s=300,
    enabled=False,  # Disabled by default - user must explicitly activate
    checks=[
        _create_check(
            "check_github_issues",
            "Monitor repos for critical issues requiring attention",
            priority="high",
            max_duration_s=60.0,
            config={
                "repositories": [],  # Auto-detect
                "labels": ["critical", "security", "bug"]
            }
        ),
        _create_check(
            "monitor_build_status",
            "CI/CD pipeline monitoring for failures",
            priority="critical",
            max_duration_s=90.0,
            config={
                "pipelines": [],  # Auto-detect
                "alert_on_failure": True
            }
        ),
        _create_check(
            "security_vulnerability_scan",
            "Dependency security scanning",
            priority="high",
            max_duration_s=120.0,
            config={
                "scan_dependencies": True,
                "severity_threshold": "medium"
            }
        ),
        _create_check(
            "check_dependency_updates",
            "Check for available package updates",
            priority="low",
            max_duration_s=90.0,
            config={
                "check_outdated": True,
                "check_security_only": False
            }
        ),
    ],
    parallel_checks=True,
    max_concurrent_checks=2,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["coordinator"],
    retain_history_count=50
)


SOCIAL_CONFIG = CrewRoutinesConfig(
    bot_name="social",
    interval_s=DEFAULT_SPECIALIST_INTERVAL_S,
    max_execution_time_s=300,
    enabled=False,  # Disabled by default - user must explicitly activate
    checks=[
        _create_check(
            "publish_scheduled_posts",
            "Auto-publish posts scheduled for current time",
            priority="critical",
            max_duration_s=60.0,
            config={}
        ),
        _create_check(
            "monitor_community_mentions",
            "Track mentions requiring response",
            priority="high",
            max_duration_s=90.0,
            config={
                "platforms": ["twitter", "linkedin", "reddit"],
                "sentiment_threshold": "negative"
            }
        ),
        _create_check(
            "check_engagement_metrics",
            "Detect engagement anomalies",
            priority="normal",
            max_duration_s=60.0,
            config={
                "metrics": ["likes", "shares", "comments", "reach"]
            }
        ),
        _create_check(
            "track_trending_topics",
            "Monitor trending topics for opportunities",
            priority="low",
            max_duration_s=120.0,
            config={
                "topics": [],  # Configurable
                "min_volume": 1000
            }
        ),
    ],
    parallel_checks=True,
    max_concurrent_checks=3,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["coordinator"],
    retain_history_count=100
)


AUDITOR_CONFIG = CrewRoutinesConfig(
    bot_name="auditor",
    interval_s=DEFAULT_SPECIALIST_INTERVAL_S,
    max_execution_time_s=600,  # 10 minutes for comprehensive checks
    enabled=False,  # Disabled by default - user must explicitly activate
    checks=[
        # Code/Technical Audits
        _create_check(
            "check_code_quality_scores",
            "Monitor code quality metrics and flag declining trends",
            priority="high",
            max_duration_s=120.0,
            config={
                "repositories": [],  # Auto-detect
                "thresholds": {
                    "coverage": 70,
                    "lint_score": 80,
                    "complexity": 15
                }
            }
        ),
        _create_check(
            "audit_compliance_status",
            "Verify compliance with security and privacy policies",
            priority="critical",
            max_duration_s=180.0,
            config={}
        ),
        _create_check(
            "review_audit_trail_integrity",
            "Verify audit trail completeness and detect gaps",
            priority="high",
            max_duration_s=90.0,
            config={
                "lookback_hours": 24
            }
        ),
        _create_check(
            "check_pending_reviews",
            "Check for pending code reviews and quality gates",
            priority="normal",
            max_duration_s=60.0,
            config={
                "max_wait_hours": 24
            }
        ),
        # Cross-Domain Audits (NEW)
        _create_check(
            "verify_research_outputs",
            "Fact-check research outputs and verify source quality",
            priority="high",
            max_duration_s=150.0,
            config={
                "check_sources": True,
                "verify_claims": True,
                "flag_unverified": True
            }
        ),
        _create_check(
            "check_creative_compliance",
            "Audit creative assets for brand compliance and completeness",
            priority="high",
            max_duration_s=120.0,
            config={
                "check_brand_guidelines": True,
                "check_copyright": True,
                "verify_completeness": True
            }
        ),
        _create_check(
            "assess_social_content_risk",
            "Risk assessment for social media content before publication",
            priority="critical",
            max_duration_s=90.0,
            config={
                "check_unverified_claims": True,
                "check_sensitive_topics": True,
                "check_brand_alignment": True,
                "block_on_critical": True
            }
        ),
        _create_check(
            "verify_cross_bot_handoffs",
            "Check cross-bot workflow compliance and handoff completeness",
            priority="high",
            max_duration_s=100.0,
            config={
                "check_deliverables": True,
                "check_context_transfer": True,
                "verify_dod": True
            }
        ),
        _create_check(
            "check_documentation_completeness",
            "Verify documentation accuracy and completeness across all domains",
            priority="normal",
            max_duration_s=120.0,
            config={
                "check_readmes": True,
                "check_api_docs": True,
                "flag_outdated": True
            }
        ),
    ],
    parallel_checks=True,  # Can run parallel checks for different domains
    max_concurrent_checks=3,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["coordinator"],
    retain_history_count=200  # Keep more history for audits
)


CREATIVE_CONFIG = CrewRoutinesConfig(
    bot_name="creative",
    interval_s=DEFAULT_SPECIALIST_INTERVAL_S,
    max_execution_time_s=300,
    enabled=False,  # Disabled by default - user must explicitly activate
    checks=[
        _create_check(
            "check_design_asset_status",
            "Monitor design asset health and detect outdated files",
            priority="high",
            max_duration_s=90.0,
            config={
                "max_age_days": 30
            }
        ),
        _create_check(
            "monitor_creative_deadlines",
            "Track approaching creative project deadlines",
            priority="critical",
            max_duration_s=60.0,
            config={}
        ),
        _create_check(
            "validate_brand_consistency",
            "Check brand guidelines compliance across assets",
            priority="normal",
            max_duration_s=120.0,
            config={}
        ),
        _create_check(
            "check_content_approval_queue",
            "Monitor content awaiting approval and publishing",
            priority="high",
            max_duration_s=60.0,
            config={
                "max_wait_hours": 48
            }
        ),
    ],
    parallel_checks=True,
    max_concurrent_checks=2,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["coordinator"],
    retain_history_count=50
)


COORDINATOR_CONFIG = CrewRoutinesConfig(
    bot_name="coordinator",
    interval_s=DEFAULT_COORDINATOR_INTERVAL_S,  # 30 minutes - more frequent
    max_execution_time_s=180,
    enabled=True,
    checks=[
        _create_check(
            "check_bot_team_health",
            "Monitor health status of all specialist bots",
            priority="critical",
            max_duration_s=60.0,
            config={
                "max_silence_minutes": 120
            }
        ),
        _create_check(
            "monitor_task_delegation_queue",
            "Check for stalled or failed task delegations",
            priority="high",
            max_duration_s=60.0,
            config={
                "max_wait_hours": 4
            }
        ),
        _create_check(
            "review_inter_bot_communication",
            "Check for communication failures between bots",
            priority="high",
            max_duration_s=45.0,
            config={
                "lookback_hours": 2
            }
        ),
        _create_check(
            "check_resource_utilization",
            "Monitor system resource usage across bot team",
            priority="normal",
            max_duration_s=45.0,
            config={
                "thresholds": {
                    "cpu_percent": 80,
                    "memory_percent": 85,
                    "api_rate_percent": 70,
                    "storage_percent": 90
                }
            }
        ),
    ],
    parallel_checks=True,
    max_concurrent_checks=4,
    stop_on_first_failure=False,
    notify_on_failure=True,
    notification_channels=["admin"],
    retain_history_count=100
)


# Map of bot names to default configs
DEFAULT_CONFIGS: Dict[str, CrewRoutinesConfig] = {
    "researcher": RESEARCHER_CONFIG,
    "coder": CODER_CONFIG,
    "social": SOCIAL_CONFIG,
    "auditor": AUDITOR_CONFIG,
    "creative": CREATIVE_CONFIG,
    "coordinator": COORDINATOR_CONFIG,
}


# =============================================================================
# Configuration Loading
# =============================================================================

def load_config_from_file(config_path: Path) -> Optional[Dict[str, Any]]:
    """Load crew routines configuration from YAML or JSON file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dict or None if file doesn't exist
    """
    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r') as f:
            if config_path.suffix in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif config_path.suffix == '.json':
                return json.load(f)
            else:
                # Try YAML first, then JSON
                try:
                    return yaml.safe_load(f)
                except Exception:
                    f.seek(0)
                    return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load crew routines config from {config_path}: {e}")
        return None


def merge_config(base: CrewRoutinesConfig, override: Dict[str, Any]) -> CrewRoutinesConfig:
    """Merge override settings into base configuration.

    Args:
        base: Base configuration
        override: Override settings from file

    Returns:
        Merged configuration
    """
    # Create a copy
    merged = CrewRoutinesConfig(
        bot_name=base.bot_name,
        interval_s=override.get('interval_s', base.interval_s),
        max_execution_time_s=override.get('max_execution_time_s', base.max_execution_time_s),
        enabled=override.get('enabled', base.enabled),
        checks=base.checks.copy(),  # Will update below
        parallel_checks=override.get('parallel_checks', base.parallel_checks),
        max_concurrent_checks=override.get('max_concurrent_checks', base.max_concurrent_checks),
        stop_on_first_failure=override.get('stop_on_first_failure', base.stop_on_first_failure),
        notify_on_failure=override.get('notify_on_failure', base.notify_on_failure),
        notify_on_success=override.get('notify_on_success', base.notify_on_success),
        notification_channels=override.get('notification_channels', base.notification_channels),
        log_level=override.get('log_level', base.log_level),
        retain_history_count=override.get('retain_history_count', base.retain_history_count)
    )

    # Update check configurations
    if 'checks' in override:
        check_overrides = {c['name']: c for c in override['checks'] if 'name' in c}

        updated_checks = []
        for check in merged.checks:
            if check.name in check_overrides:
                override_check = check_overrides[check.name]
                updated_checks.append(CheckDefinition(
                    name=check.name,
                    description=override_check.get('description', check.description),
                    priority=CheckPriority(override_check.get('priority', check.priority.value)),
                    max_duration_s=override_check.get('max_duration_s', check.max_duration_s),
                    retry_attempts=override_check.get('retry_attempts', check.retry_attempts),
                    dependencies=override_check.get('dependencies', check.dependencies),
                    enabled=override_check.get('enabled', check.enabled),
                    config={**check.config, **override_check.get('config', {})}
                ))
            else:
                updated_checks.append(check)

        merged.checks = updated_checks

    return merged


def get_bot_crew_routines_config(
    bot_name: str,
    config_dir: Optional[Path] = None,
    custom_overrides: Optional[Dict[str, Any]] = None
) -> CrewRoutinesConfig:
    """Get crew routines configuration for a bot.

    Loads default configuration and applies any overrides from:
    1. Configuration file (crew_routines.yaml or crew_routines.json)
    2. Custom overrides passed as parameter

    Args:
        bot_name: Name of the bot (researcher, coder, social, auditor, creative, coordinator)
        config_dir: Directory containing crew_routines.yaml/json (default: current dir)
        custom_overrides: Additional override settings

    Returns:
        Configured CrewRoutinesConfig for the bot

    Example:
        >>> config = get_bot_crew_routines_config("researcher")
        >>> print(f"Interval: {config.interval_s}s")

        >>> config = get_bot_crew_routines_config(
        ...     "social",
        ...     custom_overrides={"interval_s": 1800}  # 30 min
        ... )
    """
    # Get default config
    if bot_name not in DEFAULT_CONFIGS:
        logger.warning(f"Unknown bot '{bot_name}', using generic config")
        base_config = CrewRoutinesConfig(bot_name=bot_name)
    else:
        base_config = DEFAULT_CONFIGS[bot_name]

    # Load from file if exists
    if config_dir is None:
        config_dir = Path.cwd()

    for filename in ['crew_routines.yaml', 'crew_routines.yml', 'crew_routines.json']:
        config_file = config_dir / filename
        if config_file.exists():
            file_config = load_config_from_file(config_file)
            if file_config and bot_name in file_config:
                logger.info(f"Loading crew routines config for {bot_name} from {config_file}")
                base_config = merge_config(base_config, file_config[bot_name])
            break

    # Apply custom overrides
    if custom_overrides:
        base_config = merge_config(base_config, custom_overrides)

    return base_config


def get_all_crew_routines_configs(
    config_dir: Optional[Path] = None
) -> Dict[str, CrewRoutinesConfig]:
    """Get crew routines configurations for all bots.

    Args:
        config_dir: Directory containing configuration files

    Returns:
        Dict mapping bot names to their configurations
    """
    return {
        name: get_bot_crew_routines_config(name, config_dir)
        for name in DEFAULT_CONFIGS.keys()
    }


def save_crew_routines_config(
    config: CrewRoutinesConfig,
    config_path: Path,
    format: str = "yaml"
) -> None:
    """Save crew routines configuration to file.

    Args:
        config: Configuration to save
        config_path: Path to save to
        format: 'yaml' or 'json'

    Example:
        >>> config = CrewRoutinesConfig(bot_name="custom")
        >>> save_crew_routines_config(config, Path("config.yaml"))
    """
    config_dict = {
        config.bot_name: {
            "interval_s": config.interval_s,
            "max_execution_time_s": config.max_execution_time_s,
            "enabled": config.enabled,
            "parallel_checks": config.parallel_checks,
            "max_concurrent_checks": config.max_concurrent_checks,
            "stop_on_first_failure": config.stop_on_first_failure,
            "notify_on_failure": config.notify_on_failure,
            "notify_on_success": config.notify_on_success,
            "notification_channels": config.notification_channels,
            "log_level": config.log_level,
            "retain_history_count": config.retain_history_count,
            "checks": [
                {
                    "name": c.name,
                    "description": c.description,
                    "priority": c.priority.value,
                    "max_duration_s": c.max_duration_s,
                    "retry_attempts": c.retry_attempts,
                    "dependencies": c.dependencies,
                    "enabled": c.enabled,
                    "config": c.config
                }
                for c in config.checks
            ]
        }
    }

    with open(config_path, 'w') as f:
        if format in ['yaml', 'yml']:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        else:
            json.dump(config_dict, f, indent=2)

    logger.info(f"Saved crew routines config to {config_path}")


__all__ = [
    # Default configs
    "RESEARCHER_CONFIG",
    "CODER_CONFIG",
    "SOCIAL_CONFIG",
    "AUDITOR_CONFIG",
    "CREATIVE_CONFIG",
    "COORDINATOR_CONFIG",
    "DEFAULT_CONFIGS",

    # Functions
    "get_bot_crew_routines_config",
    "get_all_crew_routines_configs",
    "load_config_from_file",
    "save_crew_routines_config",
    "merge_config",
]
