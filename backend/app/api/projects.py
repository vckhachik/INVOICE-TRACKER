from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.models.models import Project, User
from app.core.deps import current_user
from app.core.permissions import require_permission, Permission
from app.core.audit import log_event, AuditAction
from app.schemas.project import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("/", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db), actor: User = Depends(current_user)):
    return db.query(Project).all()


@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(Permission.MANAGE_MAPPINGS)),
):
    new_project = Project(
        name=project.name,
        group_name=project.group_name,
        description=project.description,
        source_entity_id=project.source_entity_id,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    log_event(
        db,
        action=AuditAction.CREATE_PROJECT,
        actor_user_id=actor.id,
        target_type="project",
        target_id=new_project.id,
        metadata={"name": new_project.name, "group_name": new_project.group_name},
    )
    return new_project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db), actor: User = Depends(current_user)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
