"""
Live trading engine for SPY Iron Condor 0DTE using Tradier.

Usage:
    python -m iron_condor_0dte.live_trader

Prerequisites:
    pip install requests yfinance
    Set TRADIER_API_TOKEN, TRADIER_ACCOUNT_ID (and optionally TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID) in your .env file or environment.
    TRADIER_PAPER_TRADE defaults to "true" (sandbox); set to "false" for live.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config, config as default_config
from .options_pricing import (
    find_strike_for_delta,
    iron_condor_credit,
    iron_condor_cost_to_close,
)
from .trade_logger import TradeLogger
from .tradier_client import TradierClient

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# Absolute path to the project root (iron_condor_0dte/../)
_ROOT = Path(__file__).resolve().parent.parent


# ─── Telegram ─────────────────────────────────────────────────────────────────

def _tg_send(message: str) -> None:
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        payload = json.dumps({
            "chat_id": chat_id, "text": message, "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.warning("Telegram send failed: %s", e)


# ─── Market data helpers ───────────────────────────────────────────────────────

def _get_spy_price(client: TradierClient) -> float:
    """Fetch SPY mid-price from Tradier; falls back to yfinance on error."""
    try:
        q    = client.get_quote("SPY")
        bid  = float(q.get("bid",  0) or 0)
        ask  = float(q.get("ask",  0) or 0)
        last = float(q.get("last", 0) or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        if bid > 0:    # ask=0 after hours — use bid directly
            return bid
        if last > 0:
            return last
        raise ValueError(f"unusable Tradier quote bid={bid} ask={ask} last={last}")
    except Exception as e:
        log.warning("Tradier quote unavailable (%s) — yfinance fallback.", e)
        import yfinance as yf
        for _ in range(3):
            try:
                spy = yf.download("SPY", period="1d", interval="1m", progress=False)
                price = float(spy["Close"].iloc[-1])
                if price > 0:
                    return price
            except Exception:
                pass
            time.sleep(2)
        raise RuntimeError("Could not fetch SPY price from Tradier or yfinance.")


def _get_vix_sigma() -> float:
    """Return VIX as a decimal (e.g. 0.18 for VIX=18). Defaults to 0.18."""
    try:
        import yfinance as yf
        vix = yf.download("^VIX", period="2d", interval="1d", progress=False)
        val = float(vix["Close"].iloc[-1].item()) / 100.0
        return val if val > 0 else 0.18
    except Exception:
        return 0.18


def _build_option_symbol(underlying: str, expiry: datetime,
                          strike: float, option_type: str) -> str:
    """OCC symbol, e.g. SPY260519C00749000"""
    yymmdd = expiry.strftime("%y%m%d")
    cp = "C" if option_type.lower() == "call" else "P"
    return f"{underlying}{yymmdd}{cp}{int(round(strike * 1000)):08d}"


def _hours_to_close(now: datetime) -> float:
    """Trading hours remaining until 4:00 PM ET, as a fraction of a trading year."""
    hours_left = max(16.0 - (now.hour + now.minute / 60), 0.0001)
    return hours_left / (252 * 6.5)


# ─── Broker Factory ───────────────────────────────────────────────────────────

def _create_broker(cfg: Config):
    """Create a broker client based on configuration.

    Args:
        cfg: Config object with BROKER selection and credentials

    Returns:
        TradierClient or IBKRClient instance

    Raises:
        ValueError: if BROKER is not 'tradier' or 'ibkr'
    """
    if cfg.BROKER == "ibkr":
        from .ibkr_client import IBKRClient
        return IBKRClient(
            host=cfg.IBKR_HOST,
            port=cfg.IBKR_PORT,
            client_id=cfg.IBKR_CLIENT_ID,
            account_id=cfg.IBKR_ACCOUNT_ID,
            paper=cfg.IBKR_PAPER_TRADE,
        )
    elif cfg.BROKER == "tradier":
        return TradierClient(
            token=cfg.TRADIER_TOKEN or os.getenv("TRADIER_API_TOKEN", ""),
            account_id=cfg.TRADIER_ACCOUNT_ID or os.getenv("TRADIER_ACCOUNT_ID", ""),
            paper=cfg.PAPER_TRADE,
        )
    else:
        raise ValueError(f"Unknown broker: {cfg.BROKER}. Must be 'tradier' or 'ibkr'.")


# ─── Main Trader ──────────────────────────────────────────────────────────────

class IronCondorTrader:
    def __init__(self, cfg: Config = None):
        self.cfg      = cfg or default_config
        self.client   = _create_broker(self.cfg)
        self.position = None   # dict once entered, None when flat

        # Fetch account identity once at startup for Telegram alerts
        try:
            prof = self.client.get_profile()
            self._account_name = prof.get("name", "Unknown")
            acct = prof.get("account", {})
            if isinstance(acct, list):   # multiple sub-accounts → find matching
                acct = next(
                    (a for a in acct if a.get("account_number") == self.client.account_id),
                    acct[0] if acct else {},
                )
            self._account_id = acct.get("account_number", self.client.account_id)
        except Exception as e:
            log.warning("Could not fetch account profile for Telegram header: %s", e)
            self._account_name = "Account"
            self._account_id   = self.client.account_id

        self._last_close_info: dict = {}   # populated by close_position(); read by run_daily()

        # Trade logger — auto-selects CSV (local) or SQLite/PostgreSQL (AWS)
        self._trade_logger = TradeLogger(root_dir=_ROOT)

    # ── Time helpers ──────────────────────────────────────────────────────────

    def is_pre_market(self) -> bool:
        now = datetime.now(ET)
        return now.weekday() < 5 and now.hour < 9

    def is_market_hours(self) -> bool:
        """True between 9:30 AM and 4:00 PM ET, Monday–Friday."""
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        decimal = now.hour + now.minute / 60
        return 9.5 <= decimal < 16.0

    def is_entry_time(self) -> bool:
        now = datetime.now(ET)
        return (now.hour == self.cfg.ENTRY_HOUR and
                self.cfg.ENTRY_MIN <= now.minute < self.cfg.ENTRY_MIN + 15)

    def is_force_close_time(self) -> bool:
        now = datetime.now(ET)
        return (now.hour > self.cfg.FORCE_CLOSE_HOUR or
                (now.hour == self.cfg.FORCE_CLOSE_HOUR and
                 now.minute >= self.cfg.FORCE_CLOSE_MIN))

    # ── Account identity helper ───────────────────────────────────────────────

    def _acct_header(self) -> str:
        """One-line account identifier prepended to every Telegram alert."""
        return (
            f"👤 <b>{self._account_name}</b>  ·  "
            f"<code>#{self._account_id}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
        )

    # ── Fill price helper ─────────────────────────────────────────────────────

    # Terminal statuses that will never become fills
    _TERMINAL_UNFILLED = frozenset({"rejected", "canceled", "expired", "cancel_pending"})

    def _await_fill(self, order_id: str, timeout_sec: int = 120) -> float:
        """
        Poll Tradier until the order is filled or a terminal status is reached.

        Returns avg_fill_price as reported by Tradier:
          - Negative = net credit received (entry order)
          - Positive = net debit paid     (close order)

        Raises RuntimeError if:
          - not filled within timeout_sec seconds, or
          - Tradier reports a terminal non-fill status (rejected/canceled/expired).
        """
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                order = self.client.get_order(order_id)
            except Exception as e:
                # Convert HTTP/network errors into RuntimeError so callers get
                # a consistent exception type regardless of failure mode.
                raise RuntimeError(f"Order {order_id} status poll failed: {e}") from e
            # Tradier sometimes returns a leg sub-order when the parent is queried.
            # Guard: only act on status if the returned id matches what we placed.
            returned_id = str(order.get("id", order_id))
            if returned_id != str(order_id):
                log.warning(
                    "  Order %s poll returned mismatched id=%s — ignoring, re-polling",
                    order_id, returned_id,
                )
                time.sleep(5)
                continue
            status = order.get("status", "")
            if status == "filled":
                fill = float(order.get("avg_fill_price", 0) or 0)
                log.info("  Order %s FILLED | avg_fill_price=%.4f", order_id, fill)
                return fill
            if status in self._TERMINAL_UNFILLED:
                raise RuntimeError(
                    f"Order {order_id} reached terminal status '{status}' — will not fill."
                )
            log.info("  Order %s status=%s — waiting for fill ...", order_id, status)
            time.sleep(5)
        raise RuntimeError(f"Order {order_id} did not fill within {timeout_sec}s")

    # ── Core trade logic ──────────────────────────────────────────────────────

    def enter_trade(self, force_market: bool = False) -> bool:
        """
        Place 4-leg MLEG iron condor via Tradier. Returns True if position was opened.

        Fix C — Two-attempt credit-limit order (default):
          Attempt 1: credit limit = MIN_CREDIT ($0.40/shr), wait 3 min
          Attempt 2: credit limit = MIN_CREDIT × 0.75 ($0.30/shr), wait 2 min
          If neither fills → cancel, send NO-FILL Telegram, return False.

        force_market=True — single market order, no credit floor, 60s fill wait.
          Fix A still applies: abort if actual fill < MIN_ACTUAL_CREDIT.

        Fix A — Post-fill viability check:
          If actual fill < MIN_ACTUAL_CREDIT ($0.10/shr) → immediately flatten
          with a market close order, send ABORTED Telegram, return False.
        """
        now   = datetime.now(ET)
        S     = _get_spy_price(self.client)
        sigma = _get_vix_sigma()
        r     = 0.05
        T     = _hours_to_close(now)

        short_call = round(find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "call"))
        short_put  = round(find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "put"))
        long_call  = short_call + self.cfg.WING_WIDTH
        long_put   = short_put  - self.cfg.WING_WIDTH

        bs_credit = iron_condor_credit(S, short_call, long_call, short_put, long_put, T, r, sigma)
        contracts = self.cfg.CONTRACTS
        # Tradier: $0.35/contract/leg; IC has 4 legs, charged on open AND close
        commission_per_trade = 4 * contracts * 0.35 * 2

        entry_legs = [
            {"symbol": _build_option_symbol("SPY", now, long_call,  "call"), "side": "buy_to_open"},
            {"symbol": _build_option_symbol("SPY", now, short_call, "call"), "side": "sell_to_open"},
            {"symbol": _build_option_symbol("SPY", now, long_put,   "put"),  "side": "buy_to_open"},
            {"symbol": _build_option_symbol("SPY", now, short_put,  "put"),  "side": "sell_to_open"},
        ]

        log.info(
            "Entering IC | SPY=%.2f | P%d/%d | C%d/%d | B-S Credit=$%.4f/shr ($%.2f/contract) | Contracts=%d",
            S, long_put, short_put, short_call, long_call, bs_credit, bs_credit * 100, contracts,
        )

        filled_order_id: str        = ""
        actual_fill_price: float | None = None

        # ── Market order path (force_market=True) ─────────────────────────────
        if force_market:
            log.info("  [Market order] Placing market MLEG order (no credit floor) | timeout=60s")
            try:
                order = self.client.place_multileg_order(
                    entry_legs, qty=contracts, order_type="market"
                )
                oid = str(order.get("id"))
                log.info("  MLEG market order accepted | id=%s", oid)
                actual_fill_price = self._await_fill(oid, timeout_sec=60)
                filled_order_id   = oid
                log.info("  Market order filled | avg_fill_price=%.4f", actual_fill_price)
            except RuntimeError as e:
                log.warning("  Market order failed: %s", e)
                _tg_send(
                    self._acct_header() +
                    f"⚠️ <b>MARKET ORDER FAILED</b>\n{e}"
                )
                return False

        else:
        # ── FIX C: Three-attempt credit-limit order ───────────────────────────
            LIMIT1   = round(self.cfg.MIN_CREDIT, 2)            # e.g. $0.35/shr
            LIMIT2   = round(self.cfg.MIN_CREDIT * 0.75, 2)    # e.g. $0.26/shr
            LIMIT3   = 0.20                                      # $0.20/shr
            ATTEMPTS = [(LIMIT1, 180), (LIMIT2, 120), (LIMIT3, 180)]  # (price, timeout_sec)
            skip_reasons = {}

            for attempt, (limit, timeout) in enumerate(ATTEMPTS, start=1):
                oid: str | None = None
                try:
                    log.info(
                        "  [Attempt %d/%d] Credit limit order: $%.2f/shr | timeout=%ds",
                        attempt, len(ATTEMPTS), limit, timeout,
                    )
                    order = self.client.place_multileg_order(
                        entry_legs, qty=contracts, order_type="credit", price=limit
                    )
                    oid = str(order.get("id"))
                    log.info("  MLEG entry order accepted | id=%s", oid)

                    actual_fill_price = self._await_fill(oid, timeout_sec=timeout)
                    filled_order_id   = oid
                    log.info(
                        "  Filled on attempt %d | avg_fill_price=%.4f", attempt, actual_fill_price
                    )
                    break   # filled — exit the attempt loop

                except RuntimeError as e:
                    error_msg = str(e)
                    skip_reasons[attempt] = error_msg
                    log.warning("  Attempt %d failed: %s", attempt, error_msg)
                    # Log this failed attempt to CSV
                    today = now.strftime("%Y-%m-%d")
                    skip_reason = f"Attempt {attempt} timeout/no fill: limit=${limit:.2f}/shr, timeout={timeout}s"
                    self._trade_logger.log_skipped_trade(today, skip_reason, attempt_num=attempt)
                    # Cancel the unfilled order before trying the next limit
                    if oid and not filled_order_id:
                        try:
                            self.client.cancel_order(oid)
                            log.info("  Cancelled unfilled order %s", oid)
                        except Exception as ce:
                            log.warning("  Could not cancel order %s: %s", oid, ce)

        if actual_fill_price is None:
            # Both attempts exhausted — no fill (limit-order path only)
            log.warning("No fill after %d attempts — skipping entry.", len(ATTEMPTS))
            _tg_send(
                self._acct_header() +
                f"⚠️ <b>NO FILL — ENTRY SKIPPED</b>\n"
                f"━━━━━━━━━\n"
                f"SPY Price   : ${S:.2f}\n"
                f"Put Spread  : ${long_put:.0f} / ${short_put:.0f}\n"
                f"Call Spread : ${short_call:.0f} / ${long_call:.0f}\n"
                f"Limits tried: ${LIMIT1:.2f} -> ${LIMIT2:.2f} (per shr)\n"
                f"B-S est credit: ${bs_credit * 100:.2f} / contract\n"
                f"Time        : {now.strftime('%I:%M %p ET')}\n"
                f"Market too wide or illiquid -- no trade today."
            )
            return False

        # Entry MLEG: avg_fill_price is negative (net credit received per share).
        actual_credit = abs(actual_fill_price)

        log.info(
            "  Actual credit $%.4f/shr ($%.2f total) vs B-S est $%.4f/shr",
            actual_credit, actual_credit * 100 * contracts, bs_credit,
        )

        # ── FIX A: Post-fill viability check ─────────────────────────────────
        if actual_credit < self.cfg.MIN_ACTUAL_CREDIT:
            log.warning(
                "  ABORT: actual credit $%.4f/shr < MIN_ACTUAL_CREDIT $%.4f/shr — "
                "flattening position immediately.",
                actual_credit, self.cfg.MIN_ACTUAL_CREDIT,
            )
            # Flatten with a market close order
            try:
                close_legs = [
                    {"symbol": _build_option_symbol("SPY", now, long_call,  "call"), "side": "sell_to_close"},
                    {"symbol": _build_option_symbol("SPY", now, short_call, "call"), "side": "buy_to_close"},
                    {"symbol": _build_option_symbol("SPY", now, long_put,   "put"),  "side": "sell_to_close"},
                    {"symbol": _build_option_symbol("SPY", now, short_put,  "put"),  "side": "buy_to_close"},
                ]
                abort_order = self.client.place_multileg_order(close_legs, qty=contracts)
                abort_oid   = str(abort_order.get("id"))
                log.info("  Abort market-close order placed | id=%s", abort_oid)
                try:
                    close_fill = self._await_fill(abort_oid, timeout_sec=120)
                    abort_cost = abs(close_fill)
                    abort_pnl  = round((actual_credit - abort_cost) * 100 * contracts, 2)
                    log.info("  Abort close filled | cost=$%.4f/shr | round-trip P&L=$%.2f",
                             abort_cost, abort_pnl)
                except RuntimeError as e:
                    log.warning("  Abort close fill not confirmed: %s", e)
                    abort_pnl = 0.0
            except Exception as e:
                log.error("  Abort flatten order failed: %s", e)
                abort_pnl = 0.0

            _tg_send(
                self._acct_header() +
                f"🚫 <b>ENTRY ABORTED — CREDIT TOO LOW</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📈 SPY Price      : ${S:.2f}\n"
                f"📉 Put Spread     : ${long_put:.0f} / ${short_put:.0f}\n"
                f"📈 Call Spread    : ${short_call:.0f} / ${long_call:.0f}\n"
                f"💵 Actual Fill    : ${actual_credit * 100:.2f} / contract\n"
                f"🔴 Min Required   : ${self.cfg.MIN_ACTUAL_CREDIT * 100:.2f} / contract\n"
                f"💸 Round-trip P&L : ${abort_pnl:+.2f} (incl. slippage)\n"
                f"🏛️ Commission     : -${commission_per_trade:.2f}\n"
                f"⏰ Time           : {now.strftime('%I:%M %p ET')}\n"
                f"ℹ️ Position flattened — no trade recorded."
            )
            return False

        # ── Position viable — store and notify ───────────────────────────────
        log.info("  PT(15%%)=$%.2f  SL(45%%)=$%.2f  (based on actual credit $%.4f/shr)",
                 actual_credit * self.cfg.PROFIT_TARGET_PCT * 100 * contracts,
                 actual_credit * self.cfg.STOP_LOSS_MULT    * 100 * contracts,
                 actual_credit)

        self.position = {
            "short_call":      short_call,   "long_call":      long_call,
            "short_put":       short_put,    "long_put":       long_put,
            "credit":          bs_credit,    "actual_credit":  actual_credit,
            "contracts":       contracts,
            "sigma":           sigma,        "order_id":       filled_order_id,
            "entry_time":      now.strftime("%H:%M ET"),
            "commission":      commission_per_trade,
            "spy_price_entry": S,            # capture SPY price at entry for trade log
        }

        capital_used = (self.cfg.WING_WIDTH - actual_credit) * 100 * contracts
        _tg_send(
            self._acct_header() +
            f"🟢 <b>IRON CONDOR OPENED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📈 SPY Price      : ${S:.2f}\n"
            f"📉 Put Spread     : ${long_put:.0f} / ${short_put:.0f}\n"
            f"📈 Call Spread    : ${short_call:.0f} / ${long_call:.0f}\n"
            f"💵 Credit (Actual): ${actual_credit * 100:.2f} / contract\n"
            f"💵 Credit (B-S est): ${bs_credit * 100:.2f} / contract\n"
            f"📦 Contracts      : {contracts}\n"
            f"💰 Total Credit   : ${actual_credit * 100 * contracts:.2f}\n"
            f"🏦 Capital Used   : ${capital_used:,.2f}  (max risk)\n"
            f"📊 Return/Capital : {(actual_credit * 100 * contracts / capital_used * 100):.1f}%\n"
            f"🎯 Profit Target (15%): ${actual_credit * self.cfg.PROFIT_TARGET_PCT * 100 * contracts:.2f}\n"
            f"🛑 Stop Loss (45%)    : ${actual_credit * self.cfg.STOP_LOSS_MULT * 100 * contracts:.2f}\n"
            f"⏰ Entry Time     : {now.strftime('%I:%M %p ET')}"
        )
        return True

    def close_position(self, reason: str, pnl_estimate: float = 0.0) -> tuple[float, float]:
        """
        Submit MLEG close order via Tradier and clear self.position.

        Awaits the actual close fill, then computes gross P&L from real entry and
        exit fill prices.  Falls back to pnl_estimate if fill confirmation times out.

        Returns (gross_pnl, net_pnl).
        """
        if not self.position:
            return 0.0, 0.0

        p              = self.position
        actual_credit  = p.get("actual_credit", p["credit"])
        commission     = p.get("commission", 4 * p["contracts"] * 0.35 * 2)

        emoji  = {"profit_target": "✅", "stop_loss": "🛑", "force_close": "⏱️"}.get(reason, "🔴")
        label  = {
            "profit_target": "PROFIT TARGET HIT",
            "stop_loss":     "STOP LOSS HIT",
            "force_close":   "FORCE CLOSE (3:45 PM)",
        }.get(reason, reason.replace("_", " ").upper())

        log.info("Closing position | reason=%s | P&L estimate=$%.2f", reason, pnl_estimate)

        today          = datetime.now(ET)
        gross_pnl      = pnl_estimate   # replaced with actual once fill confirmed
        close_order_id = None
        actual_exit_cost: float | None = None   # per-share close fill (for trade logger)

        try:
            order = self.client.place_multileg_order([
                {"symbol": _build_option_symbol("SPY", today, p["long_call"],  "call"), "side": "sell_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["short_call"], "call"), "side": "buy_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["long_put"],   "put"),  "side": "sell_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["short_put"],  "put"),  "side": "buy_to_close"},
            ], qty=p["contracts"])
            close_order_id = str(order.get("id"))
            log.info("  MLEG close order accepted | id=%s", close_order_id)
        except Exception as e:
            log.error("  MLEG close order failed: %s", e)

        # ── Fetch actual close fill price and compute real P&L ────────────────
        # Close MLEG: avg_fill_price is positive (net debit paid to close).
        if close_order_id:
            try:
                close_fill  = self._await_fill(close_order_id, timeout_sec=120)
                actual_cost = abs(close_fill) if close_fill != 0 else None
                if actual_cost is not None:
                    actual_exit_cost = actual_cost
                    gross_pnl = round(
                        (actual_credit - actual_cost) * 100 * p["contracts"], 2
                    )
                    log.info(
                        "  ⚡ Actual P&L: entry=$%.4f/shr close=$%.4f/shr gross=$%.2f",
                        actual_credit, actual_cost, gross_pnl,
                    )
            except RuntimeError as e:
                log.warning("  Close fill confirmation timeout (%s) — using estimate.", e)

        net_pnl      = round(gross_pnl - commission, 2)
        capital_used = (self.cfg.WING_WIDTH - actual_credit) * 100 * p["contracts"]
        roi          = (net_pnl / capital_used * 100) if capital_used > 0 else 0.0

        # Store close details so run_daily() can send ONE combined alert
        # and _log_forward_test() can write the full trade record.
        self._last_close_info = {
            # Telegram alert fields
            "emoji":           emoji,
            "label":           label,
            "close_time":      today.strftime("%I:%M %p ET"),
            "capital_used":    capital_used,
            "roi":             roi,
            # P&L
            "gross_pnl":       gross_pnl,
            "net_pnl":         net_pnl,
            "commission":      commission,
            # Position details
            "long_put":        p["long_put"],
            "short_put":       p["short_put"],
            "short_call":      p["short_call"],
            "long_call":       p["long_call"],
            "contracts":       p["contracts"],
            # Fill prices
            "actual_credit":   actual_credit,
            "bs_credit":       p.get("credit"),          # B-S estimate at entry
            "exit_cost":       actual_exit_cost,
            # Extra context for trade logger
            "entry_time":      p.get("entry_time"),
            "entry_order_id":  p.get("order_id"),
            "exit_order_id":   close_order_id,
            "vix_sigma":       p.get("sigma"),
            "spy_price_entry": p.get("spy_price_entry"),
        }
        log.info("Position closed | reason=%s | gross=$%.2f | net=$%.2f",
                 reason, gross_pnl, net_pnl)

        self.position = None
        return gross_pnl, net_pnl

    def check_exits(self) -> tuple[bool, float]:
        """
        Evaluate profit target and stop loss against the current theoretical cost to close.
        Uses actual_credit (real fill) as reference for thresholds and P&L estimation.

        Returns (closed, gross_pnl). closed=True if position was just closed.
        gross_pnl reflects actual fills once close_position() confirms the exit fill.
        """
        if not self.position:
            return False, 0.0

        p = self.position
        try:
            now    = datetime.now(ET)
            S      = _get_spy_price(self.client)
            T      = _hours_to_close(now)
            cost   = iron_condor_cost_to_close(
                S, p["short_call"], p["long_call"],
                p["short_put"],  p["long_put"],
                T, 0.05, p["sigma"]
            )
            # PT/SL thresholds are % moves of the B-S theoretical value at entry.
            # Using actual_credit (fill) as the reference breaks when fill < B-S
            # (e.g. limit fill at $0.40 vs B-S $0.78 → cost already exceeds SL).
            bs_credit    = p["credit"]                          # B-S at entry
            actual_credit = p.get("actual_credit", bs_credit)  # real fill
            pnl_est = (actual_credit - cost) * 100 * p["contracts"]
            log.info("SPY=%.2f | cost=%.4f | bs_ref=%.4f | actual_credit=%.4f | est P&L=$%.2f",
                     S, cost, bs_credit, actual_credit, pnl_est)

            if cost <= bs_credit * (1 - self.cfg.PROFIT_TARGET_PCT):
                gross, _ = self.close_position("profit_target", pnl_est)
                return True, gross
            elif cost >= bs_credit * (1 + self.cfg.STOP_LOSS_MULT):
                gross, _ = self.close_position("stop_loss", pnl_est)
                return True, gross

        except Exception as e:
            log.error("Exit check error: %s", e)

        return False, 0.0

    # ── Forward test logging ──────────────────────────────────────────────────

    def _log_forward_test(self, outcome: str, pnl: float, credit: float) -> None:
        log_path = _ROOT / "CS_ALGOTRADER_APP" / "forward_test_results.json"
        results  = []
        if log_path.exists():
            try:
                results = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                results = []

        today      = datetime.now(ET).strftime("%Y-%m-%d")
        commission = self.position["commission"] if self.position else 4 * self.cfg.CONTRACTS * 0.35 * 2
        net_pnl    = round(pnl - commission, 2)
        existing   = next((r for r in results if r["date"] == today), None)
        entry = {
            "date":             today,
            "outcome":          outcome,
            "gross_pnl":        round(pnl, 2),
            "commission":       round(commission, 2),
            "pnl":              net_pnl,
            "credit_collected": round(credit * 100 * self.cfg.CONTRACTS, 2),
            "contracts":        self.cfg.CONTRACTS,
            "cumulative_pnl":   0.0,
        }
        if existing:
            existing.update(entry)
        else:
            results.append(entry)

        cum = 0.0
        for r in sorted(results, key=lambda x: x["date"]):
            cum += r["pnl"]
            r["cumulative_pnl"] = round(cum, 2)

        log_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        self._write_forward_test_js(results)
        log.info("Forward test updated: %s | Gross=$%.2f | Commission=$%.2f | Net=$%.2f | Cum=$%.2f",
                 today, pnl, commission, net_pnl, cum)

        # ── Persist to CSV (local) or SQLite/PostgreSQL (AWS) ─────────────────
        ci = self._last_close_info   # populated by close_position()
        trade_record = {
            "date":             today,
            "environment":      "SANDBOX" if self.cfg.PAPER_TRADE else "LIVE",
            "account_id":       self._account_id,
            "account_name":     self._account_name,
            "symbol":           self.cfg.SYMBOL,
            "strategy":         "Iron Condor 0DTE",
            "contracts":        self.cfg.CONTRACTS,
            "long_put":         ci.get("long_put"),
            "short_put":        ci.get("short_put"),
            "short_call":       ci.get("short_call"),
            "long_call":        ci.get("long_call"),
            "wing_width":       self.cfg.WING_WIDTH,
            "entry_time":       ci.get("entry_time"),
            "exit_time":        ci.get("close_time"),
            "outcome":          outcome,
            "entry_order_id":   ci.get("entry_order_id"),
            "exit_order_id":    ci.get("exit_order_id"),
            "entry_credit":     ci.get("actual_credit"),          # per-share actual fill
            "bs_credit":        ci.get("bs_credit"),              # per-share B-S estimate
            "exit_cost":        ci.get("exit_cost"),              # per-share close fill
            "gross_pnl":        round(pnl, 2),
            "commission":       round(commission, 2),
            "net_pnl":          net_pnl,
            "cumulative_pnl":   round(cum, 2),
            "vix_sigma":        ci.get("vix_sigma"),
            "spy_price_entry":  ci.get("spy_price_entry"),
            "notes":            ci.get("notes", ""),
        }
        self._trade_logger.log_trade(trade_record)

    def _write_forward_test_js(self, results: list) -> None:
        js_path = _ROOT / "CS_ALGOTRADER_APP" / "forward_test_data.js"
        payload = {
            "start_date":       "2026-05-18",
            "end_date":         "2026-05-29",
            "target_daily_pnl": 203.0,
            "results":          results,
            "generated_at":     datetime.now(timezone.utc).isoformat(),
        }
        js_path.write_text(
            "window.FORWARD_TEST_DATA = " + json.dumps(payload) + ";",
            encoding="utf-8",
        )

    # ── PDT (Pattern Day Trader) tracking ────────────────────────────────────

    _PDT_PATH = _ROOT / "pdt_trades.json"

    def _pdt_window_dates(self) -> list[str]:
        """Return the last PDT_WINDOW_DAYS business-day date strings including today."""
        dates, d = [], datetime.now(ET).date()
        while len(dates) < self.cfg.PDT_WINDOW_DAYS:
            if d.weekday() < 5:   # Mon–Fri
                dates.append(d.isoformat())
            d -= timedelta(days=1)
        return dates

    def _pdt_trade_count(self) -> int:
        """Count completed day-trade round-trips in the rolling 5-business-day window."""
        if not self._PDT_PATH.exists():
            return 0
        try:
            records = json.loads(self._PDT_PATH.read_text(encoding="utf-8"))
        except Exception:
            return 0
        window = set(self._pdt_window_dates())
        return sum(1 for r in records if r.get("date") in window)

    def _record_day_trade(self) -> None:
        """Append today to the PDT round-trip log."""
        try:
            records = (json.loads(self._PDT_PATH.read_text(encoding="utf-8"))
                       if self._PDT_PATH.exists() else [])
        except Exception:
            records = []
        today = datetime.now(ET).strftime("%Y-%m-%d")
        if not any(r["date"] == today for r in records):
            records.append({"date": today, "ts": datetime.now(ET).isoformat()})
            self._PDT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
            log.info("PDT: recorded day trade for %s", today)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run_daily(self) -> None:
        try:
            log.info("=== SPY Iron Condor 0DTE — Daily Session Started ===")

            # If started pre-market, wait until 9:00 AM ET
            while self.is_pre_market():
                now = datetime.now(ET)
                log.info("Pre-market — waiting for 9:00 AM ET (now %s ET)",
                         now.strftime("%H:%M"))
                time.sleep(60)

            now = datetime.now(ET)
            if not self.is_market_hours():
                log.info("Market not open (now %s ET, weekday=%d). Session complete.",
                         now.strftime("%H:%M"), now.weekday())
                today = now.strftime("%Y-%m-%d")
                self._trade_logger.log_skipped_trade(today, "Market closed or weekend", attempt_num=0)
                _tg_send(
                    self._acct_header() +
                    f"⏭️ <b>SESSION SKIPPED — {now.strftime('%Y-%m-%d')}</b>\n"
                    "Market closed or weekend."
                )
                return

            # ── PDT guard ─────────────────────────────────────────────────────────
            dt_used = self._pdt_trade_count()
            if dt_used >= self.cfg.PDT_MAX_DAY_TRADES:
                today = now.strftime("%Y-%m-%d")
                pdt_reason = f"PDT limit reached: {dt_used}/{self.cfg.PDT_MAX_DAY_TRADES} day trades used in rolling {self.cfg.PDT_WINDOW_DAYS}-day window"
                self._trade_logger.log_skipped_trade(today, pdt_reason, attempt_num=0)
                msg = (
                    self._acct_header() +
                    f"⚠️ <b>PDT LIMIT — NO TRADE {now.strftime('%Y-%m-%d')}</b>\n"
                    f"Day trades used: {dt_used}/{self.cfg.PDT_MAX_DAY_TRADES} "
                    f"in rolling {self.cfg.PDT_WINDOW_DAYS}-day window.\n"
                    f"Resuming when oldest trade drops off window."
                )
                log.info("PDT limit reached (%d/%d). Skipping today.", dt_used, self.cfg.PDT_MAX_DAY_TRADES)
                _tg_send(msg)
                return
            log.info("PDT: %d/%d day trades used in rolling window. Proceeding.",
                     dt_used, self.cfg.PDT_MAX_DAY_TRADES)

            # Flush logs to ensure parent process receives output
            import sys
            sys.stdout.flush()
            sys.stderr.flush()

            entered        = False
            session_pnl    = 0.0
            session_credit = 0.0
            close_reason   = "no_trade"

            log.info("Starting main trading loop...")
            while True:
                now = datetime.now(ET)

                # ── Market closed ─────────────────────────────────────────────────
                if not self.is_market_hours():
                    log.info("Market closed at %s ET. Session complete.", now.strftime("%H:%M"))
                    break

                # ── Force close at 3:45 PM ────────────────────────────────────────
                if self.position and self.is_force_close_time():
                    p = self.position
                    try:
                        S       = _get_spy_price(self.client)
                        T       = _hours_to_close(now)
                        cost    = iron_condor_cost_to_close(
                            S, p["short_call"], p["long_call"],
                            p["short_put"],  p["long_put"],
                            T, 0.05, p["sigma"]
                        )
                        actual_credit = p.get("actual_credit", p["credit"])
                        pnl_est = (actual_credit - cost) * 100 * p["contracts"]
                    except Exception as e:
                        log.error("Force-close P&L estimate failed: %s", e)
                        pnl_est = 0.0
                    gross, _    = self.close_position("force_close", pnl_est)
                    session_pnl = gross
                    self._record_day_trade()
                    close_reason = "force_close"
                    break

                # ── Entry window: 10:15–10:29 AM ─────────────────────────────────
                if not entered and not self.position:
                    entry_time_check = self.is_entry_time()
                    log.debug("Entry time check at %s ET: %s", now.strftime("%H:%M:%S"), entry_time_check)
                    if entry_time_check:
                        log.info("ENTRY WINDOW ACTIVE - Attempting entry...")
                        try:
                            success = self.enter_trade()
                            entered = True
                            if success and self.position:
                                # Use actual fill credit for session tracking
                                session_credit = self.position.get("actual_credit",
                                                                   self.position["credit"])
                        except Exception as e:
                            log.error("enter_trade raised an unexpected error: %s", e, exc_info=True)
                            entered = True   # prevent retry loop

                # ── Monitor open position ─────────────────────────────────────────
                if self.position:
                    closed, pnl = self.check_exits()
                    if closed:
                        session_pnl  = pnl   # actual gross P&L from close_position()
                        close_reason = "exit"
                        self._record_day_trade()
                        break   # done for the day

                # Sleep until next check cycle (every minute)
                log.debug("Sleeping until next check (%.2f hours to close)...", _hours_to_close(now))
                time.sleep(60)

            # ── End-of-session logging ────────────────────────────────────────────
            if entered and session_credit > 0:
                self._log_forward_test(close_reason, session_pnl, session_credit)
                ci        = self._last_close_info           # set by close_position()
                net_pnl   = ci.get("net_pnl", session_pnl - (ci.get("commission", 0)))
                pnl_emoji = "💰" if net_pnl >= 0 else "📉"
                close_lbl = ci.get("label", close_reason.replace("_", " ").title())
                _tg_send(
                    self._acct_header() +
                    f"{pnl_emoji} <b>SESSION COMPLETE — {datetime.now(ET).strftime('%Y-%m-%d')}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 Outcome     : {close_lbl}\n"
                    + (f"📉 Put Spread  : ${ci['long_put']:.0f} / ${ci['short_put']:.0f}\n"
                       f"📈 Call Spread : ${ci['short_call']:.0f} / ${ci['long_call']:.0f}\n"
                       if ci.get("long_put") else "") +
                    f"⏰ Close Time  : {ci.get('close_time', '—')}\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Credit Rcvd : ${ci.get('actual_credit', session_credit) * 100:.2f} / contract\n"
                    f"📦 Contracts   : {ci.get('contracts', self.cfg.CONTRACTS)}\n"
                    f"🏦 Capital Used: ${ci.get('capital_used', 0):,.2f}  (max risk)\n"
                    f"💰 Gross P&L   : ${session_pnl:+.2f}\n"
                    f"🏛️ Commission  : -${ci.get('commission', 0):.2f}\n"
                    f"✅ Net P&L     : ${net_pnl:+.2f}\n"
                    f"📊 ROI on Capital: {ci.get('roi', 0):+.2f}%\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 Daily Target: $203.00  "
                    + ("✅ TARGET MET" if net_pnl >= 203 else "⚠️ Below target")
                )
            elif not entered:
                today = datetime.now(ET).strftime("%Y-%m-%d")
                self._trade_logger.log_skipped_trade(today, "Entry window passed with no trade attempt (market or data issue)", attempt_num=0)
                _tg_send(
                    self._acct_header() +
                    f"⏭️ <b>SESSION SKIPPED — {today}</b>\n"
                    "Entry window passed with no trade (market or data issue)."
                )

            log.info("=== Daily Session Complete | P&L=$%.2f | Reason=%s ===",
                     session_pnl, close_reason)
        except Exception as e:
            log.error("CRITICAL: Session crashed with exception: %s", e, exc_info=True)
            import traceback
            traceback.print_exc()
            _tg_send(
                self._acct_header() +
                f"[CRITICAL ERROR]\nSession crashed: {str(e)}\n\nCheck logs for details."
            )
        finally:
            # Disconnect broker client (IBKR needs explicit disconnect; Tradier is no-op)
            if hasattr(self.client, "disconnect"):
                try:
                    self.client.disconnect()
                except Exception as e:
                    log.warning("Broker disconnect error: %s", e)


if __name__ == "__main__":
    _log_dir = _ROOT / "logs"
    _log_dir.mkdir(exist_ok=True)
    _session_log = _log_dir / f"session_{datetime.now(ET).strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(_session_log, mode="w", encoding="utf-8"),
        ],
    )
    log.info("Log file: %s", _session_log)
    IronCondorTrader().run_daily()
