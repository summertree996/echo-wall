from sqlalchemy import inspect, text

from app.db import engine, settings


def apply_startup_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "walls" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("walls")}
    additions = {
        "ai_enabled": "BOOLEAN NOT NULL DEFAULT 1",
        "ai_model": "VARCHAR(64) NOT NULL DEFAULT 'deepseek-v4-flash'",
        "ai_thinking_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        "ai_reasoning_effort": "VARCHAR(16) NOT NULL DEFAULT 'high'",
        "spotlight_card_id": "VARCHAR(32)",
        "is_locked": "BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE walls ADD COLUMN {name} {definition}"))
