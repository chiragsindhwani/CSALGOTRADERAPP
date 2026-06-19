#!/usr/bin/env python3
"""
Execute Real ES Futures BUY Order on IBKR Paper Trading Account

ES = E-mini S&P 500 Futures (most liquid stock index futures)
- Contracts per point: 50
- Tick size: 0.25 points ($12.50 per tick)
- Trading hours: 23:00 ET (Sun-Fri) to 16:00 ET
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


def buy_es_now():
    """Execute immediate BUY order for 1 ES contract."""
    print("\n" + "=" * 80)
    print("EXECUTING ES FUTURES BUY ORDER - LIVE")
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

        # Get ES quote
        print("[STEP 3] Fetching ESU26 current quote...")
        quote = client.get_futures_quote("ES", expiry="202609")  # September 2026
        bid = quote['bid']
        ask = quote['ask']
        last = quote['last']

        if bid > 0:
            print(f"      Bid:  {bid:.2f} points")
            print(f"      Ask:  {ask:.2f} points")
            print(f"      Last: {last:.2f} points")
        else:
            print(f"      (Market data unavailable - market may be closed)")
            print(f"      Will place order anyway - will fill at market open")
        print()

        # Place BUY order
        print("[STEP 4] PLACING BUY ORDER...")
        print("      Symbol: ESU26 (E-mini S&P 500 - Sep 2026)")
        print("      Quantity: 1 contract")
        print("      Order Type: MARKET")
        print("      Action: BUY TO OPEN")
        print()

        order_result = client.place_futures_order(
            symbol="ES",
            qty=1,
            side="buy",
            order_type="market",
            expiry="202609"  # September 2026 in YYYYMM format
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

                    status_display = f"Status: {status}"
                    if filled > 0:
                        status_display += f" | Filled: {filled} @ ${avg_price:.2f}"
                    else:
                        status_display += f" | Remaining: {remaining}"

                    print(f"      [{i+1}s] {status_display}")

                    if status == "Filled":
                        print()
                        print("=" * 80)
                        print("[OK] ORDER FILLED SUCCESSFULLY!")
                        print("=" * 80)
                        print()
                        print("ORDER SUMMARY:")
                        print(f"      Order ID: {order_id}")
                        print(f"      Symbol: ES (E-mini S&P 500)")
                        print(f"      Side: BUY TO OPEN")
                        print(f"      Quantity: 1 contract")
                        print(f"      Fill Price: {avg_price:.2f} points")
                        print(f"      Fill Value: ${avg_price * 50:.2f} (50 multiplier)")
                        print(f"      Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"      Account: {cfg.IBKR_ACCOUNT_ID} (Paper Trading)")
                        print()
                        print("POSITION DETAILS:")
                        print(f"      Long 1x ES @ {avg_price:.2f} points")
                        if bid > 0:
                            print(f"      Current Bid: {bid:.2f} points")
                            print(f"      Current Ask: {ask:.2f} points")
                            unrealized = (last - avg_price) * 50
                            print(f"      Unrealized P&L: ${unrealized:.2f} per contract")
                        print()
                        print("CONTRACT DETAILS:")
                        print(f"      Multiplier: 50 (each point = $50)")
                        print(f"      Tick Size: 0.25 points ($12.50 per tick)")
                        print(f"      Trading Hours: 23:00 ET (Sun-Fri) to 16:00 ET")
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
        print("IMPORTANT: ES trades 23 hours/day (Sun-Fri)")
        print("- If market is closed, order will fill at market open")
        print("- Check TWS for real-time order status")
        print()
        print("To monitor the order:")
        print("  1. Open TWS")
        print("  2. Go to Account -> Orders")
        print("  3. Look for Order ID:", order_id)
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"[ERROR] {e}")
        print("=" * 80)
        print()
        import traceback
        traceback.print_exc()
        return 1

    finally:
        if client:
            try:
                client.disconnect()
                print("[OK] Disconnected from IBKR\n")
            except Exception:
                pass


if __name__ == "__main__":
    exit_code = buy_es_now()
    sys.exit(exit_code)
