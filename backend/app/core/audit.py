from sqlalchemy.orm import Session as DBSession
from app.models.models import AuditLog


class AuditAction:
    # Auth
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGIN_LOCKED = "login_locked"
    LOGOUT = "logout"

    # Passwords
    PASSWORD_SET = "password_set"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"

    # User admin
    USER_INVITED = "user_invited"
    INVITE_RESENT = "invite_resent"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    ROLE_CHANGED = "role_changed"

    # Invoice workflow
    INVOICE_APPROVED = "invoice_approved"
    INVOICE_UNAPPROVED = "invoice_unapproved"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_CANCELLED = "approval_cancelled"

    # Mapping management
    CREATE_PROJECT = "create_project"
    CREATE_ENTITY = "create_entity"
    UPDATE_ENTITY = "update_entity"

    # Balances
    BALANCE_UPDATED = "balance_updated"


def log_event(
    db: DBSession,
    action: str,
    actor_user_id: int = None,
    target_type: str = None,
    target_id=None,
    metadata: dict = None,
    ip_address: str = None,
) -> None:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        event_metadata=metadata,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
