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
    volatility: float = 0.02
) -> pd.DataFrame:
    """
    Create synthetic OHLCV data for testing.

    Args:
        days: Number of days of data
        start_price: Starting price
        trend: 'up', 'down', or 'flat'
        volatility: Daily volatility (std dev)

    Returns:
        DataFrame with OHLCV data
    """
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Generate price series based on trend
    if trend == 'up':
        drift = 0.001  # 0.1% per day upward drift
    elif trend == 'down':
        drift = -0.001
    else:
        drift = 0.0

    # Random walk with drift
    returns = np.random.normal(drift, volatility, days)
    prices = start_price * np.exp(np.cumsum(returns))

    # Generate OHLCV
    data = pd.DataFrame({
        'Open': prices * (1 + np.random.uniform(-0.005, 0.005, days)),
        'High': prices * (1 + np.random.uniform(0.0, 0.01, days)),
        'Low': prices * (1 + np.random.uniform(-0.01, 0.0, days)),
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

        # Spike VIX in last 5 days
        vix_data['Close'].iloc[-1] = vix_data['Close'].iloc[-6] * 1.15  # +15%

        gate = MarketRegimeGate()
        result = gate.evaluate(spy_data, vix_data)

        assert result['pass'] is False
        assert result['details']['vix_stable'] is False


class TestRelativeStrengthGate:
    """Test cases for the Relative Strength Gate."""

    def test_outperforming_stock_passes(self):
        """Test that a stock outperforming SPY passes."""
        # Create SPY data with moderate gain
        spy_data = create_mock_price_data(days=100, trend='up', volatility=0.01)

        # Create stock data with stronger gain
        stock_data = create_mock_price_data(days=100, trend='up', volatility=0.015)
        stock_data['Close'] = stock_data['Close'] * 1.1  # Boost performance

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

        # Calculate 50-SMA
        sma_50 = stock_data['Close'].rolling(50).mean().iloc[-1]

        # Test a strike above the SMA
        test_strike = sma_50 * 1.01  # 1% above SMA

        result = gate.evaluate(stock_data, 'TEST', hypothetical_strike=test_strike)

        assert result['pass'] is False
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
