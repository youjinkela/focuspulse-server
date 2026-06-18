import pytest
from httpx import AsyncClient


class TestPairingAPI:
    """Integration tests using a shared test DB.

    NOTE: These tests require a running PostgreSQL.
    For CI/local, set DATABASE_URL env var to test DB.
    Skip with `@pytest.mark.skipif` if no DB available.
    """

    @pytest.mark.skip(reason="Requires PostgreSQL — run manually")
    async def test_register_and_verify_flow(self, async_client: AsyncClient):
        # Register first device
        resp = await async_client.post("/api/v1/pairing/register", json={
            "device_name": "测试电脑",
            "device_type": "desktop",
            "platform": {"os": "Windows 11"},
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "device_code" in data
        assert data["device_code"]  # non-empty
        assert data["api_key"].startswith("fp_")

        device_code = data["device_code"]

        # Verify second device uses same code
        resp2 = await async_client.post("/api/v1/pairing/verify", json={
            "device_code": device_code,
            "device_name": "测试手机",
            "device_type": "android",
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["api_key"].startswith("fp_")
        assert len(data2["existing_devices"]) == 1
        assert data2["existing_devices"][0]["device_name"] == "测试电脑"
