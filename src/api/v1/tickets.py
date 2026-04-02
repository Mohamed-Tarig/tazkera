import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.domain.loader import get_available_domains, load_domain_config
from src.models.ticket import Ticket
from src.schemas.ticket import TicketCreate, TicketRead

router = APIRouter(tags=["tickets"])


@router.get("/domains")
async def list_domains():
    """List all available domain configurations."""
    domains = get_available_domains()
    return {
        "domains": [
            {"id": d, "name": load_domain_config(d).domain.name}
            for d in domains
        ]
    }


@router.get("/domains/{domain_id}")
async def get_domain_config(domain_id: str):
    """Get full domain configuration."""
    try:
        config = load_domain_config(domain_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    return config.model_dump()


@router.post("/tickets", response_model=TicketRead, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new ticket."""
    # Generate ticket number
    count = await session.scalar(select(func.count(Ticket.id)))
    ticket_number = f"TZK-{count + 1:06d}"

    ticket = Ticket(
        ticket_number=ticket_number,
        domain_id=payload.domain_id,
        source_system=payload.source_system,
        source_ticket_id=payload.source_ticket_id,
        subject=payload.subject,
        description=payload.description,
        submitter_name=payload.submitter_name,
        submitter_email=payload.submitter_email,
        custom_fields=payload.custom_fields,
        status="new",
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    return ticket


@router.get("/tickets", response_model=list[TicketRead])
async def list_tickets(
    domain: str = Query(default=None),
    status: str = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(get_session),
):
    """List tickets with optional filters."""
    query = select(Ticket).order_by(Ticket.created_at.desc())

    if domain:
        query = query.where(Ticket.domain_id == domain)
    if status:
        query = query.where(Ticket.status == status)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/tickets/{ticket_id}", response_model=TicketRead)
async def get_ticket(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a single ticket by ID."""
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket