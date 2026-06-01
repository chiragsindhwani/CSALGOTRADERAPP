#!/usr/bin/env python3
"""
Check IBKR Account - View Pending Orders and Positions
"""

import asyncio
import time
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

# Initialize event loop for Windows
try:
    asyncio.get_running_loop()
except RuntimeError:
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass

from iron_condor_0dte.config import Config
from iron_condor_0dte.ibkr_client import IBKRClient
from ib_insync import IB

print("=" * 80)
print("IBKR ACCOUNT STATUS - CHECK ORDERS & POSITIONS")
print("=" * 80)
print()

ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
print(f"Check Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print()

print("[1] Loading Configuration...")
print("-" * 80)
try:
    cfg = Config()
    print(f"[OK] Configuration loaded")
    print(f"    Account: {cfg.IBKR_ACCOUNT_ID}")
    print(f"    Mode: {'Paper' if cfg.IBKR_PAPER_TRADE else 'Live'}")
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

print()
print("[2] Connecting to IB Gateway...")
print("-" * 80)
try:
    ib = IB()
    ib.connect("127.0.0.1", 4002, clientId=4)
    print(f"[OK] Connected to IB Gateway")
    time.sleep(1)
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

print()
print("[3] Retrieving Open Orders...")
print("-" * 80)
try:
    open_orders = ib.openOrders()
    if open_orders:
        print(f"[OK] Found {len(open_orders)} open order(s):")
        print()
        for i, order in enumerate(open_orders, 1):
            print(f"Order #{i}:")
            print(f"  Order ID: {order.orderId}")
            print(f"  Status: {order.orderStatus.status if order.orderStatus else 'Unknown'}")
            if hasattr(order, 'contract'):
                print(f"  Symbol: {order.contract.symbol if order.contract else 'Unknown'}")
            if hasattr(order, 'action'):
                print(f"  Action: {order.action}")
            if hasattr(order, 'totalQuantity'):
                print(f"  Quantity: {order.totalQuantity}")
            print()
    else:
        print(f"[INFO] No open orders found")
except Exception as e:
    print(f"[WARN] Could not retrieve open orders: {e}")

print()
print("[4] Retrieving Account Positions...")
print("-" * 80)
try:
    positions = ib.positions()
    if positions:
        print(f"[OK] Found {len(positions)} position(s):")
        print()
        for i, position in enumerate(positions, 1):
            print(f"Position #{i}:")
            print(f"  Symbol: {position.contract.symbol if position.contract else 'Unknown'}")
            print(f"  Quantity: {position.position}")
            print(f"  Avg Cost: {position.avgCost}")
            print()
    else:
        print(f"[INFO] No open positions")
except Exception as e:
    print(f"[WARN] Could not retrieve positions: {e}")

print()
print("[5] Account Summary...")
print("-" * 80)
try:
    account_values = ib.accountSummary()
    if account_values:
        print(f"[OK] Account information:")
        print()

        # Filter for key values
        key_fields = ['NetLiquidation', 'BuyingPower', 'AvailableFunds', 'TotalCashValue']
        for field in key_fields:
            for av in account_values:
                if av.tag == field:
                    print(f"  {field}: {av.value} {av.currency}")
                    break
    else:
        print(f"[INFO] Account summary not available")
except Exception as e:
    print(f"[WARN] Could not retrieve account summary: {e}")

print()
print("[6] Disconnecting...")
print("-" * 80)
try:
    ib.disconnect()
    print(f"[OK] Disconnected")
except Exception as e:
    print(f"[WARN] {e}")

print()
print("=" * 80)
print("ACCOUNT CHECK COMPLETE")
print("=" * 80)
print()
print("Summary:")
print("  • If MNQ order shows in 'Open Orders': It's pending execution")
print("  • Pending orders execute when market opens (Sun 23:30 ET)")
print("  • If no orders show: Orders may have been cancelled or expired")
print()
print("For trades placed during market hours (9:30 AM - 4:00 PM ET),")
print("orders will execute immediately at market price.")
print()
