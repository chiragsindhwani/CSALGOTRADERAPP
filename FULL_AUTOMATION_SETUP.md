# Full Automation Setup — SPY 0DTE Iron Condor

**Status**: Ready to deploy  
**Target Launch Date**: Monday, June 2, 2026 (or next trading day)  
**Manual Intervention Required**: None (except keeping IB Gateway and laptop running)

---

## What Gets Automated

| Task | Before | After |
|------|--------|-------|
| Run validation script | Manual (9:45 AM) | **Automatic (9:30 AM)** |
| Start dashboard | Manual (9:50 AM) | **Automatic (9:30 AM)** |
| Start live trader | Manual (9:55 AM) | **Automatic (9:30 AM)** |
| Monitor position | Manual (every 5 min) | **Automatic (built into trader)** |
| Check exits | Manual | **Automatic (built into trader)** |
| Log trades | Automatic | **Automatic** |
| Telegram alerts | Automatic | **Automatic** |

**Result**: From 9:30 AM onward, EVERYTHING is automated. You only need to keep IB Gateway running.

---

## Two-Step Setup (5 minutes total)

### Step 1: Run the Setup Script (Administrator)

1. **Open PowerShell as Administrator**
   - Right-click Windows PowerShell
   - Select "Run as administrator"

2. **Navigate to project directory**
   ```powershell
   cd c:\MyApp\CSAlgoTraderApp
   ```

3. **Allow script execution** (one-time only)
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
   - Press `Y` and Enter when prompted

4. **Run the setup script**
   ```powershell
   .\setup_scheduled_task.ps1
   ```

5. **Watch for success message**
   ```
   ═══════════════════════════════════════════════════════════════════════════════
   ✓ SETUP COMPLETE!
   ═══════════════════════════════════════════════════════════════════════════════
   ```

### Step 2: Verify the Scheduled Task

1. **Open Task Scheduler**
   - Press Windows key + R
   - Type: `taskschd.msc`
   - Press Enter

2. **Find your task**
   - In the left panel, click "Task Scheduler Library"
   - Look for: **SPY_Iron_Condor_0DTE_AutoStart**
   - Status should show: **Enabled**

3. **Verify trigger**
   - Right-click the task
   - Select "Properties"
   - Click "Triggers" tab
   - Should show: "At 9:30 AM every Mon, Tue, Wed, Thu, Fri"

**Done! Your automation is now set up.**

---

## How It Works Tomorrow Morning

### 9:30 AM ET (Automatic)
1. **Windows Task Scheduler triggers**
2. **autostart_trader.py launches**
3. **System runs automatically**:
   - ✅ Validates all systems (12 checks)
   - ✅ Checks IB Gateway connectivity
   - ✅ Starts dashboard on port 8888
   - ✅ Starts live trader
   - ✅ Logs everything to `logs/autostart_YYYYMMDD_HHMMSS.log`

### 10:15 AM ET (Automatic)
1. **Strategy enters market**
2. **Places Iron Condor order** (9 contracts)
3. **Monitors position every 5 minutes**

### 10:15 AM - 3:45 PM ET (Automatic)
1. **Strategy checks for exits**:
   - Profit target (35% decay): **Auto-close**
   - Stop loss (45% rise): **Auto-close**
   - 3:45 PM market close: **Force-close**
2. **Dashboard shows live position**
3. **Logs all actions**

### 4:00 PM ET
1. **Session ends**
2. **Trade logged to CSV**
3. **Telegram alert sent** (if configured)
4. **Next day: Task runs again at 9:30 AM ET**

---

## Your Daily Checklist (Morning Only)

**Before 9:30 AM ET:**
- [ ] Laptop is powered on
- [ ] IB Gateway is running and logged in
- [ ] Network connection is active

**That's it.** Everything else is automatic.

---

## Monitoring & Logs

### Real-Time Monitoring
- **Dashboard**: http://localhost:8888/tradier_dashboard.html
  - Shows live position, entry/exit, P&L
  - Automatically updates every second

### Logs (for troubleshooting)
- **Autostart log**: `logs/autostart_YYYYMMDD_HHMMSS.log`
  - Records when system started
  - Validation results
  - Dashboard startup
  - Trader startup

- **Trader session log**: `logs/session_YYYYMMDD.log`
  - Every market-monitoring action
  - Entry order details
  - Exit triggers
  - Any errors or warnings

- **Trade log**: `data/trades/trade_log.csv`
  - Entry price, exit price, P&L
  - Commission details
  - Notes (e.g., "profit target", "stop loss")

### Example Log Output
```
autostart_20260602_093000.log
├─ 09:30:00  INFO  Autostart sequence initiated
├─ 09:30:01  INFO  Market is open (current time: 10:30 ET)
├─ 09:30:02  INFO  ✓ IB Gateway is running on localhost:4002
├─ 09:30:03  INFO  Validation: Checks Passed 12/12
├─ 09:30:05  INFO  ✓ Dashboard is running on http://localhost:8888
├─ 09:30:10  INFO  ✓ Live trader process started (PID: 12345)
├─ 10:15:30  INFO  [TRADER] === SPY Iron Condor 0DTE — Daily Session Started ===
├─ 10:15:45  INFO  [TRADER] Placing Iron Condor order (9 contracts)
├─ 10:16:00  INFO  [TRADER] Order filled: entry credit $0.40/shr
├─ ...
```

---

## What If Something Goes Wrong?

### IB Gateway Crashes
- **Task will fail at 9:30 AM** (can't connect to IB Gateway)
- **Check log**: `logs/autostart_YYYYMMDD_HHMMSS.log` will show error
- **Fix**: Restart IB Gateway, task will retry next trading day

### No Trade Executed
- **Check log**: `logs/autostart_YYYYMMDD_HHMMSS.log`
- **Likely causes**:
  - IB Gateway not running → Restart IB Gateway
  - Network issue → Check internet connection
  - Account not configured → Verify .env has correct account ID
- **Manual override**: `python autostart_trader.py` (runs immediately)

### Trade Executed But Something Unexpected
- **Check logs**:
  1. `logs/autostart_YYYYMMDD_HHMMSS.log` (startup)
  2. `logs/session_YYYYMMDD.log` (trader actions)
  3. `data/trades/trade_log.csv` (trade details)
- **Contact your broker** if IBKR-related issues

### Task Doesn't Run at 9:30 AM
- **Verify in Task Scheduler**:
  1. Open Task Scheduler
  2. Find `SPY_Iron_Condor_0DTE_AutoStart`
  3. Check "Enabled" checkbox (should be checked)
  4. Right-click > Run to test immediately
- **Check Windows logs**:
  1. Event Viewer (Windows key + R: `eventvwr.msc`)
  2. Windows Logs > System
  3. Look for task execution entries

---

## Advanced Configuration

### Change Startup Time
1. Open Task Scheduler
2. Find `SPY_Iron_Condor_0DTE_AutoStart`
3. Right-click > Properties
4. Click "Triggers" tab
5. Click existing trigger, then "Edit"
6. Change "Begin the task at:" time
7. Click OK

### Add Days to Schedule (e.g., for backtesting)
1. Task Scheduler > Find task > Properties
2. Triggers tab > Edit trigger
3. Check "Repeat task every" and set to weekdays/custom
4. OK

### Disable Automation (Keep IB Gateway)
1. Task Scheduler > Find task
2. Right-click > Disable
3. To re-enable: Right-click > Enable

### Manual Run Anytime
```powershell
# Run immediately (don't wait for 9:30 AM)
python autostart_trader.py
```

---

## Troubleshooting Automation

### Symptom: Task doesn't appear in Task Scheduler
**Solution**:
1. Open Task Scheduler
2. View > Refresh (F5)
3. If still missing, re-run setup script as Administrator

### Symptom: Task runs but fails immediately
**Solution**:
1. Check autostart log: `logs/autostart_*.log`
2. Common issues:
   - Python not in PATH → Specify full path in setup script
   - IB Gateway not running → Start IB Gateway first
   - Wrong working directory → Verify PROJECT_ROOT in setup script

### Symptom: Task runs but trader doesn't start
**Solution**:
1. Check autostart log for errors
2. Manually test: `python -m iron_condor_0dte.live_trader`
3. If manual works but task doesn't:
   - Task may be running as different user (SYSTEM)
   - Edit task > General > "Run whether user is logged in or not"
   - Change to: "Run only when user is logged in"

### Symptom: Dashboard doesn't load
**Solution**:
1. Check http://localhost:8888/tradier_dashboard.html
2. If 404:
   - Check autostart log for dashboard startup errors
   - Try manual: `python scripts/dashboard_server.py`
3. If port 8888 is in use:
   - Find process using port: `netstat -ano | findstr :8888`
   - Kill it or change DASHBOARD_PORT in autostart script

---

## Safety Features Built Into Automation

✅ **Won't run on weekends** (checks weekday automatically)  
✅ **Won't run if market is closed** (checks 4:00 PM ET)  
✅ **Prevents multiple instances** (Task Scheduler: IgnoreNew)  
✅ **Validates everything before starting** (12 pre-flight checks)  
✅ **Checks IB Gateway connectivity** (fails gracefully if not running)  
✅ **Cleans up processes on exit** (stops dashboard when trader ends)  
✅ **Logs everything** (for debugging and audit trail)  
✅ **Network required** (won't run on WiFi-only without connection)  

---

## Files Involved in Automation

| File | Purpose |
|------|---------|
| `autostart_trader.py` | Main automation script (runs at 9:30 AM) |
| `setup_scheduled_task.ps1` | Creates Windows Task Scheduler task |
| `validate_ibkr_setup.py` | Pre-flight validation (called by autostart) |
| `scripts/dashboard_server.py` | Dashboard HTTP server (started by autostart) |
| `iron_condor_0dte/live_trader.py` | Live trading engine (started by autostart) |
| `logs/autostart_*.log` | Startup logs (created each run) |
| `logs/session_*.log` | Trading session logs (created by trader) |
| `data/trades/trade_log.csv` | Trade results (updated by trader) |

---

## Next Steps

1. **Right now**: Run setup script (takes 2 minutes)
   ```powershell
   .\setup_scheduled_task.ps1
   ```

2. **Verify in Task Scheduler** (takes 1 minute)
   - Open Task Scheduler
   - Find `SPY_Iron_Condor_0DTE_AutoStart`
   - Verify "Enabled" and schedule shows 9:30 AM weekdays

3. **Tomorrow morning**:
   - Start IB Gateway before 9:30 AM ET
   - Keep laptop and IB Gateway running
   - Everything else is automatic

---

## Summary

| Before Automation | After Automation |
|-------------------|------------------|
| Manual: 9:45 AM validation | Automatic: 9:30 AM |
| Manual: 9:50 AM dashboard | Automatic: 9:30 AM |
| Manual: 9:55 AM trader | Automatic: 9:30 AM |
| Manual: Monitor all day | Automatic: Built-in monitoring |
| Manual: Record trades | Automatic: CSV logging |
| **Total manual time: 30+ minutes/day** | **Total manual time: 0 minutes/day** |

**Your new daily workflow: Keep IB Gateway running. That's it.**

---

**Ready to automate? Run the setup script now!** 🚀

```powershell
cd c:\MyApp\CSAlgoTraderApp
.\setup_scheduled_task.ps1
```

---

*Complete automation documentation | June 1, 2026*
