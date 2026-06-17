#!/usr/bin/env python3
"""
Execute Real MGC Futures BUY Order on IBKR Paper Trading Account
"""

import sys
import logging
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from iron_condor_0dte.ibkr_client import IBKRClient
from iron_condor_0dte.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
)
log = logging.getLogger(__name__)


def buy_mgc_now():
    """Execute immediate BUY order for 1 MGC contract."""
    print("\n" + "=" * 80)
    print("EXECUTING MGC FUTURES BUY ORDER - LIVE")
    print("=" * 80)

    cfg = Config()
    client = None

    try:
        # Connect
        print("\n[STEP 1] Connecting to IBKR...")
        client = IBKRClient(
            host=cfg.IBKR_HOST,
            port=cfg.IBKR_PORT,
            client_id=1,
            account_id=cfg.IBKR_ACCOUNT_ID,
            paper=cfg.PAPER_TRADE
        )
        print(f"[OK] Connected to {cfg.IBKR_ACCOUNT_ID}\n")

        # Get account info
        print("[STEP 2] Verifying account...")
        profile = client.get_profile()
        print(f"[OK] Account: {profile.get('name')}\n")

        # Get MGC quote
        print("[STEP 3] Fetching MGC current quote...")
        quote = client.get_futures_quote("MGC")
        print(f"      Bid:  ${quote['bid']:.2f}")
        print(f"      Ask:  ${quote['ask']:.2f}")
        print(f"      Last: ${quote['last']:.2f}")
        print()

        # Place BUY order
        print("[STEP 4] PLACING BUY ORDER...")
        print("      Symbol: MGC (Micro Gold Futures)")
        print("      Quantity: 1 contract")
        print("      Order Type: MARKET")
        print("      Action: BUY TO OPEN")
        print()

        order_result = client.place_futures_order(
            symbol="MGC",
            qty=1,
            side="buy",
            order_type="market"
        )

        order_id = order_result.get("id")
        print(f"[OK] ORDER PLACED SUCCESSFULLY!")
        print(f"      Order ID: {order_id}")
        print(f"      Status: {order_result.get('status', 'submitted')}\n")

        # Wait and get order status
        print("[STEP 5] Monitoring order status...")
        for i in range(5):
            time.sleep(1)
            for trade in client.ib.trades():
                if trade.order.orderId == order_id:
                    status = trade.orderStatus.status
                    filled = trade.orderStatus.filled
                    remaining = trade.order.totalQuantity - filled
                    avg_price = trade.orderStatus.avgFillPrice

                    print(f"      [{i+1}s] Status: {status} | Filled: {filled} | Remaining: {remaining} | Avg Price: ${avg_price:.2f}")

                    if status == "Filled":
                        print()
                        print("=" * 80)
                        print("[OK] ORDER FILLED SUCCESSFULLY!")
                        print("=" * 80)
                        print()
                        print("ORDER SUMMARY:")
                        print(f"      Order ID: {order_id}")
                        print(f"      Symbol: MGC (Micro Gold Futures)")
                        print(f"      Side: BUY TO OPEN")
                        print(f"      Quantity: 1 contract")
                        print(f"      Fill Price: ${avg_price:.2f}")
                        print(f"      Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"      Account: {cfg.IBKR_ACCOUNT_ID} (Paper Trading)")
                        print()
                        print("POSITION DETAILS:")
                        print(f"      Long 1x MGC @ ${avg_price:.2f}")
                        print(f"      Current Bid: ${quote['bid']:.2f}")
                        print(f"      Current Ask: ${quote['ask']:.2f}")
                        print(f"      Unrealized P&L: ${(quote['last'] - avg_price):.2f} per contract")
                        print()
                        return 0

                    elif status in ["Cancelled", "Rejected"]:
                        print()
                        print("=" * 80)
                        print("[FAIL] ORDER CANCELLED/REJECTED")
                        print("=" * 80)
                        print(f"Status: {status}")
                        print()
                        return 1

                    break

        # If still pending after 5 seconds
        print()
        print("=" * 80)
        print("[PENDING] Order still pending...")
        print("=" * 80)
        print(f"Order ID: {order_id}")
        print("Status: Awaiting execution from market")
        print()
        print("Note: Market may be closed or order awaiting fill")
        print("Check TWS for real-time order status")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"[ERROR] {e}")
        print("=" * 80)
        print()
        return 1

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK] Disconnected from IBKR\n")
            except Exception:
                pass


if __name__ == "__main__":
    exit_code = buy_mgc_now()
    sys.exit(exit_code)
