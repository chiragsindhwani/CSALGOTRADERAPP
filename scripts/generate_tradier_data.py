"""
Fetch live Tradier account data and write tradier_account_data.js for the dashboard.
Run this script any time to refresh the dashboard data.

Usage:
    python generate_tradier_data.py
"""
from __future__ import annotations
import csv, http.client, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def _parse_option_symbol(sym: str) -> dict | None:
    """Parse OCC option symbol: SPY260528P00748000 → dict with expiry, type, strike."""
    import re
    m = re.match(r'^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$', sym)
    if not m:
        return None
    und, yy, mm, dd, cp, stk = m.groups()
    return {
        "underlying": und,
        "expiry": f"20{yy}-{mm}-{dd}",
        "option_type": "call" if cp == "C" else "put",
        "strike": int(stk) / 1000,
    }


def _fetch_gainloss_history(get_fn, account_id: str, days: int = 365) -> list[dict]:
    """
    Fetch all closed-position gain/loss records from Tradier for the last `days` days.
    Groups legs by close_date + open_date to reconstruct each IC round-trip.
    Returns list of daily trade dicts sorted oldest → newest.
    """
    from datetime import datetime, timezone
    ET = ZoneInfo("America/New_York")
    start = (datetime.now(ET) - timedelta(days=days)).strftime("%Y-%m-%d")
    end   = datetime.now(ET).strftime("%Y-%m-%d")

    # Fetch records — Tradier gainloss uses page-number pagination, not offset
    all_legs: list[dict] = []
    limit, page = 100, 1
    while True:
        path = (
            f"/v1/accounts/{account_id}/gainloss"
            f"?start_date={start}&end_date={end}&limit={limit}&page={page}"
        )
        data = get_fn(path)
        gl   = data.get("gainloss") or {}
        recs = gl.get("closed_position", []) if gl and gl != "null" else []
        if isinstance(recs, dict):
            recs = [recs]
        if not recs:
            break
        all_legs.extend(recs)
        if len(recs) < limit:
            break
        page += 1

    # Filter: SPY options only
    spy_legs = [
        r for r in all_legs
        if isinstance(r.get("symbol"), str) and r["symbol"].startswith("SPY")
        and len(r["symbol"]) > 3
    ]
    if not spy_legs:
        return []

    # Group by (close_date_YYYYMMDD, open_date_YYYYMMDD)
    from collections import defaultdict
    groups: dict[str, list] = defaultdict(list)
    for leg in spy_legs:
        close_d = (leg.get("close_date") or "")[:10]
        open_d  = (leg.get("open_date")  or "")[:10]
        groups[f"{open_d}|{close_d}"].append(leg)

    trades = []
    cumulative = 0.0
    for key in sorted(groups.keys()):
        open_d, close_d = key.split("|")
        legs = groups[key]

        # Determine contracts from first leg quantity
        contracts = int(abs(legs[0].get("quantity", 9)))

        # Gross P&L = sum of all leg gains/losses
        gross_pnl = round(sum(float(lg.get("gain_loss", 0) or 0) for lg in legs), 2)

        # Commission: $0.35/contract/leg, charged on open AND close
        n_legs   = len(legs)
        commission = round(n_legs * contracts * 0.35 * 2, 2)
        net_pnl    = round(gross_pnl - commission, 2)
        cumulative = round(cumulative + net_pnl, 2)

        # Parse strikes from option symbols
        puts  = sorted([_parse_option_symbol(lg["symbol"]) for lg in legs
                        if _parse_option_symbol(lg.get("symbol","")) and
                        _parse_option_symbol(lg["symbol"])["option_type"] == "put"],
                       key=lambda x: x["strike"])
        calls = sorted([_parse_option_symbol(lg["symbol"]) for lg in legs
                        if _parse_option_symbol(lg.get("symbol","")) and
                        _parse_option_symbol(lg["symbol"])["option_type"] == "call"],
                       key=lambda x: x["strike"])

        long_put   = puts[0]["strike"]  if len(puts)  >= 2 else None
        short_put  = puts[-1]["strike"] if len(puts)  >= 2 else None
        short_call = calls[0]["strike"] if len(calls) >= 2 else None
        long_call  = calls[-1]["strike"] if len(calls) >= 2 else None
        wing_width = round(short_put - long_put, 1) if long_put and short_put else None

        # Infer outcome from gross P&L (before commission)
        if gross_pnl > 0:
            outcome = "profit_target"          # IC decayed → closed at profit
        elif abs(gross_pnl) < contracts * 8:
            outcome = "aborted"                # tiny loss → likely a quick abort
        else:
            outcome = "stop_loss"              # significant loss → stop or force-close

        trades.append({
            "date":           close_d,
            "open_date":      open_d,
            "close_date":     close_d,
            "source":         "tradier_gainloss",
            "contracts":      contracts,
            "long_put":       long_put,
            "short_put":      short_put,
            "short_call":     short_call,
            "long_call":      long_call,
            "wing_width":     wing_width,
            "n_legs":         n_legs,
            "gross_pnl":      gross_pnl,
            "commission":     commission,
            "net_pnl":        net_pnl,
            "cumulative_pnl": cumulative,
            "outcome":        outcome,
        })

    return trades


def _load_trade_log() -> list[dict]:
    """Read all trade_log_*.csv files from trades/ dir and return as list of dicts (newest first)."""
    trades_dir = Path(__file__).resolve().parent.parent / "trades"
    if not trades_dir.exists():
        return []

    rows = []
    # Load all date-specific CSV files (trade_log_YYYY-MM-DD.csv)
    csv_files = sorted(trades_dir.glob("trade_log_*.csv"))
    for csv_path in csv_files:
        try:
            with csv_path.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    # Coerce numeric fields so JSON stays compact
                    for col in ("contracts", "long_put", "short_put", "short_call", "long_call",
                                "wing_width", "entry_credit", "bs_credit", "exit_cost",
                                "gross_pnl", "commission", "net_pnl", "cumulative_pnl",
                                "vix_sigma", "spy_price_entry"):
                        try:
                            row[col] = float(row[col]) if row[col] not in ("", "None", None) else None
                        except (ValueError, TypeError):
                            row[col] = None
                    rows.append(row)
        except Exception as e:
            import sys
            print(f"Warning: Could not read {csv_path}: {e}", file=sys.stderr)

    return list(reversed(rows))   # newest first

# ── Load .env manually (no extra deps) ────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent  # project root (one level up from scripts/)
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

# ── P&L chart — gainloss API (settled) + orders fallback (same-day) ───────────
LIVE_START_DATE = "2026-05-26"   # first day of live strategy trading

# 1) Gainloss API — settled closed positions (may lag same-day by T+1)
gl_raw = _get(
    f"/v1/accounts/{ACCOUNT_ID}/gainloss"
    f"?start={LIVE_START_DATE}&limit=500&sortBy=closeDate&sort=asc"
)
gl_obj = gl_raw.get("gainloss", {})
closed_positions: list = []
if gl_obj and gl_obj != "null":
    cp = gl_obj.get("closed_position", [])
    closed_positions = [cp] if isinstance(cp, dict) else (cp or [])

# Aggregate per calendar date — SPY options only (sym len > 6; "SPY" equity is len 3)
# gain_loss = raw proceeds − cost (does NOT include commissions)
# commission = $0.35/contract charged on both open AND close legs
daily_gl: dict = {}
for pos in closed_positions:
    sym        = (pos.get("symbol") or "").upper()
    close_date = (pos.get("close_date") or "")[:10]   # "YYYY-MM-DD"
    # Only process SPY option symbols (len > 6); skip bare equity and non-SPY
    if not sym.startswith("SPY") or len(sym) <= 6:
        continue
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
        daily_gl[close_date]["contracts"] = int(qty)


# 2) Orders-based fallback — for same-day trades before gainloss API settles
#
#    Iron Condor round-trip math:
#      Entry order : avg_fill_price < 0  (credit received, e.g. -0.02/share)
#      Close order : avg_fill_price > 0  (debit paid,     e.g. +0.05/share)
#      qty = contracts_per_leg × num_legs  (e.g. 80 = 20 × 4)
#      gross   = (|entry_avg| − |close_avg|) × 100 × contracts_per_leg
#      commission = 4 × contracts_per_leg × $0.35 × 2   (open + close)
def _pnl_from_orders(all_orders: list) -> dict:
    """Return {date: {gross_pnl, commission, contracts}} from filled multileg orders."""
    by_date: dict = {}
    for o in all_orders:
        if o.get("status") != "filled":
            continue
        if o.get("class") != "multileg":
            continue
        legs = o.get("leg", [])
        if isinstance(legs, dict):
            legs = [legs]
        # At least one leg must reference a SPY option
        spy_opt = any(
            "SPY" in (lg.get("option_symbol") or lg.get("symbol") or "")
            and len(lg.get("option_symbol") or lg.get("symbol") or "") > 6
            for lg in legs
        )
        if not spy_opt:
            continue
        order_date = (o.get("create_date") or "")[:10]
        if order_date < LIVE_START_DATE:
            continue
        avg = float(o.get("avg_fill_price", 0) or 0)
        by_date.setdefault(order_date, {"credits": [], "debits": []})
        if avg < 0:
            by_date[order_date]["credits"].append(o)   # entry — credit received
        elif avg > 0:
            by_date[order_date]["debits"].append(o)    # close  — debit paid

    result: dict = {}
    for date, sides in by_date.items():
        credits = sides["credits"]
        debits  = sides["debits"]
        if not credits or not debits:
            continue   # only one side present; skip incomplete day

        # Derive contracts_per_leg from the first credit (entry) order
        c_ord  = credits[0]
        c_legs = c_ord.get("leg", [])
        if isinstance(c_legs, dict):
            c_legs = [c_legs]
        num_legs  = max(len(c_legs), 1)
        qty       = int(c_ord.get("quantity", 0))
        contracts = qty // num_legs

        entry_avg = abs(float(c_ord.get("avg_fill_price", 0)))        # credit/share
        close_avg = abs(float(debits[0].get("avg_fill_price", 0)))    # debit/share
        gross = round((entry_avg - close_avg) * 100 * contracts, 2)
        comm  = round(4 * contracts * 0.35 * 2, 2)
        result[date] = {"gross_pnl": gross, "commission": comm, "contracts": contracts}

    return result

daily_orders_pnl = _pnl_from_orders(orders)


# 3) Build chart window: all business days from LIVE_START_DATE → today (max 21)
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
        # Prefer settled gainloss data (most accurate, includes all legs individually)
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
            "spreads":    "settled",
        })
    elif date in daily_orders_pnl:
        # Fallback: derive P&L from filled multileg orders (same-day, not yet settled)
        op    = daily_orders_pnl[date]
        gross = op["gross_pnl"]
        comm  = op["commission"]
        pnl_chart.append({
            "date":       date,
            "gross_pnl":  gross,
            "commission": comm,
            "net_pnl":    round(gross - comm, 2),
            "outcome":    "live",
            "contracts":  op["contracts"],
            "spreads":    "orders",
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
    "broker":       os.getenv("BROKER", "tradier"),
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
    "pnl_chart":        pnl_chart,
    "trade_log":        _load_trade_log(),
    "backtest_history": _fetch_gainloss_history(_get, ACCOUNT_ID, days=365),
}

# ── Write JS file ──────────────────────────────────────────────────────────────
out_path = _ROOT / "dashboard" / "tradier_account_data.js"
out_path.write_text(
    "window.TRADIER_DATA = " + json.dumps(payload, indent=2) + ";",
    encoding="utf-8",
)

trade_days   = [d for d in pnl_chart if d["outcome"] == "live"]
total_gross  = sum(d["gross_pnl"]  for d in trade_days)
total_net    = sum(d["net_pnl"]    for d in trade_days)
total_comm   = sum(d["commission"] for d in trade_days)
settled_days = sum(1 for d in trade_days if d["spreads"] == "settled")
orders_days  = sum(1 for d in trade_days if d["spreads"] == "orders")

print(f"Written -> {out_path}")
print(f"  Account   : {payload['profile']['account_number']} ({payload['profile']['name']})")
print(f"  Equity    : ${payload['balances']['total_equity']:,.2f}")
print(f"  Cash      : ${payload['balances']['total_cash']:,.2f}")
print(f"  Open P&L  : ${payload['balances']['open_pl']:+,.2f}")
print(f"  Positions : {len(positions)}")
print(f"  Orders    : {len(orders)}")
print(f"  PDT used  : {pdt_used}/3 in rolling window")
print(f"  Live P&L chart ({LIVE_START_DATE} onwards):")
print(f"    Trade days : {len(trade_days)} / {len(pnl_chart)} shown  ({settled_days} settled, {orders_days} from orders)")
print(f"    Gross P&L  : ${total_gross:+,.2f}")
print(f"    Commission : -${total_comm:,.2f}")
print(f"    Net P&L    : ${total_net:+,.2f}")

bt_trades = payload["backtest_history"]
if bt_trades:
    bt_net = sum(t["net_pnl"] for t in bt_trades)
    bt_wins = sum(1 for t in bt_trades if t["gross_pnl"] > 0)
    print(f"  Backtest history: {len(bt_trades)} IC round-trips from Tradier gain/loss API")
    print(f"    Win rate   : {bt_wins}/{len(bt_trades)} ({bt_wins/len(bt_trades)*100:.0f}%)")
    print(f"    Net P&L    : ${bt_net:+,.2f}")
else:
    print("  Backtest history: no data returned from Tradier gain/loss API")
