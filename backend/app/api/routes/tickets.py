from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.base import get_db
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate, TicketOut

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketOut, status_code=201)
async def submit_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("agent", "admin")),
) -> Ticket:
    result = await db.execute(
        select(Customer).where(Customer.masked_identifier == payload.customer_masked_identifier)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(masked_identifier=payload.customer_masked_identifier)
        db.add(customer)
        await db.flush()

    ticket = Ticket(
        customer_id=customer.id,
        channel=payload.channel,
        raw_text=payload.raw_text,
        status="new",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket
