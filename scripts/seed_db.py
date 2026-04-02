import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.generator import generate_kb_articles, generate_tickets
from src.database import async_session, engine
from src.models.ticket import Base, KnowledgeBase, Ticket


def _ticket_number(index: int) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    return f"TZK-{date_str}-{index:04d}"


async def seed():
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # --- Tickets ---
        tickets_data = generate_tickets(200)
        print(f"Generating {len(tickets_data)} tickets...")

        for i, t in enumerate(tickets_data, 1):
            ticket = Ticket(
                ticket_number=_ticket_number(i),
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

        # --- Knowledge Base ---
        articles = generate_kb_articles()
        print(f"Generating {len(articles)} KB articles...")

        for article in articles:
            kb = KnowledgeBase(
                domain_id=article["domain_id"],
                title=article["title"],
                content=article["content"],
                category=article["category"],
                is_active=article["is_active"],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(kb)

        await session.commit()
        print("Done! Database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())