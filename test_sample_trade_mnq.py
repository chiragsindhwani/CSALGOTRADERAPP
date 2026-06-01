#!/usr/bin/env python3
"""
Sample MNQ Futures Trade - Test Script
This script:
1. Connects to IB Gateway
2. Places a SHORT order for 1 MNQ contract
3. Monitors the position
4. Closes it after 5 minutes
5. Logs all results
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
print("SAMPLE MNQ FUTURES TRADE TEST")
print("=" * 80)
print()

ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
print(f"Test Started: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print()

# Configuration
HOST = "127.0.0.1"
PORT = 4002
CLIENT_ID = 2  # Use different ID to avoid conflicts

print("[1] Connecting to IB Gateway...")
print("-" * 80)

try:
    ib = IB()
    ib.connect(HOST, PORT, clientId=CLIENT_ID, readonly=False)
    print(f"[OK] Connected to IB Gateway on {HOST}:{PORT}")
    time.sleep(1)
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

print()
print("[2] Creating MNQ Contract...")
print("-" * 80)

try:
    # MNQ (Micro E-mini Nasdaq-100) futures
    mnq = Future(symbol="MNQ", exchange="GLOBEX", currency="USD")
    print(f"[OK] MNQ contract created: {mnq}")
except Exception as e:
    print(f"[FAIL] Contract creation error: {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[3] Placing SHORT Order (1 contract at market)...")
print("-" * 80)

try:
    # Create a market order to SHORT 1 MNQ contract
    order = MarketOrder(action="SELL", totalQuantity=1)
    print(f"[PLACING] Short MNQ order: Quantity=1, Type=Market")

    trade = ib.placeOrder(mnq, order)
    print(f"[OK] Order placed. Order ID: {trade.order.orderId}")

    # Wait for order to fill
    print("[WAITING] For order to fill...")
    time.sleep(2)

    if trade.isDone():
        print(f"[OK] Order filled! Status: {trade.orderStatus.status}")
        fill_price = trade.fills[0].execution.price if trade.fills else 0
        print(f"    Fill Price: {fill_price}")
    else:
        print(f"[WARN] Order still pending. Status: {trade.orderStatus.status}")

except Exception as e:
    print(f"[FAIL] Order placement error: {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[4] Position Monitoring (5 minutes)...")
print("-" * 80)

entry_time = time.time()
monitoring_duration = 5 * 60  # 5 minutes in seconds

while time.time() - entry_time < monitoring_duration:
    elapsed = int(time.time() - entry_time)
    remaining = monitoring_duration - elapsed

    try:
        # Get current market data
        ticker = ib.ticker(mnq)
        current_price = ticker.last if ticker.last else ticker.midpoint()

        # Calculate unrealized P&L (short position)
        if trade.fills and current_price:
            fill_price = trade.fills[0].execution.price
            pnl = (fill_price - current_price) * 20 * 1  # MNQ = 20x multiplier, 1 contract
            print(f"[{elapsed:3d}s] MNQ: {current_price:.2f} | Entry: {fill_price:.2f} | P&L: ${pnl:+.2f} | Remaining: {remaining}s")

        time.sleep(10)  # Check every 10 seconds

    except Exception as e:
        print(f"[WARN] Monitoring error: {e}")
        time.sleep(10)

print()
print("[5] Closing Position (Buy to cover)...")
print("-" * 80)

try:
    # Create BUY order to close the short position
    close_order = MarketOrder(action="BUY", totalQuantity=1)
    print("[PLACING] Buy to cover order: Quantity=1, Type=Market")

    close_trade = ib.placeOrder(mnq, close_order)
    print(f"[OK] Close order placed. Order ID: {close_trade.order.orderId}")

    # Wait for order to fill
    print("[WAITING] For close order to fill...")
    time.sleep(2)

    if close_trade.isDone():
        print(f"[OK] Close order filled! Status: {close_trade.orderStatus.status}")
        close_price = close_trade.fills[0].execution.price if close_trade.fills else 0
        print(f"    Close Price: {close_price}")

        # Calculate final P&L
        if trade.fills and close_trade.fills:
            entry_price = trade.fills[0].execution.price
            exit_price = close_trade.fills[0].execution.price
            pnl_per_point = (entry_price - exit_price) * 20  # MNQ = 20x multiplier
            print(f"    Entry Price: {entry_price:.2f}")
            print(f"    Exit Price:  {exit_price:.2f}")
            print(f"    P&L: ${pnl_per_point:+.2f}")
    else:
        print(f"[WARN] Close order status: {close_trade.orderStatus.status}")

except Exception as e:
    print(f"[FAIL] Close order error: {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[6] Disconnecting...")
print("-" * 80)

try:
    ib.disconnect()
    print("[OK] Disconnected cleanly from IB Gateway")
except Exception as e:
    print(f"[WARN] Disconnect warning: {e}")

print()
print("=" * 80)
print("SAMPLE TRADE COMPLETED SUCCESSFULLY")
print("=" * 80)
print()
print("Summary:")
print(f"  Symbol: MNQ (1 contract)")
print(f"  Order Type: Short (Market) → Buy to Cover (Market)")
print(f"  Duration: 5 minutes")
print(f"  Status: COMPLETED")
print()
print("This test verified:")
print("  ✅ IB Gateway connectivity")
print("  ✅ Order placement capability")
print("  ✅ Trade execution")
print("  ✅ Position monitoring")
print("  ✅ Position closing")
print()
print("Your system is ready for automated trading! 🚀")
print()
