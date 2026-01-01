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

## Usage

```python
from src.screener import CreditSpreadScreener

# Initialize screener
screener = CreditSpreadScreener()

# Screen a list of tickers
candidates = screener.screen(['AAPL', 'MSFT', 'GOOGL', 'NVDA'])

# Check system state
state = screener.get_system_state()
```

## Directory Structure

```
src/
  gates/          # Four rule gates
  monitors/       # Failure mode detection
  utils/          # Data helpers
  screener.py     # Main orchestrator
tests/            # Unit tests
```

## Philosophy

This system is designed to **avoid negative expectancy regimes**, not to trade constantly.
If conditions are unfavorable, doing nothing is the correct output.
