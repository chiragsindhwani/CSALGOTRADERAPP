"""
Manual force-entry for SPY Iron Condor — bypasses the 10:15 AM entry window.
Enters immediately at current time, then monitors until exit or force close at 3:45 PM.

Usage:
    python run_manual_trade.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Load .env ──────────────────────────────────────────────────────────────────
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("iron_condor_session.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# ── Imports ────────────────────────────────────────────────────────────────────
from iron_condor_0dte.config import config
from iron_condor_0dte.live_trader import (
    IronCondorTrader, _get_spy_price, _get_vix_sigma,
    _build_option_symbol, _tg_send,
)
from iron_condor_0dte.options_pricing import (
    find_strike_for_delta, iron_condor_credit, iron_condor_cost_to_close,
)

config.API_KEY    = os.environ.get("ALPACA_API_KEY", "")
config.SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")

# ── Manual entry ───────────────────────────────────────────────────────────────

def force_enter(trader: IronCondorTrader):
    try:
        from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest
        from alpaca.trading.enums import TimeInForce, OrderClass, PositionIntent
    except ImportError:
        log.error("alpaca-py not installed.")
        return

    now  = datetime.now(ET)
    S    = _get_spy_price(trader.data_cl)
    sigma = _get_vix_sigma()
    r    = 0.05

    # T computed from current time — not locked to 10:15 AM
    hours_left = max(16.0 - (now.hour + now.minute / 60), 0.0001)
    T = hours_left / (252 * 6.5)

    short_call = round(find_strike_for_delta(S, T, r, sigma, config.TARGET_DELTA, "call"))
    short_put  = round(find_strike_for_delta(S, T, r, sigma, config.TARGET_DELTA, "put"))
    long_call  = short_call + config.WING_WIDTH
    long_put   = short_put  - config.WING_WIDTH

    credit    = iron_condor_credit(S, short_call, long_call, short_put, long_put, T, r, sigma)
    contracts = config.CONTRACTS

    if credit < config.MIN_CREDIT:
        log.warning("Credit $%.2f below minimum $%.2f — skipping.", credit * 100, config.MIN_CREDIT * 100)
        return

    log.info("MANUAL ENTRY | SPY=%.2f | P%d/%d | C%d/%d | Credit=$%.2f | Contracts=%d",
             S, long_put, short_put, short_call, long_call, credit * 100, contracts)
    log.info("  Profit Target (15%%): $%.2f  |  Stop Loss (45%%): $%.2f",
             credit * config.PROFIT_TARGET_PCT * 100 * contracts,
             credit * config.STOP_LOSS_MULT     * 100 * contracts)

    _tg_send(
        f"🟢 <b>IRON CONDOR OPENED (Manual)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📈 SPY Price   : ${S:.2f}\n"
        f"📉 Put Spread  : ${long_put:.0f} / ${short_put:.0f}\n"
        f"📈 Call Spread : ${short_call:.0f} / ${long_call:.0f}\n"
        f"💵 Credit      : ${credit * 100:.2f} / contract\n"
        f"📦 Contracts   : {contracts}\n"
        f"💰 Total Credit: ${credit * 100 * contracts:.2f}\n"
        f"🎯 Profit Target (15%): ${credit * config.PROFIT_TARGET_PCT * 100 * contracts:.2f}\n"
        f"🛑 Stop Loss (45%)    : ${credit * config.STOP_LOSS_MULT * 100 * contracts:.2f}\n"
        f"⏰ Entry Time  : {now.strftime('%I:%M %p ET')}"
    )

    try:
        order = trader.client.submit_order(MarketOrderRequest(
            qty=contracts,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.MLEG,
            legs=[
                OptionLegRequest(
                    symbol=_build_option_symbol("SPY", now, long_call, "call"),
                    ratio_qty=1,
                    position_intent=PositionIntent.BUY_TO_OPEN,
                ),
                OptionLegRequest(
                    symbol=_build_option_symbol("SPY", now, short_call, "call"),
                    ratio_qty=1,
                    position_intent=PositionIntent.SELL_TO_OPEN,
                ),
                OptionLegRequest(
                    symbol=_build_option_symbol("SPY", now, long_put, "put"),
                    ratio_qty=1,
                    position_intent=PositionIntent.BUY_TO_OPEN,
                ),
                OptionLegRequest(
                    symbol=_build_option_symbol("SPY", now, short_put, "put"),
                    ratio_qty=1,
                    position_intent=PositionIntent.SELL_TO_OPEN,
                ),
            ],
        ))
        log.info("  MLEG order submitted | id=%s", order.id)
        trader.position = {
            "short_call": short_call, "long_call": long_call,
            "short_put":  short_put,  "long_put":  long_put,
            "credit": credit, "contracts": contracts,
            "sigma": sigma, "order_id": str(order.id),
            "entry_T": T,
        }
    except Exception as e:
        log.error("MLEG entry failed: %s", e)


def run():
    log.info("=== SPY Iron Condor — Manual Session ===")
    trader = IronCondorTrader(config)

    force_enter(trader)

    if not trader.position:
        log.warning("Entry failed — nothing to monitor. Exiting.")
        return

    session_credit = trader.position["credit"]
    session_pnl    = 0.0
    close_reason   = "no_close"

    while True:
        now = datetime.now(ET)

        # Force close at 3:45 PM
        if now.hour > 15 or (now.hour == 15 and now.minute >= 45):
            if trader.position:
                trader.close_position("force_close")
                close_reason = "force_close"
            break

        # Market closed
        if now.hour >= 16:
            break

        if trader.position:
            prev_pos = trader.position
            trader.check_exits()
            if not trader.position:
                # Closed by check_exits (PT or SL)
                p = prev_pos
                S = _get_spy_price(trader.data_cl)
                now_et = datetime.now(ET)
                hours_left = max(16.0 - (now_et.hour + now_et.minute / 60), 0.0001)
                T_close = hours_left / (252 * 6.5)
                cost = iron_condor_cost_to_close(
                    S, p["short_call"], p["long_call"],
                    p["short_put"],  p["long_put"],
                    T_close, 0.05, p["sigma"]
                )
                session_pnl = (p["credit"] - cost) * 100 * p["contracts"]
                close_reason = "exit"
                break
        else:
            # Position was closed — exit loop
            break

        time.sleep(60)

    # Compute P&L if force-closed
    if close_reason == "force_close" and session_credit > 0:
        try:
            p   = trader.position or {}
            S   = _get_spy_price(trader.data_cl)
            now_et = datetime.now(ET)
            hours_left = max(16.0 - (now_et.hour + now_et.minute / 60), 0.0001)
            T_fc = hours_left / (252 * 6.5)
            cost = iron_condor_cost_to_close(
                S, p.get("short_call", 0), p.get("long_call", 0),
                p.get("short_put", 0),  p.get("long_put", 0),
                T_fc, 0.05, p.get("sigma", 0.18)
            )
            session_pnl = (session_credit - cost) * 100 * config.CONTRACTS
        except Exception:
            session_pnl = 0.0

    # Log forward test
    log_path = Path("CS_ALGOTRADER_APP/forward_test_results.json")
    results  = json.loads(log_path.read_text()) if log_path.exists() else []
    today    = datetime.now(ET).strftime("%Y-%m-%d")
    existing = next((r for r in results if r["date"] == today), None)
    entry = {
        "date":             today,
        "outcome":          close_reason,
        "pnl":              round(session_pnl, 2),
        "credit_collected": round(session_credit * 100 * config.CONTRACTS, 2),
        "contracts":        config.CONTRACTS,
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

    log_path.write_text(json.dumps(results, indent=2))

    js_payload = {
        "start_date":       "2026-05-18",
        "end_date":         "2026-05-29",
        "target_daily_pnl": 203.0,
        "results":          results,
        "generated_at":     datetime.now(ET).isoformat(),
    }
    Path("CS_ALGOTRADER_APP/forward_test_data.js").write_text(
        "window.FORWARD_TEST_DATA = " + json.dumps(js_payload) + ";"
    )

    pnl_emoji = "💰" if session_pnl >= 0 else "📉"
    _tg_send(
        f"{pnl_emoji} <b>SESSION COMPLETE — {today}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Outcome     : {close_reason.replace('_', ' ').title()}\n"
        f"💵 Daily P&L   : ${session_pnl:+.2f}\n"
        f"📦 Contracts   : {config.CONTRACTS}\n"
        f"🎯 Daily Target: $203.00\n"
        f"{'✅ TARGET MET' if session_pnl >= 203 else '⚠️ Below target'}"
    )
    log.info("=== Session Complete | P&L=$%.2f | Reason=%s ===", session_pnl, close_reason)


if __name__ == "__main__":
    run()
