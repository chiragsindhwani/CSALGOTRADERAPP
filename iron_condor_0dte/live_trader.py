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
        val = float(vix["Close"].iloc[-1]) / 100.0
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


# ─── Main Trader ──────────────────────────────────────────────────────────────

class IronCondorTrader:
    def __init__(self, cfg: Config = None):
        self.cfg      = cfg or default_config
        self.client   = TradierClient(
            token=self.cfg.TRADIER_TOKEN or os.getenv("TRADIER_API_TOKEN", ""),
            account_id=self.cfg.TRADIER_ACCOUNT_ID or os.getenv("TRADIER_ACCOUNT_ID", ""),
            paper=self.cfg.PAPER_TRADE,
        )
        self.position = None   # dict once entered, None when flat

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

    # ── Core trade logic ──────────────────────────────────────────────────────

    def enter_trade(self) -> bool:
        """Place 4-leg MLEG iron condor via Tradier. Returns True if position opened."""
        now   = datetime.now(ET)
        S     = _get_spy_price(self.client)
        sigma = _get_vix_sigma()
        r     = 0.05
        T     = _hours_to_close(now)

        short_call = round(find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "call"))
        short_put  = round(find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "put"))
        long_call  = short_call + self.cfg.WING_WIDTH
        long_put   = short_put  - self.cfg.WING_WIDTH

        credit    = iron_condor_credit(S, short_call, long_call, short_put, long_put, T, r, sigma)
        contracts = self.cfg.CONTRACTS
        # Tradier: $0.35/contract/leg; IC has 4 legs, charged on open AND close
        commission_per_trade = 4 * contracts * 0.35 * 2

        if credit < self.cfg.MIN_CREDIT:
            log.warning("Credit $%.2f below minimum $%.2f — skipping entry.",
                        credit * 100, self.cfg.MIN_CREDIT * 100)
            return False

        log.info("Entering IC | SPY=%.2f | P%d/%d | C%d/%d | Credit=$%.2f | Contracts=%d",
                 S, long_put, short_put, short_call, long_call, credit * 100, contracts)
        log.info("  PT(15%%)=$%.2f  SL(45%%)=$%.2f",
                 credit * self.cfg.PROFIT_TARGET_PCT * 100 * contracts,
                 credit * self.cfg.STOP_LOSS_MULT    * 100 * contracts)

        order = self.client.place_multileg_order([
            {"symbol": _build_option_symbol("SPY", now, long_call,  "call"), "side": "buy_to_open"},
            {"symbol": _build_option_symbol("SPY", now, short_call, "call"), "side": "sell_to_open"},
            {"symbol": _build_option_symbol("SPY", now, long_put,   "put"),  "side": "buy_to_open"},
            {"symbol": _build_option_symbol("SPY", now, short_put,  "put"),  "side": "sell_to_open"},
        ], qty=contracts)
        log.info("  MLEG entry order accepted | id=%s", order.get("id"))

        self.position = {
            "short_call":  short_call, "long_call": long_call,
            "short_put":   short_put,  "long_put":  long_put,
            "credit":      credit,     "contracts": contracts,
            "sigma":       sigma,      "order_id":  str(order.get("id")),
            "entry_time":  now.strftime("%H:%M ET"),
            "commission":  commission_per_trade,
        }

        capital_used = (self.cfg.WING_WIDTH - credit) * 100 * contracts
        _tg_send(
            f"🟢 <b>IRON CONDOR OPENED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📈 SPY Price   : ${S:.2f}\n"
            f"📉 Put Spread  : ${long_put:.0f} / ${short_put:.0f}\n"
            f"📈 Call Spread : ${short_call:.0f} / ${long_call:.0f}\n"
            f"💵 Credit      : ${credit * 100:.2f} / contract\n"
            f"📦 Contracts   : {contracts}\n"
            f"💰 Total Credit: ${credit * 100 * contracts:.2f}\n"
            f"🏦 Capital Used: ${capital_used:,.2f}  (max risk)\n"
            f"📊 Return/Capital: {(credit * 100 * contracts / capital_used * 100):.1f}%\n"
            f"🎯 Profit Target (15%): ${credit * self.cfg.PROFIT_TARGET_PCT * 100 * contracts:.2f}\n"
            f"🛑 Stop Loss (45%)    : ${credit * self.cfg.STOP_LOSS_MULT * 100 * contracts:.2f}\n"
            f"⏰ Entry Time  : {now.strftime('%I:%M %p ET')}"
        )
        return True

    def close_position(self, reason: str, pnl: float = 0.0) -> None:
        """Submit MLEG close order via Tradier and clear self.position."""
        if not self.position:
            return

        p      = self.position
        emoji  = {"profit_target": "✅", "stop_loss": "🛑", "force_close": "⏱️"}.get(reason, "🔴")
        label  = {
            "profit_target": "PROFIT TARGET HIT",
            "stop_loss":     "STOP LOSS HIT",
            "force_close":   "FORCE CLOSE (3:45 PM)",
        }.get(reason, reason.replace("_", " ").upper())

        log.info("Closing position | reason=%s | P&L=$%.2f", reason, pnl)

        today = datetime.now(ET)
        try:
            order = self.client.place_multileg_order([
                {"symbol": _build_option_symbol("SPY", today, p["long_call"],  "call"), "side": "sell_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["short_call"], "call"), "side": "buy_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["long_put"],   "put"),  "side": "sell_to_close"},
                {"symbol": _build_option_symbol("SPY", today, p["short_put"],  "put"),  "side": "buy_to_close"},
            ], qty=p["contracts"])
            log.info("  MLEG close order accepted | id=%s", order.get("id"))
        except Exception as e:
            log.error("  MLEG close order failed: %s", e)

        commission   = p.get("commission", 4 * p["contracts"] * 0.35 * 2)
        net_pnl      = pnl - commission
        capital_used = (self.cfg.WING_WIDTH - p["credit"]) * 100 * p["contracts"]
        roi          = (net_pnl / capital_used * 100) if capital_used > 0 else 0.0
        _tg_send(
            f"{emoji} <b>IRON CONDOR CLOSED — {label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📉 Put Spread  : ${p['long_put']:.0f} / ${p['short_put']:.0f}\n"
            f"📈 Call Spread : ${p['short_call']:.0f} / ${p['long_call']:.0f}\n"
            f"💵 Credit Rcvd : ${p['credit'] * 100:.2f} / contract\n"
            f"📦 Contracts   : {p['contracts']}\n"
            f"🏦 Capital Used: ${capital_used:,.2f}  (max risk)\n"
            f"💰 Gross P&L   : ${pnl:+.2f}\n"
            f"🏛️ Commission  : -${commission:.2f}\n"
            f"✅ Net P&L     : ${net_pnl:+.2f}\n"
            f"📊 ROI on Capital: {roi:+.2f}%\n"
            f"⏰ Close Time  : {today.strftime('%I:%M %p ET')}"
        )

        self.position = None

    def check_exits(self) -> tuple[bool, float]:
        """
        Evaluate profit target and stop loss.
        Returns (closed, pnl). closed=True if position was just closed.
        """
        if not self.position:
            return False, 0.0

        p = self.position
        try:
            now   = datetime.now(ET)
            S     = _get_spy_price(self.client)
            T     = _hours_to_close(now)
            cost  = iron_condor_cost_to_close(
                S, p["short_call"], p["long_call"],
                p["short_put"],  p["long_put"],
                T, 0.05, p["sigma"]
            )
            credit = p["credit"]
            pnl    = (credit - cost) * 100 * p["contracts"]
            log.info("SPY=%.2f | cost=%.4f | credit=%.4f | P&L=$%.2f",
                     S, cost, credit, pnl)

            if cost <= credit * (1 - self.cfg.PROFIT_TARGET_PCT):
                self.close_position("profit_target", pnl)
                return True, pnl
            elif cost >= credit * (1 + self.cfg.STOP_LOSS_MULT):
                self.close_position("stop_loss", pnl)
                return True, pnl

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
            _tg_send(f"⏭️ <b>SESSION SKIPPED — {now.strftime('%Y-%m-%d')}</b>\n"
                     "Market closed or weekend.")
            return

        # ── PDT guard ─────────────────────────────────────────────────────────
        dt_used = self._pdt_trade_count()
        if dt_used >= self.cfg.PDT_MAX_DAY_TRADES:
            msg = (f"⚠️ <b>PDT LIMIT — NO TRADE {now.strftime('%Y-%m-%d')}</b>\n"
                   f"Day trades used: {dt_used}/{self.cfg.PDT_MAX_DAY_TRADES} "
                   f"in rolling {self.cfg.PDT_WINDOW_DAYS}-day window.\n"
                   f"Resuming when oldest trade drops off window.")
            log.info("PDT limit reached (%d/%d). Skipping today.", dt_used, self.cfg.PDT_MAX_DAY_TRADES)
            _tg_send(msg)
            return
        log.info("PDT: %d/%d day trades used in rolling window. Proceeding.",
                 dt_used, self.cfg.PDT_MAX_DAY_TRADES)

        entered        = False
        session_pnl    = 0.0
        session_credit = 0.0
        close_reason   = "no_trade"

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
                    S    = _get_spy_price(self.client)
                    T    = _hours_to_close(now)
                    cost = iron_condor_cost_to_close(
                        S, p["short_call"], p["long_call"],
                        p["short_put"],  p["long_put"],
                        T, 0.05, p["sigma"]
                    )
                    session_pnl = (p["credit"] - cost) * 100 * p["contracts"]
                except Exception as e:
                    log.error("Force-close P&L calc failed: %s", e)
                    session_pnl = 0.0
                self.close_position("force_close", session_pnl)
                self._record_day_trade()
                close_reason = "force_close"
                break

            # ── Entry window: 10:15–10:29 AM ─────────────────────────────────
            if not entered and not self.position and self.is_entry_time():
                try:
                    success = self.enter_trade()
                    entered = True
                    if success and self.position:
                        session_credit = self.position["credit"]
                except Exception as e:
                    log.error("enter_trade raised an unexpected error: %s", e)
                    entered = True   # prevent retry loop

            # ── Monitor open position ─────────────────────────────────────────
            if self.position:
                closed, pnl = self.check_exits()
                if closed:
                    session_pnl  = pnl
                    close_reason = "exit"
                    self._record_day_trade()
                    break   # done for the day

            time.sleep(60)

        # ── End-of-session logging ────────────────────────────────────────────
        if entered and session_credit > 0:
            self._log_forward_test(close_reason, session_pnl, session_credit)
            pnl_emoji = "💰" if session_pnl >= 0 else "📉"
            _tg_send(
                f"{pnl_emoji} <b>SESSION COMPLETE — {datetime.now(ET).strftime('%Y-%m-%d')}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"📋 Outcome     : {close_reason.replace('_', ' ').title()}\n"
                f"💵 Daily P&L   : ${session_pnl:+.2f}\n"
                f"📦 Contracts   : {self.cfg.CONTRACTS}\n"
                f"🎯 Daily Target: $203.00\n"
                f"{'✅ TARGET MET' if session_pnl >= 203 else '⚠️ Below target'}"
            )
        elif not entered:
            _tg_send(
                f"⏭️ <b>SESSION SKIPPED — {datetime.now(ET).strftime('%Y-%m-%d')}</b>\n"
                "Entry window passed with no trade (market or data issue)."
            )

        log.info("=== Daily Session Complete | P&L=$%.2f | Reason=%s ===",
                 session_pnl, close_reason)


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
