import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.odoo import OdooAdapter
from src.database import get_session
from src.models.ticket import Ticket, TicketClassification
from src.schemas.ticket import TicketRead

router = APIRouter(prefix="/odoo", tags=["odoo"])
adapter = OdooAdapter()


@router.get("/health")
async def odoo_health():
    """Check Odoo connection."""
    ok = await adapter.verify_connection()
    if not ok:
        raise HTTPException(status_code=503, detail="Cannot connect to Odoo")
    return {"status": "connected", "project": adapter.project_name}


@router.post("/sync-in", response_model=list[TicketRead])
async def sync_from_odoo(
    session: AsyncSession = Depends(get_session),
):
    """Pull new tickets from Odoo, classify them, and save."""
    from src.workflows.intake import intake_graph
    from src.models.ticket import TicketClassification
    from sqlalchemy import func

    # Fetch new tasks from Odoo
    new_tickets = await adapter.fetch_new_tickets()
    if not new_tickets:
        return []

    created = []
    for t in new_tickets:
        # Check if already imported
        existing = await session.execute(
            select(Ticket).where(
                Ticket.source_system == "odoo",
                Ticket.source_ticket_id == t.source_ticket_id,
            )
        )
        if existing.scalars().first():
            continue

        # Generate ticket number
        count = await session.scalar(select(func.count(Ticket.id)))
        ticket = Ticket(
            ticket_number=f"TZK-{count + 1:06d}",
            domain_id=t.domain_id,
            source_system=t.source_system,
            source_ticket_id=t.source_ticket_id,
            subject=t.subject,
            description=t.description,
            submitter_name=t.submitter_name,
            submitter_email=t.submitter_email,
            custom_fields=t.custom_fields,
            status="new",
        )
        session.add(ticket)
        await session.flush()

        # Run classification pipeline
        result = intake_graph.invoke({
            "ticket_id": str(ticket.id),
            "domain_id": ticket.domain_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "custom_fields": ticket.custom_fields or {},
            "classification": {},
            "status": "",
            "error": "",
        })

        if result["status"] == "routed":
            cls = result["classification"]
            classification = TicketClassification(
                ticket_id=ticket.id,
                domain_id=ticket.domain_id,
                predicted_type=cls["request_type"],
                predicted_department=cls["department"],
                predicted_priority=cls["priority"],
                confidence_score=cls["confidence"],
                reasoning=cls.get("reasoning"),
                model_version=cls.get("model_version", "unknown"),
            )
            session.add(classification)
            ticket.status = "classified"

        created.append(ticket)

    await session.commit()
    return created


@router.post("/sync-back/{ticket_id}")
async def sync_to_odoo(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Push classification + suggested response back to Odoo."""
    ticket = await session.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.source_system != "odoo":
        raise HTTPException(status_code=400, detail="Ticket is not from Odoo")
    if not ticket.source_ticket_id:
        raise HTTPException(status_code=400, detail="No Odoo task ID")

    # Get classification
    cls_result = await session.execute(
        select(TicketClassification)
        .where(TicketClassification.ticket_id == ticket_id)
        .order_by(TicketClassification.classified_at.desc())
    )
    classification_row = cls_result.scalars().first()

    classification = {}
    if classification_row:
        classification = {
            "request_type": classification_row.predicted_type,
            "department": classification_row.predicted_department,
            "priority": classification_row.predicted_priority,
            "confidence": classification_row.confidence_score,
        }

    # Generate response suggestion
    from src.services.embeddings import get_embedding
    from src.services.rag import find_similar_articles, generate_response

    query_embedding = get_embedding(f"{ticket.subject}\n{ticket.description}")
    articles = await find_similar_articles(
        session=session,
        query_embedding=query_embedding,
        domain_id=ticket.domain_id,
        limit=5,
    )

    suggestion = await generate_response(
        subject=ticket.subject,
        description=ticket.description,
        classification=classification,
        articles=articles,
        domain_id=ticket.domain_id,
    )

    # Sync back to Odoo
    success = await adapter.sync_back(
        ticket_id=ticket.source_ticket_id,
        updates={"classification": classification, "suggestion": suggestion},
    )

    if not success:
        raise HTTPException(status_code=502, detail="Failed to sync back to Odoo")

    ticket.status = "routed"
    await session.commit()

    return {
        "ticket_id": str(ticket.id),
        "odoo_task_id": ticket.source_ticket_id,
        "synced": True,
        "classification": classification,
    }