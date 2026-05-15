from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.models import Entity, Project, User
from app.core.deps import current_user
from app.core.permissions import require_permission, Permission
from app.core.audit import log_event, AuditAction
from app.schemas.entity import EntityCreate, EntityUpdate, EntityResponse

router = APIRouter(prefix="/entities", tags=["Entities"])


@router.get("/", response_model=List[EntityResponse])
def get_entities(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    return db.query(Entity).all()


@router.post("/", response_model=EntityResponse)
def create_entity(
    entity: EntityCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.MANAGE_MAPPINGS)),
):
    new_entity = Entity(
        name=entity.name,
        aliases=entity.aliases,
        project_id_default=entity.project_id_default,
        show_as_project=entity.show_as_project,
    )
    db.add(new_entity)
    db.flush()  # acquire entity.id before creating the paired project

    if entity.show_as_project:
        paired_project = Project(name=entity.name, source_entity_id=new_entity.id)
        db.add(paired_project)
        db.flush()  # acquire paired_project.id
        new_entity.project_id_default = paired_project.id

    db.commit()
    db.refresh(new_entity)

    log_event(
        db,
        action=AuditAction.CREATE_ENTITY,
        actor_user_id=actor.id,
        target_type="entity",
        target_id=new_entity.id,
        metadata={
            "name": new_entity.name,
            "show_as_project": new_entity.show_as_project,
            "project_id_default": new_entity.project_id_default,
        },
    )
    if entity.show_as_project:
        log_event(
            db,
            action=AuditAction.CREATE_PROJECT,
            actor_user_id=actor.id,
            target_type="project",
            target_id=new_entity.project_id_default,
            metadata={"name": new_entity.name, "source_entity_id": new_entity.id, "auto_created": True},
        )

    return new_entity


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(entity_id: int, db: Session = Depends(get_db), actor: User = Depends(current_user)):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.patch("/{entity_id}", response_model=EntityResponse)
def update_entity(
    entity_id: int,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.MANAGE_MAPPINGS)),
):
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    old_values: dict = {}
    if payload.aliases is not None:
        old_values["aliases"] = entity.aliases
        entity.aliases = payload.aliases
    if payload.show_as_project is not None:
        old_values["show_as_project"] = entity.show_as_project
        entity.show_as_project = payload.show_as_project

    db.commit()
    db.refresh(entity)

    log_event(
        db,
        action=AuditAction.UPDATE_ENTITY,
        actor_user_id=actor.id,
        target_type="entity",
        target_id=entity.id,
        metadata={"old": old_values, "new": payload.model_dump(exclude_none=True)},
    )
    return entity
