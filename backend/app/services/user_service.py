from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from fastapi import HTTPException, status

from app.models.models import User, UserToken
from app.core.security.tokens import generate_token, hash_token, invite_expiry, reset_expiry
from app.core.security.sessions import revoke_all_user_sessions
from app.core.security.passwords import hash_password
from app.core.security.password_policy import validate_password
from app.core.audit import log_event, AuditAction
from app.services.email import send_invite_email, send_password_reset_email


def get_user_by_email(db: DBSession, email: str) -> User | None:
    return db.query(User).filter(func.lower(User.email) == email.lower().strip()).first()


def get_user_by_id(db: DBSession, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def _count_active_partners(db: DBSession) -> int:
    return db.query(User).filter(
        User.role == "partner",
        User.is_active.is_(True)
    ).count()


def invite_user(db: DBSession, actor: User, email: str, full_name: str,
                role: str, ip_address: str = None) -> User:
    email = email.lower().strip()

    if role not in ("partner", "finance"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Role must be 'partner' or 'finance'.")

    if get_user_by_email(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "A user with that email already exists.")

    new_user = User(
        email=email,
        full_name=full_name.strip(),
        role=role,
        is_active=True,
        must_reset_password=True,
        invited_by_id=actor.id,
    )
    db.add(new_user)
    db.flush()

    raw, token_hash = generate_token()
    token = UserToken(
        user_id=new_user.id,
        token_type="invite",
        token_hash=token_hash,
        expires_at=invite_expiry(),
    )
    db.add(token)
    db.commit()
    db.refresh(new_user)

    send_invite_email(email, new_user.full_name, raw)

    log_event(db, AuditAction.USER_INVITED, actor_user_id=actor.id,
              target_type="user", target_id=new_user.id,
              metadata={"email": email, "role": role}, ip_address=ip_address)

    return new_user


def resend_invite(db: DBSession, actor: User, user_id: int,
                  ip_address: str = None) -> None:
    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.password_hash is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "User has already set a password.")

    raw, token_hash = generate_token()
    token = UserToken(
        user_id=target.id,
        token_type="invite",
        token_hash=token_hash,
        expires_at=invite_expiry(),
    )
    db.add(token)
    db.commit()

    send_invite_email(target.email, target.full_name, raw)
    log_event(db, AuditAction.INVITE_RESENT, actor_user_id=actor.id,
              target_type="user", target_id=target.id, ip_address=ip_address)


def request_password_reset(db: DBSession, email: str,
                           ip_address: str = None) -> None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return

    raw, token_hash = generate_token()
    token = UserToken(
        user_id=user.id,
        token_type="reset",
        token_hash=token_hash,
        expires_at=reset_expiry(),
    )
    db.add(token)
    db.commit()

    send_password_reset_email(user.email, user.full_name, raw)
    log_event(db, AuditAction.PASSWORD_RESET_REQUESTED,
              actor_user_id=user.id, ip_address=ip_address)


def consume_token_and_set_password(db: DBSession, raw_token: str,
                                   new_password: str,
                                   ip_address: str = None) -> User:
    hashed = hash_token(raw_token)
    token = db.query(UserToken).filter(UserToken.token_hash == hashed).first()

    if not token or token.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    now = datetime.now(timezone.utc)
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    user = get_user_by_id(db, token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired token")

    try:
        validate_password(new_password, user_context=[user.email, user.full_name])
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    user.password_hash = hash_password(new_password)
    user.password_set_at = now
    user.must_reset_password = False
    user.failed_login_count = 0
    user.locked_until = None
    token.used_at = now

    revoke_all_user_sessions(db, user.id)
    db.commit()

    action = AuditAction.PASSWORD_RESET_COMPLETED if token.token_type == "reset" \
        else AuditAction.PASSWORD_SET
    log_event(db, action, actor_user_id=user.id,
              metadata={"token_type": token.token_type}, ip_address=ip_address)

    return user


def deactivate_user(db: DBSession, actor: User, user_id: int,
                    ip_address: str = None) -> None:
    if user_id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Cannot deactivate your own account.")

    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if not target.is_active:
        return

    if target.role == "partner" and _count_active_partners(db) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Cannot deactivate the last active partner.")

    target.is_active = False
    revoke_all_user_sessions(db, user_id)
    db.commit()

    log_event(db, AuditAction.USER_DEACTIVATED, actor_user_id=actor.id,
              target_type="user", target_id=user_id, ip_address=ip_address)


def reactivate_user(db: DBSession, actor: User, user_id: int,
                    ip_address: str = None) -> None:
    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.is_active:
        return

    target.is_active = True
    db.commit()

    log_event(db, AuditAction.USER_REACTIVATED, actor_user_id=actor.id,
              target_type="user", target_id=user_id, ip_address=ip_address)


def change_user_role(db: DBSession, actor: User, user_id: int,
                     new_role: str, ip_address: str = None) -> User:
    if new_role not in ("partner", "finance"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Role must be 'partner' or 'finance'.")

    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.role == new_role:
        return target

    if target.role == "partner" and new_role != "partner" \
            and _count_active_partners(db) <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Cannot demote the last active partner.")

    old_role = target.role
    target.role = new_role
    revoke_all_user_sessions(db, user_id)
    db.commit()

    log_event(db, AuditAction.ROLE_CHANGED, actor_user_id=actor.id,
              target_type="user", target_id=user_id,
              metadata={"from": old_role, "to": new_role},
              ip_address=ip_address)

    return target