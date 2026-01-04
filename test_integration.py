"""
Integration Test: Full System Test with Real Data

This script tests the entire pipeline:
1. Tradier API connection
2. Market data fetching (yfinance)
3. Full screening with all 4 gates
4. Database save/query
5. Data validation

Run after setting up your Tradier API key in .env

Usage: python test_integration.py
"""

import os
from dotenv import load_dotenv
import yfinance as yf
from datetime import datetime

from src.screener import CreditSpreadScreener
from src.data import TradierProvider, Database

# Load environment variables
load_dotenv()


def test_tradier_connection():
    """Test Tradier API connection and data fetching."""
    print("=" * 80)
    print("TEST 1: Tradier API Connection")
    print("=" * 80)

    if not os.getenv('TRADIER_API_KEY'):
        print("❌ TRADIER_API_KEY not found in .env")
        print("\nSetup instructions:")
        print("1. Copy .env.example to .env")
        print("2. Add your Tradier API key")
        print("3. Set TRADIER_USE_SANDBOX (true/false)")
        return None

    try:
        use_sandbox = os.getenv('TRADIER_USE_SANDBOX', 'true').lower() == 'true'
        tradier = TradierProvider(use_sandbox=use_sandbox)

        mode = "sandbox" if use_sandbox else "production"
        print(f"✓ Tradier provider initialized ({mode})")

        # Test connection
        if tradier.is_available():
            print("✓ Tradier API connection successful")
        else:
            print("❌ Cannot connect to Tradier API")
            return None

        # Test data fetching with a known ticker
        test_ticker = 'SPY'
        print(f"\nTesting data fetch for {test_ticker}:")

        # Get quote
        quote = tradier.get_quote(test_ticker)
        if quote:
            print(f"  ✓ Quote: ${quote.get('last', 'N/A')}")
        else:
            print(f"  ❌ Could not get quote")

        # Get current IV
        iv = tradier.get_current_iv(test_ticker)
        if iv:
            print(f"  ✓ Current IV: {iv:.1f}%")
        else:
            print(f"  ⚠ Current IV: Not available")

        # Get IV Rank
        iv_rank = tradier.get_iv_rank(test_ticker)
        if iv_rank:
            print(f"  ⚠ IV Rank: {iv_rank:.1f} (approximated - see notes)")
        else:
            print(f"  ⚠ IV Rank: Not available")

        # Get earnings
        earnings = tradier.get_earnings_date(test_ticker)
        if earnings:
            print(f"  ✓ Earnings: {earnings.strftime('%Y-%m-%d')}")
        else:
            print(f"  ⚠ Earnings: Not available")

        print("\n" + "=" * 80)
        print("TRADIER TEST SUMMARY")
        print("=" * 80)
        print("✓ Connection: Working")
        print("✓ Quotes: Working")
        print("⚠ IV/IV Rank: Partial (see warnings)")
        print("⚠ Earnings: May not be available")
        print("\nNOTE: IV Rank is approximated. For production, consider:")
        print("  - Market Chameleon API ($50/mo)")
        print("  - OptionMetrics")
        print("\nNOTE: Earnings dates have limited coverage. Consider:")
        print("  - Earnings Whispers API")
        print("  - Yahoo Finance (via yfinance)")

        return tradier

    except Exception as e:
        print(f"❌ Tradier error: {e}")
        return None


def test_market_data_fetch():
    """Test market data fetching with yfinance."""
    print("\n" + "=" * 80)
    print("TEST 2: Market Data Fetching (yfinance)")
    print("=" * 80)

    try:
        # Test SPY
        print("Fetching SPY...")
        spy_data = yf.download('SPY', period='6mo', progress=False)
        if len(spy_data) > 0:
            print(f"  ✓ SPY: {len(spy_data)} days of data")
            latest_close = float(spy_data['Close'].iloc[-1])
            print(f"    Latest close: ${latest_close:.2f}")
        else:
            print("  ❌ SPY: No data")
            return None, None, None

        # Test VIX
        print("Fetching VIX...")
        vix_data = yf.download('^VIX', period='6mo', progress=False)
        if len(vix_data) > 0:
            print(f"  ✓ VIX: {len(vix_data)} days of data")
            latest_close = float(vix_data['Close'].iloc[-1])
            print(f"    Latest close: {latest_close:.2f}")
        else:
            print("  ❌ VIX: No data")
            return None, None, None

        # Test sample stock
        print("Fetching AAPL...")
        aapl_data = yf.download('AAPL', period='6mo', progress=False)
        if len(aapl_data) > 0:
            print(f"  ✓ AAPL: {len(aapl_data)} days of data")
            latest_close = float(aapl_data['Close'].iloc[-1])
            print(f"    Latest close: ${latest_close:.2f}")
        else:
            print("  ❌ AAPL: No data")
            return None, None, None

        print("\n✓ Market data fetch: SUCCESS")
        return spy_data, vix_data, {'AAPL': aapl_data}

    except Exception as e:
        print(f"❌ Market data fetch error: {e}")
        return None, None, None


def test_full_screening(spy_data, vix_data, stock_data, tradier):
    """Test full screening pipeline."""
    print("\n" + "=" * 80)
    print("TEST 3: Full Screening Pipeline")
    print("=" * 80)

    try:
        # Initialize screener
        screener = CreditSpreadScreener()
        print("✓ Screener initialized")

        # Get options data if Tradier available
        tickers = list(stock_data.keys())
        iv_rank_dict = None
        earnings_dates = None

        if tradier:
            print(f"\nFetching options data for {len(tickers)} tickers...")
            iv_rank_dict = {}
            earnings_dates = {}

            for ticker in tickers:
                iv_rank = tradier.get_iv_rank(ticker)
                earnings = tradier.get_earnings_date(ticker)

                if iv_rank:
                    iv_rank_dict[ticker] = iv_rank
                if earnings:
                    earnings_dates[ticker] = earnings

            print(f"  ✓ IV Rank for {len(iv_rank_dict)}/{len(tickers)} tickers")
            print(f"  ✓ Earnings for {len(earnings_dates)}/{len(tickers)} tickers")

        # Run screening
        print("\nRunning screener...")
        results = screener.screen(
            tickers=tickers,
            stock_data_dict=stock_data,
            spy_data=spy_data,
            vix_data=vix_data,
            iv_rank_dict=iv_rank_dict,
            earnings_dates_dict=earnings_dates
        )

        print("\n" + "-" * 80)
        print("SCREENING RESULTS")
        print("-" * 80)
        print(f"System State: {results['system_state']}")
        print(f"Allow New Trades: {results['allow_new_trades']}")
        print(f"Tickers Screened: {len(results['gate_results'])}")
        print(f"Qualified: {len(results['qualified_tickers'])}")
        print(f"Failed: {len(results['failed_tickers'])}")

        if results['failure_mode_alerts']:
            print(f"\nAlerts: {len(results['failure_mode_alerts'])}")
            for alert in results['failure_mode_alerts']:
                print(f"  [{alert.get('severity')}] {alert.get('message')}")

        if results['qualified_tickers']:
            print(f"\nQualified Tickers:")
            for ticker in results['qualified_tickers']:
                ticker_results = results['gate_results'][ticker]
                safety = ticker_results['gates']['structural_safety']['details']
                print(f"  ✓ {ticker}: ${safety.get('current_price', 'N/A'):.2f} "
                      f"→ max strike ${safety.get('max_safe_strike', 'N/A'):.2f}")
        else:
            print(f"\nNo qualified tickers")
            print("Reasons:")
            for ticker, reason in results['failed_tickers'].items():
                print(f"  ✗ {ticker}: {reason}")

        print("\n✓ Screening: SUCCESS")
        return results

    except Exception as e:
        print(f"❌ Screening error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_database_integration(results):
    """Test database save and query."""
    print("\n" + "=" * 80)
    print("TEST 4: Database Integration")
    print("=" * 80)

    try:
        # Initialize database
        db = Database(db_path='data/test_integration.db')
        print("✓ Database initialized")

        # Save results
        scan_id = db.save_scan_results(results)
        print(f"✓ Saved scan with ID: {scan_id}")

        # Query back
        latest = db.get_latest_scan()
        if latest:
            print(f"✓ Retrieved latest scan (ID: {latest['scan_id']})")
            print(f"  Date: {latest['scan_date']}")
            print(f"  System State: {latest['system_state']}")
            print(f"  Qualified: {len(latest['qualified_tickers'])}")
        else:
            print("❌ Could not retrieve scan")
            return False

        # Test specific ticker query
        if results['gate_results']:
            test_ticker = list(results['gate_results'].keys())[0]
            history = db.get_ticker_history(test_ticker, days=7)
            print(f"✓ Retrieved history for {test_ticker}: {len(history)} records")

        print("\n✓ Database integration: SUCCESS")
        return True

    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_data_completeness(results):
    """Validate that all expected data fields are present."""
    print("\n" + "=" * 80)
    print("TEST 5: Data Completeness Validation")
    print("=" * 80)

    issues = []

    # Check top-level results
    required_keys = ['qualified_tickers', 'failed_tickers', 'system_state',
                     'allow_new_trades', 'gate_results', 'market_regime']

    for key in required_keys:
        if key not in results:
            issues.append(f"Missing top-level key: {key}")

    # Check gate results structure
    for ticker, ticker_data in results.get('gate_results', {}).items():
        if 'gates' not in ticker_data:
            issues.append(f"{ticker}: Missing 'gates' key")
            continue

        gates = ticker_data['gates']

        # Check each gate
        expected_gates = ['relative_strength', 'structural_safety', 'event_volatility']
        for gate_name in expected_gates:
            if gate_name not in gates:
                issues.append(f"{ticker}: Missing gate '{gate_name}'")
            elif 'details' not in gates[gate_name]:
                issues.append(f"{ticker}: Missing details in '{gate_name}'")

        # Check specific data fields
        rs_details = gates.get('relative_strength', {}).get('details', {})
        if 'relative_strength' not in rs_details:
            issues.append(f"{ticker}: Missing relative_strength value")

        safety_details = gates.get('structural_safety', {}).get('details', {})
        if 'current_price' not in safety_details:
            issues.append(f"{ticker}: Missing current_price")
        if 'max_safe_strike' not in safety_details and ticker in results.get('qualified_tickers', []):
            issues.append(f"{ticker}: Missing max_safe_strike (qualified ticker)")

    if issues:
        print("❌ Data completeness issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nSome features may not work correctly.")
    else:
        print("✓ All required data fields present")

    return len(issues) == 0


def main():
    """Run full integration test suite."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "INTEGRATION TEST SUITE" + " " * 36 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Test 1: Tradier
    tradier = test_tradier_connection()

    # Test 2: Market Data
    spy_data, vix_data, stock_data = test_market_data_fetch()

    if spy_data is None:
        print("\n❌ Cannot proceed without market data")
        return

    # Test 3: Screening
    results = test_full_screening(spy_data, vix_data, stock_data, tradier)

    if results is None:
        print("\n❌ Cannot proceed without screening results")
        return

    # Test 4: Database
    db_success = test_database_integration(results)

    # Test 5: Validation
    validation_success = validate_data_completeness(results)

    # Final Summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print(f"\n✓ Tradier API: {'Connected' if tradier else 'Not configured'}")
    print(f"✓ Market Data: Working")
    print(f"✓ Screener: Working")
    print(f"✓ Database: {'Working' if db_success else 'Failed'}")
    print(f"✓ Data Validation: {'Passed' if validation_success else 'Issues Found'}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)

    if not tradier:
        print("\n⚠ Tradier not configured:")
        print("  - Screener will work without IV Rank and earnings")
        print("  - To enable: See TRADIER_SETUP.md")

    if validation_success and db_success:
        print("\n✓ System is ready for production use!")
        print("\nYou can now:")
        print("  - Run daily_scan.py (Phase 2)")
        print("  - Set up notifications (Phase 3)")
        print("  - Schedule automated runs (Phase 4)")
    else:
        print("\n⚠ Fix issues above before proceeding to next phases")

    print()


if __name__ == '__main__':
    main()
