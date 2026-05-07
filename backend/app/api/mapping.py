from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import MappingRule, Entity, Project, Invoice, User
from app.core.deps import current_user
from app.core.permissions import require_permission, Permission
from app.services.mapping import (
    apply_mapping_to_invoice,
    save_mapping_rule,
    find_entity_match
)

router = APIRouter(prefix="/mapping", tags=["Mapping"])


def serialise_match_result(raw_text: str, result: dict) -> dict:
    return {
        "raw_text": raw_text,
        "matched": result["matched"],
        "match_type": result["match_type"],
        "confidence": result["confidence"],
        "entity": {
            "id": result["entity"].id,
            "name": result["entity"].name,
        } if result["entity"] else None,
        "project": {
            "id": result["project"].id,
            "name": result["project"].name,
        } if result["project"] else None,
    }


@router.post("/invoices/{invoice_id}/map")
def map_invoice(invoice_id: int, db: Session = Depends(get_db), actor: User = Depends(require_permission(Permission.EDIT_INVOICE))):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = apply_mapping_to_invoice(invoice, db)

    return {
        "invoice_id": invoice_id,
        **serialise_match_result(invoice.paying_entity_raw or "", result),
    }


@router.post("/rules")
def create_mapping_rule(
    raw_text: str,
    entity_id: int,
    project_id: Optional[int] = None,
    priority: int = 0,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.MANAGE_MAPPINGS)),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    if project_id is not None:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

    rule = save_mapping_rule(raw_text, entity_id, project_id, db, priority)

    return {
        "rule_id": rule.id,
        "raw_text_pattern": rule.raw_text_pattern,
        "entity_id": rule.mapped_entity_id,
        "project_id": rule.mapped_project_id,
        "active": rule.active
    }


@router.get("/rules")
def get_mapping_rules(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    rules = (
        db.query(MappingRule)
        .filter(MappingRule.active.is_(True))
        .order_by(MappingRule.priority.desc(), MappingRule.id.desc())
        .all()
    )
    return rules


@router.delete("/rules/{rule_id}")
def delete_mapping_rule(rule_id: int, db: Session = Depends(get_db), actor: User = Depends(require_permission(Permission.MANAGE_MAPPINGS))):
    rule = db.query(MappingRule).filter(MappingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.active = False
    db.commit()
    db.refresh(rule)
    return {"message": "Rule deactivated"}


@router.post("/match-test")
def test_match(raw_text: str, db: Session = Depends(get_db), actor: User = Depends(current_user)):
    result = find_entity_match(raw_text, db)
    return serialise_match_result(raw_text, result)