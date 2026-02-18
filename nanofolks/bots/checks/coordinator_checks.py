"""Heartbeat checks for CoordinatorBot (Orchestrator).

These checks run every 30 minutes (by default, more frequent than specialists)
to monitor bot team health, task delegation, communication, and resource usage.

Usage:
    Automatically registered when CoordinatorBot initializes.
"""

from datetime import datetime
from typing import Any, Dict

from loguru import logger

from nanofolks.heartbeat.check_registry import register_check


@register_check(
    name="check_bot_team_health",
    description="Monitor health status of all specialist bots",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["coordination"]
)
async def check_bot_team_health(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check health status of all registered specialist bots.

    Monitors bot heartbeats, last activity, error rates, and resource
    usage. Escalates if any bot appears unhealthy or unresponsive.

    Args:
        bot: The CoordinatorBot instance
        config: Check configuration

    Returns:
        Dict with team health status
    """
    try:
        max_silence_minutes = config.get("max_silence_minutes", 120)

        if hasattr(bot, 'get_bot_health_status'):
            health_data = await bot.get_bot_health_status()
        else:
            return {
                "success": True,
                "message": "Bot health monitoring not available",
                "bots_checked": 0
            }

        now = datetime.now()
        unhealthy = []
        silent = []
        degraded = []
        healthy = []

        for bot_info in health_data:
            bot_id = getattr(bot_info, 'bot_id', 'unknown')
            bot_name = getattr(bot_info, 'bot_name', 'Unknown Bot')
            status = getattr(bot_info, 'status', 'unknown')
            last_heartbeat = getattr(bot_info, 'last_heartbeat', None)
            error_rate = getattr(bot_info, 'error_rate', 0.0)

            # Calculate silence time
            if last_heartbeat:
                if isinstance(last_heartbeat, str):
                    try:
                        last_heartbeat = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
                    except Exception:
                        last_heartbeat = now

                silence_minutes = (now - last_heartbeat).total_seconds() / 60
            else:
                silence_minutes = max_silence_minutes + 1  # Force silent if no heartbeat

            bot_status = {
                "bot_id": bot_id,
                "bot_name": bot_name,
                "status": status,
                "silence_minutes": round(silence_minutes, 1),
                "error_rate": error_rate
            }

            # Categorize health
            if status == "unhealthy" or error_rate > 0.5:
                unhealthy.append(bot_status)
            elif silence_minutes > max_silence_minutes:
                silent.append(bot_status)
            elif status == "degraded" or error_rate > 0.1:
                degraded.append(bot_status)
            else:
                healthy.append(bot_status)

        # Escalate critical issues
        if unhealthy or silent:
            if hasattr(bot, 'escalate_to_admin'):
                try:
                    await bot.escalate_to_admin(
                        f"Bot team health issues: {len(unhealthy)} unhealthy, {len(silent)} silent",
                        priority="critical",
                        data={
                            "unhealthy": unhealthy,
                            "silent": silent,
                            "degraded": degraded,
                            "healthy_count": len(healthy)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif degraded:
            if hasattr(bot, 'notify_team'):
                try:
                    await bot.notify_team(
                        f"{len(degraded)} bots showing degraded performance",
                        data={"degraded": degraded}
                    )
                    action = "notified"
                except Exception as e:
                    logger.error(f"Failed to notify: {e}")
                    action = "logged"
            else:
                action = "logged"
        else:
            action = None

        return {
            "success": len(unhealthy) == 0 and len(silent) == 0,
            "bots_checked": len(health_data),
            "healthy": len(healthy),
            "degraded": len(degraded),
            "unhealthy": len(unhealthy),
            "silent": len(silent),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_bot_team_health: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="monitor_task_delegation_queue",
    description="Check for stalled or failed task delegations",
    priority="high",
    max_duration_s=60.0,
    bot_domains=["coordination"]
)
async def monitor_task_delegation_queue(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor task delegation queue for stalled or failed tasks.

    Checks pending tasks, failed delegations, and tasks that have
    been waiting too long for assignment or completion.

    Args:
        bot: The CoordinatorBot instance
        config: Check configuration

    Returns:
        Dict with delegation queue status
    """
    try:
        max_wait_hours = config.get("max_wait_hours", 4)

        if hasattr(bot, 'get_delegation_queue'):
            queue = await bot.get_delegation_queue()
        else:
            return {
                "success": True,
                "message": "Delegation queue not available",
                "tasks_checked": 0
            }

        now = datetime.now()

        stalled = []
        failed = []
        pending = []

        for task in queue:
            task_id = getattr(task, 'id', 'unknown')
            task_title = getattr(task, 'title', 'Untitled Task')
            status = getattr(task, 'status', 'unknown')
            created_at = getattr(task, 'created_at', now)

            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except Exception:
                    created_at = now

            hours_pending = (now - created_at).total_seconds() / 3600

            task_data = {
                "task_id": task_id,
                "title": task_title,
                "status": status,
                "hours_pending": round(hours_pending, 1),
                "assigned_to": getattr(task, 'assigned_to', 'unassigned')
            }

            if status == "failed":
                failed.append(task_data)
            elif hours_pending > max_wait_hours:
                stalled.append(task_data)
            elif status in ["pending", "assigned"]:
                pending.append(task_data)

        if stalled or failed:
            if hasattr(bot, 'escalate_to_admin'):
                try:
                    await bot.escalate_to_admin(
                        f"Task delegation issues: {len(stalled)} stalled, {len(failed)} failed",
                        priority="high" if failed else "normal",
                        data={
                            "stalled": stalled[:10],
                            "failed": failed[:10],
                            "pending_count": len(pending)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        else:
            action = None

        return {
            "success": len(failed) == 0 and len(stalled) == 0,
            "tasks_checked": len(queue),
            "pending": len(pending),
            "stalled": len(stalled),
            "failed": len(failed),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in monitor_task_delegation_queue: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="review_inter_bot_communication",
    description="Check for communication failures between bots",
    priority="high",
    max_duration_s=45.0,
    bot_domains=["coordination"]
)
async def review_inter_bot_communication(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Review inter-bot communication health.

    Checks message delivery success rates, response times, and
    detects communication failures or timeouts between bots.

    Args:
        bot: The CoordinatorBot instance
        config: Check configuration

    Returns:
        Dict with communication health status
    """
    try:
        lookback_hours = config.get("lookback_hours", 2)

        if hasattr(bot, 'get_communication_metrics'):
            metrics = await bot.get_communication_metrics(hours=lookback_hours)
        else:
            return {
                "success": True,
                "message": "Communication metrics not available",
                "channels_checked": 0
            }

        failed_channels = []
        slow_channels = []
        healthy_channels = []

        for channel in getattr(metrics, 'channels', []):
            channel_name = getattr(channel, 'name', 'unknown')
            success_rate = getattr(channel, 'success_rate', 1.0)
            avg_response_ms = getattr(channel, 'avg_response_ms', 0)
            failed_count = getattr(channel, 'failed_count', 0)

            channel_data = {
                "channel": channel_name,
                "success_rate": success_rate,
                "avg_response_ms": avg_response_ms,
                "failed_count": failed_count
            }

            if success_rate < 0.5 or failed_count > 10:
                failed_channels.append(channel_data)
            elif success_rate < 0.9 or avg_response_ms > 5000:
                slow_channels.append(channel_data)
            else:
                healthy_channels.append(channel_data)

        if failed_channels:
            if hasattr(bot, 'escalate_to_admin'):
                try:
                    await bot.escalate_to_admin(
                        f"Inter-bot communication failures: {len(failed_channels)} channels down",
                        priority="critical",
                        data={
                            "failed": failed_channels,
                            "slow": slow_channels[:5]
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif slow_channels:
            if hasattr(bot, 'notify_team'):
                try:
                    await bot.notify_team(
                        f"{len(slow_channels)} inter-bot channels showing degraded performance",
                        data={"slow_channels": slow_channels}
                    )
                    action = "notified"
                except Exception as e:
                    logger.error(f"Failed to notify: {e}")
                    action = "logged"
            else:
                action = "logged"
        else:
            action = None

        return {
            "success": len(failed_channels) == 0,
            "channels_checked": len(getattr(metrics, 'channels', [])),
            "healthy": len(healthy_channels),
            "slow": len(slow_channels),
            "failed": len(failed_channels),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in review_inter_bot_communication: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_resource_utilization",
    description="Monitor system resource usage across bot team",
    priority="normal",
    max_duration_s=45.0,
    bot_domains=["coordination"]
)
async def check_resource_utilization(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check resource utilization across the bot team.

    Monitors CPU, memory, API rate limits, and storage usage.
    Alerts on high utilization or approaching limits.

    Args:
        bot: The CoordinatorBot instance
        config: Check configuration

    Returns:
        Dict with resource utilization status
    """
    try:
        thresholds = config.get("thresholds", {
            "cpu_percent": 80,
            "memory_percent": 85,
            "api_rate_percent": 70,
            "storage_percent": 90
        })

        if hasattr(bot, 'get_resource_metrics'):
            resources = await bot.get_resource_metrics()
        else:
            return {
                "success": True,
                "message": "Resource metrics not available",
                "bots_checked": 0
            }

        high_utilization = []
        critical_resources = []

        for resource in getattr(resources, 'bots', []):
            bot_name = getattr(resource, 'bot_name', 'unknown')
            metrics = {
                "cpu": getattr(resource, 'cpu_percent', 0),
                "memory": getattr(resource, 'memory_percent', 0),
                "api_rate": getattr(resource, 'api_rate_percent', 0),
                "storage": getattr(resource, 'storage_percent', 0)
            }

            issues = []

            if metrics["cpu"] > thresholds["cpu_percent"]:
                issues.append(f"CPU at {metrics['cpu']}%")
            if metrics["memory"] > thresholds["memory_percent"]:
                issues.append(f"Memory at {metrics['memory']}%")
            if metrics["api_rate"] > thresholds["api_rate_percent"]:
                issues.append(f"API rate at {metrics['api_rate']}%")
            if metrics["storage"] > thresholds["storage_percent"]:
                issues.append(f"Storage at {metrics['storage']}%")

            if issues:
                # Determine severity
                if any(metrics[k] > thresholds[k] + 10 for k in metrics):
                    critical_resources.append({
                        "bot": bot_name,
                        "issues": issues,
                        "metrics": metrics
                    })
                else:
                    high_utilization.append({
                        "bot": bot_name,
                        "issues": issues,
                        "metrics": metrics
                    })

        if critical_resources:
            if hasattr(bot, 'escalate_to_admin'):
                try:
                    await bot.escalate_to_admin(
                        f"Critical resource utilization: {len(critical_resources)} bots",
                        priority="high",
                        data={"critical": critical_resources[:5]}
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif high_utilization:
            if hasattr(bot, 'notify_team'):
                try:
                    await bot.notify_team(
                        f"{len(high_utilization)} bots showing high resource utilization",
                        data={"high_utilization": high_utilization[:5]}
                    )
                    action = "notified"
                except Exception as e:
                    logger.error(f"Failed to notify: {e}")
                    action = "logged"
            else:
                action = "logged"
        else:
            action = None

        return {
            "success": len(critical_resources) == 0,
            "bots_checked": len(getattr(resources, 'bots', [])),
            "normal": len(getattr(resources, 'bots', [])) - len(high_utilization) - len(critical_resources),
            "high": len(high_utilization),
            "critical": len(critical_resources),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_resource_utilization: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


__all__ = [
    "check_bot_team_health",
    "monitor_task_delegation_queue",
    "review_inter_bot_communication",
    "check_resource_utilization",
]
