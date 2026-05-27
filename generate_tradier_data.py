"""
Fetch live Tradier account data and write tradier_account_data.js for the dashboard.
Run this script any time to refresh the dashboard data.

Usage:
    python generate_tradier_data.py
"""
from __future__ import annotations
import http.client, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Load .env manually (no extra deps) ────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_env  = _ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

TOKEN      = os.getenv("TRADIER_API_TOKEN", "")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID", "")
PAPER      = os.getenv("TRADIER_PAPER_TRADE", "false").lower() == "true"
BASE_HOST  = "sandbox.tradier.com" if PAPER else "api.tradier.com"
ET         = ZoneInfo("America/New_York")

if not TOKEN or not ACCOUNT_ID:
    print("ERROR: TRADIER_API_TOKEN and TRADIER_ACCOUNT_ID must be set in .env")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def _get(path: str) -> dict:
    conn = http.client.HTTPSConnection(BASE_HOST, timeout=15)
    conn.request("GET", path, headers=HEADERS)
    resp = conn.getresponse()
    raw  = resp.read().decode()
    conn.close()
    return json.loads(raw)


def _safe_list(obj, key: str) -> list:
    inner = obj.get(key)
    if not inner or inner == "null":
        return []
    items = inner.get(key.rstrip("s"), inner.get(key, []))
    if isinstance(items, dict):
        items = [items]
    return items or []


# ── Fetch data ─────────────────────────────────────────────────────────────────
print(f"Fetching Tradier data from {BASE_HOST} ...")

profile_raw  = _get("/v1/user/profile")
balances_raw = _get(f"/v1/accounts/{ACCOUNT_ID}/balances")
positions_raw= _get(f"/v1/accounts/{ACCOUNT_ID}/positions")
orders_raw   = _get(f"/v1/accounts/{ACCOUNT_ID}/orders")

profile  = profile_raw.get("profile", {})
acc      = profile.get("account", {}) if isinstance(profile.get("account"), dict) else {}
balances = balances_raw.get("balances", {})

# Positions
pos_obj  = positions_raw.get("positions", {})
positions = []
if pos_obj and pos_obj != "null":
    p = pos_obj.get("position", [])
    positions = [p] if isinstance(p, dict) else p

# Orders — all of them, sorted newest first
ord_obj = orders_raw.get("orders", {})
orders  = []
if ord_obj and ord_obj != "null":
    o = ord_obj.get("order", [])
    orders = [o] if isinstance(o, dict) else o
orders_sorted = sorted(orders, key=lambda x: x.get("create_date", ""), reverse=True)

# ── PDT rolling window ─────────────────────────────────────────────────────────
pdt_path = _ROOT / "pdt_trades.json"
pdt_records = []
if pdt_path.exists():
    try:
        pdt_records = json.loads(pdt_path.read_text(encoding="utf-8"))
    except Exception:
        pdt_records = []

today = datetime.now(ET).date()
pdt_window = []
d = today
while len(pdt_window) < 5:
    if d.weekday() < 5:
        pdt_window.append(d.isoformat())
    d -= timedelta(days=1)
pdt_window.reverse()   # oldest → newest

pdt_used   = sum(1 for r in pdt_records if r.get("date") in set(pdt_window))
pdt_dates  = {r["date"] for r in pdt_records}

# ── P&L chart — live Tradier gainloss, SPY options from LIVE_START_DATE ────────
LIVE_START_DATE = "2026-05-26"   # first day of live strategy trading

gl_raw = _get(
    f"/v1/accounts/{ACCOUNT_ID}/gainloss"
    f"?start={LIVE_START_DATE}&limit=500&sortBy=closeDate&sort=asc"
)
gl_obj = gl_raw.get("gainloss", {})
closed_positions: list = []
if gl_obj and gl_obj != "null":
    cp = gl_obj.get("closed_position", [])
    closed_positions = [cp] if isinstance(cp, dict) else (cp or [])

# Aggregate per calendar date — SPY options only
# gain_loss = raw proceeds − cost (does NOT include commissions)
# commission = $0.35/contract charged on open AND close
daily_gl: dict = {}
for pos in closed_positions:
    sym        = (pos.get("symbol") or "").upper()
    close_date = (pos.get("close_date") or "")[:10]   # "YYYY-MM-DD"
    # Skip non-SPY symbols and anything before the live start
    if not sym.startswith("SPY") or len(sym) > 6:      # bare "SPY" = equity; options are longer
        if sym == "SPY":
            continue                                    # skip SPY equity trades
    if close_date < LIVE_START_DATE:
        continue
    gain = float(pos.get("gain_loss", 0) or 0)
    qty  = abs(float(pos.get("quantity", 0) or 0))
    comm = round(qty * 0.35 * 2, 2)                   # open + close, per Tradier pricing
    if close_date not in daily_gl:
        daily_gl[close_date] = {"gross_pnl": 0.0, "commission": 0.0, "contracts": 0}
    daily_gl[close_date]["gross_pnl"]  += gain
    daily_gl[close_date]["commission"] += comm
    if daily_gl[close_date]["contracts"] == 0:
        daily_gl[close_date]["contracts"] = int(qty)   # infer from first leg seen

# Build chart window: all business days from LIVE_START_DATE to today (max 21)
from datetime import date as _date
start_d = _date.fromisoformat(LIVE_START_DATE)
chart_days: list[str] = []
d = start_d
while d <= today and len(chart_days) < 21:
    if d.weekday() < 5:
        chart_days.append(d.isoformat())
    d += timedelta(days=1)

pnl_chart = []
for date in chart_days:
    if date in daily_gl:
        gl    = daily_gl[date]
        gross = round(gl["gross_pnl"], 2)
        comm  = round(gl["commission"], 2)
        pnl_chart.append({
            "date":       date,
            "gross_pnl":  gross,
            "commission": comm,
            "net_pnl":    round(gross - comm, 2),
            "outcome":    "live",
            "contracts":  gl["contracts"],
            "spreads":    "",
        })
    else:
        pnl_chart.append({
            "date":       date,
            "gross_pnl":  0,
            "commission": 0,
            "net_pnl":    0,
            "outcome":    "",
            "contracts":  0,
            "spreads":    "",
        })

# ── Build payload ──────────────────────────────────────────────────────────────
margin = balances.get("margin", {}) or {}
payload = {
    "generated_at": datetime.now(ET).isoformat(),
    "environment":  "SANDBOX" if PAPER else "LIVE",
    "profile": {
        "name":           profile.get("name", ""),
        "id":             profile.get("id", ""),
        "account_number": acc.get("account_number", ACCOUNT_ID),
        "classification": acc.get("classification", ""),
        "type":           acc.get("type", ""),
        "option_level":   acc.get("option_level", 0),
        "day_trader":     acc.get("day_trader", False),
        "status":         acc.get("status", ""),
        "date_created":   acc.get("date_created", ""),
    },
    "balances": {
        "total_equity":         balances.get("total_equity", 0),
        "total_cash":           balances.get("total_cash", 0),
        "open_pl":              balances.get("open_pl", 0),
        "close_pl":             balances.get("close_pl", 0),
        "long_market_value":    balances.get("long_market_value", 0),
        "short_market_value":   balances.get("short_market_value", 0),
        "option_long_value":    balances.get("option_long_value", 0),
        "option_short_value":   balances.get("option_short_value", 0),
        "market_value":         balances.get("market_value", 0),
        "option_buying_power":  margin.get("option_buying_power", 0),
        "stock_buying_power":   margin.get("stock_buying_power", 0),
        "uncleared_funds":      balances.get("uncleared_funds", 0),
        "pending_orders_count": balances.get("pending_orders_count", 0),
        "current_requirement":  balances.get("current_requirement", 0),
    },
    "positions": positions,
    "orders":    orders_sorted[:50],   # last 50
    "pdt": {
        "max_trades":  3,
        "window_days": 5,
        "used":        pdt_used,
        "remaining":   max(0, 3 - pdt_used),
        "window":      pdt_window,
        "trade_dates": sorted(pdt_dates),
    },
    "pnl_chart": pnl_chart,
}

# ── Write JS file ──────────────────────────────────────────────────────────────
out_path = _ROOT / "CS_ALGOTRADER_APP" / "tradier_account_data.js"
out_path.write_text(
    "window.TRADIER_DATA = " + json.dumps(payload, indent=2) + ";",
    encoding="utf-8",
)

trade_days   = [d for d in pnl_chart if d["gross_pnl"] > 0]
total_net    = sum(d["net_pnl"]    for d in trade_days)
total_comm   = sum(d["commission"] for d in trade_days)

print(f"Written -> {out_path}")
print(f"  Account   : {payload['profile']['account_number']} ({payload['profile']['name']})")
print(f"  Equity    : ${payload['balances']['total_equity']:,.2f}")
print(f"  Cash      : ${payload['balances']['total_cash']:,.2f}")
print(f"  Open P&L  : ${payload['balances']['open_pl']:+,.2f}")
print(f"  Positions : {len(positions)}")
print(f"  Orders    : {len(orders)}")
print(f"  PDT used  : {pdt_used}/3 in rolling window")
print(f"  Live P&L chart ({LIVE_START_DATE} onwards):")
print(f"    Trade days : {len(trade_days)} / {len(pnl_chart)} shown")
print(f"    Net P&L    : ${total_net:+,.2f}")
print(f"    Commission : -${total_comm:,.2f}")
