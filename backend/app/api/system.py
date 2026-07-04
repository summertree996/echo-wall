from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.deepseek import deepseek_client
from app.api.deps import require_admin
from app.core.config import get_settings
from app.db import get_db
from app.models import User, Wall
from app.schemas.system import SystemCheckPublic, SystemStatusPublic
from app.services.seed import DEMO_WALL_IDS


router = APIRouter(prefix="/system", tags=["system"])


CheckStatus = Literal["ok", "warning", "error"]
STATUS_ORDER: dict[CheckStatus, int] = {"ok": 0, "warning": 1, "error": 2}


def _check(key: str, label: str, status: CheckStatus, detail: str) -> SystemCheckPublic:
    return SystemCheckPublic(key=key, label=label, status=status, detail=detail)


def _overall(checks: list[SystemCheckPublic]) -> CheckStatus:
    return max((item.status for item in checks), key=lambda status: STATUS_ORDER[status], default="ok")


@router.get("/status", response_model=SystemStatusPublic)
def system_status(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemStatusPublic:
    settings = get_settings()
    checks: list[SystemCheckPublic] = []

    try:
        wall_count = db.scalar(select(func.count(Wall.id))) or 0
        checks.append(_check("database", "数据库", "ok", f"连接正常，当前 {wall_count} 面墙。"))
    except Exception as exc:
        checks.append(_check("database", "数据库", "error", f"数据库连接失败：{exc.__class__.__name__}"))

    try:
        demo_walls = db.scalars(select(Wall).where(Wall.id.in_(DEMO_WALL_IDS))).all()
        active_demo_count = sum(1 for wall in demo_walls if not wall.is_archived)
        expected_demo_count = len(DEMO_WALL_IDS)
        demo_status: CheckStatus = "ok" if active_demo_count == expected_demo_count else "warning"
        checks.append(
            _check(
                "demo_gallery",
                "演示墙组",
                demo_status,
                f"{active_demo_count}/{expected_demo_count} 面内置演示墙可用。" if demo_status == "ok" else "内置演示墙组不完整，可运行 reset_demo_data.py。",
            )
        )
    except Exception as exc:
        checks.append(_check("demo_gallery", "演示墙组", "error", f"演示墙组检查失败：{exc.__class__.__name__}"))

    checks.append(
        _check(
            "deepseek_key",
            "DeepSeek",
            "ok" if deepseek_client.configured() else "warning",
            "API key 已配置，可在单面墙上继续测试连接。" if deepseek_client.configured() else "未配置 API key，AI 分析和摘要会不可用。",
        )
    )

    checks.append(
        _check(
            "jwt_secret",
            "JWT Secret",
            "warning" if settings.jwt_secret == "dev-change-me" else "ok",
            "仍为开发默认值，部署前应替换。" if settings.jwt_secret == "dev-change-me" else "已使用自定义密钥。",
        )
    )

    checks.append(
        _check(
            "cors",
            "CORS",
            "warning" if any(origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost") for origin in settings.cors_origins) else "ok",
            f"当前允许 {len(settings.cors_origins)} 个来源。",
        )
    )

    checks.append(
        _check(
            "websocket_runtime",
            "WebSocket 部署",
            "ok",
            "当前设计使用进程内房间管理，云上部署请保持单 Uvicorn worker。",
        )
    )

    return SystemStatusPublic(status=_overall(checks), checked_at=datetime.now(timezone.utc), checks=checks)
