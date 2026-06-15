"""Alpaca Markets REST API client — supports paper and live trading."""
from __future__ import annotations

import logging
import requests
from typing import Any

from .broker_base import BaseBrokerClient

log = logging.getLogger(__name__)

_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
_LIVE_BASE_URL = "https://api.alpaca.markets"


class AlpacaClient(BaseBrokerClient):
    """Thin wrapper around the Alpaca REST API."""

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.base_url = _PAPER_BASE_URL if paper else _LIVE_BASE_URL
        self._s = requests.Session()
        self._s.headers.update({
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Content-Type": "application/json",
        })
        log.info("AlpacaClient initialised | %s", "PAPER" if paper else "LIVE")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get(self, path: str, **params) -> Any:
        resp = self._s.get(f"{self.base_url}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> Any:
        resp = self._s.post(f"{self.base_url}{path}", json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str) -> Any:
        resp = self._s.delete(f"{self.base_url}{path}", timeout=10)
        if resp.status_code == 204:
            return {}
        resp.raise_for_status()
        return resp.json()

    # ── Market data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Fetch latest quote for a symbol.

        Returns:
            dict with keys: bid, ask, last
        """
        try:
            data = self._get(f"/v2/stocks/{symbol}/latest/quote")
            quote = data.get("quote", {})
            return {
                "bid": float(quote.get("bp", 0)),
                "ask": float(quote.get("ap", 0)),
                "last": float(quote.get("lp", 0)),
            }
        except Exception as e:
            log.warning("get_quote failed for %s: %s", symbol, e)
            return {"bid": 0, "ask": 0, "last": 0}

    # ── Account ────────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        """Get account information."""
        return self._get("/v2/account")

    def get_profile(self) -> dict:
        """Get account profile info.

        Returns:
            dict with keys: name, account (dict with 'number' key)
        """
        try:
            account = self.get_account()
            return {
                "name": f"Alpaca Account",
                "account": {
                    "number": account.get("account_number", ""),
                    "status": account.get("status", ""),
                    "equity": account.get("equity", 0),
                    "cash": account.get("cash", 0),
                },
                "profile": account,
            }
        except Exception as e:
            log.error("get_profile failed: %s", e)
            return {"name": "Alpaca Account", "account": {"number": ""}}

    def get_positions(self) -> list[dict]:
        """Get all open positions."""
        try:
            return self._get("/v2/positions")
        except Exception as e:
            log.warning("get_positions failed: %s", e)
            return []

    def get_open_orders(self) -> list[dict]:
        """Get all open orders."""
        try:
            orders = self._get("/v2/orders", status="open")
            return orders if isinstance(orders, list) else []
        except Exception as e:
            log.warning("get_open_orders failed: %s", e)
            return []

    def get_order(self, order_id: str | int) -> dict:
        """Get single order by ID.

        Returns:
            dict with keys: id, status, avg_fill_price
        """
        try:
            order = self._get(f"/v2/orders/{order_id}")
            status_map = {
                "pending_new": "open",
                "accepted": "open",
                "pending_cancel": "open",
                "pending_replace": "open",
                "accepted_for_bidding": "open",
                "filled": "filled",
                "partially_filled": "open",
                "done_for_day": "filled",
                "canceled": "cancelled",
                "expired": "cancelled",
                "rejected": "cancelled",
            }
            return {
                "id": order.get("id"),
                "status": status_map.get(order.get("status"), "open"),
                "avg_fill_price": float(order.get("filled_avg_price", 0) or 0),
            }
        except Exception as e:
            log.warning("get_order failed for %s: %s", order_id, e)
            return {"id": order_id, "status": "open", "avg_fill_price": 0}

    # ── Orders ─────────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,  # buy or sell
        order_type: str = "market",
        limit_price: float | None = None,
        time_in_force: str = "day",
    ) -> dict:
        """Place a single order."""
        data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price:
            data["limit_price"] = limit_price

        try:
            order = self._post("/v2/orders", data)
            return {"id": order.get("id"), "status": "open"}
        except Exception as e:
            log.error("place_order failed: %s", e)
            raise

    def place_multileg_order(
        self,
        legs: list[dict],
        qty: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict:
        """Place a multi-leg options order (Iron Condor, etc).

        Note: Alpaca's options API is in beta. This uses the standard order format.
        For best results with spreads, submit individual legs separately or use
        the Alpaca options API when available.

        Args:
            legs: list of {"symbol": "<OCC>", "side": "buy_to_open|sell_to_open|..."}
            qty: number of contracts
            order_type: "market" or "credit"
            price: limit price for credit orders

        Returns:
            dict with key: id (order_id)
        """
        try:
            # For multi-leg options orders, we'll submit them sequentially
            # A real implementation would use Alpaca's multileg order API if available
            order_ids = []
            for leg in legs:
                symbol = leg.get("symbol", "")
                side_str = leg.get("side", "")

                # Parse side (buy_to_open, sell_to_open, buy_to_close, sell_to_close)
                side = "buy" if "buy" in side_str else "sell"

                # Place individual leg order
                leg_order = self.place_order(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    order_type=order_type if order_type == "market" else "limit",
                    limit_price=price,
                    time_in_force="day"
                )
                order_ids.append(leg_order["id"])

            # Return the first order ID as the "parent" order
            return {"id": order_ids[0] if order_ids else None}
        except Exception as e:
            log.error("place_multileg_order failed: %s", e)
            raise

    def cancel_order(self, order_id: str | int) -> dict:
        """Cancel a pending order."""
        try:
            self._delete(f"/v2/orders/{order_id}")
            return {"status": "cancelled"}
        except Exception as e:
            log.warning("cancel_order failed for %s: %s", order_id, e)
            return {"status": "not_found"}

    def cancel_all_orders(self) -> list[dict]:
        """Cancel all open orders."""
        try:
            return self._delete("/v2/orders")
        except Exception as e:
            log.warning("cancel_all_orders failed: %s", e)
            return []
