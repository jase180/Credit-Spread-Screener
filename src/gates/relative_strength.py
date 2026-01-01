"""
RULE 2: Relative Strength Gate

Purpose: Identify stocks that outperform SPY (relative strength).

Logic:
- Stock 30-day return > SPY 30-day return (outperformance)
- Stock close > stock 50-day SMA (stock in uptrend)
- Stock 50-day SMA slope ≥ 0 (SMA rising)

Why this matters:
This is NOT momentum chasing. The goal is to find stocks that:
- Decline slower than SPY during pullbacks
- Recover faster than SPY during bounces
- Show institutional support (buying the dips)

These stocks have better odds of defending strike prices during volatility.
Put sellers want stocks that act as safe havens, not lottery tickets.
"""

import pandas as pd
from typing import Dict, Any
from src.utils.data_helpers import (
    calculate_sma,
    calculate_sma_slope,
    calculate_return
)


class RelativeStrengthGate:
    """Evaluates whether a stock shows relative strength vs SPY."""

    def __init__(
        self,
        return_period: int = 30,
        sma_period: int = 50
    ):
        """
        Initialize the Relative Strength Gate.

        Args:
            return_period: Period for return comparison (default 30)
            sma_period: Period for SMA calculation (default 50)
        """
        self.return_period = return_period
        self.sma_period = sma_period

    def evaluate(
        self,
        stock_data: pd.DataFrame,
        spy_data: pd.DataFrame,
        ticker: str
    ) -> Dict[str, Any]:
        """
        Evaluate relative strength for a stock.

        Args:
            stock_data: DataFrame with stock OHLC data (must have 'Close' column)
            spy_data: DataFrame with SPY OHLC data (must have 'Close' column)
            ticker: Stock ticker symbol

        Returns:
            Dictionary containing:
                - pass: Boolean indicating if the gate passed
                - details: Dict with individual check results
                - reason: String explaining failure (if failed)
        """
        # Calculate returns
        stock_return = calculate_return(stock_data['Close'], self.return_period)
        spy_return = calculate_return(spy_data['Close'], self.return_period)

        # Check 1: Stock 30-day return > SPY 30-day return
        outperforms_spy = stock_return > spy_return

        # Calculate stock 50-day SMA
        stock_sma_50 = calculate_sma(stock_data['Close'], self.sma_period)
        stock_close = stock_data['Close'].iloc[-1]
        stock_sma_current = stock_sma_50.iloc[-1]

        # Check 2: Stock close > stock 50-day SMA
        above_sma = stock_close > stock_sma_current

        # Check 3: Stock 50-day SMA slope ≥ 0
        sma_slope = calculate_sma_slope(stock_sma_50, lookback=1)
        sma_rising = sma_slope >= 0

        # All checks must pass
        passed = outperforms_spy and above_sma and sma_rising

        # Build detailed response
        details = {
            'ticker': ticker,
            'stock_return_30d': stock_return,
            'spy_return_30d': spy_return,
            'relative_strength': stock_return - spy_return,
            'outperforms_spy': outperforms_spy,
            'stock_close': stock_close,
            'stock_sma_50': stock_sma_current,
            'above_sma': above_sma,
            'sma_slope': sma_slope,
            'sma_rising': sma_rising,
        }

        # Determine failure reason
        reason = None
        if not passed:
            reasons = []
            if not outperforms_spy:
                reasons.append(
                    f"Underperforming SPY ({stock_return:.1f}% vs {spy_return:.1f}%)"
                )
            if not above_sma:
                reasons.append(
                    f"Below 50-SMA ({stock_close:.2f} < {stock_sma_current:.2f})"
                )
            if not sma_rising:
                reasons.append(f"50-SMA falling (slope: {sma_slope:.2f})")

            reason = "; ".join(reasons)

        return {
            'pass': passed,
            'details': details,
            'reason': reason,
            'gate': 'RELATIVE_STRENGTH'
        }

    def calculate_relative_strength_score(
        self,
        stock_data: pd.DataFrame,
        spy_data: pd.DataFrame
    ) -> float:
        """
        Calculate a simple relative strength score.

        Args:
            stock_data: DataFrame with stock OHLC data
            spy_data: DataFrame with SPY OHLC data

        Returns:
            Relative strength score (stock return - SPY return)
        """
        stock_return = calculate_return(stock_data['Close'], self.return_period)
        spy_return = calculate_return(spy_data['Close'], self.return_period)

        return stock_return - spy_return
