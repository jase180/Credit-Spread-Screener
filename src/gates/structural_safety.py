"""
RULE 3: Structural Safety Gate

Purpose: Ensure the hypothetical short put strike is below key support zones.

Logic:
A hypothetical short put strike must be below ALL of:
- Stock 50-day SMA
- Most recent higher low (swing low in uptrend)
- Prior daily consolidation base low

Optional safety filter:
- Strike distance ≥ 1.5 × ATR(14)

Why this matters:
Price has memory. Stocks tend to defend levels that previously acted as support.
This gate ensures we're selling puts below areas where:
- Institutions have shown willingness to buy
- Previous breakouts occurred
- Moving averages provide dynamic support

The goal is NOT to time entries, but to avoid strikes that sit in
"no man's land" with no structural support below them.
"""

import pandas as pd
from typing import Dict, Any, Optional
from src.utils.data_helpers import (
    calculate_sma,
    calculate_atr,
    find_most_recent_higher_low,
    find_consolidation_base
)


class StructuralSafetyGate:
    """Evaluates whether strike placement has structural support."""

    def __init__(
        self,
        sma_period: int = 50,
        atr_period: int = 14,
        atr_multiplier: float = 1.5,
        use_atr_filter: bool = True
    ):
        """
        Initialize the Structural Safety Gate.

        Args:
            sma_period: Period for SMA calculation (default 50)
            atr_period: Period for ATR calculation (default 14)
            atr_multiplier: ATR multiplier for distance check (default 1.5)
            use_atr_filter: Whether to enforce ATR distance check (default True)
        """
        self.sma_period = sma_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.use_atr_filter = use_atr_filter

    def evaluate(
        self,
        stock_data: pd.DataFrame,
        ticker: str,
        hypothetical_strike: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluate structural safety for a stock.

        Args:
            stock_data: DataFrame with stock OHLC data (must have 'Close', 'High', 'Low' columns)
            ticker: Stock ticker symbol
            hypothetical_strike: Proposed short put strike price.
                               If None, will calculate suggested strike zone.

        Returns:
            Dictionary containing:
                - pass: Boolean indicating if the gate passed
                - details: Dict with support levels and checks
                - reason: String explaining failure (if failed)
                - suggested_strike_max: Maximum safe strike price
        """
        # Calculate support levels
        stock_close = stock_data['Close'].iloc[-1]

        # Level 1: 50-day SMA
        stock_sma_50 = calculate_sma(stock_data['Close'], self.sma_period)
        sma_level = stock_sma_50.iloc[-1]

        # Level 2: Most recent higher low
        higher_low_level = find_most_recent_higher_low(stock_data['Low'], lookback=60)

        # Level 3: Consolidation base
        consolidation_level = find_consolidation_base(stock_data['Low'], lookback=60)

        # Calculate ATR for distance check
        atr = calculate_atr(
            stock_data['High'],
            stock_data['Low'],
            stock_data['Close'],
            self.atr_period
        )
        current_atr = atr.iloc[-1]
        min_strike_distance = self.atr_multiplier * current_atr

        # Determine the maximum safe strike (below all support levels)
        support_levels = [sma_level]

        if higher_low_level is not None:
            support_levels.append(higher_low_level)

        if consolidation_level is not None:
            support_levels.append(consolidation_level)

        # The strike must be below the LOWEST support level
        max_safe_strike = min(support_levels)

        # If ATR filter is enabled, further restrict the strike
        if self.use_atr_filter:
            atr_restricted_strike = stock_close - min_strike_distance
            max_safe_strike = min(max_safe_strike, atr_restricted_strike)

        # If a hypothetical strike is provided, evaluate it
        if hypothetical_strike is not None:
            below_sma = hypothetical_strike < sma_level

            below_higher_low = True
            if higher_low_level is not None:
                below_higher_low = hypothetical_strike < higher_low_level

            below_consolidation = True
            if consolidation_level is not None:
                below_consolidation = hypothetical_strike < consolidation_level

            # ATR distance check
            strike_distance = stock_close - hypothetical_strike
            sufficient_distance = True
            if self.use_atr_filter:
                sufficient_distance = strike_distance >= min_strike_distance

            # All checks must pass
            passed = (
                below_sma and
                below_higher_low and
                below_consolidation and
                sufficient_distance
            )

            # Build detailed response
            details = {
                'ticker': ticker,
                'current_price': stock_close,
                'hypothetical_strike': hypothetical_strike,
                'sma_50_level': sma_level,
                'below_sma': below_sma,
                'higher_low_level': higher_low_level,
                'below_higher_low': below_higher_low,
                'consolidation_level': consolidation_level,
                'below_consolidation': below_consolidation,
                'atr_14': current_atr,
                'min_strike_distance': min_strike_distance,
                'strike_distance': strike_distance,
                'sufficient_distance': sufficient_distance,
                'max_safe_strike': max_safe_strike,
            }

            # Determine failure reason
            reason = None
            if not passed:
                reasons = []
                if not below_sma:
                    reasons.append(
                        f"Strike above 50-SMA ({hypothetical_strike:.2f} >= {sma_level:.2f})"
                    )
                if not below_higher_low and higher_low_level is not None:
                    reasons.append(
                        f"Strike above higher low ({hypothetical_strike:.2f} >= {higher_low_level:.2f})"
                    )
                if not below_consolidation and consolidation_level is not None:
                    reasons.append(
                        f"Strike above consolidation ({hypothetical_strike:.2f} >= {consolidation_level:.2f})"
                    )
                if not sufficient_distance:
                    reasons.append(
                        f"Insufficient distance ({strike_distance:.2f} < {min_strike_distance:.2f})"
                    )

                reason = "; ".join(reasons)

        else:
            # No hypothetical strike provided - just return the safe zone
            passed = True
            details = {
                'ticker': ticker,
                'current_price': stock_close,
                'sma_50_level': sma_level,
                'higher_low_level': higher_low_level,
                'consolidation_level': consolidation_level,
                'atr_14': current_atr,
                'min_strike_distance': min_strike_distance,
                'max_safe_strike': max_safe_strike,
            }
            reason = None

        return {
            'pass': passed,
            'details': details,
            'reason': reason,
            'suggested_strike_max': max_safe_strike,
            'gate': 'STRUCTURAL_SAFETY'
        }

    def suggest_strike_range(self, stock_data: pd.DataFrame) -> Dict[str, float]:
        """
        Suggest a safe strike range for a stock.

        Args:
            stock_data: DataFrame with stock OHLC data

        Returns:
            Dictionary with 'max_strike' and 'current_price'
        """
        result = self.evaluate(stock_data, ticker='', hypothetical_strike=None)

        return {
            'current_price': result['details']['current_price'],
            'max_safe_strike': result['suggested_strike_max'],
            'discount_pct': (
                (result['details']['current_price'] - result['suggested_strike_max'])
                / result['details']['current_price'] * 100
            )
        }
