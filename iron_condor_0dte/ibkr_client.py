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

    def get_options_chain(self, symbol: str = "SPY", expiration: str = None) -> list:
        """Fetch live options chain from TWS market data.

        Args:
            symbol: underlying symbol (default: "SPY")
            expiration: expiration date (YYYYMMDD format, default: today for 0DTE)

        Returns:
            list of dicts with strike, call data, put data
        """
        try:
            from datetime import datetime

            # Get stock to get current price
            stk = Stock(symbol, "SMART", "USD")
            self.ib.qualifyContracts(stk)
            stk_ticker = self.ib.reqMktData(stk, "", False, False)
            self.ib.sleep(0.2)
            spy_price = float(stk_ticker.last or stk_ticker.close or 0)

            # Get option chains from IBKR
            chains = self.ib.reqSecDefOptParams(symbol, "", "STK", None)
            if not chains:
                log.warning("No option chains found for %s", symbol)
                return []

            # Use first chain (usually the closest expiration)
            chain = chains[0]

            # Determine expiration to use
            if expiration is None:
                # Use today's date for 0DTE
                today = datetime.now().strftime("%Y%m%d")
                expirations = chain.expirations
                exp_to_use = today if today in expirations else (expirations[0] if expirations else None)
            else:
                exp_to_use = expiration

            if not exp_to_use:
                log.warning("No valid expiration found for %s", symbol)
                return []

            # Get strikes
            strikes = chain.strikes

            options_data = []

            # Request market data for calls and puts
            for strike in strikes:
                # Only request nearby strikes (within $20 of price)
                if abs(strike - spy_price) > 20:
                    continue

                call = Option(symbol, exp_to_use, strike, "CALL", "SMART")
                put = Option(symbol, exp_to_use, strike, "PUT", "SMART")

                # Qualify and request market data
                self.ib.qualifyContracts(call, put)
                call_ticker = self.ib.reqMktData(call, "100,101,104,106,107,165,221", False, False)
                put_ticker = self.ib.reqMktData(put, "100,101,104,106,107,165,221", False, False)

                self.ib.sleep(0.1)

                # Extract data from tickers
                strike_data = {
                    "strike": float(strike),
                    "call": {
                        "last": float(call_ticker.last or 0),
                        "bid": float(call_ticker.bid or 0),
                        "ask": float(call_ticker.ask or 0),
                        "volume": int(call_ticker.volume or 0),
                        "openInterest": int(call_ticker.openInterest or 0),
                        "iv": float(call_ticker.impliedVolatility or 0),
                        "delta": float(call_ticker.delta or 0),
                        "gamma": float(call_ticker.gamma or 0),
                        "theta": float(call_ticker.theta or 0),
                        "vega": float(call_ticker.vega or 0),
                    },
                    "put": {
                        "last": float(put_ticker.last or 0),
                        "bid": float(put_ticker.bid or 0),
                        "ask": float(put_ticker.ask or 0),
                        "volume": int(put_ticker.volume or 0),
                        "openInterest": int(put_ticker.openInterest or 0),
                        "iv": float(put_ticker.impliedVolatility or 0),
                        "delta": float(put_ticker.delta or 0),
                        "gamma": float(put_ticker.gamma or 0),
                        "theta": float(put_ticker.theta or 0),
                        "vega": float(put_ticker.vega or 0),
                    },
                }

                options_data.append(strike_data)

            # Cancel market data requests
            for opt_data in options_data:
                # Cleanup (optional - depends on ib_insync behavior)
                pass

            return sorted(options_data, key=lambda x: x["strike"])

        except Exception as e:
            log.error("get_options_chain failed: %s", e)
            return []

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

    def place_futures_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        limit_price: float | None = None,
        expiry: str = "",
    ) -> dict:
        """Place a futures order.

        Args:
            symbol: Futures symbol (e.g., "ES", "NQ", "CL")
            qty: Number of contracts
            side: "buy" or "sell"
            order_type: "market" or "limit"
            limit_price: Limit price (required if order_type="limit")
            expiry: Expiry in format: YYYYMM for MGC, or code for others
                   ES/NQ: Z6=Dec2026, M6=June2026, U6=Sep2026, H6=March2026

        Returns:
            dict with order_id
        """
        try:
            from datetime import datetime

            # Create futures contract with expiry
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "FUT"
            contract.currency = "USD"

            if symbol == "ES" or symbol == "NQ":
                contract.exchange = "CME"
                contract.multiplier = "50" if symbol == "ES" else "20"  # ES multiplier = 50, NQ = 20
                # ES/NQ use month codes: Z=Dec, M=June, U=Sep, H=March
                if not expiry:
                    now = datetime.now()
                    # Use next available contract month
                    # June->U6(Sep), Sep->Z6(Dec), Dec->H7(Mar), Mar->M7(June)
                    month_codes = {
                        1: "H", 2: "H", 3: "M",  # Jan-Mar -> Mar(H)
                        4: "M", 5: "M", 6: "U",  # Apr-Jun -> Sep(U)
                        7: "U", 8: "U", 9: "Z",  # Jul-Sep -> Dec(Z)
                        10: "Z", 11: "Z", 12: "Z"  # Oct-Dec -> Dec(Z)
                    }
                    code = month_codes.get(now.month, "Z")
                    year = str(now.year)[-1]  # Last digit of year
                    expiry = f"{code}{year}"
            elif symbol == "MGC":
                contract.exchange = "COMEX"
                # MGC uses YYYYMM format
                if not expiry:
                    now = datetime.now()
                    month = ((now.month - 1) // 3 + 1) * 3
                    if month <= now.month:
                        month += 3
                    year = now.year if month <= 12 else now.year + 1
                    expiry = f"{year}{month:02d}"
            else:
                contract.exchange = "CME"

            if expiry:
                contract.lastTradeDateOrContractMonth = expiry

            # Place order
            action = "BUY" if side.lower() == "buy" else "SELL"
            if order_type.lower() == "market":
                order = MarketOrder(action, qty)
            else:
                order = LimitOrder(action, qty, limit_price)

            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(0.5)

            order_id = trade.order.orderId
            log.info(
                "Placed futures order %s | %s %s %s (%s) @ %s",
                order_id,
                action,
                qty,
                symbol,
                expiry,
                order_type,
            )
            return {"id": order_id, "status": "submitted"}

        except Exception as e:
            log.error("place_futures_order failed: %s", e)
            raise

    def get_futures_quote(self, symbol: str, expiry: str = "") -> dict:
        """Get futures quote.

        Args:
            symbol: Futures symbol (e.g., "ES", "NQ", "MGC")
            expiry: Expiry format - YYYYMM for MGC, month codes for ES/NQ

        Returns:
            dict with bid, ask, last
        """
        try:
            from datetime import datetime

            contract = Contract()
            contract.symbol = symbol
            contract.secType = "FUT"
            contract.currency = "USD"

            if symbol == "ES" or symbol == "NQ":
                contract.exchange = "CME"
                contract.multiplier = "50" if symbol == "ES" else "20"
                if not expiry:
                    now = datetime.now()
                    month_codes = {
                        1: "H", 2: "H", 3: "M",
                        4: "M", 5: "M", 6: "U",
                        7: "U", 8: "U", 9: "Z",
                        10: "Z", 11: "Z", 12: "Z"
                    }
                    code = month_codes.get(now.month, "Z")
                    year = str(now.year)[-1]
                    expiry = f"{code}{year}"
            elif symbol == "MGC":
                contract.exchange = "COMEX"
                if not expiry:
                    now = datetime.now()
                    month = ((now.month - 1) // 3 + 1) * 3
                    if month <= now.month:
                        month += 3
                    year = now.year if month <= 12 else now.year + 1
                    expiry = f"{year}{month:02d}"
            else:
                contract.exchange = "CME"

            if expiry:
                contract.lastTradeDateOrContractMonth = expiry

            ticker = self.ib.reqMktData(contract)
            self.ib.sleep(1)

            return {
                "bid": float(ticker.bid) if ticker.bid else 0,
                "ask": float(ticker.ask) if ticker.ask else 0,
                "last": float(ticker.last) if ticker.last else 0,
            }
        except Exception as e:
            log.warning("get_futures_quote failed for %s: %s", symbol, e)
            return {"bid": 0, "ask": 0, "last": 0}

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
