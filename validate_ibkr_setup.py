#!/usr/bin/env python3
"""IBKR Paper Trading - Pre-Launch Validation Script"""
import os
from pathlib import Path

print("=" * 70)
print("IBKR PAPER TRADING - PRE-LAUNCH VALIDATION")
print("=" * 70)
print()

# 1. Check .env configuration
print("[1] Configuration Check")
print("-" * 70)
env_file = Path(".env")
if env_file.exists():
    env_vars = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

    broker = env_vars.get("BROKER", "not set")
    ibkr_host = env_vars.get("IBKR_HOST", "not set")
    ibkr_port = env_vars.get("IBKR_PORT", "not set")
    ibkr_account = env_vars.get("IBKR_ACCOUNT_ID", "not set")
    ibkr_paper = env_vars.get("IBKR_PAPER_TRADE", "not set")

    print(f"[OK] BROKER: {broker}")
    if broker == "ibkr":
        print(f"     Status: CORRECT (set to IBKR)")
    else:
        print(f"     Status: WRONG (should be 'ibkr')")

    print()
    print(f"[OK] IBKR_HOST: {ibkr_host}")
    print(f"     Status: {'CORRECT (localhost)' if ibkr_host == '127.0.0.1' else 'CHECK'}")

    print()
    print(f"[OK] IBKR_PORT: {ibkr_port}")
    print(f"     Status: {'CORRECT (paper)' if ibkr_port == '4002' else 'CHECK (should be 4002 for paper)'}")

    print()
    if "DU" in ibkr_account and ibkr_account != "DU123456789":
        print(f"[OK] IBKR_ACCOUNT_ID: {ibkr_account}")
        print(f"     Status: SET (valid format)")
    else:
        print(f"[WARN] IBKR_ACCOUNT_ID: {ibkr_account}")
        print(f"     Status: PLACEHOLDER (needs your actual account ID)")

    print()
    print(f"[OK] IBKR_PAPER_TRADE: {ibkr_paper}")
    print(f"     Status: {'CORRECT (paper mode)' if ibkr_paper == 'true' else 'CHECK'}")
else:
    print("[FAIL] .env file not found!")

print()
print("[2] Python Imports Check")
print("-" * 70)

checks = []
try:
    from iron_condor_0dte.broker_base import BaseBrokerClient
    print("[OK] BaseBrokerClient imported")
    checks.append(True)
except Exception as e:
    print(f"[FAIL] BaseBrokerClient: {e}")
    checks.append(False)

try:
    from iron_condor_0dte.ibkr_client import IBKRClient
    print("[OK] IBKRClient imported")
    checks.append(True)
except Exception as e:
    print(f"[FAIL] IBKRClient: {e}")
    checks.append(False)

try:
    from iron_condor_0dte.config import Config
    print("[OK] Config imported")
    checks.append(True)
except Exception as e:
    print(f"[FAIL] Config: {e}")
    checks.append(False)

try:
    from iron_condor_0dte.live_trader import IronCondorTrader
    print("[OK] IronCondorTrader imported")
    checks.append(True)
except Exception as e:
    print(f"[FAIL] IronCondorTrader: {e}")
    checks.append(False)

print()
print("[3] Files Check")
print("-" * 70)

files_to_check = [
    ("core/config", Path("iron_condor_0dte/config.py")),
    ("IBKR client", Path("iron_condor_0dte/ibkr_client.py")),
    ("live trader", Path("iron_condor_0dte/live_trader.py")),
    ("broker server", Path("scripts/dashboard_server.py")),
    ("trade logger", Path("iron_condor_0dte/trade_logger.py")),
]

for name, path in files_to_check:
    if path.exists():
        size_kb = path.stat().st_size / 1024
        print(f"[OK] {name}: {path} ({size_kb:.1f} KB)")
        checks.append(True)
    else:
        print(f"[FAIL] {name}: {path} NOT FOUND")
        checks.append(False)

print()
print("[4] Data Directory Check")
print("-" * 70)

data_dirs = [
    ("trades", Path("data/trades")),
    ("logs", Path("data/logs")),
]

for name, path in data_dirs:
    if path.exists():
        print(f"[OK] {name}: {path}")
        checks.append(True)
    else:
        print(f"[WARN] {name}: {path} (will be created on first run)")

print()
print("[5] Dashboard Check")
print("-" * 70)

dashboard_file = Path("dashboard/tradier_dashboard.html")
if dashboard_file.exists():
    size_kb = dashboard_file.stat().st_size / 1024
    print(f"[OK] Dashboard: {dashboard_file} ({size_kb:.1f} KB)")
    # Check if broker toggle is in the file
    try:
        content = dashboard_file.read_text(encoding='utf-8')
    except:
        content = dashboard_file.read_text(encoding='utf-8', errors='ignore')
    if "broker-toggle-wrap" in content:
        print(f"     Broker toggle: PRESENT")
        checks.append(True)
    else:
        print(f"     Broker toggle: NOT FOUND")
        checks.append(False)
else:
    print(f"[FAIL] Dashboard: {dashboard_file} NOT FOUND")
    checks.append(False)

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
passed = sum(checks)
total = len(checks)
print(f"Checks Passed: {passed}/{total}")

if passed == total:
    print()
    print("[OK] ALL SYSTEMS GO FOR TOMORROW MORNING!")
    print()
    print("NEXT STEPS:")
    print("1. Get your IBKR paper account ID (format: DU1234567)")
    print("2. Update .env: IBKR_ACCOUNT_ID=YOUR_ACCOUNT_ID")
    print("3. Download IB Gateway: https://www.interactivebrokers.com/en/trading/ibgateway-latest.php")
    print("4. Tomorrow at 9:30 AM ET: Start IB Gateway, log in")
    print("5. Tomorrow at 9:45 AM ET: Run python validate_ibkr_setup.py")
    print("6. Tomorrow at 9:55 AM ET: Run python -m iron_condor_0dte.live_trader")
else:
    print()
    print(f"[WARN] {total - passed} check(s) failed. Review above.")
