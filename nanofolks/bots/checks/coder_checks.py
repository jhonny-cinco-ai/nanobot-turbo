"""CrewRoutines checks for CoderBot (Gunner).

These checks run every 60 minutes (by default) to monitor development
workflows, CI/CD pipelines, security issues, and repository health.

Usage:
    Automatically registered when CoderBot initializes.
    Can be used standalone if needed.
"""

from datetime import datetime
from typing import Any, Dict

from loguru import logger

from nanofolks.crew_routines.check_registry import register_check


@register_check(
    name="check_github_issues",
    description="Check GitHub repositories for new issues",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["development"],
    repositories=[]  # Configurable repos
)
async def check_github_issues(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check configured GitHub repositories for new issues.

    Monitors repositories for new issues, with special attention to
    critical and high-priority issues that need immediate action.

    Args:
        bot: The CoderBot instance
        config: Configuration with repositories list

    Returns:
        Dict with issue counts and critical findings
    """
    repositories = config.get("repositories", [])

    if not repositories:
        logger.debug(f"[{bot.role_card.bot_name}] No repositories configured")
        return {
            "success": True,
            "message": "No repositories configured",
            "repositories_checked": 0,
            "total_issues": 0
        }

    total_issues = 0
    critical_issues = []

    for repo in repositories:
        try:
            logger.debug(f"[{bot.role_card.bot_name}] Checking repo: {repo}")

            # Get last check time
            last_check_key = f"last_issue_check_{repo.replace('/', '_')}"
            last_check = bot.private_memory.get(last_check_key)

            # Check for issues
            if hasattr(bot, 'check_repository_issues'):
                issues = await bot.check_repository_issues(repo, since=last_check)
            else:
                issues = []

            total_issues += len(issues)

            # Identify critical issues
            critical = [
                i for i in issues
                if getattr(i, 'priority', '') in ["critical", "high"] or
                getattr(i, 'labels', []).count("critical") > 0
            ]

            if critical:
                critical_issues.append({
                    "repository": repo,
                    "critical_count": len(critical),
                    "issues": [
                        {
                            "number": getattr(issue, 'number', 0),
                            "title": getattr(issue, 'title', 'Unknown'),
                            "url": getattr(issue, 'url', '')
                        }
                        for issue in critical[:5]  # Top 5
                    ]
                })

            # Update memory
            bot.private_memory[last_check_key] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error checking repo {repo}: {e}")

    # Escalate critical issues
    if critical_issues:
        escalation_msg = f"Critical GitHub issues detected in {len(critical_issues)} repositories"

        if hasattr(bot, 'escalate_to_coordinator'):
            try:
                await bot.escalate_to_coordinator(
                    escalation_msg,
                    priority="critical",
                    data={"critical_issues": critical_issues}
                )
                action = "escalated"
            except Exception as e:
                logger.error(f"Failed to escalate: {e}")
                action = "detected"
        else:
            action = "detected"

        return {
            "success": True,
            "repositories_checked": len(repositories),
            "total_issues": total_issues,
            "critical_issues": sum(i["critical_count"] for i in critical_issues),
            "action_taken": action,
            "details": critical_issues
        }

    return {
        "success": True,
        "repositories_checked": len(repositories),
        "total_issues": total_issues,
        "critical_issues": 0,
        "action_taken": None
    }


@register_check(
    name="monitor_build_status",
    description="Monitor CI/CD build and test status",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["development"]
)
async def monitor_build_status(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor build pipelines and report failures.

    Checks CI/CD pipelines for failed builds, tests, or deployments.
    Failed builds are escalated immediately with details.

    Args:
        bot: The CoderBot instance
        config: Check configuration

    Returns:
        Dict with build status and any failures
    """
    try:
        # Get build status
        if hasattr(bot, 'check_build_status'):
            build_status = await bot.check_build_status()
        else:
            # Simulate
            build_status = MockBuildStatus(failed=False)

        if build_status.failed:
            failed_builds = [
                b for b in getattr(build_status, 'builds', [])
                if getattr(b, 'status', '') == "failed"
            ]

            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Build failures detected: {len(failed_builds)} builds failed",
                        priority="high",
                        data={
                            "failed_builds": [
                                {
                                    "pipeline": getattr(b, 'pipeline', 'Unknown'),
                                    "failed_tests": getattr(b, 'failed_tests', 0),
                                    "error_summary": getattr(b, 'error_summary', '')
                                }
                                for b in failed_builds
                            ]
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "detected"
            else:
                action = "detected"

            return {
                "success": False,
                "builds_checked": len(getattr(build_status, 'builds', [])),
                "failed_builds": len(failed_builds),
                "action_taken": action,
                "message": f"{len(failed_builds)} builds failed"
            }

        return {
            "success": True,
            "builds_checked": len(getattr(build_status, 'builds', [])),
            "all_passing": True,
            "message": "All builds passing"
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error checking build status: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="security_vulnerability_scan",
    description="Scan for security vulnerabilities in dependencies",
    priority="critical",
    max_duration_s=120.0,
    bot_domains=["development"]
)
async def security_vulnerability_scan(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Scan project dependencies for known security vulnerabilities.

    Runs security scan on all dependencies. Critical vulnerabilities
    are escalated immediately for action.

    Args:
        bot: The CoderBot instance
        config: Check configuration

    Returns:
        Dict with vulnerability scan results
    """
    try:
        # Run security scan
        if hasattr(bot, 'run_security_scan'):
            scan_results = await bot.run_security_scan()
        else:
            scan_results = MockScanResults()

        vulnerabilities = getattr(scan_results, 'vulnerabilities', [])

        # Categorize by severity
        critical_severity = [
            v for v in vulnerabilities
            if getattr(v, 'severity', '') == "critical"
        ]
        high_severity = [
            v for v in vulnerabilities
            if getattr(v, 'severity', '') == "high"
        ]

        # Handle critical vulnerabilities
        if critical_severity:
            escalation_msg = f"CRITICAL: {len(critical_severity)} security vulnerabilities found"

            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        escalation_msg,
                        priority="critical",
                        data={
                            "critical_vulnerabilities": [
                                {
                                    "package": getattr(v, 'package', 'Unknown'),
                                    "cve": getattr(v, 'cve_id', 'N/A'),
                                    "severity": getattr(v, 'severity', 'critical'),
                                    "fixed_version": getattr(v, 'fixed_version', 'Unknown')
                                }
                                for v in critical_severity[:10]  # Top 10
                            ]
                        }
                    )
                    action = "escalated_critical"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "detected"
            else:
                action = "detected"

            return {
                "success": False,
                "vulnerabilities_found": len(vulnerabilities),
                "critical": len(critical_severity),
                "high": len(high_severity),
                "action_taken": action
            }

        # Handle high severity (notify but don't escalate)
        if high_severity:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"{len(high_severity)} high-severity vulnerabilities found",
                        priority="high",
                        data={"vulnerabilities": high_severity[:5]}
                    )
                    action = "notified"
                except Exception as e:
                    logger.error(f"Failed to notify: {e}")
                    action = "detected"
            else:
                action = "detected"
        else:
            action = None

        return {
            "success": True,
            "vulnerabilities_found": len(vulnerabilities),
            "critical": len(critical_severity),
            "high": len(high_severity),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error running security scan: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_dependency_updates",
    description="Check for available dependency updates",
    priority="normal",
    max_duration_s=60.0,
    bot_domains=["development"]
)
async def check_dependency_updates(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check for outdated dependencies and suggest updates.

    Scans project dependencies for available updates, focusing on
    significant updates (major/minor versions or security fixes).

    Args:
        bot: The CoderBot instance
        config: Check configuration

    Returns:
        Dict with available updates
    """
    try:
        if hasattr(bot, 'check_dependency_updates'):
            updates = await bot.check_dependency_updates()
        else:
            updates = []

        # Filter to significant updates
        significant = [
            u for u in updates
            if getattr(u, 'update_type', '') in ["major", "minor"] or
            getattr(u, 'security_fix', False)
        ]

        if significant:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"{len(significant)} significant dependency updates available",
                        data={
                            "updates": [
                                {
                                    "package": getattr(u, 'package', 'Unknown'),
                                    "current": getattr(u, 'current_version', ''),
                                    "latest": getattr(u, 'latest_version', ''),
                                    "type": getattr(u, 'update_type', 'patch')
                                }
                                for u in significant[:10]
                            ]
                        }
                    )
                    action = "notified"
                except Exception as e:
                    logger.error(f"Failed to notify: {e}")
                    action = "detected"
            else:
                action = "detected"
        else:
            action = None

        return {
            "success": True,
            "dependencies_checked": len(updates),
            "updates_available": len(updates),
            "significant_updates": len(significant),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error checking dependencies: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


# Mock classes for simulation
class MockBuildStatus:
    def __init__(self, failed=False):
        self.failed = failed
        self.builds = []

class MockScanResults:
    def __init__(self):
        self.vulnerabilities = []


__all__ = [
    "check_github_issues",
    "monitor_build_status",
    "security_vulnerability_scan",
    "check_dependency_updates",
]
