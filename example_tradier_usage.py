"""
Example: Using Tradier Options Data Provider

This demonstrates how to use the Tradier API to get options data
for the credit spread screener.

Setup:
1. Get Tradier account (sandbox OR brokerage - see TRADIER_SETUP.md)
2. Get your API key from your dashboard
3. Copy .env.example to .env and add your API key
4. Set TRADIER_USE_SANDBOX (true for sandbox, false for production)
5. Run: pip install -r requirements.txt
6. Run this script: python example_tradier_usage.py
"""

import os
from dotenv import load_dotenv
from src.data import TradierProvider

# Load environment variables from .env file
load_dotenv()


def main():
    print("=" * 80)
    print("TRADIER OPTIONS DATA PROVIDER - EXAMPLE")
    print("=" * 80)
    print()

    # Initialize Tradier provider
    # Reads TRADIER_API_KEY and TRADIER_USE_SANDBOX from .env file
    try:
        use_sandbox = os.getenv('TRADIER_USE_SANDBOX', 'true').lower() == 'true'
        provider = TradierProvider(use_sandbox=use_sandbox)

        mode = "sandbox (15-min delayed)" if use_sandbox else "production (real-time)"
        print(f"✓ Tradier provider initialized ({mode})")
        print()
    except ValueError as e:
        print(f"✗ Error: {e}")
        print()
        print("Setup instructions:")
        print("1. See TRADIER_SETUP.md for detailed setup")
        print("2. Copy .env.example to .env")
        print("3. Add your API key and set TRADIER_USE_SANDBOX")
        return

    # Check if API is accessible
    print("Checking Tradier API connection...")
    if provider.is_available():
        print("✓ Tradier API is accessible")
    else:
        print("✗ Cannot connect to Tradier API")
        return

    print()

    # Test with a few tickers
    test_tickers = ['AAPL', 'MSFT', 'SPY']

    print("=" * 80)
    print("FETCHING OPTIONS DATA")
    print("=" * 80)
    print()

    for ticker in test_tickers:
        print(f"\n{ticker}:")
        print("-" * 40)

        # Get current quote
        quote = provider.get_quote(ticker)
        if quote:
            print(f"  Last Price: ${quote.get('last', 'N/A')}")
            print(f"  Volume: {quote.get('volume', 'N/A'):,}")

        # Get current IV
        iv = provider.get_current_iv(ticker)
        if iv is not None:
            print(f"  Current IV: {iv:.1f}%")
        else:
            print(f"  Current IV: Not available")

        # Get IV Rank
        iv_rank = provider.get_iv_rank(ticker)
        if iv_rank is not None:
            print(f"  IV Rank: {iv_rank:.1f}")
        else:
            print(f"  IV Rank: Not available")

        # Get earnings date
        earnings = provider.get_earnings_date(ticker)
        if earnings:
            print(f"  Next Earnings: {earnings.strftime('%Y-%m-%d')}")
        else:
            print(f"  Next Earnings: Not available")

    print()
    print("=" * 80)
    print("NOTES")
    print("=" * 80)
    print()
    print("1. IV Rank calculation:")
    print("   - Tradier doesn't provide IV Rank directly")
    print("   - Current implementation uses approximation")
    print("   - For accurate IV Rank, consider Market Chameleon or OptionMetrics")
    print()
    print("2. Earnings dates:")
    print("   - Tradier's calendar API has limited coverage")
    print("   - Consider using Earnings Whispers or Yahoo Finance API")
    print("   - You can still use the screener without earnings dates")
    print()
    print("3. Current IV:")
    print("   - Calculated from ATM options with 30-45 DTE")
    print("   - This is accurate and suitable for screening")
    print()


if __name__ == '__main__':
    main()
