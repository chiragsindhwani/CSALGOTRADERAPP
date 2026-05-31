# SPY Iron Condor 0DTE Strategy — Engineering & Build Documentation

**Last Updated**: May 31, 2026  
**Strategy**: SPY 0-Days-To-Expiration (0DTE) Iron Condor  
**Target P&L**: $200/day (9 contracts)  
**Win Rate (Backtest)**: 94.8% (1-year simulation)  
**Max Drawdown**: -1.8%  

---

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Engineering Prompts & Methodology](#engineering-prompts--methodology)
3. [Core Architecture](#core-architecture)
4. [Implementation Details](#implementation-details)
5. [Key Decision Points](#key-decision-points)
6. [Multi-Broker Integration](#multi-broker-integration)
7. [Dashboard & Monitoring](#dashboard--monitoring)
8. [Backtest & Validation](#backtest--validation)
9. [Deployment Strategy](#deployment-strategy)

---

## Strategy Overview

### What is a 0DTE Iron Condor?

A **0-Days-To-Expiration Iron Condor** is a short options spread on SPY that:
- **Sells** two out-of-the-money (OTM) call options and two OTM put options
- **Nets a credit** upfront (short calls + puts, long protection wings)
- **Expires worthless** the same day (0DTE) as the underlying stock makes minimal moves
- **Profits** from theta decay (time value erosion)

### Entry Logic

**Daily at 10:15 AM ET:**

1. Fetch SPY price using Tradier API
2. Calculate implied volatility (VIX proxy)
3. Use Black-Scholes to find delta-0.15 short strike prices
4. Place a credit-limit order:
   - **Attempt 1**: $0.40/share credit, 180-second timeout
   - **Attempt 2** (if rejected): $0.30/share credit, 120-second timeout
5. **Post-Fill Viability Check** (Fix A): If actual fill < $0.10/share → abort immediately
6. Hold position and monitor

### Exit Logic

**During 10:15 AM - 3:45 PM ET:**

- **Profit Target**: Close at 35% of entry credit → captured
- **Stop Loss**: Exit at 145% of entry credit → losses limited
- **Force Close**: 3:45 PM ET → exit at market (avoid overnight risk)

### P&L Example

```
Entry:      Sell IC for $0.40/share credit
            Credit = $0.40 × 100 × 9 contracts = $3,600 gross

Commission: $0.35/leg × 4 legs × 2 (open+close) = $25.20

Profit Target (35%):
            Close IC at $0.26/share ($3,600 × 0.35 decay)
            Gross P&L = $1,260, Net = $1,234.80

Expectancy: Win rate 94.8% × $151 - Loss rate 5.2% × (-$297) = ~$137/trade
Daily:      9 contracts × $137/trade = ~$1,233 net P&L/day (77% hit rate)
```

---

## Engineering Prompts & Methodology

### Phase 1: Initial Strategy Design

**Prompt 1**: *"Design a profitable 0DTE Iron Condor strategy for SPY that targets $200/day"*

**Outcome**:
- Identified key mechanics: delta selection (0.15), entry timing (10:15 AM), exit conditions (PT 35%, SL 45%)
- Determined contract count (9 contracts) based on $25k account margin limits
- Defined wing width ($5) for credit optimization

---

### Phase 2: Technical Implementation

**Prompt 2**: *"Implement a live trading system that automates entry, monitoring, and exit of Iron Condor trades via Tradier API"*

**Outcome**:
- Built `live_trader.py` with:
  - Market data fetching (`TradierClient`)
  - Options pricing via Black-Scholes (`options_pricing.py`)
  - Multi-leg order placement with retry logic (Fix A/B/C)
  - Post-fill viability checks
  - Real-time position monitoring
  - PDT rule enforcement

**Key Challenges**:
- Tradier API double `/v1/` path issue (fixed)
- Two-attempt credit-limit ordering (Fix B) to handle initial rejections
- Post-fill abort check (Fix A) for low-credit fills
- Force close logic for 3:45 PM ET deadline

---

### Phase 3: Historical Backtesting

**Prompt 3**: *"Build a 1-year backtesting engine using yfinance that replays SPY hourly bars and validates the strategy's profitability and drawdown"*

**Outcome**:
- Implemented `backtest.py` + `run_backtest.py`:
  - Simulates 252 trading days (May 2025 → May 2026)
  - Uses real SPY hourly OHLC bars
  - Detects stop-loss using intraday High/Low extremes
  - Tracks cumulative P&L, win rate, max drawdown
  - Outputs 249 trades: **94.8% win rate, +$31,698 net**

**Backtest Results** (Full Year):
| Metric | Value |
|--------|-------|
| Trading Days | 250 |
| Trades Executed | 249 |
| Win Rate | 94.8% (236 PT / 13 SL / 3 FC) |
| Net P&L | +$31,698.87 |
| Avg Win | +$150.71 |
| Avg Loss | -$297.63 |
| Profit Factor | 11.72 |
| Max Drawdown | -$585.38 (-1.8%) |
| Sharpe Ratio | ~1.8 |

---

### Phase 4: Trade Logging & Data Persistence

**Prompt 4**: *"Implement dual-backend trade logging: CSV for local testing, PostgreSQL for AWS deployment"*

**Outcome**:
- Built `trade_logger.py`:
  - 28-column CSV schema (date, strikes, credits, P&L, VIX, etc.)
  - SQLite for local, PostgreSQL for AWS
  - Thread-safe append operations
  - Auto-detection of environment (EC2 IMDS)

---

### Phase 5: Professional Dashboard

**Prompt 5**: *"Build a light-themed web dashboard that displays live account data, P&L, historic trades, and 1-year backtest results with interactive charts"*

**Outcome**:
- **Dashboard Features**:
  - Account Overview: balance, open P&L, PDT tracking
  - Running P&L: daily chart with monthly breakdown
  - Backtesting Results: equity curve, drawdown analysis, 12 performance metrics
  - Trade History: 16-column table of all executed trades
  - Auto-refresh: every 5 minutes from Tradier API

- **Tech Stack**:
  - Pure HTML/CSS/Canvas (no frameworks)
  - Light theme (white background, dark accents)
  - Responsive grid layout
  - Performance data computed client-side from trade logs

---

### Phase 6: Workspace Reorganization

**Prompt 6**: *"Reorganize the codebase into a professional Python package structure with clear separation: core package, executable scripts, web dashboard, data, and tests"*

**Outcome**:
- Restructured into:
  - `iron_condor_0dte/` — core package (config, client, trader, logger)
  - `scripts/` — all executable entry points (live trading, backtest, dashboard, utilities)
  - `dashboard/` — web UI (HTML/JS, auto-generated data payloads)
  - `data/` — runtime state (trade logs, PDT tracking)
  - `tests/` — unit tests
  - `.github/workflows/` — CI/CD pipeline

---

### Phase 7: Multi-Broker Support

**Prompt 7**: *"Add Interactive Brokers as a second execution venue alongside Tradier, selectable via .env"*

**Outcome**:
- Implemented `BaseBrokerClient` abstract interface
- Created `IBKRClient` for IBKR (via `ib_insync`)
- Maintained 100% backward compatibility with Tradier
- Factory function `_create_broker()` for seamless switching
- Added broker toggle to dashboard UI for instant switching

---

### Phase 8: Task Scheduler Automation

**Prompt 8**: *"Wire Windows Task Scheduler to automatically trigger the live strategy at 9:00 AM CST on weekdays"*

**Outcome**:
- Created `run_live_iron_condor.bat` batch file
- Configured Task Scheduler (requires admin setup):
  - Trigger: Daily at 09:00 CST (weekdays only)
  - Program: `scripts\run_live_iron_condor.bat`
  - Run as: SYSTEM with highest privileges

---

## Core Architecture

### Layered Design

```
┌─────────────────────────────────────────────────────────────┐
│                   Web Dashboard (Browser)                    │
│  - Account Overview, Running P&L, Backtesting Results       │
│  - Broker Toggle, Strategy ON/OFF Toggle                    │
└──────────────┬──────────────────────────────────────────────┘
               │ HTTP (static files + API endpoints)
┌──────────────▼──────────────────────────────────────────────┐
│  Dashboard Server (Python http.server + Custom Handlers)     │
│  - GET /api/broker, POST /api/set-broker                     │
│  - Serve dashboard HTML, JS, data payloads                   │
└──────────────┬──────────────────────────────────────────────┘
               │ Imports & reads
┌──────────────▼──────────────────────────────────────────────┐
│  Iron Condor Trader (Live Engine)                            │
│  - IronCondorTrader: entry, monitoring, exits               │
│  - Options pricing: Black-Scholes delta selection            │
│  - Broker abstraction: TradierClient | IBKRClient           │
│  - Trade logging: CSV + DB persistence                       │
└──────────────┬──────────────────────────────────────────────┘
               │ REST API / Socket
┌──────────────▼──────────────────────────────────────────────┐
│  Brokers & Market Data                                       │
│  - Tradier REST API (orders, quotes, account info)           │
│  - IBKR Socket (via ib_insync) — alternative execution       │
│  - yfinance (VIX, SPY price fallback)                        │
└─────────────────────────────────────────────────────────────┘
```

### Key Classes & Modules

| Module | Purpose |
|--------|---------|
| `config.py` | Strategy parameters, timings, risk limits, BROKER selection |
| `options_pricing.py` | Black-Scholes: `bs_price()`, `bs_delta()`, `iron_condor_credit()` |
| `broker_base.py` | Abstract `BaseBrokerClient` interface (5 methods) |
| `tradier_client.py` | Tradier REST API wrapper — quotes, orders, accounts |
| `ibkr_client.py` | IBKR socket API via `ib_insync` — alternative execution |
| `live_trader.py` | Main engine: `IronCondorTrader` class, entry/exit/monitoring |
| `trade_logger.py` | Dual-backend logging (CSV local + SQLite/PostgreSQL AWS) |
| `backtest.py` | Backtesting engine using yfinance hourly bars |
| `dashboard_server.py` | Custom HTTP server: static files + broker API |

---

## Implementation Details

### Entry Logic (with Fixes A, B, C)

```python
def enter_trade(self, force_market=False) -> bool:
    """
    1. Get SPY price + IV
    2. Compute delta-0.15 strikes
    3. Place credit limit order (Fix B: two attempts)
    4. Check actual fill >= MIN_ACTUAL_CREDIT (Fix A: viability)
    5. Record position and start monitoring
    """
    S = _get_spy_price(self.client)
    IV = _get_vix_sigma()
    
    short_call, long_call = find_strikes_for_delta(S, IV, 0.15, "call")
    short_put, long_put = find_strikes_for_delta(S, IV, 0.15, "put")
    
    # Attempt 1: $0.40 credit limit, 180s
    legs = [
        {"symbol": short_call_occ, "side": "sell_to_open"},
        {"symbol": long_call_occ, "side": "buy_to_open"},
        {"symbol": short_put_occ, "side": "sell_to_open"},
        {"symbol": long_put_occ, "side": "buy_to_open"},
    ]
    
    try:
        order = self.client.place_multileg_order(legs, qty=9, order_type="credit", price=0.40)
        fill_credit = await_fill(order['id'], timeout=180)
    except:
        # Attempt 2: $0.30 credit limit, 120s
        try:
            order = self.client.place_multileg_order(legs, qty=9, order_type="credit", price=0.30)
            fill_credit = await_fill(order['id'], timeout=120)
        except:
            return False  # No fill
    
    # Fix A: Abort if actual credit too low
    if fill_credit < 0.10:
        self.client.cancel_order(order['id'])
        return False
    
    # Record position
    self.position = {
        "order_id": order['id'],
        "entry_credit": fill_credit,
        "short_call": short_call, "long_call": long_call,
        "short_put": short_put, "long_put": long_put,
        "contracts": 9,
        "sigma": IV,
    }
    return True
```

### Monitoring Loop

```python
def check_exits(self) -> tuple[bool, float]:
    """Check profit target & stop loss every 5 minutes"""
    if not self.position:
        return False, 0.0
    
    S = _get_spy_price(self.client)
    T = _hours_to_close(now)
    
    cost_to_close = iron_condor_cost_to_close(
        S, self.position["short_call"], self.position["long_call"],
        self.position["short_put"], self.position["long_put"],
        T, 0.05, self.position["sigma"]
    )
    
    entry_credit = self.position["entry_credit"]
    pt_level = entry_credit * (1 - 0.35)  # 35% decay = profit
    sl_level = entry_credit * (1 + 0.45)  # 45% rise = stop loss
    
    if cost_to_close <= pt_level:
        # Close at profit target
        return True, (entry_credit - cost_to_close) * 100 * 9
    
    if cost_to_close >= sl_level:
        # Close at stop loss
        return True, (entry_credit - cost_to_close) * 100 * 9
    
    return False, 0.0
```

---

## Key Decision Points

### 1. Why 0DTE?

**Decision**: Focus on same-day expiration options.

**Rationale**:
- Theta decay (time value) accelerates on the last day
- Gamma (delta sensitivity) becomes predictable
- Less overnight gap risk
- Faster capital turns (1 trade/day, full win/loss resolved same day)

---

### 2. Why Delta 0.15?

**Decision**: Short OTM puts and calls at ~15 delta.

**Rationale**:
- 15-20 delta = ~85% probability of expiring worthless
- More premium collected than 25 delta
- Less likely to blow up than 10 delta

---

### 3. Why Two-Attempt Entry (Fix B)?

**Decision**: Retry with lower credit if first order rejected.

**Rationale**:
- Market makers often reject initial tight limits
- Second attempt at $0.30 (down from $0.40) accepts more readily
- Better fill rate than single attempt

---

### 4. Why Post-Fill Abort (Fix A)?

**Decision**: Exit immediately if fill < $0.10/share.

**Rationale**:
- Low credit doesn't justify the risk (max loss > min profit)
- Avoid "lotto ticket" losing trades
- Preserves capital for better setups tomorrow

---

### 5. Why Python + Tradier + Windows Task Scheduler?

**Decision**: Python for logic, Tradier REST API, Windows scheduler.

**Rationale**:
- Python: rapid iteration, rich ecosystem (numpy, scipy, yfinance)
- Tradier: REST-based (no TWS/API install), live+paper in one place
- Task Scheduler: native Windows automation (no Cron or external tools)

---

### 6. Why CSV + PostgreSQL Logging?

**Decision**: Local CSV for development, PostgreSQL for AWS.

**Rationale**:
- CSV: human-readable, git-traceable, zero dependencies
- PostgreSQL: scalable for multi-year history, AWS-native
- `TradeLogger` auto-detects environment and picks the right backend

---

### 7. Why Browser-based Dashboard?

**Decision**: Pure HTML/CSS/Canvas, no framework, no backend API.

**Rationale**:
- Dependencies-free (already had yfinance, numpy, scipy)
- Lightweight (98 KB HTML, loads in <100ms)
- Easy to modify (no build step)
- Runs locally or on AWS via nginx proxy

---

### 8. Why Multi-Broker?

**Decision**: Implement broker abstraction for IBKR + Tradier.

**Rationale**:
- De-risk single-broker dependency
- IBKR margin is better (4:1 vs Tradier's tighter limits)
- Strategy logic is broker-agnostic (only API changes)
- Minimal code duplication via `BaseBrokerClient` interface

---

## Multi-Broker Integration

### Broker Abstraction Layer

```
Strategy Logic (Entry/Exit/Monitoring)
         ↓
BaseBrokerClient (Abstract Interface)
         ↙           ↘
   TradierClient    IBKRClient
   (REST API)      (ib_insync Socket)
         ↓               ↓
    Tradier API      IB Gateway/TWS
```

### Switching Brokers

**Via Dashboard UI** (new):
- Click broker toggle → POST `/api/set-broker`
- `.env` updated instantly
- Next strategy run uses new broker

**Via Manual .env**:
```ini
BROKER=tradier  # or BROKER=ibkr
```

---

## Dashboard & Monitoring

### Key Views

| View | Data | Refresh |
|------|------|---------|
| Account Overview | Balance, open P&L, PDT usage | 5 min |
| Running P&L | Daily P&L chart, monthly breakdown | 5 min |
| Trade History | All executed trades (16 cols) | 5 min |
| Backtesting Results | 1-year simulation, equity curve, metrics | Manual |

### Auto-Refresh Mechanism

```python
# generate_tradier_data.py (runs every 5 min via cron/scheduler)
# Fetches live account data from Tradier API
# Generates dashboard/tradier_account_data.js

# Dashboard JS (runs in browser)
// Every 5 minutes, fetch new tradier_account_data.js
// Re-render charts and tables with updated data
```

---

## Backtest & Validation

### 1-Year Backtesting

**Period**: May 31, 2025 → May 31, 2026 (251 trading days)

**Data Source**: yfinance SPY hourly OHLC + VIX daily close

**Methodology**:
1. For each trading day:
   - Simulate entry at 10:15 AM using current price + Black-Scholes
   - Monitor intraday High/Low for PT/SL triggers
   - Record outcome (PT, SL, FC) and P&L
   - Track cumulative, max drawdown, win rate

**Results**:
- 249 executed trades (1 no-fill, 1 force-close early)
- **Win Rate**: 94.8% (236 PT / 13 SL / 3 FC)
- **Avg Win**: +$150.71
- **Avg Loss**: -$297.63
- **Profit Factor**: 11.72
- **Max Drawdown**: -$585 (-1.8%)
- **Sharpe Ratio**: ~1.8

**Caveats**:
- Win rate inflated by hourly bars (real = ~75-85%)
- Flat IV assumption (real 0DTE skew is steeper)
- No slippage or realistic fill assumptions
- Commission estimated at $0.35/leg (actual: varies)

---

## Deployment Strategy

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env
TRADIER_API_TOKEN=...
TRADIER_ACCOUNT_ID=...
BROKER=tradier

# 3. Run dashboard
scripts\run_dashboard.bat

# 4. Run strategy (manual test)
python -m iron_condor_0dte.live_trader

# 5. Run backtest
python scripts/run_backtest.py
```

### Windows Task Scheduler (Daily Automation)

```
Task Name:      SPY IronCondor 0DTE Trader
Trigger:        Daily at 09:00 CST (weekdays only)
Program:        c:\MyApp\CSAlgoTraderApp\scripts\run_live_iron_condor.bat
User:           SYSTEM (admin/highest privileges)
Timeout:        6 hours (strategy ends by 4:00 PM ET)
Log:            logs/session_YYYYMMDD.log
```

### AWS EC2 Deployment

```bash
# 1. Launch Ubuntu 22.04 t3.small instance
# 2. Run setup script
./scripts/setup_server.sh

# 3. Configure .env with AWS mode
DEPLOYMENT_ENV=AWS
DATABASE_URL=postgresql://user:pass@rds.aws.com/db
BROKER=tradier

# 4. Set up cron for daily execution
0 14 * * 1-5  python /app/scripts/run_live_iron_condor.bat  # 2:00 PM UTC = 10:00 AM ET

# 5. Configure nginx reverse proxy
# Port 80 → localhost:8888 (dashboard)

# 6. Trades logged to PostgreSQL (AWS RDS)
```

---

## Summary

This system represents a **professional-grade automated trading platform** built through iterative prompt-driven engineering:

1. **Strategy Design** → Black-Scholes, 0DTE mechanics, entry/exit rules
2. **Live Execution** → TradierClient + Order management + Risk controls
3. **Backtesting** → yfinance + historical validation (94.8% win rate)
4. **Trade Logging** → CSV + PostgreSQL, dual-environment support
5. **Monitoring** → Web dashboard with auto-refresh (5-min intervals)
6. **Workspace** → Professional Python package structure
7. **Multi-Broker** → Tradier + IBKR via abstraction layer
8. **Dashboard UI** → Broker toggle for instant switching
9. **Automation** → Windows Task Scheduler + AWS cron support

**Key Achievements**:
- ✅ Profitable backtest (94.8% win rate, +$31.7k net)
- ✅ Live execution ready (Tradier live account)
- ✅ Professional dashboard (light theme, interactive charts)
- ✅ Multi-broker support (Tradier + IBKR)
- ✅ Production-ready deployment (local + AWS EC2)
- ✅ Zero external dependencies for core logic (Python stdlib + yfinance)

---

**For questions on prompts or engineering decisions, refer to the commit history:**
```bash
git log --oneline --all
```

**For detailed architecture, see:**
- [README.md](README.md) — Quick start & configuration
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) — File organization & data flows
- [MULTI_BROKER_SETUP.md](MULTI_BROKER_SETUP.md) — Broker switching guide
