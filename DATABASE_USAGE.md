# Database Usage Guide

This guide shows how to use the SQLite database for persistent storage of screening results.

## Quick Start

```python
from src.screener import CreditSpreadScreener
from src.data import Database
import yfinance as yf

# Initialize screener and database
screener = CreditSpreadScreener()
db = Database()  # Creates data/screening.db

# Run screening
spy_data = yf.download('SPY', period='6mo', progress=False)
vix_data = yf.download('^VIX', period='6mo', progress=False)
stock_data = {'AAPL': yf.download('AAPL', period='6mo', progress=False)}

results = screener.screen(
    tickers=['AAPL'],
    stock_data_dict=stock_data,
    spy_data=spy_data,
    vix_data=vix_data
)

# Save to database
scan_id = db.save_scan_results(results)
print(f"Saved scan with ID: {scan_id}")
```

## Database Schema

The database uses 3 normalized tables:

### 1. `daily_scans`
One row per day with scan metadata:
- System state (RISK-ON/RISK-OFF/REDUCED-RISK)
- SPY metrics (close, 50-SMA, slope)
- VIX metrics (close, 5-day change)
- Number of tickers screened/qualified

### 2. `screening_results`
One row per ticker per scan:
- Pass/fail status
- Current price and suggested strike
- Relative strength, IV Rank, etc.
- Failure reason (if failed)

### 3. `failure_mode_alerts`
Zero or more rows per scan:
- Failure mode type
- Severity level
- Action and message

## Query Examples

### Get Today's Qualified Tickers

```python
from src.data import Database

db = Database()
qualified = db.get_qualified_tickers()

for ticker_data in qualified:
    print(f"{ticker_data['ticker']}: "
          f"${ticker_data['current_price']:.2f} → "
          f"${ticker_data['max_safe_strike']:.2f}")
```

**Output:**
```
AAPL: $185.50 → $179.75
MSFT: $420.00 → $408.50
```

### Get Latest Scan Summary

```python
latest = db.get_latest_scan()

print(f"Date: {latest['scan_date']}")
print(f"System State: {latest['system_state']}")
print(f"Qualified: {len(latest['qualified_tickers'])}")

for ticker in latest['qualified_tickers']:
    print(f"  - {ticker['ticker']}: {ticker['discount_pct']:.1f}% OTM")
```

**Output:**
```
Date: 2025-01-31
System State: RISK-ON
Qualified: 2
  - AAPL: 3.1% OTM
  - MSFT: 2.7% OTM
```

### Get AAPL History (Last 30 Days)

```python
history = db.get_ticker_history('AAPL', days=30)

for day in history:
    status = "✓ PASSED" if day['passed'] else "✗ FAILED"
    print(f"{day['scan_date']}: {status}")
    if not day['passed']:
        print(f"  Reason: {day['failure_reason']}")
```

**Output:**
```
2025-01-31: ✗ FAILED
  Reason: Market regime failed
2025-01-30: ✓ PASSED
2025-01-29: ✓ PASSED
```

### Get Qualification Summary

Shows which tickers qualify most often:

```python
summary = db.get_qualification_summary(days=30)

for ticker_stats in summary:
    print(f"{ticker_stats['ticker']}: "
          f"{ticker_stats['times_qualified']}/{ticker_stats['times_screened']} "
          f"({ticker_stats['qualification_rate']:.0f}%)")
```

**Output:**
```
AAPL: 20/30 (66.7%)
MSFT: 18/30 (60.0%)
NVDA: 12/30 (40.0%)
```

### Get System State History

```python
history = db.get_system_state_history(days=7)

for day in history:
    print(f"{day['scan_date']}: {day['system_state']} "
          f"(SPY: ${day['spy_close']:.2f}, VIX: {day['vix_close']:.1f})")
```

**Output:**
```
2025-01-31: RISK-OFF (SPY: $572.30, VIX: 18.5)
2025-01-30: RISK-ON (SPY: $580.50, VIX: 15.2)
2025-01-29: RISK-ON (SPY: $578.20, VIX: 14.8)
```

### Get Alerts for Today

```python
alerts = db.get_alerts_for_date()

for alert in alerts:
    print(f"[{alert['severity']}] {alert['failure_mode']}")
    print(f"  {alert['message']}")
```

**Output:**
```
[CRITICAL] REGIME_TRANSITION
  SPY below 50-SMA (572.30 < 574.20); VIX spiking (+21.7% in 5 days)
[WARNING] VOLATILITY_EXPANSION
  VIX elevated (18.5 > 16.2) with increasing volume on SPY red days
```

## Advanced Usage

### Export to CSV

```python
# Export last 7 days to Excel
db.export_to_csv('results/weekly_report.csv', days=7)
```

### Custom SQL Queries

```python
with db.get_connection() as conn:
    cursor = conn.cursor()

    # Find tickers that qualified 3+ times this month
    cursor.execute("""
        SELECT ticker, COUNT(*) as times
        FROM screening_results
        WHERE passed = 1
          AND scan_id IN (
              SELECT scan_id FROM daily_scans
              WHERE scan_date >= '2025-01-01'
          )
        GROUP BY ticker
        HAVING times >= 3
        ORDER BY times DESC
    """)

    for row in cursor.fetchall():
        print(f"{row['ticker']}: {row['times']} times")
```

### Check if Scan Exists for Today

```python
from datetime import date

latest = db.get_latest_scan()

if latest and latest['scan_date'] == str(date.today()):
    print("Already scanned today!")
else:
    print("No scan yet - run the screener")
```

## Database Location

**Default:** `data/screening.db`

**Custom location:**
```python
db = Database(db_path='path/to/custom.db')
```

**In-memory (testing):**
```python
db = Database(db_path=':memory:')
```

## Integration with Daily Scanning

```python
# daily_scan.py
from src.screener import CreditSpreadScreener
from src.data import Database
import yfinance as yf
from datetime import date

def run_daily_scan():
    """Run daily scan and save to database."""

    # Check if already scanned today
    db = Database()
    latest = db.get_latest_scan()

    if latest and latest['scan_date'] == str(date.today()):
        print("Already scanned today - skipping")
        return

    # Run screener
    screener = CreditSpreadScreener()
    # ... fetch data ...
    results = screener.screen(...)

    # Save results
    scan_id = db.save_scan_results(results)

    # Print summary
    print(f"Scan complete! System state: {results['system_state']}")
    print(f"Qualified tickers: {len(results['qualified_tickers'])}")

    for ticker in results['qualified_tickers']:
        print(f"  - {ticker}")

if __name__ == '__main__':
    run_daily_scan()
```

## Troubleshooting

### "Table already exists" error

This is normal - the database auto-creates tables on first use and reuses them.

### "Foreign key constraint failed"

Make sure you're saving the entire scan result dict, not partial data.

### Database locked

SQLite doesn't support concurrent writes. Only run one scan at a time.

### Reset database

```python
import os
if os.path.exists('data/screening.db'):
    os.remove('data/screening.db')

# Database will be recreated on next use
db = Database()
```

## Next Steps

1. **Automate daily scanning** - See Phase 2 (daily_scan.py)
2. **Add notifications** - See Phase 3 (notifications)
3. **Build CLI query tool** - See Phase 5 (query.py)
4. **Create dashboard** - See Phase 6 (Streamlit)

All of these will use this database as the foundation.
