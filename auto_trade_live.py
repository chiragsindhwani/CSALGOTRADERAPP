#!/usr/bin/env python3
"""
FULLY AUTOMATED IRON CONDOR TRADER
- Automatic order placement (no manual intervention)
- Real-time monitoring
- Auto-exit on profit target or stop loss
- Force close at end of day

Usage:
    python auto_trade_live.py

Start Time: 10:15 AM ET (entry window)
End Time: 3:45 PM ET (force close)
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from iron_condor_0dte.auto_trader import AutomatedIronCondorTrader
from iron_condor_0dte.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.FileHandler("logs/auto_trader.log"),
        logging.StreamHandler(),
    ],
)

log = logging.getLogger(__name__)


def main():
    """Start automated trader"""
    print("=" * 80)
    print("FULLY AUTOMATED SPY 0DTE IRON CONDOR TRADER")
    print("=" * 80)
    print()
    print("Configuration:")
    print("  Broker: Tradier (Full API support)")
    print("  Strategy: SPY 0DTE Iron Condor")
    print("  Entry Window: 10:15 AM - 10:29 AM ET")
    print("  Profit Target: 35% of credit received")
    print("  Stop Loss: 45% of credit received")
    print("  Force Close: 3:45 PM ET")
    print()
    print("Starting automated trader...")
    print()

    cfg = Config()
    trader = AutomatedIronCondorTrader(cfg)

    try:
        trader.run()
    except KeyboardInterrupt:
        log.info("Trader stopped by user")
        print("\nTrader stopped.")
    except Exception as e:
        log.error("Fatal error: %s", e, exc_info=True)
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
