"""
RULE 1: Market Regime Gate

Purpose: Determine if SPY is in a healthy bullish regime suitable for put credit spreads.

Logic:
- SPY must be above its 50-day SMA (uptrend)
- 50-day SMA must be rising (positive slope)
- No lower low in the last 20 days (no breakdown pattern)
- VIX 5-day change ≤ +10% (volatility not spiking)

Why this matters:
Put credit spreads profit from theta decay in stable/rising markets.
When SPY breaks down, correlations spike and protective puts fail.
This gate prevents trading in negative expectancy environments.
"""

import pandas as pd
from typing import Dict, Any
from src.utils.data_helpers import (
    calculate_sma,
    calculate_sma_slope,
    has_lower_low,
    calculate_pct_change
)


class MarketRegimeGate:
    """Evaluates whether the market regime supports put credit spreads."""

    def __init__(self, sma_period: int = 50, lower_low_lookback: int = 20):
        """
        Initialize the Market Regime Gate.

        Args:
            sma_period: Period for SPY SMA calculation (default 50)
            lower_low_lookback: Days to check for lower low (default 20)
        """
        self.sma_period = sma_period
        self.lower_low_lookback = lower_low_lookback

    def evaluate(
        self,
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Evaluate the market regime.

        Args:
            spy_data: DataFrame with SPY OHLC data (must have 'Close', 'Low' columns)
            vix_data: DataFrame with VIX data (must have 'Close' column)

        Returns:
            Dictionary containing:
                - pass: Boolean indicating if the gate passed
                - details: Dict with individual check results
                - reason: String explaining failure (if failed)
        """
        # Calculate SPY 50-day SMA
        spy_sma_50 = calculate_sma(spy_data['Close'], self.sma_period)

        # Get current values
        spy_close = spy_data['Close'].iloc[-1]
        spy_sma_current = spy_sma_50.iloc[-1]

        # Check 1: SPY close > 50-day SMA
        above_sma = spy_close > spy_sma_current

        # Check 2: 50-day SMA slope ≥ 0
        sma_slope = calculate_sma_slope(spy_sma_50, lookback=1)
        sma_rising = sma_slope >= 0

        # Check 3: No lower low in the last 20 trading days
        no_lower_low = not has_lower_low(spy_data['Low'], self.lower_low_lookback)

        # Check 4: VIX 5-day % change ≤ +10%
        vix_change = calculate_pct_change(vix_data['Close'], period=5)
        vix_stable = vix_change <= 10.0

        # All checks must pass
        passed = above_sma and sma_rising and no_lower_low and vix_stable

        # Build detailed response
        details = {
            'spy_close': spy_close,
            'spy_sma_50': spy_sma_current,
            'above_sma': above_sma,
            'sma_slope': sma_slope,
            'sma_rising': sma_rising,
            'has_lower_low': not no_lower_low,
            'no_lower_low': no_lower_low,
            'vix_change_5d': vix_change,
            'vix_stable': vix_stable,
        }

        # Determine failure reason
        reason = None
        if not passed:
            reasons = []
            if not above_sma:
                reasons.append(f"SPY below 50-SMA ({spy_close:.2f} < {spy_sma_current:.2f})")
            if not sma_rising:
                reasons.append(f"50-SMA falling (slope: {sma_slope:.2f})")
            if not no_lower_low:
                reasons.append("Lower low detected in last 20 days")
            if not vix_stable:
                reasons.append(f"VIX spiking (+{vix_change:.1f}% in 5 days)")

            reason = "; ".join(reasons)

        return {
            'pass': passed,
            'details': details,
            'reason': reason,
            'gate': 'MARKET_REGIME'
        }

    def get_market_state(self, spy_data: pd.DataFrame, vix_data: pd.DataFrame) -> str:
        """
        Get a simple market state label.

        Args:
            spy_data: DataFrame with SPY OHLC data
            vix_data: DataFrame with VIX data

        Returns:
            'RISK-ON' if regime is healthy, 'RISK-OFF' if not
        """
        result = self.evaluate(spy_data, vix_data)
        return 'RISK-ON' if result['pass'] else 'RISK-OFF'
