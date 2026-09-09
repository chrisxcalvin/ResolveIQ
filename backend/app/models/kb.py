import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

KbSourceType = Enum("help_doc", "resolved_ticket", name="kb_source_type")

# sentence-transformers all-MiniLM-L6-v2 output dimension.
EMBEDDING_DIM = 384


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(KbSourceType, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chunks: Mapped[list["KbChunk"]] = relationship(back_populates="document")


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kb_documents.id"), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    retrieval_boost: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    times_retrieved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    times_corrected_against: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    document: Mapped["KbDocument"] = relationship(back_populates="chunks")
