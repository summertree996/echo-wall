from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "ECHO"
    api_prefix: str = "/api"
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'echo_wall.sqlite3'}"
    jwt_secret: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_api_key: str | None = None
    deepseek_key_file: str = str(ROOT_DIR / ".key")
    deepseek_default_model: str = "deepseek-v4-flash"
    deepseek_default_thinking: bool = False
    deepseek_timeout_seconds: float = 60.0
    deepseek_card_timeout_seconds: float = 60.0
    deepseek_summary_timeout_seconds: float = 600.0
    deepseek_max_concurrency: int = 8

    wechat_assistant_provider: str = "http"
    wechat_assistant_worker: bool = True
    wechat_assistant_poll_interval_seconds: float = 2.0
    wechat_assistant_base_url: str = "https://ilinkai.weixin.qq.com"
    wechat_assistant_admin_token: str | None = None
    wechat_assistant_app_id: str = "bot"
    wechat_assistant_client_version: str = "131335"
    wechat_assistant_channel_version: str = "2.0.0"

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_prefix="TALON_",
        case_sensitive=False,
        extra="ignore",
    )

    def resolved_deepseek_key(self) -> str | None:
        if self.deepseek_api_key:
            return self.deepseek_api_key.strip()
        key_path = Path(self.deepseek_key_file)
        if key_path.exists():
            value = key_path.read_text(encoding="utf-8").strip()
            return value or None
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
