"""
Backtesting engine for SPY Iron Condor 0DTE Strategy.

Data sources:
  - SPY OHLCV: yfinance (1 year of daily bars)
  - VIX:       yfinance (^VIX, used as proxy for implied volatility)

Simulation model:
  - Entry at the day's open price (approximates 10:15 AM price level)
  - Time to expiration = 5.75 trading hours at entry
  - Strikes selected via Black-Scholes at target delta
  - Stop loss / profit target checked against intraday high/low
  - Force close at end-of-day (4:00 PM equivalent)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from .config import Config, config as default_config
from .options_pricing import (
    find_strike_for_delta,
    iron_condor_credit,
    iron_condor_cost_to_close,
    trading_hours_remaining,
    bs_price,
)

log = logging.getLogger(__name__)


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class TradeResult:
    date: str
    spy_open: float
    spy_high: float
    spy_low: float
    spy_close: float
    vix: float
    short_call: float
    long_call: float
    short_put: float
    long_put: float
    credit_per_contract: float   # total credit × 100 (dollar amount)
    max_loss_per_contract: float
    profit_target_per_contract: float
    stop_loss_per_contract: float
    outcome: str                 # "profit_target" | "call_stop" | "put_stop" | "double_stop" | "expired"
    pnl_per_contract: float      # net P&L in dollars
    contracts: int
    total_pnl: float
    cumulative_pnl: float = 0.0
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class BacktestSummary:
    start_date: str
    end_date: str
    total_trading_days: int
    days_traded: int
    days_skipped: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    avg_credit_collected: float
    avg_daily_pnl: float
    best_day: float
    worst_day: float
    config_snapshot: dict = field(default_factory=dict)


# ─── Backtest Engine ──────────────────────────────────────────────────────────

class IronCondorBacktester:
    def __init__(self, cfg: Config = None):
        self.cfg = cfg or default_config

    def _fetch_data(self, start: str, end: str) -> pd.DataFrame:
        """Fetch SPY OHLCV and VIX daily data from Yahoo Finance."""
        log.info("Fetching SPY data from %s to %s ...", start, end)
        spy = yf.download("SPY", start=start, end=end, auto_adjust=True, progress=False)
        vix = yf.download("^VIX", start=start, end=end, auto_adjust=True, progress=False)

        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)

        df = spy[["Open", "High", "Low", "Close"]].copy()
        df.columns = ["spy_open", "spy_high", "spy_low", "spy_close"]
        df["vix"] = vix["Close"].reindex(df.index).ffill()
        df.dropna(inplace=True)
        log.info("Loaded %d trading days.", len(df))
        return df

    def _should_skip(self, trade_date: date, vix: float) -> tuple:
        """Return (skip, reason) for a given day."""
        date_str = trade_date.strftime("%Y-%m-%d")
        if self.cfg.SKIP_FOMC and date_str in self.cfg.FOMC_DATES:
            return True, "FOMC day"
        if vix > self.cfg.MAX_VIX:
            return True, f"VIX {vix:.1f} > {self.cfg.MAX_VIX}"
        return False, ""

    def _simulate_day(self, row: pd.Series, cum_pnl: float) -> TradeResult:
        """Simulate one trading day and return a TradeResult."""
        trade_date = row.name.date() if hasattr(row.name, "date") else row.name
        date_str = str(trade_date)

        S = float(row["spy_open"])
        high = float(row["spy_high"])
        low = float(row["spy_low"])
        vix = float(row["vix"])
        sigma = vix / 100.0      # annualised implied volatility
        r = 0.05                 # risk-free rate
        T = trading_hours_remaining(self.cfg.ENTRY_HOUR, self.cfg.ENTRY_MIN)

        skip, reason = self._should_skip(trade_date, vix)
        if skip:
            return TradeResult(
                date=date_str, spy_open=S, spy_high=high, spy_low=float(row["spy_low"]),
                spy_close=float(row["spy_close"]), vix=vix,
                short_call=0, long_call=0, short_put=0, long_put=0,
                credit_per_contract=0, max_loss_per_contract=0,
                profit_target_per_contract=0, stop_loss_per_contract=0,
                outcome="skipped", pnl_per_contract=0, contracts=0,
                total_pnl=0, cumulative_pnl=cum_pnl,
                skipped=True, skip_reason=reason,
            )

        # ── Strike selection ──────────────────────────────────────────────────
        short_call = find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "call")
        short_put  = find_strike_for_delta(S, T, r, sigma, self.cfg.TARGET_DELTA, "put")
        long_call  = short_call + self.cfg.WING_WIDTH
        long_put   = short_put  - self.cfg.WING_WIDTH

        # ── Credit & risk ─────────────────────────────────────────────────────
        total_credit = iron_condor_credit(S, short_call, long_call, short_put, long_put, T, r, sigma)
        credit_dollars = round(total_credit * 100, 2)

        if total_credit < self.cfg.MIN_CREDIT:
            return TradeResult(
                date=date_str, spy_open=S, spy_high=high, spy_low=float(row["spy_low"]),
                spy_close=float(row["spy_close"]), vix=vix,
                short_call=short_call, long_call=long_call,
                short_put=short_put, long_put=long_put,
                credit_per_contract=credit_dollars, max_loss_per_contract=0,
                profit_target_per_contract=0, stop_loss_per_contract=0,
                outcome="skipped", pnl_per_contract=0, contracts=0,
                total_pnl=0, cumulative_pnl=cum_pnl,
                skipped=True, skip_reason=f"Credit ${credit_dollars:.2f} < min ${self.cfg.MIN_CREDIT*100:.2f}",
            )

        max_loss_dollars  = (self.cfg.WING_WIDTH - total_credit) * 100
        profit_target_dol = total_credit * self.cfg.PROFIT_TARGET_PCT * 100
        stop_loss_dollars = total_credit * self.cfg.STOP_LOSS_MULT * 100

        # ── Position sizing ───────────────────────────────────────────────────
        contracts = self.cfg.CONTRACTS

        # ── Intraday simulation (using daily high/low as path bounds) ─────────
        # Stop territory: stock has moved halfway into the wing
        call_stop_price = short_call + self.cfg.WING_WIDTH * 0.5
        put_stop_price  = short_put  - self.cfg.WING_WIDTH * 0.5

        call_breached = high >= call_stop_price
        put_breached  = low  <= put_stop_price

        if call_breached and put_breached:
            outcome = "double_stop"
            pnl_per = -max_loss_dollars * 1.5
        elif call_breached:
            outcome = "call_stop"
            pnl_per = -stop_loss_dollars + (total_credit * 0.5 * 100)
        elif put_breached:
            outcome = "put_stop"
            pnl_per = -stop_loss_dollars + (total_credit * 0.5 * 100)
        else:
            outcome = "profit_target"
            pnl_per = profit_target_dol

        total_pnl = round(pnl_per * contracts, 2)
        new_cum   = round(cum_pnl + total_pnl, 2)

        return TradeResult(
            date=date_str,
            spy_open=round(S, 2),
            spy_high=round(high, 2),
            spy_low=round(float(row["spy_low"]), 2),
            spy_close=round(float(row["spy_close"]), 2),
            vix=round(vix, 2),
            short_call=round(short_call, 1),
            long_call=round(long_call, 1),
            short_put=round(short_put, 1),
            long_put=round(long_put, 1),
            credit_per_contract=round(credit_dollars, 2),
            max_loss_per_contract=round(max_loss_dollars, 2),
            profit_target_per_contract=round(profit_target_dol, 2),
            stop_loss_per_contract=round(stop_loss_dollars, 2),
            outcome=outcome,
            pnl_per_contract=round(pnl_per, 2),
            contracts=contracts,
            total_pnl=total_pnl,
            cumulative_pnl=new_cum,
        )

    def run(self, start_date: str, end_date: str) -> tuple:
        df = self._fetch_data(start_date, end_date)
        results = []
        cum_pnl = 0.0

        for idx, row in df.iterrows():
            result = self._simulate_day(row, cum_pnl)
            if not result.skipped:
                cum_pnl = result.cumulative_pnl
            results.append(result)

        summary = self._compute_summary(results, start_date, end_date, df)
        return results, summary

    def _compute_summary(self, results, start_date, end_date, df):
        traded = [r for r in results if not r.skipped]
        wins   = [r for r in traded if r.total_pnl > 5]
        losses = [r for r in traded if r.total_pnl < -5]
        beven  = [r for r in traded if -5 <= r.total_pnl <= 5]

        total_pnl   = sum(r.total_pnl for r in traded)
        avg_win     = float(np.mean([r.total_pnl for r in wins]))   if wins   else 0.0
        avg_loss    = float(np.mean([r.total_pnl for r in losses])) if losses else 0.0
        gross_wins  = sum(r.total_pnl for r in wins)
        gross_loss  = abs(sum(r.total_pnl for r in losses))
        pf          = gross_wins / gross_loss if gross_loss > 0 else float("inf")

        equity = [0.0]
        for r in traded:
            equity.append(equity[-1] + r.total_pnl)
        equity_arr = np.array(equity)
        peak = np.maximum.accumulate(equity_arr)
        dd = equity_arr - peak
        max_dd = float(np.min(dd))
        max_dd_pct = (max_dd / self.cfg.ACCOUNT_SIZE) * 100

        daily_pnls = np.array([r.total_pnl for r in traded])
        sharpe = 0.0
        if len(daily_pnls) > 1 and daily_pnls.std() > 0:
            sharpe = (daily_pnls.mean() / daily_pnls.std()) * np.sqrt(252)

        avg_credit = float(np.mean([r.credit_per_contract for r in traded])) if traded else 0.0

        return BacktestSummary(
            start_date=start_date,
            end_date=end_date,
            total_trading_days=len(df),
            days_traded=len(traded),
            days_skipped=len(results) - len(traded),
            total_trades=len(traded),
            winning_trades=len(wins),
            losing_trades=len(losses),
            breakeven_trades=len(beven),
            win_rate=round(len(wins) / len(traded) * 100, 1) if traded else 0.0,
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(pf, 2),
            total_pnl=round(total_pnl, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            avg_credit_collected=round(avg_credit, 2),
            avg_daily_pnl=round(float(np.mean(daily_pnls)) if len(daily_pnls) else 0.0, 2),
            best_day=round(float(np.max(daily_pnls)) if len(daily_pnls) else 0.0, 2),
            worst_day=round(float(np.min(daily_pnls)) if len(daily_pnls) else 0.0, 2),
            config_snapshot={
                "symbol": self.cfg.SYMBOL,
                "wing_width": self.cfg.WING_WIDTH,
                "target_delta": self.cfg.TARGET_DELTA,
                "profit_target_pct": f"{self.cfg.PROFIT_TARGET_PCT*100:.0f}%",
                "stop_loss_pct": f"{self.cfg.STOP_LOSS_MULT*100:.0f}%",
                "contracts": self.cfg.CONTRACTS,
                "buying_power_required": f"~${self.cfg.WING_WIDTH * 100 * self.cfg.CONTRACTS:,.0f}",
                "max_vix": self.cfg.MAX_VIX,
                "entry_time": f"{self.cfg.ENTRY_HOUR:02d}:{self.cfg.ENTRY_MIN:02d} ET",
                "force_close": f"{self.cfg.FORCE_CLOSE_HOUR:02d}:{self.cfg.FORCE_CLOSE_MIN:02d} ET",
            },
        )


def save_results_json(results, summary, output_path: str) -> None:
    """Save backtest results to JSON and a companion JS file for the web app."""
    data = {
        "summary": asdict(summary),
        "trades": [asdict(r) for r in results],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Results saved -> {output_path}")

    # Write a JS file so index.html works with file:// and http:// alike
    js_path = output_path.replace("backtest_results.json", "backtest_data.js")
    with open(js_path, "w") as f:
        f.write("window.BACKTEST_DATA = ")
        json.dump(data, f)
        f.write(";")
    print(f"JS bundle  saved -> {js_path}")
