# SPY Iron Condor 0DTE - Trading Strategy Rules

## Overview

**Strategy Name:** SPY Iron Condor 0DTE (Zero Days to Expiration)  
**Underlying:** SPY (S&P 500 ETF)  
**Expiration:** Same-day (0DTE) - expires at market close  
**Position Type:** Short Iron Condor (4-leg spread)  
**Profit Mode:** Time decay + volatility crush  
**Account:** IBKR Paper Trading (DUQ566282)

---

## Entry Rules

### Entry Window
- **Time:** 10:15 AM - 10:29 AM ET (15-minute window only)
- **Conditions:** Monday-Friday during market hours
- **Max Contracts:** 1 contract per trade

### Strike Selection

**Call Spread:**
- Short Call: 0.20 delta (75% probability ITM)
- Long Call: Short Call + $5.00 (protective wing)

**Put Spread:**
- Short Put: 0.20 delta (75% probability ITM)  
- Long Put: Short Put - $5.00 (protective wing)

### Entry Order Logic (3 Attempts)

```
Attempt 1:  Place credit limit order at $0.35/share
            Timeout: 3 minutes
            → If filled: PROCEED TO MONITORING
            → If not filled: Go to Attempt 2

Attempt 2:  Place credit limit order at $0.26/share
            Timeout: 2 minutes
            → If filled: PROCEED TO MONITORING
            → If not filled: Go to Attempt 3

Attempt 3:  Place credit limit order at $0.20/share
            Timeout: 3 minutes
            → If filled: PROCEED TO MONITORING
            → If not filled: SKIP TRADE (log as skipped_attempt_0)

Total Entry Window: 8 minutes maximum
```

### Minimum Credit Requirements

- **Entry Threshold:** $0.35 per share minimum
- **Abort Threshold:** If order fills below $0.10/share, exit immediately

---

## Position Monitoring Rules

### Monitoring Period
- **Start:** Immediately after entry fill
- **End:** Either profit target, stop loss, or force close
- **Interval:** Check every 1 minute

### Profit Target (Primary Exit)
- **Rule:** Close position when 35% of entry credit is gained
- **Example:** Entry credit $2.00 → Close at $0.70 profit
- **Typical Time:** 1-3 hours after entry
- **Expected Frequency:** ~75% of trades
- **Exit Method:** Market order (close quickly)

### Stop Loss (Risk Management)
- **Rule:** Close position when 45% of entry credit is lost
- **Example:** Entry credit $2.00 → Stop loss at $0.90 loss
- **Max Loss:** Limits downside to 45% of credit received
- **Expected Frequency:** ~25% of trades
- **Exit Method:** Market order (minimize loss)

### Force Close Rule (Mandatory Exit)
- **Time:** 3:45 PM ET (15 minutes before market close)
- **Action:** Automatically close ANY open position
- **Reason:** Avoid gamma risk and closing bell volatility
- **Exit Method:** Market order (whatever price is available)

---

## Daily Trading Schedule

```
09:05 AM ET   → System auto-starts
09:30 AM ET   → Market opens (ready for trading)

10:15 AM ET   → ENTRY WINDOW OPENS
              • Fetch SPY current price
              • Fetch VIX for volatility
              • Calculate Greeks (Delta, IV, Theta, Vega)
              • Select proper strikes (0.20 delta)
              • Place Attempt 1 credit limit order ($0.35/share)

10:18 AM ET   → If not filled: Place Attempt 2 ($0.26/share)

10:20 AM ET   → If not filled: Place Attempt 3 ($0.20/share)

10:23 AM ET   → Entry window closes
              • If filled: BEGIN POSITION MONITORING
              • If not filled: SKIP TRADE (log reason)

10:24 AM - 3:44 PM → POSITION MONITORING
              • Check profit target every minute
              • Check stop loss every minute
              • Monitor Greeks
              • Auto-close if targets hit

3:45 PM ET    → FORCE CLOSE (if still open)
              • Mandatory exit to avoid closing bell risk
              • Accept any P&L (profit or loss)

4:00 PM ET    → Market closes
              • Session complete
              • Results logged to CSV file
              • Telegram alert sent
```

---

## Risk Management Rules

### Per-Trade Risk

| Metric | Value | Notes |
|--------|-------|-------|
| Max Loss | 45% of credit | Stop loss limit |
| Profit Target | 35% of credit | Primary exit |
| Position Size | 1 contract | Max per trade |
| Margin Required | ~$500 | Per contract (0DTE) |

### Daily Rules

| Rule | Limit | Notes |
|------|-------|-------|
| Max Trades/Day | 3 | PDT rule (5-day rolling) |
| Max Contracts/Day | 3 | (1 contract × 3 trades) |
| Max Daily Loss | 3 × (0.45 × avg credit) | Worst case scenario |

### Account Constraints

- **Starting Capital:** $125,000 (paper trading)
- **Minimum Margin:** ~$500 per contract
- **Available Margin:** Can support 200+ concurrent positions
- **Risk Profile:** Very conservative position sizing

---

## Exit Strategy

### Exit Scenarios (in priority order)

**1. Profit Target Hit (Most Common - 75% of trades)**
- Close position at 35% of entry credit
- Locks in quick gains from theta decay
- Typical duration: 1-3 hours
- Typical profit: $25-75 per contract

**2. Stop Loss Hit (Less Common - 25% of trades)**
- Close position at 45% of entry credit loss
- Prevents runaway losses
- Triggered by SPY moving >1% unexpectedly
- Typical loss: -$20-50 per contract

**3. Force Close at 3:45 PM ET (Mandatory)**
- Close any open position regardless of P&L
- Avoids overnight risk
- Avoids closing bell volatility
- Accept whatever P&L exists

### Exit Order Type
- **Method:** Market order (immediate execution)
- **Reason:** Ensure execution at close-of-day

---

## Position Greeks Monitoring

During the hold, system monitors:

| Greek | Target | Purpose |
|-------|--------|---------|
| **Delta** | Near zero | Neutral directional exposure |
| **Gamma** | Short (negative) | Stable prices preferred |
| **Theta** | Long (positive) | Time decay works for us |
| **Vega** | Short (negative) | Volatility crush helps us |

### Why These Targets Matter

- **Delta ≈ 0:** Position profits whether SPY goes up or down
- **Short Gamma:** Large moves hurt us, small moves help
- **Long Theta:** Every minute that passes helps us
- **Short Vega:** If implied volatility drops, we profit

---

## Market Filters

### Required Conditions for Trading

- **Day of Week:** Monday - Friday only
- **Not Holiday:** Skip US market holidays
- **Market Hours:** 9:30 AM - 4:00 PM ET
- **Early Close Check:** Skip if market closes before 1:00 PM
- **FOMC Days:** Skip FOMC announcement days (2026-06-10 is FOMC)

### Volatility Filters

| Filter | Rule |
|--------|------|
| Min VIX | No minimum (all environments OK) |
| Max VIX | 30.0 (skip if above this) |
| Note | Higher VIX = higher option premiums = better credits |

---

## Pattern Day Trading (PDT) Rules

**Rule:** Maximum 3 day-trade round-trips in any rolling 5-business-day window

- **Each trade = 1 day trade** (entry + exit same day)
- **Rolling window:** Spans any 5 consecutive business days
- **Current usage:** 0/3 (fresh for tomorrow)

**If PDT limit reached:** Skip trades until window rolls over

---

## Success Metrics

### Expected Win Rate
- **Profit Targets Hit:** ~75% (3 out of 4 trades)
- **Stop Loss Hit:** ~25% (1 out of 4 trades)
- **Trades Skipped:** <5% (market data issues)

### Expected Monthly Performance

| Metric | Expected |
|--------|----------|
| Trades/Month | ~20 (4 per week) |
| Winning Trades | ~15 (75%) |
| Losing Trades | ~5 (25%) |
| Avg Win | $50-100 per trade |
| Avg Loss | -$30-50 per trade |
| Net Monthly | Positive (wins exceed losses) |
| Monthly Target | $1,000-3,000 (variable) |

### Risk-Reward Ratio
- **Win Size:** 35% of credit
- **Loss Size:** -45% of credit
- **Ratio:** 35/45 = 0.78:1 (favorable even with 75% win rate)

---

## Example Trade Walkthrough

### Setup
```
Current Conditions:
  SPY Price:     $741.75
  VIX:           17.96
  Time:          10:15 AM ET
```

### Strike Selection
```
Call Spread:
  Short Call:    $745.00 (0.20 delta)
  Long Call:     $750.00 (protection)
  
Put Spread:
  Short Put:     $738.00 (0.20 delta)
  Long Put:      $733.00 (protection)
```

### Entry
```
Attempt 1 (10:15 AM):
  Place credit limit order: $0.35/share
  Expected Credit: $35.00 per contract
  Timeout: 3 minutes
  Result: FILLED at $0.37/share → $37.00 credit
```

### Monitoring
```
10:15 AM: Position opened
  Profit Target: $0.37 × 0.35 = $0.13 profit needed
  Stop Loss: $0.37 × 0.45 = -$0.17 loss limit
  
11:00 AM: Theta decay crushes option value
  Position now worth $0.24 to close
  Close cost: $24.00
  Profit: $37.00 - $24.00 = $13.00 (35% gain!)
```

### Exit
```
11:00 AM:
  Profit target triggered ($0.13 ≥ gained)
  Place market close order
  Close at: $0.24/share
  Result: EXIT with $13.00 profit
  Duration: 45 minutes
  ROI: 35% ($13 gain on $37 credit)
```

---

## Critical Configuration Values for Tomorrow

```
ENTRY_HOUR:           10
ENTRY_MIN:            15          (10:15 AM ET)
FORCE_CLOSE_HOUR:     15
FORCE_CLOSE_MIN:      45          (3:45 PM ET)

TARGET_DELTA:         0.20        (75% probability strikes)
WING_WIDTH:           5.00        ($5.00 wide spreads)

MIN_CREDIT:           0.35        (entry threshold)
MIN_ACTUAL_CREDIT:    0.10        (abort threshold)

PROFIT_TARGET_PCT:    0.35        (35% of credit)
STOP_LOSS_MULT:       0.45        (45% max loss)

CONTRACTS:            9           (max per trade, using 1 for paper trading)
PAPER_TRADE:          true        (IBKR paper account)
```

---

## Summary

This is a **high-probability, time-decay-focused strategy** designed to:

1. ✅ Profit from theta decay (time working for us)
2. ✅ Use wide wings ($5) for lower risk
3. ✅ Enter at optimal volatility (morning of 0DTE day)
4. ✅ Close quickly at profit targets (1-3 hours)
5. ✅ Use stop losses to limit risk (45% max)
6. ✅ Force close to avoid overnight risk (3:45 PM)

**Expected Outcome:** 75% win rate with positive monthly P&L
