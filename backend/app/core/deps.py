from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.models.models import User, Session as SessionModel
from app.core.security.sessions import load_session

COOKIE_NAME = "invoice_session"
BEARER_PREFIX = "Bearer "


@dataclass
class AuthContext:
    user: User
    session: SessionModel


def _extract_token(request: Request) -> str | None:
    # Try cookie first
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    # Try query param (used by direct browser file links from Streamlit)
    token = request.query_params.get("token")
    if token:
        return token
    # Fall back to Authorization header (for Streamlit API calls)
    auth = request.headers.get("Authorization", "")
    if auth.startswith(BEARER_PREFIX):
        return auth[len(BEARER_PREFIX):].strip() or None
    return None


def current_auth(
    request: Request,
    db: DBSession = Depends(get_db),
) -> AuthContext:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = load_session(db, token)
    if not session:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
        )

    return AuthContext(user=user, session=session)


def current_user(auth: AuthContext = Depends(current_auth)) -> User:
    return auth.user