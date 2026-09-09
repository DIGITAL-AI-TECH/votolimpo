"""Tests for API key authentication."""

import hmac

import pytest

from app.api.auth import verify_api_key


class TestTimingSafeComparison:
    """Verify auth uses timing-safe comparison."""

    def test_hmac_compare_digest_used(self):
        """The auth module should use hmac.compare_digest, not ==."""
        import inspect
        source = inspect.getsource(verify_api_key)
        assert "hmac.compare_digest" in source
        assert 'credentials.credentials !=' not in source
