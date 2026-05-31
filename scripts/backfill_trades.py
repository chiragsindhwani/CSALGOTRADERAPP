"""
Backfill yesterday (2026-05-26) and today (2026-05-27) into trades/trade_log.csv.

Sources:
  logs/session_20260526.log        — entry/exit times, strikes, fill prices
  logs/session_20260527.log        — entry/exit times, strikes, B-S credit
  CS_ALGOTRADER_APP/forward_test_results.json  — authoritative P&L figures
  Tradier orders (verified earlier) — actual fill for today: $0.02/shr ($40 total)
"""
import os
from pathlib import Path

# Force local mode so we write to CSV (not SQLite)
os.environ["DEPLOYMENT_ENV"] = "local"

from iron_condor_0dte.trade_logger import TradeLogger

ROOT   = Path(__file__).resolve().parent
logger = TradeLogger(root_dir=ROOT)

# ─────────────────────────────────────────────────────────────────────────────
# Trade 1 — 2026-05-26 (yesterday)
# ─────────────────────────────────────────────────────────────────────────────
# From session_20260526.log:
#   Entry  09:15 CST = 10:15 AM ET  |  SPY=$751.48  |  P742/744 | C760/762
#   B-S credit  $0.4639/shr  ($46.39/contract × 30 contracts = $1,391.70 total)
#   Entry order  id=05ab9c77-2b13-4b79-9be2-9acec5429b41
#   Exit   10:10 CST = 11:10 AM ET  |  reason=profit_target
#   Close order  id=f34af99d-bffc-4031-bb34-254fe1f50222
#   Cost at close (last B-S check before PT hit): $0.3933/shr
# From forward_test_results.json:
#   gross_pnl=$211.75  commission=$156.00  net_pnl=$55.75  cumulative=$440.88
# Note: entry_credit == bs_credit ($0.4639) because old code used B-S for fills.
#   exit_cost calculated: (0.4639 - exit_cost) × 100 × 30 = 211.75
#   → exit_cost = 0.4639 - 211.75/3000 = 0.4639 - 0.0706 = $0.3933/shr ✓

trade_20260526 = {
    "date":             "2026-05-26",
    "environment":      "LIVE",
    "account_id":       "6YB67181",
    "account_name":     "Ruchika Dhawan",
    "symbol":           "SPY",
    "strategy":         "Iron Condor 0DTE",
    "contracts":        30,
    "long_put":         742.0,
    "short_put":        744.0,
    "short_call":       760.0,
    "long_call":        762.0,
    "wing_width":       2.0,
    "entry_time":       "10:15 ET",
    "exit_time":        "11:10 ET",
    "outcome":          "profit_target",
    "entry_order_id":   "05ab9c77-2b13-4b79-9be2-9acec5429b41",
    "exit_order_id":    "f34af99d-bffc-4031-bb34-254fe1f50222",
    "entry_credit":     0.4639,   # per-share (B-S = actual in old code)
    "bs_credit":        0.4639,   # per-share B-S estimate
    "exit_cost":        0.3933,   # per-share cost to close at profit target
    "gross_pnl":        211.75,
    "commission":       156.00,
    "net_pnl":          55.75,
    "cumulative_pnl":   440.88,
    "vix_sigma":        None,     # not captured in old session log
    "spy_price_entry":  751.48,
    "notes":            "Old code — B-S credit used as actual fill. 30 contracts @ $2 wing.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Trade 2 — 2026-05-27 (today)
# ─────────────────────────────────────────────────────────────────────────────
# From session_20260527.log:
#   Entry  09:15 CST = 10:15 AM ET  |  SPY=$750.79  |  P741/743 | C759/761
#   B-S credit  $0.4681/shr  ($46.81/contract × 20 = $936.20 B-S estimate)
#   Entry order  id=128194768
#   Exit   10:09 CST = 11:09 AM ET  |  reason=profit_target (B-S triggered)
#   Close order  id=128232848
# Actual fills (confirmed from Tradier orders — corrected in forward_test_results.json):
#   Actual entry fill  $0.02/shr  ($40.00 total for 20 contracts)
#   Gross P&L = -$60.00  →  exit_cost = 0.02 + 60/(100×20) = $0.05/shr
#   Commission = 4 legs × 20 contracts × $0.35 × 2 sides = $56.00
#   Net P&L = -$60.00 - $56.00 = -$116.00
#   Cumulative = $440.88 - $116.00 = $324.88

trade_20260527 = {
    "date":             "2026-05-27",
    "environment":      "LIVE",
    "account_id":       "6YB67181",
    "account_name":     "Ruchika Dhawan",
    "symbol":           "SPY",
    "strategy":         "Iron Condor 0DTE",
    "contracts":        20,
    "long_put":         741.0,
    "short_put":        743.0,
    "short_call":       759.0,
    "long_call":        761.0,
    "wing_width":       2.0,
    "entry_time":       "10:15 ET",
    "exit_time":        "11:09 ET",
    "outcome":          "profit_target",
    "entry_order_id":   "128194768",
    "exit_order_id":    "128232848",
    "entry_credit":     0.02,     # per-share ACTUAL fill ($40 total / 20 contracts / 100)
    "bs_credit":        0.4681,   # per-share B-S estimate at entry
    "exit_cost":        0.05,     # per-share actual exit cost (back-calculated from gross P&L)
    "gross_pnl":        -60.00,
    "commission":       56.00,
    "net_pnl":          -116.00,
    "cumulative_pnl":   324.88,
    "vix_sigma":        None,     # not captured in old session log
    "spy_price_entry":  750.79,
    "notes":            "Market order filled at $0.02/shr vs B-S est $0.4681. "
                        "Commission ($56) exceeded actual credit ($40). "
                        "Fix A/B/C deployed after this trade.",
}

# ── Write both ────────────────────────────────────────────────────────────────
print(f"Writing to: {logger.csv_path}")
print()

for trade in [trade_20260526, trade_20260527]:
    logger.log_trade(trade)
    print(f"  {trade['date']}  {trade['outcome']:15s}  "
          f"contracts={trade['contracts']:2d}  "
          f"credit=${trade['entry_credit']:.4f}/shr  "
          f"gross=${trade['gross_pnl']:+.2f}  "
          f"commission=${trade['commission']:.2f}  "
          f"net=${trade['net_pnl']:+.2f}  "
          f"cumulative=${trade['cumulative_pnl']:+.2f}")

print()
print("Done. Verifying CSV contents:")
print()

import csv
rows = list(csv.DictReader(open(logger.csv_path, encoding="utf-8")))
print(f"{'Row':<4} {'Date':<12} {'Outcome':<16} {'Ct':>3} {'Credit/shr':>11} {'Gross P&L':>10} {'Commission':>11} {'Net P&L':>10} {'Cumulative':>11}")
print("-" * 92)
for r in rows:
    print(f"{r['id']:<4} {r['date']:<12} {r['outcome']:<16} "
          f"{r['contracts']:>3}  "
          f"${float(r['entry_credit']):>9.4f}  "
          f"${float(r['gross_pnl']):>+9.2f}  "
          f"${float(r['commission']):>9.2f}  "
          f"${float(r['net_pnl']):>+9.2f}  "
          f"${float(r['cumulative_pnl']):>+9.2f}")
