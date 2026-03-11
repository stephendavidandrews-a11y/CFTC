"""
Push notification service using ntfy.sh.
Sends notifications to the user's iPhone via the ntfy app.
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "network-outreach")
NTFY_BASE_URL = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh")
SITE_URL = os.environ.get("SITE_URL", "https://cftc.stephenandrews.org/network")


async def send_notification(
    title: str,
    message: str,
    tag: str = "outreach",
    priority: int = 3,
    url: str = None,
) -> bool:
    """
    Send a push notification via ntfy.sh.

    Args:
        title: Notification title
        message: Notification body text
        tag: ntfy tag for icon (e.g., "outreach", "loudspeaker", "beer")
        priority: 1-5 (1=min, 3=default, 5=urgent)
        url: Click action URL (defaults to approval queue)

    Returns:
        True if notification was sent successfully, False otherwise.
    """
    click_url = url or f"{SITE_URL}/queue"

    headers = {
        "Title": title,
        "Priority": str(priority),
        "Tags": tag,
        "Click": click_url,
        "Actions": f"view, Open Queue, {click_url}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{NTFY_BASE_URL}/{NTFY_TOPIC}",
                content=message,
                headers=headers,
            )
            if response.status_code == 200:
                logger.info(f"Notification sent: {title}")
                return True
            else:
                logger.warning(f"ntfy returned {response.status_code}: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


async def notify_new_outreach(plan_count: int, plan_type: str = "outreach"):
    """Send a notification about new outreach plans ready for approval."""
    type_labels = {
        "social_thursday": "Thursday Touchbase",
        "professional_pulse": "Professional Pulse",
        "happy_hour_invite": "Happy Hour Invites",
        "happy_hour_reminder": "Happy Hour Reminders",
        "ad_hoc_due": "Due Contacts",
    }
    label = type_labels.get(plan_type, "Outreach")
    tag_map = {
        "happy_hour_invite": "beer",
        "happy_hour_reminder": "beer",
        "social_thursday": "speech_balloon",
        "professional_pulse": "briefcase",
        "ad_hoc_due": "wave",
    }
    tag = tag_map.get(plan_type, "loudspeaker")

    await send_notification(
        title=f"{label}: {plan_count} messages ready",
        message=f"You have {plan_count} new {label.lower()} messages to review and send.",
        tag=tag,
        priority=3 if plan_type != "happy_hour_reminder" else 4,
    )
