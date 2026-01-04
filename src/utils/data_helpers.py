"""
Data helper utilities for the credit spread screener.
Handles data fetching and common technical calculations.
"""

import pandas as pd
import numpy as np
from typing import Optional


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average.

    Args:
        prices: Price series
        period: SMA period

    Returns:
        SMA series
    """
    return prices.rolling(window=period).mean()


def calculate_sma_slope(sma: pd.Series, lookback: int = 1) -> float:
    """
    Calculate the slope of an SMA.

    Args:
        sma: SMA series
        lookback: Number of periods to look back for slope calculation

    Returns:
        Slope value (positive = upward, negative = downward)
    """
    if len(sma) < lookback + 1:
        return 0.0

    current = float(sma.iloc[-1])
    previous = float(sma.iloc[-(lookback + 1)])

    return current - previous


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range.

    Args:
        high: High price series
        low: Low price series
        close: Close price series
        period: ATR period

    Returns:
        ATR series
    """
    # True Range calculation
    h_l = high - low
    h_c = abs(high - close.shift(1))
    l_c = abs(low - close.shift(1))

    tr = pd.concat([h_l, h_c, l_c], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr


def has_lower_low(low: pd.Series, lookback: int = 20) -> bool:
    """
    Check if price made a lower low in the lookback period.

    A lower low occurs when:
    - Current low < previous swing low

    Args:
        low: Low price series
        lookback: Number of days to look back

    Returns:
        True if a lower low was made
    """
    if len(low) < lookback:
        return False

    # Convert to numpy array to avoid pandas Series comparison issues
    recent_lows = low.iloc[-lookback:].values

    # Flatten if multi-dimensional (happens with yfinance multi-ticker data)
    if recent_lows.ndim > 1:
        recent_lows = recent_lows.flatten()

    # Find local minima (lows)
    # A point is a local minimum if it's lower than neighbors
    for i in range(1, len(recent_lows) - 1):
        if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
            # This is a swing low
            # Check if there's a lower swing low before it
            for j in range(i):
                if j > 0 and recent_lows[j] < recent_lows[j-1]:
                    if j < len(recent_lows) - 1 and recent_lows[j] < recent_lows[j+1]:
                        if recent_lows[i] < recent_lows[j]:
                            return True

    return False


def calculate_return(prices: pd.Series, period: int) -> float:
    """
    Calculate percentage return over a period.

    Args:
        prices: Price series
        period: Number of periods

    Returns:
        Percentage return
    """
    if len(prices) < period + 1:
        return 0.0

    current = float(prices.iloc[-1])
    previous = float(prices.iloc[-(period + 1)])

    return ((current - previous) / previous) * 100


def calculate_pct_change(series: pd.Series, period: int = 5) -> float:
    """
    Calculate percentage change over a period.

    Args:
        series: Data series
        period: Number of periods

    Returns:
        Percentage change
    """
    if len(series) < period + 1:
        return 0.0

    current = float(series.iloc[-1])
    previous = float(series.iloc[-(period + 1)])

    if previous == 0:
        return 0.0

    return ((current - previous) / previous) * 100


def find_most_recent_higher_low(low: pd.Series, lookback: int = 60) -> Optional[float]:
    """
    Find the most recent higher low (swing low in an uptrend).

    A higher low is a local minimum that is higher than the previous local minimum.
    This represents a defended price level in an uptrend.

    Args:
        low: Low price series
        lookback: Number of days to look back

    Returns:
        Price level of the most recent higher low, or None if not found
    """
    if len(low) < 5:
        return None

    # Convert to numpy array to avoid pandas Series comparison issues
    recent_lows_series = low.iloc[-lookback:] if len(low) >= lookback else low
    recent_lows = recent_lows_series.values

    # Flatten if multi-dimensional (happens with yfinance multi-ticker data)
    if recent_lows.ndim > 1:
        recent_lows = recent_lows.flatten()

    # Find local minima
    swing_lows = []
    for i in range(1, len(recent_lows) - 1):
        if recent_lows[i] <= recent_lows[i-1] and recent_lows[i] <= recent_lows[i+1]:
            swing_lows.append((i, float(recent_lows[i])))

    if len(swing_lows) < 2:
        return None

    # Find the most recent higher low
    for i in range(len(swing_lows) - 1, 0, -1):
        if swing_lows[i][1] > swing_lows[i-1][1]:
            return float(swing_lows[i][1])

    return None


def find_consolidation_base(low: pd.Series, lookback: int = 60, tolerance: float = 0.02) -> Optional[float]:
    """
    Find the most recent consolidation base low.

    A consolidation base is a price range where the stock traded sideways
    before breaking out. The low of this range represents support.

    Args:
        low: Low price series
        lookback: Number of days to look back
        tolerance: Price tolerance for consolidation (2% default)

    Returns:
        Price level of the consolidation base low, or None if not found
    """
    if len(low) < 10:
        return None

    # Convert to numpy array to avoid pandas Series comparison issues
    recent_lows_series = low.iloc[-lookback:] if len(low) >= lookback else low
    recent_lows = recent_lows_series.values

    # Flatten if multi-dimensional (happens with yfinance multi-ticker data)
    if recent_lows.ndim > 1:
        recent_lows = recent_lows.flatten()

    # Look for periods where price stayed within a tight range
    # A consolidation is defined as 5+ consecutive days within tolerance range
    min_consolidation_days = 5

    for i in range(len(recent_lows) - min_consolidation_days, 0, -1):
        window = recent_lows[i:i+min_consolidation_days]
        range_pct = (window.max() - window.min()) / window.min()

        if range_pct <= tolerance:
            # Found a consolidation
            return float(window.min())

    return None
