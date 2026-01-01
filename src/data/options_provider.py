"""
Options Data Provider Interface

Abstract base class defining the interface for options data providers.
This allows swapping between different data sources (Tradier, TastyTrade, etc.)
without changing the screener code.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class OptionsDataProvider(ABC):
    """
    Abstract base class for options data providers.

    All providers must implement these methods to fetch:
    - IV Rank (implied volatility percentile)
    - Next earnings date
    """

    @abstractmethod
    def get_iv_rank(self, ticker: str) -> Optional[float]:
        """
        Get the IV Rank for a ticker.

        IV Rank = percentile of current IV vs 52-week IV range (0-100).
        Example: IV Rank of 45 means current IV is higher than 45% of the past year.

        Args:
            ticker: Stock ticker symbol

        Returns:
            IV Rank (0-100) or None if unavailable
        """
        pass

    @abstractmethod
    def get_earnings_date(self, ticker: str) -> Optional[datetime]:
        """
        Get the next earnings announcement date for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Next earnings date or None if unavailable
        """
        pass

    @abstractmethod
    def get_current_iv(self, ticker: str) -> Optional[float]:
        """
        Get the current implied volatility for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current IV (as percentage, e.g., 35.5 for 35.5%) or None if unavailable
        """
        pass

    def is_available(self) -> bool:
        """
        Check if the data provider is available and configured.

        Returns:
            True if provider is ready to use
        """
        return True
