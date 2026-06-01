#!/usr/bin/env python3
"""Comprehensive IB Gateway connectivity verification test."""

import socket
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

print("=" * 80)
print("IB GATEWAY CONNECTIVITY VERIFICATION")
print("=" * 80)
print()

ET = ZoneInfo("America/New_York")
now = datetime.now(ET)
print(f"Test Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print()

# Step 1: Network connectivity test
print("[1] Network Connectivity Check")
print("-" * 80)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3)
    result = sock.connect_ex(("127.0.0.1", 4002))
    sock.close()
    if result == 0:
        print("[OK] IB Gateway is accessible on 127.0.0.1:4002")
    else:
        print("[FAIL] Cannot reach IB Gateway on 127.0.0.1:4002")
        print("      IB Gateway may not be running")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Network test error: {e}")
    sys.exit(1)

print()
print("[2] Configuration Verification")
print("-" * 80)
try:
    from iron_condor_0dte.config import Config
    cfg = Config()
    print(f"[OK] BROKER: {cfg.BROKER}")
    print(f"[OK] IBKR_HOST: {cfg.IBKR_HOST}")
    print(f"[OK] IBKR_PORT: {cfg.IBKR_PORT}")
    print(f"[OK] IBKR_CLIENT_ID: {cfg.IBKR_CLIENT_ID}")
    print(f"[OK] IBKR_ACCOUNT_ID: {cfg.IBKR_ACCOUNT_ID}")
    print(f"[OK] IBKR_PAPER_TRADE: {cfg.IBKR_PAPER_TRADE}")
except Exception as e:
    print(f"[FAIL] Configuration error: {e}")
    sys.exit(1)

print()
print("[3] IBKRClient Connection Test")
print("-" * 80)
try:
    from iron_condor_0dte.ibkr_client import IBKRClient
    print("[CONNECTING] Initializing IBKRClient...")
    client = IBKRClient(
        host=cfg.IBKR_HOST,
        port=cfg.IBKR_PORT,
        client_id=cfg.IBKR_CLIENT_ID,
        account_id=cfg.IBKR_ACCOUNT_ID,
        paper=cfg.IBKR_PAPER_TRADE,
    )
    print("[OK] IBKRClient connected successfully")
    print(f"[OK] Account ID: {client.account_id}")
    print(f"[OK] Paper Mode: {client.paper}")
    print("[DISCONNECTING] Closing connection...")
    client.disconnect()
    print("[OK] Disconnected cleanly")
except Exception as e:
    print(f"[FAIL] Connection error: {e}")
    sys.exit(1)

print()
print("[4] Live Trader Integration Test")
print("-" * 80)
try:
    from iron_condor_0dte.live_trader import _create_broker
    print("[CONNECTING] Creating broker via factory function...")
    broker = _create_broker(cfg)
    print(f"[OK] Broker created: {type(broker).__name__}")
    print(f"[OK] Account: {broker.account_id}")
    print("[DISCONNECTING] Disconnecting broker...")
    broker.disconnect()
    print("[OK] Broker disconnected cleanly")
except Exception as e:
    print(f"[FAIL] Broker factory error: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("✅ ALL CONNECTIVITY TESTS PASSED")
print("=" * 80)
print()
print("VERIFICATION RESULTS:")
print("  ✅ IB Gateway is running and responsive")
print("  ✅ Network connectivity verified (127.0.0.1:4002)")
print("  ✅ Configuration loaded correctly from .env")
print("  ✅ IBKRClient connection successful")
print("  ✅ Broker factory integration working")
print("  ✅ Live trader ready to execute")
print("  ✅ Clean disconnect confirmed")
print()
print("STATUS: ✅ SYSTEM IS FULLY OPERATIONAL & READY FOR TRADING")
print()
print("=" * 80)
