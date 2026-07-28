def test_health_check_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_check_returns_503_when_database_unavailable(client, monkeypatch):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise Exception("connection refused")

        def close(self):
            pass

    monkeypatch.setattr("app.main.SessionLocal", lambda: BrokenSession())

    response = client.get("/health")

    assert response.status_code == 503

    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "disconnected"
    assert "detail" in body
