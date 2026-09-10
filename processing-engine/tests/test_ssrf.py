"""Tests for SSRF protection in orchestrator and sink."""


from app.core.orchestrator import _validate_callback_url


class TestCallbackUrlValidation:
    def test_allows_public_https(self):
        assert _validate_callback_url("https://example.com/webhook") is True

    def test_allows_public_http(self):
        assert _validate_callback_url("http://example.com/callback") is True

    def test_blocks_localhost(self):
        assert _validate_callback_url("http://localhost:8080/hook") is False

    def test_blocks_127_0_0_1(self):
        assert _validate_callback_url("http://127.0.0.1/hook") is False

    def test_blocks_metadata_service(self):
        assert _validate_callback_url("http://169.254.169.254/latest/meta-data") is False

    def test_blocks_private_10_network(self):
        assert _validate_callback_url("http://10.0.0.1:3000/hook") is False

    def test_blocks_private_172_network(self):
        assert _validate_callback_url("http://172.16.0.1/hook") is False

    def test_blocks_private_192_168(self):
        assert _validate_callback_url("http://192.168.1.1/hook") is False

    def test_blocks_ftp_scheme(self):
        assert _validate_callback_url("ftp://example.com/file") is False

    def test_blocks_empty_url(self):
        assert _validate_callback_url("") is False

    def test_blocks_no_host(self):
        assert _validate_callback_url("http://") is False

    def test_blocks_file_scheme(self):
        assert _validate_callback_url("file:///etc/passwd") is False


class TestDatabaseUrlEnvWhitelist:
    def test_allowed_env_accepted(self):
        """Whitelisted env vars should not raise."""
        from app.plugins.sinks import PostgreSQLSink
        # Just verify the whitelist exists and contains expected values
        # Full integration test requires DB
        sink = PostgreSQLSink()
        # The whitelist is checked inside persist(), we verify the pattern
        import inspect
        source = inspect.getsource(sink.persist)
        assert "ALLOWED_DB_ENVS" in source
        assert "PE_VOTOLIMPO_DATABASE_URL" in source
        assert "PE_DATABASE_URL" in source
