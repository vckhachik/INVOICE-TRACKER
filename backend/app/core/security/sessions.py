import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session as DBSession
from app.models.models import Session as SessionModel

SESSION_IDLE_TIMEOUT = timedelta(hours=12)
SESSION_MAX_LIFETIME = timedelta(days=7)


def create_session(db: DBSession, user_id: int, ip: str = None, user_agent: str = None) -> str:
    session_token = secrets.token_urlsafe(32)
    session = SessionModel(
        session_token=session_token,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + SESSION_MAX_LIFETIME,
        ip_address=ip,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(session)
    db.commit()
    return session_token


def load_session(db: DBSession, session_token: str) -> SessionModel | None:
    if not session_token:
        return None

    session = db.query(SessionModel).filter_by(session_token=session_token).first()
    if not session:
        return None

    now = datetime.now(timezone.utc)
    expires_at = _as_utc(session.expires_at)
    last_active = _as_utc(session.last_active_at)

    if session.revoked_at is not None:
        return None
    if expires_at < now:
        return None
    if last_active + SESSION_IDLE_TIMEOUT < now:
        return None

    session.last_active_at = now
    db.commit()
    return session


def revoke_session(db: DBSession, session_token: str) -> None:
    session = db.query(SessionModel).filter_by(session_token=session_token).first()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_user_sessions(db: DBSession, user_id: int) -> None:
    now = datetime.now(timezone.utc)
    db.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.revoked_at.is_(None),
    ).update({"revoked_at": now})
    db.commit()


def _as_utc(dt: datetime) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt