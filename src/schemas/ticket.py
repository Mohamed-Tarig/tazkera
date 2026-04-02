import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    """What comes IN — from any adapter or webhook."""

    domain_id: str
    source_system: str = "webhook"
    source_ticket_id: str | None = None
    subject: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=10)
    submitter_name: str | None = None
    submitter_email: str | None = None
    custom_fields: dict = Field(default_factory=dict)


class TicketRead(BaseModel):
    """What goes OUT — API response."""

    id: uuid.UUID
    ticket_number: str
    domain_id: str
    source_system: str
    subject: str
    description: str
    submitter_name: str | None
    submitter_email: str | None
    custom_fields: dict
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClassificationRead(BaseModel):
    """Classification result — API response."""

    predicted_type: str
    predicted_department: str
    predicted_priority: str
    confidence_score: float
    reasoning: str | None
    model_version: str
    classified_at: datetime

    model_config = {"from_attributes": True}