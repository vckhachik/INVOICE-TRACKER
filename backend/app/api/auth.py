from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.models.models import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, ForgotPasswordRequest,
    SetPasswordRequest, OkResponse, MeResponse, UserDTO,
)
from app.core.security.passwords import verify_password, hash_password, needs_rehash
from app.core.security.sessions import create_session, revoke_session, SESSION_MAX_LIFETIME
from app.core.deps import current_auth, COOKIE_NAME, AuthContext
from app.core.audit import log_event, AuditAction
from app.core.permissions import user_permissions
from app.services.user_service import (
    get_user_by_email, request_password_reset, consume_token_and_set_password
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
):
    email = body.email.lower().strip()
    ip = _ip(request)
    ua = request.headers.get("user-agent", "")

    user = get_user_by_email(db, email)
    generic_error = HTTPException(status.HTTP_401_UNAUTHORIZED,
                                  detail="Invalid email or password")

    if not user or not user.password_hash:
        log_event(db, AuditAction.LOGIN_FAILURE,
                  metadata={"email": email, "reason": "no_user"}, ip_address=ip)
        raise generic_error

    if not user.is_active:
        log_event(db, AuditAction.LOGIN_FAILURE, actor_user_id=user.id,
                  metadata={"reason": "inactive"}, ip_address=ip)
        raise generic_error

    now = datetime.now(timezone.utc)
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            log_event(db, AuditAction.LOGIN_LOCKED,
                      actor_user_id=user.id, ip_address=ip)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                                detail="Account temporarily locked. Try again later.")

    if not verify_password(body.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_THRESHOLD:
            user.locked_until = now + LOCKOUT_DURATION
        db.commit()
        log_event(db, AuditAction.LOGIN_FAILURE, actor_user_id=user.id,
                  metadata={"failed_count": user.failed_login_count}, ip_address=ip)
        raise generic_error

    # Success
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    db.commit()

    session_token = create_session(db, user.id, ip=ip, user_agent=ua)

    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=False,   # set True once on HTTPS
        samesite="lax",
        max_age=int(SESSION_MAX_LIFETIME.total_seconds()),
        path="/",
    )

    log_event(db, AuditAction.LOGIN_SUCCESS, actor_user_id=user.id, ip_address=ip)

    return LoginResponse(
        user=UserDTO.model_validate(user),
        session_token=session_token,
    )


@router.post("/logout", response_model=OkResponse)
def logout(
    response: Response,
    auth: AuthContext = Depends(current_auth),
    db: DBSession = Depends(get_db),
):
    revoke_session(db, auth.session.session_token)
    response.delete_cookie(COOKIE_NAME, path="/")
    log_event(db, AuditAction.LOGOUT, actor_user_id=auth.user.id)
    return OkResponse(message="Logged out")


@router.get("/me", response_model=MeResponse)
def me(auth: AuthContext = Depends(current_auth)):
    return MeResponse(
        user=UserDTO.model_validate(auth.user),
        permissions=sorted(user_permissions(auth.user)),
    )


@router.post("/forgot-password", response_model=OkResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: DBSession = Depends(get_db),
):
    request_password_reset(db, body.email, ip_address=_ip(request))
    return OkResponse(message="If that email is registered, a reset link has been sent.")


@router.post("/set-password", response_model=OkResponse)
def set_password(
    body: SetPasswordRequest,
    request: Request,
    db: DBSession = Depends(get_db),
):
    consume_token_and_set_password(
        db, body.token, body.new_password, ip_address=_ip(request)
    )
    return OkResponse(message="Password set. Please log in.")