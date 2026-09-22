import uuid
from datetime import datetime

from pydantic import BaseModel


class PortalCustomer(BaseModel):
    id: uuid.UUID
    display_name: str
    account_reference: str | None

    model_config = {"from_attributes": True}


class PortalTicketCreate(BaseModel):
    customer_id: uuid.UUID
    subject: str
    description: str


class PortalTicketCreated(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PortalTicketStatus(BaseModel):
    id: uuid.UUID
    status: str
    category: str | None
    created_at: datetime
    # Only ever populated once status == "resolved" — an escalated ticket
    # has no reply actually sent to the customer, and every other internal
    # field (confidence, specialist routing, cited sources) stays off this
    # schema entirely, not just unset.
    final_reply: str | None


class PortalTicketListItem(BaseModel):
    id: uuid.UUID
    status: str
    category: str | None
    created_at: datetime
