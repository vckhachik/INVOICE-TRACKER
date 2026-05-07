from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.db.database import get_db
from app.models.models import Invoice, Project, Entity, InvoiceActivityLog, User
from app.core.deps import current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    aggregates = db.query(
        func.count(Invoice.id).label("total_invoices"),
        func.sum(case((Invoice.is_paid == True, Invoice.gross_amount), else_=0)).label("paid_total"),
        func.sum(case((Invoice.is_paid == False, Invoice.gross_amount), else_=0)).label("unpaid_total"),
        func.sum(case((Invoice.is_vat_recovered == False, Invoice.vat_amount), else_=0)).label("unrecovered_vat_total"),
        func.sum(case((Invoice.is_approved_to_pay == True, Invoice.gross_amount), else_=0)).label("approved_to_pay_total"),
    ).one()

    return {
        "total_invoices": int(aggregates.total_invoices or 0),
        "paid_total": float(aggregates.paid_total or 0),
        "unpaid_total": float(aggregates.unpaid_total or 0),
        "unrecovered_vat_total": float(aggregates.unrecovered_vat_total or 0),
        "approved_to_pay_total": float(aggregates.approved_to_pay_total or 0),
    }


@router.get("/by-project")
def get_by_project(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    project_rows = db.query(
        Project.id.label("project_id"),
        Project.name.label("project_name"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.gross_amount).label("total"),
        func.sum(case((Invoice.is_paid == True, Invoice.gross_amount), else_=0)).label("paid_total"),
        func.sum(case((Invoice.is_paid == False, Invoice.gross_amount), else_=0)).label("unpaid_total"),
        func.sum(case((Invoice.is_vat_recovered == False, Invoice.vat_amount), else_=0)).label("unrecovered_vat_total"),
    ).outerjoin(Invoice, Invoice.project_id == Project.id) \
     .group_by(Project.id, Project.name) \
     .order_by(Project.name.asc()) \
     .all()

    entity_rows = db.query(
        Invoice.project_id.label("project_id"),
        Entity.id.label("entity_id"),
        Entity.name.label("entity_name"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.gross_amount).label("total"),
        func.sum(case((Invoice.is_paid == True, Invoice.gross_amount), else_=0)).label("paid_total"),
        func.sum(case((Invoice.is_paid == False, Invoice.gross_amount), else_=0)).label("unpaid_total"),
        func.sum(case((Invoice.is_vat_recovered == False, Invoice.vat_amount), else_=0)).label("unrecovered_vat_total"),
    ).outerjoin(Entity, Invoice.paying_entity_id == Entity.id) \
     .group_by(Invoice.project_id, Entity.id, Entity.name) \
     .all()

    entities_by_project = {}
    for row in entity_rows:
        project_id = row.project_id
        if project_id not in entities_by_project:
            entities_by_project[project_id] = []

        entities_by_project[project_id].append(
            {
                "entity_id": row.entity_id,
                "entity": row.entity_name or "Unassigned",
                "count": int(row.count or 0),
                "total": float(row.total or 0),
                "paid_total": float(row.paid_total or 0),
                "unpaid_total": float(row.unpaid_total or 0),
                "unrecovered_vat_total": float(row.unrecovered_vat_total or 0),
            }
        )

    response = []
    for row in project_rows:
        response.append(
            {
                "project_id": row.project_id,
                "project": row.project_name or "Unassigned",
                "count": int(row.count or 0),
                "total": float(row.total or 0),
                "paid_total": float(row.paid_total or 0),
                "unpaid_total": float(row.unpaid_total or 0),
                "unrecovered_vat_total": float(row.unrecovered_vat_total or 0),
                "entities": entities_by_project.get(row.project_id, []),
            }
        )

    unassigned_project_entities = entities_by_project.get(None, [])
    if unassigned_project_entities:
        response.append(
            {
                "project_id": None,
                "project": "Unassigned",
                "count": sum(item["count"] for item in unassigned_project_entities),
                "total": sum(item["total"] for item in unassigned_project_entities),
                "paid_total": sum(item["paid_total"] for item in unassigned_project_entities),
                "unpaid_total": sum(item["unpaid_total"] for item in unassigned_project_entities),
                "unrecovered_vat_total": sum(item["unrecovered_vat_total"] for item in unassigned_project_entities),
                "entities": unassigned_project_entities,
            }
        )

    return response


@router.get("/by-entity")
def get_by_entity(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    results = db.query(
        Entity.id.label("entity_id"),
        Entity.name.label("entity_name"),
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.gross_amount).label("total"),
        func.sum(case((Invoice.is_paid == True, Invoice.gross_amount), else_=0)).label("paid_total"),
        func.sum(case((Invoice.is_paid == False, Invoice.gross_amount), else_=0)).label("unpaid_total"),
        func.sum(case((Invoice.is_vat_recovered == False, Invoice.vat_amount), else_=0)).label("unrecovered_vat_total"),
    ).outerjoin(Invoice, Invoice.paying_entity_id == Entity.id) \
     .group_by(Entity.id, Entity.name) \
     .order_by(Entity.name.asc()) \
     .all()

    response = [
        {
            "entity_id": row.entity_id,
            "entity": row.entity_name or "Unassigned",
            "count": int(row.count or 0),
            "total": float(row.total or 0),
            "paid_total": float(row.paid_total or 0),
            "unpaid_total": float(row.unpaid_total or 0),
            "unrecovered_vat_total": float(row.unrecovered_vat_total or 0),
        }
        for row in results
    ]

    unassigned_row = db.query(
        func.count(Invoice.id).label("count"),
        func.sum(Invoice.gross_amount).label("total"),
        func.sum(case((Invoice.is_paid == True, Invoice.gross_amount), else_=0)).label("paid_total"),
        func.sum(case((Invoice.is_paid == False, Invoice.gross_amount), else_=0)).label("unpaid_total"),
        func.sum(case((Invoice.is_vat_recovered == False, Invoice.vat_amount), else_=0)).label("unrecovered_vat_total"),
    ).filter(Invoice.paying_entity_id.is_(None)).one()

    if (unassigned_row.count or 0) > 0:
        response.append(
            {
                "entity_id": None,
                "entity": "Unassigned",
                "count": int(unassigned_row.count or 0),
                "total": float(unassigned_row.total or 0),
                "paid_total": float(unassigned_row.paid_total or 0),
                "unpaid_total": float(unassigned_row.unpaid_total or 0),
                "unrecovered_vat_total": float(unassigned_row.unrecovered_vat_total or 0),
            }
        )

    return response

@router.get("/activity")
def get_activity(limit: int = 20, db: Session = Depends(get_db), actor: User = Depends(current_user)):
    logs = (
        db.query(InvoiceActivityLog)
        .order_by(InvoiceActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "invoice_id": log.invoice_id,
            "event_type": log.event_type,
            "event_label": log.event_label,
            "changed_by": log.changed_by,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "project_id": log.project_id,
            "entity_id": log.entity_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]