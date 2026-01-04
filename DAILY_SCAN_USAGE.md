# Daily Scan Usage Guide

## Quick Start

After market close, run:
```bash
python daily_scan.py
```

This will:
1. Load tickers from `watchlist.txt` (111 stocks included)
2. Fetch market data (SPY, VIX, all stocks)
3. Fetch options data (IV Rank, earnings) if Tradier configured
4. Run 4-gate screening system
5. Save results to database (`data/screening.db`)
6. Display clean results in terminal

---

## Usage Examples

### Scan Default Watchlist
```bash
python daily_scan.py
```
Uses `watchlist.txt` automatically.

### Scan Specific Tickers
```bash
python daily_scan.py AAPL MSFT GOOGL NVDA
```
Quick one-off scans without editing watchlist.

### Use Custom Watchlist File
```bash
python daily_scan.py --file tech_stocks.txt
```
Scan tickers from a different file.

---

## Understanding the Output

### System Status
Shows market regime and whether new trades are allowed:
```
SYSTEM STATUS
  Market Regime: RISK-ON ✓    ← SPY healthy, VIX stable
  Allow New Trades: YES        ← Safe to enter new positions

  SPY: $683.17 (50-SMA: $680.42, +0.40%)
  VIX: -2.1% over 5 days
```

Or when markets are unhealthy:
```
SYSTEM STATUS
  Market Regime: RISK-OFF ⚠    ← SPY breakdown detected
  Allow New Trades: NO          ← Do not enter new positions
```

### Qualified Tickers
Shows stocks that passed all 4 gates:
```
QUALIFIED TICKERS (3)

  ✓ AAPL - $271.01
    ├─ Max Safe Strike: $262.00 (3.3% below current)  ← Sell puts here
    ├─ Relative Strength: +2.4% vs SPY                ← Outperforming
    ├─ Support: 50-SMA ($265.50), Higher Low ($263.20) ← Key levels
    └─ IV Rank: 35 (moderate premium)                  ← Good for selling
```

**Max Safe Strike** = Highest strike you should sell (below all support levels).

### Failed Tickers
Shows why stocks didn't qualify:
```
FAILED TICKERS (7)
  ✗ GOOGL: Underperforming SPY (-1.2%)     ← Failed relative strength gate
  ✗ AMD: IV Rank too high (65)             ← Failed volatility gate
  ✗ TSLA: Earnings in 8 days               ← Failed event gate
```

---

## Customizing Your Watchlist

Edit `watchlist.txt`:
```bash
# One ticker per line
# Lines starting with # are comments

AAPL
MSFT
GOOGL
# TSLA  ← Commented out = ignored
```

The default watchlist includes:
- **Tech:** AAPL, MSFT, GOOGL, NVDA, AMD, etc.
- **Finance:** JPM, BAC, WFC, V, MA, etc.
- **Healthcare:** UNH, JNJ, LLY, PFE, etc.
- **Consumer:** WMT, HD, MCD, NKE, etc.
- **Energy:** XOM, CVX, COP, etc.
- **And more...** (111 total)

**Tips:**
- Focus on liquid stocks (high volume, tight spreads)
- Avoid penny stocks (won't have good option chains)
- Include diverse sectors for more opportunities

---

## Typical Workflow

### Daily After Market Close
```bash
# 1. Run scan
python daily_scan.py

# 2. Review qualified tickers
#    - Check max safe strikes
#    - Verify support levels make sense
#    - Compare IV Rank across tickers

# 3. Open your broker
#    - Sell 30-45 DTE puts at or below max safe strike
#    - Target 1-2% premium return
#    - Use 5-10 wide spreads
```

### Weekly Review
```bash
# Check historical patterns
python -c "
from src.data import Database
db = Database()

# Most reliable setups (past 30 days)
summary = db.get_qualification_summary(days=30)
for ticker in summary[:10]:
    print(f\"{ticker['ticker']}: {ticker['qualification_rate']:.0f}% qualification rate\")
"
```

---

## When System is RISK-OFF

**Do NOT enter new trades** when you see:
```
Market Regime: RISK-OFF ⚠
Allow New Trades: NO
```

This means:
- SPY broke below 50-SMA, or
- SPY made lower low, or
- VIX spiked >10% in 5 days

**What to do:**
- Manage existing positions (roll down, close winners)
- Wait for RISK-ON before entering new trades
- System designed to **avoid negative expectancy regimes**

---

## Troubleshooting

### "Watchlist file not found"
Create `watchlist.txt` or run with tickers directly:
```bash
python daily_scan.py AAPL MSFT GOOGL
```

### "Could not fetch SPY/VIX data"
- Check internet connection
- yfinance may be down (retry later)

### "Tradier API unavailable"
- Check `.env` file has `TRADIER_API_KEY`
- Script will continue without IV Rank data (warning shown)

### Scan takes too long
Reduce watchlist size:
- 10 tickers: ~10 seconds
- 50 tickers: ~1 minute
- 100+ tickers: ~2-3 minutes

---

## Next Steps

After using for a few days, consider:
1. **Telegram notifications** - Get alerted when qualified tickers appear
2. **Scheduled runs** - Automate daily scans with cron
3. **CLI query tool** - Analyze historical patterns
4. **Custom filters** - Only show high IV Rank, or specific sectors

Let the system run for 7-10 days to build historical data, then use the database queries to find patterns!
