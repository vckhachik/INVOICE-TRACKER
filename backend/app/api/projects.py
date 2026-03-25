from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Project

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/")
def get_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()

@router.post("/")
def create_project(name: str, group_name: str = None, db: Session = Depends(get_db)):
    project = Project(name=name, group_name=group_name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project