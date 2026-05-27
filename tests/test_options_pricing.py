"""Tests for Black-Scholes options pricing utilities."""
import pytest

# Typical 0DTE conditions
SPY   = 570.0
T_0DTE = 1 / (252 * 6.5)   # ~1 trading hour expressed as fraction of year
R     = 0.05
SIGMA = 0.18


def test_bs_price_call_positive():
    from iron_condor_0dte.options_pricing import bs_price
    price = bs_price(SPY, K=580, T=T_0DTE, r=R, sigma=SIGMA, option_type="call")
    assert price > 0


def test_bs_price_put_positive():
    from iron_condor_0dte.options_pricing import bs_price
    price = bs_price(SPY, K=560, T=T_0DTE, r=R, sigma=SIGMA, option_type="put")
    assert price > 0


def test_itm_call_more_expensive_than_otm():
    from iron_condor_0dte.options_pricing import bs_price
    itm = bs_price(SPY, K=560, T=T_0DTE, r=R, sigma=SIGMA, option_type="call")
    otm = bs_price(SPY, K=580, T=T_0DTE, r=R, sigma=SIGMA, option_type="call")
    assert itm > otm


def test_call_delta_range():
    from iron_condor_0dte.options_pricing import bs_delta
    delta = bs_delta(SPY, K=580, T=T_0DTE, r=R, sigma=SIGMA, option_type="call")
    assert 0 < delta < 0.5, f"OTM call delta should be 0–0.5, got {delta:.4f}"


def test_put_delta_range():
    from iron_condor_0dte.options_pricing import bs_delta
    delta = bs_delta(SPY, K=560, T=T_0DTE, r=R, sigma=SIGMA, option_type="put")
    assert -0.5 < delta < 0, f"OTM put delta should be -0.5–0, got {delta:.4f}"


def test_find_call_strike_is_otm():
    from iron_condor_0dte.options_pricing import find_strike_for_delta
    strike = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, target_delta=0.15, option_type="call")
    assert strike > SPY, f"15-delta call strike {strike:.2f} should be above spot {SPY}"


def test_find_put_strike_is_otm():
    from iron_condor_0dte.options_pricing import find_strike_for_delta
    strike = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, target_delta=0.15, option_type="put")
    assert strike < SPY, f"15-delta put strike {strike:.2f} should be below spot {SPY}"


def test_iron_condor_credit_positive():
    from iron_condor_0dte.options_pricing import find_strike_for_delta, iron_condor_credit
    sc = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, 0.15, "call")
    sp = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, 0.15, "put")
    credit = iron_condor_credit(SPY, sc, sc + 2, sp, sp - 2, T_0DTE, R, SIGMA)
    assert credit > 0, f"Credit should be positive, got {credit:.4f}"


def test_iron_condor_credit_less_than_wing_width():
    from iron_condor_0dte.options_pricing import find_strike_for_delta, iron_condor_credit
    sc = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, 0.15, "call")
    sp = find_strike_for_delta(SPY, T_0DTE, R, SIGMA, 0.15, "put")
    wing = 2.0
    credit = iron_condor_credit(SPY, sc, sc + wing, sp, sp - wing, T_0DTE, R, SIGMA)
    assert credit < wing, "Max credit cannot exceed wing width"


def test_expiry_at_zero_time():
    """At expiry, option value is intrinsic only."""
    from iron_condor_0dte.options_pricing import bs_price
    price_itm  = bs_price(SPY, K=560, T=1e-9, r=R, sigma=SIGMA, option_type="call")
    price_otm  = bs_price(SPY, K=580, T=1e-9, r=R, sigma=SIGMA, option_type="call")
    assert price_itm == pytest.approx(SPY - 560, abs=0.01)
    assert price_otm == pytest.approx(0.0, abs=0.01)
