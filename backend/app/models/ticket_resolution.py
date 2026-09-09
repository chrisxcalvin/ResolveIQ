import uuid
from datetime import datetime

from sqlalchemy import Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ResolutionAction = Enum("approved", "edited", "escalated", name="resolution_action")


class TicketResolution(Base):
    __tablename__ = "ticket_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False)
    final_text: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(ResolutionAction, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    edit_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    escalation_note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
