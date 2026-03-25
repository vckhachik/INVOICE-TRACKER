from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Entity

router = APIRouter(prefix="/entities", tags=["Entities"])

@router.get("/")
def get_entities(db: Session = Depends(get_db)):
    return db.query(Entity).all()

@router.post("/")
def create_entity(name: str, db: Session = Depends(get_db)):
    entity = Entity(name=name)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity

@router.get("/{entity_id}")
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity