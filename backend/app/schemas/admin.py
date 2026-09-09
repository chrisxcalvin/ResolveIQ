import uuid
from datetime import datetime

from pydantic import BaseModel


class CoachingRow(BaseModel):
    agent_id: uuid.UUID
    agent_email: str
    total_resolutions: int
    avg_edit_distance: float | None
    avg_resolution_minutes: float | None
    escalation_rate: float


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    event_type: str
    detail: dict
    actor: str
    created_at: datetime

    model_config = {"from_attributes": True}
