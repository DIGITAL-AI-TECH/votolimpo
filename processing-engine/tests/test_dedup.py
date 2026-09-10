"""Tests for dedup plugins."""

from app.plugins.dedup import DEDUP_STRATEGIES, CompositeDedup, HashDedup, get_dedup


class TestHashDedup:
    def test_registry(self):
        assert "hash" in DEDUP_STRATEGIES
        dedup = get_dedup("hash")
        assert isinstance(dedup, HashDedup)


class TestCompositeDedup:
    def test_registry(self):
        assert "composite" in DEDUP_STRATEGIES
        dedup = get_dedup("composite")
        assert isinstance(dedup, CompositeDedup)


class TestGetDedup:
    def test_unknown_falls_back_to_hash(self):
        dedup = get_dedup("nonexistent")
        assert isinstance(dedup, HashDedup)
