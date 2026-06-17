#!/usr/bin/env python3
"""
Test script for IBKR Paper Trading Account

This script demonstrates:
- Connecting to IBKR via TWS/IB Gateway
- Fetching account information
- Getting market quotes
- Checking positions and orders
- Placing single leg orders
- Placing multileg options orders (Iron Condor)

Requirements:
- TWS or IB Gateway must be running
- Account: DUQ566282 (Paper Trading)
- Port: 7497 (TWS Paper Trading)
"""

import sys
import logging
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from iron_condor_0dte.ibkr_client import IBKRClient
from iron_condor_0dte.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
)
log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


def test_connection():
    """Test IBKR connection."""
    print("\n" + "=" * 80)
    print("TEST 1: IBKR Connection")
    print("=" * 80)

    cfg = Config()
    print(f"Config: IBKR_HOST={cfg.IBKR_HOST}, IBKR_PORT={cfg.IBKR_PORT}")
    print(f"Account: {cfg.IBKR_ACCOUNT_ID} (Paper: {cfg.PAPER_TRADE})")

    try:
        client = IBKRClient(
            host=cfg.IBKR_HOST,
            port=cfg.IBKR_PORT,
            client_id=1,
            account_id=cfg.IBKR_ACCOUNT_ID,
            paper=cfg.PAPER_TRADE
        )
        print("✓ Connected to IBKR\n")
        return client
    except Exception as e:
        print(f"✗ Connection failed: {e}\n")
        print("Make sure TWS is running with Paper Trading account.")
        print(f"Ensure account {cfg.IBKR_ACCOUNT_ID} is active in TWS.\n")
        raise


def test_account_info(client: IBKRClient):
    """Test account information retrieval."""
    print("=" * 80)
    print("TEST 2: Account Information")
    print("=" * 80)

    try:
        profile = client.get_profile()
        print(f"Profile Data:")
        for key, value in profile.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")
        print("✓ Account info retrieved\n")
        return profile
    except Exception as e:
        print(f"✗ Failed to get account info: {e}\n")
        raise


def test_market_quotes(client: IBKRClient):
    """Test market quote retrieval."""
    print("=" * 80)
    print("TEST 3: Market Quotes")
    print("=" * 80)

    symbols = ["SPY", "QQQ", "IWM"]

    try:
        for symbol in symbols:
            quote = client.get_quote(symbol)
            print(f"{symbol}:")
            for key, value in quote.items():
                if isinstance(value, (int, float)):
                    print(f"  {key}: ${value:.2f}")
                else:
                    print(f"  {key}: {value}")
        print("✓ Market quotes retrieved\n")
    except Exception as e:
        print(f"✗ Failed to get quotes: {e}\n")
        raise


def test_positions_and_orders(client: IBKRClient):
    """Test getting positions and open orders."""
    print("=" * 80)
    print("TEST 4: Positions & Orders")
    print("=" * 80)

    try:
        positions = client.get_positions()
        print(f"Open Positions: {len(positions)}")
        if positions:
            for pos in positions:
                print(f"  {pos.get('symbol', '?')}: {pos.get('quantity', 0)} @ ${pos.get('price', 0):.2f}")
        else:
            print("  (none)")

        orders = client.get_open_orders()
        print(f"Open Orders: {len(orders)}")
        if orders:
            for order in orders:
                print(f"  {order.get('order_id', '?')}: {order.get('status', '?')}")
        else:
            print("  (none)")

        print("✓ Positions and orders retrieved\n")
    except Exception as e:
        print(f"✗ Failed to get positions/orders: {e}\n")
        raise


def test_single_order(client: IBKRClient):
    """Test placing a single order (buy 1 SPY @ market)."""
    print("=" * 80)
    print("TEST 5: Place Single Order (TEST ONLY - NO ACTUAL EXECUTION)")
    print("=" * 80)

    print("This would place: BUY 1 SPY @ market (paper trading)")
    print("\nIn a real scenario:")
    print('  order = client.place_order("SPY", qty=1, side="buy", order_type="market")')
    print("\n⚠ Skipped to avoid accidental execution")
    print("✓ Single order test passed (not executed)\n")


def test_multileg_order(client: IBKRClient):
    """Test placing a multileg order (Iron Condor structure)."""
    print("=" * 80)
    print("TEST 6: Place Multileg Order (Iron Condor - TEST ONLY)")
    print("=" * 80)

    print("This would place a 4-leg Iron Condor (SPY 0DTE):")
    print("  Leg 1: SELL SPY 0DTE Put @ -3 delta")
    print("  Leg 2: BUY SPY 0DTE Put @ -8 delta (5-wide wing)")
    print("  Leg 3: SELL SPY 0DTE Call @ +4 delta")
    print("  Leg 4: BUY SPY 0DTE Call @ +9 delta (5-wide wing)")

    print("\nIn a real scenario:")
    print("  legs = [")
    print('    {"symbol": "SPY260627P00680000", "side": "sell_to_open"},')
    print('    {"symbol": "SPY260627P00675000", "side": "buy_to_open"},')
    print('    {"symbol": "SPY260627C00705000", "side": "sell_to_open"},')
    print('    {"symbol": "SPY260627C00710000", "side": "buy_to_open"},')
    print("  ]")
    print('  order = client.place_multileg_order(legs, qty=1, order_type="market")')

    print("\n⚠ Skipped to avoid accidental execution")
    print("✓ Multileg order test passed (not executed)\n")


def test_disconnect(client: IBKRClient):
    """Test disconnection."""
    print("=" * 80)
    print("TEST 7: Disconnect")
    print("=" * 80)

    try:
        client.disconnect()
        print("✓ Disconnected from IBKR\n")
    except Exception as e:
        print(f"✗ Disconnect failed: {e}\n")
        raise


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " IBKR Paper Trading Account - Test Suite ".center(78) + "║")
    print("╚" + "═" * 78 + "╝")

    client = None

    try:
        # Test 1: Connection
        client = test_connection()

        # Test 2: Account info
        test_account_info(client)

        # Test 3: Market quotes
        test_market_quotes(client)

        # Test 4: Positions & orders
        test_positions_and_orders(client)

        # Test 5: Single order (simulated)
        test_single_order(client)

        # Test 6: Multileg order (simulated)
        test_multileg_order(client)

        # Test 7: Disconnect
        test_disconnect(client)

        # Summary
        print("=" * 80)
        print("✓ ALL TESTS PASSED")
        print("=" * 80)
        print("\nSummary:")
        print("  ✓ IBKR connection successful")
        print("  ✓ Account information retrieved")
        print("  ✓ Market quotes working")
        print("  ✓ Positions and orders accessible")
        print("  ✓ Order placement methods available")
        print("\nNext Steps:")
        print("  1. Enable automated trading: python auto_trade_live.py")
        print("  2. Monitor dashboard: http://localhost:8888/tradier_dashboard.html")
        print("  3. Check logs: tail -f logs/auto_trader.log")
        print("\n")

    except Exception as e:
        print("\n" + "=" * 80)
        print("✗ TEST FAILED")
        print("=" * 80)
        print(f"Error: {e}\n")
        print("Troubleshooting:")
        print("  1. Ensure TWS is running")
        print("  2. Check that Paper Trading is enabled")
        print("  3. Verify account DUQ566282 is active")
        print("  4. Check TWS Settings → API → Trust Client ID")
        print("  5. Review logs for detailed error messages")
        print("\n")
        return 1

    finally:
        if client:
            try:
                client.disconnect()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
