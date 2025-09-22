import json
import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

ADMIN_USER = "admin"
ADMIN_PASS = "Admin123!"


def get_token_or_create_admin():
    # 先尝试直接获取 token（系统若内置了 admin，可直接通过）
    resp = client.post(
        "/users/token",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if resp.status_code == 200 and resp.json().get("access_token"):
        return resp.json()["access_token"]

    # 若失败，尝试创建管理员账户（根据你的实际用户创建 API 字段调整）
    create = client.post(
        "/users/",
        json={"username": ADMIN_USER, "password": ADMIN_PASS, "role": "admin"},
    )
    assert create.status_code in (200, 201), f"Create admin failed: {create.text}"

    # 再次获取 token
    resp2 = client.post(
        "/users/token",
        data={"username": ADMIN_USER, "password": ADMIN_PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp2.status_code == 200, f"Token failed: {resp2.text}"
    token = resp2.json()["access_token"]
    assert token
    return token


def _create_device(H):
    unique_name = f"pytest-risk-demo-{uuid.uuid4().hex[:8]}"
    dev = client.post(
        "/devices/",
        headers=H,
        json={"name": unique_name, "type": "camera", "owner_id": 3},
    )
    assert dev.status_code in (200, 201), dev.text
    return int(str(dev.json().get("id")).strip())


def _post_high_risk_events(H, device_id):
    # 至少 5 条 auth_fail 以满足阈值
    events = {
        "events": [
            {"event_type": "auth_fail", "payload": {}},
            {"event_type": "auth_fail", "payload": {}},
            {"event_type": "auth_fail", "payload": {}},
            {"event_type": "auth_fail", "payload": {}},
            {"event_type": "auth_fail", "payload": {}},
            {"event_type": "policy_violation", "payload": {"rule": "block-telnet"}},
            {"event_type": "net_flow", "payload": {"bytes_out": 30000, "protocol": "mqtt"}},
            {"event_type": "command", "payload": {"cmd": "factory_reset"}},
        ]
    }
    r = client.post(f"/devices/{device_id}/events", headers=H, json=events)
    assert r.status_code in (200, 201), r.text


def test_high_triggers_isolate():
    """
    快速稳定：验证 high 评分触发自动隔离（isolate）。
    """
    token = get_token_or_create_admin()
    H = {"Authorization": f"Bearer {token}"}

    device_id = _create_device(H)
    _post_high_risk_events(H, device_id)

    # 评估（窗口=5）→ 期望 high（触发自动隔离）
    high = client.post(f"/risk/evaluate/{device_id}?window=5", headers=H)
    assert high.status_code == 200, high.text
    j = high.json()
    assert j.get("level") == "high", j

    # 查询动作，期望已出现 isolate
    acts = client.get(f"/risk/actions/{device_id}", headers=H)
    assert acts.status_code == 200, acts.text
    body = json.dumps(acts.json())
    assert "isolate" in body.lower(), body


@pytest.mark.skipif(
    os.getenv("RUN_SLOW_RESTORE") != "1", reason="默认跳过慢速用例，设 RUN_SLOW_RESTORE=1 启用"
)
def test_restore_after_cooldown_and_low():
    """
    可选慢速：等待窗口老化 + 冷却完成后，连续低分评估触发 restore。
    说明：在某些实现里，恢复动作可能依赖定时器或在下一次评估后才落库，
    因此这里包含较长等待和轮询，仅在明确启用时运行。
    """
    token = get_token_or_create_admin()
    H = {"Authorization": f"Bearer {token}"}

    device_id = _create_device(H)
    _post_high_risk_events(H, device_id)

    # 先触发 high
    high = client.post(f"/risk/evaluate/{device_id}?window=5", headers=H)
    assert high.status_code == 200, high.text
    assert high.json().get("level") == "high", high.json()

    # 冷却 + 让高风险事件从 1 分钟窗口中滑出
    time.sleep(70)

    # 连续低分评估（window=1），每次间隔 1 秒，确保计数与时序稳定
    for _ in range(3):
        low = client.post(f"/risk/evaluate/{device_id}?window=1", headers=H)
        assert low.status_code == 200, low.text
        assert low.json().get("level") != "high", low.json()
        time.sleep(1)

    # 轮询查询动作，等待 restore 出现（最多等 90 秒，每 0.5 秒一次）
    body2 = ""
    for _ in range(180):
        acts2 = client.get(f"/risk/actions/{device_id}", headers=H)
        assert acts2.status_code == 200, acts2.text
        body2 = json.dumps(acts2.json())
        if "restore" in body2.lower():
            break
        time.sleep(0.5)

    assert "restore" in body2.lower(), body2
