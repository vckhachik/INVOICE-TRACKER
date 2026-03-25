from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EntityCreate(BaseModel):
    name: str
    aliases: Optional[list] = None
    project_id_default: Optional[int] = None


class EntityResponse(BaseModel):
    id: int
    name: str
    aliases: Optional[list] = None
    project_id_default: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True