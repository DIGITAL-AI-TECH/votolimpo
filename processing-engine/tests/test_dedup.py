"""Tests for dedup plugins."""

import hashlib

import pytest

from app.plugins.dedup import HashDedup, CompositeDedup, get_dedup, DEDUP_STRATEGIES


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
