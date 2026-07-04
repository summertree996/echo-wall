import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
TEST_DB = ROOT_DIR / ".codex_tmp" / "pytest_backend_smoke.sqlite3"

sys.path.insert(0, str(BACKEND_DIR))
TEST_DB.parent.mkdir(parents=True, exist_ok=True)
for suffix in ("", "-shm", "-wal"):
    path = Path(f"{TEST_DB}{suffix}")
    if path.exists():
        path.unlink()

os.environ["TALON_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["TALON_JWT_SECRET"] = "pytest-secret"
os.environ["TALON_CORS_ORIGINS"] = '["http://testserver"]'
os.environ["TALON_DEEPSEEK_KEY_FILE"] = str(ROOT_DIR / ".codex_tmp" / "missing-deepseek.key")

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ActionLog, AiSummaryCache, Card, ResearchEvent  # noqa: E402
from app.services.seed import CANTEEN_WALL_ID, COURSE_WALL_ID, DEMO_WALL_ID  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    for suffix in ("", "-shm", "-wal"):
        path = Path(f"{TEST_DB}{suffix}")
        if path.exists():
            path.unlink()


@pytest.fixture(scope="module")
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": "demo@talon.wall", "password": "demo123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def student_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": "student@talon.wall", "password": "demo123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def card_payload(text: str, x: int = 200, y: int = 220) -> dict:
    return {
        "content_json": {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]},
            ],
        },
        "plain_text": text,
        "x": x,
        "y": y,
        "canvas_width": 720,
    }


def test_sentiment_confidence_model_uses_float() -> None:
    assert Card.__table__.c.sentiment_confidence.type.python_type is float


def test_demo_wall_snapshot_seeded(client: TestClient, admin_token: str) -> None:
    response = client.get("/api/walls/w_demo_open_feedback", headers=auth_headers(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["wall"]["title"] == "开放交流反馈墙"
    assert payload["wall"]["access_mode"] == "login_required"
    assert len(payload["cards"]) == 30
    assert all(card["sentiment_confidence"] is None or 0 <= card["sentiment_confidence"] <= 1 for card in payload["cards"])
    assert sum(sum(card["reaction_counts"].values()) for card in payload["cards"]) == 156


def test_admin_wall_gallery_seeded(client: TestClient, admin_token: str) -> None:
    response = client.get("/api/walls/admin", headers=auth_headers(admin_token))

    assert response.status_code == 200
    walls = {wall["id"]: wall for wall in response.json()}
    assert {DEMO_WALL_ID, COURSE_WALL_ID, CANTEEN_WALL_ID}.issubset(walls)
    assert walls[DEMO_WALL_ID]["card_count"] == 30
    assert walls[COURSE_WALL_ID]["card_count"] == 12
    assert walls[CANTEEN_WALL_ID]["card_count"] == 10
    assert walls[CANTEEN_WALL_ID]["access_mode"] == "password_required"
    assert walls[CANTEEN_WALL_ID]["has_password"] is True


def test_websocket_snapshot_uses_protocol_auth(client: TestClient, admin_token: str) -> None:
    with client.websocket_connect(
        "/ws/walls/w_demo_open_feedback",
        subprotocols=["talon", f"talon.auth.{admin_token}"],
    ) as websocket:
        message = websocket.receive_json()

    assert message["type"] == "wall:snapshot"
    assert message["payload"]["wall"]["id"] == "w_demo_open_feedback"
    assert len(message["payload"]["cards"]) == 30


def test_websocket_presence_dedupes_same_user(client: TestClient, admin_token: str) -> None:
    subprotocols = ["talon", f"talon.auth.{admin_token}"]
    with client.websocket_connect("/ws/walls/w_demo_open_feedback", subprotocols=subprotocols) as first_socket:
        first_socket.receive_json()
        with client.websocket_connect("/ws/walls/w_demo_open_feedback", subprotocols=subprotocols) as second_socket:
            message = second_socket.receive_json()

    users = message["payload"]["online_users"]
    assert len(users) == 1
    assert users[0]["nickname"] == "崔晓琳"


def test_password_wall_access_accepts_header_and_query_fallback(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    create_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "测试密码墙",
            "description": "用于验证墙访问令牌传输方式",
            "access_mode": "password_required",
            "password": "gate123",
            "ai_enabled": False,
        },
    )
    assert create_response.status_code == 200
    wall_id = create_response.json()["id"]

    student_headers = auth_headers(student_token)
    locked_response = client.get(f"/api/walls/{wall_id}", headers=student_headers)
    assert locked_response.status_code == 200
    assert locked_response.json()["requires_password"] is True

    unlock_response = client.post(
        f"/api/walls/{wall_id}/access",
        json={"password": "gate123"},
    )
    assert unlock_response.status_code == 200
    wall_access_token = unlock_response.json()["wall_access_token"]

    header_response = client.get(
        f"/api/walls/{wall_id}",
        headers={**student_headers, "X-Wall-Access-Token": wall_access_token},
    )
    assert header_response.status_code == 200
    header_payload = header_response.json()
    assert header_payload["wall"]["id"] == wall_id
    assert "requires_password" not in header_payload

    query_response = client.get(
        f"/api/walls/{wall_id}?wall_access_token={wall_access_token}",
        headers=student_headers,
    )
    assert query_response.status_code == 200
    assert query_response.json()["wall"]["id"] == wall_id


def test_move_commit_uses_client_canvas_width(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    create_wall_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "窄屏拖拽测试墙",
            "description": "验证拖拽提交使用客户端画布宽度",
            "access_mode": "login_required",
            "ai_enabled": False,
        },
    )
    assert create_wall_response.status_code == 200
    wall_id = create_wall_response.json()["id"]

    content_json = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "窄屏边界测试"}]},
        ],
    }
    create_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json={
            "content_json": content_json,
            "plain_text": "窄屏边界测试",
            "x": 200,
            "y": 220,
            "canvas_width": 720,
        },
    )
    assert create_card_response.status_code == 200
    card_id = create_card_response.json()["id"]

    move_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/move",
        headers=auth_headers(student_token),
        json={"x": 700, "y": 520, "canvas_width": 720},
    )

    assert move_response.status_code == 200
    assert move_response.json()["x"] <= 600


def test_locked_wall_blocks_member_create_and_move_but_allows_reaction_and_admin_move(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    create_wall_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "锁定语义测试墙",
            "description": "验证锁定后普通成员不能新增和拖拽",
            "access_mode": "login_required",
            "ai_enabled": False,
        },
    )
    assert create_wall_response.status_code == 200
    wall_id = create_wall_response.json()["id"]

    create_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("锁定前创建的卡片"),
    )
    assert create_card_response.status_code == 200
    card_id = create_card_response.json()["id"]

    lock_response = client.patch(
        f"/api/walls/{wall_id}",
        headers=auth_headers(admin_token),
        json={"is_locked": True},
    )
    assert lock_response.status_code == 200
    assert lock_response.json()["is_locked"] is True

    snapshot_response = client.get(f"/api/walls/{wall_id}", headers=auth_headers(student_token))
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["wall"]["is_locked"] is True

    blocked_create_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("锁定后普通成员不能新增", x=240, y=280),
    )
    assert blocked_create_response.status_code == 403
    assert blocked_create_response.json()["detail"] == "Wall is locked"

    blocked_move_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/move",
        headers=auth_headers(student_token),
        json={"x": 360, "y": 380, "canvas_width": 720},
    )
    assert blocked_move_response.status_code == 403
    assert blocked_move_response.json()["detail"] == "Wall is locked"

    reaction_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/reactions",
        headers=auth_headers(student_token),
        json={"reaction_type": "question"},
    )
    assert reaction_response.status_code == 200
    assert reaction_response.json()["reaction_counts"]["question"] == 1

    admin_move_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/move",
        headers=auth_headers(admin_token),
        json={"x": 420, "y": 460, "canvas_width": 720},
    )
    assert admin_move_response.status_code == 200


def test_card_reactions_are_mutually_exclusive_and_toggleable(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    create_wall_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "反应互斥测试墙",
            "description": "验证喜欢、不喜欢和疑问三选一",
            "access_mode": "login_required",
            "ai_enabled": False,
        },
    )
    assert create_wall_response.status_code == 200
    wall_id = create_wall_response.json()["id"]

    create_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("这是一张用于测试反应状态的卡片"),
    )
    assert create_card_response.status_code == 200
    card_id = create_card_response.json()["id"]

    like_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/reactions",
        headers=auth_headers(student_token),
        json={"reaction_type": "like"},
    )
    assert like_response.status_code == 200
    assert like_response.json()["reaction_counts"] == {"like": 1, "dislike": 0, "question": 0}

    question_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/reactions",
        headers=auth_headers(student_token),
        json={"reaction_type": "question"},
    )
    assert question_response.status_code == 200
    assert question_response.json()["reaction_counts"] == {"like": 0, "dislike": 0, "question": 1}

    question_cancel_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/reactions",
        headers=auth_headers(student_token),
        json={"reaction_type": "question"},
    )
    assert question_cancel_response.status_code == 200
    assert question_cancel_response.json()["reaction_counts"] == {"like": 0, "dislike": 0, "question": 0}

    dislike_response = client.post(
        f"/api/walls/{wall_id}/cards/{card_id}/reactions",
        headers=auth_headers(student_token),
        json={"reaction_type": "dislike"},
    )
    assert dislike_response.status_code == 200
    assert dislike_response.json()["reaction_counts"] == {"like": 0, "dislike": 1, "question": 0}


def test_card_soft_delete_and_admin_hide_preserve_action_difference(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    create_wall_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "软删除语义测试墙",
            "description": "验证作者删除和管理员隐藏都保留数据库记录",
            "access_mode": "login_required",
            "ai_enabled": False,
        },
    )
    assert create_wall_response.status_code == 200
    wall_id = create_wall_response.json()["id"]

    own_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("作者自己删除的卡片"),
    )
    assert own_card_response.status_code == 200
    own_card_id = own_card_response.json()["id"]

    delete_response = client.delete(
        f"/api/walls/{wall_id}/cards/{own_card_id}",
        headers=auth_headers(student_token),
    )
    assert delete_response.status_code == 204

    hidden_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("管理员隐藏的卡片", x=260, y=320),
    )
    assert hidden_card_response.status_code == 200
    hidden_card_id = hidden_card_response.json()["id"]

    hide_response = client.delete(
        f"/api/walls/{wall_id}/cards/{hidden_card_id}",
        headers=auth_headers(admin_token),
    )
    assert hide_response.status_code == 204

    snapshot_response = client.get(f"/api/walls/{wall_id}", headers=auth_headers(admin_token))
    assert snapshot_response.status_code == 200
    visible_card_ids = {card["id"] for card in snapshot_response.json()["cards"]}
    assert own_card_id not in visible_card_ids
    assert hidden_card_id not in visible_card_ids

    with SessionLocal() as db:
        own_card = db.get(Card, own_card_id)
        hidden_card = db.get(Card, hidden_card_id)
        assert own_card is not None
        assert hidden_card is not None
        assert own_card.is_deleted is True
        assert hidden_card.is_deleted is True

        actions = db.scalars(select(ActionLog).where(ActionLog.wall_id == wall_id)).all()
        action_by_card = {(action.action_type, (action.payload or {}).get("card_id")) for action in actions}
        assert ("card:delete", own_card_id) in action_by_card
        assert ("card:hide", hidden_card_id) in action_by_card


def test_research_events_summary_and_user_exports(
    client: TestClient,
    admin_token: str,
    student_token: str,
) -> None:
    student = client.get("/api/auth/me", headers=auth_headers(student_token)).json()
    create_wall_response = client.post(
        "/api/walls",
        headers=auth_headers(admin_token),
        json={
            "title": "科研行为数据测试墙",
            "description": "验证用户级汇总和导出",
            "access_mode": "login_required",
            "ai_enabled": False,
        },
    )
    assert create_wall_response.status_code == 200
    wall_id = create_wall_response.json()["id"]

    create_card_response = client.post(
        f"/api/walls/{wall_id}/cards",
        headers=auth_headers(student_token),
        json=card_payload("这条反馈用于科研行为数据导出测试"),
    )
    assert create_card_response.status_code == 200
    card_id = create_card_response.json()["id"]

    ingest_response = client.post(
        f"/api/walls/{wall_id}/research/events",
        headers=auth_headers(student_token),
        json={
            "events": [
                {
                    "client_session_id": "rs_pytest_student",
                    "client_event_id": "rs_pytest_student:1",
                    "event_type": "card:visible",
                    "target_type": "card",
                    "target_id": card_id,
                    "viewport_width": 1280,
                    "viewport_height": 720,
                    "canvas_width": 1100,
                    "canvas_height": 2400,
                    "payload": {"ratio": 0.8, "view_mode": "free"},
                    "client_ts": "2026-07-04T12:00:00Z",
                },
                {
                    "client_session_id": "rs_pytest_student",
                    "client_event_id": "rs_pytest_student:2",
                    "event_type": "pointer:sample",
                    "target_type": "canvas",
                    "x": 320,
                    "y": 460,
                    "payload": {"tool": "react"},
                    "client_ts": "2026-07-04T12:00:01Z",
                },
            ]
        },
    )
    assert ingest_response.status_code == 200
    assert ingest_response.json()["accepted"] == 2

    with SessionLocal() as db:
        stored_events = db.scalars(select(ResearchEvent).where(ResearchEvent.wall_id == wall_id)).all()
        assert len(stored_events) == 2
        assert {event.event_type for event in stored_events} == {"card:visible", "pointer:sample"}

    summary_response = client.get(
        f"/api/walls/{wall_id}/research/summary",
        headers=auth_headers(admin_token),
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    user_summary = next(item for item in summary["users"] if item["user_id"] == student["id"])
    assert user_summary["card_count"] == 1
    assert user_summary["research_event_count"] == 2
    assert user_summary["event_counts"]["card:visible"] == 1
    assert user_summary["client_session_ids"] == ["rs_pytest_student"]

    dashboard_response = client.get(
        f"/api/walls/{wall_id}/research/dashboard",
        headers=auth_headers(admin_token),
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["metrics"]["cards"] == 1
    assert dashboard["metrics"]["behavior_events"] == 2
    assert dashboard["cards"][0]["id"] == card_id
    assert any(point["event_type"] == "card:visible" for point in dashboard["heatmap_points"])
    assert any(event["event_type"] == "card:authored" for event in dashboard["timeline"])

    export_response = client.get(
        f"/api/walls/{wall_id}/research/export.csv",
        headers=auth_headers(admin_token),
    )
    assert export_response.status_code == 200
    assert export_response.content.startswith(b"\xef\xbb\xbf")
    export_text = export_response.text
    assert "research_event" in export_text
    assert "pointer:sample" in export_text
    assert "card:authored_snapshot" in export_text

    user_export_response = client.get(
        f"/api/walls/{wall_id}/research/users/{student['id']}/export.csv",
        headers=auth_headers(admin_token),
    )
    assert user_export_response.status_code == 200
    assert user_export_response.content.startswith(b"\xef\xbb\xbf")
    user_export_text = user_export_response.text
    assert "card:visible" in user_export_text
    assert "这条反馈用于科研行为数据导出测试" in user_export_text

    cards_export_response = client.get(
        f"/api/walls/{wall_id}/export.csv",
        headers=auth_headers(admin_token),
    )
    assert cards_export_response.status_code == 200
    assert cards_export_response.content.startswith(b"\xef\xbb\xbf")

    actions_export_response = client.get(
        f"/api/walls/{wall_id}/export.actions.csv",
        headers=auth_headers(admin_token),
    )
    assert actions_export_response.status_code == 200
    assert actions_export_response.content.startswith(b"\xef\xbb\xbf")


def test_admin_status_and_integration_endpoints(client: TestClient, admin_token: str) -> None:
    headers = auth_headers(admin_token)

    system_response = client.get("/api/system/status", headers=headers)
    integration_response = client.get("/api/integrations/wechat/status", headers=headers)

    assert system_response.status_code == 200
    system_payload = system_response.json()
    check_keys = {check["key"] for check in system_payload["checks"]}
    assert {"database", "demo_gallery", "deepseek_key", "websocket_runtime"}.issubset(check_keys)
    demo_check = next(check for check in system_payload["checks"] if check["key"] == "demo_gallery")
    assert "3/3" in demo_check["detail"]

    assert integration_response.status_code == 200
    integration_payload = integration_response.json()
    assert integration_payload["key"] == "wechat"
    assert integration_payload["enabled"] is True
    assert len(integration_payload["requirements"]) == 4


def test_auth_audit_prefers_forwarded_ip(client: TestClient, admin_token: str) -> None:
    response = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.12"},
        json={"email": "missing@talon.wall", "password": "wrong-password"},
    )
    assert response.status_code == 401

    events_response = client.get(
        "/api/auth/events?event_type=auth:login_failed&email=missing@talon.wall",
        headers=auth_headers(admin_token),
    )
    assert events_response.status_code == 200
    events = events_response.json()
    assert events
    assert events[0]["ip_address"] == "203.0.113.10"


def test_ai_summary_failure_returns_latest_cache(client: TestClient, admin_token: str, monkeypatch: pytest.MonkeyPatch) -> None:
    wall_id = "w_demo_open_feedback"
    with SessionLocal() as db:
        cache = AiSummaryCache(
            wall_id=wall_id,
            cache_key="pytest-cache-fallback",
            model="deepseek-v4-flash",
            thinking_enabled=False,
            reasoning_effort="high",
            card_count=30,
            payload={
                "overview": "缓存摘要可用",
                "model": "deepseek-v4-flash",
                "thinking_enabled": False,
                "reasoning_effort": "high",
                "sentiment_counts": {"positive": 1, "neutral": 0, "negative": 0, "unknown": 0},
                "key_points": [],
                "risks": [],
                "representative_cards": [],
            },
        )
        db.add(cache)
        db.commit()

    async def fail_summary(*_args, **_kwargs):
        raise RuntimeError("simulated DeepSeek outage")

    monkeypatch.setattr("app.api.ai.deepseek_client.summarize_wall", fail_summary)

    response = client.post(
        f"/api/walls/{wall_id}/ai/summary?refresh=true",
        headers=auth_headers(admin_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is True
    assert payload["cache_key"] == "pytest-cache-fallback"
    assert payload["overview"] == "缓存摘要可用"
