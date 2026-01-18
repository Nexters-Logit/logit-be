from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CompanyCreate(BaseModel):
    """Schema for creating a company."""

    name: str
    talents: list[str] | None = None


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""

    name: str | None = None
    talents: list[str] | None = None


class CompanyRead(BaseModel):
    """Schema for reading a company."""

    id: UUID
    name: str
    talents: list[str] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
