from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.models.models import User
from app.schemas.user import InviteUserRequest, UpdateUserRequest, UserListItem
from app.schemas.auth import OkResponse
from app.core.permissions import require_permission, Permission
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[UserListItem])
def list_users(
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def invite_user(
    body: InviteUserRequest,
    request: Request,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    return user_service.invite_user(
        db, actor=actor, email=body.email,
        full_name=body.full_name, role=body.role,
        ip_address=_ip(request),
    )


@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    request: Request,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    if body.role is not None:
        user_service.change_user_role(db, actor, user_id, body.role,
                                      ip_address=_ip(request))
    if body.full_name is not None:
        target = user_service.get_user_by_id(db, user_id)
        if target:
            target.full_name = body.full_name.strip()
            db.commit()
    return user_service.get_user_by_id(db, user_id)


@router.post("/{user_id}/deactivate", response_model=OkResponse)
def deactivate_user(
    user_id: int,
    request: Request,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    user_service.deactivate_user(db, actor, user_id, ip_address=_ip(request))
    return OkResponse(message="User deactivated")


@router.post("/{user_id}/reactivate", response_model=OkResponse)
def reactivate_user(
    user_id: int,
    request: Request,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    user_service.reactivate_user(db, actor, user_id, ip_address=_ip(request))
    return OkResponse(message="User reactivated")


@router.post("/{user_id}/resend-invite", response_model=OkResponse)
def resend_invite(
    user_id: int,
    request: Request,
    actor: User = Depends(require_permission(Permission.MANAGE_USERS)),
    db: DBSession = Depends(get_db),
):
    user_service.resend_invite(db, actor, user_id, ip_address=_ip(request))
    return OkResponse(message="Invite resent")