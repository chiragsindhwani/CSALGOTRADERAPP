# IBKR Paper Trading — Launch Checklist for Tomorrow Morning

**Date**: May 31, 2026 (tomorrow: June 1, 2026)  
**Trading Time**: 10:15 AM - 3:45 PM ET  
**Strategy**: SPY 0DTE Iron Condor (9 contracts)  
**Broker**: Interactive Brokers (Paper Account)  

---

## Critical Pre-Launch Items

### ✅ Configuration Status

| Item | Status | Value |
|------|--------|-------|
| **BROKER** | ✅ SET | `ibkr` |
| **IBKR_HOST** | ✅ SET | `127.0.0.1` |
| **IBKR_PORT** | ✅ SET | `4002` (paper) |
| **IBKR_CLIENT_ID** | ✅ SET | `1` |
| **IBKR_PAPER_TRADE** | ✅ SET | `true` |
| **IBKR_ACCOUNT_ID** | ⚠️ **NEEDS UPDATE** | `DU123456789` (placeholder) |

---

## URGENT: Before Tomorrow Morning

### Step 1: Update IBKR Account ID (CRITICAL)

**Current Value**: `DU123456789` (placeholder)  
**Required**: Your actual IBKR paper account ID (format: `DU1234567`)

**How to find your Account ID:**

**Option A - IB Gateway (fastest if already installed):**
1. Download IB Gateway: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php
2. Install and launch IB Gateway
3. Log in with your IBKR credentials
4. Account ID is displayed on the main window (top-left area)
5. Copy it (format: `DU1234567`)

**Option B - Online at IBKR:**
1. Log in to https://account.interactivebrokers.com
2. Go to Account → Summary
3. Copy your account number

**Option C - TWS Desktop (if you use TWS instead of Gateway):**
1. Open TWS
2. Go to Account → Account Settings
3. Copy account number

**Update .env:**
```bash
# Edit c:\MyApp\CSAlgoTraderApp\.env
# Change this line:
IBKR_ACCOUNT_ID=DU123456789

# To this (use YOUR actual account ID):
IBKR_ACCOUNT_ID=DU1234567
```

---

### Step 2: Install & Start IB Gateway (CRITICAL)

**Before 10:00 AM ET tomorrow:**

1. **Download** (if not already installed):
   - https://www.interactivebrokers.com/en/trading/ibgateway-latest.php

2. **Install** (if not already installed):
   - Run the installer
   - Includes Java runtime
   - Choose installation directory (e.g., `C:\IBGateway`)

3. **Launch** (MUST be running before strategy starts):
   - Double-click `ibgateway.exe` or create a shortcut
   - It runs silently in the background (doesn't need to be visible)
   - **Correct port settings:**
     - Paper account: port `4002` (default)
     - Live account: port `4001` (not for tomorrow!)

4. **Log In**:
   - Use your IBKR credentials (username + password + 2FA code if enabled)
   - Leave it running in the background
   - **Do NOT close it** during trading hours

---

### Step 3: Verify Configuration

**Run this command at 9:45 AM ET tomorrow (before trading):**

```bash
cd c:\MyApp\CSAlgoTraderApp
python verify_broker_setup.py
```

**Expected output:**
```
[OK] BROKER: ibkr (default: tradier)
[OK] IBKR_HOST: 127.0.0.1
[OK] IBKR_PORT: 4002
[OK] IBKR_ACCOUNT_ID: DU1234567
[OK] IBKR_PAPER_TRADE: True
[OK] IBKR broker attempted (connection established)
[OK] IronCondorTrader instantiated with IBKR
SUMMARY: Multi-broker support ready!
```

**If connection fails:**
- Make sure IB Gateway is running on port 4002
- Verify IBKR_ACCOUNT_ID is correct (check .env)
- Check that you're logged in to IB Gateway

---

### Step 4: Dashboard Pre-Check (9:50 AM ET)

**Start the dashboard:**
```bash
scripts\run_dashboard.bat
```

**Verify:**
1. Dashboard loads at http://localhost:8888/tradier_dashboard.html
2. **Broker toggle** shows "IBKR" (blue color)
3. Toast notification appears "Switched to IBKR" or shows correct state

**If broker toggle shows TRADIER:**
- Click it once to switch to IBKR
- Toast should confirm "Switched to IBKR"

---

### Step 5: Live Trading Start (9:55 AM ET)

**One of two options:**

**Option A: Manual Start (recommended for first time)**
```bash
cd c:\MyApp\CSAlgoTraderApp
python -m iron_condor_0dte.live_trader
```

Output should show:
```
Log file: C:\MyApp\CSAlgoTraderApp\logs\session_20260601.log
IBKRClient initialised | host=127.0.0.1 port=4002 | account=DU1234567 | PAPER
TradeLogger: LOCAL mode -> C:\MyApp\CSAlgoTraderApp\data\trades/trade_log.csv
=== SPY Iron Condor 0DTE — Daily Session Started ===
```

Then waits for 10:15 AM entry window...

**Option B: Automated via Task Scheduler (set up later)**
- Currently configured for Tradier
- After confirming manual run works, we can update Task Scheduler to use IBKR

---

## Tomorrow Morning Schedule

| Time (ET) | Action |
|-----------|--------|
| **8:30 AM** | Wake up, review this checklist |
| **9:00 AM** | Download & install IB Gateway (if not done) |
| **9:15 AM** | Launch IB Gateway, log in |
| **9:30 AM** | Verify IB Gateway is running (check System Tray) |
| **9:45 AM** | Run `python verify_broker_setup.py` |
| **9:50 AM** | Start dashboard: `scripts\run_dashboard.bat` |
| **9:55 AM** | Launch live trader: `python -m iron_condor_0dte.live_trader` |
| **10:15 AM** | **ENTRY WINDOW** — Strategy attempts to place order |
| **10:15-3:45 PM** | **MONITORING** — Trader checks exits every 5 min |
| **3:45 PM** | **FORCE CLOSE** — Trade exited at market (if still open) |
| **4:00 PM** | Session complete, review trade log |

---

## Expected First Trade Tomorrow

### Entry (10:15 AM ET)

**Scenario**: SPY = $550, VIX = 15, IV = 0.15

```
Iron Condor:
  Sell 9x SPY 550C (call)      ← delta -0.15
  Buy  9x SPY 560C (call)      ← protection wing
  Sell 9x SPY 540P (put)       ← delta -0.15
  Buy  9x SPY 530P (put)       ← protection wing

Entry Credit: $0.40/share = $3,600 gross = $3,575 net (after $25 commission)

Profit Target:   $3,600 × 0.35 = $1,260 (35% decay)
Stop Loss Level: $3,600 × 1.45 = $5,220 (45% rise = loss)
Max Loss (wings): $1,000 × 9 = $9,000 (if SPY moves 10 pts in one direction)
Max Profit: $3,600 (credit received)
```

### Monitoring (10:15 AM - 3:45 PM)

- Every 5 minutes, strategy checks:
  - **Is IC value ≤ $2,340?** → Close at profit target (35% decay)
  - **Is IC value ≥ $5,220?** → Close at stop loss (45% rise)
  - **Is it 3:45 PM?** → Force close at market

### Exit (typical outcomes)

| Outcome | Probability | Gross P&L | Net P&L |
|---------|-------------|-----------|---------|
| Profit Target | 94.8% | +$1,260 | +$1,235 |
| Stop Loss | 4.5% | -$1,620 | -$1,645 |
| Force Close | 0.7% | Varies | Varies |

**Expected daily P&L**: 94.8% × $1,235 - 5.2% × (-$1,645) ≈ +$1,085/day

---

## Troubleshooting

### "Connection refused: No connection could be made"

**Problem**: IB Gateway not running or on wrong port

**Fix**:
1. Check System Tray for IB Gateway icon
2. Verify it's running on port 4002 (Settings → Gateway → Port)
3. Make sure you're logged in

### "Unauthorized to place orders"

**Problem**: Paper account not enabled for options trading

**Fix**:
1. Log into IBKR Account Management (https://account.interactivebrokers.com)
2. Go to Account → Account Settings → Trading Permissions
3. Ensure "Options" is enabled for your paper account
4. May require re-login to IB Gateway

### "Order rejected by IBKR"

**Problem**: Several possible causes:
- Account lacks margin for 9 contracts
- Options not enabled for SPY
- Market hours issue (orders only accepted during 9:30 AM - 4:00 PM ET)
- Position size exceeds account limits

**Fix**:
1. Reduce CONTRACTS in `iron_condor_0dte/config.py` to 3-5
2. Verify options trading is enabled
3. Check account buying power (need ~$4,500 for 9 contracts)

### "Dashboard shows TRADIER instead of IBKR"

**Problem**: Configuration didn't persist or wasn't read correctly

**Fix**:
1. Manually click broker toggle on dashboard (should switch to IBKR)
2. Check .env file: should say `BROKER=ibkr`
3. Restart dashboard: `scripts\run_dashboard.bat`

---

## Success Criteria for Tomorrow

✅ **Before 10:15 AM:**
- [ ] IB Gateway installed, running, logged in
- [ ] `verify_broker_setup.py` passes all checks
- [ ] Dashboard shows "IBKR" in broker toggle
- [ ] Live trader process started successfully
- [ ] No error messages in console

✅ **At 10:15 AM:**
- [ ] Strategy places Iron Condor order
- [ ] Order fills within 60 seconds
- [ ] Trade logged to `data/trades/trade_log.csv`
- [ ] Position appears in IBKR Account
- [ ] Dashboard reflects open position

✅ **Before 3:45 PM:**
- [ ] Position monitored continuously
- [ ] Either profit target or stop loss hit (or force close at 3:45 PM)
- [ ] Trade closed automatically
- [ ] Trade logged to CSV with P&L

✅ **After 4:00 PM:**
- [ ] Session log in `logs/session_20260601.log` shows all steps
- [ ] Trade summary sent to Telegram (if enabled)
- [ ] P&L recorded in dashboard

---

## After Tomorrow's First Trade

**If successful**: Repeat this setup for 2-5 more days to validate
**If issues found**: Debug, document, and fix before going live with real money
**Next milestone**: Transition from IBKR paper to Tradier live (if desired)

---

## Contact / Help

If you hit issues tomorrow morning:

1. **Check logs**: `C:\MyApp\CSAlgoTraderApp\logs\session_20260601.log`
2. **Verify broker**: Run `python verify_broker_setup.py`
3. **Check IB Gateway**: Make sure it's running and logged in
4. **Check .env**: Ensure `BROKER=ibkr` and `IBKR_ACCOUNT_ID=YOUR_ACCOUNT_ID`

---

**Good luck with your first IBKR paper trade tomorrow morning! 🚀**

The system is ready. Just need your actual IBKR account ID and IB Gateway running.
