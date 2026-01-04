"""
Unit Tests for Gate Modules

These tests demonstrate how to test individual gates with synthetic data.

Run with: python -m pytest tests/
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.gates import (
    MarketRegimeGate,
    RelativeStrengthGate,
    StructuralSafetyGate,
    EventVolatilityGate
)


def create_mock_price_data(
    days: int = 100,
    start_price: float = 100.0,
    trend: str = 'up',
    volatility: float = 0.02,
    seed: int = 42
) -> pd.DataFrame:
    """
    Create synthetic OHLCV data for testing.

    Args:
        days: Number of days of data
        start_price: Starting price
        trend: 'up', 'down', or 'flat'
        volatility: Daily volatility (std dev)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV data (with MultiIndex columns like yfinance)
    """
    np.random.seed(seed)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate price series based on trend
    if trend == 'up':
        # Smooth uptrend - linear increase with small oscillations
        # This ensures higher lows throughout
        base_prices = start_price * (1 + 0.003 * np.arange(days))  # 0.3% daily gain
        # Add controlled oscillation that maintains higher lows
        oscillation = np.sin(np.arange(days) / 5) * volatility * start_price
        prices = base_prices + oscillation
        # Ensure strictly higher lows by taking cumulative max of (price * 0.99)
        low_floor = np.maximum.accumulate(prices * 0.99)
        prices = np.maximum(prices, low_floor)
    elif trend == 'down':
        base_prices = start_price * (1 - 0.003 * np.arange(days))
        oscillation = np.sin(np.arange(days) / 5) * volatility * start_price
        prices = base_prices + oscillation
    else:
        # Flat with noise
        prices = start_price * (1 + np.random.normal(0, volatility, days))

    # Generate OHLCV with proper structure
    # For uptrend, ensure Low values also form higher lows
    if trend == 'up':
        # Low should be below close but also maintain higher lows pattern
        low_prices = prices * 0.99  # 1% below close
        low_prices = np.maximum.accumulate(low_prices * 0.995)  # Ensure higher lows
    else:
        low_prices = prices * (1 + np.random.uniform(-0.01, 0.0, days))

    data = pd.DataFrame({
        'Open': prices * (1 + np.random.uniform(-0.005, 0.005, days)),
        'High': prices * (1 + np.random.uniform(0.0, 0.01, days)),
        'Low': low_prices,
        'Close': prices,
        'Volume': np.random.randint(1_000_000, 10_000_000, days)
    }, index=dates)

    return data


class TestMarketRegimeGate:
    """Test cases for the Market Regime Gate."""

    def test_bullish_regime_passes(self):
        """Test that a healthy bullish regime passes."""
        # Create uptrending SPY data
        spy_data = create_mock_price_data(days=100, trend='up')

        # Create stable VIX data
        vix_data = create_mock_price_data(
            days=100,
            start_price=15.0,
            trend='flat',
            volatility=0.01
        )

        gate = MarketRegimeGate()
        result = gate.evaluate(spy_data, vix_data)

        assert result['pass'] is True
        assert result['details']['above_sma'] is True
        assert result['details']['sma_rising'] is True

    def test_bearish_regime_fails(self):
        """Test that a bearish regime fails."""
        # Create downtrending SPY data
        spy_data = create_mock_price_data(days=100, trend='down')

        # Create stable VIX data
        vix_data = create_mock_price_data(
            days=100,
            start_price=15.0,
            trend='flat',
            volatility=0.01
        )

        gate = MarketRegimeGate()
        result = gate.evaluate(spy_data, vix_data)

        # Should fail due to downtrend
        assert result['pass'] is False

    def test_vix_spike_fails(self):
        """Test that a VIX spike causes failure."""
        # Create stable SPY data
        spy_data = create_mock_price_data(days=100, trend='up')

        # Create VIX data with recent spike
        vix_data = create_mock_price_data(
            days=100,
            start_price=15.0,
            trend='flat',
            volatility=0.01
        )

        # Spike VIX in last 5 days (use .loc to avoid chained assignment warning)
        vix_data.loc[vix_data.index[-1], 'Close'] = vix_data['Close'].iloc[-6] * 1.15  # +15%

        gate = MarketRegimeGate()
        result = gate.evaluate(spy_data, vix_data)

        assert result['pass'] is False
        assert result['details']['vix_stable'] is False


class TestRelativeStrengthGate:
    """Test cases for the Relative Strength Gate."""

    def test_outperforming_stock_passes(self):
        """Test that a stock outperforming SPY passes."""
        # Create SPY data with moderate gain
        spy_data = create_mock_price_data(days=100, trend='up', start_price=100.0, seed=42)

        # Create stock data starting from same base but with stronger uptrend
        # Use higher drift rate to ensure it outperforms over 30-day period
        stock_data = create_mock_price_data(days=100, trend='up', start_price=100.0, seed=100)

        # Apply a gradient multiplier - stronger gain in recent days
        # This ensures 30-day return is higher while maintaining realistic data
        gradient = np.linspace(1.0, 1.25, 100)  # 0% to 25% boost over time
        stock_data['Close'] = stock_data['Close'] * gradient
        stock_data['Low'] = stock_data['Low'] * gradient
        stock_data['High'] = stock_data['High'] * gradient
        stock_data['Open'] = stock_data['Open'] * gradient

        gate = RelativeStrengthGate()
        result = gate.evaluate(stock_data, spy_data, 'TEST')

        assert result['pass'] is True
        assert result['details']['outperforms_spy'] is True

    def test_underperforming_stock_fails(self):
        """Test that a stock underperforming SPY fails."""
        # Create SPY data with gain
        spy_data = create_mock_price_data(days=100, trend='up', volatility=0.01)

        # Create stock data with weaker performance
        stock_data = create_mock_price_data(days=100, trend='flat', volatility=0.015)

        gate = RelativeStrengthGate()
        result = gate.evaluate(stock_data, spy_data, 'TEST')

        assert result['pass'] is False
        assert result['details']['outperforms_spy'] is False


class TestStructuralSafetyGate:
    """Test cases for the Structural Safety Gate."""

    def test_strike_below_support_passes(self):
        """Test that a strike below all support levels passes."""
        stock_data = create_mock_price_data(days=100, trend='up', start_price=150.0)

        gate = StructuralSafetyGate(use_atr_filter=False)

        # Get the safe strike zone
        result = gate.evaluate(stock_data, 'TEST', hypothetical_strike=None)

        # Now test a strike below the safe zone
        safe_strike = result['suggested_strike_max']
        test_strike = safe_strike * 0.95  # 5% below safe zone

        result = gate.evaluate(stock_data, 'TEST', hypothetical_strike=test_strike)

        assert result['pass'] is True

    def test_strike_above_sma_fails(self):
        """Test that a strike above the 50-SMA fails."""
        stock_data = create_mock_price_data(days=100, trend='up', start_price=150.0)

        gate = StructuralSafetyGate(use_atr_filter=False)

        # Calculate 50-SMA (convert to float to avoid numpy type issues)
        sma_50 = float(stock_data['Close'].rolling(50).mean().iloc[-1])

        # Test a strike above the SMA
        test_strike = sma_50 * 1.01  # 1% above SMA

        result = gate.evaluate(stock_data, 'TEST', hypothetical_strike=test_strike)

        assert result['pass'] == False  # Use == instead of 'is' for numpy compatibility
        assert result['details']['below_sma'] is False


class TestEventVolatilityGate:
    """Test cases for the Event & Volatility Gate."""

    def test_no_earnings_conflict_passes(self):
        """Test that no earnings conflict passes."""
        stock_data = create_mock_price_data(days=100)

        gate = EventVolatilityGate(trade_duration_days=45)

        # Earnings 60 days away (outside window)
        earnings_date = datetime.now() + timedelta(days=60)

        result = gate.evaluate(
            stock_data,
            'TEST',
            earnings_date=earnings_date,
            current_date=datetime.now()
        )

        assert result['details']['no_earnings_conflict'] is True

    def test_earnings_inside_window_fails(self):
        """Test that earnings inside trade window fails."""
        stock_data = create_mock_price_data(days=100)

        gate = EventVolatilityGate(trade_duration_days=45)

        # Earnings 30 days away (inside window)
        earnings_date = datetime.now() + timedelta(days=30)

        result = gate.evaluate(
            stock_data,
            'TEST',
            earnings_date=earnings_date,
            current_date=datetime.now()
        )

        assert result['pass'] is False
        assert result['details']['no_earnings_conflict'] is False

    def test_iv_rank_in_range_passes(self):
        """Test that IV rank in acceptable range passes."""
        stock_data = create_mock_price_data(days=100)

        gate = EventVolatilityGate()

        result = gate.evaluate(
            stock_data,
            'TEST',
            iv_rank=40.0  # In range [20, 60]
        )

        assert result['details']['iv_in_range'] is True

    def test_iv_rank_too_low_fails(self):
        """Test that IV rank too low fails."""
        stock_data = create_mock_price_data(days=100)

        gate = EventVolatilityGate()

        result = gate.evaluate(
            stock_data,
            'TEST',
            iv_rank=10.0  # Below minimum of 20
        )

        assert result['pass'] is False
        assert result['details']['iv_in_range'] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
