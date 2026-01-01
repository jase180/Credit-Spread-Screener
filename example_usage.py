"""
Example Usage: Credit Spread Screener

This script demonstrates how to use the screening system with real market data.

Run with: python example_usage.py
"""

import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.screener import CreditSpreadScreener

# Load environment variables from .env file (for Tradier API key)
load_dotenv()


def fetch_data(ticker: str, period: str = '6mo') -> pd.DataFrame:
    """
    Fetch historical OHLCV data for a ticker.

    Args:
        ticker: Stock ticker symbol
        period: Data period (default '6mo')

    Returns:
        DataFrame with OHLC data
    """
    print(f"Fetching data for {ticker}...")
    data = yf.download(ticker, period=period, progress=False)
    return data


def main():
    """Main example execution."""

    print("=" * 80)
    print("CREDIT SPREAD SCREENER - EXAMPLE USAGE")
    print("=" * 80)
    print()

    # --------------------------------------------------
    # STEP 1: Define the universe of stocks to screen
    # --------------------------------------------------
    print("STEP 1: Defining stock universe")
    print("-" * 80)

    # Example: Screen some mega-cap tech stocks
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'AMD', 'AMZN']
    print(f"Tickers to screen: {', '.join(tickers)}")
    print()

    # --------------------------------------------------
    # STEP 2: Fetch market data
    # --------------------------------------------------
    print("STEP 2: Fetching market data")
    print("-" * 80)

    # Fetch SPY and VIX data (required for regime evaluation)
    spy_data = fetch_data('SPY')
    vix_data = fetch_data('^VIX')

    # Fetch data for each stock
    stock_data_dict = {}
    for ticker in tickers:
        try:
            stock_data_dict[ticker] = fetch_data(ticker)
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

    print(f"Successfully fetched data for {len(stock_data_dict)} tickers")
    print()

    # --------------------------------------------------
    # STEP 2.5: Fetch options data (OPTIONAL - requires Tradier API)
    # --------------------------------------------------
    print("STEP 2.5: Fetching options data (optional)")
    print("-" * 80)

    iv_rank_dict = None
    earnings_dates_dict = None

    # Try to initialize Tradier provider if API key is configured
    if os.getenv('TRADIER_API_KEY'):
        try:
            from src.data import TradierProvider

            print("Tradier API key found - fetching options data...")
            use_sandbox = os.getenv('TRADIER_USE_SANDBOX', 'true').lower() == 'true'
            tradier = TradierProvider(use_sandbox=use_sandbox)

            if tradier.is_available():
                print("✓ Tradier API connected")

                # Fetch IV Rank and earnings for each ticker
                iv_rank_dict = {}
                earnings_dates_dict = {}

                for ticker in tickers:
                    if ticker in stock_data_dict:
                        iv_rank = tradier.get_iv_rank(ticker)
                        earnings = tradier.get_earnings_date(ticker)

                        if iv_rank is not None:
                            iv_rank_dict[ticker] = iv_rank
                        if earnings is not None:
                            earnings_dates_dict[ticker] = earnings

                print(f"✓ Fetched IV Rank for {len(iv_rank_dict)} tickers")
                print(f"✓ Fetched earnings dates for {len(earnings_dates_dict)} tickers")
            else:
                print("✗ Cannot connect to Tradier API")
                print("  Continuing without options data...")

        except Exception as e:
            print(f"✗ Error initializing Tradier: {e}")
            print("  Continuing without options data...")
    else:
        print("No Tradier API key found - skipping options data")
        print("  To enable: See TRADIER_SETUP.md for instructions")

    print()

    # --------------------------------------------------
    # STEP 3: Initialize the screener
    # --------------------------------------------------
    print("STEP 3: Initializing screener")
    print("-" * 80)

    screener = CreditSpreadScreener(
        enable_atr_filter=True,
        correlated_breakdown_threshold=0.40
    )

    print("Screener initialized with:")
    print("  - ATR filter: ENABLED")
    print("  - Correlated breakdown threshold: 40%")
    print()

    # --------------------------------------------------
    # STEP 4: Check system state first
    # --------------------------------------------------
    print("STEP 4: Checking system state")
    print("-" * 80)

    # We need to run a preliminary check to load market data
    _ = screener.market_regime_gate.evaluate(spy_data, vix_data)
    screener.last_spy_data = spy_data
    screener.last_vix_data = vix_data

    system_state = screener.get_system_state()

    print(f"System State: {system_state['state']}")
    print(f"Allow New Trades: {system_state['allow_new_trades']}")
    print(f"Market Regime Healthy: {system_state['market_regime_healthy']}")

    if system_state['alerts']:
        print("\nActive Alerts:")
        for alert in system_state['alerts']:
            print(f"  [{alert['severity']}] {alert['message']}")
    else:
        print("\nNo active alerts - system is healthy")

    print()

    # --------------------------------------------------
    # STEP 5: Run the screening process
    # --------------------------------------------------
    print("STEP 5: Running screening process")
    print("-" * 80)

    # Note: iv_rank_dict and earnings_dates_dict were populated in Step 2.5
    # If Tradier is not configured, they will be None (checks skipped)

    # Run the screen
    results = screener.screen(
        tickers=tickers,
        stock_data_dict=stock_data_dict,
        spy_data=spy_data,
        vix_data=vix_data,
        iv_rank_dict=iv_rank_dict,
        earnings_dates_dict=earnings_dates_dict
    )

    print(f"Screening complete!")
    print()

    # --------------------------------------------------
    # STEP 6: Display results
    # --------------------------------------------------
    print("STEP 6: Results")
    print("=" * 80)

    print(f"\nSystem State: {results['system_state']}")
    print(f"New Trades Allowed: {results['allow_new_trades']}")

    if results['failure_mode_alerts']:
        print("\nFailure Mode Alerts:")
        for alert in results['failure_mode_alerts']:
            print(f"  [{alert['severity']}] {alert.get('action', 'N/A')}")
            print(f"    {alert['message']}")

    print(f"\n{'=' * 80}")
    print(f"QUALIFIED TICKERS ({len(results['qualified_tickers'])})")
    print(f"{'=' * 80}")

    if results['qualified_tickers']:
        for ticker in results['qualified_tickers']:
            print(f"\n{ticker}:")

            # Get strike suggestion
            strike_info = screener.get_strike_suggestion(
                ticker,
                stock_data_dict[ticker]
            )

            print(f"  Current Price: ${strike_info['current_price']:.2f}")
            print(f"  Max Safe Strike: ${strike_info['max_safe_strike']:.2f}")
            print(f"  Discount: {strike_info['discount_pct']:.1f}%")

            # Show gate details
            ticker_gates = results['gate_results'][ticker]['gates']

            rs_details = ticker_gates['relative_strength']['details']
            print(f"  Relative Strength: +{rs_details['relative_strength']:.1f}% vs SPY")

            safety_details = ticker_gates['structural_safety']['details']
            print(f"  Support Levels:")
            print(f"    - 50-day SMA: ${safety_details['sma_50_level']:.2f}")
            if safety_details['higher_low_level']:
                print(f"    - Higher Low: ${safety_details['higher_low_level']:.2f}")
            if safety_details['consolidation_level']:
                print(f"    - Consolidation: ${safety_details['consolidation_level']:.2f}")

    else:
        print("\nNo tickers qualified. Reasons:")
        for ticker, reason in results['failed_tickers'].items():
            print(f"  {ticker}: {reason}")

    print(f"\n{'=' * 80}")
    print(f"FAILED TICKERS ({len(results['failed_tickers'])})")
    print(f"{'=' * 80}")

    if results['failed_tickers']:
        for ticker, reason in results['failed_tickers'].items():
            if ticker not in results['qualified_tickers']:
                print(f"  {ticker}: {reason}")

    print("\n" + "=" * 80)
    print("END OF SCREENING REPORT")
    print("=" * 80)


if __name__ == '__main__':
    main()
