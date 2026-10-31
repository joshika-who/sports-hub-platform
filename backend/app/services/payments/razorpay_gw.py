import hashlib
import hmac
import json
from typing import Dict

from app.config import settings
from app.services.payments.base import GatewayOrderResult, PaymentGateway


class RazorpayGateway(PaymentGateway):
    """Razorpay Orders API & Webhook adapter (live mode)."""

    def create_order(
        self,
        amount: int,
        currency: str,
        purpose: str,
        ref_id: str,
    ) -> GatewayOrderResult:
        import httpx

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise RuntimeError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not configured for live mode.")

        resp = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                "amount": amount,
                "currency": currency.upper(),
                "receipt": f"{purpose}_{ref_id}"[:40],
                "notes": {"purpose": purpose, "ref_id": ref_id},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return GatewayOrderResult(
            gateway_order_id=data["id"],
            checkout_url_or_token=data["id"],
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> str:
        sig = (
            headers.get("x-razorpay-signature")
            or headers.get("X-Razorpay-Signature")
            or ""
        )
        if not sig:
            raise ValueError("Missing X-Razorpay-Signature header.")

        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, sig):
            raise ValueError("Invalid Razorpay webhook signature.")

        payload = json.loads(body.decode("utf-8"))
        order_id = (
            payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")
            or payload.get("gateway_order_id")
            or payload.get("order_id")
        )
        if not order_id:
            raise ValueError("Missing order_id in Razorpay webhook payload.")
        return str(order_id)

