# CSAlgoTraderApp — Project Structure

## Directory Layout

```
c:\MyApp\CSAlgoTraderApp\
├── iron_condor_0dte/           ← Main trading package
│   ├── __init__.py
│   ├── config.py               # Strategy configuration (TARGET_DELTA, WING_WIDTH, etc.)
│   ├── live_trader.py          # Live trading execution engine
│   ├── tradier_client.py       # Tradier REST API wrapper
│   ├── trade_logger.py         # Trade log persistence (CSV + DB)
│   ├── options_pricing.py      # Black-Scholes option pricing
│   ├── backtest.py             # Backtesting engine (legacy)
│   └── run_backtest.py         # Backtest runner (legacy)
│
├── scripts/                    ← Executable entry points & tools
│   ├── run_live_iron_condor.bat        # Task Scheduler → start live trading
│   ├── run_backtest.py                 # 1-year historical backtest (yfinance)
│   ├── run_backtest.bat                # Windows batch wrapper for backtest
│   ├── run_manual_trade.py             # Manual trade entry (testing)
│   ├── generate_tradier_data.py        # Fetch live account data → JS payload
│   ├── run_dashboard.bat               # Start local HTTP server + browser
│   ├── backfill_trades.py              # Manually log historical trades
│   ├── resend_telegram_alert.py        # Resend missed alerts
│   ├── run_scheduled_iron_condor.bat   # (deprecated)
│   ├── setup_server.sh                 # EC2 deployment setup
│   └── nginx.conf                      # Nginx reverse proxy config
│
├── dashboard/                  ← Web UI (light theme)
│   ├── tradier_dashboard.html          # Main dashboard (Backtesting Results tab, charts)
│   ├── tradier_account_data.js         # Generated: live account data payload
│   ├── backtest_simulation.js          # Generated: 1-year simulation results
│   ├── index.html                      # (legacy/placeholder)
│   ├── backtest_data.js                # (legacy)
│   ├── forward_test_data.js            # (legacy)
│   └── *.json                          # Historical test data
│
├── data/                       ← Trade logs & state
│   ├── trades/
│   │   └── trade_log.csv               # Live trades CSV log (28 columns)
│   ├── logs/                           # Application logs (if local)
│   └── pdt_trades.json                 # PDT day-trade window state
│
├── tests/                      ← Unit tests
│   ├── test_config.py
│   ├── test_options_pricing.py
│   ├── test_tradier_client.py
│   └── __init__.py
│
├── .github/workflows/          ← CI/CD
│   └── ci.yml                          # GitHub Actions: lint, security, tests, config check
│
├── .env                        ← Environment (NOT tracked by git)
├── .gitignore
├── requirements.txt            ← Python dependencies
└── PROJECT_STRUCTURE.md        ← This file
```

## File Purposes

### Core Package (`iron_condor_0dte/`)

**config.py**
- Strategy parameters: delta target, wing width, entry/exit times
- Risk management: profit target %, stop loss multiplier
- PDT rule tracking
- VIX & FOMC filters

**live_trader.py**
- Main trading loop
- Order entry (Fix A/B/C: two-attempt credit limits, post-fill abort check)
- Position monitoring (profit target & stop loss checks)
- P&L calculation & position closing
- Integration with TradeLogger

**tradier_client.py**
- REST API wrapper for Tradier broker
- Authentication & session management
- Methods: `get_profile()`, `place_multileg_order()`, `get_orders()`, `cancel_order()`, `get_history()`
- Error handling & retry logic

**trade_logger.py**
- Dual-backend logging: CSV (local) + SQLite/PostgreSQL (AWS)
- 28-column trade record schema
- Auto-detect environment (LIVE vs sandbox) via EC2 IMDS
- Thread-safe append + retrieval methods

**options_pricing.py**
- Black-Scholes pricing: `call()`, `put()`, `call_delta()`
- Strike-finding: locate delta 0.15 short strikes
- IC valuation: combined spread pricing

### Scripts (`scripts/`)

**run_live_iron_condor.bat**
- Called by Task Scheduler at 9:00 AM CST (weekdays)
- Activates strategy at 10 AM ET, deactivates at 4 PM ET
- Triggers live_trader.py

**run_backtest.py**
- 1-year historical simulation using yfinance hourly SPY bars
- Replays all 252 trading days with real IV (VIX) data
- Uses OHLC intraday extremes to detect stop-loss triggers
- Outputs: `dashboard/backtest_simulation.js` (loaded by dashboard)
- Results: 94.4% win rate, $31.4k net P&L (simulation), max DD $585

**generate_tradier_data.py**
- Fetches live account snapshot from Tradier API
- Computes PDT usage, positions, open P&L
- Pulls traded history via gainloss API → reconstructs IC round-trips
- Embeds trade_log.csv into JS payload
- Outputs: `dashboard/tradier_account_data.js` (auto-refresh every 5 min)

**run_dashboard.bat**
- Starts Python `http.server` on port 8888
- Opens browser to `tradier_dashboard.html`

### Dashboard (`dashboard/`)

**tradier_dashboard.html**
- Light-themed trading dashboard
- Sections:
  - **Account Overview**: balance, open P&L, PDT tracker (compact card)
  - **Running P&L**: live positions + daily P&L chart
  - **Backtesting Results** (new): 12 metrics across 4 cards + 2 charts
    - **Equity Curve**: cumulative net P&L with SL dots
    - **Drawdown Curve**: peak-to-trough decline (max DD annotated)
    - **Profitability**: net profit, annualized return, win rate, profit factor
    - **Risk/Drawdown**: max drawdown, recovery factor, Ulcer Index
    - **Risk-Adjusted**: Sharpe, Sortino, Calmar ratios
    - **Execution**: avg trade, risk-reward ratio, consecutive losses/wins
  - **Trade-by-Trade**: 16-column table of all logged trades (sourced from Tradier API or CSV)

### Data (`data/`)

**trades/trade_log.csv**
- 28-column CSV: date, outcome, strikes, contracts, entry/exit credit, P&L, cumulative, VIX, etc.
- Loaded by `generate_tradier_data.py` into dashboard
- Managed by `trade_logger.py` (append mode)

**pdt_trades.json**
- JSON state file: list of day-trade dates in rolling 5-day window
- Updated after each trade close
- Used to enforce PDT rule

## Key Data Flows

### Live Trading (daily, 9 AM → 4 PM ET)

1. **Task Scheduler** fires `scripts/run_live_iron_condor.bat` at 9:00 AM CST
2. **live_trader.py** activates at 10:00 AM ET
3. Entry attempt at 10:15 AM:
   - Fetch SPY price, compute delta-0.15 strikes
   - Place credit-limit order (attempt 1: $0.40/shr, 180s timeout)
   - If rejected, retry at attempt 2: $0.30/shr, 120s timeout
   - If both fail: skip the day (outcome: no_fill)
4. **Post-fill check (Fix A)**:
   - If actual_credit < $0.10/shr: abort & exit immediately
5. **Monitoring loop** (every 5 min until 3:45 PM):
   - Check if IC value ≤ PT level (35% of entry) → close at profit_target
   - Check if IC value ≥ SL level (145% of entry) → close at stop_loss
6. **Force close** at 3:45 PM ET
7. **Log trade** to `data/trades/trade_log.csv` via TradeLogger

### Dashboard Refresh (every 5 min, market hours)

1. **generate_tradier_data.py** runs (via cron or manual)
2. Fetches:
   - Account profile, balances, positions
   - Trade history (gainloss API) → reconstructs IC trades from legs
   - PDT state
3. Computes:
   - Open P&L, margin utilization
   - Monthly P&L chart data
   - Historic trade table (from CSV + API)
4. Generates `tradier_account_data.js` (JSON payload)
5. **Dashboard** loads JS → renders live data

### Backtesting (on-demand, ~30 seconds)

1. **scripts/run_backtest.py** invoked
2. Downloads:
   - SPY hourly OHLC bars for past 365 days (yfinance)
   - VIX daily close (IV proxy)
   - Tradier market calendar (trading days only)
3. For each trading day:
   - Simulate entry at 10:15 AM using B-S pricing
   - Monitor intraday bars for PT/SL triggers (using High/Low for SL detection)
   - Record outcome & P&L
4. Generates `backtest_simulation.js` (full trade list + summary stats)
5. **Dashboard** loads → renders Backtesting Results tab

## Code Quality & Deployment

### CI/CD Pipeline (`.github/workflows/ci.yml`)

- **Lint**: ruff on `iron_condor_0dte/` + scripts
- **Security**: checks for .env tracking, hardcoded tokens, account data leaks
- **Tests**: pytest on Python 3.11 & 3.12, coverage floor 60%
- **Config check**: validates all strategy parameters (delta, wing, credits, timings)

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Manual trade entry (testing)
python scripts/run_manual_trade.py

# Generate dashboard data
python scripts/generate_tradier_data.py

# Run 1-year backtest
python scripts/run_backtest.py

# Start dashboard web server
scripts/run_dashboard.bat   # Windows
./scripts/setup_server.sh   # Linux/EC2
```

### AWS EC2 Deployment

1. Run `scripts/setup_server.sh` (creates venv, installs deps, sets env vars)
2. Configure `DEPLOYMENT_ENV=AWS` in `.env`
3. Task Scheduler/cron triggers `run_live_iron_condor.bat`
4. Trades logged to PostgreSQL (via DATABASE_URL)
5. nginx proxies port 80 → localhost:8888 (dashboard)

## Recent Changes (May 26–30, 2026)

✅ Fixed double `/v1/` path in Tradier API calls
✅ Implemented Fix A/B/C: two-attempt credit limits + post-fill abort check
✅ Added trade logging to CSV + SQLite with commission tracking
✅ Redesigned dashboard: dark → light theme, added Performance metrics
✅ Implemented Backtesting Results tab: 12 metrics + 2 charts (equity curve, drawdown)
✅ Added 1-year historical simulation using yfinance (94.4% win rate, $31.4k net)
✅ Integrated Tradier gainloss API for reconstructed IC trade history
✅ Created responsive mobile-friendly dashboard layout

## Known Limitations & TODOs

- **Win rate inflation**: Hourly bars miss sub-hourly spikes → live win rates ~75–85% vs sim 94%
- **Flat volatility**: B-S uses single sigma → real 0DTE skew is steeper (wings more expensive)
- **Commission estimate**: Uses $0.35/leg fixed; actual may vary by volume
- **PDT enforcement**: Tracked locally; production should validate against broker
- **Backtest data**: yfinance lookback ~2 years; Tradier API free tier ~90 days intraday

---

**Last updated**: May 30, 2026
