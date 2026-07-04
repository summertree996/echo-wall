from __future__ import annotations

import base64
import itertools
import json
import os
import secrets
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings


TEXT = "text"
VOICE = "voice"
IMAGE = "image"
FILE = "file"
VIDEO = "video"
UNKNOWN = "unknown"

ILINK_ITEM_TYPES = {
    1: TEXT,
    2: IMAGE,
    3: VOICE,
    4: FILE,
    5: VIDEO,
}


@dataclass
class QRCodeResult:
    session: str
    qrcode_url: str


@dataclass
class PollResult:
    status: str
    bot_token: str | None = None
    provider_account_id: str | None = None
    base_url: str | None = None
    reason: str | None = None


@dataclass
class InboundUpdate:
    external_message_id: str
    external_user_id: str
    message_type: str = TEXT
    text_content: str | None = None
    media_url: str | None = None
    context_token: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    reason: str | None = None


def _redact(value: str | None, keep: int = 8) -> str | None:
    if not value:
        return value
    if len(value) <= keep + 4:
        return "***"
    return f"{value[:keep]}...{value[-4:]}"


def _normalize_qrcode_url(value: str) -> str:
    qrcode = value.strip()
    if not qrcode:
        return qrcode
    if qrcode.startswith(("http://", "https://", "data:")):
        return qrcode
    return f"data:image/png;base64,{qrcode}"


def _item_text(items: list[dict[str, Any]]) -> str | None:
    for item in items:
        if item.get("type") == 1:
            payload = item.get("text_item") if isinstance(item.get("text_item"), dict) else {}
            text = payload.get("text") or payload.get("content")
            return str(text) if text is not None else None
        if item.get("type") == 3:
            payload = item.get("voice_item") if isinstance(item.get("voice_item"), dict) else {}
            text = payload.get("text")
            if text:
                return str(text)
    return None


def _item_media_ref(items: list[dict[str, Any]]) -> str | None:
    for item in items:
        for key in ("image_item", "voice_item", "file_item", "video_item"):
            payload = item.get(key)
            if not isinstance(payload, dict):
                continue
            media = payload.get("media")
            if isinstance(media, dict):
                return media.get("full_url") or media.get("encrypt_query_param") or json.dumps(media, ensure_ascii=False)
    return None


def _item_message_type(items: list[dict[str, Any]]) -> str:
    if not items:
        return TEXT
    return ILINK_ITEM_TYPES.get(items[0].get("type"), UNKNOWN)


class WechatAssistantProvider:
    requires_production_secret = False

    def request_qrcode(self) -> QRCodeResult:
        raise NotImplementedError

    def poll_qrcode(self, session: str) -> PollResult:
        raise NotImplementedError

    def get_updates(self, bot_token: str, cursor: str | None) -> tuple[list[InboundUpdate], str | None]:
        raise NotImplementedError

    def send_message(
        self,
        *,
        bot_token: str,
        external_user_id: str,
        text: str | None,
        context_token: str | None,
    ) -> SendResult:
        raise NotImplementedError


class MockWechatAssistantProvider(WechatAssistantProvider):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_counter = itertools.count(1)
        self._message_counter = itertools.count(1)
        self._sessions: dict[str, dict[str, Any]] = {}
        self._inbox: dict[str, list[InboundUpdate]] = {}
        self.sent: list[dict[str, Any]] = []
        self.fail_send = False
        self.fail_reason: str | None = None

    def request_qrcode(self) -> QRCodeResult:
        with self._lock:
            session = f"mock-session-{next(self._session_counter)}"
            self._sessions[session] = {"status": "waiting"}
        return QRCodeResult(session=session, qrcode_url=f"https://mock.local/wechat/{session}.png")

    def confirm(self, session: str, provider_account_id: str = "mock-bot") -> str:
        with self._lock:
            token = f"mock-token-{session}"
            self._sessions[session] = {
                "status": "confirmed",
                "bot_token": token,
                "provider_account_id": provider_account_id,
                "base_url": "https://mock.local",
            }
            self._inbox[token] = []
            return token

    def poll_qrcode(self, session: str) -> PollResult:
        with self._lock:
            data = self._sessions.get(session)
            if not data:
                return PollResult(status="error", reason="unknown_session")
            return PollResult(
                status=data["status"],
                bot_token=data.get("bot_token"),
                provider_account_id=data.get("provider_account_id"),
                base_url=data.get("base_url"),
            )

    def push_inbound(self, bot_token: str, update: InboundUpdate) -> None:
        with self._lock:
            self._inbox.setdefault(bot_token, []).append(update)

    def get_updates(self, bot_token: str, cursor: str | None) -> tuple[list[InboundUpdate], str | None]:
        with self._lock:
            updates = list(self._inbox.get(bot_token, []))
            self._inbox[bot_token] = []
        if not updates:
            return [], cursor
        return updates, updates[-1].external_message_id

    def send_message(
        self,
        *,
        bot_token: str,
        external_user_id: str,
        text: str | None,
        context_token: str | None,
    ) -> SendResult:
        if self.fail_send:
            return SendResult(ok=False, reason=self.fail_reason or "mock_send_failed")
        with self._lock:
            provider_message_id = f"mock-out-{next(self._message_counter)}"
            self.sent.append(
                {
                    "bot_token": bot_token,
                    "external_user_id": external_user_id,
                    "text": text,
                    "context_token": context_token,
                    "provider_message_id": provider_message_id,
                }
            )
        return SendResult(ok=True, provider_message_id=provider_message_id)


class HttpWechatAssistantProvider(WechatAssistantProvider):
    requires_production_secret = True

    def __init__(
        self,
        base_url: str,
        admin_token: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.client = httpx.Client(timeout=timeout, transport=transport)
        self._qr_redirect_bases: dict[str, str] = {}

    @staticmethod
    def _wechat_uin() -> str:
        raw = str(secrets.randbits(32)).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _base_info() -> dict[str, str]:
        settings = get_settings()
        channel_version = (
            os.environ.get("TALON_WECHAT_ASSISTANT_CHANNEL_VERSION")
            or settings.wechat_assistant_channel_version
        )
        return {"channel_version": str(channel_version)}

    @staticmethod
    def _common_headers() -> dict[str, str]:
        settings = get_settings()
        app_id = os.environ.get("TALON_WECHAT_ASSISTANT_APP_ID") or settings.wechat_assistant_app_id
        client_version = (
            os.environ.get("TALON_WECHAT_ASSISTANT_CLIENT_VERSION")
            or settings.wechat_assistant_client_version
        )
        return {
            "iLink-App-Id": app_id,
            "iLink-App-ClientVersion": str(client_version),
        }

    def _headers(self, bot_token: str | None = None) -> dict[str, str]:
        headers = {
            **self._common_headers(),
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._wechat_uin(),
        }
        token = bot_token or self.admin_token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def request_qrcode(self) -> QRCodeResult:
        response = self.client.get(
            f"{self.base_url}/ilink/bot/get_bot_qrcode",
            params={"bot_type": "3"},
            headers=self._common_headers(),
        )
        response.raise_for_status()
        data = response.json()
        return QRCodeResult(
            session=str(data["qrcode"]),
            qrcode_url=_normalize_qrcode_url(
                str(data.get("qrcode_img_content") or data.get("qrcode_img_url") or data.get("url") or "")
            ),
        )

    def poll_qrcode(self, session: str) -> PollResult:
        base_url = self._qr_redirect_bases.get(session, self.base_url)
        try:
            response = self.client.get(
                f"{base_url}/ilink/bot/get_qrcode_status",
                params={"qrcode": session},
                headers=self._common_headers(),
            )
        except httpx.HTTPError as exc:
            return PollResult(status="waiting", reason=f"transport:{type(exc).__name__}")
        if response.status_code >= 500:
            return PollResult(status="waiting", reason=f"http_{response.status_code}")
        response.raise_for_status()
        data = response.json()
        current_status = str(data.get("status") or "error")
        if current_status == "scaned_but_redirect" and data.get("redirect_host"):
            self._qr_redirect_bases[session] = f"https://{data['redirect_host']}"
        return PollResult(
            status=current_status,
            bot_token=data.get("bot_token"),
            provider_account_id=data.get("ilink_bot_id") or data.get("provider_account_id") or data.get("account"),
            base_url=data.get("baseurl"),
            reason=data.get("reason"),
        )

    def get_updates(self, bot_token: str, cursor: str | None) -> tuple[list[InboundUpdate], str | None]:
        payload = {"get_updates_buf": cursor or "", "base_info": self._base_info()}
        try:
            response = self.client.post(
                f"{self.base_url}/ilink/bot/getupdates",
                headers=self._headers(bot_token),
                json=payload,
            )
        except httpx.ReadTimeout:
            return [], cursor
        response.raise_for_status()
        data = response.json()
        if data.get("ret", 0) not in (0, None):
            raise RuntimeError(data.get("errmsg") or f"getupdates ret={data.get('ret')}")
        updates: list[InboundUpdate] = []
        for item in data.get("msgs", []) or data.get("updates", []) or []:
            item_list = item.get("item_list") if isinstance(item.get("item_list"), list) else []
            message_type = str(item.get("type") or "")
            if message_type not in {TEXT, VOICE, IMAGE, FILE, VIDEO, UNKNOWN}:
                message_type = _item_message_type(item_list)
            updates.append(
                InboundUpdate(
                    external_message_id=str(item.get("message_id") or item.get("client_id") or item.get("seq") or ""),
                    external_user_id=str(item.get("from_user_id") or item.get("from_user") or item.get("user_id") or ""),
                    message_type=message_type,
                    text_content=item.get("text") or _item_text(item_list),
                    media_url=item.get("media_url") or _item_media_ref(item_list),
                    context_token=item.get("context_token"),
                    raw=item,
                )
            )
        return updates, data.get("get_updates_buf") or data.get("next_cursor") or cursor

    def send_message(
        self,
        *,
        bot_token: str,
        external_user_id: str,
        text: str | None,
        context_token: str | None,
    ) -> SendResult:
        client_id = f"talon-{os.urandom(8).hex()}"
        payload = {
            "msg": {
                "from_user_id": "",
                "to_user_id": external_user_id,
                "client_id": client_id,
                "message_type": 2,
                "message_state": 2,
                "item_list": [{"type": 1, "text_item": {"text": text or ""}}],
                "context_token": context_token,
            },
            "base_info": self._base_info(),
        }
        try:
            response = self.client.post(
                f"{self.base_url}/ilink/bot/sendmessage",
                headers=self._headers(bot_token),
                json=payload,
            )
        except httpx.HTTPError as exc:
            return SendResult(ok=False, reason=f"transport:{type(exc).__name__}")
        if response.status_code >= 400:
            return SendResult(ok=False, reason=f"http_{response.status_code}")
        data = response.json() if response.content else {}
        if data.get("ret", 0) not in (0, None):
            return SendResult(ok=False, reason=data.get("errmsg") or f"ret_{data.get('ret')}")
        return SendResult(
            ok=bool(data.get("ok", True)),
            provider_message_id=str(data.get("message_id") or data.get("provider_message_id") or client_id),
            reason=data.get("reason"),
        )


_provider: WechatAssistantProvider = MockWechatAssistantProvider()


def get_provider() -> WechatAssistantProvider:
    return _provider


def set_provider(provider: WechatAssistantProvider) -> None:
    global _provider
    _provider = provider


def configure_default_provider() -> WechatAssistantProvider:
    settings = get_settings()
    kind = (settings.wechat_assistant_provider or "http").lower()
    if kind == "http":
        provider = HttpWechatAssistantProvider(
            settings.wechat_assistant_base_url,
            admin_token=settings.wechat_assistant_admin_token,
            timeout=settings.deepseek_timeout_seconds,
        )
    else:
        provider = MockWechatAssistantProvider()
    set_provider(provider)
    return provider


def provider_status() -> dict[str, Any]:
    provider = get_provider()
    return {
        "kind": provider.__class__.__name__,
        "requires_production_secret": bool(getattr(provider, "requires_production_secret", False)),
    }
