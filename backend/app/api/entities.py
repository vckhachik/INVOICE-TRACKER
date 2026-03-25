from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.models import Entity
from app.schemas.entity import EntityCreate, EntityResponse

router = APIRouter(prefix="/entities", tags=["Entities"])

@router.get("/", response_model=List[EntityResponse])
def get_entities(db: Session = Depends(get_db)):
    return db.query(Entity).all()

@router.post("/", response_model=EntityResponse)
def create_entity(entity: EntityCreate, db: Session = Depends(get_db)):
    new_entity = Entity(
        name=entity.name,
        aliases=entity.aliases,
        project_id_default=entity.project_id_default
    )
    db.add(new_entity)
    db.commit()
    db.refresh(new_entity)
    return new_entity

@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity