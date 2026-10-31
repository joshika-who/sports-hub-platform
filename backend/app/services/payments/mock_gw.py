import json
import uuid
from typing import Dict

from app.services.payments.base import GatewayOrderResult, PaymentGateway


class MockGateway(PaymentGateway):
    """
    Deterministic mock payment gateway for local development, demos, and CI testing.
    Requires zero API keys while exercising the full webhook/confirmation lifecycle.
    """

    def __init__(self, label: str = "mock") -> None:
        self.label = label

    def create_order(
        self,
        amount: int,
        currency: str,
        purpose: str,
        ref_id: str,
    ) -> GatewayOrderResult:
        order_id = f"mock_{self.label}_ord_{uuid.uuid4().hex[:12]}"
        checkout_token = f"/mock-checkout/{order_id}?amount={amount}&currency={currency}&gateway={self.label}"
        return GatewayOrderResult(
            gateway_order_id=order_id,
            checkout_url_or_token=checkout_token,
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> str:
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"Invalid JSON webhook body: {exc}")

        order_id = payload.get("gateway_order_id") or payload.get("order_id")
        if not order_id:
            raise ValueError("Missing gateway_order_id in webhook payload")
        return str(order_id)

