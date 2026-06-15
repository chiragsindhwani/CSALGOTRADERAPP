#!/usr/bin/env python3
"""
Fully automated startup script for SPY Iron Condor 0DTE strategy.
This script handles everything needed to start trading without manual intervention.

Usage:
    python autostart_trader.py

Setup:
    1. Windows Task Scheduler: Create a task to run this at 9:30 AM ET on weekdays
    2. Task settings:
       - Program: C:\Python314\python.exe (or your Python path)
       - Arguments: c:\MyApp\CSAlgoTraderApp\autostart_trader.py
       - Start in: c:\MyApp\CSAlgoTraderApp
       - Run with highest privileges: Yes
       - Run whether user is logged in or not: Yes
"""

import subprocess
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Log both to file and console
log_file = log_dir / f"autostart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")

# ─── Configuration ─────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_SCRIPT = PROJECT_ROOT / "scripts" / "dashboard_server.py"
VALIDATION_SCRIPT = PROJECT_ROOT / "validate_ibkr_setup.py"

DASHBOARD_PORT = 8888
DASHBOARD_STARTUP_TIMEOUT = 10  # seconds
IB_GATEWAY_TIMEOUT = 30  # seconds to wait for IB Gateway to be ready


# ─── Helper Functions ─────────────────────────────────────────────────────

def log_section(title: str):
    """Print a section header to logs."""
    log.info("=" * 70)
    log.info(title)
    log.info("=" * 70)


def is_market_open() -> bool:
    """Check if market is open (9:30 AM - 4:00 PM ET, Monday-Friday)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    decimal_hour = now.hour + now.minute / 60
    return 9.5 <= decimal_hour < 16.0


def is_pre_market() -> bool:
    """Check if we're in pre-market (before 9:30 AM ET)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    decimal_hour = now.hour + now.minute / 60
    return decimal_hour < 9.5


def wait_for_market_open(max_wait_minutes: int = 60):
    """Wait until market opens (9:30 AM ET), checking every 10 seconds."""
    log.info(f"Waiting for market to open... (max {max_wait_minutes} min)")
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60

    while time.time() - start_time < max_wait_seconds:
        now = datetime.now(ET)
        if is_market_open():
            log.info(f"Market is now open! (Current time: {now.strftime('%H:%M:%S ET')})")
            return True

        elapsed = int(time.time() - start_time)
        decimal_hour = now.hour + now.minute / 60
        if decimal_hour >= 9.5:
            minutes_to_open = int((9.5 - decimal_hour) * 60) if decimal_hour < 9.5 else 0
            log.info(
                f"Pre-market: {now.strftime('%H:%M:%S ET')} - Market opens in ~{abs(minutes_to_open)} min"
            )
        else:
            log.info(f"Pre-market: {now.strftime('%H:%M:%S ET')} - Waiting... ({elapsed}s elapsed)")

        time.sleep(10)

    log.error(f"Timeout waiting for market to open (waited {max_wait_minutes} min)")
    return False


def check_ib_gateway() -> bool:
    """Check if IB Gateway is running and responding on port 4002."""
    log.info("Checking IB Gateway connectivity...")
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()
        if result == 0:
            log.info("[OK] IB Gateway is running on localhost:4002")
            return True
        else:
            log.error("[FAIL] IB Gateway is NOT running on port 4002")
            return False
    except Exception as e:
        log.error(f"[FAIL] IB Gateway check failed: {e}")
        return False


def run_validation() -> bool:
    """Run the validation script and check results."""
    log_section("RUNNING PRE-FLIGHT VALIDATION")
    try:
        result = subprocess.run(
            [sys.executable, str(VALIDATION_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        log.info(result.stdout)
        if result.returncode == 0:
            log.info("[OK] Validation passed")
            return True
        else:
            log.error("[FAIL] Validation failed")
            if result.stderr:
                log.error(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        log.error("[FAIL] Validation script timed out")
        return False
    except Exception as e:
        log.error(f"[FAIL] Validation script error: {e}")
        return False


def start_dashboard() -> subprocess.Popen:
    """Start the dashboard server in the background."""
    log_section("STARTING DASHBOARD SERVER")
    try:
        log.info(f"Launching: {DASHBOARD_SCRIPT}")
        process = subprocess.Popen(
            [sys.executable, str(DASHBOARD_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        log.info(f"[OK] Dashboard process started (PID: {process.pid})")
        time.sleep(DASHBOARD_STARTUP_TIMEOUT)

        # Check if process is still running
        if process.poll() is None:
            log.info(f"[OK] Dashboard is running on http://localhost:{DASHBOARD_PORT}")
            return process
        else:
            log.error("[FAIL] Dashboard process exited unexpectedly")
            return None
    except Exception as e:
        log.error(f"[FAIL] Failed to start dashboard: {e}")
        return None


def start_live_trader():
    """Start the automated live trader (blocking, runs until session ends or error)."""
    log_section("STARTING AUTOMATED LIVE TRADER")
    try:
        log.info("Launching automated trader: python auto_trade_live.py")
        process = subprocess.Popen(
            [sys.executable, "auto_trade_live.py"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log.info(f"[OK] Automated trader process started (PID: {process.pid})")

        # Stream output from the trader in real-time
        while True:
            line = process.stdout.readline()
            if not line:
                break
            log.info(f"[TRADER] {line.rstrip()}")

        # Wait for process to complete
        process.wait()
        log.info(f"[OK] Automated trader session ended (exit code: {process.returncode})")
        return process.returncode
    except Exception as e:
        log.error(f"[FAIL] Failed to start live trader: {e}")
        return 1


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    """Main automation sequence."""
    log_section(f"AUTOSTART SEQUENCE INITIATED - {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")

    # Step 1: Check if it's a trading day
    now = datetime.now(ET)
    if now.weekday() >= 5:
        log.info(f"Today is {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]}")
        log.error("[FAIL] Markets are closed (weekend). Exiting.")
        return 1

    log.info(f"Today is {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]}")
    log.info(f"Current time: {now.strftime('%H:%M:%S ET')}")

    # Step 2: Wait for market to open if it's pre-market
    if is_pre_market():
        if not wait_for_market_open(max_wait_minutes=60):
            log.error("[FAIL] Failed to start: Market did not open in time")
            return 1
    elif not is_market_open():
        log.error("[FAIL] Market is closed. Exiting.")
        return 1

    # Step 3: Check broker-specific prerequisites
    log_section("PRE-FLIGHT CHECKS")
    import os
    broker = os.getenv("BROKER", "tradier").lower()

    if broker == "ibkr":
        # IBKR requires IB Gateway to be running
        if not check_ib_gateway():
            log.error("[FAIL] CRITICAL: IB Gateway is not running. Start IB Gateway and restart.")
            return 1
        # Run IBKR validation
        if not run_validation():
            log.error("[FAIL] CRITICAL: Pre-flight validation failed. Review errors above.")
            return 1
    elif broker == "tradier":
        # Tradier just needs API connectivity check (done in live_trader)
        log.info("[OK] Tradier broker configured (no IB Gateway required)")
    else:
        log.error(f"[FAIL] Unknown broker: {broker}")
        return 1

    # Step 5: Start dashboard
    dashboard_process = start_dashboard()
    if not dashboard_process:
        log.error("⚠ Dashboard startup failed, but continuing with trader...")

    # Step 6: Start live trader (blocking)
    try:
        exit_code = start_live_trader()
    except KeyboardInterrupt:
        log.info("[OK] Trader interrupted by user")
        exit_code = 0
    finally:
        # Cleanup: Stop dashboard if it's still running
        if dashboard_process and dashboard_process.poll() is None:
            log_section("CLEANUP")
            log.info(f"Stopping dashboard process (PID: {dashboard_process.pid})")
            dashboard_process.terminate()
            try:
                dashboard_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                dashboard_process.kill()
            log.info("[OK] Dashboard stopped")

    log_section("AUTOSTART SEQUENCE COMPLETE")
    log.info(f"Session ended at {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S ET')}")
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
