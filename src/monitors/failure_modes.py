"""
Failure Mode Detection System

Purpose: Continuously monitor for conditions that signal the system should
stop trading or reduce risk exposure.

This is the "kill switch" that prevents trading in negative expectancy environments.

FAILURE MODE 1: REGIME TRANSITION
- SPY breaks down (closes below 50-SMA, SMA turns down, or makes lower low)
- VIX spikes > +15% in 5 days
Action: Disable new entries, flag RISK-OFF

FAILURE MODE 2: RELATIVE STRENGTH BREAKDOWN
- Stock's 10-day return falls below SPY
- AND stock closes below its 50-SMA
Action: Remove ticker from candidates

FAILURE MODE 3: CORRELATED BREAKDOWN
- More than 40% of screened stocks fall below their 50-SMA
Action: Reduce global risk (institutional liquidation)

FAILURE MODE 4: VOLATILITY EXPANSION
- VIX > VIX 20-day SMA
- AND SPY red days show increasing volume
Action: Warn that theta decay is unreliable
"""

import pandas as pd
from typing import Dict, Any, List
from enum import Enum
from src.utils.data_helpers import (
    calculate_sma,
    calculate_sma_slope,
    has_lower_low,
    calculate_pct_change,
    calculate_return
)


class FailureMode(Enum):
    """Enumeration of failure modes."""
    REGIME_TRANSITION = "REGIME_TRANSITION"
    RELATIVE_STRENGTH_BREAKDOWN = "RELATIVE_STRENGTH_BREAKDOWN"
    CORRELATED_BREAKDOWN = "CORRELATED_BREAKDOWN"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"


class FailureModeDetector:
    """Detects and reports system failure modes."""

    def __init__(
        self,
        correlated_breakdown_threshold: float = 0.40,
        vix_spike_threshold: float = 15.0
    ):
        """
        Initialize the Failure Mode Detector.

        Args:
            correlated_breakdown_threshold: % of stocks below 50-SMA to trigger alert (default 0.40)
            vix_spike_threshold: VIX % change threshold for regime transition (default 15%)
        """
        self.correlated_breakdown_threshold = correlated_breakdown_threshold
        self.vix_spike_threshold = vix_spike_threshold

    def check_regime_transition(
        self,
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Check for FAILURE MODE 1: Regime Transition.

        Args:
            spy_data: DataFrame with SPY OHLC data
            vix_data: DataFrame with VIX data

        Returns:
            Dictionary with failure mode status and details
        """
        # Calculate SPY metrics
        spy_sma_50 = calculate_sma(spy_data['Close'], 50)
        spy_close = float(spy_data['Close'].iloc[-1])
        spy_sma_current = float(spy_sma_50.iloc[-1])

        # Trigger conditions
        below_sma = spy_close < spy_sma_current
        sma_slope = calculate_sma_slope(spy_sma_50, lookback=1)
        sma_falling = sma_slope < 0
        made_lower_low = has_lower_low(spy_data['Low'], lookback=20)
        vix_change = calculate_pct_change(vix_data['Close'], period=5)
        vix_spiking = vix_change > self.vix_spike_threshold

        # Failure triggered if ANY condition is true
        triggered = below_sma or sma_falling or made_lower_low or vix_spiking

        details = {
            'spy_close': spy_close,
            'spy_sma_50': spy_sma_current,
            'below_sma': below_sma,
            'sma_slope': sma_slope,
            'sma_falling': sma_falling,
            'made_lower_low': made_lower_low,
            'vix_change_5d': vix_change,
            'vix_spiking': vix_spiking,
        }

        message = None
        if triggered:
            triggers = []
            if below_sma:
                triggers.append(f"SPY below 50-SMA ({spy_close:.2f} < {spy_sma_current:.2f})")
            if sma_falling:
                triggers.append(f"50-SMA turning down (slope: {sma_slope:.2f})")
            if made_lower_low:
                triggers.append("SPY made a lower low")
            if vix_spiking:
                triggers.append(f"VIX spiking (+{vix_change:.1f}% in 5 days)")

            message = "REGIME TRANSITION: " + "; ".join(triggers)

        return {
            'mode': FailureMode.REGIME_TRANSITION,
            'triggered': triggered,
            'severity': 'CRITICAL',
            'action': 'DISABLE NEW ENTRIES - RISK-OFF',
            'details': details,
            'message': message
        }

    def check_relative_strength_breakdown(
        self,
        stock_data: pd.DataFrame,
        spy_data: pd.DataFrame,
        ticker: str
    ) -> Dict[str, Any]:
        """
        Check for FAILURE MODE 2: Relative Strength Breakdown.

        Args:
            stock_data: DataFrame with stock OHLC data
            spy_data: DataFrame with SPY OHLC data
            ticker: Stock ticker symbol

        Returns:
            Dictionary with failure mode status and details
        """
        # Calculate returns
        stock_return_10d = calculate_return(stock_data['Close'], 10)
        spy_return_10d = calculate_return(spy_data['Close'], 10)

        # Check relative strength
        underperforming = stock_return_10d < spy_return_10d

        # Check if below 50-SMA
        stock_sma_50 = calculate_sma(stock_data['Close'], 50)
        stock_close = float(stock_data['Close'].iloc[-1])
        stock_sma_current = float(stock_sma_50.iloc[-1])
        below_sma = stock_close < stock_sma_current

        # Both conditions must be true
        triggered = underperforming and below_sma

        details = {
            'ticker': ticker,
            'stock_return_10d': stock_return_10d,
            'spy_return_10d': spy_return_10d,
            'underperforming': underperforming,
            'stock_close': stock_close,
            'stock_sma_50': stock_sma_current,
            'below_sma': below_sma,
        }

        message = None
        if triggered:
            message = (
                f"RS BREAKDOWN: {ticker} underperforming SPY "
                f"({stock_return_10d:.1f}% vs {spy_return_10d:.1f}%) "
                f"and below 50-SMA ({stock_close:.2f} < {stock_sma_current:.2f})"
            )

        return {
            'mode': FailureMode.RELATIVE_STRENGTH_BREAKDOWN,
            'triggered': triggered,
            'severity': 'WARNING',
            'action': f'REMOVE {ticker} FROM CANDIDATES',
            'details': details,
            'message': message
        }

    def check_correlated_breakdown(
        self,
        stock_data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Check for FAILURE MODE 3: Correlated Breakdown.

        Args:
            stock_data_dict: Dictionary mapping tickers to their OHLC DataFrames

        Returns:
            Dictionary with failure mode status and details
        """
        if not stock_data_dict:
            return {
                'mode': FailureMode.CORRELATED_BREAKDOWN,
                'triggered': False,
                'severity': 'HIGH',
                'action': 'REDUCE GLOBAL RISK',
                'details': {},
                'message': None
            }

        # Count how many stocks are below their 50-SMA
        total_stocks = len(stock_data_dict)
        stocks_below_sma = 0
        breakdown_tickers = []

        for ticker, stock_data in stock_data_dict.items():
            if len(stock_data) < 50:
                continue

            stock_sma_50 = calculate_sma(stock_data['Close'], 50)
            stock_close = float(stock_data['Close'].iloc[-1])
            stock_sma_current = float(stock_sma_50.iloc[-1])

            if stock_close < stock_sma_current:
                stocks_below_sma += 1
                breakdown_tickers.append(ticker)

        breakdown_pct = stocks_below_sma / total_stocks if total_stocks > 0 else 0
        triggered = breakdown_pct > self.correlated_breakdown_threshold

        details = {
            'total_stocks': total_stocks,
            'stocks_below_sma': stocks_below_sma,
            'breakdown_pct': breakdown_pct * 100,
            'threshold_pct': self.correlated_breakdown_threshold * 100,
            'breakdown_tickers': breakdown_tickers,
        }

        message = None
        if triggered:
            message = (
                f"CORRELATED BREAKDOWN: {stocks_below_sma}/{total_stocks} stocks "
                f"({breakdown_pct*100:.1f}%) below 50-SMA "
                f"(threshold: {self.correlated_breakdown_threshold*100:.0f}%)"
            )

        return {
            'mode': FailureMode.CORRELATED_BREAKDOWN,
            'triggered': triggered,
            'severity': 'HIGH',
            'action': 'REDUCE GLOBAL RISK - INSTITUTIONAL LIQUIDATION DETECTED',
            'details': details,
            'message': message
        }

    def check_volatility_expansion(
        self,
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Check for FAILURE MODE 4: Volatility Expansion.

        Args:
            spy_data: DataFrame with SPY OHLC data
            vix_data: DataFrame with VIX data

        Returns:
            Dictionary with failure mode status and details
        """
        # Check if VIX is above its 20-day SMA
        vix_sma_20 = calculate_sma(vix_data['Close'], 20)
        vix_close = float(vix_data['Close'].iloc[-1])
        vix_sma_current = float(vix_sma_20.iloc[-1])
        vix_elevated = vix_close > vix_sma_current

        # Check if SPY red days show increasing volume
        # Look at the last 5 red days
        red_days_volume_increasing = False

        if len(spy_data) >= 10:
            # Find recent red days
            red_days = spy_data[spy_data['Close'] < spy_data['Close'].shift(1)].tail(5)

            if len(red_days) >= 2:
                # Check if volume is trending up on red days
                volumes = red_days['Volume'].values
                if len(volumes) >= 2:
                    recent_avg = volumes[-2:].mean()
                    earlier_avg = volumes[:-2].mean() if len(volumes) > 2 else volumes[0]
                    red_days_volume_increasing = recent_avg > earlier_avg

        # Both conditions must be true
        triggered = vix_elevated and red_days_volume_increasing

        details = {
            'vix_close': vix_close,
            'vix_sma_20': vix_sma_current,
            'vix_elevated': vix_elevated,
            'red_days_volume_increasing': red_days_volume_increasing,
        }

        message = None
        if triggered:
            message = (
                f"VOLATILITY EXPANSION: VIX elevated ({vix_close:.2f} > {vix_sma_current:.2f}) "
                f"with increasing volume on SPY red days"
            )

        return {
            'mode': FailureMode.VOLATILITY_EXPANSION,
            'triggered': triggered,
            'severity': 'WARNING',
            'action': 'WARN - THETA DECAY UNRELIABLE',
            'details': details,
            'message': message
        }

    def run_all_checks(
        self,
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame,
        stock_data_dict: Dict[str, pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Run all failure mode checks.

        Args:
            spy_data: DataFrame with SPY OHLC data
            vix_data: DataFrame with VIX data
            stock_data_dict: Optional dict mapping tickers to OHLC DataFrames

        Returns:
            Dictionary with all failure mode results
        """
        results = {
            'regime_transition': self.check_regime_transition(spy_data, vix_data),
            'volatility_expansion': self.check_volatility_expansion(spy_data, vix_data),
        }

        if stock_data_dict:
            results['correlated_breakdown'] = self.check_correlated_breakdown(stock_data_dict)

        # Determine overall system state
        any_critical = results['regime_transition']['triggered']
        any_high = stock_data_dict and results.get('correlated_breakdown', {}).get('triggered', False)

        if any_critical:
            system_state = 'RISK-OFF'
        elif any_high:
            system_state = 'REDUCED-RISK'
        else:
            system_state = 'RISK-ON'

        # Collect all triggered alerts
        alerts = []
        for check_name, result in results.items():
            if result['triggered']:
                alerts.append({
                    'check': check_name,
                    'severity': result['severity'],
                    'action': result['action'],
                    'message': result['message']
                })

        return {
            'system_state': system_state,
            'checks': results,
            'alerts': alerts,
            'allow_new_trades': system_state == 'RISK-ON'
        }
