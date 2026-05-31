"""
Configuration for SPY Iron Condor 0DTE Strategy.
Based on the Breakeven Iron Condor methodology targeting $200/day.
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ── Broker Selection ──────────────────────────────────────────────────────
    BROKER: str = os.getenv("BROKER", "tradier").lower()

    # ── Tradier Credentials ───────────────────────────────────────────────────
    TRADIER_TOKEN:      str  = os.getenv("TRADIER_API_TOKEN", "")
    TRADIER_ACCOUNT_ID: str  = os.getenv("TRADIER_ACCOUNT_ID", "")
    PAPER_TRADE:        bool = os.getenv("TRADIER_PAPER_TRADE", "true").lower() == "true"

    # ── IBKR Credentials ──────────────────────────────────────────────────────
    IBKR_HOST:         str   = os.getenv("IBKR_HOST", "127.0.0.1")
    IBKR_PORT:         int   = int(os.getenv("IBKR_PORT", "4002"))
    IBKR_CLIENT_ID:    int   = int(os.getenv("IBKR_CLIENT_ID", "1"))
    IBKR_ACCOUNT_ID:   str   = os.getenv("IBKR_ACCOUNT_ID", "")
    IBKR_PAPER_TRADE:  bool  = os.getenv("IBKR_PAPER_TRADE", "true").lower() == "true"

    # ── Instrument ────────────────────────────────────────────────────────────
    SYMBOL: str = "SPY"
    ACCOUNT_SIZE: float = 25_000.0   # paper trading account size

    # ── Strike Selection ──────────────────────────────────────────────────────
    TARGET_DELTA: float = 0.15       # short strikes at ~15 delta (OTM)
    WING_WIDTH: float   = 5.0        # $5-wide spreads — wider wings = more credit on 0DTE
    MIN_CREDIT: float        = 0.40   # limit-order credit floor for entry (per share)
    MIN_ACTUAL_CREDIT: float = 0.10   # post-fill abort threshold — if actual fill < this, exit immediately

    # ── Timing (Eastern Time) ─────────────────────────────────────────────────
    ENTRY_HOUR: int = 10
    ENTRY_MIN: int = 15              # Enter at 10:15 AM ET
    FORCE_CLOSE_HOUR: int = 15
    FORCE_CLOSE_MIN: int = 45        # Force close at 3:45 PM ET

    # ── Risk Management ───────────────────────────────────────────────────────
    PROFIT_TARGET_PCT: float = 0.35  # Close at 35% of credit received
    STOP_LOSS_MULT: float = 0.45     # Stop loss at 45% of credit received
    CONTRACTS: int = 9               # Contracts per trade (live trading) — capped by TQQQ margin lock

    # ── PDT Rule ─────────────────────────────────────────────────────────────
    # Max 3 day-trade round-trips in any rolling 5-business-day window
    PDT_MAX_DAY_TRADES: int = 3
    PDT_WINDOW_DAYS: int = 5

    # ── Market Filters ────────────────────────────────────────────────────────
    MAX_VIX: float = 30.0            # Skip if VIX above this level
    SKIP_FOMC: bool = True           # Skip FOMC announcement days

    # FOMC announcement dates — update annually
    FOMC_DATES: List[str] = field(default_factory=lambda: [
        # 2024
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
        "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
        # 2025
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-11",
        "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
        # 2026
        "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-10",
    ])


# Singleton instance used across the package
config = Config()
