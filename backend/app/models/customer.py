import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    masked_identifier: Mapped[str] = mapped_column(String, nullable=False)
    # Set only for seeded demo customers (Phase 7 customer portal) — real
    # agent-side customers stay NULL here. The portal's customer-list
    # endpoint filters on `display_name IS NOT NULL`, so this column is also
    # the boundary keeping real customer data out of the public demo surface.
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    account_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")
