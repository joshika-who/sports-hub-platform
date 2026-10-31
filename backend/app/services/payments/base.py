from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict


@dataclass
class GatewayOrderResult:
    gateway_order_id: str
    checkout_url_or_token: str


class PaymentGateway(ABC):
    """Abstract base class for all payment gateway adapters."""

    @abstractmethod
    def create_order(
        self,
        amount: int,
        currency: str,
        purpose: str,
        ref_id: str,
    ) -> GatewayOrderResult:
        """Create an order/intent on the gateway and return order_id + checkout URL/token."""
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, headers: Dict[str, str], body: bytes) -> str:
        """
        Verify webhook signature and return the verified gateway_order_id.
        Raises ValueError if signature is invalid.
        """
        raise NotImplementedError

