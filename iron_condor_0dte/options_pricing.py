"""
Black-Scholes option pricing utilities for 0DTE Iron Condor simulation.
"""
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq


def bs_price(S: float, K: float, T: float, r: float, sigma: float,
             option_type: str = "call") -> float:
    """Black-Scholes option price. T in years."""
    if T <= 1e-8:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_delta(S: float, K: float, T: float, r: float, sigma: float,
             option_type: str = "call") -> float:
    """Black-Scholes delta."""
    if T <= 1e-8:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return norm.cdf(d1) if option_type == "call" else norm.cdf(d1) - 1.0


def find_strike_for_delta(S: float, T: float, r: float, sigma: float,
                          target_delta: float, option_type: str = "call") -> float:
    """
    Find the strike that produces |delta| == target_delta.
    Returns the nearest $0.50 increment (SPY strikes).
    """
    target = abs(target_delta)

    if option_type == "call":
        lo, hi = S * 1.0001, S * 1.6
        try:
            K = brentq(
                lambda k: abs(bs_delta(S, k, T, r, sigma, "call")) - target,
                lo, hi, xtol=1e-4
            )
        except ValueError:
            K = S * (1 + 1.5 * sigma * np.sqrt(T))
    else:
        lo, hi = S * 0.4, S * 0.9999
        try:
            K = brentq(
                lambda k: abs(bs_delta(S, k, T, r, sigma, "put")) - target,
                lo, hi, xtol=1e-4
            )
        except ValueError:
            K = S * (1 - 1.5 * sigma * np.sqrt(T))

    # Round to nearest $0.50 (SPY strike convention)
    return round(K * 2) / 2


def spread_credit(S: float, short_K: float, long_K: float,
                  T: float, r: float, sigma: float,
                  spread_type: str = "call") -> float:
    """Net credit received for a vertical spread (sell short, buy long)."""
    return (bs_price(S, short_K, T, r, sigma, spread_type) -
            bs_price(S, long_K, T, r, sigma, spread_type))


def iron_condor_credit(S: float,
                       short_call: float, long_call: float,
                       short_put: float, long_put: float,
                       T: float, r: float, sigma: float) -> float:
    """Total net credit for the iron condor."""
    return (spread_credit(S, short_call, long_call, T, r, sigma, "call") +
            spread_credit(S, short_put, long_put, T, r, sigma, "put"))


def iron_condor_cost_to_close(S: float,
                               short_call: float, long_call: float,
                               short_put: float, long_put: float,
                               T: float, r: float, sigma: float) -> float:
    """Current cost to close (buy back) the iron condor."""
    call_side = (bs_price(S, short_call, T, r, sigma, "call") -
                 bs_price(S, long_call, T, r, sigma, "call"))
    put_side = (bs_price(S, short_put, T, r, sigma, "put") -
                bs_price(S, long_put, T, r, sigma, "put"))
    return call_side + put_side


def trading_hours_remaining(entry_hour: int = 10, entry_min: int = 15) -> float:
    """
    Fraction-of-year T for Black-Scholes at a given entry time ET.
    Market closes at 4:00 PM; options effectively expire at close.
    """
    market_open_hr = 9.5          # 9:30 AM
    market_close_hr = 16.0        # 4:00 PM
    total_trading_hours = market_close_hr - market_open_hr  # 6.5 h

    entry_decimal = entry_hour + entry_min / 60.0
    hours_left = market_close_hr - entry_decimal
    trading_days_left = hours_left / total_trading_hours   # fraction of a day
    return trading_days_left / 252                         # fraction of a year
