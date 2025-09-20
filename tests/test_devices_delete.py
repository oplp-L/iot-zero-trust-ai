from sqlalchemy.orm import Session
from backend.app.models import Device

def test_delete_not_found_returns_404(client, as_admin):
    resp = client.delete("/devices/999999")
    assert resp.status_code == 404
    assert resp.json().get("detail") in ("设备不存在", "Device not found")

def test_delete_forbidden_for_non_admin(client, as_user):
    resp = client.delete("/devices/1")
    assert resp.status_code == 403
    assert "没有权限" in resp.json().get("detail", "") or "Admin" in resp.json().get("detail", "")

def test_delete_ok_for_admin(client, db_session: Session, as_admin):
    d = Device(name="test-device-to-delete", type="sensor", owner_id=1)
    db_session.add(d)
    db_session.commit()
    db_session.refresh(d)

    resp = client.delete(f"/devices/{d.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("deleted") is True
    assert body.get("device_id") == d.id

    resp2 = client.get(f"/devices/{d.id}")
    assert resp2.status_code == 404