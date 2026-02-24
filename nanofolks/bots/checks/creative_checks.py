"""CrewRoutines checks for CreativeBot (Design).

These checks run every 60 minutes (by default) to monitor design assets,
creative deadlines, brand consistency, and content approval queues.

Usage:
    Automatically registered when CreativeBot initializes.
"""

from datetime import datetime
from typing import Any, Dict

from loguru import logger

from nanofolks.crew_routines.check_registry import register_check


@register_check(
    name="check_design_asset_status",
    description="Monitor design asset health and detect outdated files",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["creative"]
)
async def check_design_asset_status(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check design assets for outdated or missing files.

    Scans design systems, asset libraries, and project folders for
    outdated assets, missing files, or broken references.

    Args:
        bot: The CreativeBot instance
        config: Check configuration

    Returns:
        Dict with asset status and issues
    """
    try:
        max_age_days = config.get("max_age_days", 30)

        if hasattr(bot, 'scan_design_assets'):
            assets = await bot.scan_design_assets()
        else:
            return {
                "success": True,
                "message": "Asset scanning not available",
                "assets_checked": 0
            }

        outdated = []
        broken = []
        missing = []

        for asset in assets:
            asset_id = getattr(asset, 'id', 'unknown')
            asset_name = getattr(asset, 'name', 'Unnamed Asset')

            # Check if outdated
            last_modified = getattr(asset, 'last_modified', None)
            if last_modified:
                if isinstance(last_modified, str):
                    try:
                        last_modified = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                    except Exception:
                        last_modified = datetime.now()

                age_days = (datetime.now() - last_modified).days
                if age_days > max_age_days:
                    outdated.append({
                        "id": asset_id,
                        "name": asset_name,
                        "age_days": age_days,
                        "max_age": max_age_days
                    })

            # Check for broken references
            if getattr(asset, 'is_broken', False):
                broken.append({
                    "id": asset_id,
                    "name": asset_name,
                    "issue": "Broken reference"
                })

            # Check for missing required files
            if getattr(asset, 'is_missing', False):
                missing.append({
                    "id": asset_id,
                    "name": asset_name,
                    "expected_location": getattr(asset, 'expected_path', 'unknown')
                })

        issues = outdated + broken + missing

        if issues:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Design asset issues: {len(outdated)} outdated, {len(broken)} broken, {len(missing)} missing",
                        priority="high" if broken or missing else "normal",
                        data={
                            "outdated": outdated[:5],
                            "broken": broken[:5],
                            "missing": missing[:5]
                        }
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
            "success": len(broken) == 0 and len(missing) == 0,
            "assets_checked": len(assets),
            "outdated": len(outdated),
            "broken": len(broken),
            "missing": len(missing),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_design_asset_status: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="monitor_creative_deadlines",
    description="Track approaching creative project deadlines",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["creative"]
)
async def monitor_creative_deadlines(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor creative project deadlines and alert on approaching due dates.

    Tracks design projects, deliverables, and milestones. Alerts on
    overdue items and deadlines approaching within 24/48/72 hours.

    Args:
        bot: The CreativeBot instance
        config: Check configuration

    Returns:
        Dict with deadline status and alerts
    """
    try:
        if hasattr(bot, 'get_creative_projects'):
            projects = await bot.get_creative_projects()
        else:
            return {
                "success": True,
                "message": "Project tracking not available",
                "projects_checked": 0
            }

        now = datetime.now()

        overdue = []
        due_24h = []
        due_48h = []
        due_72h = []

        for project in projects:
            deadline = getattr(project, 'deadline', None)
            if not deadline:
                continue

            if isinstance(deadline, str):
                try:
                    deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                except Exception:
                    continue

            hours_remaining = (deadline - now).total_seconds() / 3600

            project_data = {
                "id": getattr(project, 'id', 'unknown'),
                "name": getattr(project, 'name', 'Unnamed'),
                "deadline": deadline.isoformat(),
                "hours_remaining": round(hours_remaining, 1),
                "status": getattr(project, 'status', 'unknown')
            }

            if hours_remaining < 0:
                overdue.append(project_data)
            elif hours_remaining <= 24:
                due_24h.append(project_data)
            elif hours_remaining <= 48:
                due_48h.append(project_data)
            elif hours_remaining <= 72:
                due_72h.append(project_data)

        # Determine priority
        if overdue:
            priority = "critical"
            message = f"URGENT: {len(overdue)} creative projects overdue"
        elif due_24h:
            priority = "high"
            message = f"{len(due_24h)} creative projects due within 24 hours"
        elif due_48h:
            priority = "normal"
            message = f"{len(due_48h)} creative projects due within 48 hours"
        elif due_72h:
            priority = "low"
            message = f"{len(due_72h)} creative projects due within 72 hours"
        else:
            priority = None
            message = None

        if message:
            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        message,
                        priority=priority,
                        data={
                            "overdue": overdue[:5],
                            "due_24h": due_24h[:5],
                            "due_48h": due_48h[:5],
                            "due_72h": due_72h[:5]
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
            "success": len(overdue) == 0,
            "projects_checked": len(projects),
            "overdue": len(overdue),
            "due_24h": len(due_24h),
            "due_48h": len(due_48h),
            "due_72h": len(due_72h),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in monitor_creative_deadlines: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="validate_brand_consistency",
    description="Check brand guidelines compliance across assets",
    priority="normal",
    max_duration_s=120.0,
    bot_domains=["creative"]
)
async def validate_brand_consistency(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate brand consistency across creative assets.

    Checks for brand guideline violations including colors, fonts,
    logos, tone of voice, and messaging consistency.

    Args:
        bot: The CreativeBot instance
        config: Check configuration

    Returns:
        Dict with brand consistency validation results
    """
    try:
        if hasattr(bot, 'validate_brand_guidelines'):
            violations = await bot.validate_brand_guidelines()
        else:
            return {
                "success": True,
                "message": "Brand validation not available",
                "assets_checked": 0
            }

        # Categorize violations
        critical = [v for v in violations if v.get('severity') == 'critical']
        major = [v for v in violations if v.get('severity') == 'major']
        minor = [v for v in violations if v.get('severity') == 'minor']

        if critical or major:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Brand consistency issues: {len(critical)} critical, {len(major)} major",
                        priority="high" if critical else "normal",
                        data={
                            "critical": critical[:5],
                            "major": major[:5],
                            "total_assets": len(violations)
                        }
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
            "success": len(critical) == 0,
            "violations_found": len(violations),
            "critical": len(critical),
            "major": len(major),
            "minor": len(minor),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in validate_brand_consistency: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_content_approval_queue",
    description="Monitor content awaiting approval and publishing",
    priority="high",
    max_duration_s=60.0,
    bot_domains=["creative"]
)
async def check_content_approval_queue(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check content items awaiting approval or review.

    Monitors approval queues for blog posts, graphics, videos, and
    other creative content. Alerts on items pending too long.

    Args:
        bot: The CreativeBot instance
        config: Check configuration

    Returns:
        Dict with approval queue status
    """
    try:
        max_wait_hours = config.get("max_wait_hours", 48)

        if hasattr(bot, 'get_pending_approvals'):
            pending = await bot.get_pending_approvals()
        else:
            return {
                "success": True,
                "message": "Approval queue not available",
                "items_pending": 0
            }

        now = datetime.now()

        stale = []
        urgent = []
        normal = []

        for item in pending:
            submitted = getattr(item, 'submitted_at', now)
            if isinstance(submitted, str):
                try:
                    submitted = datetime.fromisoformat(submitted.replace('Z', '+00:00'))
                except Exception:
                    submitted = now

            hours_waiting = (now - submitted).total_seconds() / 3600

            item_data = {
                "id": getattr(item, 'id', 'unknown'),
                "title": getattr(item, 'title', 'Untitled'),
                "type": getattr(item, 'content_type', 'unknown'),
                "submitted_by": getattr(item, 'submitted_by', 'unknown'),
                "hours_waiting": round(hours_waiting, 1)
            }

            if hours_waiting > max_wait_hours * 2:
                stale.append(item_data)
            elif hours_waiting > max_wait_hours:
                urgent.append(item_data)
            else:
                normal.append(item_data)

        if stale or urgent:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Content approval queue: {len(stale)} stale, {len(urgent)} urgent",
                        priority="high" if stale else "normal",
                        data={
                            "stale": stale[:5],
                            "urgent": urgent[:5],
                            "normal_count": len(normal)
                        }
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
            "success": len(stale) == 0,
            "total_pending": len(pending),
            "stale": len(stale),
            "urgent": len(urgent),
            "normal": len(normal),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_content_approval_queue: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


__all__ = [
    "check_design_asset_status",
    "monitor_creative_deadlines",
    "validate_brand_consistency",
    "check_content_approval_queue",
]
