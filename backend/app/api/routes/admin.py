"""Feature 4 (coaching insights) + basic admin audit view.

Per 05_Backend_Schema.md: "edit_distance on ticket_resolutions is the core
input for the Feature 4 coaching view — aggregate it per agent, no new
backend logic required." This module is exactly that: read-only aggregation
over data Feature 1 already captures, nothing new is written here.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.base import get_db
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.models.user import User
from app.schemas.admin import AuditLogEntry, CoachingRow

router = APIRouter(prefix="/admin", tags=["admin"])

AUDIT_LOG_LIMIT = 100


@router.get("/coaching", response_model=list[CoachingRow])
async def coaching_insights(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
) -> list[CoachingRow]:
    resolution_minutes = func.extract(
        "epoch", TicketResolution.created_at - Ticket.created_at
    ) / 60

    stmt = (
        select(
            TicketResolution.agent_id,
            User.email,
            func.count(TicketResolution.id),
            func.avg(TicketResolution.edit_distance),
            func.avg(resolution_minutes),
            func.sum(case((TicketResolution.action == "escalated", 1), else_=0)),
        )
        .join(User, TicketResolution.agent_id == User.id)
        .join(Ticket, TicketResolution.ticket_id == Ticket.id)
        .group_by(TicketResolution.agent_id, User.email)
    )
    rows = (await db.execute(stmt)).all()

    return [
        CoachingRow(
            agent_id=agent_id,
            agent_email=email,
            total_resolutions=total,
            avg_edit_distance=float(avg_edit_distance) if avg_edit_distance is not None else None,
            avg_resolution_minutes=float(avg_minutes) if avg_minutes is not None else None,
            escalation_rate=escalated / total if total else 0.0,
        )
        for agent_id, email, total, avg_edit_distance, avg_minutes, escalated in rows
    ]


@router.get("/audit-log", response_model=list[AuditLogEntry])
async def audit_log(
    ticket_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("admin")),
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(AUDIT_LOG_LIMIT)
    if ticket_id is not None:
        stmt = stmt.where(AuditLog.ticket_id == ticket_id)
    return (await db.execute(stmt)).scalars().all()
