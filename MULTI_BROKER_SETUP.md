# Multi-Broker Configuration Guide

This strategy now supports both **Tradier** and **Interactive Brokers (IBKR)** as execution brokers, selectable via `.env`.

---

## Quick Start: Tradier (Default)

**Current setup**: No changes needed. Tradier is the default broker.

```bash
# Strategy runs with Tradier automatically
python -m iron_condor_0dte.live_trader
```

✅ **Status**: Ready for live trading (Tradier live account configured in `.env`)

---

## Setup: Interactive Brokers (IBKR)

### Prerequisites
1. Interactive Brokers account (apply at https://www.interactivebrokers.com)
2. Create a **paper trading account** for testing
3. Download **IB Gateway** (headless version of TWS)

### Step 1: Download & Start IB Gateway

**Option A: IB Gateway (Recommended)**
- Latest version: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php
- Stable version: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

After installation, start IB Gateway:
- Paper account: connects to port **4002**
- Live account: connects to port **4001**

**Option B: TWS Desktop (Alternative)**
- Download: https://www.interactivebrokers.com/en/trading/tws.php
- Paper account: connects to port **7497**
- Live account: connects to port **7496**

### Step 2: Log in to IB Gateway

1. Start IB Gateway
2. Log in with your IBKR credentials
3. Leave it running in the background (does not need to be visible)

### Step 3: Configure `.env`

Edit `.env` and update:

```ini
# Switch to IBKR
BROKER=ibkr

# IBKR Connection (adjust port if using TWS instead of Gateway)
IBKR_HOST=127.0.0.1
IBKR_PORT=4002              # 4002 for Gateway paper, 4001 for Gateway live
IBKR_CLIENT_ID=1
IBKR_ACCOUNT_ID=DU1234567   # Your IBKR paper account ID
IBKR_PAPER_TRADE=true       # false for live trading

# Keep Tradier config for reference (won't be used)
TRADIER_API_TOKEN=...
TRADIER_ACCOUNT_ID=...
TRADIER_PAPER_TRADE=false
```

### Step 4: Run the Strategy

```bash
# Verify connection
python verify_broker_setup.py

# Run the strategy
python -m iron_condor_0dte.live_trader

# Or via Task Scheduler
scripts\run_live_iron_condor.bat
```

---

## How to Find Your IBKR Account ID

**Method 1: IB Gateway**
1. Log in to IB Gateway
2. Account ID is displayed on the main window (format: `DU1234567`)

**Method 2: Online at ibkr.com**
1. Log in to Client Portal
2. Account → Summary
3. Copy the account number

---

## Troubleshooting

### "Connection refused: No connection could be made"
**Problem**: IB Gateway not running or on wrong port

**Solution**:
- Start IB Gateway (it runs silently)
- Verify port 4002 is correct (or 4001 for live, 7497 for TWS paper)
- Check `.env` has correct `IBKR_PORT`

### "Connection timed out"
**Problem**: IB Gateway crashed or connection lost

**Solution**:
- Restart IB Gateway
- The strategy will automatically retry on next trade entry

### Account shows as empty/no positions
**Problem**: Connected to wrong account or IB Gateway disconnected

**Solution**:
- Verify `IBKR_ACCOUNT_ID` matches the logged-in account
- Check IB Gateway is still running
- Restart IB Gateway if needed

---

## Switching Between Brokers

**To switch back to Tradier**:
```ini
BROKER=tradier
```

**To switch to IBKR**:
```ini
BROKER=ibkr
IBKR_ACCOUNT_ID=DU1234567
```

The factory function automatically selects the correct broker when the strategy starts.

---

## Architecture

Both brokers implement the same interface (`BaseBrokerClient`):

```python
# Common interface
get_quote(symbol)              → market prices
get_profile()                  → account info
place_multileg_order(...)      → place Iron Condor trade
get_order(order_id)            → check order status
cancel_order(order_id)         → cancel pending order
```

**Tradier** uses REST API (HTTP).  
**IBKR** uses IB Gateway (socket protocol via `ib_insync`).

The strategy logic is **identical on both brokers** — entry/exit rules, P&L calculations, Telegram alerts, etc.

---

## Live vs. Paper Trading

### Paper Trading (Recommended for testing)
```ini
BROKER=ibkr
IBKR_PAPER_TRADE=true
IBKR_ACCOUNT_ID=DU1234567     # Paper account
IBKR_PORT=4002                # Paper port
```

### Live Trading
```ini
BROKER=ibkr
IBKR_PAPER_TRADE=false
IBKR_ACCOUNT_ID=DU9876543     # Live account
IBKR_PORT=4001                # Live port
```

⚠️ **Warning**: Live trading executes real trades with real money. Start with paper trading.

---

## Verification

Run the verification script to check your setup:

```bash
python verify_broker_setup.py
```

Expected output:
```
[OK] All broker clients imported
[OK] TradierClient extends BaseBrokerClient: True
[OK] IBKRClient extends BaseBrokerClient: True
[OK] Tradier broker created: TradierClient
[OK] IBKR broker attempted (connection refused -- IB Gateway not running)
[OK] IronCondorTrader instantiated with Tradier
SUMMARY: Multi-broker support ready!
```

---

## Support & Issues

- **Tradier issues**: Check `.env` has valid API token and account ID
- **IBKR issues**: Ensure IB Gateway is running and logged in
- **Trade execution issues**: Check account balance and margin requirements
- **Dashboard**: Run `scripts/run_dashboard.bat` to view live trades

---

**Last Updated**: May 31, 2026
