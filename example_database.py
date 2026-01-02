"""
Example: Using the Database with the Screener

This demonstrates saving screening results to the database
and querying historical data.

Run with: python example_database.py
"""

import yfinance as yf
from datetime import date
from src.screener import CreditSpreadScreener
from src.data import Database


def main():
    print("=" * 80)
    print("DATABASE INTEGRATION EXAMPLE")
    print("=" * 80)
    print()

    # Initialize screener and database
    screener = CreditSpreadScreener()
    db = Database()  # Creates data/screening.db automatically

    print("✓ Database initialized at: data/screening.db")
    print()

    # --------------------------------------------------
    # STEP 1: Run a screening
    # --------------------------------------------------
    print("STEP 1: Running screening")
    print("-" * 80)

    # Fetch data
    tickers = ['AAPL', 'MSFT']
    print(f"Screening: {', '.join(tickers)}")

    spy_data = yf.download('SPY', period='6mo', progress=False)
    vix_data = yf.download('^VIX', period='6mo', progress=False)

    stock_data = {}
    for ticker in tickers:
        stock_data[ticker] = yf.download(ticker, period='6mo', progress=False)

    # Run screener
    results = screener.screen(
        tickers=tickers,
        stock_data_dict=stock_data,
        spy_data=spy_data,
        vix_data=vix_data
    )

    print(f"System State: {results['system_state']}")
    print(f"Qualified: {len(results['qualified_tickers'])}")
    print()

    # --------------------------------------------------
    # STEP 2: Save results to database
    # --------------------------------------------------
    print("STEP 2: Saving to database")
    print("-" * 80)

    scan_id = db.save_scan_results(results)
    print(f"✓ Saved scan with ID: {scan_id}")
    print()

    # --------------------------------------------------
    # STEP 3: Query the database
    # --------------------------------------------------
    print("STEP 3: Querying database")
    print("-" * 80)

    # Get latest scan
    latest = db.get_latest_scan()
    print(f"\nLatest Scan ({latest['scan_date']}):")
    print(f"  System State: {latest['system_state']}")
    print(f"  Qualified Tickers: {len(latest['qualified_tickers'])}")

    for ticker_data in latest['qualified_tickers']:
        print(f"\n  {ticker_data['ticker']}:")
        print(f"    Current: ${ticker_data['current_price']:.2f}")
        print(f"    Max Strike: ${ticker_data['max_safe_strike']:.2f}")
        print(f"    Discount: {ticker_data['discount_pct']:.1f}%")
        print(f"    RS Score: +{ticker_data['relative_strength']:.1f}%")

    # Get AAPL history (if available)
    if 'AAPL' in tickers:
        print("\n" + "-" * 80)
        print("AAPL History (last 30 days):")
        history = db.get_ticker_history('AAPL', days=30)

        if history:
            for entry in history[:5]:  # Show last 5
                status = "✓ PASSED" if entry['passed'] else "✗ FAILED"
                print(f"  {entry['scan_date']}: {status}")
                if not entry['passed']:
                    print(f"    Reason: {entry['failure_reason']}")
        else:
            print("  (No history yet - run screener daily to build history)")

    # Get qualification summary
    print("\n" + "-" * 80)
    print("Qualification Summary:")
    summary = db.get_qualification_summary(days=30)

    if summary:
        for ticker_stats in summary:
            print(f"\n  {ticker_stats['ticker']}:")
            print(f"    Screened: {ticker_stats['times_screened']} times")
            print(f"    Qualified: {ticker_stats['times_qualified']} times")
            print(f"    Rate: {ticker_stats['qualification_rate']:.0f}%")
    else:
        print("  (No data yet - run screener daily to build stats)")

    # Export to CSV
    print("\n" + "-" * 80)
    print("Exporting to CSV...")
    csv_path = 'data/export.csv'
    db.export_to_csv(csv_path, days=7)
    print(f"✓ Exported to: {csv_path}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("The database now contains:")
    print("  - Today's screening results")
    print("  - Searchable ticker history")
    print("  - Qualification statistics")
    print()
    print("Next steps:")
    print("  - Run daily to build history")
    print("  - Use db.get_ticker_history() to track patterns")
    print("  - Use db.get_qualification_summary() to find reliable setups")
    print()
    print("See DATABASE_USAGE.md for all query examples")


if __name__ == '__main__':
    main()
