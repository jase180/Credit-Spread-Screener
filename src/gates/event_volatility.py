"""
RULE 4: Event & Volatility Gate

Purpose: Avoid binary events and expanding volatility environments.

Logic:
PASS if ALL are true:
- No earnings inside trade duration (30-45 DTE)
- IV Rank between 20 and 60 (moderate IV, not extreme)
- IV 5-day change ≤ +5% (IV not spiking)
- Down-day volume ≤ 20-day average volume (no panic selling)

Why this matters:
Put credit spreads rely on theta decay in stable environments.
- Earnings create binary risk (gap through your strike)
- Low IV = not enough premium
- High IV = imminent crash or event
- Expanding IV = trouble brewing
- High volume on down days = institutions exiting

This gate prevents selling premium into deteriorating conditions.
"""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from src.utils.data_helpers import calculate_pct_change


class EventVolatilityGate:
    """Evaluates whether event risk and volatility conditions are favorable."""

    def __init__(
        self,
        min_iv_rank: float = 20.0,
        max_iv_rank: float = 60.0,
        max_iv_change: float = 5.0,
        trade_duration_days: int = 45
    ):
        """
        Initialize the Event & Volatility Gate.

        Args:
            min_iv_rank: Minimum acceptable IV Rank (default 20)
            max_iv_rank: Maximum acceptable IV Rank (default 60)
            max_iv_change: Maximum acceptable 5-day IV % change (default 5%)
            trade_duration_days: Expected trade duration in days (default 45)
        """
        self.min_iv_rank = min_iv_rank
        self.max_iv_rank = max_iv_rank
        self.max_iv_change = max_iv_change
        self.trade_duration_days = trade_duration_days

    def evaluate(
        self,
        stock_data: pd.DataFrame,
        ticker: str,
        iv_rank: Optional[float] = None,
        iv_series: Optional[pd.Series] = None,
        earnings_date: Optional[datetime] = None,
        current_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Evaluate event and volatility conditions for a stock.

        Args:
            stock_data: DataFrame with stock OHLC data (must have 'Close', 'Volume' columns)
            ticker: Stock ticker symbol
            iv_rank: Current IV Rank (0-100). If None, this check is skipped.
            iv_series: Time series of IV values. If None, IV change check is skipped.
            earnings_date: Next earnings date. If None, earnings check is skipped.
            current_date: Current date for earnings calculation. If None, uses last date in stock_data.

        Returns:
            Dictionary containing:
                - pass: Boolean indicating if the gate passed
                - details: Dict with individual check results
                - reason: String explaining failure (if failed)
        """
        # Default current date to last date in data
        if current_date is None:
            current_date = stock_data.index[-1] if isinstance(stock_data.index, pd.DatetimeIndex) else datetime.now()

        # Check 1: No earnings inside trade duration
        no_earnings_conflict = True
        days_to_earnings = None

        if earnings_date is not None:
            days_to_earnings = (earnings_date - current_date).days
            # Earnings should be outside the trade window
            no_earnings_conflict = days_to_earnings > self.trade_duration_days or days_to_earnings < 0

        # Check 2: IV Rank between min and max
        iv_in_range = True
        if iv_rank is not None:
            iv_in_range = self.min_iv_rank <= iv_rank <= self.max_iv_rank

        # Check 3: IV 5-day change ≤ max_iv_change
        iv_stable = True
        iv_change = None
        if iv_series is not None and len(iv_series) >= 6:
            iv_change = calculate_pct_change(iv_series, period=5)
            iv_stable = iv_change <= self.max_iv_change

        # Check 4: Down-day volume ≤ 20-day average volume
        # Identify if today is a down day
        is_down_day = False
        volume_acceptable = True

        if len(stock_data) >= 2:
            close_today = stock_data['Close'].iloc[-1]
            close_yesterday = stock_data['Close'].iloc[-2]
            is_down_day = close_today < close_yesterday

            if is_down_day and len(stock_data) >= 21:
                volume_today = stock_data['Volume'].iloc[-1]
                avg_volume_20d = stock_data['Volume'].iloc[-21:-1].mean()
                volume_acceptable = volume_today <= avg_volume_20d
            else:
                # If not a down day, this check passes
                volume_acceptable = True

        # All checks must pass
        passed = no_earnings_conflict and iv_in_range and iv_stable and volume_acceptable

        # Build detailed response
        details = {
            'ticker': ticker,
            'earnings_date': earnings_date,
            'days_to_earnings': days_to_earnings,
            'no_earnings_conflict': no_earnings_conflict,
            'iv_rank': iv_rank,
            'iv_in_range': iv_in_range,
            'iv_change_5d': iv_change,
            'iv_stable': iv_stable,
            'is_down_day': is_down_day,
            'volume_acceptable': volume_acceptable,
        }

        if len(stock_data) >= 21:
            details['volume_today'] = stock_data['Volume'].iloc[-1]
            details['avg_volume_20d'] = stock_data['Volume'].iloc[-21:-1].mean()

        # Determine failure reason
        reason = None
        if not passed:
            reasons = []

            if not no_earnings_conflict:
                reasons.append(
                    f"Earnings in {days_to_earnings} days (inside {self.trade_duration_days}-day window)"
                )

            if not iv_in_range:
                if iv_rank is not None:
                    if iv_rank < self.min_iv_rank:
                        reasons.append(
                            f"IV Rank too low ({iv_rank:.1f} < {self.min_iv_rank})"
                        )
                    else:
                        reasons.append(
                            f"IV Rank too high ({iv_rank:.1f} > {self.max_iv_rank})"
                        )

            if not iv_stable:
                reasons.append(
                    f"IV expanding (+{iv_change:.1f}% in 5 days)"
                )

            if not volume_acceptable:
                if 'volume_today' in details:
                    reasons.append(
                        f"High volume on down day ({details['volume_today']:,.0f} vs {details['avg_volume_20d']:,.0f} avg)"
                    )

            reason = "; ".join(reasons)

        return {
            'pass': passed,
            'details': details,
            'reason': reason,
            'gate': 'EVENT_VOLATILITY'
        }

    def is_iv_favorable(self, iv_rank: float) -> bool:
        """
        Quick check if IV Rank is in favorable range.

        Args:
            iv_rank: Current IV Rank (0-100)

        Returns:
            True if IV Rank is between min and max thresholds
        """
        return self.min_iv_rank <= iv_rank <= self.max_iv_rank
