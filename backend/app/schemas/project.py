from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    group_name: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    group_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True