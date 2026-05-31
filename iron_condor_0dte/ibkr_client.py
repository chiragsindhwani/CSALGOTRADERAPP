"""Interactive Brokers (IBKR) API client — connects via IB Gateway or TWS."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

# Initialize event loop for eventkit/ib_insync compatibility
try:
    asyncio.get_running_loop()
except RuntimeError:
    # No running loop; create one if needed for imports
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

from ib_insync import (
    IB,
    Stock,
    Option,
    Contract,
    ComboLeg,
    LimitOrder,
    MarketOrder,
)

from .broker_base import BaseBrokerClient

log = logging.getLogger(__name__)


class IBKRClient(BaseBrokerClient):
    """IBKR trading client using ib_insync library."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        client_id: int = 1,
        account_id: str = "",
        paper: bool = True,
    ):
        """Initialize IBKR connection.

        Args:
            host: IB Gateway/TWS host (default: localhost)
            port: IB Gateway/TWS port (4001 live, 4002 paper; TWS: 7496 live, 7497 paper)
            client_id: client ID for the connection (must be unique)
            account_id: IBKR account number (e.g., "DU1234567")
            paper: whether to use paper trading (not enforced client-side; depends on port)
        """
        self.ib = IB()
        self.account_id = account_id
        self.paper = paper
        try:
            self.ib.connect(host, port, clientId=client_id, readonly=False)
            log.info(
                "IBKRClient connected | host=%s port=%s | account=%s | %s",
                host,
                port,
                account_id,
                "PAPER" if paper else "LIVE",
            )
        except Exception as e:
            log.error("IBKRClient connection failed: %s", e)
            raise

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_occ(occ: str) -> tuple[str, str, str, float]:
        """Parse OCC option symbol into components.

        Example: 'SPY260531P00548000' → ('SPY', '20260531', 'P', 548.0)

        Args:
            occ: OCC symbol string

        Returns:
            (underlying, expiry_YYYYMMDD, right, strike)
        """
        m = re.match(r"([A-Z]+)(\d{6})([CP])(\d{8})", occ)
        if not m:
            raise ValueError(f"Invalid OCC symbol: {occ}")
        underlying = m.group(1)
        expiry = "20" + m.group(2)  # 260531 → 20260531
        right = m.group(3)  # P or C
        strike = int(m.group(4)) / 1000.0  # 00548000 → 548.0
        return underlying, expiry, right, strike

    def _qualify_option(self, occ: str) -> int:
        """Get conId (contract ID) for an OCC symbol.

        Args:
            occ: OCC symbol (e.g., 'SPY260531P00548000')

        Returns:
            conId (int)
        """
        underlying, expiry, right, strike = self._parse_occ(occ)
        opt = Option(underlying, expiry, strike, right, "SMART", currency="USD")
        self.ib.qualifyContracts(opt)
        if opt.conId == 0:
            raise ValueError(f"Could not qualify option: {occ}")
        return opt.conId

    # ── Interface ──────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Fetch market quote for a symbol.

        Args:
            symbol: ticker symbol (e.g., "SPY")

        Returns:
            dict with keys: bid, ask, last (all floats)
        """
        try:
            stk = Stock(symbol, "SMART", "USD")
            self.ib.qualifyContracts(stk)
            ticker = self.ib.reqMktData(stk, "", False, False)
            self.ib.sleep(0.5)
            return {
                "bid": float(ticker.bid or 0),
                "ask": float(ticker.ask or 0),
                "last": float(ticker.last or 0),
            }
        except Exception as e:
            log.warning("get_quote failed for %s: %s", symbol, e)
            return {"bid": 0, "ask": 0, "last": 0}

    def get_profile(self) -> dict:
        """Get account profile info.

        Returns:
            dict with name and account.number
        """
        return {
            "name": f"IBKR Account {self.account_id}",
            "account": {"number": self.account_id},
        }

    def get_order(self, order_id: str | int) -> dict:
        """Get single order status.

        Args:
            order_id: order ID to query

        Returns:
            dict with keys: id, status, avg_fill_price
        """
        status_map = {
            "Submitted": "open",
            "PreSubmitted": "open",
            "PendingSubmit": "open",
            "Filled": "filled",
            "Cancelled": "cancelled",
            "Inactive": "cancelled",
        }
        try:
            order_id_int = int(order_id)
            for trade in self.ib.trades():
                if trade.order.orderId == order_id_int:
                    fill_px = trade.orderStatus.avgFillPrice or 0
                    raw = trade.orderStatus.status
                    return {
                        "id": order_id,
                        "status": status_map.get(raw, "open"),
                        "avg_fill_price": float(fill_px),
                    }
        except Exception as e:
            log.warning("get_order failed for %s: %s", order_id, e)
        return {"id": order_id, "status": "open", "avg_fill_price": 0}

    def place_multileg_order(
        self,
        legs: list[dict],
        qty: int,
        order_type: str = "market",
        price: float | None = None,
    ) -> dict:
        """Place a multi-leg combo order (e.g., Iron Condor).

        Args:
            legs: list of {"symbol": "<OCC>", "side": "buy_to_open|sell_to_open|..."}
            qty: number of contracts
            order_type: "market" or "credit"
            price: limit price for credit orders

        Returns:
            dict with key: id (order_id)

        Raises:
            ValueError: if legs cannot be qualified or order fails
        """
        try:
            # Build BAG (combo) contract
            bag = Contract()
            bag.symbol = "SPY"
            bag.secType = "BAG"
            bag.currency = "USD"
            bag.exchange = "SMART"

            combo_legs = []
            for leg in legs:
                con_id = self._qualify_option(leg["symbol"])
                side = leg["side"]
                action = "SELL" if "sell" in side else "BUY"
                cl = ComboLeg()
                cl.conId = con_id
                cl.ratio = 1
                cl.action = action
                cl.exchange = "SMART"
                combo_legs.append(cl)

            bag.comboLegs = combo_legs

            # Iron Condor is a net credit → SELL direction at combo level
            if order_type == "market":
                order = MarketOrder("SELL", qty)
            else:
                # Credit order: limit price for the credit received
                order = LimitOrder("SELL", qty, abs(price) if price else 0.01)
                order.orderComboLegs = []  # let IBKR route

            trade = self.ib.placeOrder(bag, order)
            self.ib.sleep(0.5)
            log.info("Placed combo order %s | qty=%s | type=%s", trade.order.orderId, qty, order_type)
            return {"id": trade.order.orderId}
        except Exception as e:
            log.error("place_multileg_order failed: %s", e)
            raise

    def cancel_order(self, order_id: str | int) -> dict:
        """Cancel a pending order.

        Args:
            order_id: order ID to cancel

        Returns:
            dict with status
        """
        try:
            order_id_int = int(order_id)
            for trade in self.ib.trades():
                if trade.order.orderId == order_id_int:
                    self.ib.cancelOrder(trade.order)
                    self.ib.sleep(0.5)
                    log.info("Cancelled order %s", order_id)
                    return {"status": "cancelled"}
        except Exception as e:
            log.warning("cancel_order failed for %s: %s", order_id, e)
        return {"status": "not_found"}

    def disconnect(self) -> None:
        """Disconnect from IB Gateway/TWS."""
        try:
            self.ib.disconnect()
            log.info("IBKRClient disconnected")
        except Exception as e:
            log.warning("disconnect error: %s", e)
