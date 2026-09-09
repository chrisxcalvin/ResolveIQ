import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TicketCreate(BaseModel):
    customer_masked_identifier: str
    channel: str
    raw_text: str


class TicketOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    channel: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketListItem(BaseModel):
    id: uuid.UUID
    customer_masked_identifier: str
    channel: str
    category: str | None
    urgency_score: float | None
    breach_risk_score: float | None
    status: str
    created_at: datetime


class SourceOut(BaseModel):
    chunk_id: uuid.UUID
    document_title: str
    content: str


class DraftOut(BaseModel):
    id: uuid.UUID
    draft_text: str
    confidence: float | None
    sources: list[SourceOut]


class CustomerHistoryItem(BaseModel):
    id: uuid.UUID
    category: str | None
    status: str
    created_at: datetime


class TicketDetail(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_masked_identifier: str
    channel: str
    raw_text: str
    redacted_text: str | None
    category: str | None
    urgency_score: float | None
    breach_risk_score: float | None
    status: str
    created_at: datetime
    draft: DraftOut | None
    customer_history: list[CustomerHistoryItem]
    specialist_flagged: bool = False
    decision_reason: str | None = None


class ResolveRequest(BaseModel):
    action: Literal["approve", "edit", "escalate"]
    final_text: str | None = None
    escalation_note: str | None = None


class ResolveResponse(BaseModel):
    id: uuid.UUID
    status: str
    action: str
