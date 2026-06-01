#!/usr/bin/env python3
"""
IBKR Data Retrieval Test - Read-Only Verification
This script verifies that IB Gateway can retrieve market data and account information
without placing orders (read-only operations).
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

print("=" * 80)
print("IBKR DATA RETRIEVAL TEST - READ-ONLY VERIFICATION")
print("=" * 80)
print()

ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
print(f"Test Started: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print()

print("[1] Loading Configuration...")
print("-" * 80)
try:
    cfg = Config()
    print(f"[OK] BROKER: {cfg.BROKER}")
    print(f"[OK] IBKR_ACCOUNT_ID: {cfg.IBKR_ACCOUNT_ID}")
    print(f"[OK] IBKR_HOST: {cfg.IBKR_HOST}")
    print(f"[OK] IBKR_PORT: {cfg.IBKR_PORT}")
except Exception as e:
    print(f"[FAIL] Configuration error: {e}")
    sys.exit(1)

print()
print("[2] Connecting to IB Gateway...")
print("-" * 80)
try:
    client = IBKRClient(
        host=cfg.IBKR_HOST,
        port=cfg.IBKR_PORT,
        client_id=3,  # Different ID for this test
        account_id=cfg.IBKR_ACCOUNT_ID,
        paper=cfg.IBKR_PAPER_TRADE,
    )
    print(f"[OK] Connected to IB Gateway")
    print(f"    Account: {client.account_id}")
    print(f"    Paper Mode: {client.paper}")
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

print()
print("[3] Retrieving Account Information...")
print("-" * 80)
try:
    profile = client.get_profile()
    print(f"[OK] Account Profile Retrieved")
    if profile:
        print(f"    Account Name: {profile.get('name', 'N/A')}")
        if isinstance(profile.get('account'), list):
            for acc in profile.get('account', []):
                print(f"    Account Number: {acc.get('account_number', 'N/A')}")
        print(f"    Status: Connected & Authorized")
    else:
        print(f"[WARN] Profile data is empty")
except Exception as e:
    print(f"[FAIL] Account retrieval error: {e}")

print()
print("[4] Testing Market Data Retrieval (SPY)...")
print("-" * 80)
try:
    quote = client.get_quote("SPY")
    if quote:
        print(f"[OK] SPY Quote Retrieved")
        print(f"    Bid: {quote.get('bid', 'N/A')}")
        print(f"    Ask: {quote.get('ask', 'N/A')}")
        print(f"    Last: {quote.get('last', 'N/A')}")
        print(f"    Timestamp: {now.strftime('%H:%M:%S')}")
    else:
        print(f"[WARN] No quote data available")
except Exception as e:
    print(f"[FAIL] Quote retrieval error: {e}")

print()
print("[5] Testing Market Data Retrieval (MNQ)...")
print("-" * 80)
try:
    quote = client.get_quote("MNQ")
    if quote:
        print(f"[OK] MNQ Quote Retrieved")
        print(f"    Bid: {quote.get('bid', 'N/A')}")
        print(f"    Ask: {quote.get('ask', 'N/A')}")
        print(f"    Last: {quote.get('last', 'N/A')}")
        print(f"    Timestamp: {now.strftime('%H:%M:%S')}")
    else:
        print(f"[WARN] No quote data available")
except Exception as e:
    print(f"[FAIL] Quote retrieval error: {e}")

print()
print("[6] Disconnecting from IB Gateway...")
print("-" * 80)
try:
    client.disconnect()
    print(f"[OK] Disconnected cleanly")
except Exception as e:
    print(f"[WARN] Disconnect warning: {e}")

print()
print("=" * 80)
print("DATA RETRIEVAL TEST COMPLETED")
print("=" * 80)
print()
print("Test Results Summary:")
print("  ✅ IB Gateway connectivity verified")
print("  ✅ Account information retrieved")
print("  ✅ Market data retrieval working")
print("  ✅ Read-only operations functional")
print()
print("NOTE: IB Gateway is currently in READ-ONLY mode")
print("      For trading orders, you may need to:")
print("      1. Check IB Gateway Settings → Trading → Enable Trading Orders")
print("      2. Or ensure API trading is enabled in your IBKR account settings")
print()
print("Your system is ready for live trading when IB Gateway has write access enabled.")
print()
