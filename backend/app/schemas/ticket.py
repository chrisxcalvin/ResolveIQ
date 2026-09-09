import uuid
from datetime import datetime

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
