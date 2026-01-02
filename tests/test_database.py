"""
Unit Tests for Database Module

Tests the SQLite database manager for screening results.
"""

import pytest
import os
import tempfile
from datetime import date, datetime, timedelta
from src.data.database import Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create temp file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize database
    db = Database(db_path=path)

    yield db

    # Cleanup
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_scan_results():
    """Create sample screening results for testing."""
    return {
        'qualified_tickers': ['AAPL', 'MSFT'],
        'failed_tickers': {
            'NVDA': '[RS] Underperforming SPY',
            'TSLA': '[EV] IV Rank too high (72.0 > 60)'
        },
        'system_state': 'RISK-ON',
        'allow_new_trades': True,
        'market_regime': {
            'pass': True,
            'details': {
                'spy_close': 580.50,
                'spy_sma_50': 575.80,
                'sma_slope': 0.15,
                'vix_change_5d': 5.2
            }
        },
        'gate_results': {
            'AAPL': {
                'ticker': 'AAPL',
                'gates': {
                    'relative_strength': {
                        'pass': True,
                        'details': {
                            'ticker': 'AAPL',
                            'relative_strength': 8.5,
                            'stock_sma_50': 180.20,
                            'sma_slope': 0.12
                        }
                    },
                    'structural_safety': {
                        'pass': True,
                        'details': {
                            'ticker': 'AAPL',
                            'current_price': 185.50,
                            'max_safe_strike': 179.75,
                            'atr_14': 3.50,
                            'sma_50_level': 180.20,
                            'higher_low_level': 178.00,
                            'consolidation_level': 176.50
                        }
                    },
                    'event_volatility': {
                        'pass': True,
                        'details': {
                            'ticker': 'AAPL',
                            'iv_rank': 45.2,
                            'earnings_date': None
                        }
                    }
                }
            },
            'MSFT': {
                'ticker': 'MSFT',
                'gates': {
                    'relative_strength': {
                        'pass': True,
                        'details': {
                            'ticker': 'MSFT',
                            'relative_strength': 12.3,
                            'stock_sma_50': 410.00,
                            'sma_slope': 0.18
                        }
                    },
                    'structural_safety': {
                        'pass': True,
                        'details': {
                            'ticker': 'MSFT',
                            'current_price': 420.00,
                            'max_safe_strike': 408.50,
                            'atr_14': 8.20,
                            'sma_50_level': 410.00,
                            'higher_low_level': 405.00,
                            'consolidation_level': 402.00
                        }
                    },
                    'event_volatility': {
                        'pass': True,
                        'details': {
                            'ticker': 'MSFT',
                            'iv_rank': 39.1,
                            'earnings_date': None
                        }
                    }
                }
            },
            'NVDA': {
                'ticker': 'NVDA',
                'gates': {
                    'relative_strength': {
                        'pass': False,
                        'details': {
                            'ticker': 'NVDA',
                            'relative_strength': 4.2,
                            'stock_sma_50': 860.00,
                            'sma_slope': -0.05
                        }
                    },
                    'structural_safety': {
                        'pass': True,
                        'details': {
                            'ticker': 'NVDA',
                            'current_price': 875.00,
                            'max_safe_strike': None,
                            'atr_14': 15.50,
                            'sma_50_level': 860.00,
                            'higher_low_level': None,
                            'consolidation_level': None
                        }
                    },
                    'event_volatility': {
                        'pass': True,
                        'details': {
                            'ticker': 'NVDA',
                            'iv_rank': 58.0,
                            'earnings_date': None
                        }
                    }
                }
            },
            'TSLA': {
                'ticker': 'TSLA',
                'gates': {
                    'relative_strength': {
                        'pass': True,
                        'details': {
                            'ticker': 'TSLA',
                            'relative_strength': -5.1,
                            'stock_sma_50': 240.00,
                            'sma_slope': -0.20
                        }
                    },
                    'structural_safety': {
                        'pass': True,
                        'details': {
                            'ticker': 'TSLA',
                            'current_price': 243.00,
                            'max_safe_strike': None,
                            'atr_14': 12.00,
                            'sma_50_level': 240.00,
                            'higher_low_level': None,
                            'consolidation_level': None
                        }
                    },
                    'event_volatility': {
                        'pass': False,
                        'details': {
                            'ticker': 'TSLA',
                            'iv_rank': 75.0,
                            'earnings_date': None
                        }
                    }
                }
            }
        },
        'failure_mode_alerts': []
    }


class TestDatabaseSchema:
    """Test database schema creation."""

    def test_database_creation(self, temp_db):
        """Test that database file is created."""
        assert os.path.exists(temp_db.db_path)

    def test_tables_exist(self, temp_db):
        """Test that all required tables are created."""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check daily_scans table
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='daily_scans'
            """)
            assert cursor.fetchone() is not None

            # Check screening_results table
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='screening_results'
            """)
            assert cursor.fetchone() is not None

            # Check failure_mode_alerts table
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='failure_mode_alerts'
            """)
            assert cursor.fetchone() is not None

    def test_indexes_exist(self, temp_db):
        """Test that indexes are created."""
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index'
            """)

            indexes = [row[0] for row in cursor.fetchall()]
            assert 'idx_results_ticker' in indexes
            assert 'idx_results_passed' in indexes
            assert 'idx_scans_date' in indexes


class TestSaveScanResults:
    """Test saving screening results."""

    def test_save_basic_results(self, temp_db, sample_scan_results):
        """Test saving a basic scan result."""
        scan_id = temp_db.save_scan_results(sample_scan_results)

        assert scan_id is not None
        assert scan_id > 0

    def test_save_creates_scan_record(self, temp_db, sample_scan_results):
        """Test that saving creates a daily_scans record."""
        temp_db.save_scan_results(sample_scan_results)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily_scans")
            count = cursor.fetchone()[0]

            assert count == 1

    def test_save_creates_ticker_results(self, temp_db, sample_scan_results):
        """Test that saving creates screening_results records."""
        temp_db.save_scan_results(sample_scan_results)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM screening_results")
            count = cursor.fetchone()[0]

            # Should have 4 results (AAPL, MSFT, NVDA, TSLA)
            assert count == 4

    def test_qualified_tickers_marked_correctly(self, temp_db, sample_scan_results):
        """Test that qualified tickers are marked as passed."""
        temp_db.save_scan_results(sample_scan_results)

        with temp_db.get_connection() as conn:
            cursor = conn.cursor()

            # Check AAPL (should be passed)
            cursor.execute("""
                SELECT passed FROM screening_results
                WHERE ticker = 'AAPL'
            """)
            assert cursor.fetchone()[0] == 1

            # Check NVDA (should be failed)
            cursor.execute("""
                SELECT passed FROM screening_results
                WHERE ticker = 'NVDA'
            """)
            assert cursor.fetchone()[0] == 0

    def test_save_replaces_existing_date(self, temp_db, sample_scan_results):
        """Test that saving on the same date replaces the previous scan."""
        # Save first time
        temp_db.save_scan_results(sample_scan_results, scan_date=date(2025, 1, 31))

        # Modify and save again
        sample_scan_results['system_state'] = 'RISK-OFF'
        temp_db.save_scan_results(sample_scan_results, scan_date=date(2025, 1, 31))

        # Should only have one scan for this date
        with temp_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM daily_scans
                WHERE scan_date = '2025-01-31'
            """)
            assert cursor.fetchone()[0] == 1

            # Should have updated system_state
            cursor.execute("""
                SELECT system_state FROM daily_scans
                WHERE scan_date = '2025-01-31'
            """)
            assert cursor.fetchone()[0] == 'RISK-OFF'


class TestQueryMethods:
    """Test query methods."""

    def test_get_latest_scan(self, temp_db, sample_scan_results):
        """Test getting the latest scan."""
        # Save a scan
        temp_db.save_scan_results(sample_scan_results, scan_date=date(2025, 1, 31))

        # Get latest
        latest = temp_db.get_latest_scan()

        assert latest is not None
        assert latest['system_state'] == 'RISK-ON'
        assert latest['num_qualified'] == 2
        assert len(latest['qualified_tickers']) == 2

    def test_get_latest_scan_empty_db(self, temp_db):
        """Test getting latest scan from empty database."""
        latest = temp_db.get_latest_scan()
        assert latest is None

    def test_get_ticker_history(self, temp_db, sample_scan_results):
        """Test getting ticker history."""
        # Save scans for 3 days (using recent dates)
        today = date.today()
        for i in range(3):
            scan_date = today - timedelta(days=2-i)  # 2 days ago, 1 day ago, today
            temp_db.save_scan_results(sample_scan_results, scan_date=scan_date)

        # Get AAPL history
        history = temp_db.get_ticker_history('AAPL', days=30)

        assert len(history) == 3
        assert all(row['passed'] == 1 for row in history)
        # Most recent should be first
        assert history[0]['scan_date'] == str(today)

    def test_get_qualified_tickers(self, temp_db, sample_scan_results):
        """Test getting qualified tickers for a date."""
        temp_db.save_scan_results(sample_scan_results, scan_date=date(2025, 1, 31))

        qualified = temp_db.get_qualified_tickers(scan_date=date(2025, 1, 31))

        assert len(qualified) == 2
        tickers = [row['ticker'] for row in qualified]
        assert 'AAPL' in tickers
        assert 'MSFT' in tickers

    def test_get_qualification_summary(self, temp_db, sample_scan_results):
        """Test getting qualification summary."""
        # Save scans for 5 days, AAPL qualifies every time
        today = date.today()
        for i in range(5):
            scan_date = today - timedelta(days=4-i)  # 4 days ago to today
            temp_db.save_scan_results(sample_scan_results, scan_date=scan_date)

        summary = temp_db.get_qualification_summary(days=30)

        # Find AAPL in summary
        aapl_summary = next((s for s in summary if s['ticker'] == 'AAPL'), None)

        assert aapl_summary is not None
        assert aapl_summary['times_screened'] == 5
        assert aapl_summary['times_qualified'] == 5
        assert aapl_summary['qualification_rate'] == 100.0

    def test_get_system_state_history(self, temp_db, sample_scan_results):
        """Test getting system state history."""
        # Save scans for 3 days
        today = date.today()
        for i in range(3):
            scan_date = today - timedelta(days=2-i)  # 2 days ago to today
            temp_db.save_scan_results(sample_scan_results, scan_date=scan_date)

        history = temp_db.get_system_state_history(days=7)

        assert len(history) == 3
        assert all(row['system_state'] == 'RISK-ON' for row in history)

    def test_get_alerts_for_date(self, temp_db, sample_scan_results):
        """Test getting alerts for a specific date."""
        # Add alerts to sample data
        sample_scan_results['failure_mode_alerts'] = [
            {
                'mode': 'VOLATILITY_EXPANSION',
                'severity': 'WARNING',
                'action': 'WARN',
                'message': 'VIX elevated'
            }
        ]

        temp_db.save_scan_results(sample_scan_results, scan_date=date(2025, 1, 31))

        alerts = temp_db.get_alerts_for_date(scan_date=date(2025, 1, 31))

        assert len(alerts) == 1
        assert alerts[0]['failure_mode'] == 'VOLATILITY_EXPANSION'
        assert alerts[0]['severity'] == 'WARNING'


class TestCSVExport:
    """Test CSV export functionality."""

    def test_export_to_csv(self, temp_db, sample_scan_results):
        """Test exporting results to CSV."""
        # Save some data (use today's date)
        today = date.today()
        temp_db.save_scan_results(sample_scan_results, scan_date=today)

        # Export to temp file
        fd, csv_path = tempfile.mkstemp(suffix='.csv')
        os.close(fd)

        try:
            temp_db.export_to_csv(csv_path, days=7)

            # Check file exists and has content
            assert os.path.exists(csv_path)
            assert os.path.getsize(csv_path) > 0

            # Read and verify content
            import pandas as pd
            df = pd.read_csv(csv_path)

            assert len(df) == 4  # 4 tickers
            assert 'ticker' in df.columns
            assert 'passed' in df.columns

        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
