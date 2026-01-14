from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ProjectBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    is_active: bool = Field(default=True)


class Project(ProjectBase, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
