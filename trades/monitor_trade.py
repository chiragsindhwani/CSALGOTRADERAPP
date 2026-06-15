#!/usr/bin/env python3
"""
ALPACA PAPER TRADING - REAL-TIME TRADE MONITORING
Monitor the 3-step Iron Condor position
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from iron_condor_0dte.alpaca_client import AlpacaClient
from iron_condor_0dte.config import Config

ET = ZoneInfo("America/New_York")

def monitor_iron_condor():
    """Monitor open Iron Condor position"""
    
    cfg = Config()
    client = AlpacaClient(
        api_key=cfg.ALPACA_API_KEY,
        secret_key=cfg.ALPACA_SECRET_KEY,
        paper=cfg.ALPACA_PAPER_TRADE
    )
    
    # Trade parameters
    profit_target = 20.30  # 35% of $0.58 credit
    stop_loss = -26.10     # 45% of $0.58 credit
    force_close_time = 15  # 3:45 PM ET (15:45)
    
    print("=" * 80)
    print("ALPACA PAPER TRADING - POSITION MONITOR")
    print("=" * 80)
    print()
    print("Monitoring Iron Condor Trade:")
    print(f"  Profit Target: +${profit_target:.2f}")
    print(f"  Stop Loss: ${stop_loss:.2f}")
    print(f"  Force Close: 3:45 PM ET")
    print()
    
    while True:
        try:
            now = datetime.now(ET)
            hour = now.hour
            minute = now.minute
            
            # Check if market is closed
            if hour >= 16 or (hour < 9) or now.weekday() >= 5:
                print(f"[{now.strftime('%I:%M %p')}] Market Closed - Trade Monitoring Stopped")
                break
            
            # Get current positions
            positions = client.get_positions()
            
            print(f"\n[{now.strftime('%I:%M:%S %p')}] Position Update:")
            print("-" * 80)
            
            if not positions:
                print("  No open positions found.")
                print("  Waiting for orders to fill...")
                time.sleep(60)
                continue
            
            # Display positions
            total_pnl = 0
            for pos in positions:
                symbol = pos.get('symbol', 'N/A')
                qty = pos.get('qty', 0)
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                market_value = float(pos.get('market_value', 0))
                
                if 'SPY' in symbol:
                    print(f"  {symbol}: {qty} shares")
                    print(f"    Market Value: ${market_value:.2f}")
                    print(f"    Unrealized P&L: ${unrealized_pl:.2f}")
                    total_pnl += unrealized_pl
            
            print()
            print(f"Total Cumulative P&L: ${total_pnl:.2f}")
            print()
            
            # Check profit target
            if total_pnl >= profit_target:
                print("[ALERT] PROFIT TARGET HIT!")
                print(f"  Current P&L: ${total_pnl:.2f}")
                print(f"  Target: ${profit_target:.2f}")
                print()
                print("ACTION REQUIRED: Close entire position")
                print("  1. Log into https://app.alpaca.markets")
                print("  2. Go to 'Positions' tab")
                print("  3. Close the SPY Iron Condor position at market price")
                print("  4. Record final P&L")
                break
            
            # Check stop loss
            if total_pnl <= stop_loss:
                print("[ALERT] STOP LOSS HIT!")
                print(f"  Current P&L: ${total_pnl:.2f}")
                print(f"  Stop Loss: ${stop_loss:.2f}")
                print()
                print("ACTION REQUIRED: Close entire position IMMEDIATELY")
                print("  1. Log into https://app.alpaca.markets")
                print("  2. Go to 'Positions' tab")
                print("  3. Close the SPY Iron Condor position at market price")
                print("  4. Record final P&L")
                break
            
            # Check force close time
            if hour == force_close_time and minute >= 45:
                print("[ALERT] FORCE CLOSE TIME!")
                print(f"  Current P&L: ${total_pnl:.2f}")
                print()
                print("ACTION REQUIRED: Close entire position before market close")
                print("  1. Log into https://app.alpaca.markets")
                print("  2. Go to 'Positions' tab")
                print("  3. Close the SPY Iron Condor position at market price")
                print("  4. Record final P&L")
                break
            
            # Wait before next check
            print(f"Status: Position open | Next check in 5 minutes...")
            time.sleep(300)
            
        except KeyboardInterrupt:
            print("\n[INFO] Monitoring stopped by user")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            print("Retrying in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    monitor_iron_condor()
