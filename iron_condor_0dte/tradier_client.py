"""Tradier REST API client — supports both sandbox (paper) and live trading."""
from __future__ import annotations

import logging
import requests
from typing import Any

from .broker_base import BaseBrokerClient

log = logging.getLogger(__name__)

_SANDBOX_URL = "https://sandbox.tradier.com/v1"
_LIVE_URL    = "https://api.tradier.com/v1"


class TradierClient(BaseBrokerClient):
    """Thin wrapper around the Tradier REST API."""

    def __init__(self, token: str, account_id: str, paper: bool = True):
        self.account_id = account_id
        self.paper      = paper
        self.base_url   = _SANDBOX_URL if paper else _LIVE_URL
        self._s = requests.Session()
        self._s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept":        "application/json",
        })
        log.info("TradierClient initialised | %s | account=%s",
                 "SANDBOX" if paper else "LIVE", account_id)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get(self, path: str, **params) -> Any:
        resp = self._s.get(f"{self.base_url}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict) -> Any:
        resp = self._s.post(f"{self.base_url}{path}", data=data, timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Market data ────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Return the latest quote dict for a single symbol (stock or index)."""
        data = self._get("/markets/quotes", symbols=symbol, greeks="false")
        return data["quotes"]["quote"]

    # ── Account ────────────────────────────────────────────────────────────────

    def get_balances(self) -> dict:
        data = self._get(f"/accounts/{self.account_id}/balances")
        return data["balances"]

    def get_positions(self) -> list[dict]:
        data = self._get(f"/accounts/{self.account_id}/positions")
        pos  = data.get("positions", {})
        if not pos or pos == "null":
            return []
        p = pos.get("position", [])
        return p if isinstance(p, list) else [p]

    def get_open_orders(self) -> list[dict]:
        data   = self._get(f"/accounts/{self.account_id}/orders")
        orders = data.get("orders", {})
        if not orders or orders == "null":
            return []
        o = orders.get("order", [])
        o = o if isinstance(o, list) else [o]
        return [x for x in o if x.get("status") in ("open", "partially_filled", "pending")]

    def get_order(self, order_id: str | int) -> dict:
        """Fetch a single order by ID. Returns the order dict."""
        data = self._get(f"/accounts/{self.account_id}/orders/{order_id}")
        return data.get("order", data)

    def get_profile(self) -> dict:
        """Return the user profile dict (contains name, id, account info)."""
        data = self._get("/user/profile")
        return data.get("profile", {})

    # ── Orders ─────────────────────────────────────────────────────────────────

    def place_multileg_order(self, legs: list[dict], qty: int,
                             order_type: str = "market",
                             price: float | None = None) -> dict:
        """
        Place a multi-leg options order.

        legs:       list of dicts — {"symbol": "SPY260527C00750000", "side": "buy_to_open"}
                    side values: buy_to_open | sell_to_open | buy_to_close | sell_to_close
        qty:        contracts per leg
        order_type: "market" (default) | "credit" | "debit" | "limit"
        price:      net credit/debit per share; required when order_type != "market"

        Returns the Tradier order dict (contains "id" and "status").
        """
        # Tradier's actual working multileg format (docs show leg[N][...] but
        # that doesn't parse — the server expects option_symbol[N]/side[N]/quantity[N])
        data = {
            "class":    "multileg",
            "symbol":   "SPY",
            "type":     order_type,
            "duration": "day",
        }
        if price is not None:
            data["price"] = str(round(price, 2))
        for i, leg in enumerate(legs):
            data[f"option_symbol[{i}]"] = leg["symbol"]
            data[f"side[{i}]"]          = leg["side"]
            data[f"quantity[{i}]"]       = qty

        result = self._post(f"/accounts/{self.account_id}/orders", data)
        if "errors" in result:
            raise RuntimeError(f"Tradier order rejected: {result['errors']}")
        return result["order"]

    def cancel_order(self, order_id: str | int) -> dict:
        """Cancel a pending order. Returns the Tradier response dict."""
        resp = self._s.delete(
            f"{self.base_url}/accounts/{self.account_id}/orders/{order_id}",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
