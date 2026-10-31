import logging
from app.config import settings

logger = logging.getLogger("sportshub.notifications.fcm")


def send_fcm_push(device_token: str, title: str, body: str, data: dict) -> bool:
    """
    Sends push notification via Firebase Cloud Messaging HTTP v1 API in live mode.
    """
    if not settings.FCM_PROJECT_ID:
        logger.warning("FCM_PROJECT_ID not set; skipping live FCM HTTP v1 call.")
        return False

    try:
        import httpx

        url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
        payload = {
            "message": {
                "token": device_token,
                "notification": {"title": title, "body": body},
                "data": {k: str(v) for k, v in (data or {}).items()},
            }
        }
        headers = {"Authorization": f"Bearer {settings.FCM_SERVICE_ACCOUNT_JSON}"}
        resp = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        return resp.status_code < 300
    except Exception as exc:
        logger.error("FCM push error: %s", exc)
        return False

