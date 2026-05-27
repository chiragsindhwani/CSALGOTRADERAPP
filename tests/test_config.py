"""Tests for iron condor strategy configuration."""
import os
import pytest

# Provide dummy creds so Config() doesn't raise on import
os.environ.setdefault("TRADIER_API_TOKEN", "ci_dummy")
os.environ.setdefault("TRADIER_ACCOUNT_ID", "TESTACCT")
os.environ.setdefault("TRADIER_PAPER_TRADE", "true")


def test_config_imports():
    from iron_condor_0dte.config import config
    assert config is not None


def test_contracts():
    from iron_condor_0dte.config import config
    assert config.CONTRACTS == 20, f"Expected 20 contracts, got {config.CONTRACTS}"


def test_entry_time_is_9_15_cst():
    from iron_condor_0dte.config import config
    # 9:15 AM CST = 10:15 AM ET
    assert config.ENTRY_HOUR == 10
    assert config.ENTRY_MIN == 15


def test_force_close_time_is_2_45_cst():
    from iron_condor_0dte.config import config
    # 2:45 PM CST = 3:45 PM ET
    assert config.FORCE_CLOSE_HOUR == 15
    assert config.FORCE_CLOSE_MIN == 45


def test_strike_selection():
    from iron_condor_0dte.config import config
    assert config.TARGET_DELTA == 0.15
    assert config.WING_WIDTH == 2.0
    assert config.MIN_CREDIT == 0.40


def test_risk_management():
    from iron_condor_0dte.config import config
    assert config.PROFIT_TARGET_PCT == 0.15   # 15% profit target
    assert config.STOP_LOSS_MULT == 0.45      # 45% stop loss


def test_pdt_limits():
    from iron_condor_0dte.config import config
    assert config.PDT_MAX_DAY_TRADES == 3
    assert config.PDT_WINDOW_DAYS == 5


def test_vix_filter():
    from iron_condor_0dte.config import config
    assert config.MAX_VIX == 30.0


def test_fomc_dates_present():
    from iron_condor_0dte.config import config
    assert len(config.FOMC_DATES) >= 4
    # 2026 dates must be populated
    assert any("2026" in d for d in config.FOMC_DATES)


def test_commission_calculation():
    from iron_condor_0dte.config import config
    # Tradier: $0.35/contract/leg, 4 legs, open + close
    commission = 4 * config.CONTRACTS * 0.35 * 2
    assert commission == pytest.approx(56.0), f"Expected $56 commission for 20 contracts, got ${commission}"
