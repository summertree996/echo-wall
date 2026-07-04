from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models import AuthEvent, Card, User
from app.schemas.auth import AuthEventPublic, AuthResponse, LoginRequest, RegisterRequest, UserPublic


router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()[:64]
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()[:64]
    return request.client.host if request.client else ""


def _log_auth_event(db: Session, request: Request, event_type: str, email: str, user: User | None = None) -> None:
    db.add(
        AuthEvent(
            user_id=user.id if user else None,
            email=email.lower(),
            event_type=event_type,
            ip_address=_client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255],
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        _log_auth_event(db, request, "auth:register_conflict", payload.email, existing)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=payload.email.lower(), nickname=payload.nickname, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    _log_auth_event(db, request, "auth:register", payload.email, user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, {"is_admin": user.is_admin})
    return AuthResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        _log_auth_event(db, request, "auth:login_failed", payload.email, user)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    _log_auth_event(db, request, "auth:login", payload.email, user)
    db.commit()
    token = create_access_token(user.id, {"is_admin": user.is_admin})
    return AuthResponse(access_token=token, user=UserPublic.model_validate(user))


@router.post("/logout", status_code=204)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    _log_auth_event(db, request, "auth:logout", user.email, user)
    db.commit()


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(user)


@router.get("/me/activity")
def me_activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    cards = db.scalars(
        select(Card)
        .where(Card.author_id == user.id, Card.is_deleted == False)  # noqa: E712
        .options(selectinload(Card.wall), selectinload(Card.reactions))
        .order_by(Card.created_at.desc())
        .limit(40)
    ).all()

    recent_spaces: dict[str, dict] = {}
    recent_activities = []
    for card in cards:
        wall = card.wall
        wall_title = wall.title if wall and wall.title else "ECHO"
        created_at = card.created_at.isoformat() if card.created_at else ""
        reaction_count = len(card.reactions)
        tone = "positive" if card.sentiment == "positive" else "question" if card.sentiment == "negative" else "neutral"

        recent_activities.append(
            {
                "id": card.id,
                "wall_id": card.wall_id,
                "wall_title": wall_title,
                "excerpt": card.plain_text[:120],
                "created_at": created_at,
                "tone": tone,
                "tone_label": "便签",
                "reply_count": reaction_count,
            }
        )

        if wall and wall.id not in recent_spaces:
            recent_spaces[wall.id] = {
                "id": wall.id,
                "title": wall_title,
                "last_active_at": created_at,
                "role_in_space": "主持人" if wall.owner_id == user.id else "参与者",
                "latest_prompt": wall.description or "",
                "contribution_count": 0,
                "status": "ended" if wall.is_archived else "active",
            }
        if wall:
            recent_spaces[wall.id]["contribution_count"] += 1
            if created_at and created_at > recent_spaces[wall.id]["last_active_at"]:
                recent_spaces[wall.id]["last_active_at"] = created_at

    return {
        "recent_activities": recent_activities,
        "recent_spaces": list(recent_spaces.values()),
    }


@router.get("/events", response_model=list[AuthEventPublic])
def list_auth_events(
    limit: int = Query(default=12, ge=1, le=50),
    event_type: str | None = Query(default=None, max_length=64),
    email: str | None = Query(default=None, max_length=255),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuthEvent]:
    stmt = select(AuthEvent)
    if event_type:
        stmt = stmt.where(AuthEvent.event_type == event_type)
    if email and email.strip():
        stmt = stmt.where(AuthEvent.email.ilike(f"%{email.strip().lower()}%"))
    return db.scalars(stmt.order_by(AuthEvent.created_at.desc()).limit(limit)).all()
