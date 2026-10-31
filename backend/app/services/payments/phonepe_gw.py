import base64
import hashlib
import hmac
import json
import uuid
from typing import Dict

from app.config import settings
from app.services.payments.base import GatewayOrderResult, PaymentGateway


class PhonePeGateway(PaymentGateway):
    """PhonePe PG v1 Pay & X-VERIFY Checksum adapter (live mode)."""

    def create_order(
        self,
        amount: int,
        currency: str,
        purpose: str,
        ref_id: str,
    ) -> GatewayOrderResult:
        import httpx

        txn_id = f"PP_{uuid.uuid4().hex[:16].upper()}"
        payload_dict = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": txn_id,
            "merchantUserId": ref_id[:32],
            "amount": amount,
            "redirectUrl": "http://localhost:3000/bookings",
            "redirectMode": "REDIRECT",
            "callbackUrl": "http://localhost:8000/api/v1/payments/webhook/phonepe",
            "paymentInstrument": {"type": "PAY_PAGE"},
        }
        b64_payload = base64.b64encode(json.dumps(payload_dict).encode("utf-8")).decode("utf-8")
        endpoint = "/pg/v1/pay"
        checksum_str = f"{b64_payload}{endpoint}{settings.PHONEPE_SALT_KEY}"
        sha256_val = hashlib.sha256(checksum_str.encode("utf-8")).hexdigest()
        x_verify = f"{sha256_val}###{settings.PHONEPE_SALT_INDEX}"

        base_url = (
            "https://api-preprod.phonepe.com/apis/pg-sandbox"
            if settings.PHONEPE_ENV.upper() == "UAT"
            else "https://api.phonepe.com/apis/hermes"
        )
        resp = httpx.post(
            f"{base_url}{endpoint}",
            headers={"Content-Type": "application/json", "X-VERIFY": x_verify},
            json={"request": b64_payload},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        redirect_url = (
            data.get("data", {})
            .get("instrumentResponse", {})
            .get("redirectInfo", {})
            .get("url", txn_id)
        )
        return GatewayOrderResult(
            gateway_order_id=txn_id,
            checkout_url_or_token=redirect_url,
        )

    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> str:
        x_verify = headers.get("x-verify") or headers.get("X-VERIFY") or ""
        if not x_verify:
            raise ValueError("Missing PhonePe X-VERIFY header.")

        expected_hash = hashlib.sha256(
            body + settings.PHONEPE_SALT_KEY.encode("utf-8")
        ).hexdigest()
        expected_header = f"{expected_hash}###{settings.PHONEPE_SALT_INDEX}"

        if not hmac.compare_digest(expected_header, x_verify):
            raise ValueError("Invalid PhonePe X-VERIFY checksum.")

        payload = json.loads(body.decode("utf-8"))
        order_id = (
            payload.get("data", {}).get("merchantTransactionId")
            or payload.get("gateway_order_id")
            or payload.get("order_id")
        )
        if not order_id:
            raise ValueError("Missing merchantTransactionId in PhonePe webhook.")
        return str(order_id)

