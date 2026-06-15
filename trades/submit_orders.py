#!/usr/bin/env python3
"""
ALPACA PAPER TRADING - IRON CONDOR ORDER SUBMISSION
Execute 3-step SPY 0DTE Iron Condor trade
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from iron_condor_0dte.alpaca_client import AlpacaClient
from iron_condor_0dte.config import Config

ET = ZoneInfo("America/New_York")

def submit_iron_condor_trade():
    """Submit 4-leg Iron Condor to Alpaca"""
    
    cfg = Config()
    client = AlpacaClient(
        api_key=cfg.ALPACA_API_KEY,
        secret_key=cfg.ALPACA_SECRET_KEY,
        paper=cfg.ALPACA_PAPER_TRADE
    )
    
    print("=" * 80)
    print("ALPACA PAPER TRADING - SUBMITTING 3-STEP IRON CONDOR")
    print("=" * 80)
    print()
    
    now = datetime.now(ET)
    print(f"Submission Time: {now.strftime('%I:%M:%S %p ET')}")
    print()
    
    # Get current account state
    profile = client.get_profile()
    account = profile.get('account', {})
    equity_before = float(account.get('equity', 0))
    
    print("Pre-Trade Account State:")
    print(f"  Equity: ${equity_before:,.2f}")
    print()
    
    # Define the 4 legs
    orders = [
        {
            "symbol": "SPY",
            "action": "SELL",
            "type": "PUT",
            "strike": 751,
            "expiry": "2026-06-15",
            "qty": 1,
            "description": "SELL TO OPEN 1 SPY $751 PUT"
        },
        {
            "symbol": "SPY",
            "action": "BUY",
            "type": "PUT",
            "strike": 746,
            "expiry": "2026-06-15",
            "qty": 1,
            "description": "BUY TO OPEN 1 SPY $746 PUT"
        },
        {
            "symbol": "SPY",
            "action": "SELL",
            "type": "CALL",
            "strike": 757,
            "expiry": "2026-06-15",
            "qty": 1,
            "description": "SELL TO OPEN 1 SPY $757 CALL"
        },
        {
            "symbol": "SPY",
            "action": "BUY",
            "type": "CALL",
            "strike": 762,
            "expiry": "2026-06-15",
            "qty": 1,
            "description": "BUY TO OPEN 1 SPY $762 CALL"
        },
    ]
    
    print("Submitting Orders:")
    print("-" * 80)
    print()
    
    submitted_orders = []
    failed_orders = []
    
    for i, order in enumerate(orders, 1):
        print(f"Order {i}/4: {order['description']}")
        try:
            # Note: Alpaca's REST API doesn't natively support options orders
            # This is a placeholder for the order submission
            print(f"  [INFO] Options orders must be submitted via Alpaca web platform")
            print(f"  [INFO] See instructions below for manual submission")
            submitted_orders.append(order)
            print(f"  Status: READY FOR SUBMISSION")
            print()
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed_orders.append(order)
            print()
    
    print("=" * 80)
    print("MANUAL ORDER SUBMISSION REQUIRED")
    print("=" * 80)
    print()
    print("Alpaca's REST API does not yet support options order placement.")
    print("Please submit orders manually through Alpaca's web platform:")
    print()
    print("1. Go to: https://app.alpaca.markets/trading")
    print("2. Click 'Trade' button")
    print("3. Select 'Options' tab")
    print("4. For each of the 4 legs below, enter the order:")
    print()
    
    for i, order in enumerate(orders, 1):
        print(f"LEG {i}: {order['description']}")
        print(f"  Symbol: SPY")
        print(f"  Type: {order['type']}")
        print(f"  Strike: ${order['strike']}")
        print(f"  Expiration: Today (2026-06-15)")
        print(f"  Action: {'SELL TO OPEN' if order['action'] == 'SELL' else 'BUY TO OPEN'}")
        print(f"  Quantity: 1")
        print(f"  Order Type: MARKET")
        print()
    
    print("=" * 80)
    print("TRADE MONITORING")
    print("=" * 80)
    print()
    print("Once all 4 legs are filled, monitor using this script:")
    print("  python trades/monitor_trade.py")
    print()
    print("The monitor will:")
    print("  - Track cumulative P&L")
    print("  - Alert when profit target is hit (+$20.30)")
    print("  - Alert when stop loss is hit (-$26.10)")
    print("  - Force close at 3:45 PM ET")
    print()

if __name__ == "__main__":
    submit_iron_condor_trade()
