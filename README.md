# Put Credit Spread Screener

A rule-based screening and risk-control system for 30-45 DTE put credit spreads.

## System Design

This system uses **four gates** that must all pass for a ticker to qualify:

1. **Market Regime Gate** - SPY must be in a healthy bullish regime
2. **Relative Strength Gate** - Stock must outperform SPY
3. **Structural Safety Gate** - Strike location must be below key support zones
4. **Event & Volatility Gate** - No binary events, moderate IV

## Failure Mode Detection

The system continuously monitors for:
- Regime transitions (SPY breakdown)
- Relative strength breakdown
- Correlated market liquidation
- Volatility expansion

When failure modes trigger, the system reduces or halts new entries.

## Quick Start

**Daily scanning (recommended):**
```bash
python daily_scan.py
```

This will:
- Load 111 liquid stocks from `watchlist.txt`
- Fetch market data and run all 4 gates
- Save to database and display results

**See:** [`DAILY_SCAN_USAGE.md`](DAILY_SCAN_USAGE.md) for complete guide

---

## Advanced Usage

### Programmatic Screening

```python
from src.screener import CreditSpreadScreener
from src.data import Database

# Initialize screener and database
screener = CreditSpreadScreener()
db = Database()

# Run screening
results = screener.screen(...)
db.save_scan_results(results)

# Query historical data
history = db.get_ticker_history('AAPL', days=30)
summary = db.get_qualification_summary(days=30)
```

**See:**
- [`DAILY_SCAN_USAGE.md`](DAILY_SCAN_USAGE.md) - Daily workflow guide
- [`DATABASE_USAGE.md`](DATABASE_USAGE.md) - Database query examples
- `example_database.py` - Code examples

## Directory Structure

```
src/
  gates/          # Four rule gates
  monitors/       # Failure mode detection
  data/           # Data providers (options, database)
  utils/          # Data helpers
  screener.py     # Main orchestrator
tests/            # Unit tests
data/             # SQLite database (created automatically)
```

## Philosophy

This system is designed to **avoid negative expectancy regimes**, not to trade constantly.
If conditions are unfavorable, doing nothing is the correct output.
