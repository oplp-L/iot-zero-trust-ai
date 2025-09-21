from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_root_alive():
    r = client.get("/")
    assert r.status_code == 200
    assert "backend is running" in r.json().get("msg", "").lower()

def test_routes_endpoint():
    r = client.get("/__routes")
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data and isinstance(data["routes"], list)
    assert any(route["path"] == "/" for route in data["routes"])

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"