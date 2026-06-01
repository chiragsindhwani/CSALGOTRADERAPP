#!/usr/bin/env python3
"""
Live MNQ Futures Trade - Market Open Test
Places a SHORT order for 1 MNQ contract and monitors execution
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

from ib_insync import IB, Future, MarketOrder

print("=" * 80)
print("LIVE MNQ FUTURES TRADE - MARKET OPEN EXECUTION TEST")
print("=" * 80)
print()

ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
print(f"Trade Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Day of Week: {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]}")
print()

print("[1] Connecting to IB Gateway...")
print("-" * 80)

try:
    ib = IB()
    ib.connect("127.0.0.1", 4002, clientId=5)
    print(f"[OK] Connected to IB Gateway")
    time.sleep(1)
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

print()
print("[2] Creating MNQ Contract...")
print("-" * 80)

try:
    mnq = Future(symbol="MNQ", exchange="GLOBEX", currency="USD")
    print(f"[OK] MNQ contract created")
except Exception as e:
    print(f"[FAIL] {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[3] Placing SHORT Order (1 contract at market)...")
print("-" * 80)

try:
    order = MarketOrder(action="SELL", totalQuantity=1)
    print(f"[PLACING] SHORT MNQ order at market price")

    trade = ib.placeOrder(mnq, order)
    print(f"[OK] Order placed. Order ID: {trade.order.orderId}")

    # Wait for order to fill
    print("[MONITORING] Waiting for order to fill...")

    for i in range(30):  # Check for 30 seconds
        time.sleep(1)

        if trade.isDone():
            print(f"[FILLED] Order filled after {i+1} seconds!")

            if trade.fills:
                fill = trade.fills[0]
                print(f"[OK] Execution Details:")
                print(f"    Fill Price: {fill.execution.price}")
                print(f"    Fill Size: {fill.execution.shares}")
                print(f"    Execution Time: {fill.execution.time}")
                print(f"    Status: SUCCESS ✓")

            break
        else:
            status = trade.orderStatus.status if trade.orderStatus else "Unknown"
            print(f"[{i+1:2d}s] Status: {status}")

    if not trade.isDone():
        print(f"[PENDING] Order still pending after 30 seconds")
        print(f"[INFO] Order ID: {trade.order.orderId}")
        print(f"[INFO] Current Status: {trade.orderStatus.status if trade.orderStatus else 'Unknown'}")

except Exception as e:
    print(f"[FAIL] Order placement error: {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[4] Checking Current Position...")
print("-" * 80)

try:
    time.sleep(1)
    positions = ib.positions()

    mnq_position = None
    for pos in positions:
        if pos.contract.symbol == "MNQ":
            mnq_position = pos
            break

    if mnq_position:
        print(f"[OK] MNQ Position Found!")
        print(f"    Quantity: {mnq_position.position}")
        print(f"    Avg Cost: {mnq_position.avgCost}")
        print(f"    Position Size: {abs(int(mnq_position.position))} contracts")
    else:
        print(f"[INFO] No MNQ position currently (order may be pending)")

except Exception as e:
    print(f"[WARN] Could not retrieve positions: {e}")

print()
print("[5] Getting Live Price...")
print("-" * 80)

try:
    ticker = ib.ticker(mnq)
    if ticker:
        print(f"[OK] MNQ Live Data:")
        print(f"    Bid: {ticker.bid}")
        print(f"    Ask: {ticker.ask}")
        print(f"    Last: {ticker.last}")
        print(f"    Mid Price: {ticker.midpoint()}")

except Exception as e:
    print(f"[WARN] {e}")

print()
print("[6] Disconnecting...")
print("-" * 80)

try:
    ib.disconnect()
    print(f"[OK] Disconnected cleanly")
except Exception as e:
    print(f"[WARN] {e}")

print()
print("=" * 80)
print("LIVE TRADE TEST COMPLETE")
print("=" * 80)
print()

if trade.isDone() and trade.fills:
    print("✅ TRADE EXECUTED SUCCESSFULLY")
    print()
    print(f"Order filled in live market!")
    print(f"This confirms your system can execute trades when market is open.")
    print()
else:
    print("⏳ TRADE PENDING")
    print()
    print(f"Order is pending in the system.")
    print(f"Check your IBKR account to see current order status.")
    print()

print("════════════════════════════════════════════════════════════════════")
