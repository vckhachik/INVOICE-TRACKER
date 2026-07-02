from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sqlfunc, and_, or_
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, log_event
from app.core.deps import current_user
from app.db.database import get_db
from app.models.models import Entity, EntityBankBalance, User
from app.schemas.balance import BalanceCreate, BalanceResponse

entity_balance_router = APIRouter(prefix="/entities", tags=["Balances"])
balance_router = APIRouter(prefix="/balances", tags=["Balances"])


@entity_balance_router.get("/{entity_id}/balance", response_model=BalanceResponse)
def get_entity_balance(
    entity_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    balance = (
        db.query(EntityBankBalance)
        .filter(EntityBankBalance.entity_id == entity_id)
        .order_by(EntityBankBalance.updated_at.desc())
        .first()
    )
    if not balance:
        raise HTTPException(status_code=404, detail="No balance found")
    return balance


@entity_balance_router.post("/{entity_id}/balance", response_model=BalanceResponse)
def create_entity_balance(
    entity_id: int,
    payload: BalanceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    currency_upper = payload.currency.upper()
    account_name = payload.account_name or f"{entity.name} {currency_upper}"

    balance = EntityBankBalance(
        entity_id=entity_id,
        account_name=account_name,
        balance_amount=payload.balance_amount,
        currency=currency_upper,
        balance_date=payload.balance_date,
        note=payload.note,
        entry_type="manual",
        updated_by_user_id=actor.id,
        updated_at=datetime.utcnow(),
    )
    db.add(balance)
    db.commit()
    db.refresh(balance)

    log_event(
        db,
        action=AuditAction.BALANCE_UPDATED,
        actor_user_id=actor.id,
        target_type="entity",
        target_id=entity_id,
        metadata={
            "balance_amount": float(payload.balance_amount),
            "currency": payload.currency.upper(),
            "balance_date": str(payload.balance_date),
            "note": payload.note,
        },
    )
    return balance


@entity_balance_router.get("/{entity_id}/balance-history", response_model=List[BalanceResponse])
def get_entity_balance_history(
    entity_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    return (
        db.query(EntityBankBalance)
        .filter(EntityBankBalance.entity_id == entity_id)
        .order_by(EntityBankBalance.updated_at.desc())
        .all()
    )


@balance_router.get("/latest", response_model=List[BalanceResponse])
def get_latest_balances(
    db: Session = Depends(get_db),
    actor: User = Depends(current_user),
):
    """Latest balance entry per (entity_id, account_name) — one row per account."""
    subq = (
        db.query(
            EntityBankBalance.entity_id,
            EntityBankBalance.account_name,
            sqlfunc.max(EntityBankBalance.updated_at).label("max_updated_at"),
        )
        .group_by(EntityBankBalance.entity_id, EntityBankBalance.account_name)
        .subquery()
    )
    join_condition = and_(
        EntityBankBalance.entity_id == subq.c.entity_id,
        EntityBankBalance.updated_at == subq.c.max_updated_at,
        or_(
            EntityBankBalance.account_name == subq.c.account_name,
            and_(
                EntityBankBalance.account_name.is_(None),
                subq.c.account_name.is_(None),
            ),
        ),
    )
    return (
        db.query(EntityBankBalance)
        .join(subq, join_condition)
        .order_by(EntityBankBalance.entity_id, EntityBankBalance.account_name)
        .all()
    )
