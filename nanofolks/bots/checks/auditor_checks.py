"""CrewRoutines checks for AuditorBot (QA).

These checks run every 60 minutes (by default) to monitor code quality,
compliance issues, audit trails, and review queues.

Usage:
    Automatically registered when AuditorBot initializes.
"""

from datetime import datetime, timedelta
from typing import Any, Dict

from loguru import logger

from nanofolks.routines.crew.check_registry import register_check


@register_check(
    name="check_code_quality_scores",
    description="Monitor code quality metrics and flag declining trends",
    priority="high",
    max_duration_s=120.0,
    bot_domains=["quality"]
)
async def check_code_quality_scores(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check code quality metrics across monitored repositories.

    Analyzes linting scores, test coverage, complexity metrics, and
    documentation coverage. Flags repositories with declining quality.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with quality analysis results
    """
    try:
        # Get list of repositories to monitor
        repos = config.get("repositories", [])
        if hasattr(bot, 'get_monitored_repositories'):
            repos = await bot.get_monitored_repositories()

        if not repos:
            return {
                "success": True,
                "message": "No repositories configured for quality monitoring",
                "repositories_checked": 0
            }

        quality_issues = []

        for repo in repos:
            try:
                if hasattr(bot, 'analyze_code_quality'):
                    quality = await bot.analyze_code_quality(repo)
                else:
                    continue

                # Check for declining trends
                thresholds = config.get("thresholds", {
                    "coverage": 70,
                    "lint_score": 80,
                    "complexity": 15
                })

                issues = []

                if getattr(quality, 'test_coverage', 100) < thresholds["coverage"]:
                    issues.append(f"Test coverage below {thresholds['coverage']}%")

                if getattr(quality, 'lint_score', 100) < thresholds["lint_score"]:
                    issues.append(f"Lint score below {thresholds['lint_score']}")

                if getattr(quality, 'cyclomatic_complexity', 0) > thresholds["complexity"]:
                    issues.append(f"Complexity above {thresholds['complexity']}")

                if issues:
                    quality_issues.append({
                        "repository": repo,
                        "issues": issues,
                        "metrics": {
                            "coverage": getattr(quality, 'test_coverage', None),
                            "lint_score": getattr(quality, 'lint_score', None),
                            "complexity": getattr(quality, 'cyclomatic_complexity', None)
                        }
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error analyzing {repo}: {e}")

        # Notify if quality issues found
        if quality_issues:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Code quality issues detected in {len(quality_issues)} repositories",
                        priority="high",
                        data={"quality_issues": quality_issues}
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
            "success": len(quality_issues) == 0,
            "repositories_checked": len(repos),
            "issues_found": len(quality_issues),
            "action_taken": action,
            "issues": quality_issues if quality_issues else None
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_code_quality_scores: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="audit_compliance_status",
    description="Verify compliance with security and privacy policies",
    priority="critical",
    max_duration_s=180.0,
    bot_domains=["quality"]
)
async def audit_compliance_status(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Audit compliance with security, privacy, and regulatory policies.

    Scans for hardcoded secrets, PII exposure, license compliance issues,
    and security policy violations.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with compliance audit results
    """
    try:
        violations = []

        # Check for security violations
        if hasattr(bot, 'scan_security_compliance'):
            try:
                security_violations = await bot.scan_security_compliance()
                violations.extend([
                    {"type": "security", **v} for v in security_violations
                ])
            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Security scan error: {e}")

        # Check for PII/ Privacy compliance
        if hasattr(bot, 'scan_privacy_compliance'):
            try:
                privacy_violations = await bot.scan_privacy_compliance()
                violations.extend([
                    {"type": "privacy", **v} for v in privacy_violations
                ])
            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Privacy scan error: {e}")

        # Check license compliance
        if hasattr(bot, 'check_license_compliance'):
            try:
                license_issues = await bot.check_license_compliance()
                violations.extend([
                    {"type": "license", **v} for v in license_issues
                ])
            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] License check error: {e}")

        # Categorize violations
        critical = [v for v in violations if v.get('severity') == 'critical']
        high = [v for v in violations if v.get('severity') == 'high']

        # Escalate critical violations
        if critical:
            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"CRITICAL: {len(critical)} compliance violations detected",
                        priority="critical",
                        data={
                            "critical_violations": critical[:10],
                            "total_violations": len(violations)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif high:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"{len(high)} high-severity compliance issues detected",
                        priority="high",
                        data={"high_issues": high[:10]}
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
            "high": len(high),
            "medium_low": len(violations) - len(critical) - len(high),
            "action_taken": action,
            "violations": violations[:20] if violations else None
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in audit_compliance_status: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="review_audit_trail_integrity",
    description="Verify audit trail completeness and detect gaps",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["quality"]
)
async def review_audit_trail_integrity(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Review audit trails for completeness and detect suspicious gaps.

    Checks that all required audit events are logged, timestamps are
    sequential, and no unauthorized modifications occurred.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with audit trail integrity results
    """
    try:
        # Get audit check window
        lookback_hours = config.get("lookback_hours", 24)
        since = datetime.now() - timedelta(hours=lookback_hours)

        if hasattr(bot, 'review_audit_trail'):
            audit_result = await bot.review_audit_trail(since=since)
        else:
            return {
                "success": True,
                "message": "Audit trail review not available",
                "gaps_found": 0
            }

        gaps = getattr(audit_result, 'gaps', [])
        anomalies = getattr(audit_result, 'anomalies', [])

        # Analyze gaps
        critical_gaps = [g for g in gaps if g.get('severity') == 'critical']

        if critical_gaps or len(anomalies) > 5:
            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Audit trail integrity issues: {len(critical_gaps)} critical gaps, {len(anomalies)} anomalies",
                        priority="critical",
                        data={
                            "critical_gaps": critical_gaps[:5],
                            "anomalies": anomalies[:10],
                            "lookback_hours": lookback_hours
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif gaps:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Audit trail has {len(gaps)} gaps in last {lookback_hours}h",
                        data={"gaps": gaps[:10]}
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
            "success": len(critical_gaps) == 0 and len(anomalies) <= 5,
            "events_reviewed": getattr(audit_result, 'events_reviewed', 0),
            "gaps_found": len(gaps),
            "anomalies_detected": len(anomalies),
            "action_taken": action,
            "integrity_score": getattr(audit_result, 'integrity_score', 100)
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in review_audit_trail_integrity: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_pending_reviews",
    description="Check for pending code reviews and quality gates",
    priority="normal",
    max_duration_s=60.0,
    bot_domains=["quality"]
)
async def check_pending_reviews(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check for pull requests and reviews requiring attention.

    Monitors review queues for PRs that need auditor review or have
    been waiting too long for quality gate approval.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with pending review status
    """
    try:
        max_wait_hours = config.get("max_wait_hours", 24)

        if hasattr(bot, 'get_pending_reviews'):
            pending = await bot.get_pending_reviews()
        else:
            pending = []

        # Categorize by urgency
        now = datetime.now()
        stale_reviews = []
        urgent_reviews = []

        for review in pending:
            created = getattr(review, 'created_at', now)
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                except Exception:
                    created = now

            hours_waiting = (now - created).total_seconds() / 3600

            review_data = {
                "id": getattr(review, 'id', 'unknown'),
                "title": getattr(review, 'title', 'Untitled'),
                "author": getattr(review, 'author', 'unknown'),
                "repository": getattr(review, 'repository', 'unknown'),
                "hours_waiting": round(hours_waiting, 1)
            }

            if hours_waiting > max_wait_hours * 2:
                stale_reviews.append(review_data)
            elif getattr(review, 'requires_qa', False) or hours_waiting > max_wait_hours:
                urgent_reviews.append(review_data)

        # Notify if items need attention
        if stale_reviews:
            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"{len(stale_reviews)} reviews stale (> {max_wait_hours * 2}h)",
                        priority="high",
                        data={"stale_reviews": stale_reviews[:10]}
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            else:
                action = "logged"
        elif urgent_reviews:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"{len(urgent_reviews)} reviews need auditor attention",
                        data={"urgent_reviews": urgent_reviews[:10]}
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
            "success": True,
            "total_pending": len(pending),
            "stale": len(stale_reviews),
            "urgent": len(urgent_reviews),
            "normal": len(pending) - len(stale_reviews) - len(urgent_reviews),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_pending_reviews: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="verify_research_outputs",
    description="Fact-check research outputs and verify source quality",
    priority="high",
    max_duration_s=150.0,
    bot_domains=["quality"]
)
async def verify_research_outputs(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify research outputs from ResearcherBot for accuracy and completeness.

    Checks that research includes verifiable sources, flags unverified claims,
    verifies citation completeness, and checks for conflicting information.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with research verification results
    """
    try:
        # Get recent research outputs to verify
        if hasattr(bot, 'get_pending_research_audits'):
            pending_research = await bot.get_pending_research_audits()
        else:
            return {
                "success": True,
                "message": "No research audit interface available",
                "research_audited": 0
            }

        if not pending_research:
            return {
                "success": True,
                "message": "No research outputs pending audit",
                "research_audited": 0
            }

        verification_results = []
        unverified_claims = []
        missing_sources = []

        for research_item in pending_research:
            try:
                # Check for source verification
                has_sources = getattr(research_item, 'sources', None)
                claims = getattr(research_item, 'claims', [])
                verified_claims = getattr(research_item, 'verified_claims', [])

                item_issues = []

                # Check for unverified claims
                if len(claims) > len(verified_claims):
                    unverified = [c for c in claims if c not in verified_claims]
                    item_issues.append(f"{len(unverified)} unverified claims")
                    unverified_claims.extend(unverified[:5])  # Track first 5

                # Check for missing sources
                if not has_sources or len(has_sources) == 0:
                    item_issues.append("No sources provided")
                    missing_sources.append(getattr(research_item, 'id', 'unknown'))

                # Check source quality
                if has_sources:
                    outdated_sources = [s for s in has_sources if getattr(s, 'is_outdated', False)]
                    if outdated_sources:
                        item_issues.append(f"{len(outdated_sources)} outdated sources not flagged")

                if item_issues:
                    verification_results.append({
                        "research_id": getattr(research_item, 'id', 'unknown'),
                        "title": getattr(research_item, 'title', 'Untitled')[:50],
                        "issues": item_issues,
                        "severity": "high" if "No sources" in str(item_issues) else "medium"
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error verifying research item: {e}")

        # Report findings
        if verification_results:
            high_severity = [r for r in verification_results if r.get('severity') == 'high']

            if high_severity and hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Research verification found {len(high_severity)} high-severity issues",
                        priority="high",
                        data={
                            "high_severity_issues": high_severity[:5],
                            "total_issues": len(verification_results),
                            "unverified_claims_sample": unverified_claims[:5],
                            "missing_sources_count": len(missing_sources)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            elif hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Research verification: {len(verification_results)} items need attention",
                        priority="medium",
                        data={"issues": verification_results[:10]}
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
            "success": len([r for r in verification_results if r.get('severity') == 'high']) == 0,
            "research_audited": len(pending_research),
            "issues_found": len(verification_results),
            "high_severity": len([r for r in verification_results if r.get('severity') == 'high']),
            "unverified_claims": len(unverified_claims),
            "missing_sources": len(missing_sources),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in verify_research_outputs: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_creative_compliance",
    description="Audit creative assets for brand compliance and completeness",
    priority="high",
    max_duration_s=120.0,
    bot_domains=["quality"]
)
async def check_creative_compliance(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check creative outputs from CreativeBot for brand compliance.

    Verifies that creative assets follow brand guidelines, are complete,
    don't contain copyrighted material, and are ready for handoff.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with creative compliance results
    """
    try:
        # Get creative assets pending audit
        if hasattr(bot, 'get_pending_creative_audits'):
            pending_creative = await bot.get_pending_creative_audits()
        else:
            return {
                "success": True,
                "message": "No creative audit interface available",
                "assets_audited": 0
            }

        if not pending_creative:
            return {
                "success": True,
                "message": "No creative assets pending audit",
                "assets_audited": 0
            }

        compliance_issues = []
        brand_violations = []
        copyright_risks = []
        incomplete_assets = []

        for asset in pending_creative:
            try:
                asset_issues = []

                # Check brand compliance
                brand_check = getattr(asset, 'brand_compliance_check', None)
                if brand_check and not getattr(brand_check, 'compliant', True):
                    violations = getattr(brand_check, 'violations', [])
                    asset_issues.append(f"Brand violations: {len(violations)}")
                    brand_violations.append({
                        "asset_id": getattr(asset, 'id', 'unknown'),
                        "violations": violations[:3]
                    })

                # Check for copyright/licensed material flags
                if getattr(asset, 'uses_external_media', False):
                    if not getattr(asset, 'license_verified', False):
                        asset_issues.append("External media without verified license")
                        copyright_risks.append(getattr(asset, 'id', 'unknown'))

                # Check completeness
                required_components = getattr(asset, 'required_components', [])
                present_components = getattr(asset, 'present_components', [])
                missing = [c for c in required_components if c not in present_components]
                if missing:
                    asset_issues.append(f"Missing components: {', '.join(missing[:3])}")
                    incomplete_assets.append({
                        "asset_id": getattr(asset, 'id', 'unknown'),
                        "missing": missing
                    })

                # Check for internal paths/references
                content = getattr(asset, 'content', '') or getattr(asset, 'description', '')
                if content and ('/tmp/' in content or '/var/' in content or 'internal:' in content):
                    asset_issues.append("Contains internal references")

                if asset_issues:
                    compliance_issues.append({
                        "asset_id": getattr(asset, 'id', 'unknown'),
                        "name": getattr(asset, 'name', 'Unnamed')[:40],
                        "type": getattr(asset, 'type', 'unknown'),
                        "issues": asset_issues,
                        "severity": "high" if "copyright" in str(asset_issues).lower() else "medium"
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error checking creative asset: {e}")

        # Report findings
        if compliance_issues:
            high_severity = [i for i in compliance_issues if i.get('severity') == 'high']

            if high_severity and hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Creative compliance: {len(high_severity)} high-risk issues (copyright/brand)",
                        priority="high",
                        data={
                            "high_risk_issues": high_severity[:5],
                            "copyright_risks": copyright_risks[:5],
                            "brand_violations_sample": brand_violations[:3],
                            "total_issues": len(compliance_issues)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            elif hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Creative audit: {len(compliance_issues)} assets need attention",
                        priority="medium",
                        data={
                            "issues": compliance_issues[:10],
                            "incomplete_assets": len(incomplete_assets)
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
            "success": len([i for i in compliance_issues if i.get('severity') == 'high']) == 0,
            "assets_audited": len(pending_creative),
            "issues_found": len(compliance_issues),
            "high_severity": len([i for i in compliance_issues if i.get('severity') == 'high']),
            "brand_violations": len(brand_violations),
            "copyright_risks": len(copyright_risks),
            "incomplete_assets": len(incomplete_assets),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_creative_compliance: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="assess_social_content_risk",
    description="Risk assessment for social media content before publication",
    priority="critical",
    max_duration_s=90.0,
    bot_domains=["quality"]
)
async def assess_social_content_risk(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Audit social media content from SocialBot before it goes live.

    Checks for unverified claims, sensitive topics, brand alignment,
    potential PR risks, and ensures content meets approval criteria.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with social content risk assessment results
    """
    try:
        # Get social content pending risk assessment
        if hasattr(bot, 'get_pending_social_audits'):
            pending_content = await bot.get_pending_social_audits()
        else:
            return {
                "success": True,
                "message": "No social audit interface available",
                "content_audited": 0
            }

        if not pending_content:
            return {
                "success": True,
                "message": "No social content pending audit",
                "content_audited": 0
            }

        risk_flags = []
        unverified_claims = []
        sensitive_topics = []
        pr_risks = []

        for content in pending_content:
            try:
                content_issues = []
                severity = "low"

                # Check for unverified numeric claims
                content_text = getattr(content, 'text', '') or getattr(content, 'content', '')
                if content_text:
                    # Look for numeric claims without verification
                    import re
                    numeric_patterns = re.findall(r'\b\d+%?\b|\b\d+x\b', content_text)
                    verified_numbers = getattr(content, 'verified_numbers', [])

                    for num in numeric_patterns:
                        if num not in verified_numbers:
                            content_issues.append(f"Unverified numeric claim: {num}")
                            unverified_claims.append({
                                "content_id": getattr(content, 'id', 'unknown'),
                                "claim": num,
                                "context": content_text[max(0, content_text.find(num)-20):content_text.find(num)+len(num)+20]
                            })
                            severity = "high"

                # Check for sensitive topics
                sensitive_keywords = ['controversial', 'political', 'religious', 'legal', 'lawsuit']
                topic_tags = getattr(content, 'topic_tags', [])
                content_lower = content_text.lower() if content_text else ''

                for keyword in sensitive_keywords:
                    if keyword in content_lower or keyword in [t.lower() for t in topic_tags]:
                        content_issues.append(f"Sensitive topic detected: {keyword}")
                        sensitive_topics.append({
                            "content_id": getattr(content, 'id', 'unknown'),
                            "topic": keyword
                        })
                        severity = max(severity, "high")

                # Check brand alignment
                brand_score = getattr(content, 'brand_alignment_score', 100)
                if brand_score < 70:
                    content_issues.append(f"Low brand alignment score: {brand_score}")
                    severity = max(severity, "medium")

                # Check for negative sentiment
                sentiment = getattr(content, 'sentiment_analysis', {})
                if sentiment.get('negative', 0) > 0.5:
                    content_issues.append("High negative sentiment detected")
                    pr_risks.append(getattr(content, 'id', 'unknown'))
                    severity = max(severity, "medium")

                # Check approval status
                if getattr(content, 'bypass_audit', False):
                    content_issues.append("Content flagged to bypass audit - requires manual review")
                    severity = "critical"

                if content_issues:
                    risk_flags.append({
                        "content_id": getattr(content, 'id', 'unknown'),
                        "platform": getattr(content, 'platform', 'unknown'),
                        "preview": (content_text[:80] + '...') if content_text and len(content_text) > 80 else content_text,
                        "issues": content_issues,
                        "severity": severity
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error assessing social content: {e}")

        # Report findings
        if risk_flags:
            critical_high = [f for f in risk_flags if f.get('severity') in ['critical', 'high']]

            if critical_high and hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"URGENT: {len(critical_high)} social content items need immediate review before publication",
                        priority="critical",
                        data={
                            "critical_items": critical_high[:5],
                            "unverified_claims": unverified_claims[:5],
                            "sensitive_topics": sensitive_topics[:5],
                            "total_risks": len(risk_flags)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            elif hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Social content audit: {len(risk_flags)} items flagged",
                        priority="high",
                        data={
                            "risk_flags": risk_flags[:10],
                            "pr_risks": len(pr_risks)
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
            "success": len([f for f in risk_flags if f.get('severity') == 'critical']) == 0,
            "content_audited": len(pending_content),
            "risks_found": len(risk_flags),
            "critical": len([f for f in risk_flags if f.get('severity') == 'critical']),
            "high": len([f for f in risk_flags if f.get('severity') == 'high']),
            "unverified_claims": len(unverified_claims),
            "sensitive_topics": len(sensitive_topics),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in assess_social_content_risk: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="verify_cross_bot_handoffs",
    description="Check cross-bot workflow compliance and handoff completeness",
    priority="high",
    max_duration_s=100.0,
    bot_domains=["quality"]
)
async def verify_cross_bot_handoffs(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify that handoffs between bots are complete and compliant.

    Checks that deliverables are transferred correctly, context is preserved,
    definition-of-done criteria are met, and no information is lost in handoffs.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with handoff verification results
    """
    try:
        # Get recent cross-bot handoffs
        if hasattr(bot, 'get_recent_handoffs'):
            handoffs = await bot.get_recent_handoffs()
        else:
            return {
                "success": True,
                "message": "No handoff tracking available",
                "handoffs_checked": 0
            }

        if not handoffs:
            return {
                "success": True,
                "message": "No recent handoffs to verify",
                "handoffs_checked": 0
            }

        handoff_issues = []
        incomplete_handoffs = []
        context_gaps = []
        dod_failures = []

        for handoff in handoffs:
            try:
                issues = []

                # Check deliverable completeness
                expected_deliverables = getattr(handoff, 'expected_deliverables', [])
                actual_deliverables = getattr(handoff, 'actual_deliverables', [])
                missing = [d for d in expected_deliverables if d not in actual_deliverables]

                if missing:
                    issues.append(f"Missing deliverables: {', '.join(missing[:3])}")
                    incomplete_handoffs.append({
                        "handoff_id": getattr(handoff, 'id', 'unknown'),
                        "from_bot": getattr(handoff, 'from_bot', 'unknown'),
                        "to_bot": getattr(handoff, 'to_bot', 'unknown'),
                        "missing": missing
                    })

                # Check context transfer
                context_transferred = getattr(handoff, 'context_transferred', True)
                if not context_transferred:
                    issues.append("Context not properly transferred")
                    context_gaps.append(getattr(handoff, 'id', 'unknown'))

                # Check Definition of Done
                dod_criteria = getattr(handoff, 'definition_of_done', [])
                dod_met = getattr(handoff, 'dod_met', [])
                failed_criteria = [c for c in dod_criteria if c not in dod_met]

                if failed_criteria:
                    issues.append(f"Definition of Done not met: {len(failed_criteria)} criteria")
                    dod_failures.append({
                        "handoff_id": getattr(handoff, 'id', 'unknown'),
                        "failed_criteria": failed_criteria[:5]
                    })

                # Check for information loss
                info_loss_flags = getattr(handoff, 'information_loss_flags', [])
                if info_loss_flags:
                    issues.append(f"Potential information loss: {len(info_loss_flags)} flags")

                # Check approval status
                if getattr(handoff, 'requires_approval', False) and not getattr(handoff, 'approved', False):
                    issues.append("Handoff requires approval but not approved")

                if issues:
                    handoff_issues.append({
                        "handoff_id": getattr(handoff, 'id', 'unknown'),
                        "from_bot": getattr(handoff, 'from_bot', 'unknown'),
                        "to_bot": getattr(handoff, 'to_bot', 'unknown'),
                        "issues": issues,
                        "severity": "high" if missing or failed_criteria else "medium"
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error verifying handoff: {e}")

        # Report findings
        if handoff_issues:
            high_severity = [h for h in handoff_issues if h.get('severity') == 'high']

            if high_severity and hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Cross-bot handoff issues: {len(high_severity)} high-severity problems",
                        priority="high",
                        data={
                            "high_severity_issues": high_severity[:5],
                            "incomplete_handoffs": incomplete_handoffs[:5],
                            "dod_failures": dod_failures[:5],
                            "total_issues": len(handoff_issues)
                        }
                    )
                    action = "escalated"
                except Exception as e:
                    logger.error(f"Failed to escalate: {e}")
                    action = "logged"
            elif hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Handoff verification: {len(handoff_issues)} issues found",
                        priority="medium",
                        data={
                            "issues": handoff_issues[:10],
                            "context_gaps": len(context_gaps)
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
            "success": len([h for h in handoff_issues if h.get('severity') == 'high']) == 0,
            "handoffs_checked": len(handoffs),
            "issues_found": len(handoff_issues),
            "high_severity": len([h for h in handoff_issues if h.get('severity') == 'high']),
            "incomplete_handoffs": len(incomplete_handoffs),
            "context_gaps": len(context_gaps),
            "dod_failures": len(dod_failures),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in verify_cross_bot_handoffs: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="check_documentation_completeness",
    description="Verify documentation accuracy and completeness across all domains",
    priority="normal",
    max_duration_s=120.0,
    bot_domains=["quality"]
)
async def check_documentation_completeness(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Audit documentation across all bot outputs for completeness.

    Checks that deliverables include required documentation, READMEs are present,
    API docs are complete, and internal knowledge is captured.

    Args:
        bot: The AuditorBot instance
        config: Check configuration

    Returns:
        Dict with documentation completeness results
    """
    try:
        # Get documentation items to check
        if hasattr(bot, 'get_documentation_status'):
            docs = await bot.get_documentation_status()
        else:
            return {
                "success": True,
                "message": "No documentation tracking available",
                "docs_checked": 0
            }

        if not docs:
            return {
                "success": True,
                "message": "No documentation pending review",
                "docs_checked": 0
            }

        doc_issues = []
        missing_readmes = []
        incomplete_api_docs = []
        outdated_docs = []

        for doc in docs:
            try:
                issues = []

                # Check README completeness
                if getattr(doc, 'requires_readme', False):
                    readme = getattr(doc, 'readme_present', False)
                    if not readme:
                        issues.append("README missing")
                        missing_readmes.append(getattr(doc, 'id', 'unknown'))
                    else:
                        readme_sections = getattr(doc, 'readme_sections', [])
                        required_sections = ['Installation', 'Usage', 'Contributing']
                        missing_sections = [s for s in required_sections if s not in readme_sections]
                        if missing_sections:
                            issues.append(f"README missing sections: {', '.join(missing_sections[:2])}")

                # Check API documentation
                if getattr(doc, 'has_api', False):
                    api_docs = getattr(doc, 'api_documented', False)
                    if not api_docs:
                        issues.append("API not documented")
                        incomplete_api_docs.append(getattr(doc, 'id', 'unknown'))
                    else:
                        coverage = getattr(doc, 'api_coverage', 0)
                        if coverage < 80:
                            issues.append(f"API documentation incomplete ({coverage}% coverage)")

                # Check for outdated documentation
                last_updated = getattr(doc, 'last_updated', None)
                if last_updated:
                    try:
                        if isinstance(last_updated, str):
                            last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                        days_old = (datetime.now() - last_updated).days
                        if days_old > 90:
                            issues.append(f"Documentation outdated ({days_old} days old)")
                            outdated_docs.append({
                                "doc_id": getattr(doc, 'id', 'unknown'),
                                "days_old": days_old
                            })
                    except Exception:
                        pass

                # Check for TODO/FIXME markers
                content = getattr(doc, 'content', '')
                if content:
                    todos = content.count('TODO') + content.count('FIXME') + content.count('XXX')
                    if todos > 3:
                        issues.append(f"{todos} unresolved TODO/FIXME markers")

                if issues:
                    doc_issues.append({
                        "doc_id": getattr(doc, 'id', 'unknown'),
                        "title": getattr(doc, 'title', 'Untitled')[:50],
                        "type": getattr(doc, 'type', 'unknown'),
                        "issues": issues,
                        "severity": "medium"
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error checking documentation: {e}")

        # Report findings
        if doc_issues:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Documentation audit: {len(doc_issues)} items need attention",
                        priority="low",
                        data={
                            "issues": doc_issues[:10],
                            "missing_readmes": len(missing_readmes),
                            "incomplete_api_docs": len(incomplete_api_docs),
                            "outdated_docs": len(outdated_docs)
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
            "success": True,
            "docs_checked": len(docs),
            "issues_found": len(doc_issues),
            "missing_readmes": len(missing_readmes),
            "incomplete_api_docs": len(incomplete_api_docs),
            "outdated_docs": len(outdated_docs),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in check_documentation_completeness: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


__all__ = [
    "check_code_quality_scores",
    "audit_compliance_status",
    "review_audit_trail_integrity",
    "check_pending_reviews",
    "verify_research_outputs",
    "check_creative_compliance",
    "assess_social_content_risk",
    "verify_cross_bot_handoffs",
    "check_documentation_completeness",
]
