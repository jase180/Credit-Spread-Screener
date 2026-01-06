"""
Strike Selector - Optimal Put Credit Spread Strike Selection

Analyzes options chains and suggests optimal put credit spread strikes
based on structural safety, probability of profit, and liquidity.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from src.data.tradier_provider import TradierProvider


class StrikeSelector:
    """
    Selects optimal put credit spread strikes for qualified tickers.

    Uses structural safety levels from screening gates to identify
    strike prices with high probability of profit and acceptable risk/reward.
    """

    def __init__(
        self,
        tradier_provider: TradierProvider,
        min_dte: int = 30,
        max_dte: int = 45,
        spread_width: float = 5.0,
        min_delta: float = -0.30,
        max_delta: float = -0.15,
        min_volume: int = 10,
        min_open_interest: int = 50
    ):
        """
        Initialize strike selector.

        Args:
            tradier_provider: Tradier API provider for options data
            min_dte: Minimum days to expiration (default 30)
            max_dte: Maximum days to expiration (default 45)
            spread_width: Width of credit spread in dollars (default 5.0)
            min_delta: Minimum delta for sell strike (default -0.30, ~70% PoP)
            max_delta: Maximum delta for sell strike (default -0.15, ~85% PoP)
            min_volume: Minimum daily volume for liquidity (default 10)
            min_open_interest: Minimum open interest for liquidity (default 50)
        """
        self.tradier = tradier_provider
        self.min_dte = min_dte
        self.max_dte = max_dte
        self.spread_width = spread_width
        self.min_delta = min_delta
        self.max_delta = max_delta
        self.min_volume = min_volume
        self.min_open_interest = min_open_interest

    def filter_expirations_by_dte(self, expirations: List[str]) -> List[tuple]:
        """
        Filter expirations to target DTE range.

        Args:
            expirations: List of expiration date strings (YYYY-MM-DD)

        Returns:
            List of tuples (expiration_str, dte) within DTE range
        """
        today = datetime.now()
        valid_expirations = []

        for exp_str in expirations:
            exp_date = datetime.strptime(exp_str, '%Y-%m-%d')
            dte = (exp_date - today).days

            if self.min_dte <= dte <= self.max_dte:
                valid_expirations.append((exp_str, dte))

        # Sort by DTE
        valid_expirations.sort(key=lambda x: x[1])
        return valid_expirations

    def filter_safe_strikes(
        self,
        puts: List[Dict],
        max_safe_strike: float,
        current_price: float
    ) -> List[Dict]:
        """
        Keep only puts below structural safety max strike.

        Args:
            puts: List of put option dictionaries
            max_safe_strike: Maximum safe strike from structural safety gate
            current_price: Current stock price

        Returns:
            Filtered list of puts with strikes below max_safe_strike
        """
        safe_puts = []
        for put in puts:
            strike = put.get('strike')
            if strike and strike <= max_safe_strike and strike < current_price:
                safe_puts.append(put)
        return safe_puts

    def filter_by_delta(self, puts: List[Dict]) -> List[Dict]:
        """
        Filter puts with delta in target range.

        Args:
            puts: List of put option dictionaries

        Returns:
            Filtered list of puts with delta between min_delta and max_delta
        """
        filtered = []
        for put in puts:
            greeks = put.get('greeks', {})
            if greeks:
                delta = greeks.get('delta')
                if delta is not None and self.min_delta <= delta <= self.max_delta:
                    filtered.append(put)
        return filtered

    def filter_by_liquidity(self, puts: List[Dict]) -> List[Dict]:
        """
        Filter puts by minimum liquidity requirements.

        Args:
            puts: List of put option dictionaries

        Returns:
            Filtered list of puts meeting liquidity requirements
        """
        filtered = []
        for put in puts:
            volume = put.get('volume') or 0
            open_interest = put.get('open_interest') or 0

            if volume >= self.min_volume or open_interest >= self.min_open_interest:
                filtered.append(put)
        return filtered

    def find_protection_put(self, puts: List[Dict], sell_strike: float) -> Optional[Dict]:
        """
        Find the buy put (protection) for a given sell strike.

        Args:
            puts: List of put option dictionaries
            sell_strike: Strike price of the put we're selling

        Returns:
            Best protection put (strike = sell_strike - spread_width), or None
        """
        target_strike = sell_strike - self.spread_width

        # Find put closest to target strike
        best_put = None
        min_diff = float('inf')

        for put in puts:
            strike = put.get('strike')
            if strike:
                diff = abs(strike - target_strike)
                if diff < min_diff:
                    min_diff = diff
                    best_put = put

        return best_put

    def calculate_spread_metrics(
        self,
        sell_put: Dict,
        buy_put: Dict,
        support_level: float
    ) -> Dict[str, Any]:
        """
        Calculate spread metrics: credit, max profit, max loss, ROI, breakeven.

        Args:
            sell_put: Put option we're selling
            buy_put: Put option we're buying (protection)
            support_level: Key support level (for safety distance)

        Returns:
            Dictionary with all spread metrics
        """
        sell_strike = sell_put.get('strike', 0)
        buy_strike = buy_put.get('strike', 0)

        # Use mid price between bid/ask
        sell_bid = sell_put.get('bid') or 0
        sell_ask = sell_put.get('ask') or 0
        sell_mid = (sell_bid + sell_ask) / 2 if sell_bid and sell_ask else 0

        buy_bid = buy_put.get('bid') or 0
        buy_ask = buy_put.get('ask') or 0
        buy_mid = (buy_bid + buy_ask) / 2 if buy_bid and buy_ask else 0

        # Credit = premium collected from selling - premium paid for buying
        credit = sell_mid - buy_mid

        # Spread width
        width = sell_strike - buy_strike

        # Max profit = credit received (per share)
        max_profit = credit

        # Max loss = spread width - credit (per share)
        max_loss = width - credit

        # ROI = max profit / max loss
        roi = (max_profit / max_loss * 100) if max_loss > 0 else 0

        # Breakeven = sell strike - credit
        breakeven = sell_strike - credit

        # Distance from support
        distance_from_support = sell_strike - support_level

        # Probability of profit (from delta)
        greeks = sell_put.get('greeks', {})
        delta = greeks.get('delta')
        pop = (1 + delta) * 100 if delta else None  # Convert delta to PoP

        return {
            'sell_strike': sell_strike,
            'buy_strike': buy_strike,
            'sell_bid': sell_bid,
            'sell_ask': sell_ask,
            'sell_mid': sell_mid,
            'buy_bid': buy_bid,
            'buy_ask': buy_ask,
            'buy_mid': buy_mid,
            'credit': credit,
            'spread_width': width,
            'max_profit': max_profit,
            'max_profit_dollars': max_profit * 100,  # Per contract
            'max_loss': max_loss,
            'max_loss_dollars': max_loss * 100,  # Per contract
            'roi': roi,
            'breakeven': breakeven,
            'distance_from_support': distance_from_support,
            'delta': delta,
            'pop': pop,
            'sell_volume': sell_put.get('volume', 0),
            'sell_open_interest': sell_put.get('open_interest', 0),
            'buy_volume': buy_put.get('volume', 0),
            'buy_open_interest': buy_put.get('open_interest', 0),
        }

    def calculate_liquidity_score(self, spread_metrics: Dict) -> float:
        """
        Calculate liquidity score (0-100) based on volume and open interest.

        Args:
            spread_metrics: Spread metrics dictionary

        Returns:
            Liquidity score (0-100)
        """
        sell_vol = spread_metrics.get('sell_volume', 0)
        sell_oi = spread_metrics.get('sell_open_interest', 0)
        buy_vol = spread_metrics.get('buy_volume', 0)
        buy_oi = spread_metrics.get('buy_open_interest', 0)

        # Average volume and OI across both legs
        avg_volume = (sell_vol + buy_vol) / 2
        avg_oi = (sell_oi + buy_oi) / 2

        # Score based on thresholds
        # Volume: 0-10 = poor, 10-50 = ok, 50-100 = good, 100+ = excellent
        # OI: 0-50 = poor, 50-200 = ok, 200-500 = good, 500+ = excellent

        vol_score = min(100, (avg_volume / 100) * 100) * 0.4
        oi_score = min(100, (avg_oi / 500) * 100) * 0.6

        return vol_score + oi_score

    def rank_spreads(self, spreads: List[Dict]) -> List[Dict]:
        """
        Rank spreads by safety, ROI, and liquidity.

        Args:
            spreads: List of spread dictionaries with metrics

        Returns:
            Sorted list of spreads (best first)
        """
        # Calculate composite score for each spread
        for spread in spreads:
            # Safety score: Distance from support (higher = safer)
            distance = spread.get('distance_from_support', 0)
            safety_score = min(100, (distance / 10) * 100)  # $10 distance = 100 score

            # ROI score (capped at 50% ROI = 100 score)
            roi = spread.get('roi', 0)
            roi_score = min(100, (roi / 50) * 100)

            # Liquidity score (calculated above)
            liquidity_score = self.calculate_liquidity_score(spread)

            # Weighted composite score
            spread['safety_score'] = safety_score
            spread['roi_score'] = roi_score
            spread['liquidity_score'] = liquidity_score
            spread['composite_score'] = (
                0.5 * safety_score +      # Safety is most important
                0.3 * roi_score +          # ROI is important
                0.2 * liquidity_score      # Liquidity matters but less critical
            )

        # Sort by composite score (descending)
        spreads.sort(key=lambda x: x['composite_score'], reverse=True)

        return spreads

    def suggest_strikes(
        self,
        ticker: str,
        current_price: float,
        max_safe_strike: float,
        support_level: float,
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Generate top N put credit spread recommendations.

        Args:
            ticker: Stock ticker symbol
            current_price: Current stock price
            max_safe_strike: Maximum safe strike from structural safety gate
            support_level: Key support level (50-SMA, higher low, etc.)
            top_n: Number of top recommendations to return

        Returns:
            Dictionary containing:
                - ticker: Stock ticker
                - current_price: Current price
                - max_safe_strike: Max safe strike
                - support_level: Support level
                - recommendations: List of top N spread recommendations
                - error: Error message if failed
        """
        try:
            # Get expirations
            expirations = self.tradier.get_expirations(ticker)
            if not expirations:
                return {
                    'ticker': ticker,
                    'error': 'No options expirations available'
                }

            # Filter to target DTE range
            valid_expirations = self.filter_expirations_by_dte(expirations)
            if not valid_expirations:
                return {
                    'ticker': ticker,
                    'error': f'No expirations in {self.min_dte}-{self.max_dte} DTE range'
                }

            # Collect all spread candidates across all expirations
            all_spreads = []

            for exp_str, dte in valid_expirations:
                # Get put chain
                puts = self.tradier.get_put_options(ticker, exp_str)
                if not puts:
                    continue

                # Filter by safety
                safe_puts = self.filter_safe_strikes(puts, max_safe_strike, current_price)
                if not safe_puts:
                    continue

                # Filter by delta
                delta_filtered = self.filter_by_delta(safe_puts)
                if not delta_filtered:
                    continue

                # Filter by liquidity
                liquid_puts = self.filter_by_liquidity(delta_filtered)

                # Generate spread candidates
                for sell_put in liquid_puts:
                    sell_strike = sell_put.get('strike')
                    if not sell_strike:
                        continue

                    # Find protection put
                    buy_put = self.find_protection_put(puts, sell_strike)
                    if not buy_put:
                        continue

                    # Calculate metrics
                    metrics = self.calculate_spread_metrics(sell_put, buy_put, support_level)

                    # Skip if credit is too low
                    if metrics['credit'] <= 0.10:  # Skip if less than $0.10 credit
                        continue

                    # Add expiration info
                    metrics['expiration'] = exp_str
                    metrics['dte'] = dte

                    all_spreads.append(metrics)

            if not all_spreads:
                return {
                    'ticker': ticker,
                    'current_price': current_price,
                    'max_safe_strike': max_safe_strike,
                    'support_level': support_level,
                    'error': 'No valid spread candidates found (check delta/liquidity filters)'
                }

            # Rank spreads
            ranked_spreads = self.rank_spreads(all_spreads)

            # Return top N
            return {
                'ticker': ticker,
                'current_price': current_price,
                'max_safe_strike': max_safe_strike,
                'support_level': support_level,
                'recommendations': ranked_spreads[:top_n],
                'total_candidates': len(all_spreads)
            }

        except Exception as e:
            return {
                'ticker': ticker,
                'error': f'Error generating recommendations: {str(e)}'
            }
