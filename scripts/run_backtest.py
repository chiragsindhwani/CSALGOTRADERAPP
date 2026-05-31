#!/usr/bin/env python3
"""
SPY 0DTE Iron Condor — 1-Year Historical Backtest Simulation

For each trading day in the past year this script:
  1. Fetches SPY 5-min intraday prices from Tradier's timesales API
  2. Downloads VIX daily close from yfinance (IV proxy)
  3. At 10:15 AM ET — applies strategy entry rules:
       - Compute delta-0.15 short strikes (Black-Scholes)
       - Compute theoretical B-S credit for the $5-wide IC
       - Skip if credit < $0.30 (no fill on either limit attempt)
       - Assume fill at $0.40 (attempt 1) or $0.30 (attempt 2)
  4. Monitors every 5 min until:
       - Profit target hit  (B-S value decays 35% from entry)
       - Stop loss hit      (B-S value rises  45% from entry)
       - Force close        (3:45 PM ET)
  5. Computes P&L with actual-fill discount factor

Output:
  CS_ALGOTRADER_APP/backtest_simulation.js  (loaded by dashboard)

Usage:
  python run_backtest.py              # full 1-year backtest
  python run_backtest.py --days 90   # shorter lookback for testing
"""
from __future__ import annotations
import http.client, json, math, os, sys, time, urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent  # Go up from scripts/ to project root
sys.path.insert(0, str(ROOT))

# ── Load .env ──────────────────────────────────────────────────────────────────
for _line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    _line = _line.strip()
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

TOKEN = os.environ.get("TRADIER_API_TOKEN", "")
if not TOKEN:
    print("ERROR: TRADIER_API_TOKEN not set in .env")
    sys.exit(1)

ET = ZoneInfo("America/New_York")

# ── Strategy parameters (must match config.py) ─────────────────────────────────
WING_WIDTH       = 5.0
TARGET_DELTA     = 0.15
MIN_CREDIT_1     = 0.40    # attempt 1 limit
MIN_CREDIT_2     = 0.30    # attempt 2 limit
PT_PCT           = 0.35    # profit target: IC decays 35% of B-S entry
SL_MULT          = 0.45    # stop loss:    IC rises  45% of B-S entry
CONTRACTS        = 9
COMMISSION       = 4 * CONTRACTS * 0.35 * 2   # $25.20 round-trip
R                = 0.05    # risk-free rate

ENTRY_HOUR, ENTRY_MIN         = 10, 15
FORCE_CLOSE_HOUR, FORCE_CLOSE_MIN = 15, 45

# ── Tradier HTTP helper ────────────────────────────────────────────────────────
_HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

def _tget(path: str) -> dict:
    conn = http.client.HTTPSConnection("api.tradier.com", timeout=20)
    conn.request("GET", path, headers=_HEADERS)
    resp = conn.getresponse()
    body = resp.read().decode()
    conn.close()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}

# ── Black-Scholes helpers ──────────────────────────────────────────────────────
def _nd(x: float) -> float:
    t = 1 / (1 + 0.2316419 * abs(x))
    p = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
        + t * (-1.821255978 + t * 1.330274429))))
    v = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-x * x / 2) * p
    return v if x >= 0 else 1 - v

def _bs_put(S, K, T, r, sigma):
    if T <= 0: return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * _nd(-d2) - S * _nd(-d1)

def _bs_call(S, K, T, r, sigma):
    if T <= 0: return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _nd(d1) - K * math.exp(-r * T) * _nd(d2)

def _bs_call_delta(S, K, T, r, sigma):
    if T <= 0: return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return _nd(d1)

def _find_strike(S, T, r, sigma, target_delta, opt):
    lo, hi = S * 0.3, S * 1.7
    for _ in range(60):
        mid = (lo + hi) / 2
        d   = _bs_call_delta(S, mid, T, r, sigma)
        if opt == "call":
            if d > target_delta: lo = mid
            else: hi = mid
        else:
            d_put = d - 1
            if abs(d_put) > target_delta: hi = mid
            else: lo = mid
    return (lo + hi) / 2

def ic_credit(S, SC, LC, SP, LP, T, r, sigma):
    T = max(T, 1e-9)
    return (_bs_call(S, SC, T, r, sigma) - _bs_call(S, LC, T, r, sigma)
          + _bs_put(S, SP, T, r, sigma)  - _bs_put(S, LP, T, r, sigma))

def hours_to_expiry(hour, minute):
    """Fraction of trading year from given time to 4 PM close."""
    remaining_min = max((16 * 60) - (hour * 60 + minute), 0)
    return remaining_min / 60 / 6.5 / 252

# ── Data fetchers ──────────────────────────────────────────────────────────────
def get_trading_days(start: date, end: date) -> list[date]:
    """Get list of market-open days from Tradier calendar API."""
    days: list[date] = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        data = _tget(f"/v1/markets/calendar?month={cur.month}&year={cur.year}")
        cal  = (data.get("calendar") or {}).get("days", {})
        raw  = (cal or {}).get("day", [])
        if isinstance(raw, dict): raw = [raw]
        for d in (raw or []):
            if d.get("status") == "open":
                dt = date.fromisoformat(d["date"])
                if start <= dt <= end:
                    days.append(dt)
        cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        time.sleep(0.15)
    return sorted(days)

def get_spy_hourly(start: date, end: date) -> dict[str, list[tuple]]:
    """
    Download SPY 1-hour OHLC bars for the full date range using yfinance.
    yfinance provides hourly data for up to 730 days.
    Returns {YYYY-MM-DD: [(hour_ET, minute_ET, open, high, low, close), ...]}
    The High and Low are used to detect intraday stop-loss triggers.
    """
    import yfinance as yf
    from zoneinfo import ZoneInfo
    ET_tz = ZoneInfo("America/New_York")

    spy = yf.download(
        "SPY",
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1h",
        progress=False,
        auto_adjust=True,
    )

    daily: dict[str, list[tuple]] = {}
    for idx, row in spy.iterrows():
        if hasattr(idx, "tz_convert"):
            idx_et = idx.tz_convert(ET_tz)
        elif hasattr(idx, "tz_localize") and idx.tzinfo is None:
            idx_et = idx.tz_localize("UTC").tz_convert(ET_tz)
        else:
            idx_et = idx

        d_str = idx_et.strftime("%Y-%m-%d")
        h, m  = idx_et.hour, idx_et.minute
        if not (9 <= h <= 15):
            continue

        def _f(col):
            v = row[col]
            return float(v.iloc[0]) if hasattr(v, "iloc") else float(v)

        o, hi, lo, c = _f("Open"), _f("High"), _f("Low"), _f("Close")
        if c <= 0:
            continue
        daily.setdefault(d_str, []).append((h, m, o, hi, lo, c))

    for d_str in daily:
        daily[d_str].sort()
    return daily

def get_vix_history(start: date, end: date) -> dict[str, float]:
    """Download ^VIX daily close. Returns {YYYY-MM-DD: sigma}."""
    try:
        import yfinance as yf
        vix = yf.download(
            "^VIX",
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d", progress=False, auto_adjust=True,
        )
        result = {}
        for idx, row in vix.iterrows():
            dt    = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            close_val = row["Close"]
            close_f = float(close_val.iloc[0]) if hasattr(close_val, "iloc") else float(close_val)
            result[dt.isoformat()] = close_f / 100.0
        return result
    except Exception as e:
        print(f"  [WARN] VIX download failed: {e}  →  using 16% fallback")
        return {}

# ── Core simulation ───────────────────────────────────────────────────────────
def simulate_day(
    bars:  list[tuple],   # (h, m, open, high, low, close)
    sigma: float,
) -> dict | None:
    """
    Simulate one 0DTE IC session using SPY hourly OHLC bars.

    Stop-loss check uses the bar's HIGH (worst case for short call) and LOW
    (worst case for short put) so intraday spikes are captured even with
    hourly data.  Profit-target uses the bar's CLOSE (conservative).
    """
    # ── Find entry bar ────────────────────────────────────────────────────────
    entry = next(
        (b for b in bars if b[0] > ENTRY_HOUR or (b[0] == ENTRY_HOUR and b[1] >= ENTRY_MIN)),
        None,
    )
    if not entry:
        return None

    S     = entry[5]            # use close of the first bar at/after 10:xx
    T_ent = hours_to_expiry(ENTRY_HOUR, ENTRY_MIN)
    if T_ent <= 0:
        return None

    # ── Strikes ───────────────────────────────────────────────────────────────
    try:
        SC = round(_find_strike(S, T_ent, R, sigma, TARGET_DELTA, "call"))
        SP = round(_find_strike(S, T_ent, R, sigma, TARGET_DELTA, "put"))
    except Exception:
        return None

    LC = SC + WING_WIDTH
    LP = SP - WING_WIDTH

    try:
        bs_ent = ic_credit(S, SC, LC, SP, LP, T_ent, R, sigma)
    except Exception:
        return None

    # ── Credit limit check ────────────────────────────────────────────────────
    if bs_ent >= MIN_CREDIT_1:
        actual_credit = MIN_CREDIT_1
    elif bs_ent >= MIN_CREDIT_2:
        actual_credit = MIN_CREDIT_2
    else:
        return {"outcome": "no_fill", "bs_credit": round(bs_ent, 4)}

    discount = actual_credit / max(bs_ent, 1e-9)
    PT_level = bs_ent * (1 - PT_PCT)
    SL_level = bs_ent * (1 + SL_MULT)

    # ── Monitor hourly bars ───────────────────────────────────────────────────
    outcome   = "force_close"
    close_bs  = None
    close_hm  = (FORCE_CLOSE_HOUR, FORCE_CLOSE_MIN)
    past_entry = False

    for h, m, bar_open, bar_high, bar_low, bar_close in bars:
        if not past_entry:
            if h > ENTRY_HOUR or (h == ENTRY_HOUR and m > ENTRY_MIN):
                past_entry = True
            else:
                continue

        # Force close
        if h > FORCE_CLOSE_HOUR or (h == FORCE_CLOSE_HOUR and m >= FORCE_CLOSE_MIN):
            T_now    = hours_to_expiry(FORCE_CLOSE_HOUR, FORCE_CLOSE_MIN)
            close_bs = ic_credit(bar_close, SC, LC, SP, LP, max(T_now, 1e-9), R, sigma)
            close_hm = (h, m)
            outcome  = "force_close"
            break

        T_now = max(hours_to_expiry(h, m), 1e-9)

        # ── SL check: use intraday extremes ───────────────────────────────────
        # A move UP hurts the short call side → check bar HIGH
        # A move DOWN hurts the short put side → check bar LOW
        try:
            ic_hi  = ic_credit(bar_high,  SC, LC, SP, LP, T_now, R, sigma)
            ic_lo  = ic_credit(bar_low,   SC, LC, SP, LP, T_now, R, sigma)
            ic_cls = ic_credit(bar_close, SC, LC, SP, LP, T_now, R, sigma)
        except Exception:
            continue

        worst_ic = max(ic_hi, ic_lo, ic_cls)

        if worst_ic >= SL_level:
            outcome  = "stop_loss"
            close_bs = worst_ic
            close_hm = (h, m)
            break

        # ── PT check: use closing value only (conservative) ───────────────────
        if ic_cls <= PT_level:
            outcome  = "profit_target"
            close_bs = ic_cls
            close_hm = (h, m)
            break

    if close_bs is None:
        if bars:
            lh, lm, lo, lhi, llo, lc = bars[-1]
            close_bs = ic_credit(lc, SC, LC, SP, LP, max(hours_to_expiry(lh, lm), 1e-9), R, sigma)
            close_hm = (lh, lm)
        else:
            close_bs = 0.0
        outcome = "force_close"

    # ── P&L ──────────────────────────────────────────────────────────────────
    actual_close = close_bs * discount
    gross_pnl    = round((actual_credit - actual_close) * 100 * CONTRACTS, 2)
    net_pnl      = round(gross_pnl - COMMISSION, 2)

    return {
        "outcome":       outcome,
        "close_time":    f"{close_hm[0]:02d}:{close_hm[1]:02d} ET",
        "spy_entry":     round(S, 2),
        "long_put":      LP,
        "short_put":     SP,
        "short_call":    SC,
        "long_call":     LC,
        "bs_credit":     round(bs_ent, 4),
        "actual_credit": actual_credit,
        "exit_bs":       round(close_bs, 4),
        "actual_close":  round(actual_close, 4),
        "gross_pnl":     gross_pnl,
        "commission":    COMMISSION,
        "net_pnl":       net_pnl,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def run(lookback_days: int = 365):
    today      = datetime.now(ET).date()
    start_date = today - timedelta(days=lookback_days)

    print(f"\n  Fetching trading calendar ({start_date} to {today})...")
    trading_days = get_trading_days(start_date, today)
    # Exclude today unless market is closed
    now_et = datetime.now(ET)
    if now_et.hour < 16 or now_et.weekday() >= 5:
        trading_days = [d for d in trading_days if d < today]
    n_days = len(trading_days)
    print(f"  {n_days} trading days found")

    print("  Downloading SPY hourly bars from Yahoo Finance (covers 730 days)...")
    spy_daily = get_spy_hourly(start_date, today)
    print(f"  SPY data: {len(spy_daily)} trading days with hourly bars")

    print("  Downloading VIX history from Yahoo Finance...")
    vix = get_vix_history(start_date, today)
    print(f"  VIX data: {len(vix)} days")

    trades: list[dict] = []
    cum    = 0.0

    for i, d in enumerate(trading_days):
        d_str = d.isoformat()
        pct   = (i + 1) / n_days * 100

        # VIX sigma: use this day's close, or nearest prior day
        sigma = None
        for lag in range(5):
            sigma = vix.get((d - timedelta(days=lag)).isoformat())
            if sigma:
                break
        if not sigma:
            sigma = 0.16

        # Get SPY bars from pre-downloaded data (no API call per day)
        bars = spy_daily.get(d_str, [])

        if not bars:
            print(f"  [{pct:5.1f}%] {d_str}: no SPY bars — skipped (holiday/data gap)")
            continue

        result = simulate_day(bars, sigma)
        if result is None:
            continue

        outcome = result["outcome"]

        if outcome == "no_fill":
            entry_bar = next(
                (b for b in bars if b[0] > ENTRY_HOUR or (b[0] == ENTRY_HOUR and b[1] >= ENTRY_MIN)),
                None,
            )
            spy_price = round(entry_bar[5], 2) if entry_bar else 0
            trades.append({
                "date": d_str, "outcome": "no_fill",
                "spy_entry": spy_price,
                "vix_pct": round(sigma * 100, 1),
                "bs_credit": result.get("bs_credit", 0),
                "gross_pnl": 0.0, "commission": 0.0, "net_pnl": 0.0,
                "cumulative_pnl": round(cum, 2),
            })
            print(f"  [{pct:5.1f}%] {d_str}: NO FILL  SPY={spy_price:.2f}  VIX={sigma*100:.1f}%  B-S={result.get('bs_credit',0):.4f}")
            continue

        net    = result["net_pnl"]
        cum    = round(cum + net, 2)
        tag    = {"profit_target": "PT", "stop_loss": "SL", "force_close": "FC"}.get(outcome, outcome[:2].upper())

        trades.append({
            "date":           d_str,
            "vix_pct":        round(sigma * 100, 1),
            "cumulative_pnl": cum,
            **result,
        })

        print(
            f"  [{pct:5.1f}%] {d_str}: {tag:2s}  "
            f"SPY={result['spy_entry']:.2f}  VIX={sigma*100:.1f}%  "
            f"B-S={result['bs_credit']:.4f}  fill={result['actual_credit']:.2f}  "
            f"net=${net:+.2f}  cum=${cum:+.2f}"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    live = [t for t in trades if t["outcome"] != "no_fill"]
    wins = [t for t in live if t.get("net_pnl", 0) > 0]
    loss = [t for t in live if t.get("net_pnl", 0) <= 0]
    by_outcome = {o: sum(1 for t in live if t["outcome"] == o)
                  for o in ("profit_target", "stop_loss", "force_close")}
    gross_wins  = sum(t["gross_pnl"] for t in wins)
    gross_loss  = abs(sum(t["gross_pnl"] for t in loss))

    # Max drawdown from peak
    peak, trough, max_dd = 0.0, 0.0, 0.0
    run_cum = 0.0
    for t in live:
        run_cum += t.get("net_pnl", 0)
        if run_cum > peak: peak = run_cum
        dd = peak - run_cum
        if dd > max_dd: max_dd = dd; trough = run_cum

    summary = {
        "total_trading_days":  n_days,
        "trade_days":          len(live),
        "no_fill_days":        sum(1 for t in trades if t["outcome"] == "no_fill"),
        "wins":                len(wins),
        "losses":              len(loss),
        "by_outcome":          by_outcome,
        "win_rate":            round(len(wins) / max(len(live), 1) * 100, 1),
        "net_pnl":             round(cum, 2),
        "gross_pnl":           round(sum(t.get("gross_pnl", 0) for t in live), 2),
        "total_commission":    round(COMMISSION * len(live), 2),
        "profit_factor":       round(gross_wins / gross_loss, 2) if gross_loss > 0 else None,
        "max_drawdown":        round(-max_dd, 2),
        "max_drawdown_pct":    round(-max_dd / max(peak, 1) * 100, 1) if peak > 0 else 0,
        "avg_win":             round(sum(t.get("net_pnl", 0) for t in wins) / max(len(wins), 1), 2),
        "avg_loss":            round(sum(t.get("net_pnl", 0) for t in loss) / max(len(loss), 1), 2),
    }

    payload = {
        "generated_at": datetime.now(ET).isoformat(),
        "period": {
            "start": start_date.isoformat(),
            "end":   today.isoformat(),
            "lookback_days": lookback_days,
        },
        "strategy": {
            "wing_width":         WING_WIDTH,
            "target_delta":       TARGET_DELTA,
            "min_credit_1":       MIN_CREDIT_1,
            "min_credit_2":       MIN_CREDIT_2,
            "profit_target_pct":  PT_PCT,
            "stop_loss_mult":     SL_MULT,
            "contracts":          CONTRACTS,
            "commission_per_trade": COMMISSION,
        },
        "summary":  summary,
        "trades":   trades,
    }

    # ── Write output ──────────────────────────────────────────────────────────
    out = ROOT / "dashboard" / "backtest_simulation.js"
    out.write_text(
        "window.BACKTEST_SIMULATION = " + json.dumps(payload, indent=2) + ";",
        encoding="utf-8",
    )

    s = summary
    print()
    print("=" * 65)
    print("  SIMULATION COMPLETE")
    print("=" * 65)
    print(f"  Period         : {start_date} to {today}")
    print(f"  Trading days   : {n_days}  |  Trades: {s['trade_days']}  |  No fill: {s['no_fill_days']}")
    print(f"  Win Rate       : {s['wins']}/{s['trade_days']} = {s['win_rate']}%")
    print(f"  By outcome     : PT={by_outcome.get('profit_target',0)}  SL={by_outcome.get('stop_loss',0)}  FC={by_outcome.get('force_close',0)}")
    print(f"  Net P&L        : ${s['net_pnl']:+,.2f}")
    print(f"  Avg Win        : ${s['avg_win']:+.2f}  |  Avg Loss: ${s['avg_loss']:+.2f}")
    print(f"  Profit Factor  : {s['profit_factor'] or 'N/A'}")
    print(f"  Max Drawdown   : ${abs(s['max_drawdown']):,.2f} ({abs(s['max_drawdown_pct']):.1f}%)")
    print(f"  Saved to       : {out}")
    print()


if __name__ == "__main__":
    days = 365
    if "--days" in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index("--days") + 1])
        except (IndexError, ValueError):
            pass

    print("=" * 65)
    print("  SPY 0DTE Iron Condor — Historical Backtest Simulation")
    print(f"  Lookback: {days} calendar days")
    print("  Data source: yfinance SPY 1-hour bars (2-year history)")
    print("=" * 65)
    run(days)
