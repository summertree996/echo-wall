from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.db import SessionLocal, create_all  # noqa: E402
from app.db_migrations import apply_startup_migrations  # noqa: E402
from app.models import Card, Reaction, User, Wall  # noqa: E402
from app.services.seed import DEMO_WALL_IDS, reset_demo_gallery  # noqa: E402


def counts() -> dict[str, int]:
    with SessionLocal() as db:
        demo_cards_by_wall = {
            wall_id: db.scalar(select(func.count()).select_from(Card).where(Card.wall_id == wall_id)) or 0
            for wall_id in DEMO_WALL_IDS
        }
        demo_reactions_by_wall = {}
        for wall_id in DEMO_WALL_IDS:
            demo_reactions_by_wall[wall_id] = (
                db.scalar(
                    select(func.count())
                    .select_from(Reaction)
                    .join(Card, Reaction.card_id == Card.id)
                    .where(Card.wall_id == wall_id)
                )
                or 0
            )
        return {
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "walls": db.scalar(select(func.count()).select_from(Wall)) or 0,
            "demo_cards_by_wall": demo_cards_by_wall,
            "demo_reactions_by_wall": demo_reactions_by_wall,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the built-in demo gallery data.")
    parser.add_argument("--yes", action="store_true", help="Actually reset the demo gallery. Without this flag, only prints counts.")
    args = parser.parse_args()

    create_all()
    apply_startup_migrations()

    before = counts()
    print({"before": before})
    if not args.yes:
        print("Dry run only. Re-run with --yes to reset the demo gallery.")
        return 0

    with SessionLocal() as db:
        reset_demo_gallery(db)
        db.commit()
    print({"after": counts()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
