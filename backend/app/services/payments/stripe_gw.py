import hashlib
import hmac
import json
from typing import Dict

from app.config import settings
from app.services.payments.base import GatewayOrderResult, PaymentGateway


class StripeGateway(PaymentGateway):
    """Stripe PaymentIntent & Webhook adapter (live mode)."""

    def create_order(
        self,
        amount: int,
        currency: str,
        purpose: str,
        ref_id: str,
    ) -> GatewayOrderResult:
        import httpx

        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured for live mode.")

        resp = httpx.post(
            "https://api.stripe.com/v1/payment_intents",
            headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
            data={
                "amount": str(amount),
                "currency": currency.lower(),
                "metadata[purpose]": purpose,
                "metadata[ref_id]": ref_id,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return GatewayOrderResult(
            gateway_order_id=data["id"],
            checkout_url_or_token=data.get("client_secret", data["id"]),
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> str:
        sig_header = (
            headers.get("stripe-signature")
            or headers.get("Stripe-Signature")
            or ""
        )
        if not sig_header:
            raise ValueError("Missing Stripe-Signature header.")

        # Support both `t=...,v1=...` format and direct HMAC hex digest
        parts = dict(
            item.split("=", 1) for item in sig_header.split(",") if "=" in item
        )
        if "t" in parts and "v1" in parts:
            signed_payload = f"{parts['t']}.".encode("utf-8") + body
            expected = hmac.new(
                settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
                signed_payload,
                hashlib.sha256,
            ).hexdigest()
            provided = parts["v1"]
        else:
            expected = hmac.new(
                settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            provided = sig_header

        if not hmac.compare_digest(expected, provided):
            raise ValueError("Invalid Stripe webhook HMAC signature.")

        payload = json.loads(body.decode("utf-8"))
        order_id = (
            payload.get("data", {}).get("object", {}).get("id")
            or payload.get("gateway_order_id")
            or payload.get("order_id")
        )
        if not order_id:
            raise ValueError("Missing order ID in Stripe webhook payload.")
        return str(order_id)

