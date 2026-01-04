#!/usr/bin/env python3
"""
Daily Credit Spread Scanner

Screens a watchlist of tickers through the 4-gate system and saves results to database.

Usage:
    python daily_scan.py                    # Uses watchlist.txt
    python daily_scan.py AAPL MSFT GOOGL   # Scan specific tickers
    python daily_scan.py --file custom.txt # Use custom watchlist file
    python daily_scan.py --help            # Show help

Run after market close for best results.
"""

import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import yfinance as yf
from dotenv import load_dotenv

from src.screener import CreditSpreadScreener
from src.data import Database, TradierProvider


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Daily Credit Spread Screener',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        Use watchlist.txt (default)
  %(prog)s AAPL MSFT GOOGL       Scan specific tickers
  %(prog)s --file custom.txt     Use custom watchlist file
        """
    )

    parser.add_argument(
        'tickers',
        nargs='*',
        help='Ticker symbols to scan (if provided, ignores watchlist file)'
    )

    parser.add_argument(
        '--file',
        type=str,
        default='watchlist.txt',
        help='Path to watchlist file (default: watchlist.txt)'
    )

    return parser.parse_args()


def load_watchlist(args: argparse.Namespace) -> List[str]:
    """
    Load ticker watchlist from command-line args or file.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of ticker symbols
    """
    # If tickers provided on command line, use those
    if args.tickers:
        tickers = [t.upper().strip() for t in args.tickers]
        print(f"📋 Scanning {len(tickers)} ticker(s) from command line")
        return tickers

    # Otherwise, try to load from file
    watchlist_file = args.file

    if not os.path.exists(watchlist_file):
        print(f"❌ Error: Watchlist file '{watchlist_file}' not found")
        print(f"\nCreate {watchlist_file} with one ticker per line, or provide tickers directly:")
        print(f"  python daily_scan.py AAPL MSFT GOOGL")
        sys.exit(1)

    # Read tickers from file
    tickers = []
    with open(watchlist_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                tickers.append(line.upper())

    if not tickers:
        print(f"❌ Error: No tickers found in {watchlist_file}")
        sys.exit(1)

    print(f"📋 Loaded {len(tickers)} ticker(s) from {watchlist_file}")
    return tickers


def fetch_market_data(tickers: List[str]) -> tuple:
    """
    Fetch SPY, VIX, and stock price data using yfinance.

    Args:
        tickers: List of ticker symbols to fetch

    Returns:
        Tuple of (spy_data, vix_data, stock_data_dict)
    """
    print(f"\n📊 Fetching market data...")

    # Fetch SPY
    print("  Fetching SPY...", end=' ')
    spy_data = yf.download('SPY', period='6mo', progress=False)
    if len(spy_data) == 0:
        print("❌ FAILED")
        print("\n❌ Error: Could not fetch SPY data")
        sys.exit(1)
    print(f"✓ ({len(spy_data)} days)")

    # Fetch VIX
    print("  Fetching VIX...", end=' ')
    vix_data = yf.download('^VIX', period='6mo', progress=False)
    if len(vix_data) == 0:
        print("❌ FAILED")
        print("\n❌ Error: Could not fetch VIX data")
        sys.exit(1)
    print(f"✓ ({len(vix_data)} days)")

    # Fetch stocks
    print(f"  Fetching {len(tickers)} stocks...")
    stock_data_dict = {}
    failed_tickers = []

    for i, ticker in enumerate(tickers, 1):
        try:
            data = yf.download(ticker, period='6mo', progress=False)
            if len(data) > 0:
                stock_data_dict[ticker] = data
                print(f"    [{i}/{len(tickers)}] {ticker}: ✓ ({len(data)} days)")
            else:
                failed_tickers.append(ticker)
                print(f"    [{i}/{len(tickers)}] {ticker}: ⚠ No data")
        except Exception as e:
            failed_tickers.append(ticker)
            print(f"    [{i}/{len(tickers)}] {ticker}: ⚠ Error ({str(e)[:50]})")

    if failed_tickers:
        print(f"\n  ⚠ Warning: Could not fetch data for {len(failed_tickers)} ticker(s): {', '.join(failed_tickers)}")

    if not stock_data_dict:
        print("\n❌ Error: No valid stock data fetched")
        sys.exit(1)

    print(f"\n✓ Successfully fetched data for {len(stock_data_dict)} stocks")
    return spy_data, vix_data, stock_data_dict


def fetch_options_data(tickers: List[str]) -> tuple:
    """
    Fetch IV Rank and earnings dates using Tradier (if configured).

    Args:
        tickers: List of ticker symbols

    Returns:
        Tuple of (tradier_provider, iv_rank_dict, earnings_dates_dict)
    """
    # Check if Tradier is configured
    if not os.getenv('TRADIER_API_KEY'):
        print("\n⚠ Tradier API not configured - skipping IV Rank and earnings data")
        print("  To enable: Add TRADIER_API_KEY to .env file")
        return None, None, None

    print(f"\n📈 Fetching options data from Tradier...")

    try:
        use_sandbox = os.getenv('TRADIER_USE_SANDBOX', 'true').lower() == 'true'
        tradier = TradierProvider(use_sandbox=use_sandbox)

        if not tradier.is_available():
            print("  ⚠ Tradier API unavailable - skipping options data")
            return None, None, None

        print(f"  ✓ Connected to Tradier ({'sandbox' if use_sandbox else 'production'})")

        iv_rank_dict = {}
        earnings_dates_dict = {}

        for i, ticker in enumerate(tickers, 1):
            # Get IV Rank
            iv_rank = tradier.get_iv_rank(ticker)
            if iv_rank is not None:
                iv_rank_dict[ticker] = iv_rank

            # Get earnings date
            earnings = tradier.get_earnings_date(ticker)
            if earnings is not None:
                earnings_dates_dict[ticker] = earnings

            print(f"    [{i}/{len(tickers)}] {ticker}: IV Rank: {iv_rank if iv_rank else 'N/A'}, "
                  f"Earnings: {earnings.strftime('%Y-%m-%d') if earnings else 'N/A'}")

        print(f"\n  ✓ IV Rank for {len(iv_rank_dict)}/{len(tickers)} tickers")
        print(f"  ✓ Earnings for {len(earnings_dates_dict)}/{len(tickers)} tickers")

        return tradier, iv_rank_dict, earnings_dates_dict

    except Exception as e:
        print(f"  ⚠ Tradier error: {e}")
        return None, None, None


def print_header():
    """Print scan header."""
    now = datetime.now()
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "CREDIT SPREAD SCREENER" + " " * 36 + "║")
    print("║" + " " * 22 + now.strftime("%Y-%m-%d %H:%M:%S") + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")


def print_system_status(results: Dict):
    """Print system status and market regime."""
    print("\nSYSTEM STATUS")
    print("─" * 80)

    system_state = results['system_state']
    allow_trades = results['allow_new_trades']

    status_icon = "✓" if allow_trades else "⚠"
    print(f"  Market Regime: {system_state} {status_icon}")
    print(f"  Allow New Trades: {'YES' if allow_trades else 'NO'}")

    # Show market metrics
    regime_details = results.get('market_regime', {})
    if regime_details:
        spy_close = regime_details.get('spy_close')
        spy_sma = regime_details.get('spy_sma_50')
        vix_change = regime_details.get('vix_change_5d')

        if spy_close and spy_sma:
            spy_pct = ((spy_close - spy_sma) / spy_sma) * 100
            print(f"\n  SPY: ${spy_close:.2f} (50-SMA: ${spy_sma:.2f}, {spy_pct:+.2f}%)")

        if vix_change is not None:
            print(f"  VIX: {vix_change:+.1f}% over 5 days")

    # Show alerts
    alerts = results.get('failure_mode_alerts', [])
    if alerts:
        print(f"\nALERTS")
        print("─" * 80)
        for alert in alerts:
            severity = alert.get('severity', 'INFO')
            message = alert.get('message', '')
            print(f"  [{severity}] {message}")


def print_qualified_tickers(results: Dict):
    """Print qualified tickers with details."""
    qualified = results.get('qualified_tickers', [])

    if not qualified:
        print(f"\nNO QUALIFIED TICKERS")
        if not results['allow_new_trades']:
            print("  Reason: System is RISK-OFF")
        return

    print(f"\n{'─' * 80}")
    print(f"QUALIFIED TICKERS ({len(qualified)})")
    print("─" * 80)

    for ticker in qualified:
        ticker_results = results['gate_results'][ticker]
        safety = ticker_results['gates']['structural_safety']['details']
        rs = ticker_results['gates']['relative_strength']['details']
        ev = ticker_results['gates']['event_volatility']['details']

        current_price = safety.get('current_price', 0)
        max_strike = safety.get('max_safe_strike', 0)

        if current_price and max_strike:
            discount_pct = ((current_price - max_strike) / current_price) * 100

            print(f"\n  ✓ {ticker} - ${current_price:.2f}")
            print(f"    ├─ Max Safe Strike: ${max_strike:.2f} ({discount_pct:.1f}% below current)")

            rel_strength = rs.get('relative_strength', 0)
            print(f"    ├─ Relative Strength: {rel_strength:+.1f}% vs SPY")

            # Show support levels
            supports = []
            sma_level = safety.get('sma_level')
            if sma_level:
                supports.append(f"50-SMA (${sma_level:.2f})")
            higher_low = safety.get('higher_low_level')
            if higher_low:
                supports.append(f"Higher Low (${higher_low:.2f})")
            consolidation = safety.get('consolidation_level')
            if consolidation:
                supports.append(f"Consolidation (${consolidation:.2f})")

            if supports:
                print(f"    ├─ Support: {', '.join(supports)}")

            # Show IV Rank if available
            iv_rank = ev.get('iv_rank')
            if iv_rank is not None:
                print(f"    └─ IV Rank: {iv_rank:.0f} (moderate premium)")
            else:
                print(f"    └─ IV Rank: N/A")


def print_failed_tickers(results: Dict):
    """Print failed tickers with reasons (verbose mode)."""
    failed = results.get('failed_tickers', {})

    if not failed:
        return

    print(f"\n{'─' * 80}")
    print(f"FAILED TICKERS ({len(failed)})")
    print("─" * 80)

    for ticker, reason in failed.items():
        print(f"  ✗ {ticker}: {reason}")


def print_summary(results: Dict, scan_id: int):
    """Print scan summary."""
    print(f"\n{'─' * 80}")
    print("SCREENING RESULTS")
    print("─" * 80)
    print(f"  Tickers Screened: {len(results['gate_results'])}")
    print(f"  Qualified: {len(results['qualified_tickers'])}")
    print(f"  Failed: {len(results['failed_tickers'])}")

    print(f"\n{'─' * 80}")
    print("DATA SAVED")
    print("─" * 80)
    print(f"  Database: data/screening.db (Scan ID: {scan_id})")
    print(f"  Query history: python -c \"from src.data import Database; db=Database(); print(db.get_latest_scan())\"")
    print()


def main():
    """Main execution function."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Load watchlist
    tickers = load_watchlist(args)

    # Print header
    print_header()

    # Fetch market data
    spy_data, vix_data, stock_data_dict = fetch_market_data(tickers)

    # Fetch options data (if Tradier configured)
    tradier, iv_rank_dict, earnings_dates_dict = fetch_options_data(list(stock_data_dict.keys()))

    # Run screener
    print(f"\n🔍 Running screener...")
    screener = CreditSpreadScreener()
    results = screener.screen(
        tickers=list(stock_data_dict.keys()),
        stock_data_dict=stock_data_dict,
        spy_data=spy_data,
        vix_data=vix_data,
        iv_rank_dict=iv_rank_dict,
        earnings_dates_dict=earnings_dates_dict
    )
    print("  ✓ Screening complete")

    # Save to database
    print(f"\n💾 Saving results to database...")
    db = Database()
    scan_id = db.save_scan_results(results)
    print(f"  ✓ Saved (Scan ID: {scan_id})")

    # Print results
    print_system_status(results)
    print_qualified_tickers(results)
    print_failed_tickers(results)
    print_summary(results, scan_id)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Scan interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
