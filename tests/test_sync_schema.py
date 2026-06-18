from app.schemas.sync import SyncResponse


class TestSyncSchema:
    def test_sync_response_defaults(self):
        resp = SyncResponse(accepted=5)
        assert resp.accepted == 5
        assert resp.skipped == 0

    def test_sync_response_full(self):
        resp = SyncResponse(accepted=3, skipped=2)
        assert resp.accepted == 3
        assert resp.skipped == 2
