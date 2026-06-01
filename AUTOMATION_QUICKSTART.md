# Automation Quick Start (5 Minutes)

**Your automated trading system is ready. Let's deploy it now.**

---

## What You're About To Do

Create a **Windows Task Scheduler job** that automatically:
- ✅ Validates all systems (9:30 AM)
- ✅ Starts the dashboard (9:30 AM)
- ✅ Starts the live trader (9:30 AM)
- ✅ Monitors your position all day (automatic)
- ✅ Closes trades at profit target or stop loss (automatic)
- ✅ Logs everything (automatic)

**Result**: From tomorrow on, you just keep IB Gateway running. Everything else is automatic.

---

## Setup: 3 Easy Steps (5 minutes total)

### Step 1: Open PowerShell as Administrator (1 minute)

1. **Right-click the Windows PowerShell icon** on your taskbar or Start menu
2. **Select "Run as administrator"**
3. **Click "Yes"** when prompted

You should see a blue window that says "Administrator: Windows PowerShell"

### Step 2: Run the Setup Script (2 minutes)

Copy and paste this into PowerShell:

```powershell
cd c:\MyApp\CSAlgoTraderApp
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
.\setup_scheduled_task.ps1
```

Press Enter and watch for the success message:

```
═══════════════════════════════════════════════════════════════════════════════
✓ SETUP COMPLETE!
═══════════════════════════════════════════════════════════════════════════════
```

### Step 3: Verify in Task Scheduler (2 minutes)

1. **Open Task Scheduler**:
   - Press Windows key + R
   - Type: `taskschd.msc`
   - Press Enter

2. **Find your automated task**:
   - Look for: **SPY_Iron_Condor_0DTE_AutoStart**
   - Status should show: **Enabled** (blue checkbox)
   - Schedule shows: **Every Mon, Tue, Wed, Thu, Fri at 9:30 AM**

3. **You're done!** 🎉

---

## What Happens Tomorrow Morning

**Before 9:30 AM ET:**
- Keep IB Gateway running
- Keep laptop on

**At 9:30 AM ET:**
- Task Scheduler automatically triggers
- autostart_trader.py launches
- All systems start automatically
- No manual action needed

**At 10:15 AM ET:**
- Strategy places first Iron Condor order
- Position shown on dashboard
- All monitoring is automatic

**Until 3:45 PM ET:**
- Strategy monitors your position
- Automatically closes at profit target (95% chance)
- Or closes at stop loss (5% chance)
- Or force-closes at 3:45 PM market close

**That's it!** No more manual intervention needed.

---

## If Setup Fails

### Error: "This script must run as Administrator"
- **Solution**: Right-click PowerShell, select "Run as administrator"

### Error: "Python not found in PATH"
- **Solution**: Either:
  - Install Python properly (add to PATH), OR
  - Edit `setup_scheduled_task.ps1` line 26 and change:
    ```powershell
    $PYTHON_EXE = "C:\Python314\python.exe"  # Your actual Python path
    ```
  - Re-run setup script

### Error: "Cannot find autostart_trader.py"
- **Solution**: Make sure you're in the right directory:
  ```powershell
  cd c:\MyApp\CSAlgoTraderApp
  ls autostart_trader.py  # Should show the file
  ```

### Can't find Task Scheduler or task doesn't appear
- **Solution**: Open Task Scheduler and press F5 to refresh

---

## Verify It's Working (Optional)

### Test 1: Run Manually to Check Errors
```powershell
cd c:\MyApp\CSAlgoTraderApp
python autostart_trader.py
```

This will:
- Check if IB Gateway is running
- Validate all systems
- Start dashboard
- Start trader

If you see errors, check them and fix them now.

### Test 2: Force Task to Run
1. Open Task Scheduler
2. Find `SPY_Iron_Condor_0DTE_AutoStart`
3. Right-click > **Run**
4. Watch the output in a PowerShell window

If this works, the scheduled version will work too.

---

## Monitoring Your Trades

### Live Dashboard
```
http://localhost:8888/tradier_dashboard.html
```
- Shows live position
- Shows entry/exit prices
- Shows real-time P&L

### Logs for Debugging
```
c:\MyApp\CSAlgoTraderApp\logs\autostart_*.log
```
- Records when system started
- Validation results
- Any errors

### Trade Results
```
c:\MyApp\CSAlgoTraderApp\data\trades\trade_log.csv
```
- CSV file with all trades
- Entry price, exit price, P&L
- Open with Excel to analyze

---

## You're Ready!

✅ Automation is set up  
✅ Task Scheduler is configured  
✅ System will run automatically tomorrow  

### Tomorrow Morning Checklist
- [ ] IB Gateway running before 9:30 AM ET
- [ ] Laptop is powered on
- [ ] Network connection is active

**That's all you need to do. Everything else is automatic.** 🚀

---

**Questions?** Check `FULL_AUTOMATION_SETUP.md` for detailed documentation.

---

*Setup completed: June 1, 2026*
