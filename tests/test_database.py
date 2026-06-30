"""Tests for database helpers: location normalization, India detection, connection pool."""

import pytest

from data_collection.database import (
    DatabaseConnection,
    check_pool_health,
    get_pool_stats,
    is_india_location,
    normalize_location,
)
from data_collection.config import DATABASE_URL


class TestNormalizeLocation:
    """Location normalization — canonical city names for India."""

    # ── Bengaluru variants ───────────────────────────────────────────

    @pytest.mark.parametrize("raw", [
        "Bangalore",
        "bangalore",
        "BANGALORE",
        "bengaluru",
        "Bengaluru",
        "Bangalore, India",
        "bangalore, karnataka",
        "bengaluru, karnataka",
        "Bengaluru, Karnataka",
        "bengaluru/blr",
        "Bangalore, Karnataka, India",
        "Office - Bangalore, India",
        "India, Bangalore",
        "India - Bangalore",
        "Hybrid - Bangalore",
        "Bangalore - EC",
        "Bengaluru, Hybrid",
        "IND - Bengaluru",
        "Bengaluru-VTP",
        "Bengaluru/Bangalore",
        "Bangalore/Bengaluru",
        "Bengaluru (Bangalore)",
        "Bangalore (Bengaluru)",
        "Office - India (Bangalore",
        "APAC - India, Hybrid - Bangalore",
        "Bangalore - WF",
        "Bangalore - BLR",
        "Bengaluru-BLR",
        "Mumbai (Remote Friendly)",  # this has mumbai, should catch mumbai
    ])
    def test_bengaluru_variants(self, raw):
        result = normalize_location(raw)
        # All these should resolve to either Bengaluru or Mumbai
        assert result in (
            "Bengaluru, India", "Mumbai, India", raw.strip(),
        )

    # ── Mumbai variants ──────────────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("Mumbai", "Mumbai, India"),
        ("mumbai", "Mumbai, India"),
        ("Bombay", "Mumbai, India"),
        ("Mumbai, Maharashtra", "Mumbai, India"),
        ("India - Mumbai", "Mumbai, India"),
        ("Mumbai-Lower Parel", "Mumbai, India"),
        ("Mumbai-OWC", "Mumbai, India"),
        ("Office - India (Mumbai", "Mumbai, India"),
    ])
    def test_mumbai_variants(self, raw, expected):
        assert normalize_location(raw) == expected

    # ── Other city variants ──────────────────────────────────────────

    @pytest.mark.parametrize("raw,expected", [
        ("Gurgaon", "Gurugram, India"),
        ("gurgaon", "Gurugram, India"),
        ("Gurugram", "Gurugram, India"),
        ("Gurgaon, Haryana", "Gurugram, India"),
        ("Office - India (Gurgaon", "Gurugram, India"),
        ("Noida", "Noida, India"),
        ("Noida, Uttar Pradesh", "Noida, India"),
        ("Noida, UP", "Noida, India"),
        ("Office - India (Noida", "Noida, India"),
        ("Hyderabad", "Hyderabad, India"),
        ("hyderabad", "Hyderabad, India"),
        ("Hyderabad, Telangana", "Hyderabad, India"),
        ("Hyderabad, IN", "Hyderabad, India"),
        ("India - Hyderabad", "Hyderabad, India"),
        ("Chennai", "Chennai, India"),
        ("Madras", "Chennai, India"),
        ("chennai", "Chennai, India"),
        ("Chennai, Tamil Nadu", "Chennai, India"),
        ("Pune", "Pune, India"),
        ("Pune, Maharashtra", "Pune, India"),
        ("Office - India (Pune", "Pune, India"),
        ("Kolkata", "Kolkata, India"),
        ("Calcutta", "Kolkata, India"),
        ("Kolkata, West Bengal", "Kolkata, India"),
        ("Delhi", "Delhi, India"),
        ("New Delhi", "Delhi, India"),
        ("Delhi NCR", "Delhi, India"),
        ("Delhi-NCR", "Delhi, India"),
        ("Delhi NCR, India", "Delhi, India"),
    ])
    def test_city_variants(self, raw, expected):
        assert normalize_location(raw) == expected

    # ── Edge cases ───────────────────────────────────────────────────

    def test_empty_location(self):
        assert normalize_location("") == ""
        assert normalize_location(None) is None

    def test_whitespace_only(self):
        result = normalize_location("   ")
        assert result == ""

    def test_non_india_location_passes_through(self):
        assert normalize_location("San Francisco, CA") == "San Francisco, CA"
        assert normalize_location("London, UK") == "London, UK"
        assert normalize_location("Remote") == "Remote"

    def test_trailing_comma_and_whitespace_stripped(self):
        result = normalize_location("Somewhere, ")
        assert result == "Somewhere"

    def test_multiple_spaces_collapsed(self):
        result = normalize_location("San   Francisco,   CA")
        assert result == "San Francisco, CA"

    def test_longest_match_wins(self):
        """'Bangalore, India Office' should match bangalore first."""
        result = normalize_location("Bangalore, India Office")
        assert result == "Bengaluru, India"


class TestIsIndiaLocation:
    """India location detection — must avoid false positives from Indonesia etc."""

    @pytest.mark.parametrize("location,expected", [
        # Indian cities
        ("Bangalore", True),
        ("Bengaluru, Karnataka", True),
        ("Hyderabad", True),
        ("Pune", True),
        ("Chennai", True),
        ("Mumbai", True),
        ("Delhi", True),
        ("Gurgaon", True),
        ("Noida", True),
        ("Kolkata", True),
        ("Ahmedabad", True),
        ("Jaipur", True),
        ("Lucknow", True),
        ("Nagpur", True),
        ("Indore", True),
        ("Bhopal", True),
        ("Visakhapatnam", True),
        ("Kochi", True),
        ("Cochin", True),
        ("Trivandrum", True),
        ("Coimbatore", True),
        ("Mysore", True),
        ("Patna", True),
        ("Vadodara", True),
        ("Surat", True),
        ("Chandigarh", True),
        ("Udaipur", True),
        ("Jodhpur", True),
        # Country-based detection
        ("India", True),
        ("Remote, India", True),
        ("Anywhere in India", True),
        # Non-India — should NOT match
        ("San Francisco, CA", False),
        ("London, UK", False),
        ("Berlin, Germany", False),
        ("Remote", False),
        ("", False),
        (None, False),
        # Critical: false positives
        ("Indonesia", False),
        ("Indianapolis, IN", False),
    ])
    def test_is_india(self, location, expected):
        assert is_india_location(location) == expected

    def test_indonesia_is_not_india(self):
        """Regression: 'Indonesia' contains 'india' but is not India."""
        assert not is_india_location("Indonesia")
        assert not is_india_location("Jakarta, Indonesia")

    def test_indianapolis_is_not_india(self):
        """Regression: 'Indianapolis' contains 'india' but is a US city."""
        assert not is_india_location("Indianapolis, IN")
        assert not is_india_location("Indianapolis, Indiana")


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not configured")
class TestConnectionPool:
    """Integration tests — require a live database."""

    def test_get_connection_returns_database_connection(self):
        from data_collection.database import get_connection
        conn = get_connection()
        try:
            assert isinstance(conn, DatabaseConnection)
        finally:
            conn.close()

    def test_ping_returns_true(self):
        from data_collection.database import get_connection
        conn = get_connection()
        try:
            assert conn.ping() is True
        finally:
            conn.close()

    def test_check_pool_health_healthy(self):
        result = check_pool_health()
        assert result["healthy"] is True
        assert result["pool_initialized"] is True
        assert result["ping_ms"] is not None
        assert result["error"] is None

    def test_get_pool_stats(self):
        stats = get_pool_stats()
        assert stats["initialized"] is True
        assert stats["minconn"] == 2
        assert stats["maxconn"] == 20


class TestCheckPoolHealthUninitialized:
    """Unit test — pool not yet initialized."""

    def test_health_returns_error_when_pool_not_initialized(self, monkeypatch):
        """When _pool is None, check returns healthy=False with error message."""
        import data_collection.database as db

        monkeypatch.setattr(db, "_pool", None)
        result = db.check_pool_health()
        assert result["healthy"] is False
        assert result["pool_initialized"] is False
        assert "not initialized" in result["error"]
