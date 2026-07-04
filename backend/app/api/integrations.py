from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models import User
from app.schemas.integration import IntegrationStatusPublic
from app.integrations.wechat_assistant.provider import provider_status


router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/wechat/status", response_model=IntegrationStatusPublic)
def wechat_status(_admin: User = Depends(require_admin)) -> IntegrationStatusPublic:
    return IntegrationStatusPublic(
        key="wechat",
        label="AI 微信助手",
        status="available",
        enabled=True,
        message="当前版本提供管理员微信私聊查询入口，用于讨论反馈墙数据。",
        planned_endpoint="/api/wechat-assistant/connections/request-qrcode",
        requirements=[
            {
                "title": "一对一连接",
                "detail": "管理员扫码后建立个人微信助手通道，微信消息按连接所属管理员鉴权。",
            },
            {
                "title": "只读讨论",
                "detail": "助手只读取和讨论反馈墙数据，不删除用户、卡片或墙，不修改权限。",
            },
            {
                "title": "回复窗口",
                "detail": "微信回复依赖用户消息带来的 context token，不把它当长期主动推送凭据。",
            },
            {
                "title": "Provider",
                "detail": f"当前 provider：{provider_status()['kind']}。",
            },
        ],
    )
