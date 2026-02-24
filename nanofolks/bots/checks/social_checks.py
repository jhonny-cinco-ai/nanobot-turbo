"""CrewRoutines checks for SocialBot (Lookout).

These checks run every 60 minutes (by default) to monitor social media,
scheduled posts, community engagement, and trending topics.

Usage:
    Automatically registered when SocialBot initializes.
"""

from datetime import datetime
from typing import Any, Dict

from loguru import logger

from nanofolks.crew_routines.check_registry import register_check


@register_check(
    name="publish_scheduled_posts",
    description="Publish posts scheduled for current time",
    priority="critical",
    max_duration_s=60.0,
    bot_domains=["community"]
)
async def publish_scheduled_posts(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check for and publish scheduled social media posts.

    Automatically publishes posts that are scheduled for the current
    time or past due. Tracks successes and failures.

    Args:
        bot: The SocialBot instance
        config: Check configuration

    Returns:
        Dict with publishing results
    """
    try:
        # Get scheduled posts
        now = datetime.now()
        if hasattr(bot, 'get_scheduled_posts'):
            scheduled_posts = await bot.get_scheduled_posts(before=now)
        else:
            scheduled_posts = []

        if not scheduled_posts:
            return {
                "success": True,
                "message": "No scheduled posts",
                "posts_scheduled": 0,
                "published": 0,
                "failed": 0
            }

        published = []
        failed = []

        for post in scheduled_posts:
            try:
                success = False
                if hasattr(bot, 'publish_post'):
                    success = await bot.publish_post(post)

                if success:
                    published.append({
                        "post_id": getattr(post, 'id', 'unknown'),
                        "platform": getattr(post, 'platform', 'unknown'),
                        "content_preview": str(getattr(post, 'content', ''))[:50] + "..."
                    })
                else:
                    failed.append({
                        "post_id": getattr(post, 'id', 'unknown'),
                        "platform": getattr(post, 'platform', 'unknown'),
                        "error": "Publishing failed"
                    })

            except Exception as e:
                logger.error(f"[{bot.role_card.bot_name}] Error publishing post: {e}")
                failed.append({
                    "post_id": getattr(post, 'id', 'unknown'),
                    "error": str(e)
                })

        # Escalate failures
        if failed:
            if hasattr(bot, 'escalate_to_coordinator'):
                try:
                    await bot.escalate_to_coordinator(
                        f"Failed to publish {len(failed)} scheduled posts",
                        priority="high",
                        data={"failed_posts": failed}
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
            "success": len(failed) == 0,
            "posts_scheduled": len(scheduled_posts),
            "published": len(published),
            "failed": len(failed),
            "action_taken": action
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error in publish_scheduled_posts: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="monitor_community_mentions",
    description="Monitor social platforms for mentions and engagement",
    priority="high",
    max_duration_s=90.0,
    bot_domains=["community"],
    platforms=["twitter", "linkedin", "reddit"]
)
async def monitor_community_mentions(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Monitor social platforms for mentions requiring response.

    Checks configured platforms for mentions, especially those with
    negative sentiment or requiring urgent response.

    Args:
        bot: The SocialBot instance
        config: Configuration with platforms list

    Returns:
        Dict with mention counts and urgent items
    """
    platforms = config.get("platforms", ["twitter", "linkedin"])

    total_mentions = 0
    urgent_mentions = []

    for platform in platforms:
        try:
            # Get last check time
            last_check_key = f"last_mention_check_{platform}"
            since = bot.private_memory.get(last_check_key)

            # Check mentions
            if hasattr(bot, 'check_mentions'):
                mentions = await bot.check_mentions(platform, since=since)
            else:
                mentions = []

            total_mentions += len(mentions)

            # Identify urgent mentions
            urgent = [
                m for m in mentions
                if getattr(m, 'requires_response', False) or
                getattr(m, 'sentiment', '') in ["negative", "urgent", "angry"]
            ]

            if urgent:
                # Draft responses
                for mention in urgent:
                    if hasattr(bot, 'draft_response'):
                        mention.response = await bot.draft_response(mention)

                urgent_mentions.extend(urgent)

            # Update memory
            bot.private_memory[last_check_key] = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error checking {platform}: {e}")

    # Notify if urgent mentions
    if urgent_mentions:
        if hasattr(bot, 'notify_coordinator'):
            try:
                await bot.notify_coordinator(
                    f"{len(urgent_mentions)} urgent community mentions require response",
                    priority="high",
                    data={
                        "mentions": [
                            {
                                "id": getattr(m, 'id', 'unknown'),
                                "platform": getattr(m, 'platform', 'unknown'),
                                "author": getattr(m, 'author', 'unknown'),
                                "sentiment": getattr(m, 'sentiment', 'unknown'),
                                "preview": str(getattr(m, 'content', ''))[:100] + "..."
                            }
                            for m in urgent_mentions[:5]
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
        "platforms_checked": len(platforms),
        "total_mentions": total_mentions,
        "urgent_mentions": len(urgent_mentions),
        "action_taken": action
    }


@register_check(
    name="check_engagement_metrics",
    description="Analyze engagement metrics and report anomalies",
    priority="normal",
    max_duration_s=60.0,
    bot_domains=["community"]
)
async def check_engagement_metrics(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze engagement metrics and detect significant changes.

    Tracks likes, shares, comments, reach, and other engagement metrics.
    Detects sudden drops or spikes that may indicate issues or opportunities.

    Args:
        bot: The SocialBot instance
        config: Check configuration

    Returns:
        Dict with metric analysis and anomalies
    """
    try:
        if hasattr(bot, 'analyze_engagement_metrics'):
            metrics = await bot.analyze_engagement_metrics()
        else:
            metrics = {}

        # Detect anomalies
        anomalies = []

        for metric_name, values in metrics.items():
            if len(values) < 2:
                continue

            current = values[-1]
            avg = sum(values[:-1]) / len(values[:-1])

            # 30% drop or 50% spike
            if current < avg * 0.7:
                anomalies.append({
                    "metric": metric_name,
                    "change": "drop",
                    "percent": round(((avg - current) / avg) * 100, 1),
                    "current": current,
                    "average": round(avg, 1)
                })
            elif current > avg * 1.5:
                anomalies.append({
                    "metric": metric_name,
                    "change": "spike",
                    "percent": round(((current - avg) / avg) * 100, 1),
                    "current": current,
                    "average": round(avg, 1)
                })

        if anomalies:
            if hasattr(bot, 'notify_coordinator'):
                try:
                    await bot.notify_coordinator(
                        f"Engagement anomalies detected: {len(anomalies)} metrics",
                        data={"anomalies": anomalies}
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
            "metrics_analyzed": len(metrics),
            "anomalies_detected": len(anomalies),
            "action_taken": action,
            "anomalies": anomalies if anomalies else None
        }

    except Exception as e:
        logger.error(f"[{bot.role_card.bot_name}] Error checking engagement: {e}")
        return {
            "success": False,
            "error": str(e),
            "action_taken": "error"
        }


@register_check(
    name="track_trending_topics",
    description="Track trending topics relevant to the brand",
    priority="low",
    max_duration_s=120.0,
    bot_domains=["community"],
    topics=[]  # Configurable topics to track
)
async def track_trending_topics(bot, config: Dict[str, Any]) -> Dict[str, Any]:
    """Track trending topics and suggest content opportunities.

    Monitors configured topics for trending activity. High-opportunity
    trends are reported for potential content creation.

    Args:
        bot: The SocialBot instance
        config: Configuration with topics list

    Returns:
        Dict with trending topics and opportunities
    """
    tracked_topics = config.get("topics", [])

    if not tracked_topics:
        return {
            "success": True,
            "message": "No topics configured",
            "topics_checked": 0,
            "trending": 0
        }

    trending = []

    for topic in tracked_topics:
        try:
            if hasattr(bot, 'check_trending'):
                trend_data = await bot.check_trending(topic)
            else:
                trend_data = None

            if (trend_data and
                getattr(trend_data, 'is_trending', False) and
                getattr(trend_data, 'volume', 0) > 1000):

                trending.append({
                    "topic": topic,
                    "volume": getattr(trend_data, 'volume', 0),
                    "sentiment": getattr(trend_data, 'sentiment', 'neutral'),
                    "opportunity_score": getattr(trend_data, 'opportunity_score', 0.5),
                    "trending_since": getattr(trend_data, 'trending_since', None)
                })

        except Exception as e:
            logger.error(f"[{bot.role_card.bot_name}] Error checking topic {topic}: {e}")

    # Sort by opportunity score
    trending.sort(key=lambda x: x["opportunity_score"], reverse=True)

    if trending:
        if hasattr(bot, 'notify_coordinator'):
            try:
                await bot.notify_coordinator(
                    f"{len(trending)} tracked topics are trending",
                    data={
                        "trending_topics": trending[:5],
                        "suggested_action": "Consider creating content around these topics"
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
        "topics_checked": len(tracked_topics),
        "trending": len(trending),
        "action_taken": action,
        "top_topics": trending[:3] if trending else None
    }


__all__ = [
    "publish_scheduled_posts",
    "monitor_community_mentions",
    "check_engagement_metrics",
    "track_trending_topics",
]
