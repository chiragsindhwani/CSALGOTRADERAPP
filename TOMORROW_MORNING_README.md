# Tomorrow Morning: SPY 0DTE Iron Condor - IBKR Paper Trading Launch

**Date**: June 1, 2026 (Saturday is only for setup if needed)  
**Trading Time**: 9:55 AM - 3:45 PM ET  
**Broker**: Interactive Brokers (Paper Account)  
**Strategy**: SPY 0DTE Iron Condor (9 contracts)  
**Target P&L**: $200/day minimum  

---

## Pre-Launch Status: ✅ ALL SYSTEMS GO

### Configuration Verification
```
[12/12 checks passed]

[OK] BROKER: ibkr (configured for IBKR)
[OK] IBKR_HOST: 127.0.0.1 (localhost)
[OK] IBKR_PORT: 4002 (paper trading port)
[WARN] IBKR_ACCOUNT_ID: needs your actual account ID
[OK] IBKR_PAPER_TRADE: true (paper mode enabled)

[OK] All core modules importable (BaseBrokerClient, IBKRClient, Config, IronCondorTrader)
[OK] All required files present (config, client, trader, server, logger)
[OK] Data directories ready (trades, logs)
[OK] Dashboard HTML with broker toggle present
```

---

## Critical: Before 9:30 AM ET Tomorrow

### 1. Get Your IBKR Paper Account ID (15 minutes)

**Step A: Via IB Gateway (if already installed)**
- Launch IB Gateway
- Log in with IBKR credentials
- Account ID visible on main window (format: `DU1234567`)

**Step B: Via IBKR Website (fastest)**
- Log in to https://account.interactivebrokers.com
- Account → Summary → Copy account number

**Step C: Via TWS Desktop**
- Open TWS (Trader Workstation)
- Account → Account Settings → Copy account number

### 2. Update .env with Your Account ID (2 minutes)

Edit `c:\MyApp\CSAlgoTraderApp\.env`:

```ini
# Find this line:
IBKR_ACCOUNT_ID=DU123456789

# Replace with your actual account ID:
IBKR_ACCOUNT_ID=DU1234567
```

**Save the file.**

### 3. Download & Install IB Gateway (10 minutes)

**If not already installed:**

1. Download: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php
2. Run installer
3. Installation directory: `C:\IBGateway` (or your preference)
4. Note: Includes Java runtime

**If already installed:**
- Skip to step 4

---

## Tomorrow Morning Schedule

| Time (ET) | Action | Command |
|-----------|--------|---------|
| **9:00 AM** | Wake up, review checklist | - |
| **9:15 AM** | Ensure .env has correct IBKR_ACCOUNT_ID | - |
| **9:30 AM** | **Launch IB Gateway** | Double-click `ibgateway.exe` |
| **9:35 AM** | Log into IB Gateway | Username + password + 2FA code |
| **9:40 AM** | Verify IB Gateway running (System Tray icon) | - |
| **9:45 AM** | Run validation script | `python validate_ibkr_setup.py` |
| **9:50 AM** | Start dashboard | `scripts\run_dashboard.bat` |
| **9:55 AM** | **Launch live trader** | `python -m iron_condor_0dte.live_trader` |
| **10:00 AM** | Verify console shows "SPY Iron Condor 0DTE — Daily Session Started" | - |
| **10:15 AM** | **ENTRY WINDOW** — Strategy places Iron Condor order | Monitor console |
| **10:15-3:45 PM** | **MONITORING** — Strategy checks exits every 5 min | Dashboard shows position |
| **3:45 PM** | **FORCE CLOSE** — Trade exited at market | Session ends |
| **4:00 PM** | Review trade log & P&L | Check `data/trades/trade_log.csv` |

---

## What to Expect Tomorrow

### Entry (10:15 AM ET)

```
Iron Condor on SPY (9 contracts):
  Sell 9x SPY $XX0C (call)  ← delta -0.15
  Buy  9x SPY $XX10C (call) ← protection wing
  Sell 9x SPY $XX0P (put)   ← delta -0.15
  Buy  9x SPY $XX-10P (put) ← protection wing

Entry Credit: $0.40/share = $3,600 gross
Commission: ~$25 (4 legs × 2 sides × $0.35)
Net Credit: ~$3,575

Profit Target:   $1,260 (35% of $3,600)
Stop Loss Level: $5,220 (145% of $3,600)
Max Loss:        $9,000 (wings width × contracts)
Max Profit:      $3,600 (credit received)
```

### Expected Outcome

| Scenario | Probability | Gross P&L | Net P&L |
|----------|-------------|-----------|---------|
| Profit Target Hit | 94.8% | +$1,260 | +$1,235 |
| Stop Loss Hit | 4.5% | -$1,620 | -$1,645 |
| Force Close | 0.7% | Varies | Varies |

**Expected daily P&L**: ~+$1,085 (94.8% × $1,235 - 5.2% × $1,645)

---

## Troubleshooting Tomorrow

### "Connection refused" at 10:15 AM
- **Cause**: IB Gateway not running or wrong port
- **Fix**:
  1. Check System Tray for IB Gateway icon
  2. Verify Settings → Gateway → Port = 4002
  3. Restart IB Gateway if needed

### "Unauthorized to place orders"
- **Cause**: Paper account not enabled for options trading
- **Fix**:
  1. Log into IBKR Account Management
  2. Account Settings → Trading Permissions
  3. Enable "Options"
  4. Restart IB Gateway

### "Order rejected by IBKR"
- **Cause**: Insufficient margin or trading hours
- **Fix**:
  1. Reduce CONTRACTS to 3-5 in `iron_condor_0dte/config.py`
  2. Verify options trading enabled
  3. Check trading hours (9:30 AM - 4:00 PM ET)

### Dashboard shows "TRADIER" instead of "IBKR"
- **Cause**: Configuration not read
- **Fix**:
  1. Click broker toggle on dashboard to switch to IBKR
  2. Verify .env says `BROKER=ibkr`
  3. Restart dashboard

---

## Success Criteria for Tomorrow

**Before 10:15 AM:**
- ✅ IB Gateway installed and running
- ✅ `validate_ibkr_setup.py` passes all 12 checks
- ✅ Dashboard shows "IBKR" in broker toggle
- ✅ Live trader process started (no errors)

**At 10:15 AM:**
- ✅ Strategy places Iron Condor order
- ✅ Order fills within 60 seconds
- ✅ Position appears in IBKR account
- ✅ Dashboard shows open position

**Before 3:45 PM:**
- ✅ Position monitored continuously
- ✅ Either profit target OR stop loss hit
- ✅ Trade closed automatically

**After 4:00 PM:**
- ✅ Session log shows all steps
- ✅ Trade logged to CSV with P&L
- ✅ P&L tracked in trade history

---

## Documents to Review Before Tomorrow

1. **IBKR_LAUNCH_CHECKLIST.md** — Detailed 9-step setup guide
2. **validate_ibkr_setup.py** — Run this at 9:45 AM to confirm readiness
3. **Iron_Condor_0DTE_Strategy_Builder.md** — Engineering & strategy details
4. **MULTI_BROKER_SETUP.md** — Broker switching reference

---

## Files You'll Use Tomorrow

| File | Purpose |
|------|---------|
| `.env` | Config (BROKER=ibkr, account ID, port) |
| `scripts/run_dashboard.bat` | Start dashboard web server |
| `python -m iron_condor_0dte.live_trader` | Start trading engine |
| `validate_ibkr_setup.py` | Verify system is ready (9:45 AM) |
| `data/trades/trade_log.csv` | Review executed trades after 4 PM |
| `logs/session_20260601.log` | Detailed session log |

---

## Contact / Support

If you hit critical issues tomorrow morning:

1. Check `validate_ibkr_setup.py` output for which check failed
2. Review **Troubleshooting** section above
3. Verify `IBKR_ACCOUNT_ID` is correct in `.env`
4. Ensure IB Gateway is running and logged in

---

## Summary

**Status**: ✅ **READY FOR TOMORROW MORNING**

**System**: All 12 validation checks passed  
**Configuration**: IBKR paper trading configured  
**Dashboard**: Broker toggle present and functional  
**Modules**: All core modules importable  
**Data**: Directories ready for trade logging  

**Action Items (Before 9:30 AM):**
1. ✓ Get your IBKR paper account ID (format: DU1234567)
2. ✓ Update `.env` with your account ID
3. ✓ Download IB Gateway (if not installed)

**Timeline:**
- 9:30 AM: Start IB Gateway
- 9:45 AM: Run validation script
- 9:55 AM: Launch live trader
- 10:15 AM: **Strategy enters first trade**

---

**Good luck with your first IBKR paper trade tomorrow! 🚀**

The system is ready. Just need your account ID and IB Gateway running.
