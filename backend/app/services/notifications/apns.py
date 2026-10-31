import logging
from app.config import settings

logger = logging.getLogger("sportshub.notifications.apns")


def send_apns_push(device_token: str, title: str, body: str, data: dict) -> bool:
    """
    Sends push notification via Apple Push Notification service (APNs) in live mode.
    """
    clean_token = device_token.replace("apns:", "").replace("ios:", "")
    if not settings.APNS_KEY_ID or not settings.APNS_TEAM_ID:
        logger.warning("APNS credentials not set; skipping live APNs push.")
        return False

    try:
        import httpx

        url = f"https://api.sandbox.push.apple.com/3/device/{clean_token}"
        payload = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
            },
            "custom": data or {},
        }
        headers = {"apns-topic": settings.APNS_BUNDLE_ID}
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        return resp.status_code < 300
    except Exception as exc:
        logger.error("APNs push error: %s", exc)
        return False

