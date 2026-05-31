"""
Manual force-entry for SPY Iron Condor — bypasses the 10:15 AM entry window.
Enters immediately at current time using the same Fix A/B/C logic as the
scheduled bot, then monitors until profit target, stop loss, or 3:45 PM ET
force close.

Usage:
    python run_manual_trade.py
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Load .env ──────────────────────────────────────────────────────────────────
for _line in Path(".env").read_text(encoding="utf-8").splitlines():
    _line = _line.strip()
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ[_k.strip()] = _v.strip()

# ── Logging ────────────────────────────────────────────────────────────────────
ET = ZoneInfo("America/New_York")
_today = datetime.now(ET).strftime("%Y%m%d")
_log_path = Path(f"logs/session_{_today}_manual.log")
_log_path.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_path, mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Imports ────────────────────────────────────────────────────────────────────
from iron_condor_0dte.live_trader import IronCondorTrader, _tg_send

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    now = datetime.now(ET)
    log.info("=== SPY Iron Condor — Manual Session | %s ===", now.strftime("%Y-%m-%d %H:%M ET"))

    trader = IronCondorTrader()

    # ── PDT guard ─────────────────────────────────────────────────────────────
    dt_used = trader._pdt_trade_count()
    if dt_used >= trader.cfg.PDT_MAX_DAY_TRADES:
        log.warning("PDT limit reached (%d/%d). Aborting manual entry.",
                    dt_used, trader.cfg.PDT_MAX_DAY_TRADES)
        _tg_send(
            trader._acct_header() +
            f"⚠️ <b>PDT LIMIT — MANUAL ENTRY BLOCKED</b>\n"
            f"Day trades used: {dt_used}/{trader.cfg.PDT_MAX_DAY_TRADES}"
        )
        return

    log.info("PDT: %d/%d day trades used. Proceeding with manual entry.",
             dt_used, trader.cfg.PDT_MAX_DAY_TRADES)

    # ── Force entry — bypasses is_entry_time() check, uses market order ──────
    log.info("--- Forcing MARKET ORDER entry now (bypassing 10:15 AM window) ---")
    log.info("    Fix A still active: abort if actual fill < $%.2f/shr",
             trader.cfg.MIN_ACTUAL_CREDIT)
    try:
        success = trader.enter_trade(force_market=True)
    except Exception as e:
        log.error("enter_trade raised an unexpected error: %s", e)
        return

    if not success or not trader.position:
        log.warning("Entry failed or was aborted (no fill / credit too low). Nothing to monitor.")
        return

    session_credit = trader.position.get("actual_credit", trader.position.get("credit", 0))
    session_pnl    = 0.0
    close_reason   = "no_close"

    # ── Monitoring loop ───────────────────────────────────────────────────────
    while True:
        now = datetime.now(ET)

        if not trader.is_market_hours():
            log.info("Market closed at %s ET. Session complete.", now.strftime("%H:%M"))
            break

        if trader.position and trader.is_force_close_time():
            log.info("Force-close time reached (%s ET).", now.strftime("%H:%M"))
            try:
                trader.close_position("force_close")
                close_reason = "force_close"
            except Exception as e:
                log.error("Force close failed: %s", e)
            trader._record_day_trade()
            break

        if trader.position:
            closed, pnl = trader.check_exits()
            if closed:
                session_pnl  = pnl
                close_reason = "exit"
                trader._record_day_trade()
                break

        time.sleep(60)

    # ── End-of-session logging ────────────────────────────────────────────────
    if session_credit > 0:
        trader._log_forward_test(close_reason, session_pnl, session_credit)
        ci      = trader._last_close_info
        net_pnl = ci.get("net_pnl", session_pnl - ci.get("commission", 0))
        emoji   = "💰" if net_pnl >= 0 else "📉"
        _tg_send(
            trader._acct_header() +
            f"{emoji} <b>SESSION COMPLETE (Manual) — {datetime.now(ET).strftime('%Y-%m-%d')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Outcome     : {ci.get('label', close_reason.replace('_', ' ').title())}\n"
            + (f"📉 Put Spread  : ${ci['long_put']:.0f} / ${ci['short_put']:.0f}\n"
               f"📈 Call Spread : ${ci['short_call']:.0f} / ${ci['long_call']:.0f}\n"
               if ci.get("long_put") else "") +
            f"⏰ Close Time  : {ci.get('close_time', '—')}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💵 Credit Rcvd : ${ci.get('actual_credit', session_credit) * 100:.2f} / contract\n"
            f"📦 Contracts   : {ci.get('contracts', trader.cfg.CONTRACTS)}\n"
            f"💰 Gross P&L   : ${session_pnl:+.2f}\n"
            f"🏛️ Commission  : -${ci.get('commission', 0):.2f}\n"
            f"✅ Net P&L     : ${net_pnl:+.2f}\n"
        )

    log.info("=== Manual Session Complete | P&L=$%.2f | Reason=%s ===",
             session_pnl, close_reason)


if __name__ == "__main__":
    main()
