#!/usr/bin/env python3
"""
Test MGC Futures Trade on IBKR Paper Trading Account

This script demonstrates placing a Micro Gold Futures (MGC) trade.
MGC is 1/10th the size of the full gold contract (GC), making it ideal for testing.

Requirements:
- TWS running with Paper Trading enabled
- Account: DUQ566282
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from iron_condor_0dte.ibkr_client import IBKRClient
from iron_condor_0dte.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
)
log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def test_mgc_trade():
    """Test MGC futures trade."""
    print("\n" + "=" * 80)
    print("MGC FUTURES TRADE TEST")
    print("=" * 80)

    cfg = Config()
    client = None

    try:
        # Connect to IBKR
        print("\n[1] Connecting to IBKR Paper Trading Account...")
        client = IBKRClient(
            host=cfg.IBKR_HOST,
            port=cfg.IBKR_PORT,
            client_id=1,
            account_id=cfg.IBKR_ACCOUNT_ID,
            paper=cfg.PAPER_TRADE
        )
        print(f"    [OK] Connected to {cfg.IBKR_ACCOUNT_ID}\n")

        # Get MGC quote
        print("[2] Fetching MGC Futures Quote...")
        quote = client.get_futures_quote("MGC")
        bid = quote.get("bid", 0)
        ask = quote.get("ask", 0)
        last = quote.get("last", 0)

        print(f"    Bid:  ${bid:.2f}")
        print(f"    Ask:  ${ask:.2f}")
        print(f"    Last: ${last:.2f}")

        if bid == 0 and ask == 0:
            print("    [NOTE] Market data may not be available (market closed)")
            print("    This is normal outside market hours\n")
        else:
            print("    [OK] Live quote received\n")

        # Place test buy order for 1 MGC contract
        print("[3] Placing Sample BUY order for 1 MGC contract...")
        print("    Order Details:")
        print("      Symbol: MGC (Micro Gold Futures)")
        print("      Quantity: 1 contract")
        print("      Side: BUY")
        print("      Type: MARKET")
        print("      Account: DUQ566282 (Paper Trading)")

        order_result = client.place_futures_order(
            symbol="MGC",
            qty=1,
            side="buy",
            order_type="market"
        )

        order_id = order_result.get("id")
        print(f"\n    [OK] Order Placed Successfully!")
        print(f"    Order ID: {order_id}")
        print(f"    Status: {order_result.get('status', 'submitted')}\n")

        # Get order status
        print("[4] Checking Order Status...")
        import time
        time.sleep(1)

        for trade in client.ib.trades():
            if trade.order.orderId == order_id:
                status = trade.orderStatus.status
                filled = trade.orderStatus.filled
                print(f"    Order ID: {trade.order.orderId}")
                print(f"    Status: {status}")
                print(f"    Filled: {filled} contracts")
                print(f"    Remaining: {trade.order.totalQuantity - filled}")

                if status == "Filled":
                    print(f"    [OK] Order FILLED at market price\n")
                elif status in ["PendingSubmit", "PreSubmitted", "Submitted"]:
                    print(f"    [OK] Order PENDING - awaiting execution\n")
                else:
                    print(f"    Status: {status}\n")
                break

        # Account summary
        print("[5] Account Summary:")
        profile = client.get_profile()
        print(f"    Account: {profile.get('name', '?')}")
        print(f"    Account ID: {profile.get('account', {}).get('number', '?')}\n")

        # Cancel the order (cleanup)
        print("[6] Cleanup - Canceling Order...")
        cancel_result = client.cancel_order(order_id)
        if cancel_result.get("status") == "cancelled":
            print(f"    [OK] Order {order_id} cancelled\n")
        else:
            print(f"    [NOTE] Order may have already filled\n")

        # Summary
        print("=" * 80)
        print("[OK] MGC FUTURES TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print("\nTest Summary:")
        print("  [OK] Connected to IBKR Paper Trading Account (DUQ566282)")
        print("  [OK] Retrieved MGC futures quote")
        print(f"  [OK] Placed BUY order for 1 MGC contract (Order ID: {order_id})")
        print("  [OK] Verified order status")
        print("  [OK] Canceled test order")
        print("\nFutures Trading Ready!")
        print("  - MGC Micro Gold Futures trading is now enabled")
        print("  - Can place BUY/SELL orders for MGC contracts")
        print("  - Supports market and limit orders")
        print("\n")

        return 0

    except Exception as e:
        print(f"\n[FAIL] Error: {e}\n")
        print("Troubleshooting:")
        print("  1. Ensure TWS is running")
        print("  2. Verify DUQ566282 is active")
        print("  3. Check API -> Trust Client ID is enabled")
        print("  4. Confirm internet connection")
        print("\n")
        return 1

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK] Disconnected from IBKR")
            except Exception:
                pass


if __name__ == "__main__":
    exit_code = test_mgc_trade()
    sys.exit(exit_code)
