import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text as sql_text

from src.database import async_session, engine
from src.models.ticket import KnowledgeBase
from src.services.embeddings import content_hash, get_embeddings_batch


async def embed_kb_articles():
    async with async_session() as session:
        # Get all articles without embeddings
        result = await session.execute(
            select(KnowledgeBase).where(KnowledgeBase.embedding.is_(None))
        )
        articles = result.scalars().all()

        if not articles:
            print("All articles already have embeddings.")
            return

        print(f"Generating embeddings for {len(articles)} articles...")

        # Prepare texts — combine title + content for richer embedding
        texts = [f"{a.title}\n{a.content}" for a in articles]

        # Batch embed (Azure supports up to 16 texts per call)
        batch_size = 16
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_articles = articles[i : i + batch_size]

            embeddings = get_embeddings_batch(batch_texts)

            for article, embedding in zip(batch_articles, embeddings):
                article.embedding = embedding

            print(f"  Embedded {min(i + batch_size, len(articles))}/{len(articles)}")

        await session.commit()
        print("Done! All KB articles embedded.")

async def embed_tickets():
    async with async_session() as session:
        # Get all tickets that don't have embeddings yet
        result = await session.execute(
            sql_text("""
                SELECT t.id, t.subject, t.description
                FROM tickets t
                LEFT JOIN ticket_embeddings te ON te.ticket_id = t.id
                WHERE te.id IS NULL
            """)
        )
        tickets = result.fetchall()

        if not tickets:
            print("All tickets already have embeddings.")
            return

        print(f"Generating embeddings for {len(tickets)} tickets...")

        batch_size = 16
        for i in range(0, len(tickets), batch_size):
            batch = tickets[i : i + batch_size]
            texts = [f"{t.subject}\n{t.description}" for t in batch]

            embeddings = get_embeddings_batch(texts)

            for ticket, embedding in zip(batch, embeddings):
                await session.execute(
                    sql_text("""
                        INSERT INTO ticket_embeddings (id, ticket_id, embedding, content_hash, created_at)
                        VALUES (:id, :ticket_id, CAST(:embedding AS vector), :hash, NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "ticket_id": str(ticket.id),
                        "embedding": str(embedding),
                        "hash": content_hash(f"{ticket.subject}\n{ticket.description}"),
                    },
                )

            print(f"  Embedded {min(i + batch_size, len(tickets))}/{len(tickets)}")

        await session.commit()
        print("Done! All tickets embedded.")

async def main():
    await embed_kb_articles()
    await embed_tickets()

if __name__ == "__main__":
    asyncio.run(main())