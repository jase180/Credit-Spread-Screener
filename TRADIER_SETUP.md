# Tradier API Setup Guide

This guide shows you how to set up the Tradier API for options data.

## Why Tradier?

- **Free API access** with market data
- Unlimited API calls
- Options data with IV calculations
- Perfect for daily screening

## Which API Should You Use?

**Sandbox (Developer Account)**
- 15-minute delayed data
- No brokerage account needed
- Sign up at https://developer.tradier.com/

**Production (Brokerage Account)**
- Real-time data
- Requires Tradier brokerage account (can be unfunded)
- Same API, just real-time instead of delayed

**For daily screening after market close**: Both work identically. Use whichever is easier for you.

## Step 1: Create Tradier Account

**Option A - Sandbox (15-min delay):**
1. Go to https://developer.tradier.com/
2. Click "Sign Up"
3. Fill out the registration form
4. Verify your email

**Option B - Production (real-time):**
1. Open a Tradier brokerage account
2. Account can remain unfunded
3. Get API access from brokerage dashboard

## Step 2: Get Your API Key

**For Sandbox:**
1. Log in to https://developer.tradier.com/
2. Go to your **Dashboard**
3. Under "API Access", you'll see your **Access Token**
4. Copy this token

**For Production:**
1. Log in to your Tradier brokerage account
2. Go to API settings in your account dashboard
3. Copy your production API token

**Note**: Sandbox and production have different API keys!

## Step 3: Configure the Screener

### Option A: Using .env file (Recommended)

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env and paste your API key
nano .env  # or use any text editor
```

**For Sandbox:**
```
TRADIER_API_KEY=your_sandbox_api_key_here
TRADIER_USE_SANDBOX=true
```

**For Production:**
```
TRADIER_API_KEY=your_production_api_key_here
TRADIER_USE_SANDBOX=false
```

### Option B: Set environment variable

**Linux/Mac:**
```bash
export TRADIER_API_KEY="your_api_key_here"
```

**Windows (Command Prompt):**
```cmd
set TRADIER_API_KEY=your_api_key_here
```

**Windows (PowerShell):**
```powershell
$env:TRADIER_API_KEY="your_api_key_here"
```

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Test the Connection

```bash
python example_tradier_usage.py
```

You should see:
```
✓ Tradier provider initialized
✓ Tradier API is accessible

AAPL:
  Last Price: $185.50
  Current IV: 28.5%
  IV Rank: 45.2
  ...
```

## Using Tradier in the Screener

```python
from src.screener import CreditSpreadScreener
from src.data import TradierProvider
import yfinance as yf

# Initialize Tradier provider
tradier = TradierProvider()

# Fetch market data (still use yfinance for price data)
spy_data = yf.download('SPY', period='6mo', progress=False)
vix_data = yf.download('^VIX', period='6mo', progress=False)
stock_data = {
    'AAPL': yf.download('AAPL', period='6mo', progress=False)
}

# Get options data from Tradier
iv_rank_dict = {
    'AAPL': tradier.get_iv_rank('AAPL')
}

earnings_dates = {
    'AAPL': tradier.get_earnings_date('AAPL')
}

# Run screener with Tradier data
screener = CreditSpreadScreener()
results = screener.screen(
    tickers=['AAPL'],
    stock_data_dict=stock_data,
    spy_data=spy_data,
    vix_data=vix_data,
    iv_rank_dict=iv_rank_dict,
    earnings_dates_dict=earnings_dates
)
```

## Troubleshooting

### "ValueError: Tradier API key required"

**Solution**: Make sure your `.env` file exists and contains your API key:
```bash
cat .env  # Should show: TRADIER_API_KEY=...
```

### "Cannot connect to Tradier API"

**Possible causes**:
1. **Invalid API key** - Check you copied it correctly
2. **Network issue** - Try accessing the appropriate endpoint in browser
3. **Mismatched API key/endpoint** - Sandbox key only works with sandbox endpoint, production key only works with production endpoint
4. **Check TRADIER_USE_SANDBOX setting** - Make sure it matches your API key type

### "IV Rank is approximated" warning

**Explanation**: Tradier doesn't provide IV Rank directly. The current implementation uses a simplified calculation.

**Solutions**:
1. **Ignore it** - The approximation is often good enough for screening
2. **Use Market Chameleon** - They provide accurate IV Rank ($50/mo)
3. **Disable IV Rank filter** - Modify the screener to skip this check

### Earnings dates not available

**Explanation**: Tradier's calendar API has limited coverage.

**Solutions**:
1. **Use Yahoo Finance** for earnings dates (free, via yfinance)
2. **Use Earnings Whispers API** ($50/mo for real-time data)
3. **Skip earnings filter** - Pass `None` for `earnings_dates_dict`

## API Rate Limits

**Sandbox Account**:
- **120 requests per minute**
- **Unlimited daily requests**
- Should be more than enough for daily screening

**Production Account** (if you upgrade):
- **60 requests per minute** (standard)
- **120+ requests per minute** (premium tiers)

## Sandbox vs Production Data

| Feature | Sandbox (Free) | Production (Paid) |
|---------|---------------|-------------------|
| Real-time quotes | ✓ 15-min delayed | ✓ Real-time |
| Options chains | ✓ Yes | ✓ Yes |
| Historical data | ✓ Yes | ✓ Yes |
| Order placement | ✗ Paper only | ✓ Live trading |
| Cost | **FREE** | Requires brokerage account |

**For screening**: Sandbox is perfect. 15-minute delay doesn't matter for daily screening.

## Next Steps

1. ✅ Test the connection with `example_tradier_usage.py`
2. ✅ Integrate into your daily screening workflow
3. ✅ Consider upgrading to production if you want real-time data
4. ✅ Add caching (Phase 1, Task 2) to avoid redundant API calls

## Additional Resources

- **API Docs**: https://documentation.tradier.com/brokerage-api
- **Support**: support@tradier.com
- **Status**: https://status.tradier.com/
