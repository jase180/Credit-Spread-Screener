"""
Credit Spread Screener - Main Orchestrator

This module coordinates all four gates and failure mode detection
to produce a final list of qualified tickers for put credit spreads.

Usage:
    screener = CreditSpreadScreener()
    results = screener.screen(['AAPL', 'MSFT', 'GOOGL'])

    if results['allow_new_trades']:
        for candidate in results['qualified_tickers']:
            print(candidate)
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.gates import (
    MarketRegimeGate,
    RelativeStrengthGate,
    StructuralSafetyGate,
    EventVolatilityGate
)
from src.monitors import FailureModeDetector


class CreditSpreadScreener:
    """
    Main screening system for put credit spread candidates.

    Coordinates four rule gates and continuous failure mode monitoring.
    """

    def __init__(
        self,
        enable_atr_filter: bool = True,
        correlated_breakdown_threshold: float = 0.40
    ):
        """
        Initialize the screener with all gates and monitors.

        Args:
            enable_atr_filter: Whether to enforce ATR distance check (default True)
            correlated_breakdown_threshold: Threshold for correlated breakdown alert (default 0.40)
        """
        # Initialize all gates
        self.market_regime_gate = MarketRegimeGate()
        self.relative_strength_gate = RelativeStrengthGate()
        self.structural_safety_gate = StructuralSafetyGate(use_atr_filter=enable_atr_filter)
        self.event_volatility_gate = EventVolatilityGate()

        # Initialize failure mode detector
        self.failure_detector = FailureModeDetector(
            correlated_breakdown_threshold=correlated_breakdown_threshold
        )

        # State tracking
        self.last_spy_data = None
        self.last_vix_data = None
        self.last_system_state = None

    def screen(
        self,
        tickers: List[str],
        stock_data_dict: Dict[str, pd.DataFrame],
        spy_data: pd.DataFrame,
        vix_data: pd.DataFrame,
        iv_rank_dict: Optional[Dict[str, float]] = None,
        earnings_dates_dict: Optional[Dict[str, datetime]] = None
    ) -> Dict[str, Any]:
        """
        Screen a list of tickers through all four gates.

        Args:
            tickers: List of ticker symbols to screen
            stock_data_dict: Dictionary mapping tickers to their OHLC DataFrames
            spy_data: DataFrame with SPY OHLC data
            vix_data: DataFrame with VIX data
            iv_rank_dict: Optional dict mapping tickers to IV Rank values
            earnings_dates_dict: Optional dict mapping tickers to next earnings dates

        Returns:
            Dictionary containing:
                - qualified_tickers: List of tickers that passed all gates
                - failed_tickers: Dict of tickers and why they failed
                - system_state: Current system state (RISK-ON/RISK-OFF/REDUCED-RISK)
                - allow_new_trades: Boolean indicating if new trades are allowed
                - failure_mode_alerts: List of active failure mode alerts
                - gate_results: Detailed results for each ticker
        """
        # Store latest market data for monitoring
        self.last_spy_data = spy_data
        self.last_vix_data = vix_data

        # STEP 1: Check market regime (applies to all stocks)
        regime_result = self.market_regime_gate.evaluate(spy_data, vix_data)
        regime_failed = not regime_result['pass']

        # STEP 2: Run failure mode detection
        failure_modes = self.failure_detector.run_all_checks(
            spy_data=spy_data,
            vix_data=vix_data,
            stock_data_dict=stock_data_dict
        )

        self.last_system_state = failure_modes['system_state']

        # Store whether system-level gates failed (but continue screening to show details)
        system_level_failure = regime_failed or not failure_modes['allow_new_trades']

        # STEP 3: Screen each ticker through the remaining gates
        qualified_tickers = []
        failed_tickers = {}
        gate_results = {}

        for ticker in tickers:
            # Skip if no data for this ticker
            if ticker not in stock_data_dict:
                failed_tickers[ticker] = 'No data available'
                continue

            stock_data = stock_data_dict[ticker]

            # Initialize results for this ticker
            ticker_results = {
                'ticker': ticker,
                'gates': {}
            }

            # Gate 2: Relative Strength
            rs_result = self.relative_strength_gate.evaluate(
                stock_data=stock_data,
                spy_data=spy_data,
                ticker=ticker
            )
            ticker_results['gates']['relative_strength'] = rs_result

            if not rs_result['pass']:
                failed_tickers[ticker] = f"[RS] {rs_result['reason']}"
                gate_results[ticker] = ticker_results
                continue

            # Gate 3: Structural Safety
            # (Note: Without a specific strike, this evaluates support levels)
            safety_result = self.structural_safety_gate.evaluate(
                stock_data=stock_data,
                ticker=ticker,
                hypothetical_strike=None  # Will return safe strike zone
            )
            ticker_results['gates']['structural_safety'] = safety_result

            # Structural safety always passes when no strike is provided
            # It just gives us the safe zone for reference

            # Gate 4: Event & Volatility
            iv_rank = iv_rank_dict.get(ticker) if iv_rank_dict else None
            earnings_date = earnings_dates_dict.get(ticker) if earnings_dates_dict else None

            ev_result = self.event_volatility_gate.evaluate(
                stock_data=stock_data,
                ticker=ticker,
                iv_rank=iv_rank,
                earnings_date=earnings_date
            )
            ticker_results['gates']['event_volatility'] = ev_result

            if not ev_result['pass']:
                failed_tickers[ticker] = f"[EV] {ev_result['reason']}"
                gate_results[ticker] = ticker_results
                continue

            # All gates passed!
            qualified_tickers.append(ticker)
            gate_results[ticker] = ticker_results

        # STEP 4: Final failure mode check on qualified stocks
        # Check for relative strength breakdown on qualified tickers
        rs_breakdown_alerts = []
        for ticker in qualified_tickers[:]:  # Copy list since we may modify it
            rs_check = self.failure_detector.check_relative_strength_breakdown(
                stock_data=stock_data_dict[ticker],
                spy_data=spy_data,
                ticker=ticker
            )
            if rs_check['triggered']:
                rs_breakdown_alerts.append(rs_check)
                qualified_tickers.remove(ticker)
                failed_tickers[ticker] = rs_check['message']

        # Add RS breakdown alerts to failure modes
        if rs_breakdown_alerts:
            failure_modes['alerts'].extend(rs_breakdown_alerts)

        # If system-level failure occurred, override final results
        # But preserve gate_results so user can see individual ticker details
        if system_level_failure:
            # Add system-level alerts
            system_alerts = failure_modes['alerts'].copy()
            if regime_failed:
                system_alerts.insert(0, {
                    'severity': 'CRITICAL',
                    'message': regime_result['reason']
                })

            # Mark all tickers as failed with individual gate reasons, but note system is RISK-OFF
            final_qualified = []
            final_failed = {}
            for ticker in tickers:
                if ticker in failed_tickers:
                    # Already failed individual gates - keep that reason
                    final_failed[ticker] = failed_tickers[ticker]
                elif ticker in qualified_tickers:
                    # Would qualify, but system is RISK-OFF
                    final_failed[ticker] = "[SYSTEM] Market regime RISK-OFF (would qualify otherwise)"
                else:
                    # No gate results (no data, etc.)
                    final_failed[ticker] = regime_result['reason']

            return {
                'qualified_tickers': final_qualified,
                'failed_tickers': final_failed,
                'system_state': 'RISK-OFF' if regime_failed else failure_modes['system_state'],
                'allow_new_trades': False,
                'failure_mode_alerts': system_alerts,
                'gate_results': gate_results,  # Preserve individual gate details
                'market_regime': regime_result,
                'failure_modes': failure_modes
            }

        # System healthy - return normal results
        return {
            'qualified_tickers': qualified_tickers,
            'failed_tickers': failed_tickers,
            'system_state': failure_modes['system_state'],
            'allow_new_trades': failure_modes['allow_new_trades'],
            'failure_mode_alerts': failure_modes['alerts'],
            'gate_results': gate_results,
            'market_regime': regime_result,
            'failure_modes': failure_modes
        }

    def get_system_state(self) -> Dict[str, Any]:
        """
        Get the current system state.

        Returns:
            Dictionary with system state information
        """
        if self.last_spy_data is None or self.last_vix_data is None:
            return {
                'state': 'UNKNOWN',
                'message': 'No market data loaded yet'
            }

        # Run failure mode checks
        failure_modes = self.failure_detector.run_all_checks(
            spy_data=self.last_spy_data,
            vix_data=self.last_vix_data
        )

        # Check market regime
        regime_result = self.market_regime_gate.evaluate(
            self.last_spy_data,
            self.last_vix_data
        )

        return {
            'state': failure_modes['system_state'],
            'allow_new_trades': failure_modes['allow_new_trades'] and regime_result['pass'],
            'alerts': failure_modes['alerts'],
            'market_regime_healthy': regime_result['pass'],
            'regime_details': regime_result['details']
        }

    def get_strike_suggestion(
        self,
        ticker: str,
        stock_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Get suggested strike range for a ticker.

        Args:
            ticker: Stock ticker symbol
            stock_data: DataFrame with stock OHLC data

        Returns:
            Dictionary with strike suggestions
        """
        result = self.structural_safety_gate.suggest_strike_range(stock_data)
        result['ticker'] = ticker

        return result
