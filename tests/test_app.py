from fastapi.testclient import TestClient

from budget_box.app import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test-token"}


def test_health_needs_no_token():
    assert client.get("/healthz").json() == {"ok": True}


def test_rejects_a_wrong_token():
    assert client.get("/views", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/screen.png").status_code == 401


def test_views_come_from_the_fixtures():
    r = client.get("/views", headers=AUTH)
    assert r.text.split() == ["budget", "personal:Alex"]


def test_screen_is_a_png_with_a_version():
    r = client.get("/screen.png?view=personal:Alex&rotate=90", headers={**AUTH, "X-Kindle-Battery": "70"})
    assert r.headers["content-type"] == "image/png" and r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert int(r.headers["x-data-version"]) > 0
    assert client.get("/status", headers=AUTH).json()["battery"] == "70%"


def test_unknown_view_is_404():
    assert client.get("/screen.png?view=nope", headers=AUTH).status_code == 404


def test_wait_answers_at_once_for_a_stale_version():
    assert client.get("/wait?v=1&timeout=5", headers=AUTH).json()["changed"] is True


def test_source_outage_is_a_clean_502(monkeypatch):
    import httpx

    async def down(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(app.state.source, "wait", down)
    r = client.get("/wait?v=1&timeout=5", headers=AUTH)
    assert r.status_code == 502 and r.json()["error"] == "data source unavailable"
