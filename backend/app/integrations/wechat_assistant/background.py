from __future__ import annotations

import threading
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal

from .models import WechatAssistantConnection
from .provider import get_provider
from .worker import poll_connection


class WechatAssistantBackground:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        settings = get_settings()
        if not settings.wechat_assistant_worker:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="talon-wechat-assistant-bg", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def status(self) -> dict[str, object]:
        settings = get_settings()
        return {
            "enabled": bool(settings.wechat_assistant_worker),
            "running": bool(self._thread and self._thread.is_alive()),
            "poll_interval_seconds": max(1.0, float(settings.wechat_assistant_poll_interval_seconds)),
        }

    def _run(self) -> None:
        settings = get_settings()
        interval = max(1.0, float(settings.wechat_assistant_poll_interval_seconds))
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                provider = get_provider()
                rows = list(
                    db.scalars(
                        select(WechatAssistantConnection).where(WechatAssistantConnection.status == "connected")
                    )
                )
                for connection in rows:
                    try:
                        poll_connection(db, connection=connection, provider=provider, defer_agent_reply=True)
                        db.commit()
                    except Exception as exc:  # noqa: BLE001
                        db.rollback()
                        connection.status_reason = f"poll_error:{type(exc).__name__}"
                        db.add(connection)
                        db.commit()
            finally:
                db.close()
            time.sleep(0)
            if self._stop.wait(interval):
                break


wechat_assistant_background = WechatAssistantBackground()
