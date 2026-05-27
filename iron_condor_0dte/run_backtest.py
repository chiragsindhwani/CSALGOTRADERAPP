"""
Run the SPY Iron Condor 0DTE backtest and save results to
CS_ALGOTRADER_APP/backtest_results.json for the web dashboard.

Usage:
    python -m iron_condor_0dte.run_backtest
    python -m iron_condor_0dte.run_backtest --start 2024-05-01 --end 2025-05-01
    python -m iron_condor_0dte.run_backtest --contracts 3 --delta 0.12 --wing 3
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iron_condor_0dte.backtest import IronCondorBacktester, save_results_json
from iron_condor_0dte.config import Config


def main():
    _cfg = Config()
    parser = argparse.ArgumentParser(description="SPY Iron Condor 0DTE Backtester")
    parser.add_argument("--start",         default=None,  help="Start date YYYY-MM-DD")
    parser.add_argument("--end",           default=None,  help="End date YYYY-MM-DD")
    parser.add_argument("--contracts",     type=int,   default=_cfg.CONTRACTS,         help="Contracts per trade")
    parser.add_argument("--delta",         type=float, default=_cfg.TARGET_DELTA,      help="Target delta for short strikes")
    parser.add_argument("--wing",          type=float, default=_cfg.WING_WIDTH,        help="Wing width in dollars")
    parser.add_argument("--profit-target", type=float, default=_cfg.PROFIT_TARGET_PCT, help="Profit target as fraction of credit")
    parser.add_argument("--stop-mult",     type=float, default=_cfg.STOP_LOSS_MULT,    help="Stop loss multiplier of credit")
    parser.add_argument("--max-vix",       type=float, default=_cfg.MAX_VIX,           help="Skip days when VIX exceeds this")
    parser.add_argument("--output",        default=None, help="Output JSON path")
    args = parser.parse_args()

    end_date   = args.end   or date.today().strftime("%Y-%m-%d")
    start_date = args.start or (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")

    cfg = Config(
        CONTRACTS=args.contracts,
        TARGET_DELTA=args.delta,
        WING_WIDTH=args.wing,
        PROFIT_TARGET_PCT=args.profit_target,
        STOP_LOSS_MULT=args.stop_mult,
        MAX_VIX=args.max_vix,
    )

    output_dir = Path(__file__).resolve().parent.parent / "CS_ALGOTRADER_APP"
    output_dir.mkdir(exist_ok=True)
    output_path = args.output or str(output_dir / "backtest_results.json")

    log.info("=" * 60)
    log.info("  SPY Iron Condor 0DTE — Backtest")
    log.info("  Period : %s  to  %s", start_date, end_date)
    log.info("  Config : delta=%.2f  wing=$%.1f  PT=%.0f%%  SL=%.0f%%  contracts=%d",
             cfg.TARGET_DELTA, cfg.WING_WIDTH,
             cfg.PROFIT_TARGET_PCT * 100, cfg.STOP_LOSS_MULT * 100, cfg.CONTRACTS)
    log.info("=" * 60)

    backtester = IronCondorBacktester(cfg)
    results, summary = backtester.run(start_date, end_date)

    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Period          : {summary.start_date}  to  {summary.end_date}")
    print(f"  Trading days    : {summary.total_trading_days}")
    print(f"  Days traded     : {summary.days_traded}")
    print(f"  Days skipped    : {summary.days_skipped}")
    print(f"  Win rate        : {summary.win_rate:.1f}%")
    print(f"  Avg win         : ${summary.avg_win:.2f}")
    print(f"  Avg loss        : ${summary.avg_loss:.2f}")
    print(f"  Profit factor   : {summary.profit_factor:.2f}x")
    print(f"  Total P&L       : ${summary.total_pnl:,.2f}")
    print(f"  Avg daily P&L   : ${summary.avg_daily_pnl:.2f}")
    print(f"  Max drawdown    : ${summary.max_drawdown:,.2f}  ({summary.max_drawdown_pct:.1f}%)")
    print(f"  Sharpe ratio    : {summary.sharpe_ratio:.2f}")
    print(f"  Best day        : ${summary.best_day:.2f}")
    print(f"  Worst day       : ${summary.worst_day:.2f}")
    print(f"  Avg credit/day  : ${summary.avg_credit_collected:.2f}")
    print("=" * 60)

    save_results_json(results, summary, output_path)
    print(f"\nOpen CS_ALGOTRADER_APP/index.html in your browser to view the dashboard.\n")


if __name__ == "__main__":
    main()
