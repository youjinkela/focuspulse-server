import pytest
from app.config import hash_api_key, generate_api_key, generate_device_code


class TestCrypto:
    def test_generate_api_key_format(self):
        key = generate_api_key()
        assert key.startswith("fp_")
        assert len(key) == 51  # "fp_" + 48 hex chars

    def test_hash_api_key_deterministic(self):
        key = "test_key_123"
        h1 = hash_api_key(key)
        h2 = hash_api_key(key)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

    def test_hash_different_keys(self):
        assert hash_api_key("key_a") != hash_api_key("key_b")

    def test_generate_device_code_length(self):
        code = generate_device_code()
        assert len(code) == 6
        assert code.isalnum()

    def test_generate_device_code_excludes_confusables(self):
        for _ in range(100):
            code = generate_device_code()
            for ch in code:
                assert ch not in "0OIL", f"Contains confusable: {ch}"
