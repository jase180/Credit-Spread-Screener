"""
Tradier Options Data Provider

Implements the OptionsDataProvider interface using the Tradier API.

API Documentation: https://documentation.tradier.com/brokerage-api

Setup:
1. Create Tradier account (developer sandbox OR brokerage account)
   - Developer: https://developer.tradier.com/ (15-min delayed data)
   - Brokerage: Tradier brokerage account (real-time data)
2. Get API token from your dashboard
3. Set TRADIER_API_KEY and TRADIER_USE_SANDBOX environment variables

Both sandbox and production work with this provider.
"""

import os
import requests
from datetime import datetime
from typing import Optional, Dict, Any
import numpy as np

from src.data.options_provider import OptionsDataProvider


class TradierProvider(OptionsDataProvider):
    """
    Tradier API implementation of options data provider.

    Works with both Tradier sandbox (delayed) and production (real-time) APIs.
    """

    # API endpoints
    SANDBOX_URL = "https://sandbox.tradier.com/v1"
    PRODUCTION_URL = "https://api.tradier.com/v1"

    def __init__(self, api_key: Optional[str] = None, use_sandbox: bool = True):
        """
        Initialize Tradier provider.

        Args:
            api_key: Tradier API key. If None, reads from TRADIER_API_KEY env var.
            use_sandbox: True for sandbox API (15-min delayed), False for production API (real-time)
        """
        self.api_key = api_key or os.getenv('TRADIER_API_KEY')
        self.base_url = self.SANDBOX_URL if use_sandbox else self.PRODUCTION_URL

        if not self.api_key:
            raise ValueError(
                "Tradier API key required. Set TRADIER_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        })

    def is_available(self) -> bool:
        """Check if Tradier API is accessible."""
        try:
            response = self.session.get(f'{self.base_url}/markets/quotes?symbols=SPY')
            return response.status_code == 200
        except Exception:
            return False

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """
        Make API request to Tradier.

        Args:
            endpoint: API endpoint (e.g., '/markets/quotes')
            params: Query parameters

        Returns:
            Response JSON or None if request failed
        """
        try:
            url = f'{self.base_url}{endpoint}'
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Tradier API error for {endpoint}: {e}")
            return None

    def get_current_iv(self, ticker: str) -> Optional[float]:
        """
        Get current implied volatility from ATM options.

        Calculates IV by averaging the IV of ATM call and put options
        with ~30-45 days to expiration.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current IV as percentage (e.g., 35.5) or None
        """
        # Get current stock price
        quote = self._make_request('/markets/quotes', {'symbols': ticker})
        if not quote or 'quotes' not in quote:
            return None

        quotes = quote['quotes']
        if 'quote' not in quotes:
            return None

        stock_price = quotes['quote'].get('last')
        if not stock_price:
            return None

        # Get options expirations
        expirations_data = self._make_request('/markets/options/expirations', {'symbol': ticker})
        if not expirations_data or 'expirations' not in expirations_data:
            return None

        expirations = expirations_data['expirations'].get('date', [])
        if not expirations:
            return None

        # Find expiration closest to 30-45 DTE
        target_date = datetime.now()
        best_expiration = None
        target_dte = 37  # Middle of 30-45 range

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
            dte = (exp_date - target_date).days

            if 30 <= dte <= 45:
                if best_expiration is None or abs(dte - target_dte) < abs(
                    (datetime.strptime(best_expiration, '%Y-%m-%d') - target_date).days - target_dte
                ):
                    best_expiration = exp_str

        if not best_expiration:
            # Fall back to closest expiration if nothing in range
            best_expiration = expirations[0] if expirations else None

        if not best_expiration:
            return None

        # Get options chain for this expiration
        chain_data = self._make_request('/markets/options/chains', {
            'symbol': ticker,
            'expiration': best_expiration,
            'greeks': 'true'
        })

        if not chain_data or 'options' not in chain_data:
            return None

        options = chain_data['options'].get('option', [])
        if not options:
            return None

        # Find ATM options and extract IV
        ivs = []
        for option in options:
            strike = option.get('strike')
            if not strike:
                continue

            # Check if near ATM (within 5% of stock price)
            if abs(strike - stock_price) / stock_price <= 0.05:
                greeks = option.get('greeks')
                if greeks and 'mid_iv' in greeks:
                    iv = greeks['mid_iv']
                    if iv and iv > 0:
                        ivs.append(iv * 100)  # Convert to percentage

        if ivs:
            return np.mean(ivs)

        return None

    def get_iv_rank(self, ticker: str) -> Optional[float]:
        """
        Calculate IV Rank for a ticker.

        IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) * 100

        Note: Tradier doesn't provide IV Rank directly, so we calculate it
        from historical IV data. This requires fetching options data over time,
        which can be slow. For production use, consider caching or using a
        service that provides pre-calculated IV Rank.

        Args:
            ticker: Stock ticker symbol

        Returns:
            IV Rank (0-100) or None if unavailable
        """
        # For now, we'll use current IV and make a simplified calculation
        # A full implementation would need historical IV data
        # You may want to use a different service for IV Rank (like Market Chameleon)

        current_iv = self.get_current_iv(ticker)
        if current_iv is None:
            return None

        # TODO: Implement proper IV Rank calculation with historical data
        # For now, return a placeholder based on current IV level
        # This is NOT accurate - just a temporary implementation

        # Rough approximation: normalize IV assuming typical range of 15-60%
        # This should be replaced with actual 52-week high/low IV data
        iv_rank_approx = ((current_iv - 15) / (60 - 15)) * 100
        iv_rank_approx = max(0, min(100, iv_rank_approx))  # Clamp to 0-100

        print(f"WARNING: IV Rank for {ticker} is approximated. Current IV: {current_iv:.1f}%")
        print(f"         For accurate IV Rank, use Market Chameleon or similar service.")

        return iv_rank_approx

    def get_earnings_date(self, ticker: str) -> Optional[datetime]:
        """
        Get next earnings date for a ticker.

        Note: Tradier provides corporate calendar events, but earnings dates
        may not always be available in advance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Next earnings date or None if unavailable
        """
        # Tradier's corporate calendar endpoint
        # This may not have future earnings for all stocks
        calendar = self._make_request('/markets/calendar', {'month': datetime.now().month, 'year': datetime.now().year})

        if not calendar or 'calendar' not in calendar:
            return None

        # Parse calendar for earnings events
        # Note: Tradier's calendar API is limited - for production use,
        # consider using Earnings Whispers, Yahoo Finance, or similar

        # TODO: Implement proper earnings date extraction from Tradier calendar
        # For now, return None and recommend using a dedicated earnings calendar service

        print(f"WARNING: Earnings dates not fully implemented for Tradier.")
        print(f"         Consider using Earnings Whispers API or Yahoo Finance for {ticker}.")

        return None

    def get_quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote for a ticker.

        Useful helper method for additional data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Quote data dictionary or None
        """
        quote = self._make_request('/markets/quotes', {'symbols': ticker})
        if quote and 'quotes' in quote and 'quote' in quote['quotes']:
            return quote['quotes']['quote']
        return None
