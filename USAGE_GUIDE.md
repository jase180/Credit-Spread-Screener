# Credit Spread Screener - Usage Guide

## Overview

This system screens US equities for high-probability put credit spread candidates using four rule gates and continuous failure mode monitoring.

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd Credit-Spread-Screener

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Example

```bash
python example_usage.py
```

This will screen a default list of stocks and display:
- System state (RISK-ON / RISK-OFF / REDUCED-RISK)
- Qualified tickers
- Suggested strike zones
- Failure mode alerts

## System Architecture

### Four Gates (ALL must pass)

#### Gate 1: Market Regime (SPY)
- **Purpose**: Ensure market environment supports put credit spreads
- **Criteria**:
  - SPY close > 50-day SMA
  - 50-day SMA slope ≥ 0
  - No lower low in last 20 days
  - VIX 5-day change ≤ +10%
- **Failure**: No new trades allowed

#### Gate 2: Relative Strength
- **Purpose**: Find stocks that outperform SPY
- **Criteria**:
  - Stock 30-day return > SPY 30-day return
  - Stock close > stock 50-day SMA
  - Stock 50-day SMA slope ≥ 0
- **Why**: These stocks decline slower and recover faster

#### Gate 3: Structural Safety
- **Purpose**: Ensure strike placement has support
- **Criteria**: Strike must be below ALL of:
  - Stock 50-day SMA
  - Most recent higher low
  - Prior consolidation base low
  - Optional: 1.5 × ATR(14) below current price
- **Why**: Price memory - defended support zones

#### Gate 4: Event & Volatility
- **Purpose**: Avoid binary events and expanding volatility
- **Criteria**:
  - No earnings inside trade duration (30-45 days)
  - IV Rank between 20 and 60
  - IV 5-day change ≤ +5%
  - Down-day volume ≤ 20-day average
- **Why**: Prevent selling premium into deteriorating conditions

### Failure Mode Detection

#### Mode 1: Regime Transition (CRITICAL)
- **Trigger**: SPY breaks down OR VIX spikes > +15%
- **Action**: DISABLE NEW ENTRIES

#### Mode 2: Relative Strength Breakdown (WARNING)
- **Trigger**: Stock 10-day return < SPY AND below 50-SMA
- **Action**: REMOVE ticker from candidates

#### Mode 3: Correlated Breakdown (HIGH)
- **Trigger**: >40% of stocks fall below their 50-SMA
- **Action**: REDUCE GLOBAL RISK

#### Mode 4: Volatility Expansion (WARNING)
- **Trigger**: VIX > VIX 20-SMA AND increasing volume on red days
- **Action**: WARN - theta decay unreliable

## Usage Examples

### Basic Screening

```python
from src.screener import CreditSpreadScreener
import yfinance as yf

# Initialize screener
screener = CreditSpreadScreener()

# Fetch data
spy_data = yf.download('SPY', period='6mo', progress=False)
vix_data = yf.download('^VIX', period='6mo', progress=False)

stock_data = {
    'AAPL': yf.download('AAPL', period='6mo', progress=False),
    'MSFT': yf.download('MSFT', period='6mo', progress=False),
}

# Run screen
results = screener.screen(
    tickers=['AAPL', 'MSFT'],
    stock_data_dict=stock_data,
    spy_data=spy_data,
    vix_data=vix_data
)

# Check results
if results['allow_new_trades']:
    for ticker in results['qualified_tickers']:
        print(f"✓ {ticker} passed all gates")
```

### Check System State Only

```python
from src.screener import CreditSpreadScreener
import yfinance as yf

screener = CreditSpreadScreener()

# Load market data
spy_data = yf.download('SPY', period='6mo', progress=False)
vix_data = yf.download('^VIX', period='6mo', progress=False)

# Check regime
screener.last_spy_data = spy_data
screener.last_vix_data = vix_data

state = screener.get_system_state()

print(f"System State: {state['state']}")
print(f"Allow New Trades: {state['allow_new_trades']}")

for alert in state['alerts']:
    print(f"[{alert['severity']}] {alert['message']}")
```

### Get Strike Suggestions

```python
from src.screener import CreditSpreadScreener
import yfinance as yf

screener = CreditSpreadScreener()

# Fetch stock data
aapl_data = yf.download('AAPL', period='6mo', progress=False)

# Get strike suggestion
strike_info = screener.get_strike_suggestion('AAPL', aapl_data)

print(f"Current Price: ${strike_info['current_price']:.2f}")
print(f"Max Safe Strike: ${strike_info['max_safe_strike']:.2f}")
print(f"Discount: {strike_info['discount_pct']:.1f}%")
```

### Using Individual Gates

You can also use each gate independently:

```python
from src.gates import MarketRegimeGate, RelativeStrengthGate
import yfinance as yf

# Market Regime Gate
regime_gate = MarketRegimeGate()
spy_data = yf.download('SPY', period='6mo', progress=False)
vix_data = yf.download('^VIX', period='6mo', progress=False)

result = regime_gate.evaluate(spy_data, vix_data)

if result['pass']:
    print("✓ Market regime is healthy")
else:
    print(f"✗ Market regime failed: {result['reason']}")

# Relative Strength Gate
rs_gate = RelativeStrengthGate()
aapl_data = yf.download('AAPL', period='6mo', progress=False)

result = rs_gate.evaluate(aapl_data, spy_data, 'AAPL')

if result['pass']:
    print(f"✓ AAPL showing relative strength (+{result['details']['relative_strength']:.1f}%)")
else:
    print(f"✗ AAPL failed: {result['reason']}")
```

## Advanced Configuration

### Disable ATR Filter

```python
screener = CreditSpreadScreener(enable_atr_filter=False)
```

### Adjust Correlated Breakdown Threshold

```python
# More sensitive (trigger at 30% instead of 40%)
screener = CreditSpreadScreener(correlated_breakdown_threshold=0.30)
```

### Custom Gate Parameters

```python
from src.gates import MarketRegimeGate

# Custom SMA period
regime_gate = MarketRegimeGate(sma_period=100, lower_low_lookback=30)
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_gates.py -v

# Run with coverage
pytest tests/ --cov=src
```

## Design Principles

1. **Daily data only** - No intraday signals or VWAP
2. **No curve fitting** - Fixed rules, no optimization
3. **Modular design** - Each gate is independent and testable
4. **Failure-first** - Designed to avoid bad trades, not find perfect entries
5. **Do nothing is valid** - If conditions are unfavorable, output is empty

## Important Notes

### What This System Does NOT Do

- ❌ Generate entry signals (it's a screener, not a signal generator)
- ❌ Provide specific strike prices (gives safe zones only)
- ❌ Time entries (uses daily data, not intraday)
- ❌ Guarantee profitability (rules reduce risk, don't eliminate it)

### What This System DOES Do

- ✅ Filter out negative expectancy environments
- ✅ Identify stocks with institutional support
- ✅ Suggest strike zones below key support
- ✅ Alert when market regime changes
- ✅ Prevent trading into binary events

## Integration with Live Trading

This system is designed for **daily batch screening**, not real-time trading.

Recommended workflow:
1. Run screener once per day (after market close)
2. Review qualified tickers
3. Manually verify options chain and liquidity
4. Place trades with appropriate position sizing
5. Monitor failure modes daily
6. Exit positions if system state changes to RISK-OFF

## Common Issues

### "No tickers qualified"

This is expected behavior. The system is conservative by design.

Possible reasons:
- Market regime is unhealthy (SPY below 50-SMA)
- Stocks are underperforming SPY
- VIX is spiking
- No stocks meeting all four gates

**Action**: Wait for better conditions. Doing nothing is the correct output.

### "System in RISK-OFF mode"

The failure mode detector has identified dangerous conditions.

**Action**: Do not enter new trades. Review existing positions.

### Missing data for tickers

Ensure you're fetching enough historical data (recommend 6 months minimum):

```python
data = yf.download(ticker, period='6mo')
```

## Support & Contribution

- Report issues on GitHub
- Contributions welcome via pull requests
- Follow the existing code style and add tests

## License

See LICENSE file for details.
