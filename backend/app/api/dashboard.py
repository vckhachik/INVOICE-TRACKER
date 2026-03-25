from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.database import get_db
from app.models.models import Invoice, Project, Entity

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    total_invoices = db.query(Invoice).count()
    unpaid_total = db.query(func.sum(Invoice.gross_amount)).filter(
        Invoice.is_paid == False
    ).scalar() or 0
    unrecovered_vat = db.query(func.sum(Invoice.vat_amount)).filter(
        Invoice.is_vat_recovered == False
    ).scalar() or 0
    approved_total = db.query(func.sum(Invoice.gross_amount)).filter(
        Invoice.is_approved_to_pay == True
    ).scalar() or 0

    return {
        "total_invoices": total_invoices,
        "unpaid_total": float(unpaid_total),
        "unrecovered_vat_total": float(unrecovered_vat),
        "approved_to_pay_total": float(approved_total)
    }

@router.get("/by-project")
def get_by_project(db: Session = Depends(get_db)):
    results = db.query(
        Project.name,
        func.sum(Invoice.gross_amount).label("total"),
        func.count(Invoice.id).label("count")
    ).join(Invoice, Invoice.project_id == Project.id)\
     .group_by(Project.name).all()
    
    return [{"project": r.name, "total": float(r.total or 0), "count": r.count} for r in results]

@router.get("/by-entity")
def get_by_entity(db: Session = Depends(get_db)):
    results = db.query(
        Entity.name,
        func.sum(Invoice.gross_amount).label("total"),
        func.count(Invoice.id).label("count")
    ).join(Invoice, Invoice.paying_entity_id == Entity.id)\
     .group_by(Entity.name).all()
    
    return [{"entity": r.name, "total": float(r.total or 0), "count": r.count} for r in results]