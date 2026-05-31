# SPY 0DTE Iron Condor Trading System

**Automated 0-days-to-expiry (0DTE) options strategy targeting $200/day** on the SPY, with live execution via Tradier, complete backtesting, and a professional light-themed dashboard.

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Tradier account (paper or live)
- Windows Task Scheduler or Linux cron (for daily automation)

### 2. Installation

```bash
# Clone & enter directory
cd c:\MyApp\CSAlgoTraderApp

# Install dependencies
pip install -r requirements.txt

# Create & fill .env with your credentials
# (See .env.example or section below)
```

### 3. Run the Strategy

**Option A: Live Trading (automated)**
```batch
# Task Scheduler will call this at 9:00 AM CST (weekdays)
scripts\run_live_iron_condor.bat
```

**Option B: Manual Trade Entry (testing)**
```bash
python scripts/run_manual_trade.py
```

**Option C: Dashboard Only (view live positions)**
```batch
scripts\run_dashboard.bat
```
Then open `http://localhost:8888/tradier_dashboard.html` in your browser.

### 4. View Results

- **Dashboard**: Open `dashboard/tradier_dashboard.html` in browser (served by `run_dashboard.bat`)
- **Trade Log**: `data/trades/trade_log.csv` — all executed trades with P&L
- **Backtesting Results**: Click **"Backtesting Results"** tab in dashboard to see 1-year simulation metrics

---

## Configuration

### Environment Variables (`.env`)

```ini
# Tradier API
TRADIER_API_TOKEN=your_api_token_here
TRADIER_ACCOUNT_ID=your_account_id
TRADIER_PAPER_TRADE=false         # false=live, true=paper

# (Optional) AWS deployment
DEPLOYMENT_ENV=LOCAL              # LOCAL or AWS
DATABASE_URL=postgresql://...     # Only for AWS+PostgreSQL
```

### Strategy Parameters (`iron_condor_0dte/config.py`)

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `TARGET_DELTA` | 0.15 | Short strike delta (OTM, lower risk) |
| `WING_WIDTH` | $5.00 | Spread width ($5 = longer wings, more credit) |
| `MIN_CREDIT` | $0.40 | Credit limit order floor (attempt 1) |
| `MIN_ACTUAL_CREDIT` | $0.10 | Abort threshold if fill is worse |
| `PROFIT_TARGET_PCT` | 35% | Close when IC decays 35% of credit |
| `STOP_LOSS_MULT` | 45% | Exit when IC rises 45% of credit |
| `CONTRACTS` | 9 | Contracts per trade (margin-limited) |
| `ENTRY_HOUR:MIN` | 10:15 | Entry time (ET) |
| `FORCE_CLOSE_HOUR:MIN` | 15:45 | Force-close time (ET, 3:45 PM) |

---

## Strategy Overview

### Entry (10:15 AM ET)

1. **Fetch SPY price & IV** → compute delta-0.15 short strikes
2. **Place credit-limit order** (Iron Condor: short P/C + long wings)
   - **Attempt 1**: limit price = $0.40/shr, 180 sec timeout
   - **Attempt 2** (if rejected): limit price = $0.30/shr, 120 sec timeout
   - **No fill**: skip the day
3. **Post-fill check (Fix A)**: if actual credit < $0.10/shr → abort & exit immediately

### Management (10:15 AM → 3:45 PM ET)

- **Profit Target**: IC value decays 35% → close at profit
- **Stop Loss**: IC value rises 45% → cut losses
- **Force Close**: 3:45 PM ET → close at market

### P&L

- Commission: $0.35/leg × 4 legs × 2 (open+close) = $25.20/trade
- Example: $0.40 credit × 900 shr = $360 gross → $134.80 net (after $25.20 commission)

---

## One-Year Backtest Results

**Period**: May 30, 2025 → May 29, 2026 (251 trading days)

| Metric | Value |
|--------|-------|
| Trades | 250 |
| Win Rate | 94.4% (236 PT / 14 SL / 3 FC) |
| **Net P&L** | **+$31,422** |
| Avg Win | +$150.71 |
| Avg Loss | −$296.12 |
| Profit Factor | 10.95 |
| Max Drawdown | −$585 (−1.9%) |
| Sharpe Ratio | ~1.8 |

**Caveats**:
- Win rate is optimistic (hourly bars miss sub-hourly spikes)
- Real live performance ~75–85% win rate expected
- No slippage or realistic fill assumptions modeled
- Flat volatility assumption (no skew)

---

## Project Structure

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed file organization.

**Quick reference**:
```
iron_condor_0dte/     ← Core trading package
scripts/              ← Executable entry points & utilities
dashboard/            ← Web UI (HTML + JS)
data/                 ← Trade logs, state, PDT tracking
tests/                ← Unit tests
.github/workflows/    ← CI/CD pipeline
```

---

## Development

### Run Tests

```bash
pytest tests/ -v --cov=iron_condor_0dte --cov-report=term-missing
```

### Lint

```bash
ruff check iron_condor_0dte/ scripts/ --ignore E501,E402
```

### Manual Backtest

```bash
python scripts/run_backtest.py           # Full 1-year simulation
python scripts/run_backtest.py --days 30 # Last 30 days only
```

### Backfill Historical Trades

```bash
python scripts/backfill_trades.py  # Manually add past trades to CSV
```

---

## Deployment (AWS EC2)

1. Launch Ubuntu 22.04 t3.small instance
2. Run setup:
   ```bash
   ./scripts/setup_server.sh
   ```
3. Set `.env` with `DEPLOYMENT_ENV=AWS` + PostgreSQL `DATABASE_URL`
4. Configure Linux cron or systemd timer to call `run_live_iron_condor.bat` daily
5. Access dashboard via nginx proxy (port 80)

---

## Key Features

✅ **Live Trading** — automated order entry + management via Tradier  
✅ **Two-Attempt Credit Limits** — retry failed orders at lower price  
✅ **Post-Fill Viability Check** — abort if actual credit too low  
✅ **Professional Dashboard** — light theme, live P&L, trade history  
✅ **1-Year Backtesting** — 252 trading days, real SPY hourly bars + VIX data  
✅ **Dual-Backend Logging** — CSV (local) + PostgreSQL (AWS)  
✅ **PDT Rule Compliance** — enforced 3-day-trades / 5-day-window  
✅ **Telegram Alerts** — entry, exit, abort notifications  
✅ **CI/CD Pipeline** — automated linting, security checks, tests, config validation  

---

## Troubleshooting

### Dashboard not loading

- Verify `run_dashboard.bat` started the server on port 8888
- Check: `http://localhost:8888/tradier_dashboard.html`
- If blank, open browser dev tools (F12) → Console for JS errors

### Trade not entering at 10:15 AM

- Check Task Scheduler is **enabled** and scheduled correctly
- Verify `.env` has valid Tradier API token & account ID
- Check **VIX < 30** (market filter to skip extreme volatility)
- Review logs in `data/logs/`

### Backtesting gives unrealistic results

- Win rate ~94% in simulation but only ~80% live?
  - **Hourly bars miss intraday spikes** → SL not triggered as often
  - **Flat IV assumption** → real 0DTE skew makes wings pricier
  - **No slippage modeled** → fills are theoretical B-S prices
- For conservative estimate: apply **80% win rate, 20% worse fills** to results

### .env file not being read

- Ensure `.env` is in the **root directory** (`c:\MyApp\CSAlgoTraderApp\.env`)
- Check credentials are not quoted (no `TRADIER_API_TOKEN="xyz"`, use `TRADIER_API_TOKEN=xyz`)

---

## Support & Contributions

- **Questions?** Check [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed architecture
- **Issues?** Review `.github/workflows/ci.yml` config checks — they validate all critical parameters
- **Want to contribute?** All PRs must pass linting, security gates, and tests

---

## License & Disclaimers

⚠️ **Trading involves significant risk.** This strategy is provided for educational purposes. Past performance ≠ future results. Always:
- Paper-trade first
- Start with small position sizes
- Understand your broker's PDT rules
- Monitor positions actively
- Use appropriate risk management

**No guarantees** are made about profitability or correctness of the strategy logic.

---

**Last Updated**: May 30, 2026
