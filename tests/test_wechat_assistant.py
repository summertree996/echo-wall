import os
import sys
from pathlib import Path

import pytest
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
TEST_DB = ROOT_DIR / ".codex_tmp" / "pytest_wechat_assistant.sqlite3"

sys.path.insert(0, str(BACKEND_DIR))
TEST_DB.parent.mkdir(parents=True, exist_ok=True)
for suffix in ("", "-shm", "-wal"):
    path = Path(f"{TEST_DB}{suffix}")
    if path.exists():
        path.unlink()

os.environ["TALON_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["TALON_JWT_SECRET"] = "pytest-wechat-secret"
os.environ["TALON_CORS_ORIGINS"] = '["http://testserver"]'
os.environ["TALON_DEEPSEEK_KEY_FILE"] = str(ROOT_DIR / ".codex_tmp" / "missing-deepseek.key")
os.environ["TALON_WECHAT_ASSISTANT_PROVIDER"] = "mock"
os.environ["TALON_WECHAT_ASSISTANT_WORKER"] = "false"

from app.db import SessionLocal, engine  # noqa: E402
from app.integrations.wechat_assistant.models import WechatAssistantConnection  # noqa: E402
from app.integrations.wechat_assistant.provider import (  # noqa: E402
    HttpWechatAssistantProvider,
    InboundUpdate,
    MockWechatAssistantProvider,
    get_provider,
    set_provider,
)
from app.integrations.wechat_assistant.ai_gateway import format_wechat_reply_text  # noqa: E402
from app.integrations.wechat_assistant.tool_loop import ToolLoopResult, _parse_tool_arguments  # noqa: E402
from app.integrations.wechat_assistant.tooling import ToolRunContext, set_tool_context  # noqa: E402
from app.integrations.wechat_assistant.wall_tools import prepare_wall_discussion_context  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.services.seed import DEMO_WALL_ID  # noqa: E402


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
    response = client.post("/api/auth/login", json={"email": "demo@talon.wall", "password": "demo123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_wechat_assistant_qrcode_and_mock_confirm(client: TestClient, admin_token: str) -> None:
    set_provider(MockWechatAssistantProvider())
    response = client.post("/api/wechat-assistant/connections/request-qrcode", headers=auth_headers(admin_token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_qrcode"
    connection_id = payload["connection_id"]

    with SessionLocal() as db:
        connection = db.get(WechatAssistantConnection, connection_id)
        assert connection is not None
        session = connection.qrcode_session

    provider = get_provider()
    assert isinstance(provider, MockWechatAssistantProvider)
    provider.confirm(session)

    poll_response = client.post(
        "/api/wechat-assistant/connections/poll-qrcode-status",
        headers=auth_headers(admin_token),
        json={"connection_id": connection_id},
    )
    assert poll_response.status_code == 200
    assert poll_response.json()["status"] == "connected"


def test_http_wechat_assistant_qrcode_uses_public_headers_and_normalizes_base64() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ilink/bot/get_bot_qrcode"
        assert request.method == "GET"
        assert dict(request.url.params).get("bot_type") == "3"
        assert request.headers.get("iLink-App-Id") == "bot"
        assert request.headers.get("iLink-App-ClientVersion") == "131335"
        assert request.headers.get("AuthorizationType") is None
        assert request.headers.get("Authorization") is None
        assert request.headers.get("X-WECHAT-UIN") is None
        return httpx.Response(
            200,
            json={
                "ret": 0,
                "qrcode": "qr-1",
                "qrcode_img_content": "iVBORw0KGgo=",
            },
        )

    provider = HttpWechatAssistantProvider(
        "https://fake",
        admin_token="admin-token",
        transport=httpx.MockTransport(handler),
    )
    result = provider.request_qrcode()
    assert result.session == "qr-1"
    assert result.qrcode_url == "data:image/png;base64,iVBORw0KGgo="


def test_wechat_assistant_test_query_uses_deepseek_loop(
    client: TestClient,
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_provider(MockWechatAssistantProvider())
    response = client.post("/api/wechat-assistant/connections/request-qrcode", headers=auth_headers(admin_token))
    connection_id = response.json()["connection_id"]
    with SessionLocal() as db:
        session = db.get(WechatAssistantConnection, connection_id).qrcode_session
    provider = get_provider()
    assert isinstance(provider, MockWechatAssistantProvider)
    bot_token = provider.confirm(session)
    client.post(
        "/api/wechat-assistant/connections/poll-qrcode-status",
        headers=auth_headers(admin_token),
        json={"connection_id": connection_id},
    )

    def fake_run(self, *, user_text, instructions, tools, context, db):  # noqa: ANN001
        assert "Talon 共鸣墙" in instructions
        assert "最终回复不要使用 Markdown" in instructions
        assert "参数必须是合法 JSON 对象" in instructions
        assert any(tool.name == "prepare_wall_discussion_context" for tool in tools)
        return ToolLoopResult(final_text=f"已读取上下文：{user_text}", status="succeeded")

    monkeypatch.setattr("app.integrations.wechat_assistant.tool_loop.DeepSeekToolLoop.run", fake_run)
    query_response = client.post(
        f"/api/wechat-assistant/connections/{connection_id}/test-ai-query",
        headers=auth_headers(admin_token),
        json={"text": "帮我看看开放交流反馈墙主要在说什么", "wall_id": DEMO_WALL_ID},
    )

    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["reply"].startswith("已读取上下文")
    assert payload["metadata"]["mode"] == "ai_loop"

    provider.push_inbound(
        bot_token,
        InboundUpdate(
            external_message_id="wx-msg-1",
            external_user_id="wx-user",
            message_type="text",
            text_content="你好",
            context_token="wx-context-token",
            raw={"source": "test"},
        ),
    )
    poll_response = client.post(
        f"/api/wechat-assistant/connections/{connection_id}/poll-once",
        headers=auth_headers(admin_token),
    )
    assert poll_response.status_code == 200

    send_response = client.post(
        f"/api/wechat-assistant/connections/{connection_id}/test-send",
        headers=auth_headers(admin_token),
        json={"text": "测试下推"},
    )
    assert send_response.status_code == 200
    assert send_response.json()["delivery_status"] == "sent"
    assert any(item["external_user_id"] == "wx-user" and item["text"] == "测试下推" for item in provider.sent)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"wall_id":"wall-1","include_actions":true}', {"wall_id": "wall-1", "include_actions": True}),
        ('```json\n{"wall_id":"wall-1"}\n```', {"wall_id": "wall-1"}),
        ('"{\\"wall_id\\":\\"wall-1\\"}"', {"wall_id": "wall-1"}),
        ('{"arguments":{"wall_id":"wall-1","max_cards":30}}', {"wall_id": "wall-1", "max_cards": 30}),
        ('工具参数如下：{"wall_id":"wall-1","query":"负面"}', {"wall_id": "wall-1", "query": "负面"}),
    ],
)
def test_tool_argument_parser_tolerates_deepseek_json_variants(raw: str, expected: dict[str, object]) -> None:
    assert _parse_tool_arguments(raw) == expected


def test_tool_argument_parser_rejects_unrecoverable_json() -> None:
    with pytest.raises(ValueError):
        _parse_tool_arguments("这不是可解析的参数")


def test_wechat_reply_formatter_removes_common_markdown() -> None:
    raw = """# 概览

**基础数据**
- 30 条评论
> 需要关注负面反馈
```json
{"debug": true}
```
"""
    assert format_wechat_reply_text(raw) == "概览\n\n基础数据\n· 30 条评论\n需要关注负面反馈\n{\"debug\": true}"


def test_prepare_wall_discussion_context_returns_full_demo_cards(client: TestClient) -> None:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "demo@talon.wall"))
        assert admin is not None
        set_tool_context(
            ToolRunContext(
                source_user_id=admin.id,
                source_type="wechat",
                source_metadata={},
            )
        )
        try:
            payload = prepare_wall_discussion_context({"wall_id": DEMO_WALL_ID, "include_actions": True}, db)
        finally:
            set_tool_context(None)

    assert payload["wall"]["id"] == DEMO_WALL_ID
    assert len(payload["cards"]) == 30
    assert "reaction_counts" in payload["cards"][0]
    assert "brief" in payload
