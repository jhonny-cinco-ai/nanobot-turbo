"""CrewRoutines checks for ResearcherBot (Navigator).

These checks are designed to run automatically every 60 minutes (by default)
to monitor research-related tasks, data sources, and deadlines.

Usage:
    These checks are automatically registered when the ResearcherBot
    initializes its crew_routines service. They can also be used standalone:

    from nanofolks.bots.checks.researcher_checks import check_data_sources

    result = await check_data_sources(bot_instance, config)
"""

from datetime import datetime
from typing import Any, Dict

from loguru import logger

from nanofolks.crew_routines.check_registry import register_check


@register_check(
    name="monitor_data_sources",
    description="Check monitored data sources for updates",
    priority="high",
    max_duration_s=120.0,
    bot_domains=["research"],
    sources=[]  # Configurable list of sources
)
async def monitor_data_sources(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check configured data sources for new updates.

    This check monitors configured data sources (APIs, feeds, databases)
    for new content since the last check. When updates are found, it
    notifies the coordinator team.

    Args:
        bot: The bot instance (ResearcherBot)
        config: Check configuration including 'sources' list

    Returns:
        Dict with success status, update counts, and actions taken
    """
    sources = config.get("sources", [])

    if not sources:
        logger.debug(f"[{bot.role_card.bot_name}] No data sources configured")
        return {
            "success": True,
            "message": "No data sources configured",
            "sources_checked": 0,
            "updates_found": 0
        }

    updates_found = []
    sources_checked = 0

    for source in sources:
        try:
            # Get last check time from bot's private memory
            last_check_key = f"last_source_check_{source}"
            last_check = bot.private_memory.get(last_check_key, 0)

            # Check source for updates
            logger.debug(f"[{bot.role_card.bot_name}] Checking source: {source}")

            # This would be implemented by the actual bot
            # For now, we simulate the check
            if hasattr(bot, 'check_source_updates'):
                new_items = await bot.check_source_updates(source, since=last_check)
            else:
                # Simulate - in real implementation, this would query the source
                new_items = []

            sources_checked += 1

            if new_items:
                updates_found.append({
                    "source": source,
                    "new_items": len(new_items),
                    "sample": new_items[:3] if isinstance(new_items, list) else None
                })

                # Update memory with current timestamp
                bot.private_memory[last_check_key] = datetime.now().timestamp()

                logger.info(
                    f"[{bot.role_card.bot_name}] Found {len(new_items)} updates in {source}"
                )

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error checking source {source}: {e}")

    # Notify if updates found
    if updates_found:
        notification_msg = f"Found updates in {len(updates_found)} data sources"

        # Try to notify coordinator
        if hasattr(bot, 'notify_coordinator'):
            try:
                await bot.notify_coordinator(
                    notification_msg,
                    priority="normal",
                    data={"updates": updates_found}
                )
            except Exception as e:
                logger.error(f"Failed to notify coordinator: {e}")

        return {
            "success": True,
            "sources_checked": sources_checked,
            "updates_found": len(updates_found),
            "action_taken": "notified_team",
            "details": updates_found
        }

    return {
        "success": True,
        "sources_checked": sources_checked,
        "updates_found": 0,
        "action_taken": None
    }


@register_check(
    name="track_market_trends",
    description="Analyze market trends and detect significant changes",
    priority="normal",
    max_duration_s=180.0,
    bot_domains=["research"],
    markets=[]  # Configurable markets to track
)
async def track_market_trends(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Track market trends and alert on significant changes.

    Monitors configured markets for significant price movements,
    volume changes, or sentiment shifts. High-confidence changes
    are escalated to the coordinator for immediate attention.

    Args:
        bot: The bot instance (ResearcherBot)
        config: Check configuration including 'markets' list

    Returns:
        Dict with analysis results and any escalations
    """
    markets = config.get("markets", [])

    if not markets:
        logger.debug(f"[{bot.role_card.bot_name}] No markets configured for tracking")
        return {
            "success": True,
            "message": "No markets configured",
            "markets_analyzed": 0,
            "significant_changes": 0
        }

    significant_changes = []
    markets_analyzed = 0

    for market in markets:
        try:
            logger.debug(f"[{bot.role_card.bot_name}] Analyzing market: {market}")

            # This would call actual market analysis
            if hasattr(bot, 'analyze_market_trend'):
                trend = await bot.analyze_market_trend(market)
            else:
                # Simulate trend data
                trend = MockTrend(significant_change=False)

            markets_analyzed += 1

            if trend.significant_change:
                significant_changes.append({
                    "market": market,
                    "change_percent": getattr(trend, 'change_percent', 0),
                    "direction": getattr(trend, 'direction', 'unknown'),
                    "confidence": getattr(trend, 'confidence', 0.5),
                    "volume_change": getattr(trend, 'volume_change', 0)
                })

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error analyzing market {market}: {e}")

    # Handle significant changes
    if significant_changes:
        # Filter high confidence changes for escalation
        high_confidence = [
            c for c in significant_changes
            if c.get("confidence", 0) > 0.8
        ]

        if high_confidence:
            escalation_msg = f"Significant market changes detected: {len(high_confidence)} markets"

            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        escalation_msg,
                        priority="high",
                        data={"changes": high_confidence}
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "detected"
            else:
                action = "detected"
        else:
            action = "logged"

        return {
            "success": True,
            "markets_analyzed": markets_analyzed,
            "significant_changes": len(significant_changes),
            "high_confidence_changes": len(high_confidence),
            "action_taken": action,
            "changes": significant_changes
        }

    return {
        "success": True,
        "markets_analyzed": markets_analyzed,
        "significant_changes": 0,
        "action_taken": None
    }


@register_check(
    name="monitor_research_deadlines",
    description="Check for approaching research deadlines",
    priority="critical",
    max_duration_s=30.0,
    bot_domains=["research"],
    warning_days=3
)
async def monitor_research_deadlines(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor research project deadlines and alert on approaching dates.

    Checks all active research projects and identifies those with
    deadlines approaching within the warning period. Critical deadlines
    (less than 1 day) are escalated immediately.

    Args:
        bot: The bot instance (ResearcherBot)
        config: Check configuration including 'warning_days'

    Returns:
        Dict with deadline information and notifications sent
    """
    warning_days = config.get("warning_days", 3)

    # Get active research projects
    try:
        if hasattr(bot, 'get_active_research_projects'):
            projects = await bot.get_active_research_projects()
        else:
            # Simulate - in real implementation, query project database
            projects = []
    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error getting research projects: {e}")
        return {
            "success": False,
            "error": str(e),
            "approaching_deadlines": 0
        }

    approaching_deadlines = []
    now = datetime.now()

    for project in projects:
        try:
            if hasattr(project, 'deadline') and project.deadline:
                deadline = project.deadline
                if isinstance(deadline, str):
                    deadline = datetime.fromisoformat(deadline)

                days_until = (deadline - now).days

                if days_until <= warning_days and days_until >= 0:
                    urgency = "critical" if days_until < 1 else "high" if days_until < 3 else "medium"

                    approaching_deadlines.append({
                        "project": getattr(project, 'name', 'Unknown'),
                        "project_id": getattr(project, 'id', None),
                        "deadline": deadline.isoformat(),
                        "days_remaining": days_until,
                        "urgency": urgency
                    })

        except Exception as e:
            logger.warning(f"[{bot.role_card.bot_name}] Error processing project deadline: {e}")

    # Sort by urgency (most urgent first)
    approaching_deadlines.sort(key=lambda x: x["days_remaining"])

    # Notify if deadlines approaching
    if approaching_deadlines:
        critical_count = sum(1 for d in approaching_deadlines if d["urgency"] == "critical")

        notification_msg = f"{len(approaching_deadlines)} research deadlines approaching"
        if critical_count > 0:
            notification_msg += f" ({critical_count} critical)"

        if hasattr(bot, 'notify_coordinator'):
            try:
                priority = "critical" if critical_count > 0 else "high"
                await bot.notify_coordinator(
                    notification_msg,
                    priority=priority,
                    data={"deadlines": approaching_deadlines}
                )
                action = "notified_team"
            except Exception as e:
                logger.error(f"Failed to notify coordinator: {e}")
                action = "detected"
        else:
            action = "detected"

        return {
            "success": True,
            "projects_checked": len(projects),
            "approaching_deadlines": len(approaching_deadlines),
            "critical_deadlines": critical_count,
            "action_taken": action,
            "deadlines": approaching_deadlines
        }

    return {
        "success": True,
        "projects_checked": len(projects),
        "approaching_deadlines": 0,
        "action_taken": None
    }


@register_check(
    name="update_competitor_tracking",
    description="Update competitor tracking data",
    priority="normal",
    max_duration_s=300.0,
    bot_domains=["research"],
    competitors=[]  # Configurable competitor list
)
async def update_competitor_tracking(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Update competitor tracking and report significant changes.

    Monitors configured competitors for product updates, pricing changes,
    announcements, or other significant activities. Changes are summarized
    and reported to the team.

    Args:
        bot: The bot instance (ResearcherBot)
        config: Check configuration including 'competitors' list

    Returns:
        Dict with competitor update summary
    """
    competitors = config.get("competitors", [])

    if not competitors:
        logger.debug(f"[{bot.role_card.bot_name}] No competitors configured for tracking")
        return {
            "success": True,
            "message": "No competitors configured",
            "competitors_checked": 0,
            "updates_found": 0
        }

    updates = []
    competitors_checked = 0

    for competitor in competitors:
        try:
            logger.debug(f"[{bot.role_card.bot_name}] Checking competitor: {competitor}")

            # Check for updates
            if hasattr(bot, 'check_competitor_updates'):
                changes = await bot.check_competitor_updates(competitor)
            else:
                # Simulate
                changes = []

            competitors_checked += 1

            if changes:
                updates.append({
                    "competitor": competitor,
                    "changes_count": len(changes) if isinstance(changes, list) else 1,
                    "changes": changes if isinstance(changes, list) else [changes]
                })

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error checking competitor {competitor}: {e}")

    # Notify if updates found
    if updates:
        notification_msg = f"Competitor updates detected for {len(updates)} competitors"

        if hasattr(bot, 'notify_coordinator'):
            try:
                await bot.notify_coordinator(
                    notification_msg,
                    priority="normal",
                    data={"updates": updates}
                )
                action = "notified_team"
            except Exception as e:
                logger.error(f"Failed to notify coordinator: {e}")
                action = "detected"
        else:
            action = "detected"

        return {
            "success": True,
            "competitors_checked": competitors_checked,
            "updates_found": len(updates),
            "action_taken": action,
            "details": updates
        }

    return {
        "success": True,
        "competitors_checked": competitors_checked,
        "updates_found": 0,
        "action_taken": None
    }


# Mock classes for simulation (remove in production)
class MockTrend:
    """Mock trend data for testing."""
    def __init__(self, significant_change=False):
        self.significant_change = significant_change
        self.change_percent = 5.0
        self.direction = "up"
        self.confidence = 0.9
        self.volume_change = 10.0


__all__ = [
    "monitor_data_sources",
    "track_market_trends",
    "monitor_research_deadlines",
    "update_competitor_tracking",
]
