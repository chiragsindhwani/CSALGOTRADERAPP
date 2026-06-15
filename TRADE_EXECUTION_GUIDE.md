# ALPACA PAPER TRADING - 3-STEP IRON CONDOR EXECUTION GUIDE

**Date:** June 15, 2026 | **Time:** 11:15 AM ET  
**Account:** Alpaca Paper Trading  
**Starting Equity:** $100,087.59

---

## STEP 1: SUBMIT ORDERS TO ALPACA (11:15 AM - 11:20 AM ET)

### Option A: Web Platform (Recommended for Manual Control)

1. **Log in to Alpaca:**
   - Go to https://app.alpaca.markets
   - Sign in with your credentials

2. **Navigate to Options Trading:**
   - Click "Trading" at the top
   - Click "Trade" button
   - Select "Options" tab

3. **Submit First Order (SELL $751 PUT):**
   - Search: "SPY 751 P" (today's expiration)
   - Select the 0DTE $751 PUT
   - Click "BUY" → Select "SELL" from dropdown
   - Quantity: 1
   - Order Type: MARKET
   - Time in Force: DAY
   - Click "Place Order"
   - Status: WAIT FOR FILL (usually 5-30 seconds)

4. **Submit Second Order (BUY $746 PUT):**
   - Search: "SPY 746 P" (today's expiration)
   - Select the 0DTE $746 PUT
   - Click "BUY" → Keep as BUY
   - Quantity: 1
   - Order Type: MARKET
   - Time in Force: DAY
   - Click "Place Order"
   - Status: WAIT FOR FILL

5. **Submit Third Order (SELL $757 CALL):**
   - Search: "SPY 757 C" (today's expiration)
   - Select the 0DTE $757 CALL
   - Click "SELL" → Select "SELL" from dropdown
   - Quantity: 1
   - Order Type: MARKET
   - Time in Force: DAY
   - Click "Place Order"
   - Status: WAIT FOR FILL

6. **Submit Fourth Order (BUY $762 CALL):**
   - Search: "SPY 762 C" (today's expiration)
   - Select the 0DTE $762 CALL
   - Click "BUY" → Keep as BUY
   - Quantity: 1
   - Order Type: MARKET
   - Time in Force: DAY
   - Click "Place Order"
   - Status: WAIT FOR FILL

### Expected Fill Times:
- All 4 legs should fill within 2-3 minutes
- Expected Credit: $0.50-$0.60/share (varies by market)

---

## STEP 2: MONITOR FOR PROFIT TARGET (+$20.30)

Once all 4 legs are filled:

### Option A: Automated Monitoring (Linux/Mac)
```bash
cd C:\MyApp\CSAlgoTraderApp
python trades/monitor_trade.py
```

This script will:
- Check P&L every 5 minutes
- Alert when profit target is hit
- Display current P&L in real-time

### Option B: Manual Monitoring
1. Log into https://app.alpaca.markets
2. Go to "Positions" tab
3. Watch the Iron Condor position
4. Note the "Unrealized P&L" value

**When Cumulative P&L reaches +$20.30:**
- All 4 legs should be closed simultaneously
- Close at market price (fastest execution)

---

## STEP 3: EXECUTE STOP LOSS IF P&L REACHES -$26.10

**If at any point your P&L reaches -$26.10:**

1. Immediately log into https://app.alpaca.markets
2. Go to "Positions" tab
3. Find the SPY Iron Condor position
4. Click "Close" button
5. Confirm the close order

**This is a HARD STOP - exit immediately**

---

## MANDATORY FORCE CLOSE AT 3:45 PM ET

**At 3:45 PM ET (15 minutes before market close):**

1. Log into https://app.alpaca.markets
2. Go to "Positions" tab
3. Close any remaining SPY Iron Condor position
4. Record the final P&L

This prevents overnight weekend gap risk.

---

## TRADE JOURNAL TEMPLATE

Record the following information once the trade is complete:

```
TRADE ENTRY:
- Entry Time: _______________
- SPY Price at Entry: _______________
- Net Credit Received: _______________
- Fill Prices:
  * Sold $751 PUT at: _______________
  * Bought $746 PUT at: _______________
  * Sold $757 CALL at: _______________
  * Bought $762 CALL at: _______________

TRADE EXIT:
- Exit Time: _______________
- Reason: [Profit Target / Stop Loss / Force Close]
- Final P&L: _______________
- Close Prices:
  * Closed $751 PUT at: _______________
  * Closed $746 PUT at: _______________
  * Closed $757 CALL at: _______________
  * Closed $762 CALL at: _______________

NOTES:
_______________________________________________________________
_______________________________________________________________
```

---

## KEY METRICS TO WATCH

| Metric | Target | Alert Level |
|--------|--------|------------|
| **Profit Target** | +$20.30 | EXIT when hit |
| **Stop Loss** | -$26.10 | EXIT immediately if hit |
| **Force Close Time** | 3:45 PM ET | Mandatory exit |
| **Max Profit** | $58.00 | If held to expiration |
| **Max Loss** | $500.00 | (Width of spread) |

---

## TROUBLESHOOTING

### Orders Not Filling?
- Check that today's expiration (0DTE) options are available
- Try limit orders slightly better than mid-market price
- Wait 2-3 minutes before canceling

### Can't Find 0DTE Options?
- Make sure you're searching for today's date (2026-06-15)
- Look for "June 15" in the expiration selector
- Verify SPY is selected

### Position Closed Unexpectedly?
- Check that you didn't accidentally close it
- Note the P&L and record in trade journal
- Consider this a completed trade

### Monitor Script Not Working?
- Verify your Alpaca API keys are correct in `.env`
- Check that positions are showing in your Alpaca account
- Run: `python trades/monitor_trade.py`

---

## SUCCESS CRITERIA

This test trade is successful if:
1. ✓ All 4 orders fill within 5 minutes
2. ✓ Position shows in Alpaca account
3. ✓ P&L is tracked (positive or negative)
4. ✓ Position is closed before 4:00 PM ET
5. ✓ Trade journal is completed

---

## NEXT STEPS (FOR TOMORROW)

Once this test trade is complete:
1. Review the P&L and execution quality
2. Update the trade journal with lessons learned
3. Tomorrow morning at 9:00 AM ET: System will auto-execute trades
4. Monitor using the dashboard: http://localhost:8888/tradier_dashboard.html

---

**Good luck with your 3-step trade!**  
Start time: 11:15 AM ET | Force close: 3:45 PM ET
