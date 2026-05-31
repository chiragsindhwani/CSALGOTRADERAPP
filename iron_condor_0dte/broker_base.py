"""Abstract base class defining the broker integration interface."""
from abc import ABC, abstractmethod
from typing import Any


class BaseBrokerClient(ABC):
    """Common interface for trading with different brokers (Tradier, IBKR, etc.)."""

    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """Fetch market quote for a symbol.

        Returns:
            dict with keys: bid (float), ask (float), last (float)
        """
        pass

    @abstractmethod
    def get_profile(self) -> dict:
        """Get account profile info.

        Returns:
            dict with keys: name (str), account (dict with 'number' key)
        """
        pass

    @abstractmethod
    def get_order(self, order_id: str | int) -> dict:
        """Get single order status.

        Returns:
            dict with keys: id, status ("filled"|"open"|"rejected"|"cancelled"),
            avg_fill_price (float)
        """
        pass

    @abstractmethod
    def place_multileg_order(
        self,
        legs: list[dict],
        qty: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict:
        """Place a multi-leg order (e.g., Iron Condor).

        Args:
            legs: list of {"symbol": "<OCC>", "side": "buy_to_open|sell_to_open|..."}
            qty: number of contracts
            order_type: "market" or "credit"
            price: limit price for credit orders

        Returns:
            dict with key: id (order_id)
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str | int) -> dict:
        """Cancel a pending order.

        Returns:
            dict with key: status
        """
        pass
