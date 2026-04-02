import json
import logging

from openai import AzureOpenAI
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.services.embeddings import get_embedding

logger = logging.getLogger(__name__)

client = AzureOpenAI(
    api_key=settings.azure_openai_api_key,
    api_version=settings.azure_openai_api_version,
    azure_endpoint=settings.azure_openai_endpoint,
)


async def find_similar_articles(
    session: AsyncSession,
    query_embedding: list[float],
    domain_id: str,
    limit: int = 5,
) -> list[dict]:
    """Find most similar KB articles using pgvector cosine similarity."""
    result = await session.execute(
        sql_text("""
            SELECT id, title, content, category,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM knowledge_base
            WHERE domain_id = :domain_id
              AND is_active = true
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """),
        {
            "embedding": str(query_embedding),
            "domain_id": domain_id,
            "limit": limit,
        },
    )
    rows = result.fetchall()
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "content": row.content,
            "category": row.category,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]


async def find_similar_tickets(
    session: AsyncSession,
    query_embedding: list[float],
    domain_id: str,
    exclude_ticket_id: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """Find similar past tickets that have been resolved."""
    query = """
        SELECT t.id, t.subject, t.description, t.custom_fields, t.status,
               1 - (te.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM ticket_embeddings te
        JOIN tickets t ON t.id = te.ticket_id
        WHERE t.domain_id = :domain_id
          AND t.status IN ('resolved', 'closed')
    """
    params = {
        "embedding": str(query_embedding),
        "domain_id": domain_id,
        "limit": limit,
    }

    if exclude_ticket_id:
        query += " AND t.id != :exclude_id"
        params["exclude_id"] = exclude_ticket_id

    query += " ORDER BY te.embedding <=> CAST(:embedding AS vector) LIMIT :limit"

    result = await session.execute(sql_text(query), params)
    rows = result.fetchall()
    return [
        {
            "id": str(row.id),
            "subject": row.subject,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]


async def generate_response(
    subject: str,
    description: str,
    classification: dict,
    articles: list[dict],
    domain_id: str,
) -> dict:
    """Use GPT-4o to generate a suggested response based on retrieved context."""

    # Build context from retrieved articles
    context_parts = []
    for i, article in enumerate(articles, 1):
        context_parts.append(
            f"[مرجع {i}] {article['title']}\n{article['content']}"
        )
    context = "\n\n---\n\n".join(context_parts) if context_parts else "لا توجد مراجع متاحة."

    prompt = f"""أنت موظف خدمة عملاء في هيئة الغذاء والدواء السعودية.
اكتب رد مقترح على التذكرة التالية مستخدماً المراجع المتوفرة.

## التذكرة
العنوان: {subject}
التفاصيل: {description}
التصنيف: {classification.get('request_type', 'غير محدد')}
القسم: {classification.get('department', 'غير محدد')}
الأولوية: {classification.get('priority', 'غير محدد')}

## المراجع المتوفرة
{context}

## التعليمات
- اكتب رداً رسمياً مهنياً باللغة العربية
- استخدم المعلومات من المراجع المتوفرة
- اذكر الخطوات المطلوبة بوضوح
- لا تختلق معلومات غير موجودة في المراجع
- ابدأ بالسلام والترحيب
- اختم بعبارة مناسبة

أرجع JSON بهذا الشكل:
{{
    "response_text": "نص الرد المقترح",
    "references_used": ["عناوين المراجع المستخدمة"],
    "confidence": 0.0-1.0,
    "needs_human_review": true/false,
    "review_reason": "سبب الحاجة لمراجعة بشرية إن وجد"
}}"""

    logger.info(f"Generating response for: {subject[:50]}...")

    response = client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {
                "role": "system",
                "content": "أنت مساعد ذكي لخدمة عملاء هيئة الغذاء والدواء. أجب بـ JSON فقط.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)

    return {
        "response_text": result.get("response_text", ""),
        "references_used": result.get("references_used", []),
        "confidence": float(result.get("confidence", 0.5)),
        "needs_human_review": result.get("needs_human_review", True),
        "review_reason": result.get("review_reason", ""),
        "articles_retrieved": len(articles),
    }