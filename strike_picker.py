#!/usr/bin/env python3
"""
Strike Picker - Optimal Put Credit Spread Strike Selection

Analyzes qualified tickers and suggests specific strike prices for put credit spreads
based on structural safety, probability of profit, and liquidity.

Usage:
    python strike_picker.py NVDA                    # Use latest scan results
    python strike_picker.py NVDA --dte 35           # Target 35 DTE
    python strike_picker.py NVDA --spread-width 10  # $10 spread width
    python strike_picker.py NVDA --scan-id 9        # Use specific scan ID
    python strike_picker.py --list                  # List qualified tickers from latest scan

Run after daily_scan.py to get actionable trade recommendations.
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from src.data import Database, TradierProvider
from src.trading import StrikeSelector


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Strike Picker - Put Credit Spread Strike Selection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s NVDA                      Analyze NVDA from latest scan
  %(prog)s NVDA --dte 35             Target 35 DTE (default 30-45)
  %(prog)s NVDA --spread-width 10    Use $10 spread (default $5)
  %(prog)s NVDA --top 3              Show top 3 recommendations
  %(prog)s --list                    List qualified tickers from latest scan
        """
    )

    parser.add_argument(
        'ticker',
        nargs='?',
        help='Ticker symbol to analyze'
    )

    parser.add_argument(
        '--scan-id',
        type=int,
        help='Scan ID to use (default: latest scan)'
    )

    parser.add_argument(
        '--dte',
        type=int,
        default=37,
        help='Target days to expiration (default: 37, range: 30-45)'
    )

    parser.add_argument(
        '--spread-width',
        type=float,
        default=5.0,
        help='Spread width in dollars (default: 5.0)'
    )

    parser.add_argument(
        '--top',
        type=int,
        default=5,
        help='Number of recommendations to show (default: 5)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List qualified tickers from latest scan'
    )

    return parser.parse_args()


def print_header(ticker: str):
    """Print strike picker header."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + f"STRIKE RECOMMENDATIONS: {ticker}" + " " * (36 - len(ticker)) + "║")
    print("║" + " " * 22 + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")


def print_ticker_info(result: dict):
    """Print ticker information."""
    ticker = result.get('ticker', '')
    current_price = result.get('current_price', 0)
    max_safe_strike = result.get('max_safe_strike', 0)
    support_level = result.get('support_level', 0)

    print(f"\n{'─' * 80}")
    print(f"TICKER ANALYSIS")
    print("─" * 80)
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Max Safe Strike: ${max_safe_strike:.2f} (structural safety limit)")
    print(f"  Support Level: ${support_level:.2f}")

    if current_price and max_safe_strike:
        discount = ((current_price - max_safe_strike) / current_price) * 100
        print(f"  Safety Buffer: {discount:.1f}% below current price")


def print_recommendations(result: dict, support_level: float):
    """Print strike recommendations."""
    recommendations = result.get('recommendations', [])
    total_candidates = result.get('total_candidates', 0)

    if not recommendations:
        error = result.get('error', 'No recommendations found')
        print(f"\n{'─' * 80}")
        print(f"NO RECOMMENDATIONS")
        print("─" * 80)
        print(f"  {error}")
        return

    print(f"\n{'─' * 80}")
    print(f"RECOMMENDATIONS ({len(recommendations)} of {total_candidates} candidates)")
    print("─" * 80)

    for i, rec in enumerate(recommendations, 1):
        exp = rec.get('expiration', '')
        dte = rec.get('dte', 0)
        sell_strike = rec.get('sell_strike', 0)
        buy_strike = rec.get('buy_strike', 0)
        credit = rec.get('credit', 0)
        max_profit = rec.get('max_profit_dollars', 0)
        max_loss = rec.get('max_loss_dollars', 0)
        roi = rec.get('roi', 0)
        breakeven = rec.get('breakeven', 0)
        delta = rec.get('delta', 0)
        pop = rec.get('pop', 0)
        distance = rec.get('distance_from_support', 0)
        sell_vol = rec.get('sell_volume', 0)
        sell_oi = rec.get('sell_open_interest', 0)
        liquidity_score = rec.get('liquidity_score', 0)

        # Determine if top recommendation
        marker = "⭐ " if i == 1 else "  "

        # Calculate distance below support (positive means below support = good)
        distance_below_support = support_level - sell_strike

        print(f"\n{marker}RANK {i}: {exp} ({dte} DTE)")
        print("─" * 80)
        print(f"  Sell Put:   ${sell_strike:.2f} @ ${rec.get('sell_mid', 0):.2f}    (Δ {delta:.2f}, {pop:.0f}% PoP)")
        print(f"  Buy Put:    ${buy_strike:.2f} @ ${rec.get('buy_mid', 0):.2f}")
        print()
        print(f"  Credit:     ${credit:.2f} per spread (${max_profit:.0f} per contract)")
        print(f"  Max Profit: ${max_profit:.0f} ({roi:.1f}% ROI on ${max_loss:.0f} max risk)")
        print(f"  Max Loss:   ${max_loss:.0f} (spread width - credit)")
        print(f"  Breakeven:  ${breakeven:.2f}")
        print()

        # Show distance below support
        if distance_below_support > 0:
            print(f"  Distance Below Support: ${distance_below_support:.2f} ({'✓ SAFE' if distance_below_support >= 2 else '⚠ CLOSE'})")
        else:
            print(f"  Distance from Support: ${abs(distance_below_support):.2f} above ⚠ RISKY")

        # Liquidity stars
        stars = "★" * min(5, int(liquidity_score / 20)) + "☆" * max(0, 5 - int(liquidity_score / 20))
        print(f"  Liquidity: {stars} (Vol: {sell_vol}, OI: {sell_oi})")


def get_latest_scan(db: Database, scan_id: Optional[int] = None):
    """Get latest scan results from database."""
    if scan_id:
        return db.get_scan_by_id(scan_id)
    else:
        return db.get_latest_scan()


def list_qualified_tickers(db: Database):
    """List qualified tickers from latest scan."""
    scan = db.get_latest_scan()
    if not scan:
        print("❌ No scans found in database. Run daily_scan.py first.")
        sys.exit(1)

    scan_id = scan['scan_id']
    scan_date = scan['scan_date']
    qualified = scan.get('qualified_tickers', [])

    print(f"\n{'─' * 80}")
    print(f"QUALIFIED TICKERS (Scan ID: {scan_id}, Date: {scan_date})")
    print("─" * 80)

    if not qualified:
        print("  No qualified tickers found")
        print(f"  System State: {scan.get('system_state', 'UNKNOWN')}")
        print(f"  Allow Trades: {scan.get('allow_new_trades', False)}")
    else:
        for ticker in qualified:
            print(f"  ✓ {ticker}")

    print()


def main():
    """Main execution function."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Initialize database
    db = Database()

    # List mode
    if args.list:
        list_qualified_tickers(db)
        return

    # Require ticker
    if not args.ticker:
        print("❌ Error: Ticker required (or use --list to see qualified tickers)")
        print("   Example: python strike_picker.py NVDA")
        sys.exit(1)

    ticker = args.ticker.upper()

    # Print header
    print_header(ticker)

    # Get scan results
    print(f"\n📊 Loading scan results...")
    scan = get_latest_scan(db, args.scan_id)
    if not scan:
        print("❌ No scan results found. Run daily_scan.py first.")
        sys.exit(1)

    scan_id = scan['scan_id']
    scan_date = scan['scan_date']
    print(f"  ✓ Using Scan ID {scan_id} ({scan_date})")

    # Get ticker screening results from database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM screening_results
            WHERE scan_id = ? AND ticker = ?
        """, (scan_id, ticker))

        ticker_row = cursor.fetchone()
        if not ticker_row:
            print(f"\n❌ {ticker} not found in scan results")
            print(f"   Run: python daily_scan.py {ticker}")
            sys.exit(1)

        ticker_data = dict(ticker_row)

    # Extract price and safety data
    current_price = ticker_data.get('current_price')
    max_safe_strike = ticker_data.get('max_safe_strike')
    support_level = ticker_data.get('stock_sma_50') or ticker_data.get('higher_low_level') or max_safe_strike

    if not current_price or not max_safe_strike:
        print(f"\n❌ Missing price data for {ticker}")
        sys.exit(1)

    # Check if Tradier is configured
    if not os.getenv('TRADIER_API_KEY'):
        print("\n❌ Tradier API not configured")
        print("   Add TRADIER_API_KEY to .env file")
        sys.exit(1)

    # Initialize Tradier
    print(f"\n📈 Connecting to Tradier...")
    use_sandbox = os.getenv('TRADIER_USE_SANDBOX', 'true').lower() == 'true'
    tradier = TradierProvider(use_sandbox=use_sandbox)

    if not tradier.is_available():
        print("❌ Tradier API unavailable")
        sys.exit(1)

    print(f"  ✓ Connected to Tradier ({'sandbox' if use_sandbox else 'production'})")

    # Initialize strike selector
    dte_range = 15  # +/- range around target DTE
    min_dte = max(30, args.dte - dte_range)
    max_dte = min(45, args.dte + dte_range)

    selector = StrikeSelector(
        tradier_provider=tradier,
        min_dte=min_dte,
        max_dte=max_dte,
        spread_width=args.spread_width
    )

    # Generate recommendations
    print(f"\n🔍 Analyzing options chain for {ticker}...")
    print(f"  Target DTE: {args.dte} (searching {min_dte}-{max_dte})")
    print(f"  Spread Width: ${args.spread_width}")

    result = selector.suggest_strikes(
        ticker=ticker,
        current_price=current_price,
        max_safe_strike=max_safe_strike,
        support_level=support_level,
        top_n=args.top
    )

    # Print results
    print_ticker_info(result)
    print_recommendations(result, support_level)

    print(f"\n{'─' * 80}")
    print("NEXT STEPS")
    print("─" * 80)
    print("  1. Review recommendations above")
    print("  2. Check your broker's platform for current quotes")
    print("  3. Verify bid/ask spreads are acceptable")
    print("  4. Enter trade with limit order at mid price or better")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
