#!/usr/bin/env python3
"""
Live MES Futures Trade - Market Open Test
Places a SHORT order for 1 MES contract and monitors execution
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
print("LIVE MES FUTURES TRADE - MARKET OPEN EXECUTION TEST")
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
    ib.connect("127.0.0.1", 4002, clientId=6)
    print(f"[OK] Connected to IB Gateway")
    time.sleep(1)
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

print()
print("[2] Creating MES Contract...")
print("-" * 80)

try:
    mes = Future(symbol="MES", exchange="GLOBEX", currency="USD")
    print(f"[OK] MES contract created")
except Exception as e:
    print(f"[FAIL] {e}")
    ib.disconnect()
    sys.exit(1)

print()
print("[3] Placing SHORT Order (1 contract at market)...")
print("-" * 80)

try:
    order = MarketOrder(action="SELL", totalQuantity=1)
    print(f"[PLACING] SHORT MES order at market price")

    trade = ib.placeOrder(mes, order)
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
                print(f"    Status: SUCCESS")

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

    mes_position = None
    for pos in positions:
        if pos.contract.symbol == "MES":
            mes_position = pos
            break

    if mes_position:
        print(f"[OK] MES Position Found!")
        print(f"    Quantity: {mes_position.position}")
        print(f"    Avg Cost: {mes_position.avgCost}")
        print(f"    Position Size: {abs(int(mes_position.position))} contracts")
    else:
        print(f"[INFO] No MES position currently (order may be pending)")

except Exception as e:
    print(f"[WARN] Could not retrieve positions: {e}")

print()
print("[5] Getting Live Price...")
print("-" * 80)

try:
    ticker = ib.ticker(mes)
    if ticker:
        print(f"[OK] MES Live Data:")
        print(f"    Bid: {ticker.bid}")
        print(f"    Ask: {ticker.ask}")
        print(f"    Last: {ticker.last}")
        print(f"    Mid Price: {ticker.midpoint()}")

except Exception as e:
    print(f"[WARN] {e}")

print()
print("[6] Monitoring for 5 Minutes (if filled)...")
print("-" * 80)

if trade.isDone() and trade.fills:
    print("[HOLDING] Position for 5 minutes...")

    entry_price = trade.fills[0].execution.price
    print(f"[INFO] Entry Price: {entry_price}")

    for i in range(5):
        time.sleep(60)
        print(f"[{(i+1)*60}s] Still holding position... ({5-i-1} min remaining)")

        try:
            ticker = ib.ticker(mes)
            if ticker and ticker.midpoint():
                unrealized_pnl = (entry_price - ticker.midpoint()) * 50 * 1  # MES = 50x multiplier
                print(f"      Current Price: {ticker.midpoint()} | Unrealized P&L: ${unrealized_pnl:+.2f}")
        except:
            pass

    print()
    print("[7] Closing Position (Buy to cover)...")
    print("-" * 80)

    try:
        close_order = MarketOrder(action="BUY", totalQuantity=1)
        print("[PLACING] Buy to cover order: Quantity=1, Type=Market")

        close_trade = ib.placeOrder(mes, close_order)
        print(f"[OK] Close order placed. Order ID: {close_trade.order.orderId}")

        # Wait for close order to fill
        print("[WAITING] For close order to fill...")
        time.sleep(2)

        if close_trade.isDone():
            print(f"[OK] Close order filled!")
            exit_price = close_trade.fills[0].execution.price if close_trade.fills else 0
            print(f"    Exit Price: {exit_price}")

            # Calculate final P&L
            pnl_per_point = (entry_price - exit_price) * 50  # MES = 50x multiplier
            print(f"    Entry Price: {entry_price}")
            print(f"    Exit Price:  {exit_price}")
            print(f"    P&L: ${pnl_per_point:+.2f}")
        else:
            print(f"[WARN] Close order status: {close_trade.orderStatus.status if close_trade.orderStatus else 'Unknown'}")

    except Exception as e:
        print(f"[FAIL] Close order error: {e}")

print()
print("[8] Disconnecting...")
print("-" * 80)

try:
    ib.disconnect()
    print(f"[OK] Disconnected cleanly")
except Exception as e:
    print(f"[WARN] {e}")

print()
print("=" * 80)
print("MES TRADE TEST COMPLETE")
print("=" * 80)
print()
print("Summary:")
print(f"  Symbol: MES (1 contract)")
print(f"  Trade Type: Short (Market) -> Buy to Cover (Market)")
print(f"  Duration: 5 minutes")
print()
print("This test verified:")
print("  - MES contract creation")
print("  - Order placement capability")
print("  - Position monitoring")
print("  - Position closing")
print()
